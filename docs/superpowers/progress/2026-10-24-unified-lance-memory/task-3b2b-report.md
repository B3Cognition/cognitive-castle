# Task 3b2b — inactive pinned native archive source adapter

Initial implementation reviewed as Needs fixes for Important I1; fix round1 below addresses that finding and awaits independent re-review. Base `253227ffa10dcd35a3b737ef19cd7e04a9913845`. Product/test commit: `a610fad57ce3ee4946b5d863f52bc9390d6d480e` (`feat: add inactive pinned native source export`).

## Delivered boundary

- Added pure `native_export_codec.py`, engine-free `native_source_runtime.py`, read-only `native_source_export.py` and one fixed `native_source_worker.py`. The descriptor has the frozen `pinned-native-export-v1` shape and original archive/snapshot/version/start-cursor identity. No descriptor or snapshot is created or resealed by adapter code.
- Added exactly one `SemanticSession.native_source` stage: source2s,512/640 MiB, shortened by the session's remaining absolute5s deadline. Existing guardian admission, pressure/preemption, descendant cleanup and destination192/256 MiB read2/write3s and queue128/192 MiB profiles are preserved. No call to `run_history`, converter dispatch or10s history route occurs.
- The executable checks its strict request shape, history-profile live-chain admission and exact fixed guardian command/process-group/host-parent chain. It installs the existing history model/network/child guards and additionally refuses every `sqlite3.connect` audit event. Read-only history formatting imports do not grant converter or SQLite capabilities.
- Shared migration validation admits exactly the original SQLite format/domain and the new separately bound `native-migration-v1`. `_native_fixture_tick` is the sole explicit native fixture entry, sharing the existing prepare/import/identical replay/owner verification/ACK algorithm. The original SQLite registration/interval domains and bytes stay unchanged.
- Native cursors preserve canonical JSON of the exact original pre-row cursor, including absence of `row_address`. Active-owner stages keep that pre-row key. A finalization changes it only to the exact following physical/deletion-aware cursor. Owner references are independently bound to original archive/snapshot/version/physical address. Native owners are always history, including zero-member occurrences; no AUDIT/live inference occurs.
- Added narrow `NativeProjectedRow.header_or_none`; genuine fragment exhaustion returns `None`, while legacy `header()` still reports `corrupt` on exhaustion and genuine statistics/address/decode errors are never reclassified as EOF.
- Extracted only the shared pure historical scope header, bounded page packer and member payload formatter to `historical_export_evidence.py`. Both native and reviewed SQLite sources consume that formatter; native never instantiates a SQLite Source. Metadata bytes, encoded original columns, alias relations, full scope candidates/types/precedence, public original provenance and `sqlite-fts5-utf8-v1` are retained exactly.
- Native text is regenerated through≤8192-character projections and the exact canonical≤8192-UTF8-byte chunk packer. All passes share one64-call/2MiB returned-UTF8 slice budget. Ordinary ordered text/field/member SHA256 summaries are reconstructed on every replay; no serialized SHA state, whole-text join, accumulated source chunk-ID list, digest-of-page-hashes or in-memory `prepare_owner` is used in product code.

## Registered manifest decision

Root approved a strict bounded manifest: `{format,state,store_id,snapshot_identity,original,start_cursor,schema,fragments,inventory,lineage}`. `original={archive_id,snapshot_id,version}`; `schema={hash,bytes}` binds serialized Arrow schema≤64KiB. Manifest serialized bytes≤512KiB; inventory≤4096 sorted file items `{path,snapshot_identity,content_hash}` and≤4096 sorted exact native fragment metadata objects, including deletion files. Lineage is bounded supplied JSON, never proof that migration coverage is reconciled. Complete snapshot state and incomplete migration coverage remain distinct. The clarification is appended to the frozen brief.

Before/after every opened slice, the adapter validates private owned no-link paths, the snapshot root as a directory with directory link rules, manifest identity/hash/agreement, exact file inventory, immutable single-link files, native schema/version/fragment metadata and source identities. It reuses `_validate_snapshot` for the reviewed structural walk and checks full registered stat identities as well. Registered per-file content hashes are qualified sealing evidence; the adapter's stat walk does not independently prove the original copied corpus or recompute all file content on each slice. No original/live source walk occurs.

## TDD and self-review

Observed RED evidence before implementation included missing native codec, rejection of native descriptors by the old SQLite-only registration, missing fixed native worker, missing shared historical formatter, missing explicit native coordinator entry and missing fixed-guardian chain validation. Behavior tests also caught and then verified fixes for:

1. Python bool/int equality accepting wrong manifest identity/start/version values.
2. A summary deadline during postcheck overwriting an earlier projection-budget refusal with a misleading stale result.
3. A forged owner reference/partial native interval attempting to change the pre-row cursor before finalization.
4. Python `json.loads` accepting non-JSON `NaN` metadata. Native strict parsing now refuses it without source progress; original raw accepted JSON remains untouched.

Self-review checked the frozen scope, original occurrence/chunk IDs, deletion-aware offsets and physical addresses, preserved cursor JSON representation, exact original caller provenance, zero-text real owners, active/final cursor transitions, body-free intent and current-tick replay proof, immutable source inventory before/after both success and refusal, all fixed caps, and absence of any public/CLI/scheduler/production registration, converter invocation, new supervisor, model/vector path or production corpus access.

## Exact focused commands and outcomes

`PY=/Users/ladislavbihari/.echelon/venv/bin/python`; below `python` resolved to that interpreter. Every pytest launch used the guarded wrapper, explicit files and `--noconftest`. Source/native/SQLite fixtures were authorized under root's exclusive native slot; that slot was explicitly released immediately after the final changed-guard smoke. No native/storage tests ran afterward.

```sh
python scripts/safe_brain_tests.py --timeout 15 tests/test_native_export_codec.py --noconftest -x -q
# RED missing codec; subsequent codec/domain/runtime cycles GREEN.
python scripts/safe_brain_tests.py --timeout 35 tests/test_native_source_export.py -k 'small_source_identity_pages_and_eof' --noconftest -x -s
# RED missing worker; GREEN: 1 passed in8.01s; guard225.4MiB/8.3s.
python scripts/safe_brain_tests.py --timeout 15 tests/test_native_export_codec.py -k shared_historical --noconftest -x -q
# RED missing pure shared formatter; subsequent pure run GREEN.
python scripts/safe_brain_tests.py --timeout 90 tests/test_native_source_export.py -k 'empty_snapshot or changed_artifacts or multibatch' --noconftest -x -s
# GREEN: 8 passed,1 deselected in13.81s; guard226.4MiB/14.1s.
python scripts/safe_brain_tests.py --timeout 90 tests/test_native_source_export.py -k 'coordinator_staging_restart' --noconftest -x -s
# GREEN: 1 passed,9 deselected in14.85s; guard222.3MiB/15.1s.
python scripts/safe_brain_tests.py --timeout 90 tests/test_native_source_export.py -k 'type_conflicts or canonical_reuse' tests/test_sqlite_source_export.py -k 'type_conflicts or canonical_reuse or nine_chunk_and_history_exact_public_envelopes_and_audit_coverage or empty_original_alias_is_preserved_for_each_occurrence' --noconftest -x -s
# GREEN: 4 passed,28 deselected in16.49s; guard233.9MiB/16.7s.
python scripts/safe_brain_tests.py --timeout 15 tests/test_native_export_codec.py -k requires_actual_guardian --noconftest -x -q
# RED missing fixed-chain check; subsequent pure run GREEN.
python scripts/safe_brain_tests.py --timeout 15 tests/test_native_export_codec.py -k immutable_interval --noconftest -x -q
# RED forged original owner reference accepted; subsequent pure run GREEN.
python scripts/safe_brain_tests.py --timeout 20 tests/test_native_source_export.py -k invalid_json_metadata --noconftest -x -s
# RED acceptedNaN; GREEN: 1 passed,12 deselected in2.03s; guard222.0MiB/2.2s.
python scripts/safe_brain_tests.py --timeout 30 tests/test_native_source_export.py -k canonical_reuse --noconftest -x -s
# Final changed-guard/validator smoke GREEN: 1 passed,12 deselected in11.02s; guard224.5MiB/11.3s.
python scripts/safe_brain_tests.py --timeout 15 tests/test_native_export_codec.py tests/test_migration_codec.py tests/test_migration_coordinator.py tests/test_semantic_runtime.py tests/test_sqlite_export_codec.py --noconftest -k 'not (queue_prepare_restart or queue_orphan_scan or real_worker or real_no_content or real_multibatch or real_empty_history or real_proof_damage or real_source_replacement or retained_)' -x -q
# Final pure/changed-contract regression GREEN:87 tests, guard53.4MiB/0.6s.
```

The initial pure checks were rerun narrowly after their corresponding contract fixes, including `tests/test_native_export_codec.py tests/test_migration_codec.py`; intermediate green totals were21,24,27 and32 cases. The final command above supersedes those intermediate pure totals. No broad legacy/model suite or previous retained52MiB scale suite ran.

The first small fixture RED/GREEN harness initially used an8s fixture timeout; its actual measured runtime was1.8345/2.0296s. Root then explicitly fixed all new synthetic fixture stages at5s; the helper was corrected before the next native scope and all subsequent runs used5s512/640MiB. Native source stages were2s in5s sessions throughout. No production deadline/RSS/page/frame limit was raised.

Static commands use pinned `/Users/ladislavbihari/.echelon/venv/bin/ruff`0.15.12, covering all13 changed/new Python files: format, check and format--check; `git diff --check`. A first unqualified shell `ruff` resolved to0.15.5 and refused the repository's required version; it made no edits and was replaced with the pinned executable. Final results: all checks passed; no whitespace errors.

## Actual measured synthetic bounds

| Scope/stage | Measured time | Task RSS | Aggregate RSS |
|---|---:|---:|---:|
| First small native fixture GREEN |2.0296s|197,132,288B|236,437,504B|
| Small row source/replay/EOF slices |0.8347–0.8576s|≤181,747,712B|≤221,347,840B|
| Eight source-boundary cases, largest fixture aggregate |≤1.6532s|≤196,640,768B|≤238,272,512B|
|100,000-NUL source/replay slices |0.8802–0.9293s|≤184,107,008B|≤227,753,984B|
| Actual source stage in interrupted coordinator |≤0.9742s|≤184,680,448B|≤230,735,872B|
| Checked stage replay plus ACK tick |2.4153s|stage-specific profiles below|same|
| Full final owner + checked replay + owner verification + lost ACK tick |3.2054s|destination≤150,814,720B|destination≤197,771,264B|
| Canonical reuse earlier full ticks |3.0841/3.2368s|source≤180,813,824B|source≤229,703,680B|
| Final changed-guard full ticks |3.1878/3.1444s|source≤180,060,160B|source≤219,742,208B|
| Final changed-guard destination imports/replay/owner reads |0.6399–0.6955s|≤150,323,200B|≤190,119,936B|
| Deliberate oversized-metadata source refusal |0.8311s|181,895,168B|230,391,808B|
| Strict invalid-JSON source refusal GREEN |0.8670s|180,699,136B|219,348,992B|

The overall highest fixture aggregate in the mixed additional regression was245,284,864B; task196,689,920B,0.9148s. The highest observed destination aggregate across the canonical-reuse regression was199,852,032B. These are guardian sampled RSS tripwires, not guarantees against transient peaks.

Actual native ASCII frames included468,804B for a staged interval and165,933B for finalization; complete small owner frames were29,775B. Runtime and codec frame validation use the actual `json.dumps(...).encode("ascii")` transport,≤512KiB, beyond decoded UTF8 admission. Every emitted field/text page was≤8192UTF8 bytes. The large fixture used incrementally constructed Arrow buffers and an independently incrementally computed expected whole hash in the host; the host never constructed or joined the100,000-character occurrence. It produced13 canonical members over two deterministic source intervals. Source projection count/bytes are mechanically shared across all passes; the pure real-source-method test observed exactly64 calls before refusing call65. A complete four-pass traversal of this100,000-single-byte fixture would use52 projection calls/400,000 returned bytes; that is a code-derived bound, not native allocator telemetry.

## Tested correctness and refusal evidence

- Small actual native rows match old `_scan_rows` physical address/offset/identity and `_chunks` exact text/start/hash/provenance, including Unicode, supplementary codepoints, embedded NUL, combining marks and boundaries across projection/chunk windows. Non-vector reserved/spaced/nested fields remain in exact original columns.
- Two live physical fragments separated by a wholly deleted fragment, deleted rows, resume with/without original row address, empty dataset and true final exhaustion are covered. Corrupt statistics/address failures remain errors. Repeated alias, identical text in separate physical occurrences, empty alias and real zero text never collapse identities or fabricate a canonical member.
- Metadata whitespace/escapes and encoded columns are exact. Long scope text remains fully paged outside caller. Missing/null/empty and integer/boolean conflicting candidates retain their original types; null falls through while invalid non-null values do not invent lower-precedence public scopes.
- Descriptor/cursor/manifest binding, canonical embedded JSON, original start representation, booleans/ranges/packing/phases/active offsets, wrong native owner references and premature key changes are tested in the engine-free host.
- Actual writable file, extra file, symlink, hardlink, replaced manifest and replaced snapshot fixtures refuse with unchanged before/after cursor, no entries/finalization/count/completion. Exact fixture file bytes and stat inventories are compared before/after every successful source case and deliberate header/JSON refusal. No source artifact changed through export or destination publication.
- Actual one-pending-interval interruption before/after source and after staged import preserves the durable interval. Stage-only records/owner are invisible; stage ACK moves only staging cursor. Final owner publication and identical replay proof precede the owner ACK/completed frontier. Lost final ACK response is idempotent, and scan-exhaustion ACK cannot change the completed-owner frontier/count. Identical canonical original records are reused under distinct source bindings while owner/descriptor evidence remains distinct.
- Postcheck injected stale, deadline, MemoryError, invalid-value and OSError failures after tentative owner finalization or scan exhaustion clear all transient progress. Earlier projection-budget refusal reason is retained when postcheck also reaches its summary deadline.
- Fixed-session source normalization is exercised for injected worker RSS, aggregate RSS, worker deadline, background preemption and pressure refusals. These are protocol fault injections; no claim is made that the machine experienced those real resource failures during this run.
- The deliberate real metadata>1MiB fixture returned `qualification_required/native_metadata_size`, unchanged cursor/count/body. InvalidNaN metadata returned `corrupt/native_source_contract`, unchanged cursor/count/body. No genuine supervisor pressure/preemption/RSS/heap/deadline refusal occurred, so no automatic resource retry or cap raise occurred.

## Limits and next gate

This is an inactive synthetic qualification only. Source headers still materialize all admitted non-text/non-vector fields and complete encoded columns under the existing≤1MiB acceptance checks. Projected native windows can still allocate a full scalar internally. Full inventory walks retain their existing uncheckpointed per-step behavior under supervision. A budget refusal is incomplete/qualification-required state with no continuation skip.

The successful100KiB/two-batch native case does not qualify full52MiB native scalar decoding, giant destination3s finalization, all-shard reconciliation, maintenance/index scale or any production continuation. No all-shard cursor was inferred and no real corpus was read, registered, moved, copied, indexed or mutated. No adapter or test operation invoked the old converter or touched production original/protected/shard/staging data. Existing converter-stop and rollback operational controls/evidence remain root's responsibility; their current process/data state was not independently audited by this task. Coverage always stays incomplete/pending Task3c reconciliation; source EOF is only registered scan exhaustion. Root must perform independent review before any next phase.


## Fix round1/5 — Important I1, complete live session/identity boundary

Review `task-3b2b-review.md` correctly identified four omissions in initial commit `a610fad57ce3ee4946b5d863f52bc9390d6d480e`: worker session ID and guardian session ID were not required to equal the guardian PID, and neither guardian nor host effective UID was compared with the worker UID. Delegated history admission does not supply these checks. The initial smoke and three pure faults demonstrated command/group/parent checking only; they did **not** establish the brief's full session-chain contract. Any earlier implication of complete admission coverage at that commit is withdrawn.

The focused fix adds exactly those four established semantic admission conditions to `_admit_source`, plus the host process lookup needed for its UID. The existing history-profile admission remains intact, along with all APIs, fixed worker selection,512/640MiB caps,2s source stage and shared absolute5s tick. No shared validator refactor, generic provider, lifecycle work or other source/product change was introduced. Only `native_source_worker.py` and the corresponding guardian-chain fault test changed.

The test now supplies separate guardian/host process observations, tests each session/UID omission independently, retains the existing command/group/parent faults, and includes a valid-chain baseline. Before the fix, all four new faults returned `None` (admitted) instead of the unavailable refusal; the old faults and valid baseline passed. After the fix all eight cases pass. The real authorized empty snapshot proves the fixed chain still admits the actual established supervisor.

Exact commands:

```sh
python scripts/safe_brain_tests.py --timeout 15 tests/test_native_export_codec.py -k requires_actual_guardian --noconftest -q
# RED before product fix: ...FFFF.;4 failed/4 passed; guard40.2MiB/0.4s.
# The failures were worker_session, guardian_session, guardian_uid, host_uid;
# each showed None accepted instead of native_source_supervision_required.
# GREEN after product fix:8 passed; guard31.4MiB/0.2s.
python scripts/safe_brain_tests.py --timeout 20 tests/test_native_source_export.py -k empty_snapshot --noconftest -x -s
# GREEN:1 passed,12 deselected in2.70s; guard223.1MiB/2.9s.
/Users/ladislavbihari/.echelon/venv/bin/ruff format cognitive_castle/native_source_worker.py tests/test_native_export_codec.py
#1 file reformatted,1 left unchanged (test formatting only).
/Users/ladislavbihari/.echelon/venv/bin/ruff check cognitive_castle/native_source_worker.py tests/test_native_export_codec.py
#All checks passed!
/Users/ladislavbihari/.echelon/venv/bin/ruff format --check cognitive_castle/native_source_worker.py tests/test_native_export_codec.py
#2 files already formatted.
git diff --check
#No errors.
python scripts/safe_brain_tests.py --timeout 15 tests/test_native_export_codec.py -k requires_actual_guardian --noconftest -q
#Final post-format focused GREEN:8 passed; guard40.3MiB/0.4s.
```

Actual changed-guard smoke metrics:

| Stage | Time | Task RSS | Aggregate RSS |
|---|---:|---:|---:|
| Disposable empty native fixture, cap5s512/640MiB |1.7796s|189,448,192B|234,717,184B|
| Fixed native source, cap2s within5s session |0.8462s|162,824,192B|208,109,568B|

The empty-source result was genuine scan EOF with no entries/finalizations/counts, validated by the migration contract, and the source artifact fingerprint remained unchanged. No resource, pressure, heap, deadline or preemption refusal occurred. There was no automatic retry, cap change, extra native case or full-suite launch. The native slot was released immediately after this one authorized smoke; later work was pure/static/report/commit only. Root's untracked layout design/plan were excluded from staging and implementation.

Fix commit: `162a94f2e9fed205768fc3b6fa46d26bdeef900a` (`fix: require complete native source session chain`). Independent re-review remains required. The prior synthetic/production qualification limits remain unchanged.
