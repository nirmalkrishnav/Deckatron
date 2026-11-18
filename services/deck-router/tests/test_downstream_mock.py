"""Exercise the runnable echo mock directly and through the real A2A router."""

import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass

import httpx
import pytest
from a2a.types import AgentCard, Message
from deck_router.app import create_app as create_router_app
from deck_router.identifiers import decode_id
from deck_router.selection import RouteDecision, Target
from deck_router.utils.settings import Settings
from downstream_mock.api import create_app
from pydantic import HttpUrl
from starlette.testclient import TestClient


def request_body() -> dict:
    """Provide multiline text and an attachment that the mock must not process."""
    return {
        "jsonrpc": "2.0",
        "id": "echo-request",
        "method": "SendMessage",
        "params": {
            "message": {
                "messageId": "echo-message",
                "role": "ROLE_USER",
                "parts": [
                    {"text": "Create a deck"},
                    {"text": "about quarterly sales."},
                    {"filename": "source.pptx", "raw": "b3BhcXVl"},
                ],
            }
        },
    }


def test_given_mock_when_discovered_then_advertises_actual_origin_and_both_skills() -> None:
    with TestClient(create_app(), base_url="http://mock.test:9123") as client:
        card = client.get("/.well-known/agent-card.json").json()

        assert card["supportedInterfaces"][0]["url"] == "http://mock.test:9123/"
        assert {skill["id"] for skill in card["skills"]} == {"create-deck", "edit-deck"}
        assert client.get("/ping").text == "pong"


def test_given_query_when_sent_to_mock_then_returns_success_contract_and_exact_text() -> None:
    with TestClient(create_app(), headers={"A2A-Version": "1.0"}) as client:
        response = client.post("/", json=request_body())

    assert response.status_code == 200
    message = response.json()["result"]["message"]
    query = "Create a deck\nabout quarterly sales."
    assert message["parts"] == [
        {"text": f"Mock success: {query}"},
        {"data": {"status": "success", "mock": True, "query": query}},
    ]


@dataclass
class FixedSelector:
    """Keep router integration tests independent of real model credentials."""

    target: Target

    async def choose(self, message: Message, cards: Mapping[Target, AgentCard]) -> RouteDecision:
        assert set(cards) == {"create", "edit"}
        return RouteDecision(target=self.target, question=None)


@pytest.mark.parametrize("target", ["create", "edit"])
def test_given_same_mock_for_both_downstreams_when_router_forwards_then_relays_echo(
    target: Target,
) -> None:
    async def run() -> None:
        mock_app = create_app()
        async with mock_app.router.lifespan_context(mock_app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mock_app)) as downstream:
                router_app = create_router_app(
                    Settings(
                        creator_url=HttpUrl("http://mock.test:9123"),
                        editor_url=HttpUrl("http://mock.test:9123"),
                        _env_file=None,
                    ),
                    selector=FixedSelector(target),
                    http_client=downstream,
                )
                async with router_app.router.lifespan_context(router_app):
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=router_app),
                        base_url="http://router.test",
                        headers={"A2A-Version": "1.0"},
                    ) as client:
                        response = await client.post("/", json=request_body())

        assert response.status_code == 200
        envelope = response.json()
        assert "error" not in envelope
        message = envelope["result"]["message"]
        assert message["parts"][1]["data"] == {
            "status": "success",
            "mock": True,
            "query": "Create a deck\nabout quarterly sales.",
        }
        assert decode_id(message["contextId"])[0] == target

    asyncio.run(run())


@pytest.mark.skipif(
    os.environ.get("DECK_ROUTER_LIVE_DECISION_TESTS") != "1",
    reason="Opt in to paid Decision-1 calls against a running local router and echo mock",
)
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "Create a PPTX. Storyline: sales results, growth drivers, and next steps.",
            "create",
        ),
        (
            "Edit the existing PPTX: move slide 2's title up and change its font to blue.",
            "edit",
        ),
        ("Help with my presentation.", "clarify"),
    ],
)
def test_given_mock_cards_when_live_router_classifies_then_preserves_user_intent(
    query: str, expected: str
) -> None:
    settings = Settings()
    assert settings.selector == "decision", "Live regression requires Decision-1 routing"
    endpoints = [settings.public_url, settings.creator_url, settings.editor_url]
    assert all(
        endpoint is not None and endpoint.host in ("localhost", "127.0.0.1", "::1")
        for endpoint in endpoints
    ), "Live regression is restricted to a local router and local echo downstreams"
    with httpx.Client(timeout=150, follow_redirects=False) as client:
        for endpoint in (settings.creator_url, settings.editor_url):
            card = client.get(str(endpoint).rstrip("/") + "/.well-known/agent-card.json")
            card.raise_for_status()
            assert card.json()["name"] == "deck-downstream-mock", "Use echo mocks, not real workers"

        body = request_body()
        body["params"]["message"]["parts"] = [
            {"text": query},
            {
                "data": {
                    "datasource": {
                        "sales": [
                            {"quarter": "Q1", "revenue": 100000},
                            {"quarter": "Q2", "revenue": 150000},
                        ]
                    }
                }
            },
        ]
        response = client.post(
            str(settings.public_url),
            headers={"A2A-Version": "1.0"},
            json=body,
        )

    assert response.status_code == 200
    envelope = response.json()
    assert "error" not in envelope, envelope
    message = envelope["result"]["message"]
    if expected == "clarify":
        assert message["parts"] == [
            {"text": "Would you like to create a new deck or edit an existing PPTX?"}
        ]
    else:
        assert [part["data"] for part in message["parts"] if "data" in part] == [
            {"status": "success", "mock": True, "query": query}
        ]
        assert decode_id(message["contextId"])[0] == expected
