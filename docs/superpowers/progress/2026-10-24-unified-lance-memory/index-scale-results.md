# Task 3c first-scale index qualification results — 2026-10-24

**Outcome: `incremental_unproven`; matrix stopped at its first evidence failure.** The native slot was released after cleanup. The private fixture and receipts remain preserved. No matrix retry/advance, larger scale, matrix adaptation, product edit, qualification-profile change, source movement, model/provider call or suite run followed.

Frozen authorization: manifest `45dd233c65aed521e6b986a52cf68daec239cafee85fd457442d31062479789e`, only the 51 ordered 65,536-ID cases. Copied guard/runtime/exact-worker support was pinned to `d4d6850`; candidate record/store/codec helpers to `0278524`. Budgets stayed 192 MiB task /256 MiB aggregate, 2 s read /3 s write, with existing global admission, fail-closed pressure, background preemption and group cleanup.

## Completed cases and stop

Twelve stages qualified before the thirteenth stage failed its structural proof. Eight streamed seed transactions produced 65,536 canonical-valid rows in 64 fragments (storage 2.2, data version 8). The initial BTREE build published version 9, covered all 64 fragments, and reported index data version 8. Its sole active segment was `ec935110-67d9-4165-8992-afa5938122c9`, `index_version=0`, last-update dataset version 8, fragment IDs 0..63.

Fresh-worker base lookup checked 30 present IDs and 2 absent IDs, all six exact fields and canonical row validity. Its full fixture SHA inventory remained unchanged. Appending 1,024 new canonical rows produced version 10 and 65 fragments; the fresh-worker tail lookup checked 5 old/new present IDs plus 2 absent IDs and correctly reported 64 indexed fragments plus 1 unindexed fragment /1,024 rows. Reads include full fixture hashing and recursive validation inside their 2 s deadline: success qualifies this combined work, and a future deadline refusal could not be attributed to ID lookup alone. These were fresh processes, not flushed OS caches.

`DELTA-65536-ROWS` called exactly `optimize.optimize_indices(index_names=["castle_exact_id"],num_indices_to_merge=0)` and returned from the API; subsequent frozen `verify_delta` raised `RuntimeError: incremental_unproven: old segment changed`. It compared entire old segment dictionaries (UUID, fragment IDs, dataset update version, index version). This was an evidence/structural stop, **not a task/aggregate RSS, pressure, admission or deadline refusal**. The worker assigns its before/after snapshots to the result only after that verification, so the failed receipt did not preserve which field changed. The separately authorized read-only inspection below now confirms active UUID replacement; it does not establish the native internal rebuild/read algorithm.

## Per-stage measurements

RSS values below are sampled bytes, including guardian plus descendants for task, and actual host plus task for aggregate. Disk columns cover the private fixture after the stage; ceilings are admission/post-stage thresholds rather than hard in-call disk limits.

| Case | Outcome | Seconds | Task RSS B | Aggregate RSS B | Fixture logical B | Fixture allocated B | Files |
|---|---|---:|---:|---:|---:|---:|---:|
| SEED-65536-00 | qualified_fixture | 1.2827 | 146341888 | 171278336 | 1238293 | 1257472 | 11 |
| SEED-65536-01 | qualified_fixture | 0.7688 | 148029440 | 173047808 | 2484357 | 2519040 | 21 |
| SEED-65536-02 | qualified_fixture | 0.8666 | 147849216 | 173375488 | 3731597 | 3780608 | 31 |
| SEED-65536-03 | qualified_fixture | 0.7943 | 148160512 | 173703168 | 4980525 | 5046272 | 41 |
| SEED-65536-04 | qualified_fixture | 0.8027 | 147849216 | 173441024 | 6229157 | 6311936 | 51 |
| SEED-65536-05 | qualified_fixture | 0.7672 | 147734528 | 173326336 | 7477940 | 7577600 | 61 |
| SEED-65536-06 | qualified_fixture | 0.7802 | 148389888 | 174014464 | 8729372 | 8843264 | 71 |
| SEED-65536-07 | qualified_fixture | 0.7835 | 147341312 | 172982272 | 9981276 | 10113024 | 81 |
| BUILD-65536 | qualified_fixture | 0.6543 | 181305344 | 206962688 | 12937637 | 13078528 | 85 |
| READ-65536-BASE | qualified_fixture | 0.6650 | 159367168 | 185024512 | 12937637 | 13078528 | 85 |
| TAIL-65536-ROWS | qualified_fixture | 0.6475 | 145031168 | 170688512 | 13099899 | 13246464 | 88 |
| READ-65536-ROWS | qualified_fixture | 0.6554 | 154992640 | 180649984 | 13099899 | 13246464 | 88 |
| DELTA-65536-ROWS | incremental_unproven | 0.6509 | 175620096 | 201277440 | 16111068 | 16265216 | 92 |

Orchestration elapsed 10.201083 s; maximum task 181,305,344 B and aggregate 206,962,688 B occurred during the full build, below unchanged 201,326,592 /268,435,456 B tripwires. Longest stage 1.2827 s was the first seed transaction. The stopped delta measured 0.6509 s, 175,620,096 B task /201,277,440 B aggregate. No resource refusal was observed. Transient peaks between RSS samples remain possible.

## Preserved filesystem evidence and its limit

A stdlib-only post-stop read compared the two original BTREE files against the full-build receipt: both remain byte-identical. A new directory `853bdc93-a82c-45a8-9d26-3e039e167a72` contains `page_data.lance` 2,999,642 B and `page_lookup.lance` 3,759 B, totaling 3,003,401 B. The original pair totals 2,949,257 B. File retention and similar new output size are insufficient to establish the current active index segment set, exact changed descriptor field, or whether native code read/rebuilt all old entries. This filesystem evidence alone did not diagnose that distinction; the separately authorized read-only inspection below subsequently resolved the active UUID/coverage change.

Final measured fixture: 16,111,068 logical B /16,265,216 allocated B, 92 files. Final native-stage run tree including its then-current log: 16,123,836 logical B /16,281,600 allocated B, 93 files. Small summary/cleanup/filesystem receipts were added afterward using stdlib only. All are far below the 256 MiB fixture /512 MiB diagnostic accounting thresholds; no old versions or fixture files were deleted.

## Not run and cleanup

Exactly 38 remaining first-scale stages are `not_run`: `READ-65536-ROWS-AFTER`; all 32 one-row fragment-tail commits; fragment-tail read/optimization/post-read; duplicate write/read. Both 262,144 and 524,288 scales remain `not_run_pending_root_review`, with no executable cases in this bundle. The 32-commit geometry was not changed.

Frozen supervisor cleanup completed, launch exited 2, and the final stage reported no host descendants plus admission FD closed. An independent exact-executable-path process inventory found no diagnostic host, worker or guardian. Native slot release was reported promptly to root. Fixture/evidence remain private and preserved for diagnosis.

## Receipts

| Artifact | SHA256 |
|---|---|
| [events.jsonl](/private/tmp/castle-indexscale-prep-vm83c4d9/run/events.jsonl) | `de4d1f0cdf01d35bdeaadaf88712d334561b0ed321262eebd84d79dd2435e489` |
| [summary.json](/private/tmp/castle-indexscale-prep-vm83c4d9/run/summary.json) | `070681b8ccd630c1cc63814350ed4c7a2c7565d62f13bc59cbf120a8b88ccb7e` |
| [cleanup-receipt.json](/private/tmp/castle-indexscale-prep-vm83c4d9/run/cleanup-receipt.json) | `26b43d0ab87e020009842ba00fd3af6be63b25416b620c1bc789cf4d30b3e941` |
| [post-stop-filesystem-evidence.json](/private/tmp/castle-indexscale-prep-vm83c4d9/run/post-stop-filesystem-evidence.json) | `5e61fdacfe3d912b3f6ecfb4f0aca672e8747e75f115149047d7e5de4d748686` |

Frozen executable and source manifest: [/private/tmp/castle-indexscale-prep-vm83c4d9/manifest.json](/private/tmp/castle-indexscale-prep-vm83c4d9/manifest.json). Fixture: `/private/tmp/castle-indexscale-prep-vm83c4d9/run/fixture-65536`.

## One authorized read-only diagnosis attempt

Root separately reviewed the corrected active-file/private-path checks and authorized exactly one read-only inspection with manifest `9d8c13bc2d410e9645da7987fe54aecdc006e911b9d3e288f206692d376531c4`. It used the original verified private guard/helper bundle, unchanged 2 s /192 MiB task /256 MiB aggregate, global admission, pressure, background preemption and cleanup. The original frozen matrix was not resumed.

**Outcome: `unavailable/background_preempted`.** The one attempt measured 0.7935 s, 111,083,520 B task /135,364,608 B aggregate and exited 2. It returned no version snapshots, active UUID/fragment/version/file comparisons or successful read-only inventory proof. At this first attempt the exact changed segment field remained unknown; the later explicitly authorized second attempt below resolves it. The first receipt remains preserved. This was a scheduling/preemption refusal, not evidence that index inspection exceeded RSS or deadline limits.

No automatic retry, optimizer/index mutation, source movement or matrix advancement followed that first inspection. Root later separately authorized the second attempt described below. Stage cleanup reported admission FD closed and no host descendants. An independent exact-path process inventory found no inspection host/worker or original guardian; the native slot was promptly released. Both the original fixture and all receipts remain preserved. The originally stopped delta remains `incremental_unproven` and all 38 remaining matrix cases stay `not_run`.

| Diagnosis artifact | SHA256 |
|---|---|
| [RO inspection receipt](/private/tmp/castle-indexscale-inspect-d4djlfc1/receipt.json) | `1ca46c26fc766cb37c4ff0b314af7b958e1aa0cec5bd9ac21b2251148cb40958` |
| [RO cleanup receipt](/private/tmp/castle-indexscale-inspect-d4djlfc1/cleanup-receipt.json) | `6a1cc69807e77a37c1c0f220a960dd6ed6ee9e2b0f2577b3f9e2f87a59072d5e` |

## Explicitly authorized second read-only attempt

After root confirmed live interactive contention had cleared and assigned a new native slot, root authorized exactly one separate second attempt. Its host/worker bytes were identical to the reviewed first attempt; new path-bound manifest: `fcb38b238293bc8c2a3080bb1af62a0680f69793dca33caa89e676d0f0d1157e`. This was an explicit retry after a scheduling-state change, not an automatic retry loop. The first preemption receipt was retained unchanged.

**Read-only diagnosis succeeded** in 0.9130 s, sampled 134,053,888 B task /158,842,880 B aggregate, under unchanged 2 s /192 MiB /256 MiB. Full fixture SHA inventory was identical before/after: `212e598d40b9d758dbcbf16b185e75f39bb1591c0c82408d531d6be502973d33`, 16,111,068 logical B /16,265,216 allocated B, 92 files. Both pinned snapshots contain 66,560 rows /65 fragments, storage 2.2. This success covers combined native imports, metadata inspection and full artifact hashing, not an index-only microbenchmark.

| Active description | Version 10 before optimization | Version 11 after optimization |
|---|---|---|
| Segment count |1 |1 |
| Active UUID |`ec935110-67d9-4165-8992-afa5938122c9` |`853bdc93-a82c-45a8-9d26-3e039e167a72` |
| Covered fragment IDs |0..63 |0..64 |
| Last-update dataset version |8 |10 |
| Segment index version |0 |0 |
| Tail |1 fragment /1,024 rows |0 fragments /0 rows |
| Active index file logical bytes |2,949,257 |3,003,401 |

The **old UUID is removed from the version 11 active description**, and the new UUID replaces it while covering all 65 fragments. This is a replacement of the active index segment and output files, not merely an updated version field on an unchanged old segment plus a fragment 64-only delta. Therefore the frozen criterion requiring preserved old segments and new-tail-only segment coverage is not met by this API call on this fixture. The descriptors and output files do not independently reveal whether native implementation internally re-read all old rows, merged existing entries or used another reconstruction algorithm; no asymptotic RAM/I/O conclusion is claimed.

The shared retained `_indices` pool contains four files. Each version's `active_files` is derived only from its active UUID directory. The old pair remains byte-identical in that retained pool but is inactive in version 11; its retention does not rescue the delta-only claim.

| Active version | Relative file | Logical B | SHA256 |
|---|---|---:|---|
| 10 | `ec935110-67d9-4165-8992-afa5938122c9/page_data.lance` | 2945754 | `900ef9d1cee391eefe463aaf5c7e3c938aa0e48b0e18ee966322335efaad786a` |
| 10 | `ec935110-67d9-4165-8992-afa5938122c9/page_lookup.lance` | 3503 | `d1c3d566412361f47cd0f63a122a6f13dadc14c26df303699a072ec17bc65c99` |
| 11 | `853bdc93-a82c-45a8-9d26-3e039e167a72/page_data.lance` | 2999642 | `b46babcc42c924c0891f0d395e4d3bf2b9a614af1c9c5db7dd42cbf349b66aa0` |
| 11 | `853bdc93-a82c-45a8-9d26-3e039e167a72/page_lookup.lance` | 3759 | `9cd7d195878342d288166128e3ddd3faf5d4e0e86fc83453b6a15d8f5a7d3fef` |

No index mutation, optimizer rerun, third attempt or matrix advancement followed. The original result remains `incremental_unproven`, with 38 remaining first-scale cases and both larger scales unrun. Stage cleanup reported admission FD closed and no host descendants; an independent exact-path inventory found no inspection host/worker/guardian. Native slot release was reported promptly. The private fixture and all receipts remain preserved.

| Second-attempt artifact | SHA256 |
|---|---|
| [receipt.json](/private/tmp/castle-indexscale-inspect-second-ryh87z_x/receipt.json) | `278dcc098702370e0edb438b76d70655833116f6dcefe7eee45ac7c91852ed91` |
| [cleanup-receipt.json](/private/tmp/castle-indexscale-inspect-second-ryh87z_x/cleanup-receipt.json) | `6a1cc69807e77a37c1c0f220a960dd6ed6ee9e2b0f2577b3f9e2f87a59072d5e` |
| [comparison-summary.json](/private/tmp/castle-indexscale-inspect-second-ryh87z_x/comparison-summary.json) | `f9c2befe50784dceb5fc9401ff501de197a030cf19a14f6c94b3ff7be0380052` |

This run qualifies only its completed 65,536-ID initial-build and bounded lookup fixture cases. Incremental maintenance, 32-fragment tails, duplicate detection at this scale, larger cardinalities, bulk-owner proof/whole hashes, realistic payloads and migration fragment counts remain unqualified. The product 16,384-row maintenance gate is unchanged.
