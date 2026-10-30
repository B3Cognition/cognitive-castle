# Task1b final candidate: scoped static rereview

**Disposition: APPROVED for final freezing, subject to root verifying the exact final configuration/worker/helper/seal/pin chain before runtime.** The preliminary P2 is closed. No additional blocking finding in this reviewed candidate. This is not a native launch grant, performance result or completed Task1b qualification.

Reviewed candidate identities:

- Configuration candidate: 11,495 bytes, SHA-256 `5bf8e1a9dc7f4f214757a48bcdcfcffa27abf75a0b6619e7b667a65394582745`.
- Portable helper: SHA-256 `3c2597f2e11cf71520c9fd2086b9057e47d8207ae456bfe2b0479c8e569fd183`.
- Worker/test before insertion of its frozen literal: SHA-256 `08385501d9c4aef51673aa3fc876cd4782ef5157a855f63e6c5719c921e8b8db`.

## Closed finding and scoped changes

`cold_run` now returns a failed summary after writing only the allocated 4 KiB first-refusal slot. It does not create cold-result after a disk/other refusal. The new focused test supplies a refused tick and asserts both retained first-refusal content and absence of the result file. The previous unreserved post-refusal growth path is removed. The successful result path follows an admitted real ACK and its existing bounded metadata reservation.

Read the added fixed-path/seal handling, runtime attestation accounting, changed setup/basetemp handling, maintenance absolute-clock carry, native operator test, refusal/seal test bodies, and the unchanged bounded cold transport in context. The known original protocol and actual owner-proof checks from the preliminary review remain intact. The final worker test skips only when private operator configuration is absent in ordinary clean checkouts; the root-authorized native run must separately establish the expected literal/config presence and require the actual qualification result, not interpret a skip as success.

## Acyclic seal chain

Configuration C pins the helper and 28 other small code dependencies, deliberately excluding the changing worker. The final worker W contains the literal hash C. External seal S hashes exact raw C/W/H, while a fixed-location private read-only launch pin binds C and S. Neither C nor W needs to hash S or the pin; no hash cycle results.

Runtime enforces the fixed configuration and packet paths, private regular single-link pin/seal files with owner-write/group/other permissions denied, exact shape/path/length/hash bindings, and configuration hash agreement. The attested worker/config/helper/pin/seal identities are checked during sampling and full hashes pre/post; ordinary code pins remain hashed pre/post. Worker bytes are counted separately, helper bytes once through the 29 code pins. The changed worker cannot be selected by caller-controlled path or inserted into C's circular pin list. The pure seal test checks changed-seal and wrong-trusted-root refusal.

Before launch root must confirm C is copied unchanged to its fixed path, the only intended worker mutation is the frozen C literal, final raw W/H hashes match S, pin hashes match C/S, final pin/seal permissions and identities are correct, all runtime pins still match, and the run/basetemp are initially absent. These final artifacts were intentionally absent during review.

## Concrete capacity checks

Independently hashed all 29 candidate code pins: 551,767 bytes, unique paths, with the worker excluded. A bounded metadata-only census of the eight fixed source families found 122 entries, 61,522,214 logical and 61,915,136 allocated bytes. The packet currently has six entries and 49,152 allocated bytes, including retained preparation/cache artifacts.

Normal harness entries: 205 runtime harness entries + 6 current packet + 2 future seal/pin + 2 fixed config/basetemp + 29 code pins + 1 worker = 245, leaving 11 under 256. Existing byte ceilings yield 61,915,136 + 320 MiB destination + 80 MiB temporary + 24 MiB harness = 506,511,360 bytes, below the 536,870,912-byte whole ceiling. Per-stage prospective reservations, sampled/post checks, free-floor checks and refusal behavior still enforce the actual run rather than treating this arithmetic as a native expansion proof.

Nonblocking arithmetic correction: normal temporary directories are **382**, comprising the tmp root, coord-source, and 380 exact workspaces. Thus normal combined entries are **1,359**, not 1,358. This does not change C's runtime caps, the 380 logical exact calls, or the 2,432 combined maximum; no capacity increase is needed. The builder's illustrative printed normal count should be interpreted with this correction.

The profile explicitly distinguishes the 700 MiB outer safe-test aggregate from unchanged inner source 128/192 MiB and exact 192/256 MiB task/aggregate limits, and the 7-second cold transport from its unchanged 5-second inner session. Final command still needs the planned cache/output handling; no broad cap or retry permission follows from this review.

## Verification boundary

Read the new focused test implementations; root reports their targeted RED/GREEN execution. This rereview did not rerun tests. Independent checks were small-file hashes, bounded stat census, candidate/source-evidence inspection, and AST compilation of the helper/worker without execution. No engine/Castle/runtime import, original database body read, resource-setting call, native run, product edit or sealed-packet mutation occurred. The review report sits outside the candidate packet. No unchanged Task1a or reranker review was repeated.
