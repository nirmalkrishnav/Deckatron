"""Router tests using real A2A serialization and an in-process downstream transport."""

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Literal
from uuid import uuid4

import httpx
import httpx2
import pytest
from a2a.helpers import new_text_message
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Artifact,
    Message,
    Part,
    Role,
    SendMessageRequest,
    SendMessageResponse,
    Task,
    TaskState,
    TaskStatus,
)
from deck_router.app import create_app
from deck_router.identifiers import decode_id, encode_id
from deck_router.selection import RouteDecision, Target
from deck_router.utils.settings import Settings
from google.protobuf.json_format import MessageToDict, ParseDict
from openai import AsyncAzureOpenAI
from pydantic import HttpUrl
from starlette.testclient import TestClient
from typesafe_sdk import AsyncTypeSafeClient


def agent_card(target: Target) -> AgentCard:
    """Describe an external agent; these tests do not implement a PPTX worker."""
    return AgentCard(
        name=f"deck-{target}",
        description=f"Existing {target} service",
        version="1.0",
        capabilities=AgentCapabilities(),
        supported_interfaces=[
            AgentInterface(
                url=f"http://{target}.test/",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id=f"{target}-deck", name=target, description=f"{target} PPTX", tags=[target]
            )
        ],
    )


@dataclass
class FakeSelector:
    """Return a validated decision without spending credits or sending source data."""

    decision: RouteDecision = field(
        default_factory=lambda: RouteDecision(target="create", question=None)
    )
    calls: int = 0

    async def choose(self, message: Message, cards: Mapping[Target, AgentCard]) -> RouteDecision:
        assert cards["create"].skills[0].id == "create-deck"
        assert cards["edit"].skills[0].id == "edit-deck"
        self.calls += 1
        return self.decision


@dataclass
class Backends:
    """Record real SDK requests and supply canned external service responses."""

    response: Message | Task = field(default_factory=lambda: new_text_message("downstream reply"))
    calls: list[tuple[Target, str]] = field(default_factory=list)
    sent: list[SendMessageRequest] = field(default_factory=list)
    queried_ids: list[str] = field(default_factory=list)
    unsafe_card: bool = False
    unavailable: bool = False
    protocol_error: bool = False
    cards: dict[Target, AgentCard] = field(
        default_factory=lambda: {"create": agent_card("create"), "edit": agent_card("edit")}
    )

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Serve only mock Agent Cards and JSON-RPC responses."""
        target: Target = "create" if request.url.host == "create.test" else "edit"
        assert request.url.host in ("create.test", "edit.test")
        if self.unavailable:
            raise httpx.ConnectError("Mock backend offline", request=request)
        if request.method == "GET":
            card = AgentCard()
            card.CopyFrom(self.cards[target])
            if self.unsafe_card:
                card.supported_interfaces[0].url = "http://untrusted.test/"
            return httpx.Response(200, json=MessageToDict(card))

        assert request.headers["A2A-Version"] == "1.0"
        body = json.loads(request.content)
        method = body["method"]
        self.calls.append((target, method))
        if self.protocol_error:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "error": {"code": -32602, "message": "Existing worker rejected the input"},
                },
            )
        if method == "SendMessage":
            self.sent.append(ParseDict(body["params"], SendMessageRequest()))
            result = SendMessageResponse()
            if isinstance(self.response, Task):
                result.task.CopyFrom(self.response)
            else:
                result.message.CopyFrom(self.response)
            data = MessageToDict(result)
        else:
            assert method in ("GetTask", "CancelTask")
            self.queried_ids.append(body["params"]["id"])
            assert isinstance(self.response, Task)
            task = Task()
            task.CopyFrom(self.response)
            if method == "CancelTask":
                task.status.state = TaskState.TASK_STATE_CANCELED
            data = MessageToDict(task)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": data})


@dataclass
class RouterFixture:
    """HTTP router plus injectable external boundaries."""

    client: TestClient
    selector: FakeSelector
    backends: Backends
    http: httpx.AsyncClient
    settings: Settings


@pytest.fixture
def router() -> Iterator[RouterFixture]:
    """Scope the router and HTTP connection pool to one test."""
    settings = Settings(
        public_url=HttpUrl("http://router.test"),
        creator_url=HttpUrl("http://create.test"),
        editor_url=HttpUrl("http://edit.test"),
    )
    backends = Backends()
    selector = FakeSelector()
    http = httpx.AsyncClient(transport=httpx.MockTransport(backends.handle))
    with TestClient(
        create_app(settings, selector=selector, http_client=http),
        headers={"A2A-Version": "1.0"},
    ) as client:
        yield RouterFixture(client, selector, backends, http, settings)
        assert client.portal is not None
        client.portal.call(http.aclose)


def send(client: TestClient, message: Message) -> dict:
    """Submit a real SDK message through the public JSON-RPC API."""
    response = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": uuid4().hex,
            "method": "SendMessage",
            "params": MessageToDict(SendMessageRequest(message=message)),
        },
    )
    assert response.status_code == 200
    return response.json()


def user_message(text: str) -> Message:
    """Make an initial user request."""
    return Message(message_id=uuid4().hex, role=Role.ROLE_USER, parts=[Part(text=text)])


def test_given_router_when_discovered_then_exposes_routing_not_ping(router: RouterFixture) -> None:
    response = router.client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = ParseDict(response.json(), AgentCard(), ignore_unknown_fields=True)
    assert [skill.id for skill in card.skills] == ["route_deck_request"]
    assert not card.capabilities.streaming
    assert router.client.get("/ping").text == "pong"
    assert router.selector.calls == 0


@pytest.mark.parametrize("target", ["create", "edit"])
def test_given_llm_selection_when_forwarded_then_preserves_json_and_files(
    router: RouterFixture, target: Target
) -> None:
    router.selector.decision = RouteDecision(target=target, question=None)
    message = user_message("Use the existing deck service for this request")
    message.parts.extend(
        [
            Part(raw=b'{"sales":123}', filename="data.json", media_type="application/json"),
            Part(raw=b"original-pptx-bytes", filename="source.pptx"),
            ParseDict({"data": {"storyline": "Show growth", "edits": ["Move title"]}}, Part()),
        ]
    )
    router.backends.response = Message(
        message_id="external-result",
        role=Role.ROLE_AGENT,
        context_id="external-context",
        parts=[Part(raw=b"result-pptx-bytes", filename="result.pptx")],
    )

    envelope = send(router.client, message)

    assert "error" not in envelope
    assert router.backends.calls == [(target, "SendMessage")]
    assert router.backends.sent[0].message == message
    result = ParseDict(envelope["result"], SendMessageResponse()).message
    assert result.parts[0].raw == b"result-pptx-bytes"
    assert result.parts[0].filename == "result.pptx"
    assert decode_id(result.context_id) == (target, "external-context")
    assert router.selector.calls == 1


def test_given_ambiguous_intent_when_classified_then_asks_via_api_only(
    router: RouterFixture,
) -> None:
    router.selector.decision = RouteDecision(
        target="clarify", question="Create a new deck or edit an existing one?"
    )

    envelope = send(router.client, user_message("Help with a presentation"))

    result = ParseDict(envelope["result"], SendMessageResponse())
    assert result.message.parts[0].text == "Create a new deck or edit an existing one?"
    assert not router.backends.calls


@pytest.mark.parametrize("model_type", ["decision", "llm"])
def test_given_model_type_when_api_called_then_uses_utility_and_forwards_selected_service(
    router: RouterFixture, model_type: Literal["decision", "llm"], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def decision_response(request: httpx2.Request) -> httpx2.Response:
        calls.append("decision")
        return httpx2.Response(
            200,
            json={
                "model": "Decision-1",
                "usage": {},
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": "edit",
                        "confidence": 1,
                        "probabilities": {"create": 0, "edit": 1, "clarify": 0},
                    }
                },
            },
        )

    def llm_response(request: httpx.Request) -> httpx.Response:
        calls.append("llm")
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
                            "content": '{"target":"edit","question":null}',
                        },
                    }
                ],
            },
        )

    monkeypatch.setenv("AZURE_DECISION_ENDPOINT", "https://decision.test/providers/microsoft")
    monkeypatch.setenv("DECISION_API_KEY", "synthetic-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://azure.test")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-6-luna")
    monkeypatch.setattr(
        "deck_router.utils.decision.AsyncTypeSafeClient",
        partial(
            AsyncTypeSafeClient,
            transport=httpx2.MockTransport(decision_response),
            compression=False,
        ),
    )
    if model_type == "llm":
        monkeypatch.setattr(
            "deck_router.utils.llm.AsyncAzureOpenAI",
            partial(
                AsyncAzureOpenAI,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(llm_response)),
            ),
        )
    settings = Settings(
        creator_url=router.settings.creator_url,
        editor_url=router.settings.editor_url,
        selector=model_type,
        _env_file=None,
    )
    with TestClient(
        create_app(settings, http_client=router.http), headers={"A2A-Version": "1.0"}
    ) as client:
        envelope = send(client, user_message("Inspect and edit my existing deck"))

    assert "error" not in envelope
    assert calls == [model_type]
    assert router.backends.calls == [("edit", "SendMessage")]


def test_given_editor_input_required_when_followed_up_then_retains_service_across_router_instances(
    router: RouterFixture,
) -> None:
    router.selector.decision = RouteDecision(target="edit", question=None)
    router.backends.response = Task(
        id="editor-task",
        context_id="editor-context",
        status=TaskStatus(
            state=TaskState.TASK_STATE_INPUT_REQUIRED,
            message=new_text_message("Here is the layout; what should change?"),
        ),
        history=[
            Message(
                message_id="review",
                role=Role.ROLE_AGENT,
                task_id="editor-task",
                context_id="editor-context",
                parts=[Part(text="Layout review")],
            )
        ],
        artifacts=[Artifact(artifact_id="layout", parts=[Part(text="Layout details")])],
    )
    first = ParseDict(
        send(router.client, user_message("Inspect this existing PPTX"))["result"],
        SendMessageResponse(),
    ).task
    assert first.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
    assert decode_id(first.history[0].task_id) == ("edit", "editor-task")
    assert first.artifacts[0].parts[0].text == "Layout details"

    followup = user_message("Move the title up and regenerate")
    followup.task_id = first.id
    followup.context_id = first.context_id
    router.backends.response = Message(
        message_id="regenerated",
        role=Role.ROLE_AGENT,
        task_id="editor-task",
        context_id="editor-context",
        parts=[Part(raw=b"edited deck", filename="edited.pptx")],
    )
    other_selector = FakeSelector()
    with TestClient(
        create_app(router.settings, selector=other_selector, http_client=router.http),
        headers={"A2A-Version": "1.0"},
    ) as other_router:
        envelope = send(other_router, followup)

    assert other_selector.calls == 0
    assert router.selector.calls == 1
    assert router.backends.sent[-1].message.task_id == "editor-task"
    assert router.backends.sent[-1].message.context_id == "editor-context"
    assert (
        ParseDict(envelope["result"], SendMessageResponse()).message.parts[0].raw == b"edited deck"
    )


@pytest.mark.parametrize("method", ["GetTask", "CancelTask"])
def test_given_returned_task_id_when_polled_or_cancelled_then_relays_to_owner(
    router: RouterFixture, method: str
) -> None:
    router.backends.response = Task(
        id="job-1", context_id="ctx-1", status=TaskStatus(state=TaskState.TASK_STATE_WORKING)
    )
    task_id = encode_id("edit", "job-1")

    response = router.client.post(
        "/",
        json={"jsonrpc": "2.0", "id": "poll", "method": method, "params": {"id": task_id}},
    )

    assert response.status_code == 200
    assert response.json()["result"]["id"] == task_id
    assert router.backends.queried_ids == ["job-1"]
    assert router.backends.calls == [("edit", method)]
    assert router.selector.calls == 0


@pytest.mark.parametrize(
    ("task_id", "context_id"),
    [
        ("not-a-router-id", ""),
        ("dr1.edit.%%%%", ""),
        ("dr1.unknown.dGFzaw", ""),
        (encode_id("edit", "task"), encode_id("create", "ctx")),
    ],
)
def test_given_bad_affinity_when_sent_then_rejects_without_contacting_backend(
    router: RouterFixture, task_id: str, context_id: str
) -> None:
    message = user_message("Continue")
    message.task_id = task_id
    message.context_id = context_id

    envelope = send(router.client, message)

    assert envelope["error"]["code"] == -32602
    assert not router.backends.calls
    assert router.selector.calls == 0


@pytest.mark.parametrize("failure", ["unsafe_card", "unavailable", "protocol_error"])
def test_given_downstream_failure_when_routing_then_reports_error_not_false_success(
    router: RouterFixture, failure: str
) -> None:
    setattr(router.backends, failure, True)

    envelope = send(router.client, user_message("Create a deck"))

    expected = -32602 if failure == "protocol_error" else -32603
    assert envelope["error"]["code"] == expected
    assert "result" not in envelope


def test_given_unconfigured_service_when_requested_then_reports_required_environment(
    router: RouterFixture,
) -> None:
    with TestClient(
        create_app(Settings(), selector=router.selector, http_client=router.http),
        headers={"A2A-Version": "1.0"},
    ) as client:
        envelope = send(client, user_message("Create a deck"))

    assert envelope["error"]["code"] == -32603
    assert "DECK_ROUTER_" in envelope["error"]["message"]


@pytest.mark.parametrize("endpoint", ["http://[invalid", "http://create.test:not-a-port"])
def test_given_malformed_advertised_endpoint_when_discovered_then_reports_card_error(
    router: RouterFixture, endpoint: str
) -> None:
    router.backends.cards["create"].supported_interfaces[0].url = endpoint

    envelope = send(router.client, user_message("Create a deck"))

    assert envelope["error"]["code"] == -32603
    assert "same-origin" in envelope["error"]["message"]
    assert not router.backends.calls


def test_given_request_configuration_when_forwarded_then_preserves_metadata_and_preferences(
    router: RouterFixture,
) -> None:
    body = {
        "jsonrpc": "2.0",
        "id": "configured-request",
        "method": "SendMessage",
        "params": {
            "message": MessageToDict(user_message("Create the deck")),
            "metadata": {"callerTrace": "trace-123"},
            "configuration": {
                "acceptedOutputModes": ["application/octet-stream"],
                "historyLength": 4,
                "returnImmediately": True,
            },
        },
    }

    envelope = router.client.post("/", json=body).json()

    assert "error" not in envelope
    forwarded = router.backends.sent[0]
    assert MessageToDict(forwarded)["metadata"] == {"callerTrace": "trace-123"}
    assert forwarded.configuration.history_length == 4
    assert forwarded.configuration.return_immediately
    assert forwarded.configuration.accepted_output_modes == ["application/octet-stream"]


def test_given_existing_a2a_03_service_when_routed_then_negotiates_legacy_wire_format() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        target: Target = "create" if request.url.host == "create.test" else "edit"
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "name": f"deck-{target}",
                    "description": "Existing legacy service",
                    "url": f"http://{target}.test/",
                    "version": "1.0",
                    "protocolVersion": "0.3.0",
                    "capabilities": {},
                    "defaultInputModes": ["text/plain"],
                    "defaultOutputModes": ["text/plain"],
                    "skills": MessageToDict(agent_card(target))["skills"],
                },
            )
        body = json.loads(request.content)
        assert body["method"] == "message/send"
        assert body["params"]["message"]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "kind": "message",
                    "messageId": "legacy-response",
                    "role": "agent",
                    "contextId": "legacy-context",
                    "parts": [{"kind": "text", "text": "Legacy worker replied"}],
                },
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    with TestClient(
        create_app(
            Settings(
                creator_url=HttpUrl("http://create.test"),
                editor_url=HttpUrl("http://edit.test"),
            ),
            selector=FakeSelector(),
            http_client=http,
        ),
        headers={"A2A-Version": "1.0"},
    ) as client:
        envelope = send(client, user_message("Create a deck"))
        assert client.portal is not None
        client.portal.call(http.aclose)

    assert "error" not in envelope
    result = ParseDict(envelope["result"], SendMessageResponse()).message
    assert result.parts[0].text == "Legacy worker replied"
    assert decode_id(result.context_id) == ("create", "legacy-context")


@pytest.mark.parametrize(
    ("body", "error_code"),
    [
        ("{", -32700),
        ("[]", -32600),
        ('{"id":"test","method":"SendMessage","params":{}}', -32600),
        ('{"jsonrpc":"2.0","id":"test","method":"SendMessage","params":{"message":42}}', -32602),
    ],
)
def test_given_malformed_request_when_sent_then_returns_protocol_error(
    router: RouterFixture, body: str, error_code: int
) -> None:
    response = router.client.post("/", content=body, headers={"Content-Type": "application/json"})

    assert response.status_code == 200
    assert response.json()["error"]["code"] == error_code


def test_given_streaming_request_when_sent_then_reports_unsupported(router: RouterFixture) -> None:
    response = router.client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": "stream",
            "method": "SendStreamingMessage",
            "params": MessageToDict(SendMessageRequest(message=user_message("Create a deck"))),
        },
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == -32004
