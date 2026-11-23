"""A2A routing and task relay without local workflow or PPTX generation state."""

import asyncio
from collections.abc import AsyncGenerator

from a2a.helpers import new_text_message
from a2a.server.context import ServerCallContext
from a2a.server.events import Event
from a2a.server.request_handlers import RequestHandler
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    DeleteTaskPushNotificationConfigRequest,
    GetExtendedAgentCardRequest,
    GetTaskPushNotificationConfigRequest,
    GetTaskRequest,
    ListTaskPushNotificationConfigsRequest,
    ListTaskPushNotificationConfigsResponse,
    ListTasksRequest,
    ListTasksResponse,
    Message,
    Role,
    SendMessageRequest,
    SubscribeToTaskRequest,
    Task,
    TaskPushNotificationConfig,
)
from a2a.utils.errors import (
    InternalError,
    InvalidParamsError,
    PushNotificationNotSupportedError,
    UnsupportedOperationError,
)
from a2a.utils.proto_utils import validate_proto_required_fields

from deck_router.downstream import Downstream
from deck_router.identifiers import (
    bound_target,
    decode_id,
    unwrap_message,
    wrap_message,
    wrap_task,
)
from deck_router.selection import Selector, Target


class RouterHandler(RequestHandler):
    """Select a downstream agent on new requests and retain affinity on follow-ups."""

    def __init__(self, downstream: Downstream, selector: Selector) -> None:
        self.downstream = downstream
        self.selector = selector

    async def on_message_send(
        self, params: SendMessageRequest, context: ServerCallContext
    ) -> Message | Task:
        """Forward original parts and configuration; relay messages or input-required tasks."""
        validate_proto_required_fields(params)
        if params.message.role != Role.ROLE_USER or not params.message.parts:
            raise InvalidParamsError(message="Provide a user message with API request parts")
        if params.configuration.HasField("task_push_notification_config"):
            raise PushNotificationNotSupportedError

        target = bound_target(params.message)
        cards: dict[Target, AgentCard] = {}
        if target is None:
            text = "\n".join(part.text for part in params.message.parts if part.HasField("text"))
            if not text.strip() or len(text) > 16000:
                raise InvalidParamsError(
                    message="New routing requests require "
                    "1 to 16000 characters of text instructions"
                )
            creator, editor = await asyncio.gather(
                self.downstream.discover("create"), self.downstream.discover("edit")
            )
            cards = {"create": creator, "edit": editor}
            decision = await self.selector.choose(params.message, cards)
            if decision.target == "clarify":
                if not decision.question:
                    raise InternalError(message="The routing clarification is missing its question")
                return new_text_message(
                    decision.question,
                    role=Role.ROLE_AGENT,
                    context_id=params.message.context_id or None,
                )
            target = decision.target

        outgoing = SendMessageRequest()
        outgoing.CopyFrom(params)
        unwrap_message(outgoing.message, target)
        async with self.downstream.connect(target, cards.get(target)) as client:
            async for event in client.send_message(outgoing):
                if event.HasField("task"):
                    return wrap_task(event.task, target)
                if event.HasField("message"):
                    message = Message()
                    message.CopyFrom(event.message)
                    wrap_message(message, target)
                    return message
        raise InternalError(message="Downstream service returned no message or task")

    async def on_get_task(self, params: GetTaskRequest, context: ServerCallContext) -> Task:
        """Poll the owning service without invoking the LLM again."""
        validate_proto_required_fields(params)
        target, raw_id = decode_id(params.id)
        outgoing = GetTaskRequest()
        outgoing.CopyFrom(params)
        outgoing.id = raw_id
        async with self.downstream.connect(target) as client:
            return wrap_task(await client.get_task(outgoing), target)

    async def on_cancel_task(self, params: CancelTaskRequest, context: ServerCallContext) -> Task:
        """Relay cancellation to the service that owns the returned task ID."""
        validate_proto_required_fields(params)
        target, raw_id = decode_id(params.id)
        outgoing = CancelTaskRequest()
        outgoing.CopyFrom(params)
        outgoing.id = raw_id
        async with self.downstream.connect(target) as client:
            return wrap_task(await client.cancel_task(outgoing), target)

    async def on_list_tasks(
        self, params: ListTasksRequest, context: ServerCallContext
    ) -> ListTasksResponse:
        """Do not pretend to aggregate task stores belonging to separate services."""
        raise UnsupportedOperationError(message="Use GetTask with a returned router task ID")

    async def on_message_send_stream(
        self, params: SendMessageRequest, context: ServerCallContext
    ) -> AsyncGenerator[Event, None]:
        """Streaming is not advertised by this router."""
        raise UnsupportedOperationError(message="Use non-streaming SendMessage")
        yield

    async def on_subscribe_to_task(
        self, params: SubscribeToTaskRequest, context: ServerCallContext
    ) -> AsyncGenerator[Event, None]:
        """Use polling rather than subscriptions for downstream tasks."""
        raise UnsupportedOperationError(message="Use GetTask to poll downstream tasks")
        yield

    async def on_create_task_push_notification_config(
        self, params: TaskPushNotificationConfig, context: ServerCallContext
    ) -> TaskPushNotificationConfig:
        """Push callbacks are not relayed by this router."""
        raise PushNotificationNotSupportedError

    async def on_get_task_push_notification_config(
        self, params: GetTaskPushNotificationConfigRequest, context: ServerCallContext
    ) -> TaskPushNotificationConfig:
        """Push callbacks are not relayed by this router."""
        raise PushNotificationNotSupportedError

    async def on_list_task_push_notification_configs(
        self, params: ListTaskPushNotificationConfigsRequest, context: ServerCallContext
    ) -> ListTaskPushNotificationConfigsResponse:
        """Push callbacks are not relayed by this router."""
        raise PushNotificationNotSupportedError

    async def on_delete_task_push_notification_config(
        self, params: DeleteTaskPushNotificationConfigRequest, context: ServerCallContext
    ) -> None:
        """Push callbacks are not relayed by this router."""
        raise PushNotificationNotSupportedError

    async def on_get_extended_agent_card(
        self, params: GetExtendedAgentCardRequest, context: ServerCallContext
    ) -> AgentCard:
        """Only the public router card is available."""
        raise UnsupportedOperationError(
            message="No authenticated extended Agent Card is configured"
        )
