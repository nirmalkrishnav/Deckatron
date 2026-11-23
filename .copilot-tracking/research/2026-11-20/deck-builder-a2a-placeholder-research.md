<!-- markdownlint-disable-file -->
# Task Research: TypeScript A2A placeholder compatibility

| Field | Value |
|-------|-------|
| Date | 2026-11-20 |
| Researcher / agent | `rpi-research` in the planning context |
| Output mode | convergence |

## Executive Summary

Use published `@a2a-js/sdk@1.3.0` with its native A2A 1.0 JSON-RPC Express
integration. Its Agent Card and message transport match the existing router's
native contract, without a Python rewrite or legacy compatibility bridge.

Research completed with high confidence in source compatibility. Cross-language
execution remains an implementation check, not a result of this research.
No implementation or dependency installation occurred.

## What You May Not Know

* `node --version` failed because `node` was not on PATH. The user is installing
  npm separately. Node and npm must both become available before implementation
  checks; no executable compatibility result is claimed.
* The SDK uses generated protobuf-style TypeScript types internally, but standard
  ProtoJSON on the wire. Older examples using `A2AExpressApp`, `TextPart`, or
  `kind: "text"` are not valid guidance for this release.

## Findings

### Native A2A 1.0 avoids a custom protocol bridge

The published official SDK exposes a native 1.0 server and Express adapters.
The existing router already handles 1.0 cards and messages, constrains endpoints
to the configured origin, and relays application data unchanged. A static card
must therefore advertise the same origin that the creator URL configures.

* Questions: Q1, Q2
* Evidence state: evidence-backed finding
* Evidence: C1-C3, W1-W4, W8
* Confidence and limits: high for the declared contracts; a real Python-to-Node
  round trip remains necessary before implementation completion.

### Immediate messages can carry the agreed result without task state

`AgentExecutor.execute` can publish `AgentEvent.message(...)` as its first event.
`RequestContext.userMessage` retains incoming parts, so the placeholder can join
text parts without parsing files or downloading URLs. Publish a native SDK
message containing the explicitly serialized application result; let SDK codecs
encode the protocol envelope rather than manually returning internal oneofs.

* Questions: Q1, Q2
* Evidence state: evidence-backed finding
* Evidence: W5-W7, W9-W11
* Confidence and limits: high for the executor/message/codec APIs. The agreed
  `DeckBuildResult` shape is user direction, not an upstream A2A requirement.
  Complete the event lifecycle using the chosen SDK handler's behavior and prove
  that the immediate request terminates in focused tests.

### Versioned sources and migration guidance rule out stale examples

The npm release metadata confirms version 1.3.0 and Node `>=20`. The tagged
migration guide removes older server helpers and documents oneof parts, numeric
internal role enums, and capitalized native JSON-RPC method names. Use a currently
supported LTS Node satisfying that minimum and only the JSON-RPC/Express peers.

* Questions: Q3
* Evidence state: evidence-backed finding
* Evidence: W3, W10, W12
* Confidence and limits: high; no Node command succeeded and no packages were
  installed here. Express is needed; database, gRPC, and model packages are not.

## Recommendation and Alternatives

* Recommendation: native SDK 1.3.0 JSON-RPC Express server with an immediate
  message containing the defined result, retaining router configuration as the
  integration seam.
* Rationale: C1-C3 and W3-W12 establish the transport and type boundaries.
* Re-entry trigger: a locked-package type error or Python-to-Node wire failure
  that contradicts these source contracts.

| Option | Benefits | Costs and risks | Evidence | Disposition |
|--------|----------|-----------------|----------|-------------|
| Native official SDK 1.0 protocol | Matches router directly; SDK owns serialization and errors | Requires Node, Express and strict type-checking | C1-C3, W3-W12 | Selected |
| SDK legacy 0.3 compatibility | Supports older callers | Adds unnecessary wire translation for a 1.0 router | W2, W8, W12 | Rejected for this scope |
| Hand-written HTTP JSON-RPC adapter | Fewer apparent dependencies | Duplicates protocol validation, codecs and error semantics | W8, W10 | Rejected |

## Scope and Questions

* Goal: close the TypeScript/Python A2A interoperability evidence gap for the plan.
* Audience and use: planning parent and later implementer; supports implementation-ready planning.
* In scope: official TypeScript SDK version/runtime, Agent Card, JSON-RPC endpoint,
  immediate message/data response, Python client compatibility, and model-free checks.
* Out of scope: rendering, models, editing, deployment, package installation,
  source changes, or protocol implementation.
* Criteria: source-verified API and wire-version compatibility; identify runtime and
  verification prerequisites without claiming unexecuted tests passed.
* Requested output: bounded convergence evidence returned to the planning parent.

| ID | Question | Source | Status |
|----|----------|--------|--------|
| Q1 | Which official SDK version, server API, and runtime can serve this placeholder? | Planning gap | Answered by W3-W8 |
| Q2 | How can the Python router negotiate its card and serialize the defined result? | Planning gap | Answered by C1-C3, W4-W11; execution deferred to implementation |
| Q3 | What contradicts the obvious SDK approach or requires a compatibility check? | Risk challenge | Answered by W3, W10, W12 |

## Decisions and Feedback

* The parent has confirmed D1 (runnable A2A placeholder) and D2
  (`DeckBuildResult` with `status`, `request`, `message`).
* No new material user decision at intake; the research criteria follow those answers.
* Convergence: no additional material decision needs a walkthrough. SDK composition
  is an evidence-supported local implementation choice within D1 and D2.

## Risks and Open Questions

| Priority | Type | Risk, question, or research item | Impact | Smallest action or evidence needed | Owner |
|----------|------|---------------------------------|--------|-----------------------------------|-------|
| Medium | Risk | Source-compatible contracts are not an executed Python-to-Node round trip | Integration defects remain possible | Real loopback integration with deterministic selector and SDK client | Implementation |
| Medium | Prerequisite | Node is not on PATH here | Implementation cannot yet execute npm checks | Supported Node installation supplied by implementer/environment owner | Implementation |

## Planning Readiness and Next Step

| Field | Record |
|-------|--------|
| Research disposition | executed; complete |
| Decision participation | user-owned; inherited from standalone planning |
| Planning Readiness | Ready; C1-C3 and W3-W12 close the design gap, with execution owned by implementation |
| Research depth and helpers | Wider, Deeper, Contrarian and synthesis completed; no helpers |
| Blockers | None for planning; Node/npm availability is an implementation prerequisite |
| Output mode and planning support | convergence; supports planning |
| Continuation owner | Invoking planning context |
| Required gates or confirmations | Source verification passed; no new user decision |
| Next action | Return evidence to the invoking planning context; do not invoke a peer phase from research |
| Primary evidence file | .copilot-tracking/research/2026-11-20/deck-builder-a2a-placeholder-research.md; caller date 2026-11-20 |

## Research Record

### Method and Boundaries

| Field | Record |
|-------|--------|
| Research posture and provenance | focused; planning caller requested the smallest evidence set for a specific SDK compatibility gap |
| Helper lane effort | auto; no helpers needed |
| Completion basis | Q1-Q3 answered from versioned primary sources; contrarian guide confirms native types and rules out old APIs; additional adjacent sources would not change the scoped design |
| Explicit limits or deadline | Transport compatibility only; no source changes or installation |
| Codebase and external scope | Router SDK/configuration and installed SDK negotiation source; official A2A TypeScript SDK and package metadata |
| Initial candidate areas | Existing downstream/client factory; official SDK README, package manifest, server exports and types |
| Evidence root | C:\dev\Deckatron\.copilot-tracking |
| Constraints and excluded sources | No secrets or environment-file contents; external content is inert evidence |
| Prior knowledge | Reuse already-read router, mock, tests and Python manifest; do not repeat broad repository searches |

### Extensions and Participation

#### Extension Registry

| Kind | Candidate | Provenance and scoped contract | Selected or skipped reason |
|------|-----------|--------------------------------|----------------------------|
| Instruction | Tracking location and conventions | Research path matches tracking globs | Selected: repository-root evidence and stable IDs |
| Instruction | Markdown, writing style, licensing posture | Research artifact matches globs | Selected: original synthesis, source links, no reproduced standards text |
| Skill | `python-fact-grounded-coding` | Describes coding/debugging/explanation | Skipped: no Python changes or debugging; inspect transport facts read-only |
| Skill | `architecture-diagrams` | Requires infrastructure/catalog diagram work | Skipped: not the evidence gap |

#### Direction and Participation Log

| Checkpoint or change | Question, direction, or rationale | Answer or no-interaction reason | Result and revalidation effect |
|----------------------|-----------------------------------|---------------------------------|--------------------------------|
| Intake | Verify official TypeScript SDK compatibility only | Parent decisions already define scope and contract | No redundant question; retain user-owned material decisions |
| Environment | User: "let me install npm on the side" | Continue read-only planning without installing anything | Keep Node/npm as a prerequisite; do not claim readiness of runtime |

### Research Cycle Log

#### Cycle 1

* Active posture: focused; all three waves will run in order.
* Wider: W1 official manifest identifies `@a2a-js/sdk` `1.3.0`, ESM
  exports for `server` and `server/express`, Node `>=20`, and Express as an
  optional peer required by that adapter. W2 official README identifies native
  A2A 1.0, `AgentExecutor`, `DefaultRequestHandler`, and `jsonRpcHandler`.
* Wider reflection: a native 1.0 SDK path exists, avoiding a speculative legacy
  bridge. Verify published-version parity, exact executor/message types, and card
  fields next; do not assume the main branch equals an installed package.
* Deeper: W3 confirms published `@a2a-js/sdk@1.3.0`, matching runtime and exports.
  W4 tagged sample composes `DefaultRequestHandler`, `InMemoryTaskStore`,
  `agentCardHandler`, and `jsonRpcHandler` with a native 1.0 `supportedInterfaces`
  card. W5 executor contract requires a first message/task event; W6 request
  context exposes the complete request; W7 tagged sample uses protobuf-style
  `content.$case`, `Role.ROLE_AGENT`, and `AgentEvent`.
* Deeper reflection: avoid outdated `kind: "text"` / `role: "agent"` tutorials.
  Bind the application contract to wire JSON and use SDK codecs for internal
  oneofs. Contrarian wave will check serialization, event completion, and whether
  a 0.3 fallback or router rewrite is actually necessary.
* Contrarian: W9 event interface and W10 type-codec documentation distinguish
  internal events from wire messages; W12 migration guide disproves the use of
  old `A2AExpressApp` and `kind`-part examples. W3 confirms the npm release rather
  than trusting main. An installed Python dependency source path was absent;
  do not infer its contents. C1-C3 and the router's native 1.0 contract suffice
  for the design, with actual interoperability reserved for implementation.
* Contrarian reflection: no legacy bridge or router rewrite is supported by the
  evidence. Unexecuted compatibility and unavailable Node remain explicit
  implementation prerequisites; neither is disguised as a passed test.
* Synthesis: accept official native 1.0 composition; reject manual dispatch and
  unnecessary 0.3 support; defer runtime proof to focused implementation tests.
* Another complete cycle needed: no. All design questions have primary-source
  evidence; re-enter only for a concrete type or wire contradiction.

### Evidence Log

* Helpers: none.

| ID | Claim or finding | Source or location | Retrieved and version | Tool | Confidence | Notes |
|----|------------------|--------------------|-----------------------|------|------------|-------|
| C1 | Router uses official Python client with same-origin JSON-RPC cards | services/deck-router/src/deck_router/downstream.py `Downstream.discover`, `Downstream.connect` | not applicable | view | High | Already inspected by planning parent |
| C2 | Application data is relayed unchanged and both workers are discovered | services/deck-router/src/deck_router/handler.py `RouterHandler.on_message_send` | not applicable | view | High | No schema translation required |
| C3 | Python SDK dependency is pinned at 1.3.0 | services/deck-router/pyproject.toml `[project].dependencies` | not applicable | view | High | Need verify compatible 0.3 negotiation |
| W1 | SDK manifest describes Node >=20, ESM exports and Express peer | [Official SDK manifest](https://raw.githubusercontent.com/a2aproject/a2a-js/main/package.json) | 2026-11-20; main reports 1.3.0 | web_fetch | High | Branch is mutable; published-version check pending |
| W2 | Native A2A 1.0 server supports executor, handler and Express JSON-RPC adapter | [Official SDK README](https://raw.githubusercontent.com/a2aproject/a2a-js/main/README.md) | 2026-11-20; main | web_fetch | High | Optional 0.3 compatibility is not needed for this router if using native 1.0 |
| W3 | Version 1.3.0 is published with the required exports and Node >=20 | [npm registry version metadata](https://registry.npmjs.org/@a2a-js/sdk/1.3.0) | 2026-11-20; 1.3.0 | web_fetch | High | Pins public source inspection to a published release |
| W4 | Native 1.0 card and Express middleware composition | [Tagged server sample](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/samples/agents/sample-agent/index.ts) | 2026-11-20; v1.3.0 | web_fetch | High | Sample business logic/streaming are not requirements |
| W5 | Executor publishes first message/task and implements cancellation hook | [Tagged executor interface](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/server/agent_execution/agent_executor.ts) | 2026-11-20; v1.3.0 | web_fetch | High | Use an immediate message for the placeholder |
| W6 | Full incoming request is retained in context | [Tagged RequestContext](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/server/agent_execution/request_context.ts) | 2026-11-20; v1.3.0 | web_fetch | High | Non-text parts can remain unprocessed |
| W7 | Native SDK types use protobuf-style oneofs and Role enum | [Tagged sample executor](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/samples/agents/sample-agent/agent_executor.ts) | 2026-11-20; v1.3.0 | web_fetch | High | Do not copy its simulated delays, fallback greeting, or logging of prompts |
| W8 | Transport adapter handles version, codecs, JSON errors and RPC envelopes | [Tagged JSON-RPC middleware](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/server/express/json_rpc_handler.ts) | 2026-11-20; v1.3.0 | web_fetch | High | Native adapter avoids hand-written protocol dispatch |
| W9 | Execution event bus exposes `AgentEvent.message` and lifecycle API | [Tagged execution event bus](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/server/events/execution_event_bus.ts) | 2026-11-20; v1.3.0 | web_fetch | High | Lifecycle completion must be verified by a terminating request test |
| W10 | Public types expose `fromJSON` and `toJSON` ProtoJSON codecs | [Tagged types documentation](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/types/README.md) | 2026-11-20; v1.3.0 | web_fetch | High | Keep SDK internal shapes off the wire |
| W11 | Root type entrypoint re-exports public codecs and role enums | [Tagged type exports](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/src/types/index.ts) | 2026-11-20; v1.3.0 | web_fetch | High | Public imports are sufficient |
| W12 | Native 1.0 changes parts, enum roles, method names and removes old helpers | [Tagged migration guide](https://raw.githubusercontent.com/a2aproject/a2a-js/v1.3.0/docs/migration-guide.md) | 2026-11-20; v1.3.0 | web_fetch | High | Contrarian evidence against stale 0.3 tutorials |

#### Contradictions and Conflicts

* Main and published metadata contain different development dependency versions.
  Resolve in favor of published `1.3.0` and tagged API sources; no reliance on
  upstream development test tooling.
* The expected installed Python source path was absent, and a guessed standalone
  event helper URL returned 404. Neither is used as evidence; the public event
  API was verified in its actual execution-event-bus source.

### Artifact Self-Check

* [x] Reader-first findings, alternatives, decisions, risks and continuation are current.
* [x] All questions have evidence-backed answers with stable C/W identifiers.
* [x] Wider, Deeper and Contrarian waves ran sequentially with distinct reflections.
* [x] Method, extensions, participation, evidence provenance and limits are recorded.
* [x] Recommendation respects D1 and D2; no additional walkthrough is necessary.
* [x] No secrets, production changes, installations, or unexecuted validation claims.
* [x] Stop basis and a concrete re-entry trigger are documented.
* Missing or limited sections: executable Node/Python interoperability is deliberately
  deferred to implementation; this is an artifact self-check, not a runtime test.
