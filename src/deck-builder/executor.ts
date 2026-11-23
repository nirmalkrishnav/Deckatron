import { randomUUID } from "node:crypto";
import { type Message, Role } from "@a2a-js/sdk";
import { RequestMalformedError, UnsupportedOperationError } from "@a2a-js/sdk/errors";
import {
  AgentEvent,
  type AgentExecutor,
  type ExecutionEventBus,
  type RequestContext,
} from "@a2a-js/sdk/server";
import { DeckBuildResult } from "./result.js";

/** Join user text unchanged; reject absent, blank, or non-user instructions. */
export function getDeckRequest(message: Message | undefined): string {
  const request = message?.parts
    .flatMap((part) => part.content?.$case === "text" ? [part.content.value] : [])
    .join("\n") ?? "";
  if (message?.role !== Role.ROLE_USER || !request.trim()) {
    throw new RequestMalformedError("Provide a user message with nonempty deck instructions");
  }
  return request;
}

/** Publishes immediate placeholder data without processing attachments or creating tasks. */
export class DeckBuilderExecutor implements AgentExecutor {
  /** Reject invalid user text; preserve accepted text parts in their original order. */
  async execute(context: RequestContext, eventBus: ExecutionEventBus): Promise<void> {
    const result = new DeckBuildResult(getDeckRequest(context.userMessage));
    const message: Message = {
      messageId: randomUUID(),
      role: Role.ROLE_AGENT,
      contextId: context.contextId,
      taskId: "",
      parts: [{
        content: { $case: "data", value: result.toJSON() },
        filename: "",
        mediaType: "application/json",
        metadata: undefined,
      }],
      metadata: undefined,
      extensions: [],
      referenceTaskIds: [],
    };
    eventBus.publish(AgentEvent.message(message));
  }

  /** No asynchronous jobs exist; cancellation is never a successful operation. */
  async cancelTask(): Promise<void> {
    throw new UnsupportedOperationError("The deck-builder placeholder has no running tasks");
  }
}
