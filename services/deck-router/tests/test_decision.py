"""Verify reusable Decision calls through the actual SDK and mocked HTTP."""

import asyncio
import json
from functools import partial

import httpx2
import pytest
from deck_router.utils import DecisionClient, DecisionClientError, DecisionInput
from deck_router.utils.settings import DecisionSettings
from pydantic import HttpUrl, SecretStr
from typesafe_sdk import AsyncTypeSafeClient, Noul


@pytest.mark.parametrize("model", [None, "another-decision-deployment"])
def test_given_state_and_question_when_called_then_returns_probability_with_model_override(
    model: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "model": model or "Decision-1",
                "usage": {},
                "answers": {"urgent": {"type": "noul", "noul": 0.91}},
            },
        )

    monkeypatch.setattr(
        "deck_router.utils.decision.AsyncTypeSafeClient",
        partial(AsyncTypeSafeClient, transport=httpx2.MockTransport(respond), compression=False),
    )
    client = DecisionClient(
        DecisionSettings(
            endpoint=HttpUrl("https://decision.test/providers/microsoft"),
            api_key=SecretStr("synthetic-key"),
            _env_file=None,
        )
    )
    data = DecisionInput(
        state={"ticket": "The payment integration still fails. Please help today."},
        questions={"urgent": Noul(instructions="Does this message convey urgency?")},
    )

    response = asyncio.run(client.call_decision(data, model=model))

    assert response.nouls["urgent"].noul == pytest.approx(0.91)
    body = json.loads(requests[0].content)
    assert body["state"] == data.state
    assert body["questions"]["urgent"]["instructions"] == "Does this message convey urgency?"
    assert body["model"] == (model or "Decision-1")
    assert str(requests[0].url) == "https://decision.test/providers/microsoft/v1/systemone"


@pytest.mark.parametrize("failure", ["unauthorized", "invalid_response"])
def test_given_decision_api_failure_when_called_then_raises_actionable_error(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def respond(request: httpx2.Request) -> httpx2.Response:
        if failure == "unauthorized":
            return httpx2.Response(401, json={"error": "provider details must not escape"})
        return httpx2.Response(
            200,
            json={
                "model": "Decision-1",
                "usage": {},
                "answers": {"urgent": {"type": "noul", "noul": "invalid"}},
            },
        )

    monkeypatch.setattr(
        "deck_router.utils.decision.AsyncTypeSafeClient",
        partial(AsyncTypeSafeClient, transport=httpx2.MockTransport(respond), compression=False),
    )
    client = DecisionClient(
        DecisionSettings(
            endpoint=HttpUrl("https://decision.test/providers/microsoft"),
            api_key=SecretStr("synthetic-key"),
            _env_file=None,
        )
    )

    with pytest.raises(DecisionClientError, match="verify input, endpoint") as caught:
        asyncio.run(
            client.call_decision(
                DecisionInput(
                    state="Please help today",
                    questions={"urgent": Noul(instructions="Is this urgent?")},
                )
            )
        )

    assert "provider details" not in str(caught.value)
    assert "synthetic-key" not in str(caught.value)


def test_given_unconfigured_decision_client_when_called_then_does_not_use_public_sdk_defaults() -> (
    None
):
    client = DecisionClient(DecisionSettings(endpoint=None, api_key=None, _env_file=None))

    with pytest.raises(DecisionClientError, match="Configure AZURE_DECISION_ENDPOINT"):
        asyncio.run(
            client.call_decision(
                DecisionInput(
                    state="Please help today",
                    questions={"urgent": Noul(instructions="Is this urgent?")},
                )
            )
        )
