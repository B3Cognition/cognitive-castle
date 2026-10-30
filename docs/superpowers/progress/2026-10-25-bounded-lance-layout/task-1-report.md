# Task 1 ordered owner verification — implementation and qualification report

Current status: **TASK1 LIMITED SCOPE ACCEPTED; TASK1a APPROVED AND TASK1b CONDITIONAL PERSISTED-REPLAY GATE PASSED**. Root native tiny session1582 passed genuineFreshAppend→separateExistingVerified→version-owner/originalLIVE; root retained session24843 passed real source regeneration→ONE actual ExistingVerified/fulloriginalproof→version-owner→atomicACK171→real finalqueue state. Shared4.213875708s<5s; exact189versions/13696rows/171fragments unchanged; pendingNone,6656members,onehistoricalowner,sourceEOFfalse. Actual1090starts,594.8/600s cumulative admitted retained execution; historical preemptions/two-proof cold failures remain preserved. This qualifies the amended private Task1 protocol for this bounded fixture; it is not whole-memory/full-corpus qualification or activation. No native cap increase. Task2 has not started.
Workspace: `/Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse`.
Dispatch base: `4ab746ef85ac3b132301c66bbdb9d193d607f10e`.

## Scope and root rulings

Only this agent writes product implementation. No subagents, broad tests, model imports, Castle tools, palace data, installations, source/capture changes or activation. Root owns native-slot allocation and the separate frozen 54,525,952-byte / 6,656-member diagnostic gate.

Root clarified that valid Task 1 destinations are precreated private empty directories, bound to exact destination and parent device/inode identities. No absent-destination or rebinding protocol is authorized. Expected state is one exact `{version, physical_rows, fragments}` record, or two explicitly authorized consecutive before/after records; version and geometry cannot mix. Resource/unsafe qualification refuses with `unavailable`, valid opened stale pins with `stale`, malformed content with `corrupt`, canonical/batch conflicts with `conflict`.

Root authorized an ephemeral receipt-ID set bounded by the frozen receipt/physical envelope; this is neither text nor SHA progress. Frozen append/maintenance reservations must charge observed retained artifacts/bytes before mutation. A postcheck cannot authorize an overshoot. Root will supply large-fixture expansion evidence and exact numerical qualification separately.

## Implemented to date

* `bulk_owner_stream.py`: engine-free original-byte field/text/membership proof, fixed field and pair order, single-row lookahead, bounded current-frame pending map, one-ID bounded reused-original resolver, canonical/exposure/offset checks, bounded original live-receipt validation, structurally bound receipt skipping with publication boundary checks; strict immutable canonical/digest-bound `OrderedQualification`.
* `bulk_exact_store.py`: private subclass retains inherited real `import_batch` and complete `_verify_batch`; ordinary store gets only no-op before/after append hooks. Ordered path uses streaming scandir with depth-bounded iterator stack, counts root/directories/all files/orphans, checks all existing private/owner/no-link checks, total logical/allocated/max-file ceilings before native open, under-lock path/pin revalidation, exact state/storage/schema/deletion/rewrite checks, dedicated all-fragment insertion-order scan with explicit six-column projection, strict32 batches, zero readahead,1MiB I/O and physical ceiling+1. Compaction unchanged/disabled for this path. Append reservation charged before actual write and output compared against charge afterward.
* `tests/test_bulk_owner_stream.py`: pure UTF8/NUL/empty/multi-page/order/corruption/reused-original/pending/receipt/publication/qualification/artifact checks.
* `tests/test_lance_owner_stream.py`: fixed private worker with argv-frozen manifest/hash, strict ordinary arguments plus qualification reference/hash only, <=64KiB private manifest read, exact request/destination/source/owner validation, complete512KiB request/output frames, ordinary dispatch parity and engine-import evidence. Exact supervision3s/192MiB task/256MiB aggregate, fixed absolute deadline, background preemption. Initial small native RED/GREEN completed; subsequent static coverage additions remain unexecuted during the pressure stop.

## TDD commands and evidence

Every pure run used exactly:

`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_owner_stream.py --noconftest -x -q`

1. Initial RED: missing bounded owner verifier assertion failed; safe aggregate37.0MiB /0.4s.
2. First implementation exposed malformed test construction (`member.bytes=8193` violated existing canonical page constructor before the verifier); corrected the intended valid-but-wrong bytes to8191, without changing the contract.
3. GREEN3: original bytes/order/reused bytes, aggregate37.0MiB /0.3s.
4. Qualification RED: missing qualified subclass assertion failed; aggregate34.6MiB /0.2s.
5. First qualification test construction needed reservations to remain inside intentionally reduced artifact/max-file envelope; adjusted only test reservations. GREEN5, aggregate37.6MiB /0.3s.
6. Publication-boundary RED: early/duplicate owner marker was incorrectly skipped. Added constant-state marker/live checks and forbade content after owner marker.
7. Latest pure GREEN6, aggregate31.2MiB /0.3s.

Root granted only the small RED scope. Ran:

`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 60 tests/test_lance_owner_stream.py -k 'pinned_stream or layout_corruption' --noconftest -x -s`

Expected RED: the fixed worker intentionally had ordinary-only dispatch. `ordered_import_batch` returned `unavailable/invalid_exact_request`; first pinned append assertion failed. Stage elapsed0.1198s, peak task44,761,088 bytes, peak aggregate84,574,208 bytes. Safe outer aggregate79.2MiB /0.4s. Native slot released immediately. Worker dispatch is now implemented; no ordered-engine GREEN has run yet.

Latest file-scoped Ruff check: all checks passed. `git diff --check`: clean. Broad tests intentionally prohibited by root dispatch; skill-wide broad-suite guidance does not override that restriction.

## Small qualification submitted to root

Exact expected states supplied per call; precreated destination/parent identities; schema `castle-exact-six-string-v1`; storage2.0. Maxima: physical rows256, fragments16, versions32, artifact entries128 (including root and directories), depth6, logical8MiB, allocated8MiB, single file1MiB, batch receipts16. Append/maintenance reservation each: rows32, fragments1, versions1, artifact entries16, logical1MiB, allocated1MiB, single file512KiB. All values fixed by fixture builder and accepted by root before native execution; no caller replacement.

## Outstanding gates and self-review concerns

* Root review/grant for exact fixed worker GREEN delta pending.
* Native corruption coverage still needs explicit artifact/depth/oversize-before-native, row ceiling and foreign-owner cases beyond initial order/version/fragment tests.
* Ensure individual new-file output and receipt ceiling reservations are fully checked before claiming the append reservation complete.
* Root-frozen large manifest, fixed source recreation and full expansion evidence pending. No52MiB implementation/run improvised. Full finalization and fresh5s source regeneration+identical replay+owner/live checks+real metadata ACK must all pass before Task1 can finish.
* No commit yet; task is not fully verified.

## Root-approved small native GREEN and current stop

Root independently reviewed the fixed worker delta and all three supplied SHA256 hashes, then granted the same exact selector/bounds. Ran the exact small command above; **2 passed in7.19s**, outer sampled peak181.2MiB /7.4s. No native RSS, deadline or pressure refusal occurred during this run.

Stage evidence (task peak / aggregate peak / elapsed):

| Operation | Result | Bytes task | Bytes aggregate | Seconds | Native imported |
|---|---|---:|---:|---:|---|
| Split membership stage (5 entries) | ok |135,544,832|175,554,560|1.1722|yes|
| Middle stage (4 entries) | ok |150,028,288|190,054,400|0.7092|yes|
| Final pending record + owner/live/batch receipts | ok |151,388,160|191,414,272|0.6527|yes|
| Actual identical final batch replay | ok |149,209,088|189,251,584|0.6431|yes|
| Actual identical early stage replay | ok |149,127,168|189,169,664|0.6146|yes|
| Old version pin | stale |131,809,280|171,851,776|0.6201|yes|
| Wrong fragment geometry pin | stale |131,940,352|171,982,848|0.6362|yes|
| Ordinary original source read | ok |149,061,632|189,120,512|0.6238|yes|
| Missing qualification | unavailable |45,957,120|86,097,920|0.0951|no|
| Request hash differs from frozen argv hash | unavailable |46,350,336|86,491,136|0.0997|no|
| Unchanged legacy import of shuffled valid entries | ok |135,249,920|175,390,720|0.6314|yes|
| Ordered-layout claim over that shuffled dataset | corrupt |147,095,552|187,236,352|0.6245|yes|

Final native geometry:15 rows in3 insertion-order fragments, version3; the three canonical records and all original fields remain unchanged by replay. Owner publication appended exactly the final pending record plus three small receipt/marker rows. Canonical file size/mtime/hash inventory unchanged on replay, stale refusal and ordered-corrupt refusal. Host engine/model/SQLite-free assertion passed. Native slot explicitly released to root after completion.

Next pure TDD step added `test_append_reservation_rejects_individual_file_overshoot`: a file within the total/global-file envelope but above the individual frozen append reservation must leave its artifact retained and refuse. This new test has **not run**. The exact pure safe-runner invocation was refused before pytest startup with `tests not started: memory pressure is elevated`, exit1. No retry, tuning or alternate fixture; root notified. No corresponding product fix was written without the RED observation. Latest verified pure count remains6. File-scoped Ruff/diff checks preceded this final test addition and must be repeated after work resumes.

Current status: **NEEDS_CONTEXT** pending root direction after the pressure refusal, plus root-frozen large gate inputs. All artifacts retained. No commit. Full Task1 remains incomplete; dependent implementation has stopped.

## Static continuation authorized during pressure stop

Root confirmed macOS pressure2 and permitted static-only test definitions and analysis. No test, engine, application runtime, pressure retry, or alternate test route was executed. No product implementation changed after the pending reservation RED was refused.

Static edits in `tests/test_lance_owner_stream.py`:

* Missing and request-hash mismatch refusals now explicitly assert `fixture_native_imported=false`.
* Changed qualification file contents with the original frozen digest must refuse before target/native access.
* Exact registered before/after state-pair replay must run real inherited replay proofs and leave canonical files unchanged.
* A reduced physical ceiling (5 versus actual6 rows of the existing tiny legacy fixture), with reduced reservation and registered geometry, must refuse after bounded native open without mutation.
* A separate ordinary staged foreign-owner fixture must refuse an ordered target-owner claim after native open without mutation.
* First extra artifact (root + dataset +127 files =129 versus fixed128), depth7 versus fixed6, and1MiB+1 manifest versus fixed1MiB individual-file ceiling must refuse before native import and leave artifacts unchanged.
* Stage logs retain status/receipt/resource/import evidence but omit full original source text from console output. The actual read response and exact-byte assertion remain unchanged.

All new cases retain the previously accepted fixed maxima or reduce the physical ceiling; no scope/cap increase or additional worker operation. They are static definitions, not passing-test claims. The authoritative report lives here in the SDD directory; the accidental repo-root report was moved by root.

Per-file reservation analysis: current global max-file checks do not enforce the smaller frozen per-operation `file_bytes` reservation. The simplest conservative interpretation is a bound on the maximum individual file in resulting retained geometry: record only a scalar largest file during the bounded streaming walk, refuse before mutation if an existing file already exceeds that operation's frozen file ceiling, and compare the resulting largest file to the same already-charged ceiling afterward. This needs no retained names or inode list and prevents a large preexisting file from hiding a new oversize file. It can be stricter than tracking only new files; root must freeze each operation's file ceiling to cover already retained indexes/manifests too. No product fix has been written; pending pure RED must execute first once root authorizes after normal pressure. A byte overshoot must still retain artifacts/charge and stop; the postcheck never authorizes it.

Next exact commands, only after root clears the pressure stop (and grants the native slot separately for the second command):

1. `/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_owner_stream.py --noconftest -x -q`
2. `/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 60 tests/test_lance_owner_stream.py -k 'pinned_stream or layout_corruption' --noconftest -x -s`
3. File-scoped Ruff and `git diff --check` after the authorized implementation/verification continuation. These checks were not rerun during this static-only continuation.

The52MiB gate command remains prohibited until root freezes/reviews its manifest, complete expansion evidence, fixed runner and grants that distinct scope. No new commit and no completion claim.

## Pressure cleared by root; per-file reservation RED/GREEN

Root independently rechecked macOS pressure at1 (normal), authorizing the pending exact pure command once and the affected pure GREEN. The safe runner independently admitted execution. No native test was authorized or executed in this continuation.

Exact command both runs:
`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_owner_stream.py --noconftest -x -q`

RED:6 passed then `test_append_reservation_rejects_individual_file_overshoot` failed because `_after_append` did not raise for the retained256KiB+1 file above the frozen256KiB reservation (still below1MiB global file ceiling). Aggregate38.1MiB /0.4s.

After observed functional RED, implemented only scalar largest-regular-file accounting in the existing streaming walk. Before append, the existing largest file must fit the frozen operation `file_bytes`; after append, resulting largest file must fit that same already-charged maximum. `file_bytes` is deliberately excluded from additive artifact deltas. No path/name maps, extra scans, or ceiling change. Extended the same test to require refusal before a later append over the retained oversize artifact. GREEN:7 passed; sampled aggregate34.8MiB /0.2s. Artifacts remain retained after the simulated overshoot.

Root's binding rule: operation `file_bytes` is the maximum individual regular file in the resulting **complete** retained destination, including existing indexes/manifests. Cost: one scalar max comparison for each already-enumerated regular file; conservative qualification may refuse small appends when retained files exceed that operation's reservation, so root must freeze an operation ceiling covering those retained files. It is neither an incremental file byte budget nor new-file-only promise.

Latest file-scoped Ruff check passed; `git diff --check` passed. Product code has no other post-native-GREEN change. Expanded static native tests remain unexecuted and require a separate root slot/grant under the same fixed small selector and caps. No52MiB run or commit.

## Large contract clarifications from root

The52MiB/6,656-member qualification is one historical owner with `manifest.live=None`. Required live checks are conditional; the existing small three-chunk live native evidence covers ordered original live-receipt semantics. No>9-chunk live receipt and no extra large live fixture is authorized. The large gate must use the original historical registration/source cursor, full actual bulk replay/owner proof and existing metadata queue ACK. It must not claim source EOF or corpus completeness; the two later AUDIT owners stay outside this dedicated historical destination.

Root authorizes designing internal qualified fixture maintenance around unchanged existing `build_id_index` limit16,384. The historical owner (~13,696 or explicitly counted extra rows) fits. Any maintenance requires frozen expected pin, preflight charge and postcharged geometry; no new ordinary worker operation, automatic maintenance on reads, cleanup, optimization framework or cap change. Exact maintenance/staging call schedule and byte reservations remain root-frozen inputs not yet supplied. An extra last-entries staging receipt, if chosen by root for small marker finalization, must be counted explicitly and cannot repack an already pending source intent. No sequence chosen or maintenance implementation added yet.

## Expanded small native GREEN after separate root review/grant

Root read expanded test cases and scalar largest-file delta, independently matched native test87a74b20…, storef5734905…, module0f89e906…, verified pressure1 and granted the unchanged small selector/profile. Ran exact60s command above: **2 passed in10.56s**, safe sampled aggregate182.5MiB /10.9s. No resource/pressure refusal. Native slot explicitly released immediately after the run.

| Stage | Outcome | Task bytes | Aggregate bytes | Seconds | Native |
|---|---|---:|---:|---:|---|
| Split membership stage |ok|136,396,800|177,651,712|1.2727|yes|
| Middle stage |ok|151,371,776|192,626,688|0.7360|yes|
| Finalization with pending last record |ok|152,207,360|193,462,272|0.6727|yes|
| Full identical final batch replay |ok|150,093,824|191,365,120|0.6644|yes|
| Identical early batch replay |ok|149,372,928|190,644,224|0.6519|yes|
| Registered before/after pair replay |ok|149,700,608|190,971,904|0.6866|yes|
| Old version pin |stale|132,939,776|174,211,072|0.6572|yes|
| Fragment-count pin mismatch |stale|132,775,936|174,047,232|0.6898|yes|
| Exact original source read |ok|148,422,656|189,693,952|0.6524|yes|
| Missing qualification |unavailable|46,530,560|87,851,008|0.0946|no|
| Request hash mismatch |unavailable|46,596,096|87,916,544|0.0958|no|
| Frozen manifest content changed |unavailable|46,465,024|87,785,472|0.0975|no|
| Legacy arbitrary valid entry order |ok|134,889,472|176,209,920|0.6328|yes|
| Ordered claim on that physical order |corrupt|148,799,488|190,136,320|0.6436|yes|
| Actual6 rows exceed lower frozen5-row ceiling |unavailable|132,251,648|173,588,480|0.6272|yes|
| Ordinary foreign-owner stage |ok|135,380,992|176,717,824|0.6358|yes|
| Ordered target-owner claim over foreign rows |corrupt|148,324,352|189,661,184|0.6428|yes|
| First129th artifact versus128 |unavailable|46,317,568|87,670,784|0.1001|no|
| Depth7 versus6 |unavailable|45,858,816|87,212,032|0.0968|no|
| Manifest1MiB+1 versus1MiB |unavailable|45,318,144|91,521,024|0.1014|no|

All replay/refusal canonical file size/mtime/hash inventories remained unchanged; qualified paths refused artifact excess before native import/open. The final15-row/3-fragment/version3 destination preserves all original text, metadata/scopes/descriptor pages, canonical IDs and original three-chunk live receipt. Original source read returned every exact original character. No native/SQLite imports in pytest host. No artifact cleanup, cap increase or fallback path.

After native completion, file-scoped Ruff passed and `git diff --check` passed. No commit because full Task1's large gate remains pending. Product files/test files remain the four scoped files; authoritative report is this SDD path. Next dependent work requires root-frozen large runner/qualification/call sequence and separately granted native scope. No52MiB test, maintenance operation or dependent Task2 work has started.

## Qualified explicit maintenance preparation (pure TDD only)

Root authorized maintenance preparation while large source manifest finishes, with pure safe-runner only and no native/large grant. Added two pure tests using engine-free metadata objects to exercise real geometry/reservation helpers: exact physical rows/fragments preserved, unchanged16,384 index ceiling, retained/resulting largest-file charge and no artifact cleanup after overshoot. Exact20s pure command RED after7 passes: missing `_before_maintenance` assertion; safe39.0MiB /0.4s. After implementing helpers/override: **9 passed**, safe36.4MiB /0.2s.

Product delta: `OrderedBulkExactStore.build_id_index` only, preserving original `BulkExactStore` method and ceiling. Writer chain revalidates private path/exact pin under lock. `_before_maintenance` enforces physical index limit16,384 and all frozen resulting geometry/artifact/version/byte/file reservations; only afterward calls real `dataset.create_scalar_index('id','BTREE',name=INDEX_NAME,replace=True)`. `_after_maintenance` uses the actually mutated handle, checks exact unchanged physical rows and fragment count, applies existing charged postchecks, then returns coverage from that handle. It never calls `_open` using stale pre-state to authorize/check its resulting version. Common append postchecks extracted into a private charged-operation helper without changing ordinary store hooks. No automatic read maintenance, cleanup, compaction, cap or ordinary worker/runtime operation change.

Fixed fixture delta: `ordered_build_id_index` accepts exactly empty ordinary arguments plus existing same argv qualification reference/hash binding; arbitrary action/extra arguments still refuse. Exact guardian/profile remains3s/192MiB/256MiB, preemption and absolute deadline, all previous small maxima unchanged.

New unexecuted native definition `test_pinned_stream_qualified_maintenance` (matches existing selector): create one6-row/1-fragment/version1 tiny owner; frozen maintenance versions reservation0 refuses unchanged; accepted explicit index should produce version2 with same6 rows/1fragment; a separate fresh fixed worker ordinary owner read must see persisted index coverage, then real original identical batch replay under version2 pin checks full owner proof and leaves files unchanged. All calls remain within approved small8MiB total/1MiB individual global envelope and frozen512KiB resulting-file/1MiB artifact byte reservations. No native test has executed since this delta.

Latest Ruff check and diff whitespace check pass. Root review/grant requested with SHA256 store81b43c12c7970777ec97f3599ebb55e9e9d7af972a4014de5daa9d26bd5f16ca, worker14aa1f2115cd04b7777609d6ff1838c8eb27c9203d6af27a3a622359cc034f96, puretest7872381043baef157bd5625f1bd8e73521682c3d1c2fa526cfeffd6f30c8ee3d, unchanged puremodule0f89e906fe41881c219b8ffd51981fd6aac39e39900470ec0074e5672a1de072. No commit before large gate.

## Qualified maintenance native GREEN after separate root grant

Root reviewed actual fixture dispatch and maintenance/shared-postcheck delta, independently matched store81b43c12…/worker14aa1f21…, verified pressure1 and granted unchanged60s selector now selecting3 tests. Exact command: `/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 60 tests/test_lance_owner_stream.py -k 'pinned_stream or layout_corruption' --noconftest -x -s`. Result: **3 passed in13.61s**, sampled safe aggregate186.8MiB /13.8s. No pressure, RSS, deadline or overshoot refusal. Native slot explicitly released immediately.

All previously expanded append/replay/pair/stale/foreign/artifact cases passed again under changed shared postchecks. First append1.3341s (138,723,328 task /180,682,752 aggregate bytes); finalization0.6414s (152,125,440 /194,101,248); final full replay0.6663s (149,782,528 /191,774,720). Artifact/depth/manifest and qualification refusals remained before native import. Foreign owner, actual physical ceiling and bad ordered layout remained bounded post-open refusals without mutation.

Qualified maintenance stage evidence:

| Stage | Result | Task bytes | Aggregate bytes | Seconds |
|---|---|---:|---:|---:|
| Tiny original owner append (6 rows/version1/1fragment) |ok|135,708,672|182,648,832|0.6418|
| Zero-version-reservation index request |unavailable unchanged|132,333,568|179,273,728|0.6237|
| Real explicitly qualified ID BTREE creation |ok|148,946,944|195,887,104|0.6328|
| Fresh worker ordinary owner read sees persisted index |ok|149,012,480|195,952,640|0.6385|
| Full identical original batch replay with exact version2 pin |ok unchanged|151,109,632|198,049,792|0.6299|

Index result: dataset version2, index_version1 (index built over original data version1), one indexed fragment, zero tail fragments/rows. Actual-mutated-handle postchecks proved6 physical rows/1fragment unchanged; the fresh read and full replay independently proved persisted index and original owner bytes. Canonical files unchanged during refusal/fresh read/replay. Host native/SQLite-free assertion passed. Ordinary worker/runtime/public requests and16,384 product maintenance cap unchanged. No cleanup, automatic maintenance or tuning.

No commit; full Task1 still depends on root-frozen52MiB historical source/destination expansion manifest, exact call/maintenance/receipt accounting and distinct native grant. No large test executed and no sequence improvised.

## Task1a milestone commit authorized by root

Root explicitly split1a (verified primitives and small proofs) from1b (52MiB source→publication/full cold replay+metadata ACK qualification) and authorized a single local milestone commit before independent review. This supersedes the earlier instruction to avoid any Task1 commit before the large gate; it does not complete whole Task1.

Local commit: `b229f20` — `feat: add qualified ordered owner streaming primitives`.
Exactly four committed files: `cognitive_castle/bulk_owner_stream.py`, `cognitive_castle/bulk_exact_store.py`, `tests/test_bulk_owner_stream.py`, `tests/test_lance_owner_stream.py`. Commit contains no report, architecture docs, source adapter contract changes, activation or large fixture. Working tree clean after commit. Fresh scoped diff whitespace check passed immediately before commit; verified9pure/3native and Ruff evidence above remains current because no product/test change followed those checks. No redundant test run was performed.

Task1a implementation complete pending independent root review. Task1b not implemented or qualified; no52MiB destination construction/run, full cold source replay/owner/queue ACK evidence or corpus-completion claim. Root-frozen manifest/call/maintenance geometry and separate native grant remain required. Resource refusal history retained; no cap increase, retry sequence or SHA progress machinery introduced.

## Task1a independent review fix round1/5 (findings1–4)

Read full Important findings1–3 verbatim from `task-1a-review.md`; checked real import, mutation hooks and fixture budget paths before editing, using receiving-code-review/TDD guidance. Root added concrete finding4 after review: a new valid own-owner stage page after published marker could make previous full replay corrupt. All findings confirmed against milestoneb229f20. No unrelated product or public protocol change; no native run yet in this round.

1. Resulting receipt ceiling: dedicated bounded metadata scan projects six existing canonical columns and filters only `bulk_receipt` rows. Uses fixed strict32 batches, zero readahead,1MiB I/O, insertion order and `max_batch_receipts+2` sentinel (one bound owner marker plus first excess batch). Validates source/owner/receipt shapes, duplicate batch IDs and duplicate owner marker. Before every append, charges exact existing count plus newly appended batch receipt; over-ceiling refuses before mutation. Before maintenance, validates existing count without adding one. Charged postchecks require exact expected count. The scan rereads no original content payload as Python rows and retains only the bounded receipt-ID set and marker boolean. Full owner/batch proofs stay unchanged.
2. Reconciliation after-state: common mutation-geometry helper admits registered pre-state for writes, refuses `stale` from second/after-state before append or native index creation. Existing inherited receipt replay returns before either mutating hook, still performing real full batch/owner proof. Maintenance after-state explicitly refuses; a fresh ordinary read handles visibility rather than an invented maintenance receipt.
3. Fixed fixture budget: ordinary reads use2s, writes/maintenance3s, for both relative and absolute deadlines. Engine-free supervisor-argument tests assert exact budgets,192/256MiB and background preemption for both reads and ordered/ordinary writes. Earlier native elapsed read times below2s were nevertheless guarded with3s; historical evidence is preserved, but only the pending focused rerun will qualify actual2s guards.
4. Published-owner immutability: receipt metadata proof exposes publication marker. New pending `bulk_page`/`bulk_record` rows after publication refuse `conflict` before append. Actual recorded replay remains unchanged; equivalent imports whose entries already exist can append only the new bound batch receipt when within its ceiling. No source conversion/order change.

Pure TDD commands/results:

`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_owner_stream.py --noconftest -x -q`

* Receipt-boundary RED: after9 prior passes, no refusal for existing receipt1 + new receipt1 with frozen max1;35.1MiB /0.4s. GREEN11 after pre/post receipt accounting;31.2MiB /0.2s. Pure maintenance overflow regression also passed.
* After-state RED: after11 passes, append hook did not refuse;36.3MiB /0.3s. GREEN13 after shared mutation-state check;39.2MiB /0.3s. Both mutators checked; before-state semantics retained.
* Root late-content RED: after13 passes, own-owner page after published marker did not refuse;40.0MiB /0.4s. GREEN14 after publication gate;38.3MiB /0.2s. Receipt-only equivalent charge remains allowed.

`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_lance_owner_stream.py -k supervisor_budget --noconftest -x -q`

* RED: `read_sources` budget3 != required2;36.2MiB /0.2s. GREEN5 parameter cases;35.6MiB /0.2s. No engine/SQLite/model import or supervisor execution; only actual wrapper arguments captured with fake supervision/admission FD to/dev/null.

All launches independently passed safe-runner pressure gate; no pressure/resource refusal or retry in this round. File-scoped Ruff and `git diff --check` pass. No repeated broad/native tests.

Focused native definitions (not executed): same60s `-k 'pinned_stream or layout_corruption'` selector now selects6 cases. Three prior cases now use corrected2s reads; qualified-index case additionally uses a pre/after pair and refuses after-state retry. Three new cases prove (a) stage and finalization refuse max1 receipt excess unchanged, max2 final success+real replay and maintenance refusal over lower cap; (b) pair pre-state original real append succeeds, after-state identical inherited replay succeeds unchanged, new finalization/maintenance refuse unchanged, fresh ordinary owner read works; (c) late new valid own-owner page refuses unchanged and previous real replay stays valid, while receipt-only equivalent import remains valid. Same fixed global small256rows/16fragments/32versions/128entries/depth6/8MiB total/1MiB file/16batch-receipt envelope, or lower1/2receipt ceilings; no cap increase or additional worker operation.

Root review hashes: stored4a49521253820a80d440b18458a1a5b860008f465826ee856db12267abc0f51; puretest39a00ab2c0641155018633c85fceb6eabd98a35323622c42edb0303de23648a3; fixture84463b09496c137861d275081f950e473c7018476fe6873853bdd848a58a9538; puremodule unchanged0f89e906fe41881c219b8ffd51981fd6aac39e39900470ec0074e5672a1de072. Root currently holds native slot for separately reviewed source-only recreation; no native execution from this agent until distinct grant. Commit only verified fix after covering native tests. No1b destination construction/run or next task.

## Round1 sole native run —5 cases pass, sixth preempted; sequence stopped

After its source-only run stopped, root independently verified pressure1 and reviewed the complete delta. Granted exactly one run of the60s six-case selector. Immediately before launch, SHA256 matched all three reviewed/report hashes exactly (stored4a49521…, puretest39a00ab2…, fixture84463b09…). Safe runner independently admitted launch; no pressure refusal at startup.

Command:
`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 60 tests/test_lance_owner_stream.py -k 'pinned_stream or layout_corruption' --noconftest -x -s`

Result: **1 failed,5 passed,5 deselected in21.92s**. Safe sampled aggregate193.3MiB /22.2s. Failure is a preserved guard refusal, not a functional assertion about the late-content fix: sixth case `test_pinned_stream_published_owner_rejects_late_content_preserves_replay` received `unavailable/background_preempted` on its **initial original owner append**, before late-content/refusal/replay assertions. Stage elapsed0.3888s, task peak118,996,992 bytes, aggregate168,312,832 bytes. No retry, alternate route, cap/preemption change, cleanup or commit. Product/test hashes unchanged. Native slot explicitly released immediately and root notified.

Retained sixth fixture path from test evidence: `/private/var/folders/sv/07gg7rcs7gg7rl7s19f3xpsc0000gn/T/pytest-of-ladislavbihari/pytest-565/test_pinned_stream_published_o0/published`. Do not infer whether native append committed from the missing acknowledgment. It remains charged/unqualified pending root action, not automatically retried.

Completed focused evidence (all artifact immutability assertions passed):

* Existing pinned finalization/full replay/pair/stale/foreign/geometry/artifact cases passed with shared receipt postchecks. First append1.2318s (153,845,760 task /197,705,728 aggregate bytes), finalization0.6489s (153,485,312 /197,345,280), full final replay0.6225s (150,077,440 /193,970,176).
* Actual **2-second** read_sources guard succeeded0.6353s (148,750,336 /193,085,440). Both relative and absolute budgets are2s as independently covered by5 engine-free argument cases.
* Qualified real index creation using pair pre-state succeeded0.6376s (153,387,008 /202,686,464), version2/index_version1/one indexed fragment/tail0. Pair after-state maintenance retry refused `stale`0.6359s unchanged. Fresh persisted-index bulk_owner under **2-second** guard succeeded0.7065s (149,897,216 /199,196,672); full original replay0.6242s (151,568,384 /200,867,840) unchanged.
* Receipt-boundary case: original stage(max1) succeeded0.6294s; finalization excess refused `unavailable`0.7224s (150,224,896 /199,524,352); stage-only extra receipt refused0.6222s unchanged. Raising only this case from intentionally lowered max1 to its separately frozen max2 admitted exact-boundary finalization0.6325s (152,567,808 /201,867,264), and actual identical full final-batch replay succeeded0.6297s (149,553,152 /198,852,608), unchanged. Maintenance under lower max1 over existing2 receipts refused0.6229s unchanged. No global small cap changed.
* Reconciliation case: pair pre-state original real append succeeded0.6420s; actual original inherited replay from after-state succeeded0.6367s unchanged (149,880,832 /199,196,672). New finalization at after-state refused `stale`0.6324s; index request refused `stale`0.6153s; files unchanged. Fresh ordinary bulk_owner under **2-second** guard succeeded0.7623s (148,815,872 /198,131,712), manifest exact and files unchanged.
* Sixth late-content boundary did not reach its native regression assertions. Pure late-content/refused-replay-equivalence test remains GREEN, but no native qualification claim for finding4 is made.

No further test or product changes after preemption. Scoped Ruff/diff evidence above remains current because files unchanged. Root must review external admission/preemption state before any further native authorization. Fix commit remains pending completion of its covering native case; milestoneb229f20 remains base. Task1b destination/52MiB run and next tasks remain unstarted by this agent.

## Round1 final single-case native admission and fix commit

Root independently verified a changed external scheduling state: pressure1, interactive_waiting=false, global admission available/released, no workers. The previous preemption coincided with root resuming another preparation agent; that is a plausible external request explanation, not established proof of a product failure. Root authorized exactly one newly admitted run of only the previously preempted late-content test, using a fresh private fixture and unchanged budgets. Other5 green cases were not rerun. Previous unknown-acknowledgment fixture remains retained/unqualified.

Command:
`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 60 tests/test_lance_owner_stream.py::test_pinned_stream_published_owner_rejects_late_content_preserves_replay --noconftest -x -s`

Result: **1 passed in3.27s**, sampled safe aggregate180.3MiB /3.4s. No guard/resource refusal, cap change or alternate execution route. Native slot explicitly released immediately.

| Stage | Outcome | Task bytes | Aggregate bytes | Seconds |
|---|---|---:|---:|---:|
| Original committed owner (4 rows, version1, fragment1) |ok|151,011,328|189,054,976|0.6769|
| New valid own-owner descriptor page after publication |conflict unchanged|149,602,304|187,662,336|0.6375|
| Actual original inherited full batch/owner replay |ok unchanged|149,979,136|188,039,168|0.6448|
| Equivalent original entries/new batch receipt only |ok|153,321,472|191,397,888|0.6250|
| Actual original full replay after receipt-only import |ok|149,962,752|188,039,168|0.6482|

All regression assertions reached and passed, including canonical file immutability after late-content refusal and original replay. Receipt-only equivalent import increments only one receipt/version/fragment; original full owner proof remains valid. Small exact RSS192MiB task/256MiB aggregate, writes3s, read budgets2s, preemption/absolute deadlines unchanged. No original text/canonical/source contract change.

Fresh scoped Ruff check and `git diff --check` passed before commit, with no product/test change since the reviewed hashes. Authorized local fix commit: **`6fa66595c16fd71c7ec388831c199b839bf93683`**, `fix: enforce ordered publication mutation boundaries`. Exactly3 files: `cognitive_castle/bulk_exact_store.py`, `tests/test_bulk_owner_stream.py`, `tests/test_lance_owner_stream.py`; pure verifier/qualification module unchanged. Working tree clean. No push, install, merge, activation, large destination or Task1b run. Root will prepare b229f20→6fa6659 scoped rereview of findings1–4. Whole Task1 not complete.

## Task1b executable preparation and final freeze (no native execution)

Root accepted full source prerequisites from the actual numerical/final-export result SHA3301bc9f2dc9fa0fa49d58d58c4e0c6598bc2f8f7ef35c6d425215d6977e85d2 and sibling independent review. History only:13,524 entries/171 source intervals/6,656 canonical members/54,525,952 original bytes/13,696 resulting rows. Final original cursor entry13,451, fieldrecord, member6,619; actual final export73entries+one owner, frame367,932B; measured source-only final proof/export1.0106s, task55,967,744B/aggregate79,740,928B. Receipt sizing is not durable destination evidence. Two later AUDIT owners excluded; no source EOF claim.

Root corrected the plan's small-marker wording: preserve the ordinary final73entries+owner+batch receipt. NO extra staging-only batch, cursor manufacturing or pending-intent repack. Lost response uses existing `ObservedSession(loss='import_batch:1')` after actual successful final publication and before queue ACK. Fresh cold host/process uses the original coordinator and actual queue pending state, regenerates the full original interval, executes TWO real inherited import replays/full owner proofs, reads actual owner metadata and performs real metadata ACK in one5s lease. Live isNone for this historical owner; existing reviewed small live evidence remains separate, not rerun.

Tracked files: new `tests/lance_owner_stream_fixture.py` and scoped updates to `tests/test_lance_owner_stream.py`. Product store/source/runtime behavior/caps unchanged from approved1a. Private configuration, metadata-only preparation builder, retained old helper/cache, seal and pin live in the owned ignored packet. Reusable pure code is tracked/portable; clean checkouts explicitly skip only the private operator gate when config is absent. Bytecode writes disabled before dynamic helper load. No native/source rebuild or unchanged1a rerun.

Fixed schedule accepted by root:171 append fragments/receipts;18 explicit index builds before10,19,…163, versions189. Scope-specific103 physical-row/call proof gives tail<=927rows/9fragments; enforce it on actual source frames. Expected states remain exact; q maxphysical16,384 only reserves headroom. Final append75 rows; cold replay0 rows/versions/fragments. Real maintenance is unchanged16,384-row BTREE build, zero canonical row/fragment change; fresh qualified existing bulk_receipt read proves active coverage. Registered after-state is read/replay-only. No fallback schedule, automatic read maintenance, cleanup or compaction.

Hard candidate limits frozen in C: destination320MiB logical/allocated,1,024 entries/depth6, largest resulting file2MiB (retained indexes included for appends); append growth1MiB/index growth2MiB,16 artifact-entry reserve. Source families128 entries/original512MiB scope, H256 entries/24MiB, T1,024 entries/80MiB (64MiB working+16MiB retained debt), overall owned512MiB and2GiBfree+next reserved growth/workspace/metadata before mutation. Queue total DB+journal reserve8MiB plus8MiB working temp; onejob/onepending/lastACK metadata schema, no invented temp_storeMEMORY/max_page_count. Source remains immutable/query_only/temp_storeMEMORY and full-file/source proof checks. Source/queue unlinked transient disk is unmeasured; exact worker samples own FD/unlinked bytes and retained roots. Sampling is a tripwire, not kernel quota. Child native settings16MiB reservation pool/64MiB tracked shared spill, bypass absent/private TMPDIR, unchanged threads. Standard source128/192MiB2s, exact192/256MiB2s reads/3s writes, common5s session and preemption/admission unchanged.

Normal calls1,070=170×6 prior calls +5 lost-final calls +6 cold calls +36 index/fresh-read calls +3 initial/pending/final real queue-state calls. Hard1,071 permits one explicit index-reconciliation read; no automatic retry. Exactly380 logical exact workspaces (343import,one final owner read,18index,18receipt read), reused only for an explicitly resumed same phase with all debt retained. T normal382 includes temporary root and coord-source directory; normal total1,359=source122+D610+H245+T382; hard2432 unchanged. Earlier builder output omitted temp root and printed1,358; retained unmodified, corrected in focused evidence outside the frozen packet.

Actual static census source122 entries/61,522,214logical/61,915,136allocated bytes; packet6 entries/39,717logical/49,152allocated before final seal/pin. H normal245 includes205 run-H+packet6+futureseal/pin2+config/basetemp2+29 code pins+worker1. All29 code pins total551,767B. Reserved bytes source61,915,136+destination320MiB+temp80MiB+H24MiB =506,511,360B (~483.05MiB), leaving30,359,552B under512MiB. This is reservation arithmetic, NOT native disk/time/RSS qualification.

Focused pure preparation used only20s safe runner on new `large_` selectors.18 new cases passed together, sampled48.5MiB/0.4s; subsequent focused raw seal positive/changed-rejection case passed43.2MiB/0.4s. P2 failure-path regression observed actual new file after refused cold tick (RED37.3MiB/0.4s), then fixed to preallocated refusal slot/stdout only (GREEN41.9MiB/0.2s). Other observed RED/GREEN additions covered fixed schedule/no-extra-final rows, readonly qualified dispatch, exact-state/growth construction, missing freeze, bounded census/reservation, fixed native environment, accounting inside original clocks, real pending/ACK pin reconstruction and index-version read reconciliation. One test-construction error forgot to recompute modified synthetic frame_bytes; fixed test accounting while retaining strict production validator. No source/body data or engine loaded in these tests. File Ruff/diff clean before seal; no test reruns after final freeze.

Exact focused evidence outside packet: `task-1b-focused-evidence.md`, SHA8891a1620dbb99f7313f73978d7dc37a5855bf7b750477e6d4d424df2ce657bf. It faithfully states seal has a positive/expected-rejection GREEN run but no separate observed RED, and records actual P2 terminal outputs. Root rereviewer closed P2 and approved static protocol subject to final seal verification.

Final freeze authorized and performed with metadata/literal changes ONLY:

* Configuration C5bf8e1a9dc7f4f214757a48bcdcfcffa27abf75a0b6619e7b667a65394582745 copied exclusive from retained candidate to `.superpowers/sdd/2026-10-24-unified-lance-memory/layout-52mib-qualification.json`.
* Helper H3c2597f2e11cf71520c9fd2086b9057e47d8207ae456bfe2b0479c8e569fd183,73,634B; all29 code pins unchanged.
* Only worker literal set toC. Final worker W02ada197f17e79319c44f8ef06fd61dee5958d12f79532ec9ce613b7a83e2ea1,50,921B.
* Exact raw final seal S70836ee0112e40c6a407093902390a0cc87eb746d7c848ea8cadfec41729b419 binds configurationC/finalworkerW/helperH. No normalization/circular worker pin in config.
* Fixed private0400 `task1b_fixture/launch-pin.json` raw SHA10ce1cc2f5064dc0366fe3052884ee8a889100538652922925313035eb4cd8be carries C/S. Root independently verifies pin/seal/code before launch; loader rejects arbitrary CLI pin location, checks fixed private path/mode/link identities and exact raw hashes pre/post stage; sampler uses stats without hot-loop hashes.
* Runroot `task1b-history-20261025-6fa6659-run1` and explicit basetemp `task1b-pytest-20261025-6fa6659-run1` remain absent. No source/destination engine opened; no1b commit/activation.

Root's exact pending command (tool stdout only, no new run log file):
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 600 tests/test_lance_owner_stream.py::test_52mib_finalization_and_cold_replay --basetemp /Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse/.superpowers/sdd/2026-10-25-bounded-lance-layout/task1b-pytest-20261025-6fa6659-run1 --noconftest -p no:cacheprovider -x -s`

Actual supervised evidence belongs in precharged existing events/peaks/refusal slot and tool transcript. The sleeping pytest ancestor/outer safe-wrapper transient HOME/isolation/admission infrastructure and transcript transport are distinguished from the owned512MiB storage envelope; outer sampled RSS (default700MiB tripwire) is reported separately from inner unchanged task+immediate-host profiles. Cold host transport7s and bounded descendant cleanup surround, but never extend, its inner shared5s session; fixed output<=7compact stage lines+<=16KiB summary is under32KiB, checked against65,536B. Root launch must verify actual1PASS rather than SKIP. Code/candidate/seal now held unchanged for that independently authorized launch.

## First large execution and outstanding-only continuation preparation

Root first frozen attempt preempted atstage122 after19 real ACKs and2 completed index/read pairs. Full retained metadata, measured maxima, oldraw hashes, schedule correction, focused5-case TDD evidence, newcandidate hashes and precise H255/T382 accounting: `task-1b-run1-preemption-report.md`. Root authorized preparation only; no continuation freeze/runtime yet. Existing original config/seal/pin/refusal remain preserved. All resource caps unchanged; cumulative1074 is an explicit diagnostic scheduling correction, never a counter reset.

## Continuation1 final freeze (root approved, no runtime by implementer)

Root full scoped review and independent9e64c2ca approved the candidate; exact metadata/literal-only freeze completed. Candidate copied exclusively to new fixed `layout-52mib-qualification-continuation1.json`; only worker frozen literal changed afterward.29 code pins and helper raw bytes unchanged.

- C `63a2421fc669584ceb86fa710981cb92db56c8fa2ee2e4bad273c5160ba65fbb`
- final W `cbcec066056e6d30a260c5060421ab2b7210e45ec24b1c5619b7ffc0e26af8dc`
- unchanged H `beab6fa7a559511e2a226595382d7d814d442a4a3e77bf2c56b4bab383cf7f56`
- external S `bb84bd43502f3fce9f1347b5b922b60e681394cadaa720823f6a783e28cd272c`
- fixed0400 pin raw SHA256 `e5913c94c98fdbbddf0ba0c0973b1057397160cc2a5bf1904e07a7ccfc79cd2e`

New packet contains exactly root+4files (W1/H1 archives,seal,pin), no discretionary artifact. All8 prior raw claims independently rehashed unchanged immediately before freeze; new event/peak files empty and4096B continuation refusal blank; newbasetemp absent. Hnormal255/T382 accounting unchanged. No tests, reruns, source/queue opens, engines or native launch performed during freeze. Root launches the already-recorded exact540s/700MiB outer command after independent seal verification. Implementer ends turn to avoid additional process startup during native work.

## Continuation1 stopped; continuation2 preparation under explicit root amendment

Continuation1 also preempted:103 new starts,102OK plus stage225 `background_preempted`, at ordinal36 FIRST import after successful source223 (80entries/397532B) and prepare224.16 new real ACKs =>35 total;3 total maintenance/read pairs.225 cumulative starts,223OK,2preemptions. First append36 commit UNKNOWN; no finalization/cold/fullowner/finalACK or qualification PASS. Destination is preserved for real idempotent before/after reconciliation. Continuation1 retained events56673B SHA `e9ca6cc1d5355dbd87a5ee446ea1dd4209cb39529f63ef4f9bb705f036a3e4d3`; peaks72551B SHA `f6b9945570aa731873d1f660cfcde3ebeba13e2bb90024ec052392075e7a5843`; refusal4096B SHA `a857c62f01ea50207d2d858449e8969c3a954c12e069c69a76386a4dcbbfd5ef`. Inner maxima task170082304B/host+task225411072B/stage1.4541s. Root measured outer guards59.5s+50.4s=109.9s total. Source/queue unlinked transient disk peaks remain unmeasured; no completed-case fit claim.

Root traced both foreground preemptions to minute capture incorrectly using foreground admission. Separate isolated hotfix0594472692ba5d444e846bb6462af2ef51dd25c3 qualified13pure+2native and was installed locally; default foreground priority remains. Remote push blocked403 and root handles authorization. No hotfix file or installed path changed by this preparation; capacity-reuse only helper/worker changed.

Root explicitly authorized diagnostic scheduling1078 cumulative (verified225retained+max853new) and metadata-entry correction Hhard272,normal264,wholeentrysum2448. This preserves actual failed attempts caused by the now-fixed capture bug; it is NOT native-capacity tuning. Old1071/1074 and H256 failed-case evidence remain. RSS,stage/shared5s/engine/file limits, H24MiB,whole512MiB,D1024,T1024,source128,logicalexactworkspaces380 unchanged. No optional maintenance reconciliation or automatic retry. Outer next480s/700MiB gives combined admitted execution<=589.9s; idle preparation excluded.

Exact arithmetic:normal useful work through ACK35=1startup+35*6+3*2=217. Normal remaining1070−217=853=135*6+final5+cold6+15*2+2queue states. Required existing pending36 skips its original prepare (−1); new startup open adds1;853new/1078cumulative. Actual real queue open must reconstruct ACK35 `(version38,rows2686,fragments35)` and exact pending intent `1efd1c94ae142641fe368cb58aeb3c334af32352adc7654d32941f12b9c4fa9f`, existing q36 before38/2686/35→after39/2767/36. Missing/wrong pending, changed intent or pin refuses; no seeded cursor/count. Both original imports still execute; inherited real receipt/full-proof behavior handles unknown first append commit. No maintenance at ordinal36; next planned boundary37 remains original schedule.

Raw W2/H2 copied exclusively0400 BEFORE tracked edits to existing packet `worker-run2.py`54781B/hash `cbcec066056e6d30a260c5060421ab2b7210e45ec24b1c5619b7ffc0e26af8dc`, `helper-run2.py`79430B/hash `beab6fa7a559511e2a226595382d7d814d442a4a3e77bf2c56b4bab383cf7f56`. Original packet/config/seal/pin/raw archives/events/peaks/refusals unchanged. New fixed configuration path ends `layout-52mib-qualification-continuation2.json`; same existing packet root, distinct fixed seal/pin filenames `final-seal-continuation2.json` / `launch-pin-continuation2.json`. Same reviewed noncircular C→literalW/externalCWHseal/pin pattern; no generic retry framework or extra layer.

Focused TDD exactly `...python scripts/safe_brain_tests.py --timeout 20 tests/test_lance_owner_stream.py -k large_continuation2 --noconftest -x -q`: RED actual old122 schedule rejects225 claim,43.8MiB/0.4s. GREEN10,49.9MiB/0.4s:225→226 persists,1078 bound refuses without new log; both old streams changed/truncated-but-rehashed reject; ACK35/pending36 accepted and missing/wrong pending,wrong geometry,wrong pin reject. No prior green/native rerun. Scoped Ruff and diff check clean.

New3 attempt evidence files exclusively precharged only after engine-free metadata census+64KiB reservation; events/peaks empty and refusal4096B whitespace. Precharge snapshotH103entries/1283312logical/1490944allocated,free77430382592B,ledgercalls225 derived from old streams. No source/queue database/native opened. Finalconfig/seal/pin/newbasetemp remain ABSENT, worker literalNone.

Precise Hnormal255+rawW2/H2archives2+newconfig1+newseal/pin2+newevents/peaks/refusal3+newbasetemp1=264 <=272. No new packet directory, discretionary builder/cache/report inside case families. T382 unchanged(root1+coordsource1+380exact); existing `exact-stage-036-publish` reused retaining artifacts charged, no extra logical workspace. Normal combined entries1378=source122+D610+H264+T382; hard2448=128+1024+272+1024. Old immutable log debt281786B is fixed, not four future4MiB growth promises; only new event/peak logs retain existing4MiB ceilings each. Archive/newconfig debt stays inside unchanged H24MiB; no byte cap raised.

Review candidate OUTSIDE owned packet: `task-1b-continuation2-candidate.json`,15860B C=`f6bad9a670773ddbaf2f4787c58615ab42667b3d036961e43b430c8191640b4f`. Helper81332B H=`23fd83143b4bd4f5b16a3172b9e1aa9e1ae2ac269ecdb67c4914dbe39fa2517b`; unfrozenworker55607B W=`914ba05d7208d1c9808784dd510874e2caf50d6654b43487bf5b57be3c5b1785`;29 codepins559465B.16 exact prior raw claims preserve two attempts. Newmetadata scheduling/entry amendments explicitly root-authorized; root review required before freeze and launch.

Proposed exact root-only command (NO grant/runtime yet):
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 480 --rss-mib 700 tests/test_lance_owner_stream.py::test_52mib_finalization_and_cold_replay --basetemp /Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse/.superpowers/sdd/2026-10-25-bounded-lance-layout/task1b-pytest-20261025-6fa6659-continuation2 --noconftest -p no:cacheprovider -x -s`

## Continuation2 exact final freeze

Root verified full flow/29 codepins/16 prior raw claims/source identities; independent9433df89 approved subject to final raw seal. Root authorized ONLY metadata/literal freeze. Exact candidate copied exclusively to fixedconfig, only worker literal filled, distinct external seal/pin exclusively created0400 in existing packet root. No tests/native/source/queue open/runtime. Final binding:

- C `f6bad9a670773ddbaf2f4787c58615ab42667b3d036961e43b430c8191640b4f`
- W `c5631843c206403a54701d30419f9641102311d0ab38c6bc91e84d035f0c6168`
- unchanged H `23fd83143b4bd4f5b16a3172b9e1aa9e1ae2ac269ecdb67c4914dbe39fa2517b`
- S `e309c0a0858f3c2d3142c420da3ffaaec54f5ace45d4abe0f4d8d83976d61a2d`
- pin raw SHA256 `1b81063cdb05732d8e6b890944631ed3aac0bdee00276ffdff03acbb887b8c74`

All16 prior raw hashes and29codepins reverified immediately before freeze; old files preserved. New events/peaks empty,4096B refusal blank,newbasetemp absent. Packet contains exactly root+8files (2old+2newseal/pins,4rawarchives), H264/hard272/T382 unchanged. Root independently verifies and owns sole480s/700MiB launch. Implementer ends turn to avoid process startup during native work. Qualification still INCOMPLETE until actual final gate.

## Continuation2 stopped at actual cold shared deadline — qualification NOT PASS

Root alone launched the frozen continuation2 gate (session20090). Outer470.1s/238.8MiB; pytest469.82s. Combined admitted outer execution59.5+50.4+470.1=580.0s, below600s, with no budget reset. Slot released/no descendants per root. No rerun, continuation, product edit or fixture change authorized by this result. Task2 remains blocked.

Exact actual frontier: all170 prior history ACKs and all18 scheduled index updates+fresh reads succeeded. Original final interval73entries+1owner was genuinely published; native metrics fullowner proof pending74 plus original persisted13621rows, final actual geometry189/13696/171, receipts171. Final publication2.3004s/task180715520B/immediate-host+task215826432B. The intended lost response occurred only AFTER real publication and BEFORE metadata ACK; queue_refuse1070 and real pending-state1071 succeeded. `publication-loss.json`430B SHA `1199596f44ff30f6cb8caeb317df818e12e42666d17c08402980effb42b599a1` binds exact pending intent `fb5a90aaf74540004785b61f1066d34e81185cb28f3a35889b653afc408ab992` and successful original receipt. No committed final ACK was rolled back/repeated. The two later AUDIT owners remain outside history destination; no source EOF/corpus completion claim.

Fresh cold process real queue open1072=0.1143s; same original final source regeneration1073=1.0751s/frame367932B/73entries/1owner; actual inherited import replay1074=2.2323s OK. Its completed full proof streamed13696rows/171receipts,pending0, actual geometry189/13696/171, verified manifest hash `c137bf74258837fafd01c9347b13476b339299e2c0ffadea13ac89660dca644d`, matching frozen original source manifest. Second actual replay1075 was started/admitted according to root resource output (1.3558s), but no successful proof/result/end evidence. Cold shared session5.0033759s, process5.0646s, therefore failed fixed5s acceptance. No bulk_owner lookup, final metadata ACK or final state read occurred; no successful cold/final result file created. Publication remains retained/unacknowledged for real queue semantics, not fabricated progress.

Retained continuation2 events479663B SHA `c5f1d57338e006cca023824b20c3b64fd12f1f01b1a19207cb479b52ecc29d74`; peaks605299B SHA `7c55108308af2b9b5aec1dd3e9254cc4fc3b9aef7449a522a2c218d64fb9c683`; refusal4096B SHA `58366946513abe20e5125f1cc55abeaf935947fdb37bd75f4e967c1db9ed48ad`.850new starts +225retained =1075total.849new end records allOK; last1075 has START only/no END or corresponding peak. New end operations:272imports,138queueopens,137sources,135prepares,135ACKs,15indexupdates,15freshreceipts,1refuse,1state. All original/sealed/prior evidence preserved.

True retained refusal is `{kind:append,reason:'fixture census deadline',stage:1075}`. `FixedSession._run_stage` labels ANY ValueError/OSError from pre/post disk accounting `fixture_disk_guard`; post-supervision `ledger.after(...,until)` enters snapshot whose census rejects expired shared deadline BEFORE recording end/resources. This is an ACCOUNTING DEADLINE refusal, not evidence of bytes/entries/freefloor overshoot. Exact underlying second native result is unavailable in retained event stream because recording did not complete; no claim it finished or did not perform its proof. Worker deadline is a plausible underlying result, not independently established from these files alone.

Last successful measured geometry/disk before expiry: destination81253112logical/82853888allocated,610entries,maxfile1135822B; harness2629390logical/3383296allocated,259entries; source61522214logical/61915136allocated,122entries; temp380entries/36448logical directory bytes/0allocated files. Sampled owned total148152320allocatedB and1371entries,free77343985664B; no unlinked bytes observed in completed first cold replay. Actual retained TMP metadata now root+380children=381entries,379exact directories, second-cold-replay directory exists, owner-read directory absent. These are observations below frozen ceilings, not completed cold qualification, full transient diskpeak or kernel quota. Source/queue unlinked transient peaks remain unmeasured. New completed-stage maximum task180715520B/aggregate228130816B/stage2.3004s; root outer peak separately238.8MiB.

Timing evidence: first3 supervised cold stages0.1143+1.0751+2.2323=3.4217s. Adding reported second native1.3558 gives4.7775s; shared5.0033759 leaves~0.2258759s of host/accounting overhead. Second replay had only~1.36s remaining, versus first completed replay2.2323. Repeating that first observed replay time hypothetically gives5.654s BEFORE owner read, ACK or host overhead. This does not prove an optimized implementation cannot fit5s, but current code did not establish fit and cannot pass by relabeling the accounting exception.

Static cost findings (not separately timed): host exact performs complete named-family census before TMP creation, before supervision and after; worker verifies16prior claims and reparses growing event logs, does complete baseline/post code-hash snapshots, and50ms sampler repeats all source/D/H/T metadata traversal (~1371observed entries/sample), code/prior identity stats and own-FD scan. Hashes correctly omitted from hot sampler; source/harness static traversal remains. Real ordered scan uses32strict rows/batch (~428batches for13696rows), while per record scanner `_bound_row`→codec.validate_entry→CanonicalRecord, then proof `_record`→validate_entry→CanonicalRecord plus another CanonicalRecord:3full canonical validations/member. Pages validate twice; receipt decoded3times. Each repeats checksum/JSON work; no per-component timings establish exact wall contribution. Both actual imports/full original bytes remain mandatory.

Root requests scoped optimization DESIGN only: private frozen strict-decoded row carrier, central decoder preserving every original canonical/page/pointer/receipt check, reusing results only within one iterator/proof. Public raw paths still validate; legacy `_record`/checked_page/decode_receipt semantics retained; no trusted flags, caller bypass, cross-proof cache, SHA state or hash substitution. Ordered scanner and verifier share single decoded canonical/header/receipt; pending rows decode once per independent proof. Source/queue/reader/harness sampler unchanged for first product candidate unless separately justified. Actual bulk_owner is only qualified bounded owner-receipt lookup/decode, NOT a third wholeowner scan. No optimization or tests implemented yet; root must agree scope first.

## Scoped first product optimization candidate — implemented, pure-verified, NOT native-qualified/committed

Root approved first minimal product candidate following independent structural diagnosis eb8878ce. No fixture/helper/worker/config/seal/source/queue/sampler changes. Root owns tracked plan amendment; this report alone records implementation/evidence. Task1/Task2 status unchanged: full cold gate failed and remains incomplete.

Implementation: codec private `_decode_entry` contains exactly the previous complete entry validation and returns its CanonicalRecord/decoded pointer or page header/member; public `validate_entry` always calls it and returns the identical raw row. Legacy `_record`, checked_page and decode_receipt remain unchanged. `_DecodedOwnerRow` is a private frozen read-only six-string Mapping with constructor accepting ONLY raw dict; raw snapshot copied before use, strict shape/types checked, then entry/receipt/legacy reused record fully decoded. Canonical objects are frozen, header/member mappings read-only, membership scope mapping read-only. No caller-supplied decoded fields, `trusted` flag or raw public bypass. Public `verify_owner_rows` independently constructs validated carriers from all raw rows and rejects predecoded carrier as raw authority. Separate private typed iterator entry is used only by ordered store.

Ordered scanner preserves exact projection/order/32strict batches/no-readahead/sentinel/geometry/qowner/source/receipt duplicate/max/marker/live guards; it now builds each strict carrier once, using the same decoded receipt for its existing checks. Ordered verifier reuses single canonical/pointer/page/member/receipt results while retaining original field/text/membership hashes, positional owner/order/pointer/offset checks and complete source exposure/member validation. Pending current-frame raw rows decode once for EACH proof; reused originals independently decode when resolved; one-row lookahead+bounded currentframe/live<=9 only. No cross-call/process cache, proof checkpoint, SHA state, synthetic digest shortcut, native cap or source-byte change. `_bound_row` unchanged for existing append/preflight/fixture uses. Private carrier Mapping preserves frozen fixture observer `row['kind']` / `row['id']` without changing observer/rawsealedfiles. Bulkowner remains ordinary qualified manifest lookup, not a third proof.

TDD evidence:
- `...python scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_owner_stream.py -k decoded --noconftest -x -q` RED: real CanonicalRecord.__post_init__ instrumentation counted9 constructions for3actual records, expected3 per proof. Guard40.0MiB/0.4s. No mocked validation results: wrapper always calls original full constructor validation.
- Same selector GREEN11,39.6MiB/0.4s. Proves3constructions for3records separately in BOTH independent replays (6total), stored vs pendingtail, strict snapshot/rawmutation rejection/no trusted constructor fields, and public/private agreement on valid owner, text checksum, pointer, pagechecksum, membership exposure, owner, receipt checksum and postpublication-content corruption. Public raw entry rejects an already-decoded carrier.
- Added meaningful per-ID decode counts preserving original decoder side effects, then affected regression command `...python scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_owner_stream.py -k 'decoded_pages_and_receipts or test_stream_' --noconftest -x -q` GREEN5,41.2MiB/0.4s. New test checks codec public identical raw-row return and once-per-ID entry/receipt decoding; existing changed-code regressions cover original UTF8/NUL/empty bytes/pendingtails, missing/duplicate/reordered/foreign corruption, actual reused bytes, split receipt/publication boundary. No qualification/artifact/index repeat or native/engine execution.12distinct new+4affected existing cases passed across focused runs, not a full-suite claim.

Scoped4file Ruff/format/diff checks clean. Pure performance obligation established (3→1 canonical validations/member; page2→1/receipt3→1 decode), but NO actual engine/cold5s speed or full acceptance claim. Root reviews before commit/native. Existing frozen C3/H3/W3/raw seals unchanged; current product hashes intentionally differ from old frozen codepins, so no old frozen launch is authorized.

Product/test patch hashes:
- `bulk_exact_codec.py`14386B SHA `268d554f60340ca61e012fd137b839e11495e8f0dc34fc17225f9dd575133a3c`
- `bulk_owner_stream.py`14403B SHA `3aa665ea4048e5143b70bbe769d5f60a1df7df22670bf6e4caf2038166b3f62b`
- `bulk_exact_store.py`40543B SHA `fecb8c50c09a7b5fe7340cc1d40330c456607eb256f19198100f7887621dc959`
- `test_bulk_owner_stream.py`25192B SHA `7fb4416d1d566b82db63fd43114f2622e0226c61063b258982f831cab0a46be4`
- unchanged frozen helper81332B SHA `23fd83143b4bd4f5b16a3172b9e1aa9e1ae2ac269ecdb67c4914dbe39fa2517b`
- unchanged frozen worker55630B SHA `c5631843c206403a54701d30419f9641102311d0ab38c6bc91e84d035f0c6168`

No commit, broad suite, real engine, source DB open, fixture continuation or activation performed. Reader/harness census unchanged as directed.

## Scoped optimization review correction — public error normalization

Independent reviewer found generator construction evaluated iter(rows) outside the existing corruption normalization boundary. Added focused raw-iterable regression with None and raising __iter__. Exact safe20s selector `tests/test_bulk_owner_stream.py -k decoded_public_iterable --noconftest -x -q` RED leaked TypeError forNone,35.8MiB/0.4s. Minimal generator-function deferral now enters raw iteration inside the existing private validation try; no trusted flags, extra cache or materialization. Same exact selector GREEN2,37.4MiB/0.3s. No unchanged tests/native repeated. Scoped Ruff/diff clean.

Final ready-for-review hashes supersede only previous stream/test values: codec14386B `268d554f60340ca61e012fd137b839e11495e8f0dc34fc17225f9dd575133a3c`; stream14469B `6560ab766d06c02f2bfd9a24765cba1c24039f62843ea61a2138c00a3092f9ed`; store40543B `fecb8c50c09a7b5fe7340cc1d40330c456607eb256f19198100f7887621dc959`; puretest25684B `bccaa90fc3dde4f92fc6c0b85818cf242bb237b3d03743404427ce38f37c65a1`.14distinct new+4affected existing pure cases passed across focused runs; no full-suite or native fit claim. Frozen fixture/helper/W/C/seals unchanged. No commit; hold for final root/independent review.

## Approved product milestone and remaining-only cold gate preparation

Root full read and independent5ef388d7 approved single-decode product; local commit `d5ba94e718a994cdb2493b4649eefc12c11fda11` (`perf: decode ordered owner rows once per proof`) contains exactly3product files+`tests/test_bulk_owner_stream.py`. Fixture/plan excluded. No product or broad/native test changes since approved proof. Full cold qualification remains incomplete, Task2 blocked.

Root approved remaining-only gate, with NO history/index rebuild or repeated final publication. Preserve all1075actual starts, including stage1075 UNPAIRED start and raw census-deadline refusal, no invented END/result. New maximum8calls/cumulative1083:real initial queue-state1, then fresh original coordinator's6coldcalls(open,source,two independent actual imports/fullproofs,qualified owner-manifest lookup,real ACK),real final state1. Cold shared5s and transport7s unchanged; tighter outer19s/700MiB after prior rounded580.0s gives599.0s<600s. No optional maintenance reconciliation, automatic retry, cursor seeding or SHA state. Actual ACK170+exact pending171+retained publication-loss receipt must bind original final source; source EOF/two later AUDIT owners still excluded.

Archived raw W3/H3 exclusively0400 BEFORE fixture edits to same existing packet root:worker-run3.py55630B/SHA `c5631843c206403a54701d30419f9641102311d0ab38c6bc91e84d035f0c6168`;helper-run3.py81332B/SHA `23fd83143b4bd4f5b16a3172b9e1aa9e1ae2ac269ecdb67c4914dbe39fa2517b`. Original product blobs preserved by existing git baseline as root directed. All old C/seals/pins/logs/refusals/publication-loss retained unchanged. New fixed names:config `layout-52mib-qualification-cold.json`, seal `final-seal-cold.json`, pin `launch-pin-cold.json`, evidence `events-cold.jsonl`/`peaks-cold.jsonl`/4096B `first-refusal-cold.json`; new basetemp ends `task1b-pytest-20261025-6fa6659-cold`.

Fixed cold-only config rejects other modes;25exact prior raw claims include all3failed attempts and the actual publication-loss receipt. History parser derives old3streams,122paired +103paired +850starts/849ends; final1075 remains unpaired and charged. New stream starts1076, limit1083. Root required after-only native replay without a tenth qualification artifact: existing q171 raw bytes remain188/13621/170→189/13696/171; sealed cold-mode observer asserts actual189/13696/171 immediately upon first geometry inside existing open/writerlock BEFORE lookup/mutation and on subsequent observations. Before/wrong geometry refuses stale. Both imports must still independently stream13696rows/171receipts,pending0,same original ownerhash and aftergeometry. No native invocation/append/proof is simulated by this pure preflight assertion.

Main gate now ONLY reads actual pending state and verifies retained loss, launches unchanged fresh cold worker, checks actual successful cold result, then real final metadata parity. Expected ACK170 ID `4187eef5b0897f2b8f4424823e5b229fcfa447b3d981ff413c73e137aa4c20b6`; pending171 `fb5a90aaf74540004785b61f1066d34e81185cb28f3a35889b653afc408ab992`; original q171/expected receipt/digest/source are unchanged. Missing/different pending/loss/q refuses; no source body/cursor manufactured. `bulk_owner` stays qualified bounded receipt lookup, no third full proof.

Focused engine-free TDD:
`...python scripts/safe_brain_tests.py --timeout 20 tests/test_lance_owner_stream.py -k large_cold_gate --noconftest -x -q`
RED current225schedule rejects1075,51.3MiB/0.4s. GREEN15,50.6MiB/0.5s:3stream/unpaired retention+next1076/1083 cap, each of3prior streams digest/truncated-but-rehashed rejection, pending171 missing/wrong identity/geometry/pin, aftergeometry guard with successful continuation vs rejected before/wrong geometry. Added2focused loss-receipt and ACK170 identity negatives under selector `large_cold_gate and (wrong_loss or wrong_ack)`,GREEN2/50.0MiB/0.4s. No previous green suites or native runs. Scoped Ruff/diff clean. AST comparison confirms original FixedSession/source/queue stage dispatch, actual_tick, census/own_fd_metrics and exact sampler sample/monitor unchanged; only fixed cold admission/binding/orchestration and geometry assertion changed.

Actual metadata-only before preparation:source122entries/61915136allocated; D610/82853888,maxfile1135822; H259 before W3/H3 archive, then261after archives, T381 including379exact dirs. Full existing oldcase files counted. New3evidence files exclusively precharged only after complete metadata census/64KiB reservation. Actual after precharge (including actual current worker and29codepins):H264entries/2777002logical/3436544allocated; T381/0allocatedfiles;free77238534144B;ledger1075derived. This is unsealed preparation census, not launch authority/native proof. No source/queue DB opened.

Precise complete H:original actual259 +archiveW3/H3(2)+newevents/peaks/refusal(3)=264NOW; future fixedconfig1+seal/pin2+freshbasetemp1+2successresultfiles=270 <=unchanged272. Exactly9newattempt slots plus2success outputs, no newpacketdir/builder/cache/docs in case. T381+one owner-read workspace=382; cold replay directories reused with artifacts still charged. Final normal total1384=source122+D610+H270+T382; hard2448 unchanged. Conservative H bytes even reserving FULL new4MiB event+4MiB peak maxima, full8MiB queue headroom double-counted on top of presentH, config rounded20480B,seal/pin32768B,successresults32768B,basetemp4096B:20303872B <25165824B(24MiB). Existing old log debt1366748B remains charged/immutable, not future growth. Whole512MiB,D320MiB,source128,T1024/80MiB,logicalexact380,16MiBpool/64MiBtrackedspill,free2GiB,RSS/read2s/write3s/shared5s all unchanged.

Review candidate OUTSIDE packet `task-1b-cold-candidate.json`18291B C=`d77b87e4adc71266770dc30448cceccb159b1006a060c9be68696dc48418d2dd`. Helper80130B H=`9969a073f330558f836b46a1214b6fb95a798247121ca617b8faa4dd78161153`; unfrozenworker57695B W=`6fb482e1036118d87eabf1db19ea8ceed11b65b8dba4ece48787349af5bedf09`;29pins562118B. Final config/seal/pin/basetemp ABSENT, worker literalNone,newlogs/refusal blank. Candidate/code held for root/independent review; no freeze or runtime.

Exact proposed root-only command after review/freeze/new grant:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 19 --rss-mib 700 tests/test_lance_owner_stream.py::test_52mib_finalization_and_cold_replay --basetemp /Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse/.superpowers/sdd/2026-10-25-bounded-lance-layout/task1b-pytest-20261025-6fa6659-cold --noconftest -p no:cacheprovider -x -s`

No native fit claim; all original cold/source/queue/owner/ACK contracts remain required.

## Remaining-only cold gate exact final freeze

Root full delta/29pins/25prior/sourceidentity checks and independentd507f662 approved final freeze only. Exact C copied exclusively to fixed coldconfig; only worker literal filled; distinct cold seal/pin exclusively0400. No tests, native, source/queue open or other code edit. Final C/W/H/S/pin:

- C `d77b87e4adc71266770dc30448cceccb159b1006a060c9be68696dc48418d2dd`
- W `d92b740b401683f3775bb96429f17630f2eab99fc1970b19c06b251d5d604a89`
- unchanged H `9969a073f330558f836b46a1214b6fb95a798247121ca617b8faa4dd78161153`
- S `3b20063c42a45fa3e59ceea7436a9b3ce20950268e7e7c35989c69b0cf491390`
- pin raw SHA `afd962653bf84abe0fbdf3a729d2f8bb170e278dd168219f9a19e70a6bf63cc7`

All25prior raw claims and29codepins verified unchanged immediately before freeze. New events/peaks empty;4096B refusal blank; newbasetemp absent. H270/T382 bound unchanged. Root independently verifies then owns sole19s/700MiB launch and subsequent separate LIVE native scope. No qualification PASS claim yet. Implementer ends turn so no new agent processes start during native work.

## Measured phase diagnostic and private conditional replay candidate

Root phase session85115 completed ONLY the diagnostic3realcalls1081..1083:actualstate,originalsource regeneration/exact pending equality,ONE real existing import/fullowner proof. Shared3.498177s/outer3.9s204.8MiB; noACK. Full13696original rows/171receipts,pending0,originalhash/after189geometry checked. Result4096B SHA `ecdb78b54cc07164f5be9837c283c973ae3c368a47782d0985b469af37cc5683`; slot SHA `86826b6c4fbc40785c42813e043b42b841ddd8a2c821ee911b3c925f9746f3a5`. Inclusive nativeimport1.006258s,open1.026285s,wholeproof0.752555s,lookup0.116234s; sampler1.160972s OVERLAPS and is neither CPU nor additive. Diagnostic PASS is NOT old cold acceptance. Total outer589.7/600s and1083starts. Old cold-only failure also retained:5starts/4ends at1080,firstproof2.2337s,second censusdeadline/shared5.00221; no elapsed improvement vs2.2323s. All old failed/sealed/diagnostic artifacts frozen/preserved; H272.

Root tracked-plan protocol correction plus independent463d6683 approved a private worker-established persisted outcome. Existing publicimport_batch and v1 coordinator remain compatible. Implemented first candidate ONLY; no native, fixture packet, activation or commit. New154line pure `persisted_replay.py` defines statusok FreshAppend/ExistingVerified closed envelopes, no caller flag. Existing witness binds exact compactreceipt,canonicalgeneration/destination,parent+directoryactual dev/ino,sourcebinding,batchID/digest,domain-separated sorted-ID digest,datasetversion. Input ID iteration bounded512; pathcomponents<=64,privacy/no-symlink/type/deadline checks; bool counts/inodes/version rejected. No witness/cache/SHA state persisted.

Base import adds2legacy result hooks returning exactly original compactreceipt. Private qualified `_ReplayOutcomeStore` overrides only those hooks: existing outcome constructed under existing writer lock AFTER actual existing receipt `_verify_batch`+digest/source+actual expected-ID-set equality; revalidates qualified path and q identities, reads version from same proved dataset. FreshAppend carries no verified witness. `_bound_row`,original-row proof,all read/memory/native guards remain. Newprivate `_fixture_tick_persisted` validates every witness binding and pins subsequent ownerreads to verifiedversion; firstExisting skips duplicate proof, Fresh requires separate reopenedExisting (twoFresh refuse). Originalmanifest/livechecks and existing atomic pending/cursor/v1summaryACK unchanged; witness excluded from ACKsummary. Original `_fixture_tick` still2ordinarycalls/no private outcome. Privateoperation deliberately NOT registered in ordinaryworker/runtime; a future reviewed fixedqualifiedadapter must classify it as3s/write. No frozen fixture/diagnostic file changed.

Focused pureTDD via existing20s safe runner:
- Initialnewprotocol RED missingmodule35.8MiB/.4s→GREEN16 35.5MiB/.3s (strictwitnessbindings/outcomes/versionpinnedcoordinator).
- Workerbranch RED missingprivateclass37.0MiB/.4s→GREEN5 38.7MiB/.3s (fullproof-boundary ordering under mockwriter, source/digest/ID/proof refusal, identicalpubliccompactreceipt,freshno-witness). These test protocol ordering, not nativeIO/fullproof performance.
- MalformedprivateNone RED AttributeError37.8MiB/.3s→GREEN10 31.8MiB/.3s (strictrefusal,loss,pendingchange,generation,stale/wrongownerversion,manifest,live,deadline,realpathreplacement/symlink). NoACK/witnessstorage on refusal.
- Scopednewfile+existinglegacy2call test GREEN32 37.8MiB/.3s after smallowner-version helper extraction for Ruff complexity.
- A focused legacyNone test caught an intermediate publisher-helper sentinel regression that would reachACK; RED35.0MiB/.3s→GREEN5 34.9MiB/.3s after strict non-dict normalization, plus inodebool/countbool/extrawitness cases. Validlegacyreason/phase shapes unchanged.
- Final3focused staging-no-owner-upgrade,boundedID/deadline,ordinaryworker-no-privateop/flag tests GREEN31.6MiB/.3s.
39distinct new+1affected existing cases passed across focused runs; no broad/native repeats. Scoped4file Ruff/format/diff clean. Root/independent review before commit/native. Full newversion/native fit remains UNKNOWN and oldcold gate remains FAILED/Task2 blocked.

Review hashes: `persisted_replay.py`5292B `58bdfa067bdaf86cad83e4b70aaccf6da4263ba1ff84462ef45f96377ad78189`; `bulk_exact_store.py`42379B `50b0bd09a4da4c4bbeb9538798673b5e1608e3f24e9549d4a780b84cbc84db81`; `migration_coordinator.py`10580B `70be1e1c51dc299bf8b6380bc4227a3e4aaf5cfeef421e5bed0160ea20b5c99f`; `test_persisted_replay.py`16963B `af1346e5e72ddf90050a78e0de07e277fc58073f9504578b8484e560a5a54e76`. Frozenprobe648ad7c1/helper9969a073/worker d92b740b unchanged. Newruntime module must be explicitly pinned/charged in future qualification; no envelope chosen/raised here. Nohistory/index replay or new qualification artifacts prepared.

## Approved private protocol milestone and native design pending

Root full read plus independent9a6ae38c approved39new+1legacy pure evidence. Local commit `43e861422b8bfa9edaf7877d859247e5ff79eb9a` (`feat: add private persisted batch verification outcomes`) contains exactly3productfiles+newpuretest; frozenworker/helper/diagnostic and trackedplan excluded. No native qualification or activation yet.

Proposed only (root count/archive approval pending): transfer16unused T entries to H (H288/T1008,whole2448 and all byte/native caps unchanged). CurrentH272+12finalnew entries=284:2rawW4/H4 archives,1C,2seal/pin,3logs/refusal,1freshBASE,2successresults,1newruntime module. Reuse packet dir; frozen diagnostic unchanged. New31codepins include old29updated+newmodule+alreadycharged diagnostic once.37priorclaims verify old25+C4/seal/pin3+W4/H4archives2+failedcold3+diag source/result/slot3+q171; derive1083actual starts including unpaired1075/1080. No prior diagnostic proof becomes witness or source progress.

Two explicit future scopes only: tiny genuineFreshAppend→independentlyspawnedExistingVerified with pinnedowner/originallive checks under same small bounds/profile/shared5s; retained realprestate→same original source+ONEactualcurrentExistingVerified+versionowner/conditionalLIVE+atomicACK→realfinalstate,7calls/1090total,outer<=9s/700 (589.7+9=598.7<600). No170batch/index repeat, ladder, genericfixture framework or capraise. No preparation/instrumentation/runtime under this proposal until root rules.


## Conditional protocol native fixture preparation (not executed)

Private protocol milestone43e861422b8bfa9edaf7877d859247e5ff79eb9a is committed; separate test-only portability ec97ab0a1b6789064b51640d14d525c4076395e3 adds early non-POSIX skip. Root approved H288/T1008 transfer of16 unused temporary entries, whole2448/512MiB and all byte/native caps unchanged. Actual baseline S122/D610/H272/T381;12 final new entries yield H284 (four remaining reserved for transient queue journal/atomic metadata), T382, normal all1398. Old C4 and old cold pytestBASE explicitly remain charged as external harness paths after selecting new config/BASE; diagnostic source is counted once among31 codepins. No old files overwritten or deleted. W4/H4 raw archived0400 before edits;37 prior claims retain all1083 actual starts including unpaired1075/1080. Large candidate/seal final hashes held until separately reviewed pressure-port integration is approved.

Preparation only changed tests/lance_owner_stream_fixture.py and tests/test_lance_owner_stream.py: fixed private outcome write adapter3s192/256; persisted-only remaining gate7new/1090; same real source, one independently verified Existing outcome, version-pinned owner/conditionalLIVE and atomic realACK. Pre-existing proof evidence never becomes witness. Existing q171 bytes/pending/finalsource/frontier remain bound. T1008 enforced in retained census, reservation workspace and sampled open-unlinked count. Public worker dispatch unchanged.

Focused pure checks using `...python scripts/safe_brain_tests.py --timeout20 tests/test_lance_owner_stream.py -k large_persisted_gate --noconftest -x -q`: RED old1075 schedule rejects real1083,51.3MiB/.5s; GREEN20,51.1MiB/.5s. Real publisher-through-actual_tick wrapper regression caught missing remaining delegation (RED AttributeError51.9MiB/.5s); explicit fixture-only forwarding GREEN1,31.0MiB/.3s. Old config/BASE charge regression GREEN1,51.2MiB/.4s. These are engine-free protocol/accounting checks only; no sourceDB/native opens.

Root-approved tiny scope: unique absent `/private/tmp/castle-private-persisted-tiny-20261025-v1`, outer8s/384MiB, one background admission/shared5s, four isolated workers Fresh3s→Existing3s→version-owner2s→originalLIVE-receipt2s each192/256MiB,16MiB pool/64MiB trackedspill,bypass absent. Three original canonical records/nine entries produce exact12physicalrows. Qualification unchanged256rows/16fragments/32versions/128artifacts/8MiB. Entire tmp_path retained tree is inventoried before/after EACH worker, excludes nothing, <=256entries/depth8/80MiB logical and allocated bytes, private regular files/directories/no symlinks. No sampled open-unlinked peak claim for tiny. Sanitized status/reason/native-import/profile/new-stage-resource evidence prints even if postcensus refuses, avoiding stale resource attribution. All tiny artifacts retained under its separate pytestBASE, no large packet entry additions.

Three focused real-filesystem retained-tree negatives (symlink, sparse logical>80MiB,257entries) via `...python scripts/safe_brain_tests.py --timeout20 tests/test_lance_owner_stream.py -k private_tiny_retained_census --noconftest -x -q`: RED missing helper41.1MiB/.3s→GREEN3,51.6MiB/.4s. Scoped Ruff/diff clean. Current unfrozen helper83423B SHA4e35afe61c2c60a28c0b8591484213e554c15d6c5976cdf3f28d0e80719c99de; worker69087B SHAe7477c3a0b4881eca77bfb26911455c8557f1b3599e1433e13302c0470b26c5a. Root/reviewer have these inputs; no final config/pin/seal or native grant yet. Existing historical cold gate remains FAILED; Task2 blocked.


### Revised candidate ready for final review (no freeze/runtime)

Pressure port b3857380a7c2ed693695057514140f05c4f8f2a4 separately approved/committed by its owner. Candidate outside owned packet `task-1b-persisted-candidate.json`21913B SHA `e9e2a918daa8327948e89dc3ca0a966dda72b0212e51613a05fe9375bcd74f12` captures approved current31codepins600671B and37prior claims. Verified each raw pin/claim, eleven additional known historical hashes, original sourceDB+manifest full identities (metadata only); current parser derives1083starts including both unpaired1075/1080. No sourceDB/engine open. Helper4e35afe6/W e7477c3a unchanged; literalNone. Reviewer has actual candidate.

Actual precharge complete-family census H275; existing read reservation authorized64MiB working+64KiBmetadata under same caps before exclusively allocating new empty events/peaks and4096Bblank refusal. After: H278entries/3030528logical/3710976allocated; S122/61915136allocated,D610/82853888allocated,maxnativefile1135822,T381/36544logical,free77124861952. Projected newC1+sealpin2+BASE1+success2→H284/288; one owner workspace→T382/1008. Normal all1398, hard2448. Conservative H debt including fullfuture8MiB event/peak budgets plus full8MiB queueheadroom,config24576,sealpin32768,BASE4096,tworesults32768=20582400<25165824. Sourceactual+D320MiB+T80MiB+H24MiB=506511360<536870912. FourHspares are reserved transientjournal/atomicmetadata. OldC4/BASE remain explicitly charged. All failed originals untouched; newlogs blank; newconfig/seal/pin/largeBASE/tinyBASE absent.

Exact proposed ROOT-ONLY native commands, NOT executed:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 8 --rss-mib 384 tests/test_lance_owner_stream.py::test_private_outcome_fresh_append_then_persisted_reopen --basetemp /private/tmp/castle-private-persisted-tiny-20261025-v1 --noconftest -p no:cacheprovider -x -s`
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 9 --rss-mib 700 tests/test_lance_owner_stream.py::test_52mib_conditional_persisted_replay_and_ack --basetemp /Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse/.superpowers/sdd/2026-10-25-bounded-lance-layout/task1b-pytest-20261025-6fa6659-persisted --noconftest -p no:cacheprovider -x -s`

All shared/stage/profile/deadline limits unchanged. Large7actualcalls1084..1090, total priorouter589.7+9<=598.7<600. Tiny outer8/384 separately bound to fixed tinytest. Root/independent candidate approval then exact final freeze then separate root launch required; no native PASS claim.


### Exact final persisted freeze (metadata only)

Root authorized exact approved e9e2a918 candidate after independent6585420b review. Copied21913rawbytes exclusively0400 to fixed persisted configuration; worker changed ONLY literalNone to C; created distinct0400 persisted seal/pin. No tests/native/sourceDB opens. Full chain load,31codepins,37prior raw claims,1083retained starts/1090ceiling and metadata census verified. Literal/C `e9e2a918daa8327948e89dc3ca0a966dda72b0212e51613a05fe9375bcd74f12`; W69149B `7fce99ff844230988845997a024c21b642717bb0b821ced29de92d12a21aa275`; unchanged H83423B `4e35afe61c2c60a28c0b8591484213e554c15d6c5976cdf3f28d0e80719c99de`; S728B `f1afb84d064a261add06487f3bce1f2423b8f2c3a21371571f92ea3d1596e7b9`; pin212B `36bf80a9a3de3db1455f4cd36adaacdff202d61390d1e904541d01b2d8a44d72`.

Final actual H281/3743744allocated/3053507logical; futureBASE+2success→H284. S122/D610/T381 unchanged; projectedT382/normal1398, capsH288/T1008/whole2448 unchanged. Free77123153920B. Old37claims byte-identical; newlogs empty/refusal4096blank; both unique tiny/large basetemps absent. Agent ends turn now; root independently preflights then owns tiny8s/384 only, evaluates before any retained9s/700 grant. Native protocol fit remains unqualified until root evidence.


## Final native qualification evidence and metadata-only closeout

Root executed frozen inputs ONLY: tiny session1582 PASS and retained session24843 PASS. Agent ran NO native/retest. Tiny persisted receipt `persisted-tiny-native-result.json`2248B SHA `9ac00643c090609106bbfd2581a91d1676c0be18430bbbe64af2b42ae1ac3259`: four actual isolated native stages FreshAppend→ExistingVerified→version1owner→originalLIVE receipt, same files afterinitialappend. Shared3.206756667s<5, outer3.6s/204MiB<8s/384MiB, each3swrite/2sread192/256MiB;16MiBpool/64MiBtrackedspill,bypassabsent,nativeimportedallfour. Entire tiny retainedtree final12entries/40960allocated/30251logical, pre/post eachstage; open-unlinked/transient disk peaks UNMEASURED. Native sampled RSS is not guaranteed instantaneous peak. No hostnativeimports.

Retained cold actual artifact `evidence/cold-result-e9e2a918daa8.json`2248B SHA `5f805d72c3db9adbf842b9615df366f239635ab66003216f5805dfda22852234`: shared4.213875707995612s, sameoriginalsource54525952bytes/6656members/text641df0406585127d51c04579543c53ac2dae29bdbf30ddc69f75de58647ed615; oneactual privateExistingVerified proof streamsALL13696originalrows/171batchreceipts,pending0,sameownerhashc137bf74258837fafd01c9347b13476b339299e2c0ffadea13ac89660dca644d,actualafter189/13696/171. Exact calls queueopen/source/import_batch_outcome/bulk_owner/atomicqueueACK onceeach, all inside unchangedshared5s. LargehistoricalLIVE=None; tinyseparatecasequalifiesoriginalLIVE. Oneproof is the root-reviewed protocol correction, not a claim the historical two-proof gate passed. Sampled native disk allocated148520960B/1395entries,openunlinkedobserved0,temp36544B; configuredpool16MiB/trackedspill64MiB/bypassabsent. These are reservations+sampledtripwires, not kernelFSquota/unobservedpeakguarantees.

Final actual artifact `evidence/final-result-e9e2a918daa8.json`6761B SHA `f9a8732d435e9d6c781ce69d6388685218acfcd82055e4f1ee471b35a65fe9f4`: realfreshpostACKqueuependingNone,lastACK171intentfb5a90aaf74540004785b61f1066d34e81185cb28f3a35889b653afc408ab992,oneownerreference/onehistoricaloccurrence/6656members/noaudit/live/gaps/orphans,semantic_pending1,stateactive,coverageindexed-only. ActualqueueACKsummary5a203e84f8b5723f78b2fd258e1c3223ce430b656e66a1e2306de8c10a0606e6. Originalstaging/completedcursor advanced to ownerboundary; sourceEOFfalse (later2AUDITowners excluded), no corpuscompletionclaim. Root retained tool session24843 outer5.1s/254.1MiB<9s/700MiB, cumulative589.7+5.1=594.8<600. Outer safe-wrapper transport/temp isolation separate from owned512MiB family.

Seven actualSTART+END pairs1084..1090 and7peaks validated; allendstatusok,reasonNone,preallocatedrefusalstill4096blank. Events3801B SHA `d1378402e8293ffa648d9024fd5e0a1dd0edcae79472b9d02be83801a51253be`; peaks5003B SHA `5668d65f83578405b7e29863232dc902a09b3e5d05fa60655928367ac122d40f`. Retained realprior1083 includes unpaired1075/1080 forevercharged; no resetting/repeating170intervals/index rebuild. Oldfailedlogs/rawC/W/H/seals/pins/diagnostic remain unchanged.

Metadata-only postqualification frozenchain verification:31codepins+37priorclaims unchanged, originalsourceDB+manifestfullidentitiesunchanged; no sourceDB/nativeimport. ActualS122/61915136allocated,D610/82853888allocated,maxfile1135822,H284/3768320allocated/3071448logical,T382/0fileallocated/36640logical,normalall1398;capsS128/D1024/H288/T1008/whole2448,whole512MiB andallRSS/time/bytecapsunchanged. Free77114945536B. Finalresult recordsH283 beforewritingitself; thisindependentpostwritecensus correctlyincludes finalresult asH284. FourHspares reservedqueuejournal/atomicmetadata. No artifact deletion or hiding old debt.

Scoped Ruff on the four exact proposed test/harness files PASSED; gitdiffcheckclean. No repeatedpure/nativegreens. Proposed commit ONLY:
- `tests/test_lance_owner_stream.py`69149B SHA `7fce99ff844230988845997a024c21b642717bb0b821ced29de92d12a21aa275`
- `tests/lance_owner_stream_fixture.py`83423B SHA `4e35afe61c2c60a28c0b8591484213e554c15d6c5976cdf3f28d0e80719c99de`
- frozen diagnostic `tests/lance_phase_cost_probe.py`15803B SHA `648ad7c16c80de46d9138ab227b0ae7e176b50d0d456f711b4430ac2480de520`
- `tests/test_lance_phase_cost_probe.py`2781B SHA `d05d391dbafb4817c4ed8990f6e7514ef58b7695a882364695d138d01a8b8126`

Trackedplan isroot-owned and excluded; privateSDD/evidence excluded. Rootfinalreview/commitauthorizationpending; noTask2/install/activation/whole-memoryclaim.

Historical superseded checkpoint retained for audit (the currentstatus at top controls):
Superseded status: **TASK1a APPROVED; TASK1b PUBLICATION PERSISTED BUT COLD5s QUALIFICATION FAILED — TASK1 INCOMPLETE**. Actual1075 total starts;170 metadata ACKs,18 index/read maintenance pairs and genuine final owner publication persisted at189versions/13696rows/171fragments. Fresh cold same-source regeneration and first actual complete original-byte replay succeeded; second replay reached an accounting census deadline at shared5.0033759s, so no owner lookup/final ACK and no PASS. Frozen/prior evidence preserved. Single-decode optimization independently approved and committed atd5ba94e; remaining-only old cold gate also FAILED; phase-only diagnostic3calls/oneproof PASS,noACK. Privateconditional replay candidate nowpure-verified39new+1legacy cases, awaiting review/native qualification. No native cap change. Static diagnosis and exact retained hashes/frontier in `task-1b-run1-preemption-report.md`. Task2 remains blocked.


## Accepted Task1 milestone commit

Root + independent final outcome review SHA `32051f5d52ad56a4c018fa56b098e91ad4e021023d33ed3469cb72dadb89a7ae` accepted limited Task1 scope and authorized exact4-filecommit. Local commit `2cce8e53b479f8c4c330e8fa027aebdd451c6905` (`test: qualify bounded persisted owner recovery`) contains ONLY tests/test_lance_owner_stream.py,tests/lance_owner_stream_fixture.py,tests/lance_phase_cost_probe.py,tests/test_lance_phase_cost_probe.py. No new codechange,retest/native,push/install/activation. Postcommit compared exactgitblobs to workingbytes and approvedfullhashes7fce99ff844230988845997a024c21b642717bb0b821ced29de92d12a21aa275 /4e35afe61c2c60a28c0b8591484213e554c15d6c5976cdf3f28d0e80719c99de /648ad7c16c80de46d9138ab227b0ae7e176b50d0d456f711b4430ac2480de520 /d05d391dbafb4817c4ed8990f6e7514ef58b7695a882364695d138d01a8b8126; all match. Indexempty; ONLYroot-ownedtrackedplan remainsdirty. PrivateSDD/actualevidence excluded. Root will startTask2 separately; no wholememory/fullcorpusclaim.
