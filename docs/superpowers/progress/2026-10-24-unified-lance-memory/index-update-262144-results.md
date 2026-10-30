# 262,144 indexed-fixture update result

The one authorized frozen six-case launch passed all six cases; none refused and none remained unrun. Total host elapsed time was 4.748979583 seconds. This qualifies one 1,024-row tail update of this independently validated, already indexed fixture under the selected profile. It does not qualify an initial 262,144-row build, millions of product-expanded rows, repeated updates/retirement, or production readiness. Prior initial-build refusals remain unchanged evidence.

The launch used `/Users/ladislavbihari/.echelon/venv/bin/python -I /private/tmp/castle-indexupdate-262144-5xxwe3u4/run.py --run --manifest-sha256 1d3a973c0268f45b2a9cd521d2fa9082986e21c3cffaff503965f1d0564a8ade` and exited 0. No retry, rebuild, tuning, branch, cleanup, or product change followed.

The frozen plan was [index-update-262144-plan.md](index-update-262144-plan.md). Private bundle: `/private/tmp/castle-indexupdate-262144-5xxwe3u4`. Source: `/private/tmp/castle-indexspill-262144-gmnib9p0/run/fixture-262144`. Output physical copy: `/private/tmp/castle-indexupdate-262144-5xxwe3u4/run/fixture-262144`.

## Limits and measured stages

Unchanged task/aggregate RSS tripwires were 201,326,592/268,435,456 bytes (192/256 MiB), read deadline 2 seconds and write deadline 3 seconds. The copied shared admission, pressure/preemption, background-priority guardian and 50 ms sampling remained active. RSS figures are sampled tripwires; transient peaks remain possible. All measured work includes native imports and required metadata, hashing and postchecks, rather than isolated optimizer timing.

Selected child configuration was `LANCE_MEM_POOL_SIZE=16777216`, `LANCE_MAX_TEMP_DIRECTORY_SIZE=67108864`, `LANCE_BYPASS_SPILLING` absent, fixed private per-case `TMPDIR`, and unchanged thread settings. The 64 MiB limit is shared tracked spill bytes per DiskManager, not a hard process/filesystem/cross-manager allocation cap. Fixture/run ceilings stayed 256/512 MiB with a 2 GiB free-space floor. The entire private temporary tree is included in run accounting.

All rows below passed. Disk columns are poststage allocated bytes, including retained files; these are stage inventories, not a claim of exact transient filesystem peaks.

| Frozen case | Seconds | Task RSS bytes | Aggregate RSS bytes | Fixture disk bytes | Whole run disk bytes |
|---|---:|---:|---:|---:|---:|
| VALIDATE-SOURCE-262144 | 1.1422 | 171,130,880 | 196,198,400 | 0 | 0 |
| COPY-INDEXED-262144 | 0.3437 | 50,003,968 | 75,120,640 | 53,366,784 | 53,374,976 |
| READ-262144-BASE | 0.9954 | 171,327,488 | 197,132,288 | 53,366,784 | 53,374,976 |
| TAIL-262144-ROWS | 0.6460 | 147,636,224 | 173,522,944 | 53,563,392 | 53,575,680 |
| UPDATE-ONLY-262144 | 0.7626 | 198,639,616 | 224,526,336 | 65,523,712 | 65,536,000 |
| READ-262144-REPLACED | 0.7989 | 161,005,568 | 186,908,672 | 65,523,712 | 65,544,192 |

The update peak was 2,686,976 bytes below the task threshold. Its fixture grew by 11,960,320 allocated bytes (11,951,225 logical bytes); whole run poststage allocation was 65,536,000 bytes. The final fixture held 333 files, 64,898,007 logical bytes and 65,523,712 allocated bytes. Every per-stage temporary inventory had zero files/bytes after completion. Actual spill volume is unproven; selecting supported spill budgets and observing bounded performance does not prove how much was spilled. Fresh worker processes do not imply a cold OS cache.

## Identity, lookup and publication evidence

1. Source validation established version 33, 262,144 canonical six-string rows, 256 fragments and storage version 2.2. Its one active BTREE UUID was `4f48b77d-3520-4dd3-bedd-4a0fb833fc07`, covering fragments 0–255, descriptor data version 32/index version 0, with zero uncovered tail. The two active files matched the frozen hashes. Thirty present and two absent IDs passed exact bounded canonical record checks before any copy; therefore the previous refused build's artifacts were validated here rather than presumed successful.
2. COPY created independent physical files, verified no shared inodes, and reproduced content hash `c5d47f1108c45971639e824a9452f143e97221f25b108c8f260d9ce08846df26`. Copied BASE repeated the version/index/coverage and 30-present/two-absent lookup proof with the same result hash `539b9f0a96802f8941ad82833a18e9ef9bf54a5cf40790a7d89292c40f4241d0`.
3. APPEND added exactly 1,024 valid canonical rows in bounded Arrow batches, producing version 34, 263,168 rows and 257 fragments. The existing index still covered fragments 0–255, leaving the one-fragment/1,024-row tail.
4. UPDATE called only the supported existing-index optimizer and published version 35. This was a whole derived BTREE update of the existing sorted index, not an initial build or old-UUID-preserving segment merge. New UUID `9899106a-0ba9-4e3f-877e-b4671c1476bd` covers fragments 0–256, descriptor data version 34/index version 0, with zero uncovered tail. Its `page_data.lance` was 11,912,815 logical bytes, SHA-256 `41b1340e02f87afe5cafa0c7942c42b62904bb1adfc316c52ca9dfb4b2d11d89`; `page_lookup.lance` was 11,120 bytes, SHA-256 `ecc9f3b01131690a43751b3f0a972117b2a504296ba0759b7965d2048694e9fb`.
5. UPDATE proved all 257 canonical data files unchanged across publication: 40,617,098 logical/41,046,016 allocated bytes, inventory hash `7208f21e6064dcd013aecdbd35d63fb320cf6f7accc90f509a66e20a2b1fc61f`. Canonical rows and fragment geometry were unchanged. Both old active-index files and the zero-byte orphan were retained unchanged; retained index-pool file count grew from three to five. Active files are classified by each version's active UUID rather than treating the entire retained pool as active.
6. Final READ independently reopened version 35 and passed five present IDs spanning old and tail rows plus two absent IDs. It also opened pinned version 34, retaining the old UUID and its 256 covered fragments with the original 1,024-row tail, while observing the same 263,168 canonical rows/257 fragments. The final read verified original source inventory `94bbf2d88d1a5c36c125118671b5058c719131d766b2d983ce536942ec2d1030` unchanged; source before/after validation and COPY matched it too.

UPDATE reused the successfully updated Dataset for its own postchecks; final READ was independent. This pass provides no causal explanation for earlier full-build memory refusals, and does not establish that the earlier redundant reopen caused them.

Whole-output replacement and retained versions create continuing disk debt: this run retained both index generations. No version/index/orphan cleanup was performed. Repeated-update disk growth, product-expanded row geometry, admission/reservation, pinned readers/rollback and safe retired-version recovery remain separate qualification obligations.

## Receipts and release

All receipts and original/copied fixtures are preserved. Each case recorded an empty descendant list and closed admission FD. The post-run process receipt found no matching diagnostic process; the native slot was released and subsequently reassigned by root. No further native activity was run.

Receipt directory: `/private/tmp/castle-indexupdate-262144-5xxwe3u4/run`.

| Receipt | SHA-256 |
|---|---|
| `events.jsonl` | `9d802b4b549096a923301742b4947633ceca8dc85bf2db0cc29d116046ce255a` |
| `summary.json` | `04ce5bd989ca7a186a7b3b55393f5cb35d28aef9ae2fccfe3160246fd71e61d5` |
| `cleanup-receipt.json` | `6a1cc69807e77a37c1c0f220a960dd6ed6ee9e2b0f2577b3f9e2f87a59072d5e` |

The six frozen cases are complete. Larger scales, additional geometry, initial builds and lifecycle experiments were not run or authorized by this launch.
