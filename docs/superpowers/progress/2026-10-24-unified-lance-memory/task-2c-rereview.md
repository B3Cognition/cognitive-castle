### Finding Verdicts

- **Live priority can miss its 0.5-second window during pressure checking** — **ADDRESSED**. Trusted background probes now use `min(until, monotonic()+0.05)` and check the live priority lock both before and after the probe (`cognitive_castle/memory_runtime.py:318`). Initial supervisor preflight also uses this helper (`cognitive_castle/memory_runtime.py:354`). The synchronous 0.5-second probe window identified in the original review is therefore removed from both affected paths. Ordinary callers retain the original `_pressure_reason(until, _pressure_ok)` branch; unsuccessful short probes still fail closed, and an exhausted full-stage deadline remains `worker_deadline` (`cognitive_castle/memory_runtime.py:319`, `cognitive_castle/memory_runtime.py:328`).
- **Regression proof for the identified timing gap** — **VERIFIED IN DIFF AND EXISTING LOG**. The new parameterized test starts a real interactive process inside an already-entered pressure helper, runs a genuinely delayed subprocess through the actual timeout helper, and checks acquisition within 0.5 seconds plus probe/worker disappearance before admission release for both preflight and periodic phases (`tests/test_memory_preemption.py:16`). Separate tests check fail-closed short-probe exhaustion and a shorter absolute deadline (`tests/test_memory_preemption.py:144`, `tests/test_memory_preemption.py:164`). The existing `/tmp/castle-task2c-pressure-regression.log` records 12 passed/62 deselected, preflight acquisition 0.070386 seconds, periodic acquisition 0.070758 seconds, and both cleanup checks true. No test was rerun.

### New Breakage in the Fix Diff

- None found. The change is restricted to background pressure timing and its focused regression tests; it neither raises resource/deadline limits nor changes the ordinary supervisor branch (`cognitive_castle/memory_runtime.py:318`).

### Out-of-Scope Observations

- None newly identified. Cross-task boundaries and the original report's explicitly unattributed admission-refusal history remain as previously recorded; this scoped fix review does not broaden their qualification.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage.

**Spec compliance:** Approved for Task2c's reviewed scope; the original Important preemption gap is closed.

**Task quality:** Approved.

**Checks:** Read the appended fix report and `review-bb9afee..d4d6850.diff` once, applied the scoped re-review template, and inspected the existing affected-only test log. No tests, native/model operations, git mutations, product edits or subagents.
