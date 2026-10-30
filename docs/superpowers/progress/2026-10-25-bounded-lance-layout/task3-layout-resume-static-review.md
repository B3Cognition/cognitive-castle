# Task 3 existing-layout recovery entry — static review

Decision: no blocking defect found in the reviewed product/pure candidate. Approved for a separately frozen disposable hot-journal qualification. This does not prove real SQLite recovery, explain the failed first-five run, or qualify native publication performance. No tests, database operations, product imports or engines were executed by this reviewer.

## Verified bindings

Raw files and packet hashes were independently matched:

- Queue delta `task3-layout-resume.diff`:10146 bytes, `3b6217a4a8247bc99c8f4fdf4934496bd6ef66b5fda5d7686674e26933803a71`.
- Queue pure report `task3-layout-resume-pure-results.json`:2846 bytes, `f71f5f899582d542eb80f6cb2fc698723b2e0e5807ab021e28ae163a919a74b8`.
- `cognitive_castle/semantic_queue.py`:38529 bytes, `77f2b7479908c99d48daf786bd6f83e882a94b8aad0230a7ef0e209c956d3b34`.
- `cognitive_castle/semantic_store_worker.py`:7314 bytes, `ab9261e9827c0a15b6d37f03280bb81a3f3d39c5a7245f5e36bca2b1d0f93264`.
- `tests/test_layout_resume.py`:5414 bytes, `9d72088ea6207b5cdc9063173b0089d512b5552e51f688cf20d60e1b4ca02ef4`.
- Coordinator delta `task3-layout-resume-coordinator-1.diff`:8218 bytes, `beb99477ea29034026b2bcf9dad9a7a794ed812214c40bad514a90396d349897`.
- Coordinator report `task3-layout-resume-coordinator-results-1.json`:2971 bytes, `934ad5c55c996312a8c9c5427485db688d56099b17f7927cb5efa83c04bcd567`.
- `cognitive_castle/migration_coordinator.py`:23950 bytes, `4028e9ba14f8ae2be26bceed0c54fe6331a5ff5fe12c4589cbc2ffd42755f991`.
- `tests/test_layout_coordinator.py`:19656 bytes, `781479b386a7cdfee39f6c13b8977cf64223e1cb58f653b4a074146b63eab0b8`.
- Tail mechanical update `tests/test_layout_native_tail.py`:25933 bytes, `f083442dfcacfaba683d77d47014b740c0282e12bc6dfbda27d07e277eb1df28`.

## Reviewed safety and compatibility

The dedicated connection requires a writable queue instance, runs the existing supervised private-path checks with `create=False`, and opens only `queue.sqlite3?mode=rw` with zero busy timeout. There is no existence-based `rwc` fallback, directory creation, legacy schema initialization, DDL, registration insertion, cursor reset, hidden retry or additional worker. Existing cache/mmap/synchronous settings and `BEGIN IMMEDIATE` give SQLite a writable recovery path; the code itself does not manipulate a journal.

After opening, the unchanged `_NativeLayoutDirectory` requires complete schema5, authority/registry shape, generation identity, immutable qualification hash/body and resource policy. A missing attachment refuses. The shared state projection preserves the existing migration-row, attachment, pending/cursor and native-context validation, then the recovery entry requires exact equality with the submitted validated registration. Invalid authority/registration raises before returning an accepted result; the context closes rather than committing application changes on exceptions. Missing files cannot be recreated by this entry.

The ordinary `migration_state` API still calls `_run(False)` and keeps its read-only connection behavior. Extracting `_layout_state` preserves its previous projection and metadata bounds. Legacy `migration_open` and v1 coordinator paths are untouched; their creation semantics and attached-job exclusion are not repurposed for recovery.

The closed worker operation accepts only `registration`. It uses the existing queue write profile:3 seconds,128 MiB task/192 MiB total,16 MiB SQLite heap. The private layout coordinator replaces its first read with this operation exactly once, without adding starts or changing the shared five-second session. Resume refusal, mismatch or resource failure stops before planning/export/native work/ACK. Pending regeneration and exact replay are unchanged. Tail changes are only five captured operation-name replacements; its123-start schedule remains intact.

Author-reported evidence is three focused queue pure passes and nineteen coordinator pure passes, with the original missing-operation RED and corrected fake-argument failure retained. The fake connections verify mode/control/rollback and protocol behavior; they cannot establish an actual hot journal or successful recovery.

## Remaining qualification boundary

A fresh disposable fixture must establish a real hot-journal precondition, demonstrate the read-only failure, run exactly one recovery operation, and compare original registration/pending/frontier/claims before ordinary read-only access succeeds again. It must also show missing DB, wrong registration and missing/schema4 authority cannot recreate state. No conclusion about a journal in the failed first-five database is made; that retained database was not inspected or modified here.
