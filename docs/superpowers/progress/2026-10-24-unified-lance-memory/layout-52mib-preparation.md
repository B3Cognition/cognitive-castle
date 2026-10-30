# 52MiB fixture and physical layout preparation

This agent's work was preparation only. The inventory v2/proof bundles under root review were not changed or run. This agent performed no SQLite/native/model module import, engine/query, fixture build, source-body read, destination write, product edit, original-source rebaseline, converter, service or native-slot use. Standard-library analytical geometry is derived from the reviewed synthetic fixture builder/codec, not a measurement of a current stored corpus. Root subsequently reported two guarded stage0 privacy refusals; their scope and the now-frozen run boundary are recorded below.

## Existing retained fixture: location gap

The existing builder is `tests/test_sqlite_source_export.py:332–525`; test `test_representative_export_qualification_respects_limits` uses `tmp_path/source`, init +26 separately supervised256-chunk/2MiB appends +seal. Retained tests use the explicit `CASTLE_TEST_RETAINED_SOURCE` directory and never discover sources automatically.

Targeted prior artifacts inspected: `task-3b1-report.md`, fix1/review notes, relevant progress lines and `/tmp/castle-task3b1-{scale,plan,keysort-green}.log`. Logs record metrics and binding **`6c9e076ba4a78897d3edf61eb0e91f3c3b380d43c793558bf01331f56077aa99`**, but the fixture helper deliberately filtered descriptor/path fields. No current registered manifest/SQLite content/schema/file identity hash can be recovered from them. Current `CASTLE_TEST_RETAINED_SOURCE` is unset. The pytest-derived user root `/var/folders/sv/07gg7rcs7gg7rl7s19f3xpsc0000gn/T/pytest-of-ladislavbihari` had9 numbered run roots and no `test_representative_export*` candidate. The alternate known `/private/tmp/pytest-of-ladislavbihari` root was absent. No broad `/tmp`, palace, shell-history or home scan was made, and no candidate SQLite file/body was read. This is an unresolved retention/path gap, **not proof that the fixture was deleted**.

Earlier accepted evidence remains:6656 members/54525952 original text bytes and whole-text SHA parity, member stream0.4776s; one corrected export interval1.3759s/446571B ASCII with48 entries and no finalization. It does not prove complete export, last-interval regeneration or52MiB destination finalization.

## Exact synthetic geometry and conservative serialization bound

Builder facts: one historical occurrence `b636feec5f2c19356abef9c3bab039086893e4570d1041980dedf55b23df6aa9`,6656 consecutive8192B ASCII chunks, caller JSON117B, metadata`{}`2B and original columns31B. Expected synthetic whole-text SHA256 derived from the builder's repeated seed is **`641df0406585127d51c04579543c53ac2dae29bdbf30ddc69f75de58647ed615`**; it is not a newly observed storage hash. There are no live receipts, capture mappings or published staged rows. The fixture additionally has one alias relation and one indexed original attempt, exported as two separate zero-member AUDIT owners.

The shared formatter stores caller evidence as a JSON **string** in scope pages, independently of the canonical provenance object. Its fixed ASCII scope header is398B, each member scope item255B, commas6655B and suffix2B:

`scope_bytes = 398 +6656*255 +6655 +2 =1704335`; therefore **209 scope pages** at8192B/page. Metadata, columns and descriptor each occupy one page. The registered manifest size M is unknown until resealing; its fixed builder shape plus seven bounded identity integers/links1 gives M<=635B. Descriptor size is `M+673`, at most1308B, safely one page. Hash/ID hex values change contents, not these byte widths. Original file paths are not copied into the descriptor text; source binding is a64-character hash.

For the historical owner:

`entry_rows = canonical_records +membership_pages +field_pages =6656 +6656 +(1+1+209+1) =13524`.

Actual reviewed `entry_batches` geometry is constrained by256 entries,384KiB decoded values and480KiB ASCII body minus the existing16KiB packing reserve. Standard-library size modeling of both descriptor bounds yields **171 packed entry intervals**. Last packet has73 entries/355830 decoded bytes, leaving37386B for the1108B owner manifest; final records and owner fit together. No empty/artificial finalization interval is assumed. Maximum modeled entry-packet decoded size393158B and ASCII size445331B. The proposed numerical pass must verify the actual sealed instance and reject a disagreement.

| Fresh historical-owner physical row kind | Rows |
|---|---:|
| Canonical bulk records |6656|
| Membership pages |6656|
| Metadata/columns/scopes/descriptor pages |212|
| Published owner receipt row |1|
| Batch receipt rows |171|
| **Historical owner total** |**13696**|

One alias AUDIT owner and one attempt AUDIT owner each add one descriptor page, one owner row and one batch receipt: **six further rows/two intervals**, yielding **13702 rows/173 batches** for the full synthetic SQLite fixture. AUDIT rows do not add canonical text or historical occurrences. There is no original live-receipt row for this fixture.

The six-string schema (`id,kind,text,provenance,digest,receipt`) counts every UTF8 value, including page headers, canonical provenance, pointer receipts, owner fields and proof receipts. Formula:

`values = sum(entry six-string bytes) +sum(owner receipt row bytes) +sum(batch receipt row bytes)`.

For any receipt row, fixed ID/kind/digest cost is148B plus canonical JSON manifest length. Every batch proof includes all entry IDs/hashes and final owner ID/hash; there are13525 proof pairs for the historical owner. Worst valid128-byte batch keys may require768 JSON bytes when escaped, so the receipt upper below covers them rather than assuming short hex IDs.

| Serialized UTF8 values, current bulk-v1 geometry | Bytes |
|---|---:|
| Historical entry rows, upper (all fields included) |65931021|
| Historical owner row |1256|
| Historical batch receipt rows, conservative key upper |2144263|
| **Historical owner values total, upper** |**68076540**|
| Alias/attempt AUDIT values, upper |4095 /4158|
| **Full fixture values total, upper** |**68084793**|

The companion `layout-52mib-analytical-summary.json` records these formulas/results. A six-column32-bit Arrow string offset-buffer model adds `24*(rows+writes)`: full fixture333000B, giving **68417793B for values+offsets**. This excludes alignment/validity/native allocation, Lance compression/encoding/footer/version/transaction/index metadata and scratch space. It is **not a physical-disk upper or production permit**. Repeated ASCII seed text is unusually compressible; no resulting disk ratio may be applied to the real corpus. Record reuse in an existing destination can reduce new physical records, while receipts/proofs and retained versions still cost space; the table assumes a fresh destination.

Even this one owner exceeds the current1024-row unindexed-tail bound, despite its13702-row full-fixture total being below16384-row maintenance bound. The count is not authorization to append all intervals without a qualified owner/index lifecycle. Retained old versions, maintenance replacements, indexes and temp spill require separate actual filesystem measurements. No new production partition/profile/cap has been selected.

## Fresh fixed recreation bundle for root review

Root authorized **preparing** a new unique private run, preserving all originals/fixtures. Bundle:

`layout52-recreation-20261025-37b6436d/`

At preparation freeze it contained scripts/manifests/static evidence only. Root's two later stage0 privacy refusals also occurred before source/temp/peak creation, according to root's report; no source was built. Worker AST-loads exactly the reviewed `scale_fixture` function, not pytest or its broader fixture dispatcher. Dependencies were compared with reviewed commit162a94f2e9fed205768fc3b6fa46d26bdeef900a and hash-frozen. Runtime drift refuses instead of adopting the sole product writer's later unreviewed changes. No unreviewed product dependency is required by this prepared path.

Original unexecuted31-stage v1 is preserved under its `archive-unexecuted-v1/`, manifest `6c07060a4e2939dad1980561b2399835d7d586bad46ad5a68133647b74024c57`. The disk-only revision is shown in `disk-accounting-delta.diff`.

| Current file | Lines | SHA256 |
|---|---:|---|
| `host.py` |99| `2f978e93a1e45b895279eec6d8e9372e38d1c20f63380569bb4585a37e02330c` |
| `worker.py` |490| `990856a1cb6e7cd31df0d783f66077642554ff2db80798ac333a2a00c4bcf30e` |
| `manifest.json`,18 entries | | `cb473939c750cc0ed071eaff967049f40609164b465854d6db0cdcd99dfabdb5` |

The fixed schedule has **31 maximum calls**; no retry or alternative query/path:

1. Stage0 initializes a new private source. Stages1–26 append exactly256 chunks/2097152B each at fixed offsets. Stage27 seals using existing whole-text/schema/file hashing and fsync. All28 fixture stages retain128MiB task/192MiB aggregate/32MiB SQLite heap and <=5s supervision. MemoryStore's existing3s write progress handler remains unchanged.
2. Stage28 opens only the completed sealed private fixture through reviewed Source, validates file/manifest/content/schema identities, and returns three bounded body-free owner manifests/source binding. It verifies6656/54525952 and the expected synthetic text hash. Fixed source2s supervision and Source's internal1.65s work stop remain.
3. Stage29 regenerates actual entry streams, checks field/member/text hashes/counts against those manifests, and counts actual six-string/batch/proof/owner rows without Lance access or persisted bodies. Packed buffers/lookahead remain bounded (the Python loop can retain a preceding packet while the codec produces the next). Fixed work limits are13526 entries and68084793 cumulative modeled value bytes, inherited384/480/512KiB envelopes and unchanged1.65/2s source limits. It returns the **observed first entry ordinal/position of the final historical packed batch** as the validated original source cursor, not a cursor guessed from counts.
4. Stage30 calls reviewed `export_slice` once at that actual final-batch-before cursor under the same2s/128–192 source guard. Output is counters/cursor/hash metadata only. A successful replay must emit the canonical owner's final records+owner together. `_export_owner` regenerates/skips from entry zero, so this can falsify worst-interval fit **before any171 destination appends**. No artificial finalization cursor or product shortcut is used. If stage29 cannot supply the cursor, the schedule stops and this stage remains unattempted.

The numerical or last-replay stages may legitimately refuse under the existing source clock; neither first-slice evidence nor a5s fixture build stage widens that guard. Any refusal stops immediately and leaves the new fixture/artifacts retained, charged and explicitly incomplete. No destination is opened, no append/index/semantic work occurs, and the native slot is unused.

## Fixed disposable retained+temp accounting

Root's fixed diagnostic envelope is **512MiB each for total run logical/allocated bytes**,128 entries, depth4, bounded128 worker-fd slots and minimum2GiB free. Accounting includes current scripts, archived v1, source, private sibling `RUN/tmp`, peak files, failed named artifacts and regular worker fds not already visible in the run walk. It never recurses an external root or scans another process. Unlinked native temp fds are conservatively charged by fstat while open.

Before each build write, reserve **`2*current_main_file_bytes+128MiB` additional space** on top of all retained logical/allocated bytes and require free space >=2GiB+reservation. The geometry-specific allowance conservatively covers rollback of existing pages, simultaneous sort runs for52MiB text plus keys/record overhead, and new pages/index/metadata growth. Unexpected bloat refuses; no physical-size prediction is silently substituted for actual counters. Read stages reserve64KiB for their fixed body-free accounting record/directory growth. MemoryStore's1GiB internal envelope and one-third page quota are unchanged; this stricter disposable envelope does not alter them. No known fixed-function conflict has been established, but actual fit is unqualified.

Before SQLite import/heap initialization, the guarded worker admits the stage, creates private `RUN/tmp` and sets SQLITE_TMPDIR/TMPDIR/TMP/TEMP there. The sibling does not alter sealed SOURCE contents. A private SQLite Connection subclass preserves the original fixed time callback and instruction frequency, additionally sampling run/fd accounting and rechecking that time-only callback after monitoring. A monitoring failure/time/resource conflict refuses rather than removing checks or changing budgets.

Each stage preallocates a private fixed4096B peak record in RUN. Sampled high-water logical/allocated/unlinked-temp/entry/fd/free-space evidence is updated in place without growing a feedback log. Observed unlinked peaks remain after temp closure and the host retrieves this record even after worker refusal/termination; unreadable evidence refuses. All failed artifacts remain charged; there is no deletion routine. This is **conservative admission plus sampled monitoring, not a kernel hard disk quota or an instantaneous peak guarantee**. Runtime checks and a normal-pressure authorized run are still required.

## Remaining verification

Static AST parsing/compilation, fixed schedule/guard/entry/disk geometry and dependency hashes passed; no executable module was imported by this agent. A future cause-corrected root-authorized run must retain raw bounded result, per-stage guardian RSS/time/frame/disk peak evidence, source registration/file/schema/content hashes, exact observed packing/cursor and cleanup evidence. Full on-disk Lance expansion/index/temp/retained-generation capacity, native owner finalization and throughput remain separate supervised qualifications. Missing old fixture registration is not repaired by this preparation or by analytical hashes.

## Root-reported launch refusals and final freeze

Root reported two stage0 privacy refusals, both before SQLite/source/temp/peak creation. First, output redirection created a0644 result artifact. Second, this agent added `archive-unexecuted-v1/README.md` after communicating frozen code hashes; that metadata file briefly had0644 before chmod and raced root's all-private preflight. The guards correctly refused the nonprivate entries. This was a preparation/runtime coordination error; it is not evidence of source2s fit, layout success or a need to weaken privacy/capacity guards. Exact raw result filenames/metrics are retained by root and were not inspected or invented here.

Root instructed a complete RUN freeze and will preserve both results, chmod generated artifacts0600 and independently perform a fail-fast whole-run preflight before any further cause-corrected launch. **RUN is now frozen to this agent: no further files, README, chmod, reads or stats inside `layout52-recreation-20261025-37b6436d`.** Only this outer report was updated after that instruction. No launch or runtime is authorized to this agent. All actual source registration and numerical/last-interval qualification evidence remains pending.

## Later root-admitted prefix and fixed continuation preparation

Root subsequently reported stages0–5 successful and stage6 `background_preempted` before `disk-stage-06.json`/DISK/source-engine access. Root verified cleanup. On root's specific read-only authorization, this agent inspected the bounded admitted-result JSON and pinned the partial main file with engine-free SHA256 reads, requiring identical file identities before/after hashing. No SQLite open/query or mutation occurred.

`results-admitted.json` SHA256 is `f29a0094402e210a951c61880386a7f5cabe50c3ee013d9f4c971832b779b378`. Its fixed seven-result sequence is0–5 `ok`, offsets0/2097152/4194304/6291456/8388608/10485760, then6 `unavailable/background_preempted`. All18 original manifest hashes matched. Journal/WAL/SHM, stage06 peak record and sealed source manifest were absent at that inspection.

Partial source main identity: device16777233/inode293882577,11841536 physical file bytes,mtime_ns=ctime_ns1792884310133489656,mode33152 (0600),uid501,one link. SHA256: **`92a6de72c8696b5f18279b0f8579c6cc27a32146fe4f41046d019076c5bb3111`**. The10MiB text/1280 chunks are operation-history expectations, not an independent current SQL count. Existing append has no pre-count assertion: it commits its256 fixed inserts and reports arithmetic next_offset. Root accepted the narrow six-success/no-stage06/unchanged-file authority. Seal checks every offset and52MiB total/hash but prints6656 as a constant; actual6656 member count is independently checked by stage28 owner_summary. No full-fixture readiness follows from append arithmetic.

The separate outer sibling **`layout52-continuation-20261025/`** contains only a165-line fixed host,preflight pins,manifest andstatic checks. It invokes the **unchanged original worker** for stages6–30 only: maximum25 new calls,6 prior successes, completion only at31 combined successful stages. Same5s fixture/2s source,128/192MiB,32MiB heap, shared admission/preemption and original disk guard. First refusal stops; no retry, source recreation, new SQL probe or worker change. Preflight rechecks the exact original result/hash/sequence,18 original file hashes, required absences and current source identity/hash; source is rechecked under shared admission before stage6. Output is a new0600 `results-continuation.json` in the sibling, never inside original RUN.

Frozen continuation manifest: **`23ca64b6f392e66c27c25d6ed0be2efac68d0177dc9500a9d0dfafb3ccca64c9`**. Host: `fc4ab672fe96c2c35a79cdafaf51fd96bbb8b68623d899a2841d6c4944013d09`. Preflight: `8287bc09464e2c6620e606f84a654688d28a1b4369ce5bd6225118b6792cfa90`. Directory0700/all four preparation files explicitly0600. Root reviewed and accepted the complete host/manifest/static checks. **Both original RUN and continuation directory are now fully frozen to this agent, including reads/stats; no later additions or changes.** This agent has not launched the continuation; root owns independent final preflight and any runtime grant. Further updates from this agent remain outside those directories.
