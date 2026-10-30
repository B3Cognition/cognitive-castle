# Task 3a implementation report

Base: d4d6850dde81ab793bffecb6fdc5df424d084e2b. Scoped commit recorded below.

## Adapter-facing interfaces

Pure `cognitive_castle.bulk_exact_codec` (no storage/native imports):

- `owner_id(owner_key, source_binding)` derives a domain-separated `receipt:<sha256>` owner marker ID. Owner key <=256 UTF8 bytes; source binding <=1024 bytes. Supply original occurrence/request identity and observed immutable source version deliberately; these are not derived from public caller provenance.
- `page_id(owner, field, ordinal)` and `page(owner, field, ordinal, text, offset, byte_offset)` encode/validate exact UTF8 pages. Fields are `metadata`, `columns`, `scopes`, `descriptor`, `membership`. Each payload <=8192 UTF8 bytes; character/byte offsets are independent. `split_text(text)` preserves every character and splits on UTF8 boundaries. Field pages use contiguous original character/byte offsets. Scopes and descriptor are opaque exact strings: preserve full absent/conflicting attribution, aliases, original occurrence identity/cursors/capture details in their original representation; this task deliberately does not infer them from truncated caller provenance.
- Each membership page contains one canonical JSON member object: `id,ordinal,start,end,bytes,hash,exposure,scopes`. `scopes` contains `{first_page,hash,bytes,chars,pages}`, binding the complete original owner scope/attribution document; its first page is null only for an empty original scope document. A source-specific map, if present in the original document, remains exact and is not replaced by caller inference. `hash` is original chunk text SHA256; `exposure` hashes only original id/text/provenance using the established canonical JSON encoding. Membership header offset/byte_offset equal member ordinal. Owner manifest membership hash is streaming SHA256 over concatenated ordered exact membership payloads. No giant membership array is stored.
- Bulk record rows preserve original `id,text,provenance`; `digest` binds owner marker ID; `receipt` is canonical `{format:"bulk-v1",page:<membership page ID>,ordinal:<member ordinal>}`.
- `summary(text,pages)` / `validate_owner(manifest)` describe original whole-text and field hashes/lengths/page counts. Owner manifest has fixed fields `format,state,owner,owner_key,source_binding,members,membership_hash,text_hash,text_bytes,text_chars,fields,metadata_id,live`. State is `published_owner`; `fields` contains summaries `{hash,bytes,chars,pages}` for metadata/columns/scopes/descriptor. `metadata_id` is the original historical metadata identity or null. `live` is null or original `{namespace,key,digest,receipt}`. Historical identity/aliases/cursors belong in paged exact descriptor. Do not hash page hashes as a substitute for original text hashes.
- `prepare_owner(owner_key,source_binding,records,*,metadata="",columns="",scopes="null",descriptor="null",metadata_id=None,live=None)` is an in-memory codec convenience returning `(entries,manifest)`. A production streaming adapter should emit the same pages/records and incremental hashes; it must not materialize a whole large occurrence merely to use this convenience.
- `entry_batches(entries)` packs an iterable into <=256-entry batches bounded by 384KiB decoded bytes and 480KiB encoded-body ceiling with an additional16KiB packing reserve. It accounts for the guardian's actual default ASCII JSON escaping, including embedded JSON strings. `validate_batch(batch_id,source_binding,entries,finalizations)` independently validates counts, exact schemas, duplicates, bytes and canonical request digest. Batch keys <=128 bytes. Persist stable batch keys in the later operator checkpoint; a staged receipt is never a source checkpoint.

Fixed private worker operations (through existing supervision):

- `import_batch(batch_id,source_binding,entries,finalizations)` atomically appends new entries, verified owner markers, optional original-format live receipts, and one batch receipt. Compact result contains status/state/receipt_id/digest/records/published_owners/entries, never corpus IDs. Stage state is `stage_batch`; requests publishing owner(s) return `committed_batch`. Identical batch replay verifies referenced durable proofs and returns the original compact result; changed body/binding conflicts. Existing visible canonical rows are reused without rewrite; staged records cannot change owner. Finalization streams existing+incoming pages/records, validates order/offsets/hashes, and appends only marker/receipt; large text is not copied.
- `bulk_owner(owner,version=None)` returns bounded published manifest, current pinned dataset version and lookup coverage.
- `bulk_page(owner,field,ordinal,version=None)` returns exact payload/header/hash only after a published owner exists; membership uses the same operation. Use returned version on subsequent pages. A changed current dataset version returns `stale` rather than silently mixing generations.
- `bulk_receipt(batch_id,source_binding,offset=0,version=None)` verifies durable proof and returns compact receipt plus <=16 proof entries and continuation. Source binding mismatch conflicts.
- `build_id_index()` is explicit supervised BTREE maintenance on id, under the same writer lock. Ordinary reads never build/optimize. Lookup returns coverage version/index_version/indexed_fragments/tail_fragments/tail_rows. Current candidate limits: <=1024 unindexed physical rows, <=32 unindexed fragments; otherwise `index_required`. Explicit maintenance refuses beyond16384 rows (`maintenance_limit`); larger qualification remains a later gate.

All use the original six-string schema and existing fixed512KiB guardian/worker ceiling. Native reads2s/writes3s;192MiB task/256MiB aggregate, global admission, pressure and descendant cleanup unchanged. Existing remember/import_sources<=8/receipt/read_sources/page signatures remain; original nine-chunk remember receipts remain valid. Exact hydration uses one shared owner-membership gate, so Task2 cannot see staged records. Scope-prefiltered search and real source adapters/movement are not implemented here.

## Evidence so far

- Pure codec RED4 missing module failures, GREEN4 tests. Additional indexed-small-lookup RED (former use_scalar_index=False), then GREEN; batching missing-helper RED then GREEN.
- Native12 tiny sources/owners in one real dataset version1:61rows/1fragment; replay no mutation; identical-content second batch adds only one receipt; changed body conflicts; exact late-ID hydration. Peak150,732,800B task/188,809,216B aggregate, max1.1505s. Log `/tmp/castle-task3a-first.log`.
- Staging invisibility, before-finalization interruption, lost final acknowledgement, original request receipt replay, metadata descriptor, pinned-version stale, empty occurrence, missing membership and staged-owner rebind/duplicate refusal passed. Log `/tmp/castle-task3a-staging.log`.
- Nine commits,1089rows crossed tail limit and returned index_required; BTREE build version10 covering9fragments at data version9; appended6row tail participates; duplicate spanning index/tail refused. Log `/tmp/castle-task3a-index.log`.
- Long fixture initial32-page and then UTF8-only packed batches each refused pre-storage with worker_invalid_frame (0.0475/0.0455s). Guardian serializes its config with default ensure_ascii=True, unlike worker UTF8 serialization. Pure regression then demonstrated838281B outer frame against512KiB. Packing/validation now budgets actual ASCII escaping; no frame/cap change.
- Fixed-wire long fixture GREEN:870400text bytes/522240characters/128chunks plus exact metadata/scopes,288entries in8bounded staging commits,296rows before finalization,298rows after (marker+receipt only),9fragments. Whole original SHA256 verified; last source exact; receipt paging works. Finalization0.6821s,153747456B task/194019328B aggregate. No deadline/RSS/pressure refusal. Log `/tmp/castle-task3a-whole-fixed-wire.log`. This small fixture does not qualify52MB or500k records.


## Self-review adjustments and focused evidence

- All small exact ID checks now call the same bounded indexed IN lookup as bulk, including projected multi-ID existence/hydration/receipt checks. Pure RED `test_small_exact_identity_lookup_uses_shared_indexed_batch_boundary` caught the former explicitly unindexed scan; GREEN verifies index use/IN boundary without importing native code.
- Member scope-page binding was added after a pure RED (`test_membership_binds_full_scope_pages_outside_public_provenance`) demonstrated the absent direct reference. The owner descriptor remains bounded, scope text has no new small size limit, and source/exposure hashes remain unchanged.
- `_verify_receipt_records` was extracted from the existing exact receipt verifier so bulk original-live-receipt finalization uses the same identity/content/digest validation. Pure RED missing shared helper then GREEN, including nine UTF8 remember chunks and bad digest/length cases. Existing public receipt encodings and old key-derived IDs are unchanged.
- Native corruption RED `test_replay_refuses_incomplete_durable_batch_proof` removed an owner proof entry and recomputed the receipt row's local hash; replay originally accepted it. The fix verifies proof row kinds/counts/owner binding/live-receipt IDs and exact expected proof IDs on replay. Targeted GREEN1 (2.03s); `/tmp/castle-task3a-proof-red.log` and `/tmp/castle-task3a-proof-green.log` preserve the result. No corrupt proof is accepted merely because its local payload hash matches.
- Native boundary selection GREEN10 in19.50s, sampled guard183.7MiB: actual Task2 `_hydrate` through `SemanticSession` returns not_found for staged canonical records, then exact original source after finalization; six membership/order/text/metadata/columns/scope checksum corruptions refuse; all bulk reads leave full artifact inventory unchanged; hardlinks refuse; already visible legacy rows remain visible during reuse; migrated original nine-chunk remember/receipt replay succeeds. `/tmp/castle-task3a-boundaries.log`.

These tests are synthetic disposable fixtures only. Full raw occurrence descriptor/scopes are adapter inputs whose source truth must be qualified in Task3b; this codec verifies exact preservation and declared hashes, not correctness of an untrusted attribution claim. Each member binds the full scope document rather than guessing one scalar workspace. Public scope search/filtering remains Task4.


## Final qualification, interruption, and exact test accounting

Commands use `/Users/ladislavbihari/.echelon/venv/bin/python` (`PY`) and pinned `ruff` from the same venv. Every native operation ran beneath the existing fixed supervisor. No model, provider, network request, service, installed checkout, real palace or original source was used or changed.

Initial focused RED/GREEN commands:

```sh
PY scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_exact_codec.py --noconftest -q
PY scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_exact_store.py -k more_than --noconftest -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_bulk_exact_codec.py -k small_exact --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_bulk_exact_codec.py -k entry_batcher --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_bulk_exact_codec.py -k membership_binds --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_bulk_exact_codec.py -k live_receipt_validation --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_bulk_exact_store.py -k incomplete_durable --noconftest -s
```

These respectively exposed: absent codec (4failures); absent fixed worker operation (1failure); explicitly unindexed small lookup; missing byte-aware packer and then ASCII-escaped outer-frame838281B overflow; absent member scope-page reference; missing shared original-receipt proof helper; incomplete durable batch proof accepted. Each was fixed and its focused test passed. The wire-overflow native attempts and all intentional refusal statuses remain recorded above; no failed resource result was discarded or converted to a success.

The final combined regression command was:

```sh
PY scripts/safe_brain_tests.py --timeout 150 tests/test_bulk_exact_codec.py tests/test_bulk_exact_store.py tests/test_lance_exact_store.py tests/test_canonical_records.py --noconftest -s
```

**This run was intentionally stopped with SIGINT and is not claimed as an all-green run.** I mistakenly selected existing `test_canonical_records.py`, which imports legacy `fast_memory.MemoryStore` and SQLite during collection. That violated this task's no-SQLite-host constraint even with `--noconftest`; the bulk staging test's final host-import assertion failed. No legacy SQLite parity test body executed before the stop. This was a test-selection error, not a product import workaround. Product code, native budgets and safety guards were unchanged to address it. The safe runner's `finally` cleanup killed/reaped its children; its exit was130. Log: `/tmp/castle-task3a-final.log`. No final guard aggregate summary exists because the wrapper was interrupted.

Completed checks in that log, identified by deterministic collection order and progress dots:

- All9 codec tests then present passed: exact pages/exposure, empty/live owner, malformed envelopes, byte/count/duplicates, shared indexed lookup, ASCII-aware packer, wrong UID guard, member scope-page reference, shared original receipt proof.
- All19 bulk tests executed:18passed; `test_staging_visibility_finalization_and_original_receipt` reached its final host-import assertion and failed due to collection-loaded SQLite. All preceding native assertions in that test passed. Passing names: `test_more_than_eight_in_one_append_replay_and_reuse`; `test_byte_refusal_before_artifacts_and_empty_owner`; `test_missing_membership_duplicate_and_staged_rebinding`; `test_explicit_index_many_commits_late_tail_and_duplicate`; `test_multibatch_original_whole_hash_and_paged_receipt`; `test_semantic_hydration_stays_pending_until_bulk_owner_published`; `test_finalization_refuses_malformed_or_reordered_content` for membership_offset/membership_hash/text_hash/metadata_hash/columns_hash/scope_hash; `test_bulk_reads_are_readonly_and_unsafe_hardlink_is_rejected`; `test_visible_legacy_record_reused_without_exposure_or_kind_change`; `test_migrated_ninth_live_chunk_uses_original_receipt`; `test_replay_refuses_incomplete_durable_batch_proof`; `test_decoded_byte_refusal_and_256_entry_ceiling`; `test_exact_full_scope_pages_include_absence_conflict_and_unicode`.
- First5 existing exact cases passed: `test_create_append_reopen_replay_and_conflict`, `test_unicode_nul_chunk_pages_and_hash_binding`, `test_commit_with_lost_response_replays_durable_receipt`, `test_import_preserves_provenance_reuses_records_and_checks_replay`, `test_replay_refuses_duplicate_or_corrupt_committed_state[duplicate_record]`.
- Remaining25 exact cases were uncompleted at interruption: the duplicate_receipt/bad_text/missing_record/bad_receipt/bad_digest/bad_schema corruption variants; readonly missing/existing store; all5 unsafe path variants; unsupervised worker refusal; all6 invalid-request variants; writer lock; host/direct supervision; network/provider/child/readonly guards; oversized frame; both original nine-chunk/lost-response variants. All legacy `test_canonical_records.py` bodies were excluded from subsequent qualification.

That log contains98 completed bulk fixture stages with peak154386432B task /207470592B aggregate and maximum0.9846s. Its higher host RSS includes accidental SQLite collection. Status counts:74ok,10corrupt,4not_found,2conflict,1index_required,1stale,6unavailable. Unavailable outcomes are the deliberate before/after-commit lost replies, oversize-frame refusal, decoded-byte and257-entry refusals, and unsafe-hardlink refusal. There was no pressure, admission, RSS or deadline refusal. The final-schema whole-hash fixture again verified870400original text bytes/522240characters/128chunks across8staging commits; finalization0.6828s,154386432B task/207470592B aggregate, adding only marker+receipt (296→298rows,8→9fragments). Explicit index build/late tail and256-entry actual append also passed. This preserves completed fixture evidence with the host-import limitation rather than repeating every green native case.

Targeted clean verification (no product code changed after the completed cases):

```sh
PY scripts/safe_brain_tests.py --timeout 25 tests/test_bulk_exact_store.py -k staging_visibility --noconftest -s
PY scripts/safe_brain_tests.py --timeout 90 tests/test_lance_exact_store.py -k 'not (create_append_reopen or unicode_nul_chunk or commit_with_lost_response or import_preserves_provenance or duplicate_record)' --noconftest -v
PY scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_exact_codec.py tests/test_semantic_runtime.py tests/test_semantic_indexer.py -k 'bulk_worker_operations or fixed_stage_caps or shared_deadline_expiry or background_yields or deadline_consumes or infer_rejects or success_arriving or tokenizer_response_must or real_supervisor_preflight' --noconftest -v
```

Results:

- Staging/original receipt replay: **1passed,18deselected in7.67s**, guard181.2MiB/7.9s. SQLite/Lance/Arrow host-import assertion passed. Log `/tmp/castle-task3a-clean-host.log`.
- Remaining original exact checks: **25passed,5deselected in26.51s**, guard180.2MiB/26.7s. Log `/tmp/castle-task3a-exact-remaining.log`.
- Fixed bulk cap and existing shared-session/deadline checks: **9passed,37deselected in0.08s**, guard31.3MiB/0.2s. Includes one new pure test proving all five bulk operations retain3s write/2s read,192MiB task/256MiB aggregate; all7 existing semantic runtime tests and the existing fixed-stage-cap test. Log `/tmp/castle-task3a-caps.log`.

Combined evidence covers **67 distinct scoped checks**:10codec,19bulk,30original exact,7semantic runtime,1fixed semantic stage test. This is combined evidence across the explicitly reported runs, not a single green full-suite claim. The one host-collection failure is resolved by the targeted clean run; its original failure and stopped run remain disclosed. No full repository suite was run, per the task's explicit focused-test instruction. No already-green broad native suite was repeated after the interruption.

## Limitations and handoff

- Candidate limits are not production qualification:256entries,384KiB decoded/480KiB body encoded,1024 unindexed rows/32tail fragments,16384row explicit maintenance admission. The actual index fixture covered1089rows over9commits, and actual256-entry publication used tiny pages. Larger maintenance, fragment growth, sustained throughput,52MB whole verification and500k corpus readiness remain unqualified. Recursive artifact validation remains intact and may become a measured future bottleneck.
- Scope/descriptor bytes are preserved as exact paged documents. The trusted Task3b adapter must carry original identity/aliases/cursors/full per-source attribution and supply correct original whole hashes. No public policy search/prefiltering, live exporter, operator mover, capacity reservation or source checkpoint advancement is added here.
- Finalization restarts ordinary streaming hashlib after interruption; there is no speculative resumable SHA state. Larger occurrences may hit the unchanged deadline; this fixture did not. Durable receipts and owners are retained for replay/conflict proof.
- RSS is a sampled tripwire, not a kernel allocation ceiling. Stage/aggregate caps, live admission, pressure/preemption and descendant cleanup were not increased or weakened.
- Root owns independent review, downstream integration and actual-source qualification. This report is a local task artifact and is deliberately excluded from the code/test commit.

Scoped code/test files: `cognitive_castle/bulk_exact_codec.py`, `cognitive_castle/bulk_exact_store.py`, `cognitive_castle/lance_exact_store.py`, `cognitive_castle/lance_exact_worker.py`, `cognitive_castle/semantic_runtime.py`, `tests/test_bulk_exact_codec.py`, `tests/test_bulk_exact_store.py`.

## Commit and final housekeeping

Commit: `0278524e1bb85bcbea13bc6f2b55d8d50a34364f` — `feat: add bounded bulk exact owner publication`.

Pinned `ruff check` and `ruff format --check` passed for all7 scoped code/test files; staged/unstaged `git diff --check` passed. Scoped commit contains only those7 files; worktree status is clean. No push. A final process inventory found no remaining worktree guardian/exact/native fixture process. Native slot was released to root before report/commit finalization. Existing installation6402ae5, stopped old converter, real palace/sources, services and profiles remain untouched.
