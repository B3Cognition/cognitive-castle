# One disposable hot-journal fixture — static review

Decision: approved as the fixed nine-start metadata recovery qualification. No remaining protocol blocker found. This is preparation only; no test, SQLite connection, source/engine access or runtime was executed by this reviewer, and no hot journal in the failed first-five database is asserted.

Independently matched the final fixture, plan, prepared record and all ten listed dependency file hashes/byte lengths:

- `tests/test_layout_resume_recovery_native.py`:12045 bytes, SHA256 `4f6c88ed185f64702498f2c639d2eec71d88afffd46476364893b530b72e7b98`.
- `task3-layout-resume-hotjournal-plan.md`:3519 bytes, `a4a652387875c51a527f23941dc65623e29b1b7b882077adecbcd2269a60b2fa`.
- `task3-layout-resume-hotjournal-prepared.json`:3635 bytes, `40cf8b2ba1e922ad6f15b1c267f109d0add8611781e6c8296a329c4bea719252`.

The host uses only the existing pure synthetic codec fixture to derive one owner plan/intent; no original source is opened and no native publication proof is substituted. Actual production operator/bind/prepare operations create the registered schema5 pending state and authoritative claims/routes. The fixed small set fits the snapshot's16-row-per-table cap and per-column4096-byte projections.

The crash child uses the existing-only writable connection and validates current authority/qualification/registration/pending before the single update. The only application change is64 KiB trailing whitespace in the existing pending TEXT. It verifies effective two-page cache/spill thresholds and DELETE journal mode, then flushes a fixed successful marker and exits without SQLite commit, rollback or close. The journal-byte check is not treated as proof of hotness: the following production read-only connection must independently produce actual extended SQLite error776. Any other result stops the case; no adaptive size, retry or journal rewrite exists.

One production `queue_layout_resume` must then return the exact pre-crash state. A new read-only snapshot compares the original raw pending byte length/SHA256 and bounded claims/routes count/hash as well as the full logical state. This detects a committed whitespace change that JSON equality alone would miss. A second resume must return the same state, without publishing, ACKing or confirming reserved claims.

Attempt accounting now emits/increments START before entering each session, with a hard maximum of9. Every stage requires one fresh resource observation, statusOK and no resource/admission reason. The census now includes root/directories/files and both logical and allocated bytes; the generation is limited to8 MiB and32 entries, with main/journal2 MiB and qualification64 KiB file limits. The fixed generated hierarchy is shallow. Two GiB free headroom precedes generation creation. The qualified scope must also bind the outer pytest/code/log artifacts separately.

Schedule: register, bind, prepare, baseline snapshot, crash, read-only776, production resume, restored snapshot, idempotent resume. Each is an ordinary bounded metadata stage:2-second read or3-second write,128/192 MiB and16 MiB SQLite heap; each uses a fresh existing five-second session. The proposed outer run is30 seconds/256 MiB. This does not claim a nine-stage shared-five-second publication or authorize another fixture/run.

Only root may freeze the complete source pins/preflight and launch this exact scope. The failed first-five output and database remain untouched; successful metadata recovery, if later observed, would not by itself repair the separate end-to-end publication latency failure.
