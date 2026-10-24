# Shared hardening split verification — 2026-10-24

Base: develop `9c5ba82eecb4716a9f5a2b69a5e616b605cccf04`.
Original combined candidate retained: `ad18037b582148d9b23f82e8c95a416092b42b9f`
(PR #106). The split plan and observable corrections are documented in
`docs/superpowers/plans/2026-10-24-castle-pr-split.md` and `docs/shared-hardening.md`.

Final local shared-stage source verification used Python 3.11.15 on macOS ARM64,
real cached models with offline Hugging Face/Transformers, and a test-only CPU
launcher that disables MPS with an introspection-preserving wrapper. This is
local CPU evidence, not native Linux or Windows certification.

```text
python castle_cpu_diagnostic.py tests/ -q --ignore=tests/benchmarks
  --ignore=tests/test_memory_runtime.py --ignore=tests/test_memory_api_integration.py
  --cov=cognitive_castle --cov-report=term-missing --cov-fail-under=0
2432 passed, 11 existing skips, 2 benchmark deselections; 89.56 seconds

python -m pytest tests/test_memory_runtime.py tests/test_memory_api_integration.py
  -q --cov=cognitive_castle --cov-append --cov-report=term-missing
48 passed; 10.78 seconds; combined coverage 85.18%, existing 85% gate passed

ruff check . && ruff format --check . && git diff --check
passed; 259 Python files formatted
```

The initial sandbox run failed twelve existing process-inspection tests. Host
process access resolved those failures without changing their assertions. An
intermediate explicit-config test fixture supplied ambient 1024-dimensional
configuration for a four-dimensional synthetic table; the fixture now supplies
its actual identity/dimension, with every preservation/graph assertion retained.
An interrupted focused run omitted the offline model-cache environment; it is
retained as invalid setup evidence and is not a passing verification claim.

Independent review found and reproduced two defects: Windows directory fsync
through the CRT, and explicit search configuration not reaching collection
identity checks. Both have watched failing regressions, fixes and passing tests.
The final reindex lane passed 13 tests; an independent embedding/reindex/context/
auxiliary-path review run passed 38. No important review findings remain.

CI run `40073959832` on the original candidate stalled inside pytest after a
successful installation; its diagnostic upload never ran. The same-day base
passed all six platform jobs. The exact original blocking call is unproven.
The shared split adds a bounded process supervisor, stack dumps, streamed logs
and owned-child cleanup; four watchdog regressions pass. This is diagnostic
instrumentation, not by itself proof that the timeout is resolved. The full
six-job matrix and union coverage gate remain mandatory before release.

Raw logs, XML, failed/intermediate runs and fault-injection evidence are retained
in the task's `castle-split-evidence-20261024` report bundle. Optional provider
tests, adapter tests, native acceptance and publication belong to later stages.

## Native Windows fixture corrections

Tests run `40080209610` completed all six platform jobs without timeout. Four
Linux versions and macOS passed; Windows completed its main suite in 283.54s
with nineteen fixture failures (2284 passed, 140 skipped), retaining full logs.
The coverage prerequisite correctly failed and release remained blocked.

The six-file correction changes no production code: encode diary fixtures as
UTF-8 and additionally assert exact stored text; capture actual directory mode
before read-only operations and require exact equality afterward; set both HOME
and USERPROFILE for private-home tests; use legal `graph #%.sqlite3` while still
testing URI escaping; and canonicalize expected source identities with the same
platform path semantics as production. No original scope, bytes, lock-inode or
revision-completion assertion is removed. All 97 affected-file tests pass locally
(12.85s), and independent isolated-snapshot verification also passed 97 tests.
Lint/format/diff checks pass. A fresh native Windows/full matrix remains required.

## Retained native matrix and stdout backpressure regression

At `8c5466f309f8a5a58d680e45c7cccd174046189f`, Tests run `40080992056`
passed all six platform jobs, lint and the unchanged union coverage gate.
Windows main reported 2303 passed/140 existing skips in 271.52s; its fresh
supervision reported 16 passed/32 existing skips. All original diagnostics and
coverage artifacts are retained.

Later provider/package matrices stalled again. Investigation independently
reproduced a defect in the supervisor: forwarding output to an undrained stdout
pipe while holding the local-log lock prevented the deadline thread from
logging or terminating its child. A new regression first failed against the old
implementation. Forward console output through a bounded queue and a daemon
using raw writes, outside the retained-log lock; keep the local log complete and
bound console shutdown. The regression requires exit 124, complete retained
payload, the deadline/exit records and a reaped child even when stdout is never
drained. All four previous regressions remain unchanged.

This establishes and fixes a deadline vulnerability; it does not identify the
original hosted pytest blocking call. Fresh full matrices on the updated heads
remain release gates. The six platforms, test selection and 85% gate are intact.

Host verification of the fix: five supervisor regressions passed in 5.42s;
the complete shared main suite passed 2433 tests in 81.82s and fresh supervision
passed 48 in 10.46s, with 85.19% combined coverage. This run used the real CI
launcher and cached offline models without the earlier CPU-preload wrapper.
Lint, formatting, diff checks and independent review passed.
