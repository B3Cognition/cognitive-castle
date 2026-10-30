# Task2a review — 3208aea..56911a6

## Spec Compliance

- ❌ Issues found: the shared absolute five-second deadline is not carried through supervisor preflight; `semantic_runtime.py:104` passes a relative remainder to a supervisor that starts its clock only after its initial pressure check (`memory_runtime.py:322`, `memory_runtime.py:345`). See Important finding 1.
- ✅ The eight requested new modules/tests are the entire diff. Fixed worker selection, 512/640 MiB stage limits, and an inactive internal coordinator are present (`semantic_runtime.py:20`, `semantic_runtime.py:107`, `semantic_runtime.py:122`); no production-dispatch changes appear in the package.
- ⚠️ The six pinned hashes' correspondence to the private diagnostic and artifact manifest was not independently rechecked. The implementation verifies every file against those constants (`semantic_profile.py:128`); the reported offline qualification exercises the prepared assets. Controller should retain that artifact provenance evidence.
- ⚠️ Historical-vector compatibility, real-archive retrieval qualification, vector publication, contiguous durable coverage and active-stage preemption remain later integration work, as explicitly scoped by the controller. They are not claimed complete by this review.

## Strengths

- Exact source validation delegates to the existing canonical contract, including UTF-8 byte bounds, text hash and chunk offsets (`semantic_windows.py:17`; dependency check: `canonical_records.py:64`, `canonical_records.py:87`). Unit identity binds original offsets and token arrays; overflow enumeration checks against a full unchanged-source encoding (`semantic_windows.py:36`, `semantic_windows.py:234`).
- Pinned runtime versions, strict request JSON, owned artifact checks and phase-specific imports form clear boundaries (`semantic_profile.py:43`, `semantic_profile.py:82`, `semantic_profile.py:117`, `semantic_worker.py:17`). Guardian-chain admission precedes artifact/native initialization (`semantic_worker.py:74`, `semantic_worker.py:210`).
- The coordinator retains existing admission and supervision, checks issued handoffs and validates returned normalized vectors (`semantic_runtime.py:40`, `semantic_runtime.py:158`). The existing supervisor preserves pressure refusals and owned-process-group cleanup (`memory_runtime.py:322`, `memory_runtime.py:414`).
- Real offline tests cover multilingual ranking, Unicode/NUL long-tail paging and explicit whitespace units, plus observable descendant cleanup (`tests/test_semantic_worker.py:65`, `tests/test_semantic_worker.py:113`, `tests/test_semantic_worker.py:123`). The report limits its conclusions to local synthetic qualification.

## Issues

### Critical

- None identified in this task-scoped review.

### Important

1. **The actual native-work deadline can exceed the session's absolute deadline.** `semantic_runtime.py:104` snapshots the remaining budget and passes it at `semantic_runtime.py:107`. Before starting its own timer, `_supervise` calls `_pressure_ok()` (`memory_runtime.py:322`); that check can spend up to 0.5 seconds in a subprocess (`brain_reader_guardian.py:16`). Only afterward does `_supervise` record `started` (`memory_runtime.py:345`) and launch the guardian. For example, a stage entered with 0.1 seconds remaining can spend 0.2 seconds obtaining a successful pressure reading, then still launch native work with another 0.1-second allowance. Earlier stages can similarly overrun their supplied remainder. The late-success check (`semantic_runtime.py:118`) refuses the result but does not stop the launch or preserve the required execution deadline. Carry the absolute deadline through supervisor preflight, recompute remaining time before launch, and refuse without spawning once it expires. Preserve the existing pressure and cleanup behavior. Add a focused controlled-clock regression covering slow initial pressure preflight; the current deadline tests replace `_supervise` and therefore do not exercise this boundary (`tests/test_semantic_runtime.py:37`). Coordinate the shared supervisor change because it is outside the task's owned files.

### Minor

- None identified that warrants expanding this task.

## Assessment

**Task quality: Needs fixes.** The implementation is well separated and the reported scoped evidence is substantial, but the new session's relative-budget handoff does not implement the specified absolute deadline across inherited supervisor startup.

## Review checks

- Read AGENTS.md, Task2a brief, implementer report, reviewer instructions and the complete eight-file diff. The tool truncated the first large output, so only the omitted diff portion was recovered in smaller segments; no changed source file was separately reread. Line-location searches supplied precise citations.
- Named dependency risk: source validation might omit exact UTF-8 size/hash/provenance checks. Inspected `CanonicalRecord` and `from_source`; those checks are present (`canonical_records.py:64`, `canonical_records.py:87`).
- Named dependency risk: the reused supervisor might reset the deadline or lose pressure/admission/cleanup guarantees. Inspected `_supervise`, waiting-marker helpers and the guardian preflight/loop; found the deadline issue above, with existing pressure and group cleanup otherwise retained (`memory_runtime.py:143`, `memory_runtime.py:314`, `brain_reader_guardian.py:16`).
- No tests rerun; no native/model/palace operations; no subagents. Reviewed the reported 50-pass covering run and clean Ruff results without treating them as independent reruns. Only this review report was written.
