# Task 3b2b — inactive pinned native archive source export

Frozen implementation brief, 2026-10-25. Base253227ffa10dcd35a3b737ef19cd7e04a9913845 is clean; reviewed Task3b1 (48107d5) and Task3b2a (253227f) are complete. Read AGENTS.md and this brief. Consume their existing interfaces; do not rerun their passing tests except a focused regression for code you change.

## Root rulings and evidence

The guarded native scalar inventory in `native-scalar-inventory/results.md` exhausted35,746 rows after the registered, still-unreconciled cursor. Maximum text1,681B, no text>8KiB; guardian1.5132s/172,392,448B task/195,035,136B aggregate. This justifies implementing the existing projected-window reader first. It does not prove prior import coverage, metadata sizes, giant historical finalization or production readiness. Do not implement a retained Arrow-buffer/giant-scalar framework in this task. Existing giant SQLite occurrences remain preserved and handled separately; oversized native-source work must refuse without moving the cursor.

The descriptor/cursor shape below is fixed. Preserve the original archive/snapshot/version/raw-cursor identities. Permit exactly two explicit trusted source formats in shared migration validation: existing SQLite and this native source. Preserve existing `sqlite-migration-v1` identities and bytes; use a separately domain-bound `native-migration-v1` registration for native jobs. No registry/plugin/caller-selected executable. Shared coordinator verification logic may take an internal fixed source selection; do not duplicate the prepare/import/replay/ACK algorithm. Native owner classification is history, never AUDIT/live.

Approve a narrow `header_or_none` primitive while preserving legacy `header()` behavior, worker-only direct reuse of the named read-only history helpers, and extraction of a focused shared historical evidence formatter where necessary. Do not instantiate SQLite Source to format a native row. Do not open SQLite in the native source worker. An import of a read-only formatting module is not permission for its write operations.

Keep all original refusal normalization, runtime admission and source-before/after validation. Snapshot-root identity must be validated as a directory (do not wrongly require regular-file link count1); all pinned files retain private/no-link/read-only file rules. Use existing supported identity representation with strict type-specific checking. No production descriptor, source reseal or snapshot creation is authorized.

The fixed source stage is2s at512/640MiB within the same absolute5s session; exactly64 text projections at≤8192 characters each and≤2MiB aggregate returned UTF8 per slice, counting repeated passes. Whole-source summaries remain ordinary streaming hashes, not serialized SHA state. Bound resource refusal is honest incomplete state. Unqualified larger native rows cannot silently disappear.

Testing is synthetic only, supervised explicit files through `scripts/safe_brain_tests.py --noconftest`. Start with failing pure contract/targeted behavior evidence, implement, then focused covering tests. Do not run a whole legacy suite. All native/SQLite fixtures and storage tests require root's exclusive native slot; request it with the concrete first test scope before runtime. Pure host/codec tests and static checks are allowed immediately. Never raise caps, blindly retry a resource refusal, run an unguarded fixture import, or turn a diagnostic into production qualification. Record exact command/output/metrics/refusals in `task-3b2b-report.md`. Commit reviewed-scope product/tests when verified; no push/install/services/production mutation. Do not spawn subagents; root supplies independent review.

## Scope and fixed boundary

Add one inactive **read-only native source adapter** exporting exact remaining pinned rows into existing bulk-v1 entries/finalizations. No native continuation job, live source scan, converter call, snapshot creation, production permit, coordinator framework, cutover, model work or vector reuse. The old converter stays stopped; retain originals, protected snapshots and SQLite shards/stages unchanged.

Use `SemanticSession`'s existing shared admission, absolute **5 s total tick**, preemption/pressure and descendant cleanup. Add one fixed native-source stage/executable, separate from fixed SQLite source selection; it is never a caller-selected command/provider/budget. Source profile is the existing **512 MiB task/640 MiB aggregate** history profile. This is distinct from destination exact **192/256 MiB, read2/write3 s**, queue/SQLite **128/192 MiB**. Do not call `run_history` or reuse its ordinary `HISTORY_DEADLINE=10` dispatch; it currently passes `HISTORY_DEADLINE-2` to its supervisor and dispatches converter operations. No existing deadline/profile is widened. The fixed native source stage cap is **2 s**, always shortened by the session's remaining time; 5 s remains the whole-tick ceiling.

Reuse existing guardian supervision and history model/network/child guards, with a fixed strict source-only request shape and full session-chain/admission validation. Do not dispatch through `memory_history_worker.main/history_operation`. The source executable may import native readers and read-only history helpers; host remains free of SQLite/Lance/Arrow/model imports. Source and destination workers run sequentially. Verify source artifact inventory unchanged; no write-capable dataset open, index/optimization, SQLite connection, catalog/job update or child process is an adapter operation.

**No actual historical continuation before Task 3c** reconciles all SQLite shards/attempts/gaps/repairs/pending stages and canonical owners, establishes the exact pinned start cursor/source binding, and supplies snapshot/capacity/index-scale qualification. Eight supplied shards do not mean eight archives; old summary counts and a provisional remaining-row subtraction never select a cursor. Synthetic fixture start cursors demonstrate protocol behavior only.

## Concrete source contract into 3b2a

Provide focused pure `native_export_codec.py` and guarded `native_source_export.py/native_source_worker.py`, plus the one fixed session stage. No registry, generic provider layer or second supervisor. Use these names, with a focused pure runtime helper only if needed to share request/result validation.

Registered descriptor, bounded metadata only:

```
{format:"pinned-native-export-v1", store_id,
 snapshot_path, snapshot_identity,
 manifest_path, manifest_identity, manifest_hash,
 archive_id, original_snapshot_id, version, start_cursor}
```

`store_id` identifies this registered source export, not a new archive identity. `original_snapshot_id` is the historical identity input, which must not be replaced by the adapter's new registration/hash/path. Manifest binds completed immutable protected native snapshot, original archive/snapshot/version, exact schema and sorted file/content identities, fragment/deletion metadata, original source lineage and declared start boundary. Content hashes/registration are supplied by qualified snapshot creation or disposable fixture sealing, not fabricated by adapter code. `source_binding = sha256(_json(["pinned-native-export-v1","registered-source",descriptor]))`; validate exact descriptor/path/identity/hash/integer shapes and registered manifest agreement. Detailed manifest is read in the guarded worker, not embedded in host frames or copied into coordination bodies. No arbitrary caller path or mtime-only certification.

Use the **same outer cursor field set** as 3b1, with native format discriminator and unchanged `packing="bulk-v1-ascii-1"`:

```
{format,packing,source_binding,store_id,phase,key,owner,entry,
 field,member_ordinal,field_byte_offset,field_char_offset}
```

For native export `phase` is `history` or `done`. For `history`, use `key=[_json(raw_cursor)]`, where `raw_cursor` is the original deletion-aware pre-row position `{fragment,offset,row_address?}`. With `owner=null`, it is the position from which the next row is selected. With an active owner, retain that same pre-row key and `owner=<original occurrence identity>`; entry/field/member/byte/character offsets describe deterministic staged replay inside that row. After emitting the row's finalization, set `owner=null`, reset unused positions, and set key to the exact original **following** raw cursor. `done` has `key=null/owner=null` and zero unused positions. Validate all ranges, canonical embedded JSON, exact key width, owner/phase/offset relationships and binding; booleans are not integer offsets. Do not add `row_address` to an old cursor that omitted it: its original JSON representation also determines historical `_cursor_key`.

`export_slice(descriptor,cursor)` returns exactly the 3b1/3b2a result envelope:

```
{status,reason,source_binding,cursor_before,cursor_after,entries,finalizations,
 counts,phase,phase_complete,complete,coverage,frame_bytes}
```

Optional resource/refused-operation/field diagnostics follow existing source behavior. At most one historical owner per slice. Finalization increments `historical_occurrences/members` only in export counts; live/AUDIT/gap/pending counters stay zero for this row-only adapter. `phase_complete` means finalization emitted, never destination confirmation. `complete` means a proven no-next-row scan exhaustion, never all historical coverage. Keep coverage indexed-only/pending reconciliation; no source-side count closes gaps.

3b2a consumes this result through **one explicit native fixture entry/stage and validator pair**, sharing its existing interval preparation/import/replay/ACK logic. Its current SQLite descriptor/cursor validation must not be fed a disguised native descriptor. Add only the narrow native validation/call binding; no format-to-executable registry or caller selector. The outer phase/key carries explicit history classification, not a guess from zero members. Body-free intent stores exact native before/after cursors and body digest. Same source input/packing must regenerate byte-identical intervals. Existing 3b2a ephemeral-output reuse, one pending interval and current-tick restart verification remain mandatory.

## Snapshot and physical-row validation

Validate private owned no-link ancestors/root, exact registered snapshot/manifest identity, single-link read-only files and exact inventory before and after every source slice, including refusals when opened. Reject extra/missing/replaced/relinked/writable artifacts, changed schema/version/deletion metadata and manifest mismatch. `_validate_snapshot(job)` is reusable read-only structural checking when a validated registration is mapped to its exact required job view (`snapshot/inventory`); it checks stat inventory/read-only files, **not cryptographic content**. Do not claim it independently proves a copied snapshot. `_validate_original(job)` is also read-only but walks the original source; do not invoke it against a live original during adapter export. Qualified registration/3c provides original lineage and immutable snapshot proof.

Both validation walkers lack their own per-step deadline checkpoints. Preserve their checks; supervise their cost within the fixed slice and measure it. If a registered bounded inventory cannot be validated within limits, report a gate rather than silently checking only selected files or widening limits. No new snapshot/hash-spool framework. Hash original field/text bytes with ordinary streaming SHA256; interrupted passes restart.

Open only the registered immutable snapshot at its exact Lance version. Preserve current `NativeProjectedRow` cache limits, decode validation, IO buffer and scanner settings: one row/strict batch, no batch/fragment readahead, explicit fragment selection, deletion-aware offset, `_rowaddr`, no scalar-index shortcut. Header/text/statistics must select the **same physical address**; address is nonnegative<2^63 and `address >> 32 == fragment`. Moving within the same fragment must increase address and advance deletion-aware offset by exactly one. Moving to a later fragment starts offset1 after skipping empty/deleted fragments. Physical row address is not the live ordinal and is never a destination row address.

Current `NativeProjectedRow.header()` reports `corrupt` if every remaining fragment has no row. Do not interpret arbitrary `corrupt` as EOF. Add a **narrow shared read-only header-or-none primitive** (or equivalently bounded next-row probe) that distinguishes genuine exhaustion while preserving `header()`'s current caller contract. It must handle an empty dataset, final fragment and wholly deleted fragments without a full table count/text scan. EOF with no body uses 3b2a's scan-exhaustion ACK; no empty batch/fake occurrence.

## Original identities, fields and streaming

Derive exactly:

```
following = {fragment:header.fragment,offset:header.offset,row_address:header.row_address}
occurrence = sha256(_json([archive_id,original_snapshot_id,version,
                          header.fragment,header.row_address]))
chunk_id = "memory:" + sha256(_json([occurrence,character_start]))
cursor_key = sha256(_json(original_pre_row_cursor))
```

Owner key is original `occurrence`; bulk owner ID uses existing `owner_id(occurrence,source_binding)`, `metadata_id=occurrence`, `live=null`. Snapshot/destination/registration IDs do not replace original identity components. Repeated and empty drawer aliases remain exact in columns/descriptor with their occurrence relation; alias equality never collapses occurrences. Same text in separate physical rows remains separate evidence.

Keep `metadata_json` exactly as stored, including whitespace/escapes/key order. Columns are the original history `_json` encoding of all original non-text/non-vector fields except `metadata_json`, including alias and hoisted fields. This matches both ordinary `_commit_row` and projected `_stage_header` semantics. Preserve all scalar/nested value types admitted by existing `_json`; invalid metadata JSON/non-object metadata or non-JSON column values refuse, never stringify/drop. Full workspace/wing/room candidates and absent/null/empty/nonstring values live in exact paged scopes. Authority remains columns, then metadata, then bounded caller; null falls through, a present empty/invalid non-null value does not become an invented lower-precedence scope.

Reconstruct public caller via `_stage_caller`: original archive/version/metadata ID, existing workspace/wing/room order,≤64-byte caller scope values and≤512-byte caller ceiling. Use `MemoryStore._provenance` plus `CanonicalRecord` for the exact original envelope, including legacy `sqlite-fts5-utf8-v1`; destination/source-adapter location never enters exposure-bearing provenance. Full long scopes stay outside caller. Reuse reviewed 3b1's historical scope/descriptor evidence construction where genuinely shareable, extracting a focused shared formatter if required; do not copy a competing formatter or instantiate a SQLite `Source` merely to format raw rows. Descriptor must retain original alias, raw before/following cursor, cursor key, occurrence, archive/snapshot/version/fragment/address and original whole/metadata/columns summaries.

`NativeProjectedRow.header()` currently materializes all non-text/non-vector fields and `_stage_header` constructs complete columns JSON before enforcing metadata/columns≤1 MiB, alias≤4096 bytes and native batch limits. Output paging does not prove those allocations are small. Initially preserve these **existing bounded source acceptance checks** under512/640 MiB; stream admitted strings/encoded columns into≤8192-byte bulk pages with independent character/byte offsets. Avoid extra joined copies. Do not claim per-column lazy decoding, unbounded metadata acceptance or whole-field-free source decoding that this reader does not implement. Oversized metadata/native decode refusal is explicit qualification/unsupported work, with unchanged cursor; a later measured need for per-column projection requires separate review, not silent data loss.

For text, stream `NativeProjectedRow.page(start,limit)` windows into the exact `_chunks` algorithm across window boundaries. Carry≤8192 UTF8 bytes; a page boundary never flushes a partial canonical chunk. `character_start/end` count Python codepoints, byte lengths count exact UTF8, including supplementary Unicode/NUL/combining sequences. The fixed projection window is≤8192 characters, split further for bounded UTF8/actual ASCII transport. Each export slice permits at most64 text projection calls and at most2 MiB decoded UTF8 returned across those calls, including every replay/summary/emission pass. Exceeding either returns an explicit non-progress refusal; neither is a source-completeness claim. The existing maximum131072-character page is not an output frame size or an obligation to use it. Preserve native decoder guards: projected windows may still allocate the full scalar internally.

Compute whole text SHA256 over ordered original UTF8 and compare native expected hash/bytes/characters. Compute exact field summaries and ordered member payload SHA256 with existing `bulk_exact_codec.page/validate_entry/entry_batches/validate_batch/validate_owner`; member binds full scopes summaries as in3a. Do not call in-memory `prepare_owner`, accumulate all chunk IDs/text, join occurrence text, hash page hashes or serialize SHA state. Regenerate earlier bounded pages to reconstruct summaries on replay; if repeated full passes cannot finish under fixed limits, report measured qualification failure with no progress. Source whole-hash success does not qualify destination3 s finalization.

Empty text is a real occurrence with zero members, empty SHA256 and descriptor/metadata/columns/scopes; no empty canonical chunk. Large text emits staged entries over deterministic bounded batches, and finalization only after exact original summaries verify. 3a final marker grants atomic visibility; source does not write destination staging or advance a publication checkpoint. Source `cursor_after` is export progress only. 3b2a advances verified staging cursor after durable batch verification, completed-owner frontier only after final owner verification/ACK, and retains one pending interval across losses. No source cursor, phase/count or native scan EOF independently advances destination progress.

## Safe helper reuse

`_stage_header(header,job,cursor)` validates values/cursors, parses metadata, formats columns and returns `(following,occurrence,metadata,columns)`; `_stage_caller(job,staged)` formats alias/caller; `_chunks`, `_cursor_key`, `_valid_repair_cursor` perform formatting/validation. They are **read-only/no-publication helpers** and can be called directly inside the admitted source worker with minimal validated job/staged dictionaries. Their module imports SQLite/history storage, so do not import it into host. Merely importing the module does not invoke converter writes, but imported helpers are not a capability barrier: the fixed source entry must never dispatch converter operations or open a SQLite connection. Share pure helpers only if host actually needs them; do not duplicate logic.

Never call `_load_job/_root` to discover production work from a palace, or `_schema`, `_commit_row`, `_stage_begin/_stage_page/_stage_hash/_stage_publish`, `_index/_publish`, public `history_operation`, `prepare/index/repair`. Even `_stage_hash` reads SQLite staging and is the wrong source for this raw adapter; reuse its ordinary streaming validation pattern only. `NativeProjectedRow.bind_header` is read-only but accepts a full metadata-bearing header: regenerate it from the pinned row each worker slice, not a body stored in coordination. Persist only hashes/reference cursors.

## Narrow synthetic qualification only

Proposed focused files: `tests/test_native_export_codec.py`, `tests/test_native_source_export.py`, plus a narrow source-stage/adapter integration case in runtime/coordinator tests. Native fixture creation/deletion must occur only in separately supervised disposable fixture workers; seal/close/fsync and register actual manifests. Host never imports Lance/Arrow/SQLite/models or constructs a whole large occurrence. No real corpus reads or production registration.

Required cases:

1. Pure exact descriptor/cursor binding, wrong version/start/packing/booleans/active-owner positions; same immutable interval regenerates identical actual ASCII-bounded bytes and body digest. Bad snapshot/manifest replacement, extra file, symlink/hardlink/writable file and pre/post mutation refuse with unchanged cursor.
2. Two physical fragments with deletions, a wholly deleted/empty fragment, resumed offset/address and final exhaustion. Confirm old `_scan_rows` identity/address/cursor parity on small admitted rows, without using its whole-text path for large rows. Empty dataset EOF must not mask genuine corruption.
3. Repeated/empty aliases, identical text at distinct physical addresses, real zero-length text and original missing/null/empty/type-conflicting long scopes; compare legacy helper public provenance/IDs/exposure and exact metadata/columns/scope/descriptor pages. Non-vector unusual field names must not be lost through SQL projection assumptions.
4. Unicode/NUL/combining/supplementary characters spanning both projection and8192-byte chunk boundaries. Stream-compare starts/text/hashes/IDs with existing `_chunks` on small bounded fixtures; use incremental large fixture construction/hash manifests for a multi-batch row, never one host string. Preserve exact metadata whitespace and columns encoding.
5. Actual3a stage-only visibility, final owner/metadata descriptor, duplicate/replay/canonical reuse and lost final acknowledgement through the frozen3b2a path. Verify source artifact inventory unchanged and source export cursor never masquerades as committed frontier. No partial source stage is counted as a completed occurrence.
6. Header/decode/summary/frame/pressure/admission/RSS/deadline/preemption refusals and source-before/after tick interruption; keep exact pending interval and no continuation skip. Measure cold native export + checked replay + owner ACK under shared5 s. Report any repeatable non-finishing source/destination verification gate; no profile/page/frame increase or partial-proof framework.

At implementation time use explicit clean-host test files through `scripts/safe_brain_tests.py --noconftest`, scoped timeouts and existing supervision. Do not run for this draft. Report actual task/aggregate RSS, source/frame/page bounds, elapsed/cold tick cost, all refusals and source artifact parity. A small native fixture does not qualify full52 MiB native decode/destination finalization, all-shard reconciliation, maintenance scale or production continuation. No model tests/vector qualification needed.



## Approved implementation-time manifest clarification (root, 2026-10-25)

The detailed native manifest is exactly `{format,state,store_id,snapshot_identity,original,start_cursor,schema,fragments,inventory,lineage}`. `original` is exactly `{archive_id,snapshot_id,version}`. `schema` is only `{hash,bytes}` for Arrow's serialized schema; serialized bytes are at most64 KiB. Each sorted inventory item is exactly `{path,snapshot_identity,content_hash}`; at most4096 files and4096 sorted fragments. Fragment evidence is the exact version's native fragment metadata, including deletion metadata, checked before/after export. Serialized manifest is at most512 KiB. Strict type-specific snapshot-directory versus immutable-file identity rules apply. Lineage is bounded JSON supplied by fixture sealing/Task3c; it never proves reconciled source coverage. `state=complete` certifies only the registered snapshot state. New disposable fixture workers are capped at5s512/640 MiB; native source remains2s within the5s SemanticSession. No further native/storage fixtures after root reassigns the exclusive slot.
