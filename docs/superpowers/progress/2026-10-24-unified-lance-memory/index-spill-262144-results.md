# Task 3c: 262K selected spill-budget diagnostic results

**Outcome: task-RSS refusal at `BUILD-262144`; no within-budget index-build qualification.** Two cases passed, the third refused, and seven later cases stayed unrun. The copied fixture, original source, private temp directories and all receipts are preserved. Cleanup passed and the native slot was released promptly. No retry, adaptation, cap increase, orphan cleanup, larger scale or product/profile change followed.

Root separately authorized one launch of the 10-case bundle `/private/tmp/castle-indexspill-262144-gmnib9p0/`, manifest `b0eac0355246076582c4aef2b399e3cea4fdd0ef644567bbd28aa650d0af58b6`, under pinned Python 3.12.11. This was a new supported internal-configuration candidate; the prior failed run's resolved environment remains unknown.

## Selected profile and unchanged external limits

The fixed worker sets `LANCE_MEM_POOL_SIZE=16777216`, `LANCE_MAX_TEMP_DIRECTORY_SIZE=67108864`, removes `LANCE_BYPASS_SPILLING`, and creates/sets private `run/tmp/<case-label>` before Lance/Arrow imports. Successful COPY/metadata receipts report exactly 16 MiB /64 MiB, absent bypass, private TMPDIR and no thread-setting changes. The refused build returned a guardian refusal rather than the worker's profile/proof response; its fixed selected configuration/order is hash-bound, but no direct build profile or pool-use metrics were returned.

The 64 MiB value is **shared tracked spill usage per DiskManager**, updated after writes across that manager's temporary directories. It is not a hard filesystem cap, cross-manager aggregate or total-process RSS bound. The 16 MiB reservation pool is similarly not a full native-RSS cap. Whole run-tree accounting includes fixture, private temp directories, leftovers and logs. Pinned source routing/checksum proof remains in the frozen bundle.

External caps stayed 201,326,592 B task /268,435,456 B aggregate (192/256 MiB), read 2 s /write 3 s, fixture 256 MiB /run 512 MiB, >=2 GiB free admission and 900 s outer limit. Shared global admission, normal-pressure refusal, 50 ms background pressure probe, live interactive preemption and descendant kill/reap were unchanged. No source, provider, model or suite operation occurred.

## Completed cases and first refusal

`COPY-262144` passed in 0.5769 s. It physically copied all 322 source files including the zero-byte orphan, validated distinct source/destination device+inode identities, and verified unchanged source full inventory before/after:

- Full 329-entry source inventory SHA256: `2183cb70a8786c14becdfdac57408dc36224bb51d00a4af918b4262ac965870c`.
- Original/copied path-size-content SHA256: `3a3d5b57adb44f95a051459425f3b1178b39bebc8c0590040b2830d1e83b3206`.
- Copied fixture inventory SHA256: `81b46a57ad86fe0c7ea0d15d3f683bff158091169a91aa5963ad63ee7e781ae9`.

`METADATA-262144` passed in 1.2166 s: copied version 32, 262,144 canonical rows /256 fragments, exact six-string schema/storage 2.2 and no active index. It performed no native unindexed ID/content scan. Full filesystem inventory remained unchanged; filesystem SHA validation is included in that read timing.

`BUILD-262144` stopped with `unavailable/worker_memory_limit` after 0.7661 s. Sampled task RSS 202,129,408 B exceeded 201,326,592 B by 802,816 B (0.765625 MiB). Aggregate 227,950,592 B stayed below 268,435,456 B. This is a strict failure, not a passing rounded result. RSS covers guardian plus owned descendants; aggregate additionally covers the actual host. It is sampled, not a kernel hard-allocation guarantee.

The stage includes native imports, pre-build canonical file hashing, BTREE creation and post-build metadata/file proof. The sample does not identify which allocation or exact subphase caused the peak. No assertion is made that sorting alone exceeded the cap, that the operation rolled back, or that the build would have completed within bounds without verification. No successful worker build/proof response was accepted.

## Per-stage measurements

| Case | Outcome | Seconds | Task RSS B | Aggregate RSS B | Fixture logical B | Fixture allocated B | Files |
|---|---|---:|---:|---:|---:|---:|---:|
| COPY-262144 | qualified_fixture | 0.5769 | 50659328 | 76169216 | 40902029 | 41496576 | 322 |
| METADATA-262144 | qualified_fixture | 1.2166 | 134545408 | 160235520 | 40902029 | 41496576 | 322 |
| BUILD-262144 | resource_refused | 0.7661 | 202129408 | 227950592 | 52761902 | 53366784 | 326 |

Whole orchestration: 2.597042 s, process exit 2. Final native-stage run tree: 52,765,692 logical B /53,370,880 allocated B, 327 files; copied fixture 52,761,902 /53,366,784 B, 326 files. Small summary/cleanup/filesystem receipts were added afterward with stdlib only. Disk values are admission/post-stage accounting, not transient peak or hard in-call limits.

## Preserved post-refusal artifacts and spill limitation

A **stdlib-only** post-stop read found 33 manifest files and a new BTREE file pair in UUID directory `4f48b77d-3520-4dd3-bedd-4a0fb833fc07`: `page_data.lance` 11,823,023 B plus `page_lookup.lance` 10,992 B (11,834,015 B). The original zero-byte `_indices/0a434476-9cba-4fd1-afd2-f7e053b922d0/.tmpqRIkrD` remains. These are persisted publication/output artifacts; without a native reopen this report does not certify their active descriptor, coverage or current dataset state. An unavailable response must not be interpreted as rollback or permission for a blind build retry.

All 256 copied canonical data files still match the frozen source path/size/content hashes. The full 329-entry original source inventory remains exactly unchanged after the entire attempt. Those post-stop stdlib checks are forensic preservation evidence, not proof that the refused build's validation completed inside its 3 s stage.

Private TMPDIR retains `BUILD-262144/.tmpjZRzfK` plus the per-case directories; no private temporary files remain at inspection. COPY/metadata returned zero poststage temp-file bytes. The build returned no spill metrics. **Selected spill budget; actual transient/cumulative spill volume unproven.** A directory's existence, disappearing files or build output size do not establish spill volume or compliance with every internal pool reservation. No monitoring framework or unaccounted helper process was added.

## Not run, cleanup and scope

The following seven cases were not run:

- `READ-262144-BASE`
- `TAIL-262144-ROWS`
- `READ-262144-TAIL`
- `REPLACE-DERIVED-BTREE-262144`
- `READ-262144-REPLACED`
- `DUPLICATE-262144-WRITE`
- `DUPLICATE-262144-READ`

No 32 seed re-creation, 32 one-row-fragment branch, replacement, duplicate check or larger scale followed. The metadata-only base state and physical-copy proof passed; indexed lookup, whole derived replacement, retained pinned-index state and duplicate behavior at this selected 262K profile remain unqualified. Actual corpus representation may contain millions of physical rows after pages/memberships/owners/receipts; there is no migration-readiness or product-gate promotion.

The final stage reports admission FD closed and no host descendants. Independent exact-executable-path process inventory found no diagnostic host/worker/guardian. Native slot release was reported promptly. Neither original nor copy/temp/orphan evidence was deleted. No post-refusal Lance/Arrow/SQLite operation ran; all following evidence inspection used stdlib file reads only.

## Receipts

| Artifact | SHA256 |
|---|---|
| [events.jsonl](/private/tmp/castle-indexspill-262144-gmnib9p0/run/events.jsonl) | `23a7183f2e1dbfbaae8ab94de42a9fcc5e45fedfc55a9c1f142541fe16dbcabf` |
| [summary.json](/private/tmp/castle-indexspill-262144-gmnib9p0/run/summary.json) | `dddd64501f37d716a6e571bb4515473c4838eb0a5a179b548dfc6dd88db5fb23` |
| [cleanup-receipt.json](/private/tmp/castle-indexspill-262144-gmnib9p0/run/cleanup-receipt.json) | `6a1cc69807e77a37c1c0f220a960dd6ed6ee9e2b0f2577b3f9e2f87a59072d5e` |
| [post-stop-filesystem-evidence.json](/private/tmp/castle-indexspill-262144-gmnib9p0/run/post-stop-filesystem-evidence.json) | `5a44ea5e0b12f06aa75107909e2974e35db79d57a4add97ab7a49ac94496f252` |

[Frozen manifest](/private/tmp/castle-indexspill-262144-gmnib9p0/manifest.json); [source proof](/private/tmp/castle-indexspill-262144-gmnib9p0/source-proof.json); [source inventory](/private/tmp/castle-indexspill-262144-gmnib9p0/source-inventory.json).
