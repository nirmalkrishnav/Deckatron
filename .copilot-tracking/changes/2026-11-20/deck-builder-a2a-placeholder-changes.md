<!-- markdownlint-disable-file -->
# RPI Changes: TypeScript deck-builder A2A placeholder

## Metadata

* Task ID: `deck-builder-a2a-placeholder`
* Related plan: [.copilot-tracking/plans/2026-11-20/deck-builder-a2a-placeholder-plan.md](../../plans/2026-11-20/deck-builder-a2a-placeholder-plan.md)
* Implementation date: `2026-11-20`

## Execution Status

* Status: Complete for the full plan.
* Declared invocation scope: full plan.
* Completed scope markers: `P01`, `P01-T01`, `P02`, `P02-T01`, `P03`, `P03-T01`, `P03-T02`.
* All remaining active-plan markers: none.
* First dependency-ready item: none.
* Status basis: user supplied the fnm multishell executable directory. A
  process-local PATH resolves Node `26.13.1`, npm `11.20.0`, and Python `3.11.17`.

## Execution Summary

Implemented the runnable TypeScript A2A placeholder and confirmed result class.
Direct behavior, the real model-free router round trip, existing regressions and
required static checks pass. Setup and the non-generation contract are documented.
The historical `PC-001` critique finding remains resolved; optional Review is ready.

## Completed Work

### Typed package and explicit result contract

* Related phase/task: `P01`, `P01-T01`.
* Files: [src/deck-builder/package.json](../../../src/deck-builder/package.json),
  [src/deck-builder/package-lock.json](../../../src/deck-builder/package-lock.json),
  [src/deck-builder/tsconfig.json](../../../src/deck-builder/tsconfig.json),
  [src/deck-builder/result.ts](../../../src/deck-builder/result.ts),
  [src/deck-builder/index.ts](../../../src/deck-builder/index.ts),
  [.gitignore](../../../.gitignore).
* Behavior: independently buildable strict ESM package exports `DeckBuildResult`
  with exact three-field JSON serialization and no listener side effects.
  Official SDK/Express dependencies are locked; generated files stay ignored.
* Validation: package-local install, clean `npm ci --ignore-scripts`, strict
  type-check and build passed. npm reported zero vulnerabilities.

### Runnable native A2A creation placeholder

* Related phase/task: `P02`, `P02-T01`.
* Files: [src/deck-builder/app.ts](../../../src/deck-builder/app.ts),
  [src/deck-builder/executor.ts](../../../src/deck-builder/executor.ts),
  [src/deck-builder/server.ts](../../../src/deck-builder/server.ts).
* Behavior: loopback-only health/discovery and A2A 1.0 JSON-RPC endpoint returns
  one immediate structured `DeckBuildResult`. Text is preserved; attachments
  and URLs are untouched. Invalid instructions are protocol errors, not failed
  tasks; streaming/task listing are explicitly unsupported.
* Validation: strict type-check/build and actual ephemeral-loopback discovery,
  health, exact result, blank-input and wrong-role checks passed.

### Direct contract and real router interoperability

* Related phase/task: `P03`, `P03-T01`.
* Files: [src/deck-builder/tests/placeholder.test.ts](../../../src/deck-builder/tests/placeholder.test.ts),
  [services/deck-router/tests/test_deck_builder.py](../../../services/deck-router/tests/test_deck_builder.py).
* Behavior: six Node cases exercise real HTTP discovery/results/errors and
  invalid-port startup. One gated Python case calls a real compiled Node creator
  through the unchanged router SDK, with deterministic selection, mock editor
  discovery, exact output data and creator-affinity context IDs.
* Isolation: ephemeral loopback ports, bounded HTTP/readiness waits and owned
  process cleanup; missing Node/build fails an opted-in run explicitly.
  The ordinary Python suite needs no Node and makes no paid calls.
* Validation: six Node cases and one opted-in integration passed; isolated
  router regressions passed 62 cases with four expected opt-in skips.
  Strict TypeScript, targeted ruff/format, Python syntax and workspace ty passed.

### Runnable setup and explicit placeholder limitations

* Related phase/task: `P03`, `P03-T02`.
* File: [README.md](../../../README.md).
* Behavior: documents package-local Node setup, build/type-check/start/test
  commands, loopback configuration, the exact serialized class contract, ignored
  attachments and unsupported generation/editing/task workflows. Explains the
  separately discoverable editor and unchanged model-based normal routing.
* Validation: commands and contract align with the completed runtime checks.
  Safe deterministic integration instructions preserve inherited flags and
  explicitly disable paid tests. No documentation test tooling exists; no
  Markdown validation tool was installed. Existing editor/mock instructions and
  the real root `.env` were not changed.

## Implementation-Time Plan Updates

### Runtime availability needs an executable path

* Affected marker: `P01-T01`.
* Triggering evidence: `node --version` is unavailable; standard nodejs install
  locations and executable checks against current Windows user/machine PATH
  found no Node executable. `uv` is available.
* User direction: Node 26 and npm 11 are installed; do not install another runtime.
* Decision classification: environment prerequisite, not a scope or architecture change.
* Clearing action: obtain the user's actual Node/npm location and use a
  process-local PATH if necessary; never mutate system or user PATH.
* Planning/critique state: the temporary runtime prerequisite is resolved;
  planning and the historical critique disposition remain valid.
* Resolution: user supplied the fnm multishell directory; runtime verification
  passed using process-local PATH only. No installation or persistent PATH edit.

### Reject invalid requests before SDK task execution

* Affected marker: `P02-T01`.
* Triggering evidence: the first negative smoke test showed SDK 1.3.0 catches an
  executor rejection and returns a failed task with the incoming message history.
* Change: a narrow `DefaultRequestHandler` subclass validates instructions before
  delegation, using the executor's shared text guard. No protocol dispatch,
  Python production behavior, dependency or output contract changed.
* Classification: evidence-backed clarification of the existing explicit-error
  and no-input-history requirements; no significant/divergent user decision.
* Reconciliation: P02 Details updated; subsequent smoke test confirmed JSON-RPC
  errors without a result/task. Critique disposition is unchanged.

### Test fixture guidance

* Affected marker: `P03-T01`.
* `createApp(port)` needs the actual loopback port; tests can bind a test-owned
  server to port zero first and then attach the configured application.

### Isolate ambient settings during existing regressions

* Affected marker: `P03-T01`.
* Evidence: the first regression run passed 61 cases and skipped four, but the
  existing unconfigured-service case received a configured loopback creator
  instead of its expected missing-configuration error.
* Classification: evidence-backed validation clarification, not a production
  behavior or test change. Existing settings explicitly allow empty endpoint
  environment values to override dotenv.
* Action: clear only the two downstream URL values inside the regression Python
  process; keep paid tests disabled and leave the real `.env` untouched.
  The plan command now records this isolation.

## Business Alignment

* None.

## Validation Record

| Check | Scope | Status | Evidence or reason |
|-------|-------|--------|--------------------|
| Initial worktree inspection | Full plan preflight | Passed | No pre-existing production modifications at implementation start |
| `node --version` | P01 prerequisite | Passed | `26.13.1` using the user-provided fnm directory |
| `npm --version` | P01 prerequisite | Passed | `11.20.0` |
| `uv --version` | Python tooling | Passed | `uv 0.12.23` |
| npm install, `ci --ignore-scripts`, strict type-check and build | P01 | Passed | Locked restore and both TypeScript commands completed successfully |
| Node tests and strict type-check | P03 | Passed | Six cases; discovery assertion permits SDK-provided optional interface fields |
| A2A smoke check | P02 | Passed | Ephemeral HTTP listener verified discovery, health, exact result and protocol validation errors |
| Deterministic Python-to-Node integration | P03 | Passed | One real loopback Node creator round trip using deterministic selection and mock editor discovery |
| Targeted ruff, format, Python syntax and workspace ty | P03 | Passed | All checks passed |
| Initial router regressions | P03 | Failed, resolved | 61 passed, four skipped, one ambient-config failure; isolated rerun passed |
| Isolated router regressions | P03 | Passed | 62 passed, four expected opt-in skips; downstream URLs cleared only in the test Python process |
| Documentation | P03 | Skipped automated checks | No documentation test tooling exists; setup and contract use the verified commands and output |

## Pre-Review Reconciliation

* Plan markers and task-local context: all three phases and four tasks checked.
* Completed-work entries: package, runnable service, interoperability and docs recorded.
* Validation: required executable checks passed; documentation-tooling limitation explicit.
* Blockers, remaining work, and follow-up items: none.
* Business-source comparison: not applicable; no BRD, PRD or ADR cited.
* Review readiness: Ready for optional standalone Review; not invoked automatically.

## Blockers

* None.

## Remaining Work

* None.

## Follow-Up Items

* Canonical list: [.copilot-tracking/plans/2026-11-20/deck-builder-a2a-placeholder-plan.md](../../plans/2026-11-20/deck-builder-a2a-placeholder-plan.md), `## Follow-Up Items`.
* None.

## Return-to-Caller State

* Implementation execution status: Complete.
* Declared scope: full plan; no remaining active-plan markers.
* Validation coverage: locked restore, build/types, six Node cases, one real router
  integration, 62 regression cases and Python static checks; four expected opt-in skips.
* Current plan updates: runtime resolved, SDK error boundary clarified and ambient regression configuration isolated; no scope change.
* Business alignment entries: none.
* Follow-up items: none.
* Review readiness: Ready; no unresolved decisions or blockers.
* Continuation owner: user may optionally invoke `/rpi-review` with this record and plan.
