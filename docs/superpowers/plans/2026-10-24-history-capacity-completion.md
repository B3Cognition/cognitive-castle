# Historical capacity and completion implementation plan

> **For agentic workers:** Use superpowers:executing-plans or superpowers:subagent-driven-development; preserve the existing authorized execution scope.

**Goal:** Complete the real unified historical conversion within the existing aggregate disk and memory budgets, with independent inventory proof.

**Architecture:** A history-specific storage policy reserves a complete transaction envelope before writes. A separate source inventory is reconciled before the job or repair can publish completion. Existing common query routes and exact records remain unchanged.

**Tech Stack:** Python, SQLite FTS5, the existing supervised pylance reader and pytest.

**Spec:** `../specs/2026-10-24-history-capacity-completion-design.md`.

## Global constraints

- Eight historical query stores; aggregate historical output 8 GiB.
- History per-store envelope 2 GiB, persistent pages at one third; live envelope 1 GiB.
- Free disk headroom 2 GiB plus outstanding reserved growth.
- Existing RAM/time/heap/cache/native limits and pressure/admission guards unchanged.
- Exact originals, source IDs, chunks, receipts and active stages preserved.

## Review focus

- Unregistered retained stores and stale sidecars consume budget too.
- Admission precedes database creation, hot-journal recovery and scope-index writes.
- An EOF or repaired gap cannot self-certify the source inventory.
- Legacy checkpoints and crashes preserve both exact data and explicit pending work.
- Tests refused by local pressure are reported as unrun; CI supplies actual results.

### Task 1: Historical write reservation

**Files:** new `cognitive_castle/history_storage.py`, `tests/test_history_storage.py`; modify `fast_memory.py`, `memory_history.py`, `unified_memory.py`, `memory_scope_indexes.py`, related tests and operator docs.

**Interfaces:** `MemoryStore._write_budget()` returns the write envelope (default 1 GiB). `HistoryMemoryStore` overrides it with central checked historical admission. A shared history admission function is also consumed by the raw scope-index upgrader. Importer capacity estimates and catalog checks use the same constants.

- [ ] Write regressions for historical growth beyond the old cap, live quota preservation, aggregate reservation, retained/orphan sidecars, headroom and unsafe/bounded traversal.
- [ ] Observe RED through guarded focused tests or a test-only CI commit.
- [ ] Implement central admission and wire every history write path; keep generic live writes unchanged.
- [ ] Run focused tests, independent review and required CI; qualify actual resume without changing the job cursor manually.
- [ ] Commit, publish and integrate only verified changes under existing user authorization.

### Task 2: Independent source inventory

**Files:** `memory_history.py`, fixture/native history tests and operator docs, on a separate isolated branch to avoid concurrent edits.

**Interfaces:** a bounded `_source_row_count(snapshot, version)` adapter returns the pinned dataset's independent row count; persisted `expected_rows` is validated. EOF and repair completion consume one reconciliation function that checks actual shard receipts/counts and pending stages against this value.

- [ ] Write premature-EOF, legacy-missing-count, count mismatch, invalid count, staged-row, repair and deleted-native-row regressions.
- [ ] Observe RED through guarded focused tests or a test-only CI commit.
- [ ] Persist independent count only after pinned snapshot validation; reconcile actual state before completion.
- [ ] Run focused tests and independent review; merge with Task 1 and run required CI.
- [ ] Qualify the real pinned count and complete inventory, then repeat installed live/history exact-read and hook proofs.

### Task 3: Finish real conversion and completion audit

- [ ] Resume exactly one bounded continuation after installed changes and normal pressure permit it.
- [ ] Reconcile all 519,641 source rows, zero gaps, receipts/stages, unchanged originals and the actual catalog.
- [ ] Verify installed common queries, exact pages, continuing live capture and honest pending transcript coverage.
- [ ] Report remaining limitations; mark the active goal complete only when its full required state is proven.
