"""Verify the general-purpose LLM utility without making any provider requests."""

import asyncio
import json
from functools import partial

import httpx
import pytest
from deck_router.utils import LLMClient, LLMInput
from deck_router.utils.settings import AzureSettings
from openai import AsyncAzureOpenAI
from pydantic import HttpUrl, SecretStr


def test_given_plain_prompt_when_called_then_returns_text_and_overrides_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "completion",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-6-luna",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "Here is the requested summary.",
                        },
                    }
                ],
            },
        )

    async def run() -> None:
        monkeypatch.setattr(
            "deck_router.utils.llm.AsyncAzureOpenAI",
            partial(
                AsyncAzureOpenAI,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
            ),
        )
        client = LLMClient(
            AzureSettings(
                endpoint=HttpUrl("https://azure.test"),
                api_key=SecretStr("synthetic-key"),
                deployment="default-deployment",
                _env_file=None,
            )
        )

        result = await client.call_llm(
            LLMInput(prompt="Summarize this text.", system_prompt="Be concise."),
            model="gpt-6-luna",
        )

        assert result.text == "Here is the requested summary."
        assert result.parsed is None

    asyncio.run(run())
    body = json.loads(requests[0].content)
    assert body["model"] == "gpt-6-luna"
    assert body["messages"] == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Summarize this text."},
    ]
    assert "response_format" not in body
