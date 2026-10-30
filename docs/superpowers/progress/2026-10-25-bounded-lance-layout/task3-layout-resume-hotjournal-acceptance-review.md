# Disposable metadata recovery — acceptance review

Accepted for the scoped schema5 hot-journal recovery case. Root reported PASS in session42458; the preserved output contains the passing pytest marker, completed guard and exactly nine matched START/STAGE records. This reviewer read artifacts and frozen assertions only, without SQLite, source/engine access, probes or reruns.

Evidence independently checked:

- Root scope v2:27507 bytes, SHA256 `d402324d01306e4cb12a465f570f75d658aeefc748e57f52dd66c3f459449f05`.
- `task3-layout-resume-hotjournal-output-v2.txt`:2980 bytes, `24a4f93d37f02113f04e3a98e2c8e72e7858e684d140bc2dcb2b7ca31bd764b3`.
- All150 scope-bound files matched current raw sizes/hashes,2492290 bytes total. File pins and per-stage limits are identical to the prior scope. The v2 argv changes to the unique v2 basetemp and a stricter28-second outer timeout.
- Executed fixture remains the reviewed `4f6c88ed185f64702498f2c639d2eec71d88afffd46476364893b530b72e7b98`, with prepared record `40cf8b2ba1e922ad6f15b1c267f109d0add8611781e6c8296a329c4bea719252` and static review `e6c1a46bc2bad55a9d51e711422fc99a19802e63d3748953adde523db076d6a2`.

The sequence is exactly register, bind, prepare, baseline snapshot, deliberate crash, read-only776, production resume, restored snapshot, idempotent resume. Calls1–9 each have one fresh resource measurement, statusOK and no reason. No extra worker, retry or adaptive fixture size is recorded.

The frozen passing assertions establish actual read-only SQLite extended error776 before the production recovery operation. They then require exact pre-crash full state, raw pending TEXT byte length/SHA256, bounded claims/routes counts and canonical hash, and identical state on the second resume. These are code-bound assertions from the passed fixture; this review did not independently open or inspect the retained database. Raw TEXT equality excludes a false pass where the uncommitted whitespace change survived but JSON remained equivalent.

Every measured stage is below its existing2-second read/3-second write and128/192 MiB limits. Maximum sampled task RSS is52871168 bytes (50.42 MiB), maximum sampled total is91242496 bytes (87.02 MiB); summed recorded stage time is4.5418 seconds. The outer guard reports87.0 MiB and6.1 seconds, below28 seconds/256 MiB. These remain sampled RSS observations, not a guarantee against transient peaks. The fixture's logical/allocated census and fixed artifact assertions passed; no exact disk total is printed in the stage log.

The earlier denied run remains failed-admission evidence: result `67a3549876470c405d88184440cb4dd0012c9fc15081340b542af12594bca6a3` recorded zero supervised workers and1.8 seconds. The v2 scope documents a new observed admission condition after capture completion, unchanged code/limits and combined outer allowance29.8 seconds. It does not relabel the denied attempt as a pass.

Conclusion: the dedicated existing-layout entry has now demonstrated one real disposable hot-journal recovery with original pending/claim state preserved and idempotent reopening. This closes that recovery qualification only. Task3's stopped first-five publication scope, tail native cases and end-to-end latency/capacity gates remain unclosed; no source/Lance publication or original failed-database recovery is implied.
