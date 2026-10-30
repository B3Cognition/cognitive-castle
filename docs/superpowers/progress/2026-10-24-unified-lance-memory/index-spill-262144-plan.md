# Task 3c: 262K copied-fixture spill-budget diagnostic

2026-10-25. **Preparation only; no runtime, physical copy, product/profile edit or new qualification.** Root selected this separate supported internal-budget candidate after the 262K initial-build RSS refusal. The old failed fixture and receipts remain unchanged. Queue/coordinator work owns the native slot; root must review the new executable/hash binding and separately authorize one launch.

## Fixed candidate and verified private routing

The worker, after copied exact supervision admission and before any Lance/Arrow native import, applies only:

- `LANCE_MEM_POOL_SIZE=16777216` (16 MiB DataFusion reservation pool).
- `LANCE_MAX_TEMP_DIRECTORY_SIZE=67108864` (64 MiB tracked spill usage **shared per DiskManager**).
- Remove `LANCE_BYPASS_SPILLING` entirely, including an inherited empty/`false` value.
- Set `TMPDIR` to a new private 0700 `run/tmp/<fixed-case-label>` directory.

No thread settings change. This reduces an existing internal reservation/spill budget; it never raises 192 MiB task /256 MiB aggregate, 2 s read /3 s write, or any admission/pressure/preemption rule. The prior failed process's resolved environment remains unknown; do not retrofit these settings onto its receipt.

Routing is established from pinned source, not the variable name alone:

1. Lance 4.0.1 commit `5924c97123a25a3e3d500701ef3f158c01f6cd4b` uses spilling-enabled execution for BTREE training and old/new stream merge. Its executor wires the selected values into `FairSpillPool` and default `DiskManagerBuilder`.
2. That commit's Cargo.lock selects **datafusion-execution 52.5.0** and **tempfile 3.27.0**. Official crate archives were downloaded as source only and matched lockfile checksums `dc45d23c516ed8d3637751e44e09e21b45b3f58b473c802dddd1f1ad4fe435ff` / `32497e9a4c7b38532efcdebeef879707aa9f794296a4f0244f6f69e9bc8574bd`.
3. DataFusion `disk_manager.rs:45–49,279–309` defaults to `OsTmpDirectory`, creates its parent with `tempfile::tempdir()`, then creates spill files inside that parent. Tempfile `dir/mod.rs:64–65,218–219` and `lib.rs:595–597` route through its environment helper; `env.rs:45–50` delegates to `std::env::temp_dir()` unless an explicit override was installed.
4. Rust's documented Unix contract consults `TMPDIR` first; pinned Rust 1.95.0 `unix/os.rs:470–475` shows that ordering on Apple/Unix. This illustrative source is not a claim to have identified the wheel compiler. Fresh workers set the private path before loading native code; no tempfile override API is exposed or called by this diagnostic. The inspected Lance module initialization/target execution paths do not install an override.

[Pinned Lance executor](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/rust/lance-datafusion/src/exec.rs#L316), [pinned lockfile](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/Cargo.lock), [DataFusion source archive](https://static.crates.io/crates/datafusion-execution/datafusion-execution-52.5.0.crate), [tempfile source archive](https://static.crates.io/crates/tempfile/tempfile-3.27.0.crate), [Rust Unix contract](https://doc.rust-lang.org/std/env/fn.temp_dir.html).

`source-proof.json` binds the exact cached source files/checksums and scope. The 64 MiB counter covers tracked spill files across one manager's directories; callers update it after writes. It is **not** a hard file/OS allocation cap, total native RSS cap, or aggregate across different managers. All actual private temp directories, leftover files and logs are included in the separate 512 MiB run-tree accounting. The 256 MiB fixture threshold and >=2 GiB free admission remain. No exact transient spill-volume claim or monitoring framework is added: disappearing files/empty poststage inventory leave actual spill volume unproven.

## Frozen source and guarded physical copy

Source is fixed to `/private/tmp/castle-indexreplace-262144-vrr12b2u/run/fixture-262144`: last acknowledged version 32, 262,144 canonical rows /256 fragments, storage 2.2, no successfully published index, including its zero-byte `_indices/0a434476-9cba-4fd1-afd2-f7e053b922d0/.tmpqRIkrD` orphan. No source cleanup is allowed.

Preparation froze 322 files, 40,902,029 logical B /41,496,576 allocated B in `source-inventory.json`. Full path/type/mode/owner/device/inode/link/size/hash inventory digest: `2183cb70a8786c14becdfdac57408dc36224bb51d00a4af918b4262ac965870c`. Content path/size/SHA digest: `3a3d5b57adb44f95a051459425f3b1178b39bebc8c0590040b2830d1e83b3206`. The JSON itself is manifest-bound. Only stdlib reads were used; no original Lance reopen or mutation.

`COPY` runs under the same 3 s supervision, validates the source with copied path/supervision guards, and compares it to the frozen full inventory before copying. It creates a new fixed destination exclusively, reads/writes 128 KiB chunks, uses 0700 directories/0600 regular files, no symlinks/hardlinks/reflink/clone API, and proves distinct source/destination device+inode identities. It rehashes the source afterward and verifies every copied path/type/mode/owner/size/content hash. The original is opened read-only, never writable. Any changed source or incomplete copy stops the run; no re-freeze or retry follows. No 32 seed writes are recreated.

## Exactly ten ordered cases

| Order | Case / required result |
|---|---|
| 1 | `COPY-262144`, write 3 s: physical copy/proofs above; no Lance/Arrow import needed. |
| 2 | `METADATA-262144`, read 2 s: copied dataset only; require schema/storage 2.2/version 32, 262,144 rows /256 fragments and no active index. Counts/description only: no unindexed ID/content scan. Full filesystem SHA inventory remains read-only. |
| 3 | `BUILD-262144`, write 3 s: full initial BTREE under existing writer lock; require version 33, 256 indexed fragments/zero tail and unchanged canonical data-file hashes and fragment ID/row pairs. |
| 4 | `READ-262144-BASE`, read 2 s: 30 fixed present IDs /2 absent, exact six fields/canonical provenance, read-only inventory. |
| 5 | `TAIL-262144-ROWS`, write 3 s: append exactly 1,024 canonical rows at ordinals 262,144..263,167; require version 34, 263,168 rows /257 fragments. |
| 6 | `READ-262144-TAIL`, read 2 s: old first/middle/last, tail first/last and 2 absent; require 1,024-row /1-fragment tail, exact values, no mutation. |
| 7 | `REPLACE-DERIVED-BTREE-262144`, write 3 s: bounded-tail precheck and explicit `optimize_indices(index_names=["castle_exact_id"])`; accurately whole derived replacement. Require version 35, all 257 fragments covered, canonical rows/data-file bytes/fragments unchanged and old index files retained unchanged. A new active UUID is expected; no delta-only preservation criterion. |
| 8 | `READ-262144-REPLACED`, read 2 s: old/new/absent lookup and unchanged fixture; reopen pinned 34 and verify original active UUID/files, canonical state and former 1,024-row tail. Active files are separated from the retained index pool. |
| 9 | `DUPLICATE-262144-WRITE`, write 3 s: terminal identical ordinal 0 append, version 36, 263,169 rows /258 fragments. No subsequent index operation. |
| 10 | `DUPLICATE-262144-READ`, read 2 s: bounded candidate lookup must detect indexed/tail duplicate as expected `corrupt`. |

Five writes and five reads: 25 s summed native deadlines, unchanged 900 s outer orchestration cap. Source/copy hashing, imports, pressure preflight, index/metadata/data validation, private temp inventory and serialization spend the same relevant 2/3 s stage budget. The metadata case's filesystem hashing is not a native unindexed table scan. Read outcomes concern combined lookup/validation work, not an index-only benchmark. Fresh workers and physical copies do not imply flushed OS caches. No 32 tiny-fragment branch or larger scale exists in the executable.

All remaining schema/geometry/lookup controls match the reviewed 262K diagnostic: six non-null strings, complete canonical provenance, empty digest/receipt, storage 2.2, <=256-row /128 KiB Arrow batches for appended tail, 1,024 rows/file,1 MiB caches/I/O buffer, 32-ID bounded IN reads, fixed 512 KiB outer frame /4 KiB request /32 KiB response. Native packages import only in separately supervised workers; host imports no Lance/Arrow/SQLite/model/provider. Private copies pin d4d6850 guard/runtime/exact supervision and 0278524 canonical/store/codec helpers, never changing-worktree imports.

## Stop and evidence

One launch only after root review/slot assignment. Stop at the first admission/pressure/preemption/RSS/deadline/disk refusal, geometry/content/profile/evidence mismatch, bad frame or cleanup failure. No retry, tuning, cap increase, orphan deletion, seed recreation, larger scale or source movement. Keep both source and copied fixture plus all temp/orphan evidence until root diagnosis. The terminal duplicate is the only expected logical refusal.

Receipts record fixed selected/resolved child profile, private TMPDIR, complete stage time/task/aggregate RSS, source/copy hashes and inode proof, native version/coverage and canonical/index file proofs, whole-run disk before/after including temp, available poststage temp inventory, and cleanup. If temp files disappear and existing metrics do not establish spilling, state **selected spill budget; actual spill volume unproven**. Do not infer spill bytes from configuration or build success. RSS remains a sampled tripwire, not a kernel limit.

After completion/refusal, prove diagnostic descendants gone and admission released, report the native slot free promptly, and write results without promoting the product gate/profile. This tiny-payload 262K candidate does not qualify actual corpus scale, likely millions of physical rows after pages/memberships/owners/receipts, nor recovery, sustained accumulation, real bulk fragment geometry or 52 MiB occurrence finalization.
