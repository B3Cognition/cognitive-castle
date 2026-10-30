# Task 3 design notes — 2026-10-24

Read-only preparation; only this report was written. Read AGENTS.md, Task 3/global constraints, semantic-preservation spec and the three supplied audits. Inspected relevant Python source without importing it. No git mutations, native/model/SQLite operations, tests, service changes or source movement. Task 2c remains active; its interfaces below are observations, not instructions to rewrite its working implementation.

## Recommended decomposition

Four dependency-ordered implementation briefs are sufficient: **3a bulk exact format/publication**, **3b protected source adapters**, **3c capacity and reconciliation**, **3d semantic bulk scheduling/publication**. Capacity admission is a prerequisite for any real write, although its reconciliation depends on 3a/3b formats. Keep ordinary route replacement and activation in Tasks 4/5. All proposed APIs are private worker operations, never caller-selected paths/budgets/model profiles.

### 3a. Add a bulk protocol beside the small exact API

Reuse `CanonicalRecord`, `prepare_remember`, the writer lock, supervision checks and atomic append/replay principle in `lance_exact_store.py`. Preserve current `remember` receipts. Do not enlarge its eight-source import or 512 KiB JSON frame to carry a migration. Current `_find` scans separately per ID with scalar indexing disabled; `_paths` recursively inspects every artifact; receipt verification reconstructs at most nine records. These are explicit fixture limits, not a 500k-record algorithm.

Use a versioned destination schema in a new inactive generation. Retain original record ID/text/public provenance unchanged; add typed common fields `kind,id,owner_id,ordinal,field,source_id,start,end,payload_hash`, plus bounded payload and projected authoritative scope fields. Internal IDs have separate prefixes. A concrete row contract:

| Kind | Durable payload/relationship |
| --- | --- |
| `record` | Existing `memory:` identity, exact ≤8 KiB text, unchanged canonical provenance. Never inject destination/backend identifiers into exposure-bearing provenance. |
| `descriptor_page` | Occurrence ID, field (`metadata` or `columns`) and page ordinal; exact UTF-8 slice, byte and character bounds, page hash. Preserve original metadata JSON whitespace/key order; preserve the already stored columns JSON exactly. |
| `member` | `(owner_id,ordinal,canonical_id,source_hash,exposure_hash,char_start,char_end)`. Owner can be an occurrence, bulk batch or original request receipt. Page membership; never store a giant IDs array. |
| `scope` | Canonical ID plus full authoritative workspace/wing/room, attribution/state, source key/generation/time and record offsets as applicable. Preserve absence/conflict explicitly; do not replace absent values with invented scopes or truncate long values. |
| `occurrence` | Existing occurrence identity and alias; archive/snapshot/version/fragment/physical address; original cursor and following cursor; whole-text hash/bytes/characters; metadata/columns hash/length/page counts; membership count/digest; scope binding. This is the final visibility marker. |
| `batch_receipt` | Batch key/digest, source snapshot binding, exact cursor interval, counts by row kind, bytes, membership digest and final occurrence IDs via paged membership. A distinct `staged` receipt proves pieces were copied but never claims occurrence publication. |
| `request_receipt` | Original live namespace/key/digest and ordered membership, preserving retry semantics after migration. Bulk receipts alone cannot replace these existing idempotency keys. |

Keep all canonical descriptor/scope/membership content in Lance. SQLite coordination may contain references, counters, attempt states and reservations, never a text/metadata fallback.

Suggested interfaces:

```
import_batch(batch_id, source_binding, cursor_start, cursor_end,
             expected_counts, expected_digest, spool_id)
receipt_page(batch_id, after_ordinal, limit)
occurrence_members(occurrence_id, after_ordinal, limit)
finalize_occurrence(occurrence_id, expected_binding, verification_id)
page(source_id, field="text|metadata|columns", offset, limit, expected_hash)
```

`spool_id` resolves only within a worker-owned private spool registry. Its manifest binds schema, file identity, exact byte length/hash and per-frame decoded-byte/row limits; reject symlinks, hardlinks, replacement and trailing data. Stream bounded frames into `RecordBatchReader`; cap total decoded payload per append as well as individual frames. Coalesce many ordinary complete occurrences into one append containing their final markers and one receipt. Proposed 1 MiB/256-row frames and 16 MiB commits from the scale audit are **experiments, not qualified limits**; choose actual bounds from fixed-profile evidence.

Oversized occurrences append immutable staged records/pages/members over multiple bounded commits. Verify contiguous exact offsets, IDs, hashes, lengths and membership before a final small append publishes the occurrence marker and receipt atomically. Every hydration, page, lexical and vector eligibility path must require that marker at the pinned Lance version; raw presence of a staged `record` is insufficient. Existing visible records reused by another batch remain visible through their original committed membership. The final append must reference verified immutable pieces, not copy all pieces again. Cursor advances only after the canonical final receipt is recovered and verified; lost acknowledgement is safe.

Verification must itself resume: `_stage_hash` currently starts a whole-occurrence SHA-256 pass again each attempt. A digest-of-page-hashes is not the original whole-text SHA-256. Either qualify bounded whole-occurrence verification or add a separately tested versioned resumable SHA-256 state (block state, byte count, pending bytes, source/version and verification-position binding). Bind successful verification to immutable page/membership digests; never trust an unattested expected hash from an incoming spool. This is a real oversized-row blocker, not a reason to enlarge deadlines.

Scalable uniqueness requires (1) bounded duplicate detection inside each incoming commit, (2) batched projected ID checks against an explicitly maintained BTREE, (3) comparison/hydration of matching payloads only, and (4) serialized append. BTREE is not a uniqueness constraint. Detect duplicate existing IDs, not merely first-match existence. Bounded unindexed append tails must participate in checks; refuse/defer when tail work exceeds the qualified bound. Build/maintain indexes only in supervised maintenance, never reads. Replace recursive per-operation tree walks with a reviewed bounded artifact-validation boundary plus resumable full inventory; retain security checks on every artifact opened. Do not silently drop those checks for speed.

### 3b. Export protected SQLite, then continue the pinned native source

Use one adapter envelope: `source_binding`, `occurrence/request descriptor`, `bounded records/pages/members/scopes`, `cursor_before/after`, and expected hashes/counts. Both adapters feed 3a. Neither calls the old converter or changes its pause marker.

For SQLite, obtain a supervised consistent protected snapshot, including proper WAL handling; copying only a changing database file is insufficient. Export with keyset/ordinal paging and bounded BLOB slices. Reuse `MemoryStore._source/_provenance` to reconstruct the **existing public** source envelope, then validate with `CanonicalRecord`. Copy original `receipts` namespace/key/digest/order. Export both ordinary occurrence `ids` membership and oversized `history_occurrence_chunks`; `ids=[]` does not mean no chunks. Preserve aliases, exact metadata/columns strings and hashes, gap/repair/attempt identities, and any unpublished stage as pending rather than committed.

Copy authoritative `capture_chunk_scopes` and generation-attribution facts, including conflicts/first-workspace offsets. Historical precedence is columns, then metadata, then bounded caller fields; do not derive full scopes solely from the 512-byte caller envelope. Task 4 can consume these canonical mappings without SQLite rowid assumptions. A private live-export rowid watermark is acceptable only as a snapshot/delta cursor bound to its original SQLite source, never as canonical membership. Keep live capture running; retain snapshot high-water marks and reconcile later deltas under separate source generations before cutover.

For unconverted history, reuse `_validate_snapshot`, original-identity validation, cursor validation, `_stage_header`, `_chunks`, `_stage_caller`, and `NativeProjectedRow.header/page` from `memory_history.py`/`history_projection.py`. Extract pure formatting where needed; do not call `_commit_row`, `_stage_publish`, `_index`, or `_publish`, which write SQLite/catalog state. Occurrence remains SHA-256 of `[archive_id,snapshot_id,version,fragment,row_address]`; chunk remains `memory:` + SHA-256 of `[occurrence,character_start]`. A repeated drawer alias is never a unique occurrence. Continue from a cursor proven by migrated canonical attempts/receipts, not blindly from the old summary count.

Native projected headers currently materialize all non-text/non-vector columns; projected text still may allocate the original oversized scalar internally. Qualify that path under native **192/256 MiB, read 2 s/write 3 s** before actual source movement. If metadata decoding exceeds it, add per-column bounded projection or expose an explicit unsupported/refused occurrence; do not lose metadata or silently count it covered. These remain diagnostics, not changes to production dispatch.

Count interpretation is resolved: **eight SQLite stores/shards represent one archive**, not eight source archives. The capacity spec and schema diagnostic bind 519,641 pinned rows to archive `5404eb9a0f3fea7ee3c2e3c9a273592ba67575ec3914942aebfe0e5aa5a0dd0f`, version 26613. Root independently read only catalog/job JSON during this audit: catalog generation 500 has eight stores with that same archive ID and summed `indexed_rows=483895`; job agrees on archive/version and references `~/.castle/palace/lancedb/castle_drawers.lance`. This is parent-supplied metadata evidence, not a database recount here. Inventory distinct `(archive_id,snapshot_id,version)` and store-to-source relationships separately; never multiply the source count by eight. The 35,746-row remainder remains provisional until identities/attempts reconcile.

### 3c. Capacity and independent reconciliation

Reuse the concepts of `history_storage.admit_history_write` and `memory_history._run_inventory_proof`: bounded metadata work, aggregate retained-byte accounting, headroom, persisted phase/cursor, independent source count, receipt checks and sorted identity reconciliation. Their SQLite allowlist and fixed 2 GiB per-store transaction reservation cannot describe Lance physical output.

Add `reserve(operation_id,generation,operation_kind,expected_growth,envelope_binding)` and `reconcile_step(manifest_id,phase,cursor)` in coordination. Reserve before spool/output/index creation; charge retained SQLite/originals/snapshots separately from destination fragments, manifests, indices, staging, spools, orphan output and temporary maintenance overlap. Do not count referenced immutable pieces twice as both staged and published. Reconcile an interrupted reservation against durable canonical receipts and actual retained artifacts before release. Existing free-headroom/aggregate policy remains binding; no inferred permission to increase it or delete rollback files. Measure an append/maintenance envelope; a soft Lance file-size limit is not a disk reservation.

Persist a compact verification manifest with source identities/count bindings, destination versions, phase positions, counts and ordered digest roots. Stream-merge sorted occurrence/canonical-ID inventories in bounded passes rather than loading ID sets. Verify each occurrence has one matching physical source identity, final marker, descriptor hash/pages and exact contiguous members; distinguish reused identical records from occurrence multiplicity. Include empty-text historical rows (valid zero-chunk occurrences), repaired gaps and stages. Detect extras as well as omissions.

Report separate counters for pinned rows, migrated/published occurrences, canonical chunks, descriptors/pages, aliases, live observed/processed bytes, pending stages, changed/unsupported/refused work, semantic planned/published/nonsemantic units and index coverage. Unknown unit totals remain unknown until tokenization plans are committed. Exact completion cannot imply semantic completion. Final reconciliation must prove all distinct source inventories sum to the declared corpus, gaps/changes are resolved, live deltas have a known boundary, and every required semantic unit is acknowledged against committed exact evidence/profile.

### 3d. Coalesce semantic work without changing evidence identities

Reuse Task 2's `semantic_windows.make_unit/input_binding`, source exposure hash, `prepare_publication`, `_hydrate`, vector receipt validation, queue acknowledgement, new/history scheduling and lost-response recovery. Current groups contain ≤8 sources and pages ≤32 windows; `index_one` starts multiple sequential cold workers per page. Vector publication still scans each ID and appends one page/receipt. Increasing only the source count or page constant changes codec/recovery assumptions across several files and is not the first step.

Add a trusted bulk outbox containing paged references to committed 3a memberships. Derive ordinary bounded groups lazily and idempotently; persist the outbox expansion cursor only after group registration. Never materialize every semantic reference in an exact receipt. Current `semantic_intents` allows only one/two groups for `remember`; preserve it and add a migration-specific outbox contract. Current scope validator requires nonempty workspace/wing/room with fixed lengths; real absent/conflicting/long scopes require an explicit representation/eligibility decision before bulk indexing, not synthesized or truncated values.

First coalesce several validated existing publication pages into **one** Lance vector append carrying their individual durable receipts. Queue acknowledges each page only after verifying that append; crash recovery can reuse existing receipt keys without inference. Use byte-capped private spool descriptors for persisted token/vector intermediate pages if compute must span leases; account for them in capacity and keep them out of canonical SQLite. Revalidate source/hash/profile/scope before final publication. Native writes remain 3 s; tokenizer/inference stages remain sequential **512/640 MiB under one shared 5 s lease**, with admission/yield and no resident model. Coalescing is not permission to stretch leases or overlap stages.

Root's Task 2c measurements: eight-fact ticks 3.65–4.13 s; exact remembers 2.09–2.83 s; 64-window groups can commit before deadline and acknowledge next tick without reinference; queries 2.05–2.59 s before KG/reranking. These establish recovery and reveal overhead, not bulk throughput. At an optimistic eight one-window sources per tick, 519,641 rows alone imply roughly 66–75 hours before extra windows/retries/exact migration; this arithmetic is a warning, not a projection for the real corpus.

Measure bytes/chunks/windows distribution, duplicate **exact token input** rate, cold-start time, units per acknowledged second, commits/fragments per million units, actual storage growth and new-fact lag under backlog. If duplication is significant, optional compute reuse may key a verified vector by pinned profile plus complete encoded model inputs (including masks/types), while publishing a separate ID/hash/offset/scope-bound unit and receipt for every source occurrence. Never collapse canonical identities, infer compatibility from equal text alone, or treat original unknown-profile vectors as reusable. Historical profile evidence remains unproven; preserve those vectors and plan verified re-embedding.

## Narrow evidence before actual movement

1. Review/freeze 3a's versioned schema, visibility predicate, spool trust boundary, indexed duplicate handling and resumable whole-text verification. Pure fixtures cover legacy IDs/provenance/exposure, exact metadata bytes, large/absent/conflicting scopes and both membership forms.
2. Under the fixed supervised profiles, exercise byte-capped append/reopen/replay, duplicate/conflict detection, kill before/after receipt, oversized stage/finalization, metadata pages and late-ID reads at representative cardinality/fragment count. Measure manifests, retained/temp bytes, peaks and deadlines. Separately qualify BTREE maintenance and bounded unindexed tails; no query-time builds.
3. Synthetic SQLite/native adapters must produce identical occurrence IDs, descriptors, scope and receipts for equivalent pinned inputs, including deleted physical rows, repeated aliases, empty text and long Unicode/NUL content. No native/SQLite tests in the host; explicit files through the safe runner.
4. Obtain the authoritative source/store manifest and consistent protected SQLite inventory, then publish a capacity/throughput estimate with uncertainty and an independently resumable reconciliation recipe. Verify actual projected decode and spool sizes under guards before starting a bulk mover. Retain originals/rollback sources and the stopped converter.

Principal blockers are bounded whole-occurrence hash verification, scalar-index maintenance/tail cost, schema/visibility integration with Task 4, real source decode bounds, scope representation, and the combined retained-disk/throughput budget. None authorizes a larger resource profile or production cutover.

## Appendix: minimal Task 3a ruling after scope review

**This appendix narrows the initial implementation recommendation above.** Start with the existing six-string Arrow schema and bounded JSON frame. Do not build the seven-kind typed framework, spool registry or custom resumable SHA implementation now. They are possible later responses to measured limitations, not prerequisites. Leave original `remember`, eight-source `import_sources`, receipts and Task 2 callers compatible.

### Evidence correcting the hash recommendation

Read only bounded summary fields from `~/.castle/backups/durable-memory-20261024/relocation/unified-52mb-stage-resume-proof.json`; no corpus text/IDs were emitted. It reports `status=ok`, **51,784,095 bytes**, 51,784,075 characters, **6,322 chunks**, resume at character 262,144, `full_hash_verified=true`, two verified edge pages, and zero gaps. Its 416 slices include both `ok` and `unavailable`; maximum reported elapsed time is 1.5004 s, task RSS 359,399,424 bytes and aggregate RSS 387,989,504 bytes. Those maxima cover the slices, not an isolated hash-stage measurement. This proves an existing large staged conversion with ordinary full hashing succeeded. It does **not** qualify Lance hashing under 192/256 MiB, but it removes grounds for introducing custom SHA state speculatively.

Reuse `_stage_hash`'s ordinary `hashlib.sha256()` streaming validation pattern and restart an interrupted pass. Test the Lance implementation first. Only a measured repeated bounded whole-hash failure warrants reconsidering verification design; a custom SHA codec would then require a separate review.

### Smallest durable extension

Keep columns `id,kind,text,provenance,digest,receipt`, schema metadata and all existing `record`/`receipt` encodings. Add three strictly validated private kinds, with a `format: bulk-v1` payload discriminator:

| New kind | Six-column use |
| --- | --- |
| `bulk_record` | Original canonical ID/text/provenance; `digest` is the final owner-marker key; `receipt` holds only a bounded membership-page ID/entry-ordinal pointer. Owner is a historical occurrence or original live request, not a physical batch. |
| `bulk_page` | Deterministic internal ID; `text` contains a bounded exact metadata/columns slice or bounded membership/scope JSON; empty provenance; digest of exact payload; `receipt` binds owner, field, ordinal, offsets and lengths. |
| `bulk_receipt` | Deterministic internal ID; empty text/provenance; digest of canonical manifest; `receipt` is a bounded versioned manifest. Distinguish `stage_batch`, `published_owner` and `committed_batch` explicitly. Only `published_owner` grants visibility. |

Use existing `receipt:<sha256>` internal ID syntax with domain-separated hash inputs for bulk owners/pages/batches; do not alter old request-key derivation. Canonical `memory:` IDs remain unchanged. Membership pages list original IDs, exact hashes/offsets and scope-page references; owner manifests reference page counts and rolling membership digest, not giant arrays. Metadata/columns pages preserve exact UTF-8 bytes and character offsets. Owner manifests preserve original occurrence/alias/cursors/whole-text hash and descriptor lengths/hashes. Live owners also preserve original request namespace/key/digest and ordered membership. Full scopes live in bounded pages outside canonical provenance; absence/conflict remains explicit. This is encoding within the existing dataset, not a second metadata store.

For new `bulk_record` reads, require its `published_owner` marker and verified membership at the pinned dataset version before returning it; otherwise return not found/pending. Its membership pointer permits bounded point validation without scanning the owner's complete member list. `_record` validates its canonical content, while a shared visibility helper gates hydration/page callers. Existing `record` rows remain readable unchanged. Reused existing records are compared by canonical content, not physical row-kind equality, and never rewritten or hidden. A reused staged bulk record may finalize only its already bound owner. Hash/ID/scope conflicts fail closed. Task 2 already hydrates through exact `read_sources`; retain that boundary so it cannot index invisible staged records.

Keep `read_sources(ids)` and text `page(...)` signatures and receipt semantics. Attach the established top-level metadata descriptor only for committed owners; expose a small separate private metadata-page/membership-page operation. `CanonicalRecord.from_source` and exposure hashing continue to use only original ID/text/provenance. Scope preservation is in 3a; scalable policy-prefiltered scope search remains an explicit Task 4 gate, rather than pretending opaque JSON pages are already a query index.

For migrated live requests, append the **original-format `receipt` row at its original namespace/key-derived ID** together with the final owner marker. Its existing bounded IDs array is appropriate for a single original remember request. Teach existing receipt verification to validate referenced bulk-record visibility too; do not require old callers to discover a new receipt namespace or accept a bulk receipt in place of their original result.

### Initial bulk operation and bounds

Add **one** private `import_batch(batch_id, source_binding, entries, finalizations)` operation plus paged receipt lookup. `entries` are validated records/pages; `finalizations` request owner publication after complete verification. Keep the existing 512 KiB encoded request ceiling. An initial experiment can allow up to 256 entries subject to the frame and decoded-byte ceilings; **256 is a fixture candidate, not a qualified setting**. Many tiny sources then share one native startup/append instead of eight-source commits. Large 8 KiB chunks naturally hit the byte ceiling earlier. Return compact counts/digest/receipt ID, never all imported IDs.

A batch may stage pieces or finalize several small complete owners. Atomically append its new rows, any validated final owner manifests, and one batch receipt using the existing bounded Arrow-table write. A large occurrence spans many requests; the final request streams its stored pages/chunks, verifies contiguous IDs/offsets/whole hashes and appends only the final marker. Lost response replays the same digest-bound batch receipt. A changed batch key conflicts. Checkpoints advance only for final owner receipts. No full occurrence copy at finalization; no native work in the host.

No spool is needed to improve tiny-source commits within 512 KiB. If measured throughput still requires multi-megabyte commits, add a private spool protocol later with its own safety/capacity evidence. Likewise add typed scope/ordinal columns only when a measured bounded query/iteration requirement cannot be met by deterministic page IDs and an explicit derived index; preserve this codec during any later schema migration.

### Scalability required now, not deferred

Batch existence checks by validated IDs with bounded projected results; reject duplicate incoming or existing IDs, compare existing canonical records, and preserve the writer lock. Use an explicitly prepared BTREE on `id` with bounded unindexed-tail checks. A single result per ID is insufficient duplicate detection. Indexed validation must cover records, page IDs and receipts. Maintenance is a separate supervised operation, never a read side effect; defer/refuse when the qualified unindexed-tail allowance is exceeded. Existing per-ID full scans are not an acceptable bulk implementation.

Qualify late-ID lookup and append over many commits before increasing fixture cardinality. The existing recursive path validation may remain initially to preserve safety, but if its measured cost exceeds deadlines, a reviewed bounded artifact-validation boundary becomes a gate before real movement. Do not replace it opportunistically inside the format patch. This keeps the first change reviewable without claiming 500k readiness.

### Immediate fixtures and later gates

Immediate fixtures: unchanged Task 1/2 reads/remember replay; one append with more than eight tiny sources; byte-cap refusal; identical batch replay/conflict; identical-record reuse; duplicate IDs; incomplete owner invisible; interrupted staging/final-marker/ack recovery; exact metadata whitespace, Unicode/NUL and long/full/absent scopes; membership ordering; empty-text occurrence; old request-receipt fidelity. Test that vector hydration rejects staged sources. Then separately supervise representative staged whole hashing and indexed lookup/tail cases under unchanged native profiles.

Before actual source movement: qualify capacity reservation, protected adapters, real projected decode, full metadata/scope inventory, fragment/manifest growth and throughput. Before ordinary route cutover: qualify scope filtering before ranking/limits, indexed membership/metadata paging and actual corpus scale. Before semantic completion: reconcile every required unit and measure coalesced publication/lag. Task 3a produces a compatible byte-bounded bulk building block; it does not claim those later gates have passed.
