# Task2a fix round 1 review — 56911a6..fba868f

## Spec Compliance

- ✅ **Spec compliant for this fix scope. Original Important 1: ADDRESSED.** `SemanticSession` now passes its original absolute deadline (`semantic_runtime.py:112`). The supervisor starts accounting at entry, caps its deadline by that timestamp, checks expiry after pressure preflight and before guardian launch, and passes the same timestamp to the guardian (`memory_runtime.py:325`, `memory_runtime.py:333`, `memory_runtime.py:349`, `memory_runtime.py:375`). The guardian caps its own deadline and refuses expired pressure preflight before native-child launch (`brain_reader_guardian.py:142`).
- ✅ Initial and recurring pressure probes use the remaining budget and check expiry after the blocking probe; selector waits also respect the remainder (`brain_reader_guardian.py:16`, `brain_reader_guardian.py:33`, `brain_reader_guardian.py:168`; `memory_runtime.py:403`). Existing pressure refusal and cleanup paths remain in place. The diff does not increase public budgets or alter production dispatch.
- ✅ Earlier artifact-provenance evidence item resolved: `profile-receipt-comparison.json:2` reports six matching files, reference constants and manifest receipts, with the separate artifact-byte verification scope stated explicitly.
- ⚠️ Previously deferred historical-vector compatibility, real-archive qualification, vector publication, durable contiguous coverage and active-stage preemption remain future integration tasks; this verdict does not qualify them.

## Strengths

- The fix addresses both host and guardian preflight instead of merely rejecting late successful responses (`memory_runtime.py:333`, `brain_reader_guardian.py:143`). The shared pressure helper keeps deadline/refusal semantics consistent (`brain_reader_guardian.py:33`).
- Focused tests reproduce slow initial pressure in the real supervisor and guardian, check pressure subprocess timeout bounds, and exercise the semantic session through the real supervisor (`tests/test_memory_runtime.py:537`, `tests/test_memory_runtime.py:557`, `tests/test_memory_runtime.py:576`; `tests/test_semantic_runtime.py:177`). Recurring-pressure coverage asserts the same absolute timestamp at successive checks (`tests/test_memory_runtime.py:367`).

## Issues

- No remaining original finding or new actionable defect identified in the fix diff.

## Assessment

**Task quality: Approved.** The absolute deadline now survives supervisor and guardian preflight without renewed stage budgets, and the scoped regressions cover the original failure. Shared-file changes were explicitly authorized by the controller.

## Review checks

- Read the six-file fix diff once, the appended fix report and the six-file receipt-comparison evidence. Scope was original Important 1 and new breakage introduced by this fix; no broader codebase inspection.
- Reviewed reported RED evidence (three failures), final covering evidence (48 passed) and clean Ruff/format/diff checks. No tests rerun; no native/model/palace operations; no subagents. Only this review report was written.
