<!-- markdownlint-disable-file -->
# RPI Plan Critique: TypeScript deck-builder A2A placeholder

## Metadata

* Task ID: `deck-builder-a2a-placeholder`
* Critique date: `2026-11-20`
* Plan: .copilot-tracking/plans/2026-11-20/deck-builder-a2a-placeholder-plan.md
* Critique execution: Complete
* Critique depth: standard
* Depth provenance: standalone planning default; no request for deep critique
* Critique type: initial
* Earlier critique: not applicable

## Inputs and Criterion Boundary

* Caller requirements: TypeScript deck-builder package in `src`, runnable A2A
  placeholder receiving the router's request, and the agreed `DeckBuildResult`
  fields `status`, `request`, `message`; no deck generation.
* Research: .copilot-tracking/research/2026-11-20/deck-builder-a2a-placeholder-research.md,
  C1-C3 and W1-W12; source-verified official SDK 1.3.0 and native A2A 1.0.
* Supplied repository evidence: README.md, .gitignore, pyproject.toml,
  services/deck-router/pyproject.toml,
  services/deck-router/src/deck_router/app.py,
  services/deck-router/src/deck_router/downstream.py,
  services/deck-router/src/deck_router/handler.py,
  services/deck-router/src/deck_router/utils/settings.py,
  services/deck-router/src/downstream_mock/api.py,
  services/deck-router/tests/test_downstream_mock.py.
* Decisions and dependencies: D1/D2 confirmed by user; P01 package precedes P02
  transport, which precedes P03 verification/documentation. User is installing
  npm independently.
* Boundary: assess FR-001 through FR-006, NFR-001 through NFR-004, all phase/task
  Goals and Requirements, source support, executability, tests and shared-system
  risks. No production changes, installations, runtime tests or extra research.
* Lens ownership: direct assessment in this context because the bounded evidence
  fits one review; no subagents or model overrides.

## Lens Assessments

| Lens | Scope | Reasoning effort and source | Status | Candidates |
|------|-------|-----------------------------|--------|------------|
| Coverage | All FR/NFR, D1/D2, phases and task Requirements | direct | Complete | 0 adopted; no material coverage gap |
| Evidence | SDK claims, router contracts, source references and research | direct | Complete | 0 adopted; SDK composition and router seams have supplied primary-source support |
| Executability | Phase/task order, npm/uv commands, test budget and runtime | direct | Complete | 1 adopted: PC-001; phase order and seven-case budget otherwise executable |
| Risk | Shared environment, input handling, model calls and preserved behavior | direct | Complete | PC-001 also covers the inherited-flag risk; no duplicate finding. Loopback, no attachment fetching and owned-process cleanup are explicit |

## Coverage Assessment

| Requirement, research, phase, or task ID | Coverage | Evidence or concern |
|----------------------------------------|----------|---------------------|
| D1/D2, FR-001 through FR-006 | Covered | P01 class contract, P02 native transport/guards, P03 direct and routed checks |
| NFR-001, NFR-003 | Covered | Strict/locked npm build and preserved Python regression/type-check scope |
| NFR-002, NFR-004 | Partial | PC-001: executable validation block does not enforce the paid-call exclusion and does not restore an inherited integration flag |
| P01-T01, P02-T01, P03-T01, P03-T02 | Covered | Explicit outcomes, requirements, dependencies and canonical targets |
| Research Q1-Q3 | Covered | Versioned SDK/source evidence plus explicit deferred runtime proof |

## Verdict

* Verdict: Revise
* Rationale: one Medium executable-command safety correction is needed.
  No Critical or High findings; requirements and architecture are otherwise
  supported within the supplied boundary.
* Severity counts: Critical 0; High 0; Medium 1; Low 0.

## Findings

<!-- rpi:critique id=PC-001 -->
### PC-001 [Medium]: Make the validation block safe with inherited test flags

* Related IDs: `P03-T01`, `NFR-002`, `NFR-004`.
* Evidence: .copilot-tracking/plans/2026-11-20/deck-builder-a2a-placeholder-plan.md,
  P03-T01 runs the full router suite and unconditionally removes
  `DECK_ROUTER_BUILDER_INTEGRATION_TESTS` in `finally`. Its prose acknowledges
  that a pre-existing value should be preserved but its executable block does
  not do so. services/deck-router/tests/test_downstream_mock.py enables the live
  three-call Decision-1 regression when `DECK_ROUTER_LIVE_DECISION_TESTS=1`.
* Concern: copying the given block in a shell with inherited flags can enable
  paid calls during the regression suite and removes a pre-existing builder
  integration setting, contrary to the plan's explicit zero-paid/shared-state
  requirements.
* Impact: avoidable model-credit use or a misleading live-service failure, and
  mutation of the caller's shell state.
* Smallest useful change: make the command block itself disable the existing
  paid live-test flag throughout pytest execution and restore both prior flags
  in `finally`, rather than relying on a caveat below the block.
* Action owner: planning parent.
* Exact resolving evidence: P03-T01's executable commands capture both prior
  flags, set the paid flag to `0`, explicitly enable the intended builder check,
  and restore prior values including absence on every exit path.
* Decision route: direct planner correction; implements already confirmed
  model-free verification and shared-environment constraints.

## Strengths and Residual Risk

* Confirmed user scope and the serialized placeholder class are preserved without
  slide libraries, a Python rewrite, or a new routing policy.
* Real loopback SDK interoperability is required by P03 rather than replaced by
  mocked creator responses.
* Residual implementation prerequisites are explicit: user-supplied Node/npm and
  unexecuted runtime compatibility. These do not imply a source-design blocker.

## Questions or Blocking Evidence Gaps

* None. PC-001 is planner-owned and requires no user decision.

## Limitations

* Direct multi-lens review has no separate-context reviewer.
* No executable Node/Python compatibility test is claimed.
* Mermaid visual rendering is outside the supplied executable evidence.

## Recommended Next Action

* Highest-impact finding: PC-001, Medium.
* Action owner: planning parent.
* Smallest next action: correct P03-T01's environment handling, record the
  disposition and synchronize readiness. No additional critique is required.
* User response required: no
