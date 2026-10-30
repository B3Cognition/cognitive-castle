# Task 3c: ID index scale qualification plan

Status: **PREPARATION ONLY; no native run authorized or performed by this artifact.** Root must accept the exact matrix below, review the eventual fixed diagnostic executable and hash manifest, and assign the exclusive native slot before execution. Root reported Task 3a `0278524e1bb85bcbea13bc6f2b55d8d50a34364f` approved during this preparation. This plan changes no product admission limit.

Root's preparation revision: prepare and freeze **only the ordered 65,536-ID cases** below (51 stages: 42 append/create, 3 index, 6 read; 147 s summed native deadlines). The 262,144/524,288 scales are explicitly `not_run_pending_root_review`, with no executable cases for them. The first-scale result must be reviewed before another matrix is prepared/authorized. Root has not assigned this diagnostic the native slot. Its executable/manifest location is recorded in `index-scale-prepared-bundle.json`.

## Decision and scope

Determine whether a larger initial BTREE and bounded incremental BTREE maintenance can complete within the existing exact-worker limits. The candidate's `build_id_index()` rejects more than 16,384 rows and otherwise performs a full replacement; it does not yet implement delta maintenance. A successful diagnostic would support a narrowly reviewed follow-up, not automatically remove that gate.

Use only new synthetic private fixtures. No real palace/source access, movement, capture, production configuration, models, providers, network, FTS/vector build, compaction, suite execution, or installation changes. No speculative adapter/framework work. Preparation used shell/source reads and stdlib hashing only; neither Lance nor Arrow was imported.

## Fixed safety envelope

Every native operation is a new `python -I <fixed-private-worker>` beneath the unchanged guardian. The host imports no Lance, Arrow, SQLite, model or provider package. Reuse a private copy of the reviewed `d4d6850dde81ab793bffecb6fdc5df424d084e2b` supervisor bundle, including its 50 ms background pressure probe; do not alter current fixture helpers or production files. Hash the copied files and worker before launch; reject mismatches. A small fixed operation dispatcher is enough; no configurable executable, arbitrary expression, caller-selected limits, or plugin framework.

| Property | Frozen ceiling / rule |
|---|---|
| Native task RSS | 201,326,592 B (192 MiB), guardian plus owned descendants |
| Aggregate RSS | 268,435,456 B (256 MiB), task plus actual diagnostic host |
| Writes/build/optimize | 3.0 s per operation, including serialization, preflight, native import and response |
| Reads/coverage/lookup | 2.0 s per operation, same absolute accounting |
| Scheduling | Existing global `memory_runtime._admission()` inode; one admitted stage at a time; background intent checks before/after acquisition and `background_preempt=True` |
| Pressure/cleanup | Existing fail-closed OS pressure checks, 50 ms background host probe, live interactive preemption, inherited admission FD, retained process-group identity, kill/reap on every exit |
| IPC | Existing 512 KiB frame ceiling; diagnostic request <=4 KiB, response <=32 KiB |
| Python/Arrow input | At most 256 rows and 128 KiB `RecordBatch.nbytes` per yielded batch; no whole-fixture list/table |
| Seed transaction | At most 8,192 generated rows; each transaction is separately supervised |
| Disk admission/accounting | <=256 MiB per fixture and <=512 MiB total diagnostic tree, including indexes, versions, temporary/orphan files and logs; require >=2 GiB free before each stage |
| Disk observability | Inventory before/after each stage; these are admission/post-stage stop thresholds, **not a hard in-call disk allocation cap**. No claim of a hard disk bound for monolithic native index work. |
| Orchestration | <=900 s overall; this never extends any 2/3 s native deadline. Release admission between stages. |

Do not use the semantic model stage's 512/640 MiB defaults or history budgets. Do not disable spilling, change thread/environment tuning after a refusal, grant a longer build deadline, or retry an actual resource refusal. Preserve the guardian's sampled-RSS caveat: it is a tripwire, not a kernel allocation ceiling.

The private bundle needs the original package path relationship: `memory_runtime.py`, `brain_reader_guardian.py`, a side-effect-free package initializer, and exact-worker guard/supervision support. `_require_supervision` verifies the guardian executable path and actual host ancestry, so copying one script and falling back to checkout imports is insufficient. Copy the reviewed dependencies identified by source inspection, bind every file, and verify that native imports occur only after the copied guard chain. Current fixture helpers may inform this chain but are not themselves the executable.

## Synthetic schema and construction

Three independent fixture directories, created mode 0700 beneath one new private temporary run directory; files mode 0600, current owner, no links, no foreign files. Preserve the candidate's six non-null UTF8 fields and schema metadata: `id,kind,text,provenance,digest,receipt`, `castle_exact_format=1`.

For ordinal `i`, set ID to `memory:` plus SHA256 of UTF8 `index-scale-v1:` followed by decimal `i`; kind `record`; text exactly `f"index-scale ž😀\\x00\\r\\n {i}"` with actual NUL/CRLF characters; digest and receipt both empty strings. Provenance is canonical sorted compact UTF8 JSON with `origin="archive"`, `local_only=true`, `storage_format="sqlite-fts5-utf8-v1"`, `caller={"fixture":"index-scale-v1","ordinal":i}`, correct original `text_hash`, `chunk_start=0`, and `chunk_end=len(text)` in characters. This preserves all original required fields and is validated through candidate `CanonicalRecord`/`LanceExactStore._record`, not merely accepted by raw lookup. Freeze precise serialization in `spec.py` and the worker manifest. This is high-cardinality pseudorandom ID data with deliberately small payloads, not a whole bulk-owner or long-content fixture.

In the native child, a generator creates one bounded list/batch at a time; `pa.RecordBatchReader.from_batches(schema, generator)` feeds `lance.write_dataset`. No corpus-sized `to_table`, `to_pylist`, ID array, JSON request, pandas conversion, or parent spool. The first seed transaction uses `mode="create"`, later transactions `mode="append"`. Pin `data_storage_version="2.2"` and record the actual returned storage version; use `max_rows_per_file=1024`, `max_rows_per_group=256`, `max_bytes_per_file=1 MiB`. File byte sizing is soft; record actual fragments/files. No overwrite or cleanup of old versions during qualification. A mismatch/refusal in setup stops this matrix; do not silently change fixture geometry.

Open with 1 MiB metadata and index caches and candidate read parameters `cache_repetition_index=False, validate_on_decode=True`. Retain candidate path, schema, writer-lock and recursive artifact checks; report their costs inside the same deadlines. Fixtures are constructed directly only to isolate index scale; they are not imported through the 256-entry publication API.

## Proposed exact matrix for root acceptance

Execute in order **65,536; 262,144; 524,288 base unique IDs**. Each scale is independent and disposable, so terminal duplicate injection cannot contaminate a later scale. No warm-up, timing repetition or blind retry. Counts below are hypotheses checked against actual manifests, never fabricated observations.

At each `N`, execute these fixed cases in order:

1. **SEED-N**: stream `N` rows in 8,192-row transactions (8/32/64 writes). Assert exact row count and expected generated range. Expected initial fragments are 64/256/512 at the chosen 1,024-row file setting; record actual count and stop on a geometry mismatch.
2. **BUILD-N**: under writer lock, require no existing ID index and call `ds.create_scalar_index("id", "BTREE", name="castle_exact_id", replace=False)`. This is explicitly a **full initial build**, and deliberately exercises more rows than the product's 16,384-row maintenance admission only inside this reviewed private diagnostic. Reopen and require complete base-fragment coverage, no tail, correct field/type, and unchanged data count. Do not call the candidate gated operation and mistake `maintenance_limit` for a native measurement.
3. **READ-N-BASE**: a fresh worker runs candidate `coverage` and `lookup_many` over exactly 32 deterministic IDs: 30 distinct present IDs at ordinals `0`, `N//2`, `N-1` and `floor(j*(N-1)/28)` for `j=1..27`, plus two frozen absent IDs outside every generated range. Verify all six field values against the generator and absence of the two missing IDs; bounded response contains hashes/counts only. Use the candidate's projected IN scanner, `use_scalar_index=True`, limit `group_size+1`, 32-row batches, strict batches, no fragment/batch readahead, 1 MiB I/O buffer. Record `explain_plan()` if available without a second scan; no full-scan comparison. Fresh process means cold process/cache, not a flushed OS cache.
4. **TAIL-N-ROWS**: append ordinals `N..N+1023` in one write. Fresh read requires exactly 1,024 tail rows and <=32 tail fragments; lookup includes old, tail-first/tail-last and absent IDs, totaling <=32. Tail remains eligible at the candidate's row boundary. Save segment/fragment evidence before maintenance.
5. **DELTA-N-ROWS**: under writer lock, first assert tail <=1,024 rows and <=32 fragments; call only `ds.optimize.optimize_indices(index_names=["castle_exact_id"], num_indices_to_merge=0)`. Reopen and collect metadata evidence below. Fresh **READ-N-ROWS-AFTER** repeats old/tail/absent checks and requires zero tail.
6. **TAIL-N-FRAGMENTS**: append the next 32 unique ordinals in 32 separate one-row commits. Fresh read requires exactly 32 tail rows in exactly 32 tail fragments and correct old/new/absent lookup. This tests the positive fragment boundary without assuming one transaction always yields one fragment.
7. **DELTA-N-FRAGMENTS**: same explicit preflight and delta API; require evidence below. Fresh **READ-N-FRAGMENTS-AFTER** requires zero tail and exact old/new/absent results.
8. **DUPLICATE-N**: terminal fixture-only write appends one already indexed base ID with identical fields; a fresh candidate `lookup_many` for that ID must return/refuse as `corrupt`, proving the indexed/tail union does not hide a duplicate. This expected logical refusal is not a resource pass or native scale refusal. Never optimize this corrupt fixture.

Maximum matrix: 206 append/create operations, 9 index operations, 18 reads =233 stages; their native deadlines sum to 681 s. Setup/inventory/logging must also fit the 900 s orchestration cap. If root reduces the matrix, freeze that revision before running. No extra 33-fragment or 1,025-tail-row branch is hidden in this proposal: negative policy-boundary behavior is source/Task3a evidence, while this diagnostic measures both positive boundaries at scale. Such additional native cases require an explicit revised matrix.

## Incremental evidence and exact labels

Before and after each delta call, record dataset version, total rows/fragments, all ID index segment UUIDs, each segment's fragment IDs and last-update dataset version, and a sorted private index-file inventory (relative path, byte size, SHA256). Hash files in bounded reads; do not load index files into Python. If this evidence cannot fit the read/write deadline, stop and label it, rather than moving work outside measured supervision.

Require the old segments/coverage and files to remain unchanged, new segment coverage to equal the previously unindexed fragment set, no overlap/replacement of old covered fragments, unchanged data rows/fragments, and zero remaining tail. If Lance representation does not expose enough evidence or it rewrites old segments, label **incremental_unproven** and stop; never translate a successful API return into bounded incremental proof. Retained old segment files alone are insufficient, because a rebuild can leave obsolete files on disk. Metadata/retention evidence supports delta structure for these fixtures; it cannot prove native code never read old index data or establish an asymptotic memory bound.

For every stage retain JSONL with case label, input ordinal range/count, exact operation, status/reason, dataset/index versions, actual fragment/segment counts, tail rows/fragments, elapsed time, sampled peak task/aggregate RSS, before/after logical and allocated disk bytes/file count, and descendant-cleanup outcome. Preserve stdout/refusal evidence and bind log hash to frozen manifest. Reads must leave the full artifact inventory unchanged. Distinguish:

- `qualified_fixture`: exact case, fields, coverage and measured budgets all passed.
- `expected_logical_refusal`: terminal duplicate was detected; no performance claim.
- `resource_refused`: actual task/aggregate RSS, deadline, pressure, admission/preemption or disk admission/accounting threshold stopped the sequence.
- `invalid_fixture_or_evidence`: schema, content, geometry, guard, frame, coverage, mutation or cleanup mismatch; no native scalability conclusion.
- `incremental_unproven`: delta semantics could not be established from retained evidence.
- `not_run`: everything after the first stop, with its causal stage.

Stop the whole matrix at the first unexpected result, actual resource/deadline refusal, unsafe path, lost/unparseable response, failed cleanup or evidence failure. No larger scale, silent fallback, reduced batch, changed thread count, repeated cold run, or budget increase follows it. Root decides a separately reviewed next experiment from that evidence. Preserve all completed/refused results; clean only this private tree after recording results and proving all owned processes are dead/reaped and admission is released.

## Source API evidence and limitations

Source inspection on 2026-10-24, installed metadata `pylance==4.0.1`; **L** = `/Users/ladislavbihari/.echelon/venv/lib/python3.12/site-packages/lance/`:

- Candidate `bulk_exact_store.py:12-15,18-84,441-455`: <=32 lookup IDs, <=1,024 tail rows /32 fragments; full segment-derived manifest coverage; IN reads include index plus tail and detect duplicates; maintenance >16,384 refused; permitted maintenance uses `create_scalar_index(...replace=True)`, a full replacement path.
- `L/dataset.py:2480-2501,2575-2598,2780-2794`: string BTREE creation, replacement and fragment-restricted uncommitted segment API. No documented BTREE total build RSS cap. Fragment-restricted builds/merges are deferred, not an automatic fallback.
- `L/dataset.py:5657-5688`: optimizer states appended rows are not automatically indexed; `num_indices_to_merge=0` creates a new delta; `index_names` limits names. Wrapper simply forwards `**kwargs` to native `_ds.optimize_indices`. `L/lance/__init__.pyi:359` does likewise. The installed distribution exposes no native Rust implementation here; native BTREE dispatch and internal temporary memory are not source-verified by this preparation. No inference that arbitrary kwargs such as a memory limit are accepted or effective.
- `L/lance/indices/__init__.pyi:71-90`: segment UUID, fragment IDs, last-update version, index type/fields/rows and segment list are available for structural evidence.
- `L/dataset.py:5911-6000`: `RecordBatchReader` accepted by `write_dataset`; file/group knobs and explicit storage version exist; file bytes are soft. Streaming input does not bound transaction or native encoder/index RAM.
- Reviewed `d4d6850` `memory_runtime.py:315-495`, `brain_reader_guardian.py`, exact guard chain: global admission, 50 ms background host pressure probe, absolute stage accounting, group/aggregate RSS, live preemption and descendant cleanup. These supervisor files are unchanged in `0278524`.

No native operation has been performed for this plan. Success would qualify only this fixture's ID build, lookup and two bounded delta cases under measured limits. It would **not** qualify bulk-owner membership/finalization/replay/whole hashes, 52 MB occurrence handling, actual migration fragment counts, realistic payload distributions, long-lived delta accumulation/merging, sustained throughput, crash recovery or whole 500k-corpus readiness. In particular, the seed's 1,024-row fragments are not evidence about the 256-entry real bulk publication path's fragment count. Those remain separate gates before source movement.
