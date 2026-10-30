# Task 3b2a — inactive durable protected-SQLite migration coordination

Base: independently reviewed `48107d5bc9be551dcfb71642f10c1c0ecaba5c95`, branch `design/semantic-preservation`. Sole product writer; no subagents, push, public/CLI/scheduler wiring, production mover/permit, native archive adapter, old converter, source writes, real data/services, models, maintenance or resource-cap changes. All movement below is fresh/sealed private disposable fixtures explicitly authorized by root. This report is a local handoff artifact, excluded from the code/test commit.

## Interfaces and exact state schemas

`migration_codec.py` is pure, with no SQLite/Lance/Arrow/model imports. Coordinator version/domain is `sqlite-migration-v1`; packing remains reviewed `bulk-v1-ascii-1`. Metadata objects have a 192KiB actual ASCII-frame ceiling in addition to the existing 512KiB worker frames. Counts are exact nonnegative signed-64-bit integers, never booleans. Strict field allowlists reject body-bearing/unknown nested fields.

- `registration(descriptor,destination)` / `validate_registration`: exact fields `{format,packing,source_binding,descriptor,destination,job_id}`. Destination is the absolute registered generation; job identity hashes the versioned domain and entire registration, including full reviewed source descriptor binding. A complete same-job rebind returns explicit `conflict` before admission/storage. New immutable source generations have different identities; registration is never movement authorization.
- `validate_export(result,registration,before)` uses the unchanged 3b1 cursor codec and validates actual ASCII response length, exact before/after binding, one-owner source phase, finalization versus staging cursor relationships, explicit live/history/AUDIT classification and counts. Refusal carries no body/progress/completion flags. No-content `done` is separate from a content interval.
- `prepare_interval` / `validate_interval`: exact fields `{format,packing,job_id,source_binding,destination,intent_id,cursor_before,cursor_after,digest,entries,records,owners,counts,coverage,phase}`. The interval ID hashes the coordinator domain, job, full source/destination binding, packing and original before cursor. Digest is the actual `bulk_exact_codec.validate_batch(intent_id,binding,entries,finalizations)` result. No timestamp, retry count or temporary path enters identity. A pending interval regenerates identically or stops in conflict.
- Owner metadata exact fields: `{owner,owner_key,manifest_hash,members,membership_hash,text_hash,text_bytes,text_chars,fields,classification,semantic_disposition,source_phase,source_key,live_receipt_ids}`. `fields` contains only the existing four `{hash,bytes,chars,pages}` summaries. Original live IDs are references bounded to nine. Disposition is `pending` only for verified live/history owners with members, `no_members` for real empty occurrences, `audit_only` for AUDIT. No scalar scope/group binding is invented.
- Verification summary: `{intent_hash,proof_version,receipt,owner_versions}`. Receipt is exactly the prepared compact 3a status/state/receipt_id/digest/records/published_owners/entries. Proof version is `bulk-v1-identical-replay`; owner dataset versions are observed positive integers. This is an ACK input from current-tick checks, not a durable partial-proof state.

Existing `coordination/queue.sqlite3` upgrades additively to `PRAGMA user_version=3`; existing versions1/2 remain readable and upgrade under the existing FULL synchronous immediate write transaction. Existing Task2 tables/operations/schema stay compatible. Existing private-path checks, queue SQLite16MiB heap, supervision, cache/no-mmap and transaction guards stay intact.

- `migration_jobs`: `{job_id PK,registration,staging_cursor,completed_frontier,pending,counts,coverage,state,last_ack,last_refusal,owner_references,semantic_pending}`. JSON columns contain only the above metadata schemas/cursors. There is at most one `pending` interval. State is active/refused/snapshot_export_exhausted. Last ACK stores only `{intent_id,summary_hash,result}` for bounded identity/result recovery; no proof journal/offset/pages or CAS lease exists.
- `migration_owners`: `{job_id,owner,reference}`, primary key `(job_id,owner)`. A reference adds job/source/destination identity and observed proof/dataset versions to the bounded owner metadata. All classifications remain distinct; only members-bearing live/history references increment semantic_pending. No corpus-wide member list enters a row.
- `queue_migration_open(registration)` registers idempotently and returns one compact state; `queue_migration_state(job_id)` reads the same state without mutations; `queue_migration_prepare(job_id,expected_cursor,intent)` compares the verified staging cursor and installs one identical-retry interval without advancing anything; `queue_migration_ack(job_id,intent_id,verified_summary)` atomically consumes the exact pending interval, advances staging, advances completed frontier only at finalization, increments counters once, inserts distinct owner references and retains the ACK result. Wrong pending/prior cursor conflicts. `queue_migration_refuse(job_id,expected_cursor,refusal)` records bounded refusal metadata without consuming pending/progress; observed orphan count is idempotently retained.

Scan exhaustion uses `intent_id=None` and an exact `{state:"snapshot_export_exhausted",cursor_before,cursor_after,coverage}` summary. It requires no pending interval, equal acknowledged staging/completed frontiers, no staged owner and no observed orphan. It advances the scan cursor to done while preserving the last completed-owner frontier. It creates no empty batch/fake owner and claims no exact-corpus or semantic completeness.

## Shared runtime and inactive fixture boundary

`SemanticSession.sqlite_source` adds exactly one fixed `sqlite_source_worker.py` `_run_stage` call: source2s,128MiB task/192MiB aggregate, within the same existing admission and absolute5s deadline. `sqlite_source_runtime.source_request/source_result/source_refusal` are narrowly shared with the standalone API; standalone admission behavior remains compatible. Host response validation is charged to the same deadline and late source success is normalized back to an unchanged-cursor refusal. Queue state reads2s/mutations3s at128/192MiB; existing exact reads2s/writes3s at192/256MiB. Every stage uses min(fixed cap, remaining) and the original absolute deadline. There is no second source admission owner.

`migration_coordinator._fixture_tick(session,registration)` is an inactive private harness boundary. The harness owns fixture creation, closure, fsync, sealing and lifetime. The driver opens/reads the job before source selection, regenerates pending from its original cursor, prepares before any exact write, and reuses the first ephemeral export in that tick. It calls actual `import_batch` twice identically: after the first confirmed success, the second must be an existing replay, executing full native `_verify_batch` and exact expected proof-ID-set comparison. Generic first append success cannot ACK. There is no host proof paging, physical incoming-row hash comparison, whole-owner hydration, remembered verification state or body spool.

Finalization additionally compares actual `bulk_owner` manifest exactly and records its dataset version. The subsequent original `receipt(namespace,key)` API has no pinned-version parameter; its independent digest/original receipt is compared exactly. No later version-capable page API is used. Stage-only intervals omit owner lookup. ACK follows only after current-tick checks and a final session-ready check. Unavailable/not_initialized/not_found/index/maintenance/preemption/deadline outcomes never mean completion. Recording a refusal is another ordinary stage only if the same session remains ready; no post-deadline cleanup lease exists. When preemption closes admission, the returned refusal and durable pending interval preserve recovery without attempting a late write.

Registration and this private fixture call do not qualify or authorize production movement. The later adapter surface remains full source binding, validated versioned cursor and deterministic bounded export result/phase/count/coverage/staging semantics. No native profile/descriptor/registry was added.

## Test-first commands and all observed failures

`PY=/Users/ladislavbihari/.echelon/venv/bin/python`; pinned ruff is in the same venv. Every pytest command used `scripts/safe_brain_tests.py --noconftest`, explicit clean-host files, fixed outer timeout and actual guarded fixture/source/queue/exact workers where noted. No repository-wide/legacy host-import suite ran. No broad passing native suite was repeated. Root approved each storage scope before launch.

Initial RED/GREEN (logs all `/tmp/castle-task3b2a-*.log`):

```sh
PY scripts/safe_brain_tests.py --timeout 15 tests/test_migration_codec.py --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_semantic_runtime.py tests/test_migration_coordinator.py -k 'migration_source or module_is_inactive' --noconftest -q
PY scripts/safe_brain_tests.py --timeout 20 tests/test_migration_coordinator.py -k queue_prepare_restart --noconftest -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_migration_coordinator.py -k append_requires --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_migration_coordinator.py tests/test_semantic_runtime.py -k 'append_requires or module_is_inactive or migration_source' --noconftest -q
```

- `codec-red.log`:2 missing-module failures; `codec-green.log`:2passes. Stable request identity/digest, strict schemas, body/metadata/scope/descriptor sentinel absence.
- `runtime-red.log`:2 failures for absent source session method/coordinator module; `tick-red.log`:1 absent-coordinator failure. `runtime-green.log`:3passes, actual shared5s clock/fixed caps/order and exactly one ephemeral source output reused after prepare.
- `queue-red.log`:1 failure for absent operation; `queue-green.log`:1pass in1.51s. Fresh guarded workers reopen metadata, identical prepare/ACK idempotency, changed intent conflicts, frontiers/counters/reference once, body sentinel absence and existing Task2 register/status compatibility.

Native interruption qualification:

```sh
PY scripts/safe_brain_tests.py --timeout 45 tests/test_migration_coordinator.py -k real_worker_restart --noconftest -s
CASTLE_TEST_MIGRATION_RETAINED=/private/var/folders/sv/07gg7rcs7gg7rl7s19f3xpsc0000gn/T/pytest-of-ladislavbihari/pytest-524/test_real_worker_restart_expor0/generation PY scripts/safe_brain_tests.py --timeout 15 tests/test_migration_coordinator.py -k retained_original --noconftest -s
```

`restart.log` is **1 failed test in12.16s**, not an all-green test claim. All preceding real state-machine subchecks passed: discard after export; postprepare/prewrite with no exact artifact; committed batch with lost response leaves same pending; interruption after owner and original live checks leaves frontier/counts unchanged; real ACK commit with lost response reopens live1/members9/references1/semantic_pending1; identical old ACK returns original result without recount. The final standalone assertion guessed namespace `remember` instead of original `operator`, returning not_found then KeyError. Inspection of existing `MemoryStore.remember`, exact worker signatures and original source keys also caught a trailing unused test argument `key` instead of `request_id`. Only these test calls were corrected. The successful interruption sequence was not rerun.

`receipt-fix.log`: **1pass in1.90s** on the explicitly retained already acknowledged disposable dataset, only two bounded exact operations: original operator/nine receipt and identical original remember retry; byte-sentinel/clean-host checks passed. Existing pure prepare_remember supplies established namespace/request_id/digest/receipt. Original failure remains recorded separately.

Frontier/coverage qualification and actual preemption:

```sh
PY scripts/safe_brain_tests.py --timeout 85 tests/test_migration_coordinator.py -k 'real_no_content or real_multibatch or real_empty_history' --noconftest -s
CASTLE_TEST_MIGRATION_PROTOCOL=/private/var/folders/sv/07gg7rcs7gg7rl7s19f3xpsc0000gn/T/pytest-of-ladislavbihari/pytest-525/test_real_empty_history_audit_0 PY scripts/safe_brain_tests.py --timeout 30 tests/test_migration_coordinator.py -k retained_protocol --noconftest -x -s
```

`frontiers.log`: **3passed/1failed in33.93s**. Empty inventory performed no exact call/artifact and ACKed scan exhaustion. Orphan inventory refused incomplete/orphan_chunk without an exact artifact/frontier advance and durably recorded orphan1. Large exact metadata produced multibatch staging; lost staged reply retained pending, source/owner remained invisible, checked replay ACK advanced staging alone, finalization later advanced completed frontier/reference once and exact original historical hydration passed. Fixture pruning happens only before sealing; it is now a test helper, never a product/source mutation.

The fourth protocol fixture acknowledged3 real historical occurrences (including one true zero-member occurrence) and5 AUDIT owners, then **legitimately refused background_preempted** during the next first import at0.5885s. Source/prepare had succeeded; no ACK was attempted. Original pending/cursors were retained. There was no RSS/deadline failure, no increased-budget retry and no fixture reconstruction. The run had already launched when root asked for -x; this was the final selected case, so no later case ran after failure. Immediate inventory showed no worktree worker; root separately verified interactive_waiting=False and no admission/priority holders before authorizing only the remaining work.

`preemption-recovery.log`: **1pass in13.08s**. The test checked priority immediately before starting, reconstructed exactly the original descriptor from retained metadata/stat without resealing/writing, asserted pending/history3/audit5, and continued only five remaining AUDIT units plus no-content done. Final state is `snapshot_export_exhausted`, pendingnull, staging phase done, completed frontier the last history_staged_rows AUDIT key; counts live0/history3/audit10/members2/gaps1/repaired_gaps1/pending_stages1/orphans0, distinct ownerrefs13/semantic_pending2, coverageincomplete. Thus repaired occurrence is counted once, repair AUDIT is separate, the real empty occurrence is no_members, and staged8KiB text never becomes canonical evidence.

Actual proof and source boundaries:

```sh
PY scripts/safe_brain_tests.py --timeout 40 tests/test_migration_coordinator.py -k 'real_proof_damage or real_source_replacement' --noconftest -x -s
```

`proof-boundaries.log`: **4passes in13.13s**. Dedicated fresh fixtures remove a physical canonical row, remove/re-hash a proof entry, or replace a valid page proof with an unexpected valid page ID of the same kind/count and recomputed local hash. Actual identical import replay refuses corrupt before ACK, keeping the exact pending interval, both frontiers and zero owner counts/references. The replacement-ID fixture first seeds original visible legacy `record` rows, then completes actual repeated import/owner/original-nine-receipt checks before an injected preACK stop, proving semantic reuse without naïve incoming bulk_record physical hashes. Source replacement is intentional tampering only of its dedicated disposable fixture after prepare; no new manifest is blessed. It returns stale/source_identity_changed with same pending/frontiers and no destination artifact. All committed artifacts are retained for recovery evidence.

Final pure/queue guard RED/GREEN:

```sh
PY scripts/safe_brain_tests.py --timeout 15 tests/test_migration_codec.py tests/test_semantic_runtime.py -k source_response --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_migration_coordinator.py -k 'changed_original or immutable_registration or orphan_refusal_return' --noconftest -q
PY scripts/safe_brain_tests.py --timeout 10 tests/test_migration_coordinator.py -k queue_orphan_scan --noconftest -x -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_migration_codec.py tests/test_migration_coordinator.py tests/test_semantic_runtime.py tests/test_sqlite_export_codec.py -k 'not (queue_prepare_restart or queue_orphan_scan or real_worker or real_no_content or real_multibatch or real_empty_history or real_proof_damage or real_source_replacement or retained_)' --noconftest -x -q
```

- `validation-red.log`:2 failures exposed understated advertised source frame bytes accepted and source response validation completing at5s still returning ok. `validation-green.log`:2passes after exact accounting/postvalidation deadline checks; same limits.
- `refusals-red.log`:1pass/2failures exposed same-job rebind raising instead of explicit conflict and compact orphan refusal return omitting the already durable orphan count. `refusals-green.log`:3passes after those narrow response fixes. Changed original live receipt/manifest already refused correctly. Pending body/packing/binding changes, prepare failures, not_initialized/not_found/corrupt/stale/index_required/maintenance_limit and late owner success are covered by pure host decision tests; none ACK, page proof, rebuild index or create another session.
- `orphan-ack-red.log`:1 failure showed a private scan ACK could accept an already observed orphan despite correct coordinator refusal. Added the explicit orphan predicate. `orphan-ack-green.log`:1pass in0.46s, ACK conflict, refused/orphan1, unchanged frontiers, no lastACK/pending. No extra destination qualification was needed for these pure/queue-only guards.
- `pure-affected.log`:41passes before final guards. **`pure-final.log`:46passes**, engine-free host, includes existing pure source refusal/lineage and runtime deadline/admission/preemption coverage plus all final pure coordinator/codec checks. This final pure selection is justified by the subsequent guards/formatting; no previously passing broad native suite was repeated.
- First scoped ruff run found test fixture complexity31>25 after inline pruning. Extracted only the test pre-seal helper; scoped ruff check/format and git diff --check now pass. No behavior/cap workaround. No model/provider/network service was used. Final process inventory showed no remaining worktree worker/guardian/test process.

## Measured bounded fixture evidence

All metrics are actual supervisor samples, not kernel ceilings. Every worker is a fresh process. Queue mutation/read stages and source regeneration/replay/owner/live checks all share the tick's absolute5s deadline. Controlled-clock tests also prove source2/exact read2/write3 and queue2/3 fixed caps, absolute deadline propagation, postvalidation expiry and no postdeadline/preemption cleanup stage.

| Scoped log | Max tick elapsed | Source max elapsed/task/aggregate | Queue max elapsed/task/aggregate | Exact max elapsed/task/aggregate |
| --- | --- | --- | --- | --- |
| restart |3.2369s|0.1205s /48,250,880B /90,619,904B|0.1133s /48,971,776B /91,504,640B|1.1774s /150,159,360B /192,610,304B|
| frontiers |2.5900s|0.2736s /51,625,984B /102,580,224B|0.1242s /49,168,384B /101,482,496B|1.0635s /155,631,616B /207,945,728B|
| preemption recovery |2.6216s|0.1053s /47,448,064B /91,701,248B|0.1174s /48,922,624B /93,159,424B|1.0114s /149,045,248B /192,970,752B|
| proof boundaries |2.9786s|0.1209s /48,463,872B /96,092,160B|0.1114s /49,135,616B /96,763,904B|0.9525s /151,420,928B /199,016,448B|

Maximum observed source ASCII response467,786B; live response124,824B. All stay under existing512KiB frames. The cold pending-live recovery path actually completed regeneration, two checked identical import calls, owner/live checks and committed ACK within2.9031s; the earlier source/prepare-only interruption was0.3319s. Whole new history/AUDIT source-through-ACK paths also completed within the table's bounds. These measurements qualify only the small protocol fixtures.

Observed intentional statuses: orphan incomplete; three corrupt proof refusals; stale replaced source; stage/owner prepublication not_found; injected lost destination/ACK responses; one actual background_preempted. The mistaken namespace's standalone not_found and resulting failed assertion are disclosed above. No observed worker/parent/aggregate memory limit, heap, pressure or deadline refusal occurred. Pure injected deadline/index/maintenance refusals remain explicit and unchanged. No retry loop, automatic maintenance, source write or new lease was introduced to bypass a refusal.

## Remaining gates and handoff

- Task3b2b still owns pinned raw archive continuation/descriptor/cursor/profile and reconciliation of original historical attempts/raw transitions across shards. This SQLite keyset frontier is not a raw archive continuation or corpus coverage proof.
- Task3c must supply production snapshot/WAL/concurrent append consistency, genuine capacity reservations/retention/release policy, independent cross-store reconciliation, full52MiB destination finalization/all slices, sustained throughput, scope-only deltas, scalable lookup/index maintenance and real movement authorization. None is supplied or inferred here.
- Existing1024 unindexed-row/32-fragment tail and16384-row explicit maintenance bounds remain unchanged. Root's separate262144-ID BTREE build failed192MiB task cap (209,240,064B sampled versus201,326,592B); these tiny disposable fixtures do not overturn that scale gate or claim corpus readiness.
- Task3d must lazily expand semantic owner membership and validate exact hydration/exposure/full scope eligibility before groups; existing Task2 semantic_intents (1–2groups/at most9 live IDs) is unchanged. No model/vector work or semantic completeness is claimed. Task4 still owns public policy/scope projection.
- The queue can record current-tick proof metadata but cannot independently certify Lance. Interrupted verification always restarts completely. Durable artifacts and pending intents are not automatically deleted. If a future complete bounded verification cannot finish within the unchanged5s tick, it must remain pending with measured qualification evidence, not acquire durable partial proofs or larger limits.
- Root owns independent review and integration. No push.

Scoped commit SHA and final verification are recorded below after commit.

Commit: **`253227ffa10dcd35a3b737ef19cd7e04a9913845`** — `feat: add inactive durable SQLite migration coordination`.

Final precommit pinned ruff check, ruff format --check (all11 scoped files), unstaged and staged git diff --check passed. The11-file commit contains only the6 scoped product modules and5 test modules described above. Report is excluded. Postcommit worktree status is clean; no push. Root owns independent review.
