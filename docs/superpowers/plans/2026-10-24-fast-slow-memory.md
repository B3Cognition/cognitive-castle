# Fast and slow memory implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make Castle usable as this assistant's exact local memory through low-memory recall and bounded SUE, without model loading or archive scans on queries.

**Architecture:** A private SQLite FTS5 sidecar stores bounded exact-text chunks. Supervised workers perform explicit writes, recall, paging and incremental JSONL ingestion. A trusted host binding isolates Codex policy and SUE state; existing Lance originals and legacy capture stay unchanged.

**Tech Stack:** Python standard library SQLite/JSON/filesystem; existing psutil-based supervision; existing CLI/MCP boundary and host skill.

**Spec:** ../specs/2026-10-24-fast-slow-memory-design.md

## Global constraints

- Never run local models, providers, the whole test suite, or a native real-archive scan. Local tests use `scripts/safe_brain_tests.py`, serialized, with temporary HOME and synthetic data.
- Exact UTF-8 text; chunks <=8192 bytes; explicit remember text <=65536 bytes; caller provenance <=512 encoded bytes and final per-chunk provenance <=1024 bytes; max8 selected chunks.
- Literal lexical queries <=1024 bytes, <=16 terms; recall wire result <=8192 bytes. Exact pages <=2048 codepoints and <=32768 encoded response bytes.
- Sidecar <=1GiB; SQLite page cache <=4MiB, mmap off, temporary work on disk, progress deadlines and bounded busy timeout. All files owner-private, no symlinks, fail closed on unsupported permissions.
- Worker group RSS tripwire128MiB; installed parent plus task processes target/tripwire192MiB; recall deadline2s, ingest/write deadline3s; macOS pressure must be normal. No claimed hard kernel RSS ceiling.
- Ingest source record <=1MiB before JSON parsing; one slice <=8MiB input, <=128 records and <=250ms cooperative work. Preserve incomplete tails for retry. Oversized/unsupported material remains explicitly unindexed, never falsely complete.
- Only registered original Codex/Claude conversation roots or explicit requested memories. No arbitrary workspace/import fallback. Legacy embedding capture stays paused.
- Global store under `<palace>/.memory`; trusted `CASTLE_BRAIN_HOST` selects `.brain/hosts/<host>/` policy/controller, with ASCII `[a-z0-9_-]{1,32}` IDs. Tool arguments never choose host or grant policy. Missing host preserves legacy default-deny behavior.

## Review focus

- Same text under a changed source revision must not overwrite history or make stale pages appear current.
- A caller-provided role, path, host or permission label is attribution, never authorization.
- A partial JSONL tail, oversized record or killed writer must not advance a checkpoint past uncommitted text.
- Busy storage, disk limits and a memory/pressure deadline must fail visibly without loading legacy backends.
- A small successful recall must not be described as exhaustive historical coverage; bound context as well as process memory.

### Task 1: Private exact-text store and lexical retrieval

**Files:** create `cognitive_castle/fast_memory.py`, `tests/test_fast_memory.py`.

**Interfaces:** `MemoryStore(directory: Path)` does not open/create on construction. Methods: `remember(request_id: str, text: str, provenance: dict | None = None, *, namespace: str = "operator") -> dict`; `recall(query: str, *, limit: int = 8) -> dict`; `read_sources(ids: list[str]) -> dict`; `page(source_id: str, *, offset: int = 0, limit: int = 2048, expected_hash: str | None = None) -> dict`; `status() -> dict`. Sources are `{id,text,provenance}`, IDs start `memory:` and are immutable snapshot identities. Returned sources have `origin: archive`, `local_only: true`, storage format, exact text hash and original chunk offsets. Ordinary operations validate before opening storage; reads never create or migrate it. Invalid input raises ValueError; expected unavailable/busy/quota/corrupt conditions return explicit status.

- [x] RED: exact roundtrip/reassembly for whitespace, emoji, non-ASCII and LF/CRLF, 8192-byte boundaries; changed request retry conflicts; identical retry stable IDs; lexical query operators cannot broaden literal search; denied unsafe file/symlink; bounded pages; restart; read never creates; disk and busy errors preserve committed rows.
- [x] GREEN: create owner-private SQLite schema/FTS with immutable exact chunks, bounded request receipts, source metadata and counters. Use transactions, bounded SQL, small caches, no mmap/native/model imports. Keep checkpoints/ingest support in a separate table via the next task's API.
- [x] Validate in guarded runner, then report diff; root commits after review.

### Task 2: Incremental original-transcript ingestion

**Files:** create `cognitive_castle/memory_ingest.py`, `tests/test_memory_ingest.py`.

**Interfaces:** `extract_messages(record: dict, format: str) -> list[dict]` yields exact text blocks with attributed role and block identity; recognize Codex canonical `response_item` message records (avoid duplicate `event_msg` copies) and Claude `user`/`assistant` message records. `ingest_slice(store: MemoryStore, path: Path, *, allowed_root: Path, format: str) -> dict` validates root/path, streams bounded JSONL, and checkpoints transactionally. Store integration may add `load_checkpoint(source_key)` and `save_checkpoint(source_key, checkpoint)` to Task1 after coordinating the exact interface; no independent connection code that bypasses store privacy/limits. A record's deterministic write IDs make partial retries safe even if the checkpoint is not advanced. Source version/record offsets/hashes and attributed roles accompany each exact text block.

- [x] RED: synthetic Codex/Claude records preserve decoded source text exactly; user/tool-result blocks are not conflated; duplicate event representations not doubled; truncated tail resumes; oversized input is not decoded or falsely indexed; changed/truncated/replaced file retains history; symlink/outside-root refused; killed/failed write does not skip text; repeated slice deduplicates.
- [x] GREEN: bounded JSON admission and extraction, deterministic source IDs/revisions, bounded checkpoints, explicit coverage states. Existing whole-file normalizers are not called. Record identity must remain stable when an append changes file size/mtime; label append/currentness assumptions honestly.
- [x] Validate guarded synthetic tests, then report diff; coordinate checkpoint interface with Task1 before editing its file.

### Task 3: Supervised memory execution

**Files:** create `cognitive_castle/memory_runtime.py`, `cognitive_castle/memory_worker.py`, `tests/test_memory_runtime.py`; minimally extend existing guardian helpers only where necessary.

**Interfaces:** `run_memory(palace: Path, operation: str, arguments: dict) -> dict` admits one worker per OS user, applies fixed per-operation deadlines/byte/RSS/pressure budgets, forbids model imports and network, and cleans owned descendants on timeout/parent death. Worker accepts one bounded JSON request and emits one bounded JSON response. Operations are remember/recall/read_sources/page/status/ingest_slice. Paths and host namespace are supplied by the trusted boundary; untrusted inputs cannot raise budgets or register roots.

- [x] RED: memory, time, pressure, output and process cleanup boundaries; concurrent busy admission; partial worker frames; missing support fails closed before storage; no model imports/network; synthetic store persists across separate worker invocations.
- [x] GREEN: reuse proven ownership/guardian concepts without importing Lance. Include parent RSS in admission/reporting; measure complete installed chain before claiming budgets. Keep hooks off until this passes.
- [x] Validate under outer guarded runner; do not nest competing test locks or allocate unbounded memory.

### Task 4: Host-bound API/CLI and fast/slow guidance

**Files:** modify `brain_api.py`, source adapter routing, MCP/CLI registry, `tests/test_brain_api.py`, add integration tests; update `skills/castle/SKILL.md`, `.claude-plugin/skills/castle/SKILL.md`, `docs/brain-loop.md`.

**Interfaces:** Add strict `castle_memory_remember` (protocol_version1, request_id,text, optional provenance), `castle_memory_read` (protocol_version1,source_id,offset,limit,expected_hash), `castle_memory_status` (protocol_version1). Add CLI equivalents under `castle memory`. Reuse `castle_brain_recall` and `archive_ids` for new sidecar snapshots. Fast recall previews are exact contiguous slices with offsets, truncation flag and hashes; enforce encoded8KiB response budget. A missing/unindexed sidecar reports unavailable/coverage gaps, never starts a native fallback or backfill.

- [x] RED: host cannot be chosen in tool args; invalid launch host fails before writes; Codex and other-host policy/state remain isolated; deny/revoke across recall/pages/root replay; exact memory→recall→page→SUE binding across restart; read-only requests never invoke mining; bounded wire response on control characters and Unicode.
- [x] GREEN: trusted host configuration, host-private policy and controller path, explicit memory handlers, supervised source routing, operator-only root registration/ingest CLI. Existing native source behavior remains explicit and gated. Update skill to select fast recall for history, slow SUE for substantive ambiguity, neither for trivial work; remember exact text and distinguish indexed coverage.
- [x] Validate relevant guarded suite and independent integration review.

### Task 5: Activate and measure the complete installed path

**Files:** operator activation report/backups outside repo; safe capture integration only if all previous checks are complete.

- [x] Finish/merge PR104 independently at its verified remote head; preserve the dirty main checkout and installed capture-safety ancestry.
- [ ] Review new memory branch, run full remote CI and guarded relevant local tests. Merge only when checks pass.
- [ ] Install without model/dependency downloads, register Codex-only host policy and bounded tool list/skill, keeping other hosts and legacy capture paused.
- [ ] Installed synthetic smoke: exact remember, lexical recall, paging, restart, SUE binding, denial/revocation; record complete parent/worker memory and deadlines.
- [ ] Register only existing authorized conversation roots. Index a bounded slice, perform one narrow authorized real recall, and report coverage. Backfill is checkpointed and resumable, not a claim of complete migration.
- [ ] Enable a distinct model-free capture path only after measured pressure/deadline/retry tests. If that condition is not met, explicit memories and operator ingestion remain usable and capture stays visibly paused.
- [ ] Report actual merge/install state and any required client reconnect; never claim tools in an existing MCP process reloaded automatically.
