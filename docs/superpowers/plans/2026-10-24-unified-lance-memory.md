# Complete unified Lance memory

**Goal:** fulfill the active user objective, “dokonci propojeni proste super pamet”:
one working memory for exact and semantic recall of new and historical records.

**Spec:** `docs/superpowers/specs/2026-10-24-semantic-preservation-design.md`.
The qualification plan is supporting evidence, not the definition of completion.

**Architecture:** Lance owns canonical exact records and profile-bound vectors.
Lightweight coordination retains queue/checkpoints, source registry and work state.
Exact capture precedes asynchronous semantic publication. Ordinary public routes
use one coordinator with policy filtering, stable evidence identities and explicit
coverage. Tokenization and inference run in separate sequential workers.

**Tech stack:** existing Python/Lance/PyArrow; pinned offline Tokenizers/ONNX;
existing supervisor and SQLite coordination; no external model provider.

## Global constraints

- Preserve user originals, exact text, canonical IDs, full provenance and exposure
  hashes. Preserve historical metadata descriptors separately from canonical text.
- Do not restart the old historical-to-SQLite converter or delete rollback data.
- Use isolated fixtures and fixed native diagnostic profiles: exact worker
  192 MiB task / 256 MiB aggregate, reads 2 s and writes 3 s; semantic stages
  512/640 MiB with one shared 5 s interactive deadline. Existing production
  dispatch remains unchanged until integrated qualification and reviewed cutover.
- Preserve pressure refusal, global admission and descendant cleanup. Never
  increase limits to make tests pass or run models/native data in the host.
- No caller-selected runtime commands, budgets, model paths or providers on the
  public API. Offline model artifacts must match a trusted pinned profile.
- No hidden fallback from canonical Lance records to SQLite text after cutover.
  Derived bounded startup caches may reference immutable canonical evidence;
  they do not become an alternative canonical ledger.
- Preserve lexical, dense, applicable KG and configured reranking behavior;
  resource refusals and indexing lag are explicit, not silently complete answers.
- Historical vectors require verified generation compatibility or explicit
  re-embedding under the new profile. Preserve long-input tails with offset-bound
  semantic windows; dimension equality alone does not authorize reuse.
- Run explicit tests through `scripts/safe_brain_tests.py`; native/model work must
  be separately supervised. Fixtures must never open the real palace.
- Do not activate the replacement, merge or claim completion based on a toy test.
  Review and verify the actual installed system against Task 6's completion audit.

## Task 1: atomic exact-record Lance store

Create `cognitive_castle/lance_exact_store.py`,
`cognitive_castle/lance_exact_worker.py` and `tests/test_lance_exact_store.py`.
Reuse the tested `canonical_records.py`; do not change existing public routes.

Implement `LanceExactStore(directory: Path, *, writable: bool = False)` with
`remember(request_id, text, provenance=None, *, namespace='operator')`,
`read_sources(ids)`, and `page(source_id, *, offset=0, limit=2048,
expected_hash=None)` matching MemoryStore receipts/pages. Add
`import_sources(batch_id, sources, *, namespace='migration')` for at most eight
full canonical sources per batch, preserving prior provenance exactly.

Use one private Lance dataset, with record and publication-receipt row kinds so
one atomic append can publish records and its durable replay receipt together.
IDs for receipt rows occupy a distinct prefix derived from namespace/request key;
record IDs remain unchanged. Choose a small explicit Arrow schema and bounded
projection/scans. Never materialize the entire dataset. Query expressions contain
only validated canonical IDs or hex digests; do not concatenate caller text.

Serialize writes with a private nonblocking per-store lock in addition to the
runtime's global admission. Validate owner, symlinks, modes and known schema;
reject duplicate/corrupt IDs, receipts or mismatched canonical content. A repeated
identical request returns its original receipt after reopening; changed content
under the same request key conflicts. Reusing identical canonical records in a
different import batch must not duplicate them. Verify receipt-referenced records
before acknowledging replay. Publish before acknowledgement; no checkpoint is
advanced by this store. Read-only operations must create nothing, stamp nothing
and never open the legacy backend.

The worker has a bounded JSON frame and fixed operation allowlist. Deny models,
network, child processes and optional Pandas; permit only the native exact-store
dependencies. Use a trusted bootstrap into this checkout so isolated test workers
cannot accidentally load the installed older checkout. Require the existing
supervisor process chain before storage access. Do not add a production route or
an unrestricted public command in this task.

TDD: use explicit disposable fixture workers under the existing supervisor and
the exact diagnostic profile above. Host tests must not import native libraries.
Cover create/append/reopen; replay/conflict; committed write followed by a lost
response and successful replay; record reuse across import batches; corruption
and duplicate rejection; Unicode/NUL/chunk boundaries; page hash/offset behavior;
read-only missing-store/no-mutation; unsafe paths and absent supervisor. Preserve
the previously passing canonical codec tests. Native test aggregate may use the
existing guarded-test default ceiling; all native children retain the fixed
192/256 MiB profile, and tests are sequential. Record every resource refusal.

Do not add premature indexes or claim full-corpus performance from this fixture.
The later migration/read qualification determines index and publication sizing.

## Task 2: bounded semantic runtime and vector publication

Package the qualified staged tokenizer/inference path into fixed workers and a
trusted pinned profile. No changes to the selected model/tokenizer are implicit.
Provide bounded embedding requests with source hash, canonical ID and exact token
window/character offsets. Use one deadline across interactive stages, global
admission and no resident model. Prove multilingual paraphrases, invalid-profile
refusal, stale input rejection, long-tail window coverage and process cleanup.

Add a durable semantic queue and Lance vector store keyed by semantic unit ID,
profile identity and exact input hash. Exact publication enqueues idempotently;
only acknowledged vector publication advances semantic progress. Background work
yields to interactive requests and new facts progress while history is pending.
Qualify larger batches and actual Lance nearest-neighbor reads under guards.

## Task 3: migration and coverage reconciliation

Reuse pinned immutable historical evidence and existing canonical algorithms.
Import existing live and historical canonical records from SQLite as a protected
migration source; continue the remaining historical rows directly into Lance.
Preserve occurrence identities, aliases, metadata/column pages and source scopes.
Stage oversized occurrences without publishing partial content. Record durable
resumable receipts, capacity reservations and exact counts/hashes.

Reconcile all 519,641 pinned source rows, current capture backlog and every
canonical occurrence. Reuse old vectors only with verified profile evidence;
otherwise schedule a bounded, resumable re-embedding migration. Retain originals
and rollback stores. Coverage must expose pending, changed, unsupported and
refused work without hiding omissions.

## Task 4: unified capture, recall and context routes

Adapt capture/ingest publication to the Lance store and retain lightweight state
transactions. Scope publication by explicit canonical IDs rather than SQLite
rowid assumptions. Keep checkpoint-after-receipt and work-state CAS behavior.

Replace the ordinary coordinator's canonical hydration and candidate providers.
Filter trusted policy/workspace/wing/room before ranking and limiting candidates;
validate source/input hashes and generation; fuse lexical, semantic and applicable
KG ranks; preserve configured reranking under its separately measured budget.
All ordinary CLI, Python, MCP, brain and context callers use this contract.
Selected-source grants and policy changes must not expose unauthorized candidates.

Restore bounded startup context without loading a model. If needed, maintain a
small derived cache tied to immutable source hashes and trusted policy/work-state
revision; never label an unavailable semantic operation complete. Qualify hook and
startup behavior against documented budgets and report actual limitations.

## Task 5: reviewed operator cutover and activation

Provide status, prepare, verify, activate and rollback operator operations with
explicit resource profiles and model provenance. Normal queries never perform
migration or index builds. Activate only a verified generation; retain capture
while switching and recover interruption without loss/duplicates.

Run focused regression suites and the required CI split, obtain independent
whole-branch review, push to B3 and merge when verified under the user's standing
authorization. Install that reviewed commit and enable only the bounded services.
Verify installed entry points and configured Codex/Claude host behavior; never
expand exposure permissions silently. Do not delete unrelated worktrees/data.

## Task 6: completion audit on the real installation

- New real dialogue and historical evidence are both found by paraphrase through
  ordinary routes, with original exact text, citation hashes and source identity.
- All required source rows/occurrences and semantic units reconcile; historical
  and live indexes have the same declared coverage. Pending full-corpus migration
  means this goal remains active, even if partial results are useful.
- Fresh semantic publication, restart/retry, long tails, policy restrictions,
  duplicate aliases, multilingual recall and stale vectors have real evidence.
- Resource/time/disk guards hold on installed code, background jobs yield, and no
  model remains resident. Report peak RSS, latency, lag and refusal behavior.
- Every ordinary route uses the same corpus; hooks/context restore appropriate
  exact evidence and work status. Article quality and SUE retain separate roles.
- Reviewed commits are merged into B3 and installed; no required fixes remain.
- Only after all these facts are verified may the active goal be marked complete.
