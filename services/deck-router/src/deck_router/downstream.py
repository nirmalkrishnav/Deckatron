"""Discover and call existing services through the official A2A client."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientError
from a2a.types import AgentCard
from a2a.utils.errors import InternalError

from deck_router.selection import Target
from deck_router.utils.settings import Settings

logger = logging.getLogger(__name__)


class Downstream:
    """Use only environment-configured destinations, not user- or LLM-supplied URLs."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def discover(self, target: Target) -> AgentCard:
        """Load a card and constrain its JSON-RPC endpoint to the configured origin."""
        endpoint = self.settings.creator_url if target == "create" else self.settings.editor_url
        if endpoint is None:
            variable = "DECK_ROUTER_CREATOR_URL" if target == "create" else "DECK_ROUTER_EDITOR_URL"
            raise InternalError(message=f"Configure {variable} in the root .env")

        try:
            card = await A2ACardResolver(self.http_client, base_url=str(endpoint)).get_agent_card()
        except (A2AClientError, httpx.HTTPError, ValueError) as error:
            logger.error("Agent Card discovery failed for %s (%s)", target, type(error).__name__)
            raise InternalError(message=f"Could not discover the {target} A2A service") from error

        origin = httpx.URL(str(endpoint))
        safe_card = AgentCard()
        safe_card.CopyFrom(card)
        del safe_card.supported_interfaces[:]
        for interface in card.supported_interfaces:
            try:
                parsed = urlsplit(interface.url)
                url = httpx.URL(interface.url)
            except (httpx.InvalidURL, ValueError):
                continue
            if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
                continue
            if (
                interface.protocol_binding == "JSONRPC"
                and (url.scheme, url.host, url.port) == (origin.scheme, origin.host, origin.port)
                and not parsed.fragment
            ):
                safe_card.supported_interfaces.append(interface)
        if not safe_card.supported_interfaces or not safe_card.skills:
            raise InternalError(
                message=f"The {target} Agent Card must expose skills "
                "and a same-origin JSON-RPC endpoint"
            )
        return safe_card

    @asynccontextmanager
    async def connect(
        self, target: Target, card: AgentCard | None = None
    ) -> AsyncGenerator[Client, None]:
        """Close the A2A client after each call while reusing the HTTP connection pool."""
        card = card if card is not None else await self.discover(target)
        try:
            client = ClientFactory(
                ClientConfig(
                    streaming=False,
                    httpx_client=self.http_client,
                    supported_protocol_bindings=["JSONRPC"],
                )
            ).create(card)
            async with client:
                yield client
        except (A2AClientError, httpx.HTTPError, ValueError) as error:
            logger.error("Downstream %s call failed (%s)", target, type(error).__name__)
            raise InternalError(message=f"The {target} A2A service call failed") from error
