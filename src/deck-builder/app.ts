import {
  A2A_PROTOCOL_VERSION, AGENT_CARD_PATH, type AgentCard, type Message,
  type SendMessageRequest, type Task,
} from "@a2a-js/sdk";
import { UnsupportedOperationError } from "@a2a-js/sdk/errors";
import {
  DefaultRequestHandler, InMemoryTaskStore, type ServerCallContext,
} from "@a2a-js/sdk/server";
import { agentCardHandler, jsonRpcHandler, UserBuilder } from "@a2a-js/sdk/server/express";
import express, { type Express } from "express";
import { DeckBuilderExecutor, getDeckRequest } from "./executor.js";

/** Validate before the SDK converts executor rejections into failed tasks with input history. */
class DeckBuilderRequestHandler extends DefaultRequestHandler {
  override async sendMessage(
    params: SendMessageRequest, context: ServerCallContext,
  ): Promise<Message | Task> {
    getDeckRequest(params.message);
    return super.sendMessage(params, context);
  }

  override async *sendMessageStream(): AsyncGenerator<never, void, undefined> {
    throw new UnsupportedOperationError("Use non-streaming SendMessage");
  }

  override async listTasks(): Promise<never> {
    throw new UnsupportedOperationError("The deck-builder placeholder has no tasks to list");
  }
}

/**
 * Construct a local-only A2A application without opening a listener.
 * @param port - Advertised loopback port, an integer from 1 to 65535.
 * @throws RangeError for an invalid port. The caller owns the HTTP listener.
 */
export function createApp(port = 8001): Express {
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new RangeError("DECK_BUILDER_PORT must be an integer from 1 to 65535");
  }
  const card: AgentCard = {
    name: "deck-builder",
    description: "Deck creation placeholder. Accepts requests but does not generate presentations.",
    version: "0.1.0",
    supportedInterfaces: [{
      url: `http://127.0.0.1:${port}/`,
      protocolBinding: "JSONRPC",
      protocolVersion: A2A_PROTOCOL_VERSION,
      tenant: "",
    }],
    provider: undefined,
    capabilities: {
      streaming: false,
      pushNotifications: false,
      extendedAgentCard: false,
      extensions: [],
    },
    securitySchemes: {},
    securityRequirements: [],
    defaultInputModes: ["text/plain", "application/json", "application/octet-stream"],
    defaultOutputModes: ["application/json"],
    skills: [{
      id: "create-deck",
      name: "Deck creation placeholder",
      description: "Receive new-deck requests and acknowledge them; PPTX generation is not implemented.",
      tags: ["create", "deck", "placeholder"],
      examples: ["Create a deck about quarterly sales."],
      inputModes: [],
      outputModes: [],
      securityRequirements: [],
    }],
    signatures: [],
  };
  const handler = new DeckBuilderRequestHandler(
    card, new InMemoryTaskStore(), new DeckBuilderExecutor(),
  );
  const app = express();
  app.get("/ping", (_request, response) => {
    response.type("text/plain").send("pong");
  });
  app.use(`/${AGENT_CARD_PATH}`, agentCardHandler({ agentCardProvider: handler }));
  app.use("/", jsonRpcHandler({ requestHandler: handler, userBuilder: UserBuilder.noAuthentication }));
  return app;
}
