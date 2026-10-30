# Task 3c: bounded derived BTREE replacement at 262,144 base IDs

Prepared 2026-10-25. **Preparation only; no native execution, fixture creation, product change or qualification-profile change.** Root requested this exact next scale after accepting the pinned-source conclusion in `index-tail-segment-plan.md`. The segment falsification matrix will not run. Root must review this plan, executable and hash manifest and separately assign the exclusive native slot before launch.

## What is being qualified

This diagnostic measures a full initial derived BTREE build, bounded exact lookups, and **whole derived BTREE replacement** after a 1,024-row tail. Replacement may change the active UUID. It must preserve canonical rows/schema/fragments/data-file bytes and retain old index files unchanged, while publishing a new index covering the same canonical data plus the tail. The prior UUID and pinned pre-replacement dataset version remain readable. There is no old-active-segment-preservation or tail-only-delta criterion.

Pinned Lance 4.0.1 native source shows scalar optimization creates a new UUID, combines existing BTREE entries with new data and writes a new derived index. `num_indices_to_merge=0` is not a scalar delta-only control; this diagnostic does not pass it. Atomic replacement of derived storage is distinct from destroying canonical originals. Source and prior 65K evidence are in `index-tail-segment-plan.md` / `index-scale-results.md`; they are not larger-scale qualification.

Actual migrated occurrences can expand into text pages, memberships, metadata pages, owners and receipts: the actual six-string physical-row corpus is likely millions of rows. 262,144 base IDs are the next measurement, **not corpus readiness**. Tiny synthetic payloads and 1,024-row fragments do not qualify actual payload distributions,256-entry bulk publication fragment counts, whole-owner proof, 52 MiB occurrence finalization, sustained throughput, cumulative versions/orphans, compaction or crash recovery. Product `MAX_INDEX_ROWS=16384` remains unchanged.

## Frozen operation sequence

Use one independent new private fixture, never the preserved 65K fixture or a real palace/source. Fixture path and case table are fixed in the prepared bundle; no caller-selected operation/path/count/limit/executable. Run once, sequentially, without warm-up, automatic retry, matrix adaptation or larger scale.

| Case | Required state / checks |
|---|---|
| `SEED-262144-00..31` | 32 writes of 8,192 canonical-valid generated rows. Final version 32, 262,144 rows /256 fragments, storage 2.2. Each writer streams <=256-row /128 KiB Arrow batches; no host-native import or corpus-sized row/ID list. |
| `BUILD-262144` | Initial `create_scalar_index("id","BTREE",name="castle_exact_id",replace=False)` under existing writer lock; no index beforehand. Require version 33, complete 256-fragment coverage and no tail. All canonical data-file hashes and fragment ID/physical-row pairs unchanged. This private diagnostic directly calls the native API; it does not raise or silently bypass the product maintenance admission policy. |
| `READ-262144-BASE` | Fresh worker: 30 distinct present IDs at ordinals 0,`N//2`,`N-1` and `floor(j*(N-1)/28)` for j=1..27; two fixed absent generator IDs at N+1,000,000 and N+1,000,001. Verify all six exact fields/canonical provenance and complete read-only fixture inventory. |
| `TAIL-262144-ROWS` | Append exactly 1,024 canonical rows at ordinals 262,144..263,167. Require version 34, 263,168 rows /257 fragments, one unindexed fragment /1,024 rows. |
| `READ-262144-TAIL` | Fresh worker: old first/middle/last, tail first/last, two absent IDs; require exactly 1,024 tail rows /1 fragment, correct fields and no mutation. |
| `REPLACE-DERIVED-BTREE-262144` | Existing writer lock; require version 34, bounded tail and old index description. Call only `dataset.optimize.optimize_indices(index_names=["castle_exact_id"])`. Require exactly version 35, 263,168 rows /257 fragments, zero tail, one new active UUID covering all current fragment IDs, last-update dataset version 34 and BTREE index_version 0. Canonical data-file path/size/allocation/hash inventory and fragment ID/row pairs must be identical before/after. Every old retained index file must still exist byte-identically. Report active files separately from the shared retained pool. |
| `READ-262144-REPLACED` | Fresh worker: same old/tail/absent exact lookup, full read-only inventory, current version 35 with zero tail. Reopen pinned version 34 in the same 2 s read: require same canonical rows/schema/fragments, original active UUID/files and the former 1,024-row tail. These metadata/file checks establish retained readable state for this fixture; they do not replace crash/lost-ack qualification. |
| `DUPLICATE-262144-WRITE` | Terminal synthetic append of the already indexed ordinal 0 row, unchanged fields. Require version 36, 263,169 rows /258 fragments. No index operation follows. |
| `DUPLICATE-262144-READ` | Fresh bounded candidate lookup must detect duplicate ID across indexed data and appended tail as expected `corrupt`; preserve evidence. |

Exactly 40 stages: 36 writes/builds/replacement and 4 reads, 116 s summed native deadlines. No 32 one-row-fragment branch is included; it remains a separate concern. 524,288 and larger scales remain unrun with no executable cases. Every stage verifies fixed expected row/fragment/storage/version geometry. A mismatch stops the entire run rather than revising the fixture.

## Preserved fixture and safety controls

Generator bytes match the prior reviewed fixture: ID `memory:`+SHA256(`index-scale-v1:`+decimal ordinal), kind `record`, text `f"index-scale ž😀\\x00\\r\\n {i}"` with actual NUL/CRLF, empty digest/receipt. Canonical compact sorted UTF8 provenance preserves origin/archive, local_only, legacy storage_format, caller fixture/ordinal, correct text_hash and chunk_start 0/chunk_end character length. Every generated row is validated with copied candidate `LanceExactStore._record` before a batch is yielded.

Pin storage 2.2, `max_rows_per_file=1024`, `max_rows_per_group=256`, `max_bytes_per_file=1 MiB` (soft file limit, not a RAM bound). Dataset open uses 1 MiB metadata/index caches and existing validate-on-decode/no-repetition-index parameters. Lookup uses copied candidate 32-ID IN boundary, scalar-index use, strict 32-row batches, no batch/fragment readahead and 1 MiB I/O buffer. Fresh worker means fresh process, not flushed OS cache.

| Control | Unchanged / stricter fixed value |
|---|---|
| Task /aggregate RSS | 192 MiB /256 MiB; actual host included; sampled tripwires, not kernel allocation limits |
| Read /write deadline | 2 s /3 s, including admission preflight, imports, native work, hashing/verification and response serialization |
| Global scheduling | Existing shared admission inode; one background stage, intent checks before/after acquisition; 50 ms background pressure probe, fail-closed normal-pressure checks and live interactive preemption |
| Cleanup | Existing inherited admission FD, retained process-group identity, descendant kill/reap and explicit FD close on every outcome |
| Frames | Existing 512 KiB outer cap; diagnostic request<=4 KiB /worker response<=32 KiB |
| Disk | 256 MiB fixture /512 MiB diagnostic run tree including versions, indexes, orphans and logs; >=2 GiB free before each stage; admission/post-stage accounting, not a hard in-call allocation cap |
| Orchestration | Existing 900 s outer cap; cannot extend any native stage |
| Paths/files | New private 0700 tree, 0600 files, owner/mode/type/no-symlink/no-hardlink checks and original recursive artifact validation; one fixed dataset path |

Guardian/runtime/exact guard support is copied byte-for-byte from `d4d6850dde81ab793bffecb6fdc5df424d084e2b`; canonical/store/codec helpers from `0278524e1bb85bcbea13bc6f2b55d8d50a34364f`. Manifest binds those private copies, host/worker/spec/plan and pinned installed inputs. The host imports no Lance/Arrow/SQLite/model/provider; native storage imports occur only after the copied exact supervision guard validates guardian ancestry and actual host PID. No changing-worktree import, source path override, arbitrary command, environment tuning, model call or optional framework is permitted.

Native import, recursive validation, full fixture hashing, retained index hashing and pinned-version metadata all consume their existing stage deadline. A read refusal therefore concerns combined lookup/validation work and cannot be attributed to the index alone. Before/after evidence collected before a logical exception is retained in the worker's bounded failure response where possible. A guardian kill may prevent such a response; preserve the refusal and fixture rather than infer rollback.

## Stop, evidence and handoff

Stop at the first admission/pressure/preemption/RSS/deadline/disk refusal, unexpected output, evidence mismatch or failed cleanup. No retries, smaller batches, tuning, budget changes, hidden follow-up read or larger scale. The terminal duplicate is an expected logical refusal only. Preserve the synthetic fixture and every completed/refused event; never clean it up before diagnosis.

JSONL events retain operation/ranges, status/reason, versions/row/fragment coverage, active UUIDs and files versus retained pool, canonical data inventory hashes, elapsed/task/aggregate peaks, disk before/after and cleanup. Native workers are separately supervised per stage. After completion/refusal, verify no matching host/worker/guardian remains and report the native slot released promptly. Write a separate results artifact with exact qualification scope, stop attribution, unrun cases and receipt hashes. No passing result automatically changes the production gate or profile.
