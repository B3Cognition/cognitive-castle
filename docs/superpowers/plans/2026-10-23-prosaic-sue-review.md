# Optional Prosaic SUE Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans after review. This is a separate optional milestone, not a prerequisite for the read-only memory provider and not implementation authority.

**Goal:** Offer source-scoped Socratic requirements review with Castle sources, Runtime model execution and Harness-owned durable review state.

**Architecture:** Preserve the useful deterministic SUE policy and evidence checks in an optional consumer package. Each logical turn uses one trusted Runtime adapter execution; Harness admits the resulting candidate and owns correction/recovery. The Castle memory provider never starts a SUE worker.

**Tech Stack:** Python >=3.11, stdlib pure policy and rendering, existing RuntimeAdapter, Runtime HTTP execution, Harness public factory/validators/gates/store, optional Castle source-bundle client. No SOAR or native CLI subprocess transport in the new integration.

**Spec:** `../specs/2026-10-23-prosaic-memory-provider-design.md`. Requires provider M1 source-bundle semantics and M5 frozen evidence tests. Provider publication is not required.

## Global Constraints

- SUE is requirements interpretation, not a truth label, memory-certification pass or implementation test.
- Preserve eight operators, nine lenses, one revision budget, claim-version invalidation and conservative terminal semantics from the pinned engine.
- Keep existing `cognitive_castle/_vendor/sue` bytes, hashes, license and historic standalone output readable.
- No Castle model dispatch, `run_dialogue`, `execute_round`, SUE subprocess runner, module-global monkeypatch or parallel retry loop in the new consumer path.
- Runtime executes every model attempt with no tools; Harness is the sole writer of its review run state and owns retries/receipts/recovery.
- Failed/uncertain transport is never converted into a successful candidate; no automatic provider retry after interruption.
- Sources and reports remain separate; frozen originals cannot be rewritten by review.
- Use `apply_patch`, installed public APIs, synthetic provider fixtures and explicit actual release pins. Live model evaluation/publication remain opt-in execution actions.

## Review Focus

1. A syntactically valid quotation can still fail to entail a claim; RESOLVED must remain provisional: S1/S4.
2. A revised claim must invalidate previous successful probes and cannot skip the opposite/counterexample tests: S1.
3. Completed malformed output can get one corrective retry; uncertain transport must block without a nested retry: S2/S3.
4. Crash between call and checkpoint acceptance must recover from receipts without another paid call: S3.
5. Large source/history/candidate text must fit actual SDK byte limits; partial/failed runs must retain evidence: S2/S4.

## Current SUE assessment

Existing Castle SUE snapshots exact selected drawer bytes and hashes, retains metadata/revisions, runs one of nine question policies and stores separate trace/report/call evidence. Its validators check exact source quotes, premise classification, claim/revision structure and witnesses; they do not independently verify entailment. The engine labels its repaired policy experimental and says the corresponding experiment remains unrun.

It is independent of SOAR. Current hidden workflow ownership is in `sue.py:start_review`, `sue_worker.py:_examine/run_review`, vendored `run_dialogue/execute_round`, and the cold-reader subprocess runner. Current status expiration only reports interruption; it does not cancel the worker. Current per-attempt socket timeout and 2 MiB source cap do not establish an overall deadline or context fit.

The existing standalone SUE remains available for compatibility. The new integration is an explicitly selected application; it never calls those legacy dispatch paths. Do not retrofit legacy `.sue/runs` into live Harness state or silently resume legacy uncertain calls. They remain historical readable evidence. A separate future migration can provide links/projections.

## Package and data model

Create optional `adapters/sue/`, proposed distribution `b3-prosaic-sue`, import `prosaic_sue`. Depends on qualified Runtime and Harness releases; Castle adapter is an optional source extra. Pure review also accepts an authorized host-provided `SourceBundle`. No dependency is added to Core/Runtime/Harness/Castle base packages.

Modules: `policy.py` (pure transition/validation), `types.py` (immutable state/request/result records), `adapter.py` (one Runtime execution/candidate envelope), `workflow.py` (bounded native graph and admission), `validators.py` (independent state checks), `report.py` (derived export). Neutral reviewer prose and JSON schemas live in package data. Test-only pinned upstream reference files/fixtures carry the original MIT notice and hashes; active policy has a separate `prosaic-sue-v1` identity, not a false upstream hash.

Exact policy interfaces:

```python
SocraticPolicy.initial(bundle, *, decision: str, lens: str, max_turns: int) -> SocraticState
SocraticPolicy.request(state: SocraticState, bundle) -> TurnRequest
SocraticPolicy.evaluate(state: SocraticState, bundle, candidate_text: str) -> CandidateOutcome
```

`SocraticState` has schema/policy version, source-bundle digest, lens, decision, current claim/version, next operator, revisions used, accepted turns and terminal/stop reason. It has no provider settings or lifecycle status. `TurnRequest` has operator, deterministic question/prompt and output schema. `CandidateOutcome` has valid flag, bounded issue codes and proposed state or null. A model-supplied next operator/terminal is not an input to the reducer.

`CandidateEnvelope` has schema/policy/bundle identity, turn index, exact candidate stdout + SHA-256, previous state digest, candidate validity and proposed canonical state. It is schema-valid even when a completed model response is malformed; a trusted validator then rejects it for Harness correction. Full raw stdout remains in receipts; no silently normalized replacement for source evidence.

## Proposed pilot bounds

- One selected lens; 7 logical turns by default, maximum 14; 2 completed-output attempts per turn.
- RuntimeAdapter `max_attempts=1`; `execute(..., allowed_tools=frozenset(), max_tool_rounds=1)` exactly once per model attempt.
- Per-invocation timeout 120 seconds, overall Harness `max_run_s=1800`, `max_tokens=50000`, `max_calls=2*max_turns`; per-invocation provider cap 1 and tool cap 0.
- Frozen bundle <=262,144 encoded UTF-8 bytes; decision <=2,048 UTF-8 bytes; actual prompt/context admission before dispatch. These maxima do not promise that every allowed corpus can finish within the token budget.
- Candidate stdout <=16,384 UTF-8 bytes; serialized accepted turn <=4,096 bytes; canonical state <=65,536 bytes; complete encoded candidate envelope <=100,000 bytes. Reject oversized successful output for correction; never truncate a quote/history to fit. Runtime endpoint response bound is explicitly set for this reader.
- Explicit Harness policy: `max_run_input_bytes=524288`, `max_invocation_bytes=524288`, `max_output_bytes=100000`, `max_receipt_bytes=1048576`, `max_state_bytes=4194304`, `max_steps=64`, `max_agent_steps=14`, `max_calls=28`, `max_attempts=2`, `max_run_s=1800`, `max_tokens=50000`. Workflow limits narrow calls/turns to the selected review. Defaults otherwise would allow only 12 calls/64 KiB run inputs and are insufficient.
- Byte-limit/resource exhaustion remains a blocked/bounded outcome with retained partial evidence, never RESOLVED. Unknown token usage obeys Runtime/Harness accounting policy instead of assuming zero.

### S1: Isolate pure SUE policy and pin equivalence

**Files:** `adapters/sue/src/prosaic_sue/{types,policy}.py`, package metadata/license/provenance; `tests/test_policy.py`, `test_upstream_equivalence.py`, test-only pinned reference fixture source.

**Consumes/produces:** M1 `SourceBundle`; the three `SocraticPolicy` methods and records above. Default lens `euthyphro`; use the pinned engine's nine lens names and operator transitions. Keep standalone vendored code unchanged.

- [ ] Create parameterized traces for all nine lenses, successful seven-dimensional examination, partial/unknown/conflict outcomes, counterexample→REVISE, exhausted revision budget, opposite hypothesis permitted, and claim-version probe reset. Differentially compare policy states/stop reasons with pinned upstream scripted-answer runs in isolated test processes.
- [ ] Add invalid exact quotes, invented stated premises, stale-claim addresses, boundary-metadata-only support and spoofed terminal/operator cases. Require source-role labels; metadata can contextualize provenance but cannot alone establish normative requirement wording. Record this source-role restriction as an intentional `prosaic-sue-v1` policy addition.
- [ ] Run adapter SUE `.venv/bin/python -m pytest tests/test_policy.py tests/test_upstream_equivalence.py -q`; observe RED before implementing the pure port.
- [ ] Implement question/schema/validation/reduction by porting the required pure semantics, not the transport/loop. Preserve operator-contract prompt guidance in explicit versioned policy. No dynamic imports of live Castle SUE modules or global monkeypatching.
- [ ] Assert policy calls cannot use subprocess, network, write files or instantiate Runtime/Harness. Preserve original source bytes and renderer epistemic labels. Commit `feat: isolate versioned socratic review policy`.

### S2: Execute exactly one review attempt through Runtime

**Files:** `adapters/sue/src/prosaic_sue/adapter.py`, reviewer prose, schemas; `tests/test_runtime_adapter.py`, `test_review_budgets.py`.

**Interfaces:** `review_adapter(runtime, *, policy: SocraticPolicy) -> RuntimeAdapter`; adapter callback signature follows Runtime's documented `invoke(artifact, arguments, *, execute, policy, on_event, cancelled, **options)` contract. Capture the domain policy under an unambiguous name; do not confuse it with Runtime `RunPolicy`.

- [ ] Use owned loopback fake provider responses for valid output, malformed JSON, invented quotations, nonzero dispatch failure, timeout, missing usage, oversized output and cancellation. Assert one or zero real `execute` calls per invocation, zero tools and no legacy Castle transport/SUE subprocess invocation.
- [ ] Test raw candidate stdout/digest retention in the canonical envelope; full encoded envelope/state bounds; requests at actual Runtime input limits. Invalid completed outputs retain their exact bytes and yield a rejectable envelope rather than pretending policy validation succeeded.
- [ ] Run focused adapter tests, observe RED, then build deterministic unprivileged request arguments from the prior accepted state/bundle and question schema. Use the static reviewer artifact for behavioral rules, not recalled source text as a system resource.
- [ ] Invoke `execute` once with reduced authority. Preserve failure/cancellation/timeout Results unchanged. Only a successful transport output may be parsed into a candidate envelope. Preserve usage/metadata and separately mark validation issues; do not synthesize a successful model call.
- [ ] Enforce the 16 KiB/4 KiB/64 KiB/100,000-byte bounds in order. Completed malformed/oversized output can be semantically rejected for one correction; transport overrun or aggregate SDK resource failures block normally. No retry inside the adapter.
- [ ] Run installed Runtime adapter conformance and budget tests. Commit `feat: execute socratic review turns through prosaic runtime`.

### S3: Let Harness own review progression and recovery

**Files:** `adapters/sue/src/prosaic_sue/{workflow,validators}.py`; `tests/test_workflow.py`, `test_recovery.py`, `test_validation_retry.py`.

**Interfaces:** `build_review_workflow(bundle, *, decision, lens='euthyphro', max_turns=7, bindings, policy) -> PreparedWorkflow`; `review_validator(domain_policy) -> Validator`. Use `WorkflowFactory`/catalogue/registered RuntimeAdapter/public RunStore; no private engine import.

- [ ] Generate up to 14 fixed agent nodes with gate nodes checking accepted `proposed_state.terminal`/continue fields, plus completed/bounded finishes. Each agent has `max_attempts=2`; factory policy explicitly grants the pilot bounds. All callbacks are versioned and fingerprinted.
- [ ] Add tests for one malformed successful answer followed by correction (2 calls total), two invalid answers (blocked), failed first transport (1 call and blocked), and recovery of a pending uncertain request (no automatic replay). Assert the next request still answers the same operator after invalid output.
- [ ] Add process-restart tests after Runtime output before receipt save, after receipt save before acceptance, and after acceptance before the gate. Use supported Harness recovery choices. Assert accepted state is reconstructed from frozen inputs/receipts, no mutable closure or `.sue/state.json`, and no duplicate paid dispatch when a saved receipt exists.
- [ ] Run focused tests and observe RED, then have the trusted validator recompute the proposed transition from exact candidate stdout and prior accepted state and compare digests/fields. Validators return issue lists only. Gates consume only admitted state; they never trust model terminal fields.
- [ ] Preserve all rejected candidate receipts. Include Harness feedback only as bounded correction guidance for the same policy request; do not reset the claim or choose a different operator because an attempt failed validation.
- [ ] Verify all nine lens paths and default/max turn budgets; RuntimeAdapter executes once even though the whole workflow may use 14/28 calls. Commit `feat: orchestrate durable socratic reviews with harness`.

### S4: Export evidence and qualify optional review behavior

**Files:** `adapters/sue/src/prosaic_sue/report.py`, CLI/example wrapper and documentation; `tests/test_report.py`, `test_source_scope.py`, `test_packaging.py`; sanitized verification report.

**Interfaces:** `render_review(run_snapshot, *, bundle) -> DerivedReview`; `DerivedReview` contains report/trace, source digest, accepted/rejected receipt references, policy identity, terminal/stop reason and explicit epistemic status. The host chooses export destination after authorization; no model-selected filesystem path.

- [ ] Test correct source byte/line mappings with CRLF/Unicode, historical requirements, boundary metadata and source edits/deletion after the review starts. Resume/export uses original frozen bundle; changed originals require a new review identity.
- [ ] Retain exact Runtime candidate outputs and usage/call receipts, including failures. Mark unavailable raw provider-protocol evidence as unavailable; do not claim equivalence to the old Codex JSONL runner if Runtime does not expose it.
- [ ] Test that RESOLVED means required dimensions examined for the current claim, bounded stop is not substantive completion, and partial/failed reports retain unresolved issues. Neither state approves memory publication or certifies implementation.
- [ ] Run full optional package tests/build/clean wheel smoke against installed qualified Runtime/Harness. No SOAR or base Castle dependency is needed for host-supplied bundles. A Castle-source-extra smoke uses M1 and forbids `castle_sue_review`/`sue_worker` dispatch.
- [ ] Before recommending SUE as a quality gate, run an explicitly authorized evaluation against known requirement defects and a simpler single-review baseline; measure useful findings, false positives, missed defects, latency and token cost. Unit/differential tests qualify policy mechanics only. Keep review advisory until that evidence is reviewed.
- [ ] Commit `feat: export source-linked socratic review evidence`. No automatic writeback to Castle; later publication requires the separately designed host outbox.

## Compatibility and deferred work

Existing Castle SUE CLI/MCP and `.sue/runs` remain readable standalone features. Their direct Ollama/Codex/Claude execution remains outside Prosaic's memory-provider contract and is never implicitly delegated by memory reads. Document the existing status/deadline limitation; a separate standalone fix may enforce real cancellation without blocking the provider milestone.

Deferred: importing/reconciling old uncertain SUE runs into Harness, strict per-turn provider JSON Schema support (would be a generic Runtime feature), automatic selection of a complete requirements corpus, memory publication, and any claim of factual/implementation certification.
