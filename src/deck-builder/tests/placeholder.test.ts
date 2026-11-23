import assert from "node:assert/strict";
import { once } from "node:events";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createApp } from "../app.js";
import { DeckBuildResult } from "../index.js";

const server = createServer();
let origin: string;

before(async () => {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert(address && typeof address !== "string");
  origin = `http://127.0.0.1:${address.port}`;
  server.on("request", createApp(address.port));
});

after(async () => {
  server.closeAllConnections();
  await new Promise<void>((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
});

function assertObject(value: unknown): asserts value is Record<string, unknown> {
  assert(value !== null && typeof value === "object" && !Array.isArray(value));
}

async function rpc(method: string, params: unknown): Promise<Record<string, unknown>> {
  const response = await fetch(origin, {
    method: "POST",
    headers: { "Content-Type": "application/json", "A2A-Version": "1.0" },
    body: JSON.stringify({ jsonrpc: "2.0", id: "test-request", method, params }),
    signal: AbortSignal.timeout(5000),
  });
  assert.equal(response.status, 200);
  const envelope: unknown = await response.json();
  assertObject(envelope);
  return envelope;
}

test("discovery advertises the actual origin and only placeholder creation", async () => {
  const response = await fetch(`${origin}/.well-known/agent-card.json`, {
    signal: AbortSignal.timeout(5000),
  });
  assert.equal(response.status, 200);
  const card: unknown = await response.json();
  assertObject(card);
  assert(Array.isArray(card.supportedInterfaces));
  assert.equal(card.supportedInterfaces.length, 1);
  const advertised: unknown = card.supportedInterfaces[0];
  assertObject(advertised);
  assert.equal(advertised.url, `${origin}/`);
  assert.equal(advertised.protocolBinding, "JSONRPC");
  assert.equal(advertised.protocolVersion, "1.0");
  assert(Array.isArray(card.skills));
  assert.equal(card.skills.length, 1);
  const skill: unknown = card.skills[0];
  assertObject(skill);
  assert.equal(skill.id, "create-deck");
  assert.match(String(skill.description), /not implemented/i);
  assertObject(card.capabilities);
  assert.equal(card.capabilities.streaming, false);
  assert.equal(card.capabilities.pushNotifications, false);
  assert.deepEqual(card.defaultOutputModes, ["application/json"]);
  const health = await fetch(`${origin}/ping`, { signal: AbortSignal.timeout(5000) });
  assert.equal(health.status, 200);
  assert.equal(await health.text(), "pong");
});

test("mixed parts yield exactly one typed placeholder result with unchanged text", async () => {
  const request = " Create a deck \nabout sales.\n";
  assert(new DeckBuildResult(request) instanceof DeckBuildResult);
  const envelope = await rpc("SendMessage", {
    message: {
      messageId: "mixed-parts",
      contextId: "original-context",
      role: "ROLE_USER",
      parts: [
        { text: " Create a deck " },
        { data: { privateDatasource: "must-not-be-echoed" } },
        { filename: "source.pptx", raw: "b3BhcXVl" },
        { url: "http://127.0.0.1:1/do-not-fetch" },
        { text: "about sales.\n" },
      ],
    },
  });
  assert.equal(envelope.error, undefined);
  assertObject(envelope.result);
  assert.equal(envelope.result.task, undefined);
  assertObject(envelope.result.message);
  const message = envelope.result.message;
  assert.equal(message.role, "ROLE_AGENT");
  assert.equal(message.contextId, "original-context");
  assert.equal(typeof message.messageId, "string");
  assert(message.messageId);
  assert.equal(message.taskId, undefined);
  assert.deepEqual(message.parts, [{
    data: {
      status: "placeholder",
      request,
      message: "Deck generation is not implemented. No presentation was created.",
    },
    mediaType: "application/json",
  }]);
});

test("blank instructions produce a JSON-RPC error without a failed task", async () => {
  const envelope = await rpc("SendMessage", {
    message: { messageId: "blank", role: "ROLE_USER", parts: [{ text: " \n\t" }] },
  });
  assertObject(envelope.error);
  assert.equal(envelope.error.code, -32602);
  assert.equal(envelope.result, undefined);
});

test("non-user messages produce a JSON-RPC error without a result", async () => {
  const envelope = await rpc("SendMessage", {
    message: { messageId: "agent", role: "ROLE_AGENT", parts: [{ text: "Create a deck" }] },
  });
  assertObject(envelope.error);
  assert.equal(envelope.error.code, -32602);
  assert.equal(envelope.result, undefined);
});

test("an invalid configured port fails startup instead of selecting the default", () => {
  const result = spawnSync(process.execPath, [
    fileURLToPath(new URL("../server.js", import.meta.url)),
  ], {
    env: { ...process.env, DECK_BUILDER_PORT: "0" },
    encoding: "utf8",
    timeout: 5000,
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /DECK_BUILDER_PORT must be an integer from 1 to 65535/);
  assert.doesNotMatch(result.stdout, /listening/);
});

test("the start command loads the common root dotenv from the package directory", () => {
  const root = mkdtempSync(join(tmpdir(), "deck-builder-env-"));
  try {
    const packageDirectory = join(root, "src", "deck-builder");
    mkdirSync(packageDirectory, { recursive: true });
    writeFileSync(join(root, ".env"), "DECK_BUILDER_PORT=0\n");
    const manifest: unknown = JSON.parse(
      readFileSync(new URL("../../package.json", import.meta.url), "utf8"),
    );
    assertObject(manifest);
    assertObject(manifest.scripts);
    assert(typeof manifest.scripts.start === "string");
    const command = manifest.scripts.start.split(" ");
    assert.equal(command.shift(), "node");
    command[command.length - 1] = fileURLToPath(new URL("../server.js", import.meta.url));
    const env = { ...process.env };
    delete env.DECK_BUILDER_PORT;
    const result = spawnSync(process.execPath, command, {
      cwd: packageDirectory,
      env,
      encoding: "utf8",
      timeout: 5000,
    });
    assert.equal(result.error, undefined);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /DECK_BUILDER_PORT must be an integer from 1 to 65535/);
    assert.doesNotMatch(result.stdout, /listening/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("task listing is unsupported rather than a successful placeholder", async () => {
  const envelope = await rpc("ListTasks", {});
  assertObject(envelope.error);
  assert.equal(typeof envelope.error.code, "number");
  assert.equal(envelope.result, undefined);
});
