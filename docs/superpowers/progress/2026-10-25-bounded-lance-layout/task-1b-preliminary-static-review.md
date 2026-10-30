# Task1b large historical fixture: preliminary static review

**Disposition: one P2 blocker in the reviewed draft; final approval pending the author's completed code/config seal and focused delta review.** No engine, test, Castle or native execution was performed.

Reviewed draft hashes (unchanged at end of reading):

- `tests/lance_owner_stream_fixture.py`: `3aa2dc9b18f1bd3999717dd00b2e8faf67b058e4226b9b1abe8e540735a84b35` (1,185 lines).
- `tests/test_lance_owner_stream.py`: `2ecaaa9ead17aaf06d6e531cf9464f9a757bd00045971f0f277ae569b5840b24` (969 lines); reviewed its changes against c6fca0f, not unchanged Task1a test implementations.

## P2: new result-file growth after a disk-capacity refusal

`cold_run`, fixture lines 1080–1082, calls `write_metadata(result_path(config, "cold-result"), summary, 16384)` unconditionally after the cold tick, including when `FixedSession._run_stage` returned `fixture_disk_guard`. Such a refusal can occur before `DiskLedger.before` obtains any reservation, or after a stage exceeded the capacity envelope. The call creates a new file despite that refusal. Only `first-refusal.json` is preallocated; the cold-result slot is not.

Concrete path: cold queue-open preflight sees harness capacity exhausted, records the refusal in the existing 4 KiB slot and returns unavailable. `cold_run` then creates cold-result metadata without a valid prospective charge, growing the already-refused harness. This violates the stated stop-before-unreserved-write boundary even though output size is bounded.

Fix with a charged, preallocated bounded result slot or another explicit retained reservation that survives this failure path; alternatively emit the failed summary only through the already bounded transport/preallocated refusal evidence. Do not grant new disk growth after refusal. A focused pure failure-path check should cover refusal before the first reservation and refusal after an exceeded envelope.

## Protocol and evidence inspected

The current draft follows the original registration and real queue cursor. Previous intervals call the unchanged coordinator for prepare, actual publication, actual identical replay and ACK. Fixed maintenance is before 10,19,...163; final ordinal 171 retains the original 73 entries and owner/batch publication. The deliberate loss wraps the first actual successful import before metadata ACK and checks its original compact receipt.

The cold path runs in a fresh process/session, regenerates pending source content, requires the exact six-operation sequence (open, source, two imports, owner read, ACK), and checks actual imported proof metrics: one full owner proof each, zero pending proof rows, complete 13,696-row stream, 171 batch receipts and expected full owner-manifest hash. Fixture-only fields are removed before coordinator receipt equality. Fresh queue state confirms final canonical counts and semantic pending work without treating source EOF as reached. No direct SQL cursor seed, body spool, empty-finalization shortcut, extra staging batch or cached partial owner proof was found.

Qualified read adapters are readonly; ordinary worker dispatch remains separate. Native environment is set before the store opens Lance. Stage preflight/post-accounting uses the original per-stage and shared-session clocks. Code hashes are checked pre/post, not every 50 ms sample; watcher shutdown refuses when still alive. Exact-worker own-fd sampling includes open-unlinked regular files. Source/queue paths remain unchanged, and their unmeasured transient disk scopes are explicitly labeled. Portable helper imports use the checked-in tests directory, not ignored SDD files.

## Final freeze points, not additional findings

The final code/config, dedicated native test entry and 189-qualification/380-temp/1,071-call totals are still being completed. Review exact packet/code-pin/pytest overhead against the 256-entry harness ceiling and fixed byte reserves. The cold parent's `communicate(timeout=7)` transport checks output lengths after collection; document its fixed output derivation. The sleeping original pytest host lies outside the inner cold supervisor's calling-host-plus-task aggregate, so retain a distinct outer aggregate measurement/bound. Disable or account pytest cache and wrapper-owned outputs in final command/accounting. These were reported as freeze considerations, not independent product defects.

No Task1a product review or green checks were repeated. A later review should inspect only final changes plus the concrete failure-path fix and frozen configuration; this draft report is not runtime authorization or a performance result.
