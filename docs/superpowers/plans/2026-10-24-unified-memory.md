# Unified exact memory implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. The user explicitly instructed implementation on 2026-10-24; do not request the same approval again.

**Goal:** Search fresh captured text and the declared historical inventory through the same bounded default interface, preserving exact evidence.

**Architecture:** Keep the live SQLite capture store and add a bounded catalog of historical SQLite stores. A common query/read service federates these stores. A separate supervised operator job snapshots and converts legacy Lance history incrementally; queries never open native archives or load models.

**Tech Stack:** Existing Python, SQLite FTS5, psutil guardian and installed pylance; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-24-unified-memory-design.md`

## Global constraints

- Exact text and distinct occurrences survive; originals remain unchanged.
- Fast: 128 MiB task / 192 MiB including parent, two-second read deadlines.
- Slow: 512 MiB task / 640 MiB including parent, ten-second total slices, normal memory pressure only.
- Same per-user admission lock, no resident worker, no embedding/provider/network during reads.
- Live store remains separate; at most eight historical stores, 1 GiB envelope each, 8 GiB aggregate, 4 GiB snapshots, 2 GiB free headroom.
- Trusted exposure is filtered before ranking and rechecked after reads. Scope is not authorization.
- Default APIs share canonical IDs and explicit partial coverage. Existing IDs/hash semantics remain valid.
- Full corpus qualification and resolved coverage are required before claiming the user goal complete.

## Review focus

- Hash-only authorization with many disallowed high-ranking hits must still return authorized matches (Task 1/3).
- Duplicate drawer IDs, equal text from different occurrences and changed revisions must not overwrite one another (Task 2).
- Concurrent writes, catalog replacement, corrupt/missing stores and stale cursors must never look like exhaustive empty success (Task 1).
- Death between durable row writes and checkpoint advancement must resume idempotently (Task 2).
- Oversized native decoding, pressure rejection, timeout and child cleanup must preserve admission and pending coverage (Task 4).

### Task 1: Canonical query/catalog service

**Files:** Create `cognitive_castle/unified_memory.py`, `tests/test_unified_memory.py`; modify `memory_worker.py` recall/read/page/status dispatch only.

**Interfaces:** `UnifiedMemoryStore(palace: Path)` exposes `recall(query, *, limit=8, match='all', workspace=None, wing=None, room=None, allowed_source_hashes=None, policy_epoch=None, cursor=None) -> dict`, `read_sources(ids)`, `page(...)`, `status(...)`. `register_history_store(palace, store_id, *, archive_id, state, indexed_rows=0, total_rows=None) -> dict` publishes a private bounded catalog entry pointing to `.memory-history/<store_id>/memory.sqlite3`; store_id is lowercase SHA256. `history_store_path(palace, store_id) -> Path` supplies that path's directory. Catalog errors fail closed; missing catalog means legacy history not yet registered, never complete.

- [ ] Write failing tests for live plus historical matches and exact page/hash, scopes, authorized ranking, distinct IDs, stale cursor and missing/corrupt shard coverage.
- [ ] Run `python scripts/safe_brain_tests.py --timeout 60 tests/test_unified_memory.py --tb=short`; verify expected failures.
- [ ] Implement private validated bounded catalog, shared deadline, deterministic per-store rank interleave, filters before limits, generation-bound cursors and exact hydration. Bind cursor to policy epoch and live data generation. Reuse MemoryStore privacy and validation.
- [ ] Route worker read operations through common service; writes remain live-only.
- [ ] Run new and existing fast-memory tests; commit only owned files.

### Task 2: Durable historical snapshot and conversion

**Files:** Create `cognitive_castle/memory_history.py`, `tests/test_memory_history.py`.

**Interfaces:** `history_operation(palace: Path, operation: str, arguments: dict) -> dict`, operations `prepare`, `index`, `status`. Prepare takes `source` path; index resumes immutable snapshot. Uses Task 1 catalog functions. Root owns subprocess runtime and CLI, so module never self-spawns.

- [ ] Write failing tests for private snapshot pinning, mutation/symlink rejection, streaming/capacity bounds, duplicate old IDs and row retry after interruption.
- [ ] Run guarded module tests, verifying failures before implementation.
- [ ] Implement resumable private snapshot copying with identity checks and explicit disk admission. Preserve pinned version/physical row cursor, exact metadata registry and aliases, bounded scanner projection excluding vectors and explicit buffers. No whole-table fallback. Persist data before checkpoint, visible gaps on rejected rows. Keep status compact and content-free.
- [ ] Test state transitions and resumability using small fixtures without loading native libraries under elevated pressure. Root separately qualifies native behavior when pressure allows.
- [ ] Commit owned files and report native qualification still required.

### Task 3: Public routes and exposure

**Files:** Modify `searcher.py`, `brain_api.py`, `cli.py`, `mcp_server.py`, `memory_context.py`; create `tests/test_unified_routes.py`; update legacy routing tests only where they explicitly assert legacy behavior.

**Interfaces:** Task 1 service is dispatched by `run_memory`. Pass trusted `allowed_source_hashes` and `policy_epoch` to recall before ranking; preserve post-read policy recheck. Root adds runtime allowed fields. Default search mode becomes `None`, explicit legacy modes retain old semantics with `legacy_index_only` labeling. Canonical result adapters keep source IDs/hashes/coverage.

- [ ] Write failing tests demonstrating ordinary CLI/Python/MCP/brain recall see live and historical evidence without native/model imports, including scope and hash-policy filtering.
- [ ] Run guarded route tests and inspect expected failures.
- [ ] Implement default routing via trusted BrainAPI/common bounded service. Extend schemas for scopes/cursors; reject unsupported legacy-only options on default route. Preserve exact reads and SUE binding. Workspace context must select from the common catalog without erasing existing work-state behavior.
- [ ] Test compatibility, missing policy and changed policy, output budgets and explicit legacy behavior; commit owned files.

### Task 4: Supervision, CLI and integration qualification

**Files:** Modify `memory_runtime.py`; create `memory_history_worker.py`, `history_cli.py`, `tests/test_history_runtime.py`; root coordinates CLI registration with Task 3.

**Interfaces:** `run_history(palace: Path, operation: str, arguments: dict) -> dict` uses existing admission and guardian with fixed slow ceilings. New `castle memory history prepare --source PATH`, `index`, `status` operator routes. No MCP ingestion controls.

- [ ] Write failing tests for fixed limits, pressure/admission rejection and owned-process cleanup; extend fast runtime validation fields.
- [ ] Run guarded tests and inspect expected failures.
- [ ] Refactor private supervisor to accept trusted budget parameters while preserving default fast ceilings, validation and cleanup. Isolated history worker allows native imports only in conversion, forbids network and child processes, validates host lineage and aggregate admission before storage.
- [ ] Integrate CLI and test cold default routes plus native scanner qualification when pressure is normal. Never bypass a pressure refusal.
- [ ] Run affected test groups separately, lint and format. Obtain independent whole-change review, repair material findings and run relevant regressions.
- [ ] Update user/agent docs with defaults, explicit legacy diagnostics, partial coverage and operator migration. Commit and prepare reviewable PR under existing authorization.
- [ ] Qualify full declared archive capacity and resumable progress before activation. Record actual live/new/history proof and resource measurements; do not claim completion while inventory or host integration remains unresolved.

## Execution record

- 2026-10-24: User explicitly directed continuation and resolving split searches. Existing isolated worktree `design/unified-memory` at `6c2842d`; installed baseline remains `67996f0`. Native work deferred while observed macOS pressure is 2; code and bounded tests proceed.
