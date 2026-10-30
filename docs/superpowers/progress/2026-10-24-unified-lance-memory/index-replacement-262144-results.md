# Task 3c: 262,144-ID derived BTREE replacement qualification results

**Outcome: actual task-RSS scale refusal at the initial BTREE build.** The run stopped immediately, preserved its synthetic fixture/evidence, and released the native slot after cleanup. No retry, settings/budget change, larger scale, profile promotion or further native inspection followed. The derived replacement case was never attempted.

Root authorized exactly the 40 frozen cases in `/private/tmp/castle-indexreplace-262144-vrr12b2u/run.py`, manifest `a0a8b5e239d68a0ef9c35726f299b83ed120a4a9983c1e6f0299bb6e099bfe6d`, under the pinned Python 3.12.11 interpreter. The complete private d4d6850 guardian/runtime/exact guard and 0278524 canonical/store/codec copies were hash-verified. Limits remained 192 MiB task /256 MiB aggregate, reads 2 s /writes 3 s, background priority, shared admission, live pressure/preemption and descendant kill/reap.

## Completed, refused and not run

All 32 streamed seed writes passed. Last acknowledged state: version 32, 262,144 canonical-valid six-string rows, 256 data fragments, storage 2.2. No whole-fixture row/ID list or native storage import occurred in the host. Each native child streamed <=256-row /128 KiB Arrow batches and validated canonical provenance before yielding.

`BUILD-262144`, the 33rd stage, called the full initial derived BTREE creation under the existing writer lock. It returned `unavailable/worker_memory_limit` after 0.6971 s. Sampled task RSS reached 209,240,064 B (199.546875 MiB), exceeding the 201,326,592 B (192 MiB) task tripwire by 7,913,472 B. Sampled aggregate RSS was 235,454,464 B (224.546875 MiB), below 268,435,456 B (256 MiB). This is a real task-memory refusal; it was neither a deadline refusal nor a failed delta-preservation criterion. It does not measure how long a completed build would take.

Seven later cases are explicitly `not_run`:

- `READ-262144-BASE`
- `TAIL-262144-ROWS`
- `READ-262144-TAIL`
- `REPLACE-DERIVED-BTREE-262144`
- `READ-262144-REPLACED`
- `DUPLICATE-262144-WRITE`
- `DUPLICATE-262144-READ`

These comprise base lookup, 1,024-row tail append/read, whole derived replacement/read and terminal duplicate append/read. No 32 tiny-fragment branch existed. 524,288 and larger scales remain unrun. Correctness, replacement, retained-state and duplicate checks at this scale therefore remain unqualified.

## Per-stage measurements

RSS and disk are exact recorded bytes; RSS is a sampled tripwire rather than a kernel allocation ceiling. Disk columns are private fixture admission/post-stage accounting, including manifests/transactions/derived artifacts; they are not hard in-call disk limits.

| Case | Outcome | Seconds | Task RSS B | Aggregate RSS B | Fixture logical B | Fixture allocated B | Files |
|---|---|---:|---:|---:|---:|---:|---:|
| SEED-262144-00 | qualified_fixture | 1.1719 | 147652608 | 172703744 | 1248342 | 1265664 | 11 |
| SEED-262144-01 | qualified_fixture | 0.7674 | 147636224 | 172736512 | 2495558 | 2531328 | 21 |
| SEED-262144-02 | qualified_fixture | 0.7638 | 147554304 | 172769280 | 3742797 | 3788800 | 31 |
| SEED-262144-03 | qualified_fixture | 0.7887 | 148078592 | 173293568 | 4990061 | 5050368 | 41 |
| SEED-262144-04 | qualified_fixture | 0.8331 | 149159936 | 174751744 | 6238437 | 6311936 | 51 |
| SEED-262144-05 | qualified_fixture | 0.7555 | 147488768 | 173096960 | 7484917 | 7569408 | 61 |
| SEED-262144-06 | qualified_fixture | 0.7576 | 148422656 | 174063616 | 8734684 | 8830976 | 71 |
| SEED-262144-07 | qualified_fixture | 0.7649 | 148553728 | 174194688 | 9985947 | 10100736 | 81 |
| SEED-262144-08 | qualified_fixture | 0.7958 | 148750336 | 174391296 | 11238899 | 11366400 | 91 |
| SEED-262144-09 | qualified_fixture | 0.7683 | 147570688 | 173228032 | 12493603 | 12644352 | 101 |
| SEED-262144-10 | qualified_fixture | 0.7831 | 148439040 | 174129152 | 13746348 | 13918208 | 111 |
| SEED-262144-11 | qualified_fixture | 0.7928 | 148799488 | 174489600 | 15000204 | 15192064 | 121 |
| SEED-262144-12 | qualified_fixture | 0.7616 | 148914176 | 174620672 | 16279695 | 16486400 | 131 |
| SEED-262144-13 | qualified_fixture | 0.7849 | 149241856 | 174948352 | 17571672 | 17805312 | 141 |
| SEED-262144-14 | qualified_fixture | 0.8778 | 149225472 | 174948352 | 18859833 | 19103744 | 151 |
| SEED-262144-15 | qualified_fixture | 0.7866 | 148520960 | 174243840 | 20149170 | 20414464 | 161 |
| SEED-262144-16 | qualified_fixture | 0.7727 | 148914176 | 174637056 | 21444171 | 21737472 | 171 |
| SEED-262144-17 | qualified_fixture | 0.7933 | 149602304 | 175341568 | 22736836 | 23052288 | 181 |
| SEED-262144-18 | qualified_fixture | 0.8601 | 150028288 | 175767552 | 24032094 | 24371200 | 191 |
| SEED-262144-19 | qualified_fixture | 0.8253 | 149471232 | 175226880 | 25324440 | 25677824 | 201 |
| SEED-262144-20 | qualified_fixture | 0.8055 | 150618112 | 176373760 | 26615218 | 26984448 | 211 |
| SEED-262144-21 | qualified_fixture | 0.7938 | 149651456 | 175423488 | 27908140 | 28295168 | 221 |
| SEED-262144-22 | qualified_fixture | 1.1144 | 150388736 | 176177152 | 29203654 | 29609984 | 231 |
| SEED-262144-23 | qualified_fixture | 0.8013 | 149520384 | 175308800 | 30500863 | 30924800 | 241 |
| SEED-262144-24 | qualified_fixture | 0.7710 | 149422080 | 175210496 | 31797272 | 32239616 | 251 |
| SEED-262144-25 | qualified_fixture | 0.7701 | 149504000 | 175292416 | 33094994 | 33558528 | 261 |
| SEED-262144-26 | qualified_fixture | 0.7715 | 149536768 | 175325184 | 34393260 | 34881536 | 271 |
| SEED-262144-27 | qualified_fixture | 0.7978 | 148979712 | 174768128 | 35694118 | 36204544 | 281 |
| SEED-262144-28 | qualified_fixture | 0.9124 | 149340160 | 175554560 | 36995840 | 37531648 | 291 |
| SEED-262144-29 | qualified_fixture | 0.7945 | 148750336 | 174964736 | 38298105 | 38858752 | 301 |
| SEED-262144-30 | qualified_fixture | 0.7759 | 149356544 | 175570944 | 39599443 | 40177664 | 311 |
| SEED-262144-31 | qualified_fixture | 0.7966 | 149274624 | 175489024 | 40902029 | 41496576 | 321 |
| BUILD-262144 | resource_refused | 0.6971 | 209240064 | 235454464 | 40902029 | 41496576 | 322 |

Whole orchestration elapsed 27.085664 s and exited 2. Longest completed seed stage: 1.1719 s; seed peak task: 150618112 B /aggregate: 176373760 B. Failed build held the overall task/aggregate peaks. All stage deadlines and 900 s outer cap were unchanged.

## Preserved state and cleanup

Final recorded fixture: 40,902,029 logical B /41,496,576 allocated B, 322 files. The last successful seed had the same logical/allocated byte totals and 321 files. Final native-stage run tree including its then-current log: 40,933,176 logical B /41,529,344 allocated B, 323 files. Small summary/cleanup/filesystem evidence receipts were added afterward using stdlib only. These values are below 256 MiB fixture /512 MiB diagnostic-tree thresholds.

A post-stop stdlib-only filesystem inventory shows 32 manifest files and one new zero-byte temporary file under `_indices/0a434476-9cba-4fd1-afd2-f7e053b922d0/.tmpqRIkrD`. It remains preserved. No post-refusal Lance/Arrow reopen, canonical data verification, index success or publication/rollback claim was made. A guardian refusal can interrupt before the worker emits its before/after proof; preserve ambiguity and reconcile before any later authorized reuse.

Frozen supervisor cleanup completed. The final event records admission FD closed and no host descendants. A separate exact-executable-path process inventory found no diagnostic host, worker or guardian. Native slot release was reported promptly to root. No fixture/index/orphan file was deleted or modified for diagnosis.

Reads would have included recursive artifact checks/full fixture hashing and pinned-version metadata within 2 s; none of those reads executed in this run. The refusal occurred during combined initial build work, after pre-build hashing inside the 3 s stage, and its exact transient allocation source is not established by sampled RSS alone.

## Receipts

| Artifact | SHA256 |
|---|---|
| [events.jsonl](/private/tmp/castle-indexreplace-262144-vrr12b2u/run/events.jsonl) | `3dd21c9976ebace3585dc9940d1c2f2a8952357dcd7b04682f9cb98901026cc3` |
| [summary.json](/private/tmp/castle-indexreplace-262144-vrr12b2u/run/summary.json) | `8ab89120717f42ef536026237669cbd11ffac5d82f40ad795961562720a7bb13` |
| [cleanup-receipt.json](/private/tmp/castle-indexreplace-262144-vrr12b2u/run/cleanup-receipt.json) | `6a1cc69807e77a37c1c0f220a960dd6ed6ee9e2b0f2577b3f9e2f87a59072d5e` |
| [post-stop-filesystem-evidence.json](/private/tmp/castle-indexreplace-262144-vrr12b2u/run/post-stop-filesystem-evidence.json) | `dbfd10b887c640634b3e5d61ca34fb59ea65ee56e10896834bf9184d5f3a4b2e` |

Frozen manifest: [/private/tmp/castle-indexreplace-262144-vrr12b2u/manifest.json](/private/tmp/castle-indexreplace-262144-vrr12b2u/manifest.json). Preserved fixture: `/private/tmp/castle-indexreplace-262144-vrr12b2u/run/fixture-262144`.

## Scope and next read-only decision

This run establishes bounded streaming construction of this 262,144-row synthetic fixture and an actual initial-index task-memory gate at that scale. It does not qualify whole derived replacement, larger scales, real bulk fragment geometry, whole-owner membership/hash/replay, crash recovery or migration readiness. Actual corpus representation may reach millions of six-string physical rows after pages, memberships, owners and receipts. Product 16,384-row admission and qualification profile are unchanged.

Root requested only a subsequent pinned-source read-only diagnosis of supported BTREE sort/stream/spill memory controls, with a compact metadata-only ID→physical-row alternative if no supported control is established. No implementation or new native experiment is authorized by this result. The previous 65K success and 262K refusal remain separate recorded measurements, without interpolation or budget increases.
