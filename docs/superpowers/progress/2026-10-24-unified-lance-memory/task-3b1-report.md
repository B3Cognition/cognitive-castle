# Task 3b1 — inactive protected SQLite export

Implementation based on independently approved Task3a `0278524e1bb85bcbea13bc6f2b55d8d50a34364f`. No ordinary/public route, operator mover, backup constructor, source checkpoint writer, capacity permit, service operation, native archive reader or semantic completion route was added. No real palace/source/installed checkout was read or changed. The old converter remains stopped. One product writer; no subagents or push.

## Private interfaces

- `sqlite_export_codec.py`: pure `validate_descriptor`, `source_binding`, `initial_cursor`, `validate_cursor`, `frame_bytes`, `file_identity`, `empty_counts`. Importing this or `sqlite_source_runtime` imports no SQLite/Lance/Arrow/model runtime.
- `sqlite_source_runtime.export_slice(descriptor, cursor=None)`: inactive trusted-host entry point. It obtains existing global admission, yields to interactive work and invokes only the fixed source executable with **128MiB task / 192MiB aggregate / 2s**, existing pressure/deadline/descendant cleanup. No caller-selected limits, models or providers.
- `sqlite_source_worker.py`: guarded SQLite-only executable; uses existing `_admit_storage`, SQLite **32MiB** hard heap and import/network/process guards, additionally blocking direct `lance`, NumPy and Pandas. It calls `sqlite_source_export.export_slice` only after admission. Source connections are `mode=ro&immutable=1` on registered completed protected views, `query_only`, bounded cache, no mmap, MEMORY temporary work and a progress handler. It never changes journal mode, checkpoints WAL, writes tables or calls converter publication/index/repair methods.
- Descriptor exact fields: `format="protected-sqlite-export-v1", store_id, snapshot_id, path, identity, manifest_path, manifest_identity, manifest_hash`. File identity includes device/inode/size/mtime_ns/ctime_ns/mode/uid/single-link count. Source binding hashes the domain-separated **entire descriptor**, including registered manifest hash. The private manifest binds complete state, file/content/schema identity, original archive/snapshot/version, catalog, high-water and coverage facts. Files, private storage directory, no-link ancestors and absence of WAL/SHM/journal sidecars are checked; content/schema/registered manifest are verified before output, content/manifest again after successful slices, file identities after every opened slice including refusals. The module consumes a registration; it cannot certify that a live file is a complete backup.
- Cursor exact fields: `format, packing="bulk-v1-ascii-1", source_binding, store_id, phase, key, owner, entry, field, member_ordinal, field_byte_offset, field_char_offset`. Phases are `live/history/audit/orphans/done`. Original live key is `[namespace,request_id]`, history key `[identity]`, audit key `[original_table,canonical_json(original_primary_key)]`. An owner-bearing cursor means a staged replay position; a null owner with a key means the last completed export unit. Generated field/member positions are checked on replay. Offsets/counts must be exact nonnegative integers, never booleans; binding/packing/version/types/unused-state relationships are validated. No OFFSET scan or Python whole-occurrence ID/text list exists.
- Result: `status, reason, source_binding, cursor_before, cursor_after, entries, finalizations, counts, phase, phase_complete, complete, coverage, frame_bytes`, with supervisor resource metrics and refused operation/field when available. `phase_complete` means the selected owner/unit's finalization was emitted (or export phases exhausted); **it never proves destination publication**. Counts increment at emitted unit finalization and distinguish live owners, historical occurrences, AUDIT owners, members, unresolved gaps, repaired gaps, pending stages and orphans. `complete` means this snapshot's export phases exhausted, while coverage remains indexed-only or explicitly incomplete. Supervisor/resource refusals also retain the exact cursor and empty entries/finalizations.

A completed registration is an input supplied by future qualified snapshot construction. Fixtures create, close and fsync disposable databases/manifests/directories in separately supervised workers. Production online backup/WAL/concurrent append/killed-backup proof, retention/reservation and cutover are **Task3c**, not fabricated here.

## Preservation and streaming

One owner represents each original production remember request, including nine chunks, or each historical occurrence. Live digest encoding is reconstructed with ordinary streaming SHA256 over the original JSON text encoding; bounded original IDs, caller equality, contiguous offsets, per-chunk hashes and deterministic original IDs are checked. The original namespace/key/digest and original-format receipt are retained. Prototype independent-source `import_sources` receipts are outside the confirmed source set and are refused when they violate production remember identity/offset/caller rules; the existing API was not changed.

Historical JSON IDs are traversed in original array order, oversized relational membership in original start/ID order. Dual membership must match exactly; missing members, bad deterministic identities, changed original text/metadata/columns hashes, alias bindings and incompatible callers refuse with no cursor advance. Empty text remains a real zero-member historical occurrence. Repeated aliases, including empty original aliases, retain each occurrence and alias relation. Original metadata/columns bytes are paged as stored; whitespace, Unicode and escaped NUL remain unchanged. Historical identity uses original archive/snapshot/version/physical address, never destination addresses.

The guarded adapter directly reuses `MemoryStore._source`/`_provenance` through the existing formatter, `CanonicalRecord.from_source` and existing history inventory/cursor validators. No competing public provenance formatter was copied. Existing `bulk_exact_codec.page/entry_batches/validate_batch/validate_owner` are used directly; no `prepare_owner` collection in production.

Each large field is read through bounded BLOB substrings and a strict incremental UTF8 decoder with at most3 carry bytes. Byte and character offsets are separate. Scope pages preserve raw historical candidate documents and columns/metadata/caller precedence/type evidence, plus exact chunk-specific callers, authoritative capture rows and original generation state. They retain long/absent/null/empty/nonstring/conflicting facts and original source times. Later generation conflict does not replace old chunk mapping. Capture sources/checkpoints/coverage retain exact evidence strings rather than observing raw transcripts again.

AUDIT is an explicit domain-separated **descriptor kind in the existing opaque owner format**, with original table/key/version, `metadata_id=null`, `live=null` and zero canonical members. No new row kind or fake historical occurrence was introduced; real3a publication of these owners succeeded. Attempts/gaps/repair lineage, aliases, capture facts and coverage observations are separately accounted for. Unpublished stages retain a pending snapshot/cursor/recovery descriptor; staged8KiB chunk text, metadata and carry are never published as canonical evidence. Orphans return explicit incomplete coverage without invented source owners. Derived FTS is not exported.

A slice regenerates one owner with bounded rereads and ordinary `hashlib` summaries, retaining only a current chunk/page, scalar summaries and a capped batch. It may stage an owner across batches; finalization is emitted only after whole original text and field/membership hashes verify. No custom SHA state, page-hash substitution, durable text outbox, source publication advance or destination semantic claim exists. Packing enforces the existing384KiB decoded/480KiB ASCII body candidate ceilings and actual **512KiB** request/response frames, including default ASCII escaping.

## TDD and observed failures

Pinned Python/ruff: `/Users/ladislavbihari/.echelon/venv/bin/`. All pytest runs used `scripts/safe_brain_tests.py --noconftest`, separately supervised source/fixture/destination workers and clean no-SQLite/native hosts. No model or repository-wide suite was run, as required by the scoped brief.

- Pure codec RED:3 missing-module failures; GREEN3. Runtime RED missing module; GREEN4 combined. Logs `/tmp/castle-task3b1-codec-{red,green}.log`, `runtime-{red,green}.log`.
- Initial source fixture errors were corrected (nine-chunk input exceeded65536B; capture-generation placeholder count). Two subsequent prelaunch EAGAIN admission refusals were observed; immediate lsof showed no holder, so their owners remain unproven. Production guards were unchanged. The existing test-only8s logged admission coordination pattern was reused. Source RED then reached absent worker; initial small-owner GREEN1. Logs `source-red.log`, `source-green.log`, `source-green2.log`.
- Five corruption modes and large Unicode/NUL metadata:5passed/1failed in4.62s. All corruptions correctly refused; the sole failing assertion confused cursor_before phase with attempted phase across an empty phase transition. Added explicit phase reporting without changing cursor_before; targeted `new-source.log` GREEN4 includes corrected hash-phase case, exact formatter/artifact parity, orphan refusal and repaired-gap evidence. `boundaries.log` retains the failed assertion.
- Supervisor refusal envelope RED lacked cursors; GREEN retains the exact cursor/empty content and asserts fixed128/192MiB,2s/background preemption. Logs `refusal-{red,green}.log`.
- Native adapter-to-real3a publication GREEN1 in20.05s: actual exported bounded slices, original public sources compared to **existing `MemoryStore._source` plus `UnifiedMemoryStore._metadata_reference`**, original remember retry/receipt, exact metadata/scope/descriptor pages and clean host. `native.log`.
- Final affected regression GREEN7 in2.82s: all5 pure checks, formatter/artifact parity including relational history, dual-membership conflict. `affected-final.log`. Additional literal scope/pending assertions GREEN1 in2.37s: old6000Ω mapping vs later null/conflict generation; distinct second scope; seven absent mappings; historical missing/null/empty precedence; exact checkpoint/coverage whitespace; pending8KiB stage excluded. `scope-final.log`.
- Unsupported table and incomplete registration GREEN2 in0.58s, with empty output/unchanged cursor. `unsupported.log`.
- Empty original alias RED revealed both overly strict empty-key validation and SQLite empty-BLOB substr returning NULL. Explicit TEXT empty branches preserve absence/null/empty separately. `alias-red.log`, `alias-green.log`, `alias-green2.log` retain these successive genuine failures. A subsequent run passed history/most audits before legitimate `background_preempted` at audit (0.0561s), unchanged refusal cursor; admission holders were observed afterward. No RSS/deadline/heap increase or automatic resource retry. `alias-green3.log`. Final affected result recorded below.

Commands used (PY denotes the pinned interpreter):

```sh
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_export_codec.py --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_source_export.py -k nine_chunk --noconftest -s
PY scripts/safe_brain_tests.py --timeout 40 tests/test_sqlite_source_export.py -k 'corrupt_members or large_fields' --noconftest -s
PY scripts/safe_brain_tests.py --timeout 40 tests/test_sqlite_source_export.py -k 'hash-history or orphan_refuses or nine_chunk' --noconftest -s
PY scripts/safe_brain_tests.py --timeout 45 tests/test_sqlite_source_export.py -k real_bulk --noconftest -s
PY scripts/safe_brain_tests.py --timeout 45 tests/test_sqlite_source_export.py -k representative --noconftest -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_source_export.py -k retained_scale_plan --noconftest -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_source_export.py -k retained_scale_member --noconftest -s
PY scripts/safe_brain_tests.py --timeout 20 tests/test_sqlite_export_codec.py tests/test_sqlite_source_export.py::test_nine_chunk_and_history_exact_public_envelopes_and_audit_coverage 'tests/test_sqlite_source_export.py::test_corrupt_members_and_original_hashes_refuse_without_advancing[dual-history]' --noconftest -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_source_export.py -k unsupported_source --noconftest -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_source_export.py -k empty_original --noconftest -s
```

Retained-fixture plan/member commands used `CASTLE_TEST_RETAINED_SOURCE` pointing only at the disposable52MiB fixture created in the preceding supervised test; those tests skip without explicit fixture selection. The ordinary representative test builds it in26 bounded256-chunk/2MiB transactions plus separate init/seal, never a52MiB host string/list/transaction.

## 52MiB sorter defect and qualified correction

The first representative attempt completed all28 fixture stages, then refused `qualification_required/sqlite_summary_limit`, with empty entries/finalizations and identical cursors. This was **not accepted as a final unsupported-size gate**: root identified a plausible streaming defect, and a supervised EXPLAIN read confirmed it before changing code.

Old relational member query sorted projected `CHUNK_COLUMNS` including text/caller. EXPLAIN used TEMP B-TREE, six-field `MakeRecord` → `SorterInsert`, preceded by body/caller/hash column reads:52MiB text entered the32MiB SQLite sorter heap. The corrected query sorts only original `c.start,c.id` keys through the existing membership/chunk PK indexes, then fetches each bounded original chunk by ID. EXPLAIN shows two-field `MakeRecord` → `SorterInsert`; no extra heap, FILE temporary storage or wider profile was used. `/tmp/castle-task3b1-plan.log` preserves exact queries/opcodes.

Focused correction GREEN reused the same protected fixture, no repeated26 writes:

| Stage | Outcome | Task RSS | Aggregate RSS | Elapsed |
|---|---|---:|---:|---:|
| Original body-sort export | qualification_required; unchanged cursor |85,327,872B|123,387,904B|0.1453s|
| Read-only EXPLAIN | confirmed6-field vs2-field sorter |47,104,000B|90,030,080B|0.1082s|
| Corrected member stream |6656members,54,525,952 original text bytes, original SHA256 parity |56,377,344B|100,532,224B|0.4776s|
| Corrected export slice |ok;48 exact scope pages; zero owner finalizations |55,181,312B|99,368,960B|1.3759s|

Corrected actual ASCII response446,571B; cursor advances to history/scopes byte/character376832, entry48. Whole52MiB original text/membership/field summaries verified before progress. This is **one successful bounded export interval**, not complete52MiB export, destination finalization or semantic completion. Logs `scale.log`, `plan.log`, `keysort-green.log` preserve the original refusal and corrected evidence. A summary pass that cannot finish still returns explicit qualification_required with no cursor advance.

Other measured bounds: large Unicode/NUL metadata response473,656B, source0.1826s and50,970,624/95,797,248B task/aggregate. Native real3a27 destination stages all succeeded, maximum149,831,680/189,661,184B and1.1489s; writes retained3s and reads2s at192/256MiB. The historical boundary test's phase-assertion failure is disclosed above; its source refusal was correct. No worker RSS, aggregate RSS, pressure or supervisor deadline limit was relaxed.

## Remaining gates and handoff

- Source preservation/export only. Task3b2 must persist metadata-only intent, regenerate/replay exact intervals, verify durable destination receipts/owners and advance frontiers in order. No coordination store, committed destination cursor or semantic queue was added.
- Task3c must qualify production protected backup/WAL consistency and reservations, repeated slices/all fields of representative sources, full52MiB destination finalization, index/fragment scale, cross-store duplicate reconciliation, throughput and cutover/delta scope reconciliation. One successful52MiB source slice is not blanket corpus readiness.
- Task4 still owns policy/scope projection and pre-ranking/filtering. Scope pages preserve exact facts; they do not grant exposure or implement public search filtering.
- Runtime profiles remain sampled RSS tripwires, not kernel allocation ceilings. Refusals/preemption are honest and retain source progress; future supervision must not blindly skip or repeatedly advance an impossible summary.
- Report is a local task artifact excluded from scoped code/test commit. Root owns independent review.

Final alias qualification, lint/format/diff checks, commit SHA and cleanup follow below.

## Final affected alias verification and housekeeping

The first authorized post-preemption rerun had an immediate trusted `interactive_waiting=False` check, admitted its fixture after two logged waits, then returned **memory_busy before the first source worker**. Four live admission holders were observed; attribution remains unproven. Log `alias-final.log`. It is a contention refusal, not an alias correctness failure. No automatic retry or production wait/profile change followed.

Root narrowed the test to the relevant original history owner and history_aliases AUDIT owner, using valid bound cursors, instead of repeating an unrelated full audit sweep. Final affected GREEN: **1passed,15deselected in0.42s**. The exact empty occurrence alias, columns ID and alias relation were preserved; the AUDIT row retained the empty TEXT alias and original primary key, with zero historical-occurrence count. Source stages0.1179s/0.1024s,45,989,888/92,127,232B maximum source task/aggregate; fixture0.135s,51,265,536/97,124,352B. Log `/tmp/castle-task3b1-alias-narrow-final.log`. No special lease or production admission behavior was introduced.

Current product's last changes since52MiB/native qualification are bounded empty-TEXT handling, stricter original alias/columns relation checking and uniform refusal accounting. They do not change source/destination limits or public encoding. The affected empty-alias owner and audit paths were verified; no already-green broad/native suite was repeated. Full52MiB destination finalization/all-slice throughput remain unqualified as stated above.

Commit: **`2235078869563b6c2be360b4b772182e683d34d9`** — `feat: add protected streaming SQLite source export`.

Scoped commit contains only the4 new product modules and2 focused test modules listed above. Pinned `ruff check`, `ruff format --check` and staged `git diff --check` passed immediately before commit; worktree status is clean. Final exact worker/guardian/fixture process inventory found no remaining worktree processes. Report excluded from commit. No push. Root owns independent review and integration.
