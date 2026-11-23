---
title: Deckatron
description: Decision-1 and LLM routing gateway with a TypeScript A2A deck-builder placeholder
---

## What this project does

[src/deck-router](src/deck-router) is an independently runnable Python A2A service.
It replaces the sample A2A `ping` skill with `route_deck_request`:

1. Receive user instructions and optional JSON/PPTX files through an A2A API request.
2. Discover the Agent Cards of your existing deck creation and editing services.
3. Use Decision-1 to select creation, editing, or clarification.
4. Forward the original request to the selected service through the official A2A SDK.
5. Relay its message, generated file, layout review, or task back to the API client.

The router does not create, inspect, or edit PowerPoint files itself.
The TypeScript [deck-builder package](src/deck-builder) provides a runnable
creation placeholder, not a generator. There is still no PowerPoint generator
or editor implementation, terminal UI, Docker, or Nginx component here.
Real generation and editing remain downstream-service responsibilities.

### Repository layout

* [src/deck-router](src/deck-router): Python router package, source and tests.
* [src/mock/downstream_mock](src/mock/downstream_mock): independently packaged Python echo mock.
* [src/deck-builder](src/deck-builder): TypeScript creation placeholder.
* Root [pyproject.toml](pyproject.toml) and [uv.lock](uv.lock): shared Python
  workspace configuration and locked dependencies. The TypeScript package uses npm.
* One common root `.env`: router/model configuration and `DECK_BUILDER_PORT`.
  Run the commands below from the workspace root.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).
Run from the workspace root:

```powershell
uv sync --all-packages --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configure the placeholders in the common root `.env`:

```dotenv
DECK_ROUTER_CREATOR_URL=http://localhost:8001
DECK_ROUTER_EDITOR_URL=http://localhost:8002
DECK_ROUTER_SELECTOR=decision
DECK_BUILDER_PORT=8001
AZURE_DECISION_ENDPOINT=https://YOUR-RESOURCE.services.ai.azure.com/providers/microsoft
DECISION_API_KEY=YOUR-KEY
DECISION_MODEL=Decision-1
```

The service URLs above are examples: set them to your actual existing services.
They must be base URLs exposing `/.well-known/agent-card.json`, not URLs of a
specific skill. Each card must advertise skills and a JSON-RPC endpoint on that
same origin. The SDK negotiates A2A 1.0 or compatible 0.3 services from their cards.
Both services must be configured and discoverable for new model-routed requests.
Follow-up requests contact only the owning service.

Decision-1 uses a `Choice` question with `create`, `edit`, and `clarify` labels,
without an extra confidence threshold. Clarification returns a fixed API question;
Decision-1 is not asked to generate prose. Keys belong only in the ignored `.env`.
Routing classifies user intent, not downstream implementation readiness. An explicit
creation or editing request stays explicit when the downstream is an echo mock
or workflow inputs still need to be collected.

To route through a GPT-style LLM instead, set `DECK_ROUTER_SELECTOR=llm` and fill in
`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, and
`AZURE_OPENAI_API_VERSION`. Use a deployment/API version supporting structured
outputs (`response_format: json_schema`). Deployment names such as `gpt-6-luna`
must actually be available on your Azure resource; the utility does not deploy models.
There is no automatic fallback between providers.

Decision models use `AZURE_DECISION_ENDPOINT`; GPT-style LLMs use
`AZURE_OPENAI_ENDPOINT`. Their endpoints are configured independently.

### Configuration

| Variable                      | Default                 | Purpose                                   |
|-------------------------------|-------------------------|-------------------------------------------|
| `DECK_ROUTER_HOST`             | `127.0.0.1`             | Console launcher's bind address           |
| `DECK_ROUTER_PORT`             | `8000`                  | Console launcher's port                   |
| `DECK_ROUTER_PUBLIC_URL`       | `http://localhost:8000` | Router origin advertised in its card      |
| `DECK_ROUTER_CREATOR_URL`      | Empty                   | Existing deck-creation service base URL   |
| `DECK_ROUTER_EDITOR_URL`       | Empty                   | Existing deck-editing service base URL    |
| `DECK_ROUTER_REQUEST_TIMEOUT`  | `120`                   | Outbound A2A request timeout in seconds   |
| `DECK_ROUTER_SELECTOR`         | `decision`              | Routing policy backend: `decision`/`llm`  |
| `AZURE_DECISION_ENDPOINT`      | Empty                   | Decision provider base URL                |
| `DECISION_API_KEY`             | Empty                   | Decision credential                       |
| `DECISION_MODEL`               | `Decision-1`            | Default Decision deployment               |
| `DECISION_TIMEOUT`             | `60`                    | Decision request timeout in seconds       |
| `AZURE_OPENAI_ENDPOINT`        | Empty                   | Azure OpenAI resource endpoint            |
| `AZURE_OPENAI_API_KEY`         | Empty                   | Azure OpenAI credential                   |
| `AZURE_OPENAI_DEPLOYMENT`      | Empty                   | Default GPT-style deployment              |
| `AZURE_OPENAI_API_VERSION`     | `2024-10-21`            | Azure API version                         |
| `AZURE_OPENAI_TIMEOUT`         | `60`                    | LLM request timeout in seconds            |

Empty placeholders allow health checks and discovery before configuration.
Routing attempts report explicit errors until services and the selected model are set up.
There is no silent keyword fallback when a model request fails.

Run from the workspace root. Within Python, only `deck_router.utils.settings` loads `.env` from
the working directory; it does not search parent folders or mutate the process
environment. Explicit settings values override process environment, which overrides
dotenv values. Unrelated shared-file keys are ignored.

## Reusable model utilities

The `utils` package inside `deck_router` separates provider calls and configuration
from A2A routing. The two clients use typed input dataclasses and native async I/O:

* `DecisionClient.call_decision(DecisionInput(...), model=...)` accepts text or
  structured state plus named SDK `Noul`, `Choice`, or `Score` questions. It returns
  the SDK's typed response, including probabilities, model name, and usage.
* `LLMClient.call_llm(LLMInput(...), model=...)` accepts a prompt and system
  instructions, returning `LLMOutput.text`. Supply a Pydantic `response_model`
  in `LLMInput` to receive validated output in `LLMOutput.parsed`.

Both clients load connection settings through `utils` by default. You can also
pass `DecisionSettings` or `AzureSettings` to their constructors. The `model=`
argument overrides the configured deployment for one call without changing defaults.
Neither utility knows about deck creation, deck editing, or A2A.

### Verify state with Decision-1

```python
from typesafe_sdk import Noul

from deck_router.utils import DecisionClient, DecisionInput


async def verify_urgency(state: str) -> float:
    response = await DecisionClient().call_decision(
        DecisionInput(
            state=state,
            questions={"urgent": Noul(instructions="Does this message convey urgency?")},
        ),
        model="Decision-1",
    )
    return response.nouls["urgent"].noul
```

The returned number is a probability, not a verified fact or an automatic Boolean.
The caller decides whether a threshold is appropriate for its use case.

### Call a GPT-style LLM

```python
from deck_router.utils import LLMClient, LLMInput


async def summarize(text: str) -> str:
    response = await LLMClient().call_llm(
        LLMInput(prompt=text, system_prompt="Summarize the supplied text concisely."),
        model="gpt-6-luna",
    )
    return response.text
```

Use your actual Azure deployment name. Call these functions with `await` in an
async API handler, or `asyncio.run(...)` from a synchronous script. Client network
resources close after each call. Failures raise `DecisionClientError` or
`LLMClientError` instead of returning invented decisions or empty strings.

## Run with Uvicorn

```powershell
uv run --package deck-router uvicorn deck_router.app:create_app --factory --host 127.0.0.1 --port 8000 --reload --reload-dir src\deck-router\src
```

Or use the launcher, which reads its bind address and port from the environment:

```powershell
uv run --package deck-router deck-router
```

For direct Uvicorn use, `--host` and `--port` control the listener. Keep the public
URL aligned with the reachable router address. Stop the process with `Ctrl+C`.

The service binds to loopback by default. Authentication, downstream credentials,
tenant isolation, and production ingress are not configured. Do not expose it
publicly without those controls.

### Run a local downstream mock

The single-file [src/mock/downstream_mock/api.py](src/mock/downstream_mock/api.py) service advertises
both creation and editing skills and returns the user's text in a mock-success
response. It does not generate PPTX files or simulate the layout-review workflow.

Start it in a second terminal from the workspace root:

```powershell
uv run --package downstream-mock uvicorn downstream_mock.api:app --host 127.0.0.1 --port 8001 --reload --reload-dir src\mock
```

Set both downstream URLs in the root `.env` to the same mock:

```dotenv
DECK_ROUTER_CREATOR_URL=http://127.0.0.1:8001
DECK_ROUTER_EDITOR_URL=http://127.0.0.1:8001
```

Restart the router after changing its configuration, then send a normal A2A
`SendMessage` to the router on port 8000. Routing still uses your configured
Decision-1 or LLM deployment; only the downstream is mocked. To test the mock
without calling a model, send the same request directly to port 8001.

The response's `result.message.parts` contains:

```json
[
  {"text": "Mock success: Create a deck about sales"},
  {
    "data": {
      "status": "success",
      "mock": true,
      "query": "Create a deck about sales"
    }
  }
]
```

The query is the incoming text parts joined with newlines. Files and structured
data are not processed or echoed. The mock also exposes `GET /ping` and
`GET /.well-known/agent-card.json`. You can change its Uvicorn port and use that
same port in both downstream URLs; its card advertises the incoming request origin.
This unauthenticated echo server is for local development only.

## Run the TypeScript deck-builder placeholder

Requires Node.js 22.9+ and npm for the native optional dotenv-file startup flag.
Use a supported Node LTS release. From the workspace root, install the package-local locked dependencies,
check types, build, and start:

```powershell
npm.cmd --prefix src\deck-builder ci
npm.cmd --prefix src\deck-builder run typecheck
npm.cmd --prefix src\deck-builder run build
npm.cmd --prefix src\deck-builder start
```

The service binds only to `127.0.0.1:8001`. `npm start` loads the common root
`.env`, if present, without a package-local copy. Set `DECK_BUILDER_PORT` there
to choose another port from `1` to `65535`; a process-environment value overrides
the file. Invalid values fail startup instead of falling back. Stop it with `Ctrl+C`.

For a complete local router setup, start the existing mock as a separately
discoverable editor in another terminal:

```powershell
uv run --package downstream-mock uvicorn downstream_mock.api:app --host 127.0.0.1 --port 8002
```

Configure the router's root `.env` and restart the router:

```dotenv
DECK_ROUTER_CREATOR_URL=http://127.0.0.1:8001
DECK_ROUTER_EDITOR_URL=http://127.0.0.1:8002
```

Use the creator's exact advertised origin: `127.0.0.1`, not `localhost`, and the
selected port. Both workers must be discoverable for new routed requests.
Normal routing still calls your configured Decision-1 or LLM selector; the
builder does not bypass it or implement editing.

The builder exposes `GET /ping`, `GET /.well-known/agent-card.json`, and A2A 1.0
JSON-RPC `POST /`. Send `SendMessage` with `A2A-Version: 1.0` and user text.
It returns one immediate agent message with one JSON data part. Its application
payload is exactly:

```json
{
  "status": "placeholder",
  "request": "Create a deck about sales",
  "message": "Deck generation is not implemented. No presentation was created."
}
```

The package exports the [DeckBuildResult class](src/deck-builder/index.ts);
HTTP callers receive its serialized JSON, not a live JavaScript instance.
All text parts are joined with newlines, preserving their content and whitespace.
Missing or blank instructions and non-user messages produce JSON-RPC errors.
Additional data, file and URL parts are ignored, not parsed, persisted, echoed,
or fetched.

No presentation, file, artifact, or task is generated. Streaming and task
workflows are unsupported. This unauthenticated, loopback-only service is a
local development placeholder, not a production deployment.

## API

| Endpoint | Behavior |
|----------|----------|
| `GET /ping` | HTTP health check returning plain-text `pong`; not an A2A skill |
| `GET /.well-known/agent-card.json` | Public router Agent Card |
| `POST /` | A2A 1.0 JSON-RPC API |

All user instructions and editing follow-up answers arrive through `SendMessage`.
Use `A2A-Version: 1.0`. Older `message/send` method names are not accepted by
the router's public API.

### Send a creation request

This example sends a JSON datasource as an A2A file part. File bytes are base64
in JSON; `data` parts are forwarded unchanged too. Supply the actual datasource,
storyline, and any additional fields required by your existing creator's contract.
The router does not translate between application-specific worker schemas.

```powershell
function Send-DeckMessage($Message) {
    $body = @{
        jsonrpc = "2.0"
        id = [guid]::NewGuid().ToString()
        method = "SendMessage"
        params = @{ message = $Message }
    } | ConvertTo-Json -Depth 30

    Invoke-RestMethod -Uri http://localhost:8000/ -Method Post `
        -Headers @{ "A2A-Version" = "1.0" } `
        -ContentType "application/json" -Body $body
}

$message = @{
    messageId = [guid]::NewGuid().ToString()
    role = "ROLE_USER"
    parts = @(
        @{ text = "Create a PPTX. Storyline: results, growth drivers, and next steps." },
        @{
            filename = "data.json"
            mediaType = "application/json"
            raw = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\data.json"))
        }
    )
}
$reply = Send-DeckMessage $message
$reply | ConvertTo-Json -Depth 30
```

Messages, file parts, structured data, configuration, and downstream errors are
relayed. Only task/context/reference IDs are namespaced so follow-up requests
can identify their owning service. A returned PPTX remains a base64 `raw` file
part in a message or task artifact, according to the downstream service.

### Inspect an existing deck, then submit edits

Use the same API with text such as `Inspect this PPTX layout; I will provide edits`
and a file part containing your source PPTX:

```powershell
$message.messageId = [guid]::NewGuid().ToString()
$message.parts = @(
    @{ text = "Inspect this PPTX layout; I will provide edits." },
    @{
        filename = "existing.pptx"
        mediaType = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        raw = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\existing.pptx"))
    }
)
$reply = Send-DeckMessage $message
```

When the editor returns a task in `TASK_STATE_INPUT_REQUIRED`, read its layout
review and submit the user's answer using the returned task and context IDs:

```powershell
$task = $reply.result.task
$followup = @{
    messageId = [guid]::NewGuid().ToString()
    role = "ROLE_USER"
    taskId = $task.id
    contextId = $task.contextId
    parts = @(@{ text = "On slide 2, move the title up and use a dark blue font." })
}
$edited = Send-DeckMessage $followup
```

If the editor returns a standalone message with a `contextId` instead, reuse
that returned context ID without a task ID. Resend files or structured fields
if the editor's own API contract requires them. The router does not invent a
layout-review or file-storage contract.

Returned IDs are opaque: send them back unchanged. Follow-ups, `GetTask`, and
`CancelTask` go to the owning service without asking the LLM to switch workflows.
They work across router processes without a router-local task database.
The downstream service remains responsible for storing its task/session state.
Changing configured service aliases while tasks are active changes their destination.
These routing IDs are not authentication tokens or authorization checks.

### Clarifications and errors

An ambiguous new request receives an agent message asking a clarifying question,
without invoking a worker. Submit a new API request with the clarified instruction
and original attachments. This clarification is not a persisted conversation.

New routing requests require text instructions, limited to 16000 characters.
The selected model receives those instructions, attachment names/media types, and discovered
skill descriptions. File bytes and structured datasource contents are forwarded
to the selected worker, not sent to the routing model.

`GetTask` and `CancelTask` accept returned router task IDs. Task listing,
streaming, push notifications, and authenticated extended cards are not exposed.
JSON-RPC errors use an `error` envelope even when HTTP status is 200.
Provider/transport failures are explicit errors, never success-shaped responses.

## Verify

```powershell
uv run --all-packages pytest src\deck-router\tests
uv run --all-packages ruff check src\deck-router src\mock
uv run --all-packages ruff format --check src\deck-router src\mock
uv run --all-packages ty check
```

By default, tests use the real TypeSafe and Azure SDKs and A2A client/ASGI routes
with mocked HTTP boundaries. They do not consume model credits, contact your
configured services, or implement a generator/editor.

### Verify the TypeScript creator and router boundary

After installing the package dependencies, run the seven direct contract tests:

```powershell
npm.cmd --prefix src\deck-builder test
```

This builds the package and uses Node's built-in test runner. The additional
Python-to-Node integration is opt-in; the ordinary Python suite needs no Node.
It starts and stops its own isolated creator, supplies mock editor discovery,
and selects creation deterministically without any model calls or credentials.
An opted-in run fails if Node is missing from PATH or the package is not built.

From the workspace root, with the package built:

```powershell
$priorBuilderFlag = [Environment]::GetEnvironmentVariable(
    "DECK_ROUTER_BUILDER_INTEGRATION_TESTS", "Process")
$priorLiveFlag = [Environment]::GetEnvironmentVariable(
    "DECK_ROUTER_LIVE_DECISION_TESTS", "Process")
try {
    $env:DECK_ROUTER_LIVE_DECISION_TESTS = "0"
    $env:DECK_ROUTER_BUILDER_INTEGRATION_TESTS = "1"
    uv run --all-packages pytest src\deck-router\tests\test_deck_builder.py -q
} finally {
    [Environment]::SetEnvironmentVariable(
        "DECK_ROUTER_BUILDER_INTEGRATION_TESTS", $priorBuilderFlag, "Process")
    [Environment]::SetEnvironmentVariable(
        "DECK_ROUTER_LIVE_DECISION_TESTS", $priorLiveFlag, "Process")
}
```

### Optional paid live regression

An optional live regression checks explicit creation, explicit editing, and
ambiguous requests against your running local router and echo mock. Start both
servers, configure Decision-1 and both mock URLs, then opt in explicitly.
This makes three paid Decision-1 calls using synthetic sales data:

```powershell
$env:DECK_ROUTER_LIVE_DECISION_TESTS = "1"
try {
    uv run --all-packages pytest src\deck-router\tests\test_downstream_mock.py -k live_router -v
} finally {
    Remove-Item Env:\DECK_ROUTER_LIVE_DECISION_TESTS
}
```
