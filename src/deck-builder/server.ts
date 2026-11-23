import { createServer } from "node:http";
import { createApp } from "./app.js";

const configuredPort = process.env.DECK_BUILDER_PORT;
if (configuredPort !== undefined && !/^\d+$/.test(configuredPort)) {
  throw new RangeError("DECK_BUILDER_PORT must be an integer from 1 to 65535");
}
const port = configuredPort === undefined ? 8001 : Number(configuredPort);
const server = createServer(createApp(port));
server.on("error", (error: NodeJS.ErrnoException) => {
  console.error("Deck builder could not start:", error.code ?? error.name);
  process.exitCode = 1;
});
server.listen(port, "127.0.0.1", () => {
  console.info(`Deck-builder placeholder listening at http://127.0.0.1:${port}`);
});
