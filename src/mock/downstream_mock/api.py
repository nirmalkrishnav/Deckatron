"""Local A2A echo downstream; never creates or edits PPTX files."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from a2a.helpers import new_data_part, new_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Part, Role
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from a2a.utils.errors import InvalidParamsError, UnsupportedOperationError
from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route


class EchoExecutor(AgentExecutor):
    """Return the user's text and an explicit mock-success contract."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Echo text only; attachments are neither processed nor regenerated."""
        message = context.message
        query = context.get_user_input()
        if message is None or message.role != Role.ROLE_USER or not query.strip():
            raise InvalidParamsError(message="Provide a user message with text to echo")
        await event_queue.enqueue_event(
            new_message(
                parts=[
                    Part(text=f"Mock success: {query}"),
                    new_data_part({"status": "success", "mock": True, "query": query}),
                ],
                context_id=context.context_id,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """The mock returns immediate messages and has no long-running jobs."""
        raise UnsupportedOperationError(message="The echo mock has no running job to cancel")


def create_app() -> Starlette:
    """Build a standalone mock usable as both creator and editor downstreams."""
    card = AgentCard(
        name="deck-downstream-mock",
        description="Local mock for deck creation and editing; echoes queries without making PPTX.",
        version="0.1.0",
        capabilities=AgentCapabilities(),
        default_input_modes=["text/plain", "application/json", "application/octet-stream"],
        default_output_modes=["text/plain", "application/json"],
        supported_interfaces=[
            AgentInterface(
                url="http://127.0.0.1:8001/",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        skills=[
            AgentSkill(
                id="create-deck",
                name="Mock deck creation",
                description="Accept requests for a new PPTX from data and a storyline; echo only.",
                tags=["create", "pptx", "mock"],
            ),
            AgentSkill(
                id="edit-deck",
                name="Mock deck editing",
                description="Accept requests to inspect or edit an existing PPTX; echo only.",
                tags=["edit", "pptx", "mock"],
            ),
        ],
    )
    handler = DefaultRequestHandler(
        agent_executor=EchoExecutor(), task_store=InMemoryTaskStore(), agent_card=card
    )

    async def discover(request: Request) -> JSONResponse:
        """Advertise the actual request origin so any local port can be used."""
        response_card = AgentCard()
        response_card.CopyFrom(card)
        response_card.supported_interfaces[0].url = str(request.base_url)
        return JSONResponse(MessageToDict(response_card))

    async def ping(request: Request) -> PlainTextResponse:
        """Expose a local health check without invoking a model."""
        return PlainTextResponse("pong")

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            await handler.aclose()

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/ping", ping, methods=["GET"]),
            Route(AGENT_CARD_WELL_KNOWN_PATH, discover, methods=["GET"]),
            *create_jsonrpc_routes(handler, rpc_url="/"),
        ],
    )


app = create_app()
