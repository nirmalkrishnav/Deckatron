"""Uvicorn application factory for the deck-router A2A service."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from deck_router.downstream import Downstream
from deck_router.handler import RouterHandler
from deck_router.selection import AzureSelector, DecisionSelector, Selector
from deck_router.utils import DecisionClient, LLMClient
from deck_router.utils.settings import Settings


async def ping(request: Request) -> PlainTextResponse:
    """Return a lightweight HTTP liveness response without invoking A2A."""
    return PlainTextResponse("pong")


def create_app(
    settings: Settings | None = None,
    *,
    selector: Selector | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> Starlette:
    """Build the router; dependency injection keeps tests independent of real services."""
    settings = settings if settings is not None else Settings()
    owns_http_client = http_client is None
    http_client = (
        http_client
        if http_client is not None
        else httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=False)
    )
    if selector is None:
        selector = (
            DecisionSelector(DecisionClient())
            if settings.selector == "decision"
            else AzureSelector(LLMClient())
        )
    card = AgentCard(
        name="deck-router",
        description="Routes API requests to existing deck creation or layout editing A2A services.",
        version="0.1.0",
        default_input_modes=["text/plain", "application/json", "application/octet-stream"],
        default_output_modes=["text/plain", "application/json", "application/octet-stream"],
        capabilities=AgentCapabilities(),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=str(settings.public_url),
            )
        ],
        skills=[
            AgentSkill(
                id="route_deck_request",
                name="Route deck request",
                description=(
                    "Uses a configured model to choose a creation or editing A2A service, "
                    "forwards user text, structured data and files, and relays its response. "
                    "Editing follow-up instructions are supplied through subsequent API requests."
                ),
                tags=["routing", "pptx", "create", "edit"],
                examples=[
                    "Create a PPTX using this JSON datasource and storyline.",
                    "Inspect this PPTX layout so I can provide editing instructions.",
                ],
            )
        ],
    )
    handler = RouterHandler(Downstream(settings, http_client), selector)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            if owns_http_client:
                await http_client.aclose()

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/ping", ping, methods=["GET"]),
            *create_agent_card_routes(card),
            *create_jsonrpc_routes(handler, rpc_url="/"),
        ],
    )
