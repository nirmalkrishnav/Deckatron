"""Exercise the actual Azure SDK structured-output adapter with mocked HTTP only."""

import asyncio
import json
from functools import partial

import httpx
import httpx2
import pytest
from a2a.types import AgentCard, Message, Part, Role
from a2a.utils.errors import InternalError
from deck_router.selection import AzureSelector, DecisionSelector
from deck_router.utils import DecisionClient, LLMClient
from deck_router.utils.settings import AzureSettings, DecisionSettings
from google.protobuf.json_format import ParseDict
from openai import AsyncAzureOpenAI
from pydantic import HttpUrl, SecretStr
from typesafe_sdk import AsyncTypeSafeClient


@pytest.mark.parametrize("target", ["create", "edit", "clarify"])
def test_given_azure_structured_decision_when_parsed_then_limits_route_and_excludes_file_data(
    target: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    question = "Which workflow?" if target == "clarify" else None

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "completion",
                "object": "chat.completion",
                "created": 1,
                "model": "configured-deployment",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"target": target, "question": question}),
                        },
                    }
                ],
            },
        )

    async def run() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        monkeypatch.setattr(
            "deck_router.utils.llm.AsyncAzureOpenAI", partial(AsyncAzureOpenAI, http_client=http)
        )
        selector = AzureSelector(
            LLMClient(
                AzureSettings(
                    endpoint=HttpUrl("https://azure.test"),
                    api_key=SecretStr("synthetic-test-key"),
                    deployment="configured-deployment",
                    timeout=10,
                    _env_file=None,
                )
            ),
        )
        message = Message(
            message_id="request",
            role=Role.ROLE_USER,
            parts=[
                Part(text="Create a deck using this source"),
                Part(raw=b"confidential-file-content", filename="data.json"),
            ],
        )
        result = await selector.choose(
            message, {"create": AgentCard(name="creator"), "edit": AgentCard(name="editor")}
        )
        assert result.target == target
        assert result.question == question

    asyncio.run(run())
    body = json.loads(requests[0].content)
    assert body["model"] == "configured-deployment"
    assert body["response_format"]["type"] == "json_schema"
    assert requests[0].headers["api-key"] == "synthetic-test-key"
    assert b"confidential-file-content" not in requests[0].content
    assert "data.json" in body["messages"][1]["content"]


@pytest.mark.parametrize("failure", ["unauthorized", "invalid_decision", "refusal"])
def test_given_azure_failure_when_routing_then_has_no_keyword_fallback(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if failure == "unauthorized":
            return httpx.Response(401, json={"error": {"message": "Not authorized"}})
        message = {
            "role": "assistant",
            "content": '{"target":"http://invented.test","question":null}',
        }
        if failure == "refusal":
            message = {"role": "assistant", "refusal": "Cannot comply", "content": None}
        return httpx.Response(
            200,
            json={
                "id": "completion",
                "object": "chat.completion",
                "created": 1,
                "model": "deployment",
                "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
            },
        )

    async def run() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        monkeypatch.setattr(
            "deck_router.utils.llm.AsyncAzureOpenAI", partial(AsyncAzureOpenAI, http_client=http)
        )
        selector = AzureSelector(
            LLMClient(
                AzureSettings(
                    endpoint=HttpUrl("https://azure.test"),
                    api_key=SecretStr("synthetic-test-key"),
                    deployment="deployment",
                    timeout=10,
                    _env_file=None,
                )
            ),
        )
        with pytest.raises(InternalError):
            await selector.choose(
                Message(parts=[Part(text="Create a deck")]),
                {"create": AgentCard(), "edit": AgentCard()},
            )

    asyncio.run(run())


@pytest.mark.parametrize("target", ["create", "edit", "clarify"])
def test_given_decision_choice_when_routing_then_uses_exact_label_without_confidence_threshold(
    target: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "model": "Decision-1",
                "usage": {"input_tokens": 10, "output_tokens": 1},
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": target,
                        "confidence": 0.34,
                        "probabilities": {
                            label: 0.34 if label == target else 0.33
                            for label in ("create", "edit", "clarify")
                        },
                    }
                },
            },
        )

    async def run() -> None:
        monkeypatch.setattr(
            "deck_router.utils.decision.AsyncTypeSafeClient",
            partial(
                AsyncTypeSafeClient, transport=httpx2.MockTransport(respond), compression=False
            ),
        )
        selector = DecisionSelector(
            DecisionClient(
                DecisionSettings(
                    endpoint=HttpUrl("https://decision.test/providers/microsoft"),
                    api_key=SecretStr("synthetic-test-key"),
                    _env_file=None,
                )
            )
        )
        message = Message(
            parts=[
                Part(text="Decide which presentation workflow I need"),
                Part(raw=b"sensitive-bytes", filename="source.pptx"),
                Part(url="https://private.test/source"),
                ParseDict({"data": {"privateDatasource": "sensitive-records"}}, Part()),
            ]
        )

        result = await selector.choose(
            message, {"create": AgentCard(name="creator"), "edit": AgentCard(name="editor")}
        )

        assert result.target == target
        assert bool(result.question) == (target == "clarify")

    asyncio.run(run())
    body = json.loads(requests[0].content)
    assert body["questions"]["route"]["type"] == "choice"
    assert set(body["questions"]["route"]["criteria"]) == {"create", "edit", "clarify"}
    assert "source.pptx" in body["state"]
    assert "sensitive-bytes" not in body["state"]
    assert "sensitive-records" not in body["state"]
    assert "private.test" not in body["state"]


@pytest.mark.parametrize(
    "answers",
    [
        {},
        {
            "route": {
                "type": "choice",
                "choice": "invented",
                "confidence": 1,
                "probabilities": {"invented": 1},
            }
        },
    ],
)
def test_given_missing_or_invented_decision_route_when_routing_then_fails_explicitly(
    answers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={"model": "Decision-1", "usage": {}, "answers": answers},
        )

    async def run() -> None:
        monkeypatch.setattr(
            "deck_router.utils.decision.AsyncTypeSafeClient",
            partial(
                AsyncTypeSafeClient, transport=httpx2.MockTransport(respond), compression=False
            ),
        )
        selector = DecisionSelector(
            DecisionClient(
                DecisionSettings(
                    endpoint=HttpUrl("https://decision.test/providers/microsoft"),
                    api_key=SecretStr("synthetic-test-key"),
                    _env_file=None,
                )
            )
        )
        with pytest.raises(InternalError):
            await selector.choose(
                Message(parts=[Part(text="Create a deck")]),
                {"create": AgentCard(), "edit": AgentCard()},
            )

    asyncio.run(run())
