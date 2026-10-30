# Task2c implementation report

Status: implemented and scoped verification green; inactive pending root-managed independent review. No production cutover or whole-goal completion claim.
Worktree: `/Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse`; base `7fab79c`.
Scoped commit: `bb9afee` (`feat: add durable exact outbox and bounded semantic index driver`).

## Scope and interfaces

- `semantic_intents.prepare_intent(PreparedRemember, scopes, lane)` prepares an immutable, bounded metadata outbox intent. It keeps namespace/key/request digest, expected exact receipt, ordered canonical IDs/source hashes/exposure hashes, per-source trusted scope, pinned profile and deterministic group keys. Remember's nine chunks split into groups of eight and one. SQLite receives no source body, token array or vector. `source_exposure_hash` preserves the existing full-source hash encoding without importing the legacy SQLite catalog.
- `SemanticQueue.intent_prepare`, `intents`, `intent_complete` are worker-only durable operations. Schema1->2 adds intents and an intent cursor to the existing schedule. Completed intents remain conflict witnesses. At most two pending intents are returned per call, with persistent rotation so abandoned pre-exact intents cannot starve later committed requests. Existing3new:1history page scheduling is unchanged. Group registration and intent completion commit atomically in one FULL-synchronous SQLite transaction; retries preserve existing positions.
- `LanceExactStore.receipt(namespace,key)` and the fixed `lance_exact_worker` receipt operation perform bounded read-only durable lookup. Append replay and lookup call the same extracted `_verify_receipt` proof: bounded IDs, exact record/provenance validation, concatenated text hash/bytes, canonical receipt encoding, and request digest recomputed from durable content/key. This supports nine-chunk remembers and preserves the eight-source import ceiling.
- `SemanticSession.exact(directory,operation,arguments)` and `.store(...)` select only fixed internal worker allowlists/executables. Model stages remain512/640MiB. Native exact/vector stages are192/256MiB with read2s/write3s caps; queue stages128/192MiB with read2s/write3s caps. `queue_intents` is a write stage because it rotates the existing durable schedule cursor. Every stage uses min(remaining,cap), and the same absolute5s deadline/admission spans the session. Host codec/coordinator imports load no native/model/SQLite runtime.
- `with ExactPublication(generation) as publisher: publisher.remember(request_id,text,provenance,scopes=...,namespace=...,lane=...)` uses a fixed3s absolute workflow budget. It durably prepares intent before exact append, then verifies the durable exact receipt and entire expected source/reference sets before completing intent/queue registration. An exact success reports `exact_status=committed`, the original receipt, `semantic_status=pending`, and explicit `intent_pending`/reason when coordination cannot finish. Unconfirmed/lost exact responses retain the intent for recovery; changed body/scopes conflict.
- `recover_intents(session,generation)` checks at most two pending intents, comparing expected digest, IDs, exact receipt, source/exposure hashes and full ordered input bindings before registration. Missing exact proof never advances the group or a source checkpoint. Corrupt intent frames stop with explicit `invalid_durable_intent`.
- `index_one(session,generation)` recovers intents, selects one fair queue group, hydrates the entire ordered exact source set, checks source/exposure/input/reference/profile bindings, and checks the durable vector receipt before tokenization. If absent, it tokenizes the current continuation, infers <=32 windows, publishes vector+receipt, reads/verifies the durable receipt and acknowledges contiguous queue progress. A committed receipt avoids all later inference on replay. Terminal enumeration alone never completes missing prior pages. Refusal leaves the last durable position and returns phase/reason/resources. After a spent deadline, `_ready` prevents any further worker launch.
- `query_exact(session,generation,text,scope,allowed_source_hashes=...)` is an internal fixture/helper. Query tokenization+inference, actual Lance nearest and exact hydration use the same5s session; result IDs/hashes/exposure are rechecked. It accepts a single semantic query window and returns an explicit limit/unavailable outcome otherwise. There is no lexical fallback and no ordinary/public coordinator wiring.
- `_supervise(..., background_preempt=False)` defaults to existing behavior. Trusted background sessions opt in. It tests the existing live advisory priority lock during running supervision, kills/reaps through the existing process-group cleanup, then releases the admission descriptor promptly. A stale marker inode does not count. No second admission lock/scheduler, longer public wait, permanent model process or worker-spawned worker was introduced.

No current public routes, capture integration, service, installed checkout, real palace, original transcript, profile, provider or production budget changed. No dependency installation, download or push occurred. Root coordinated the native slot; no subagents were used.

## Red/green evidence

Commands below use `/Users/ladislavbihari/.echelon/venv/bin/python` (`PY`) and pinned `ruff` at the same venv.

1. `PY scripts/safe_brain_tests.py --timeout 30 tests/test_semantic_indexer.py -k 'body_free or fixed_stage'`: RED2 failures, missing `semantic_intents` and fixed session storage methods. After codec/stage implementation, both passed.
2. `... -k 'body_free or fixed_stage or recovers_committed'`: RED1 missing driver import, then GREEN3 tests.
3. `... -k live_interactive`: the first fixture attempted the global admission while capture held it and got `BlockingIOError`. The fixture was isolated to one private test admission/priority inode shared by both test processes; no production guard changed. The next RED exposed absent preemption support. The supervised GREEN confirms live waiter acquisition <0.5s and dead background PID; stale marker remains inactive.
4. `PY scripts/safe_brain_tests.py --timeout 45 tests/test_semantic_indexer.py -s`: initial GREEN6 passed in6.33s, guard aggregate peak182.7MiB.
5. `... -k 'refused_stage or stale_bindings or query_helper'`: RED missing query helper; the11 refusal/stale tests already passed. After helper implementation, pure focused selection GREEN15 tests.
6. `... -k host_imports`: RED showed transitive `sqlite3`/`_sqlite3` through legacy `unified_memory`; pure exposure encoding and deferred supervised queue imports fixed it. Focused pure selection GREEN16 tests.
7. `... -k uncommitted_old`: RED demonstrated first-two-intent starvation. Existing durable schedule cursor rotation fixed it.
8. `PY -m pytest -q tests/test_semantic_indexer.py -k query_validation_cannot --disable-warnings`: RED successful result could finish after final hash validation spent the deadline; final deadline check fixed it. `-k 'query_validation_cannot or query_helper'`: GREEN2 tests.
9. `PY -m pytest -q tests/test_semantic_indexer.py -k corrupt_pending_intent --disable-warnings`: RED raised on a malformed durable intent; bounded validation now returns an explicit corrupt recovery phase. `-k 'corrupt_pending_intent or query_validation_cannot'`: GREEN2 tests.

Additional native tests cover intent-before-exact, absent exact proof, exact lost response, read-only receipt corruption, lost atomic intent completion reply, repeated publication, vector lost reply with no model/profile needed, and queue completion after a lost acknowledgement. Pure tests cover body/scope conflict, ninth chunk grouping, fixed budgets across every storage phase, stale source/profile/scope/input/total, refusal phase preservation, exact success despite late coordination refusal and preemption releasing admission permanently for that session.

## Actual pinned model fixture and refusal history

Manifest selected only by the trusted test environment:
`/Users/ladislavbihari/.castle/backups/durable-memory-20261024/relocation/semantic-models/e8f8c211226b894fcb81acc59f3b34ba3efd5f42/profile.json`.
Profile remains `a1fdc081cd5709ddda44d2c644a24cf0658198690f93a7b68d376b3c0edb0120`.

The fixture publishes eight exact facts through the new outbox path, starts fresh supervised workers for every stage, indexes actual pinned embeddings into actual Lance, publishes a long history group of64 windows, adds a new fact after the history group's first32 windows, completes the new fact before the history tail, and verifies final contiguous position64. Fresh query sessions embed Czech/German/Spanish paraphrases, use actual Lance nearest, and recover the expected original canonical source/hash.

Every refusal is retained in fixture output. Earlier exploratory runs:

- An accidental invocation without `CASTLE_TEST_SEMANTIC_PROFILE` skipped the model fixture; it supplied no semantic proof.
- `/tmp/castle-task2c-e2e.log`: eight small groups completed in3.65–4.13s. Long page vector publication/verification succeeded, but ACK response exceeded5s: `worker_deadline`, reported position0. Test's strict single-tick assumption failed; guard475.5MiB,58.79s test duration. No caps increased.
- `/tmp/castle-task2c-e2e-resume.log`: history reached32/64; new fact completed first. Tail ACK committed but response crossed5s, reported position32; next tick was correctly idle because queue completion was already durable. Test was corrected to verify completed queue status after this possible ACK-loss boundary; guard468.3MiB,69.94s.
- `/tmp/castle-task2c-e2e-final.log`: actual eight-fact/history/fairness/three-query behavior all passed. One small-fact receipt-verification stage returned `worker_deadline` at5.0029s; next tick recovered its receipt without inference in1.8757s. Query times2.1080/2.0579/2.0584s. Final test-host import assertion failed because repository `tests/conftest.py` imports the legacy SQLite knowledge graph before tests. Product fresh-host import proof remained clean. Guard480.1MiB,73.20s. Final qualified command uses `--noconftest`, preserving built-in pytest temporary fixtures, HOME isolation, supervision, pressure checks, all production caps and the no-SQLite host assertion.

## Limits and next tasks

This proves inactive durable pipeline mechanics and recall for a small synthetic multilingual fixture only. It does not prove whole-corpus semantic coverage,120s freshness under a real backlog, migration completion, installed behavior, broad recall quality, reranker quality, ordinary policy coordination or production routing. Those remain Tasks3–6. Cold small-group ticks cost several seconds; future capture/migration throughput must batch confirmed references up to8 per group rather than invoke one cold model/storage pipeline for each small fact. This substep deliberately adds no scale optimization or budget increase.

RSS evidence is a sampled tripwire including guardian/descendants and host, not a kernel-enforced allocation ceiling; transient peaks are possible. Committed metadata is retained for idempotency/conflict proof. An intent with no durable exact receipt remains pending and cannot recreate text: recovery intentionally needs no original body and cannot invent an uncommitted exact publication. Both genuinely uncommitted and already-committed-but-lost ACK outcomes remain distinguishable through fresh durable status/receipt reads.

## Final verification and metrics

Qualified actual-model command (GREEN):

```sh
CASTLE_TEST_SEMANTIC_PROFILE=/Users/ladislavbihari/.castle/backups/durable-memory-20261024/relocation/semantic-models/e8f8c211226b894fcb81acc59f3b34ba3efd5f42/profile.json /Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 150 tests/test_semantic_indexer.py -k actual_pinned --noconftest -s
```

Result: **1 passed,28 deselected in71.06s**, guarded aggregate peak475.3MiB,71.3s elapsed. Log `/tmp/castle-task2c-e2e-cleanhost.log` contains all stage resources and final `PIPELINE_EVIDENCE` JSON. No admission, pressure or RSS refusal occurred in this final qualified run. All host SQLite/native/model import assertions passed. Model stages peaked452,313,088B task /498,368,512B aggregate host+task (431.36/475.28MiB). Ten exact publications used2.0924–2.8343s summed supervised phase time (plus small bounded codec/coordination overhead). Eight small fact ticks used3.1786–3.7392s; history first/tail32-window pages4.5349/4.5286s; newly added fact3.7168s while history remained pending. Czech/German/Spanish complete query+Lance+exact hydration used2.1186/2.5881/2.0527s. Every query returned the expected canonical ID and exact hash after worker restart.

Real live priority fixture in scoped regressions: interactive admission acquired in0.035304s; background task reaped; background stage elapsed0.1271s and peak35,225,600B task/82,083,840B aggregate. Marker inode existed stale before work began and remained inactive after the live waiter closed. The default ordinary supervisor behavior remained unchanged.

Scoped regression command:

```sh
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 240 tests/test_semantic_indexer.py tests/test_semantic_runtime.py tests/test_memory_runtime.py tests/test_lance_exact_store.py tests/test_semantic_queue.py tests/test_semantic_store_worker.py -k 'not actual_pinned' -s
```

Result: **107 passed,10 failed,1 deselected in85.70s**, guard aggregate208.1MiB,86.0s. Log `/tmp/castle-task2c-regressions.log`. All10 failures were original `test_memory_runtime.py` diagnostics:

- `test_admission_is_per_user`
- `test_exact_store_survives_worker_invocations`
- `test_output_and_time_boundaries[print("x"* (512*1024+1))-worker_output_limit-2]`
- `test_output_and_time_boundaries[print('{"status":',end="")-worker_invalid_frame-2]`
- `test_output_and_time_boundaries[import time;time.sleep(5)-worker_deadline-0.35]`
- `test_complete_chain_resources_and_maximum_remember_frame`
- `test_owned_descendants_die_before_admission_released[host]`
- `test_pressure_change_stops_worker`
- `test_live_total_budget_rejects_before_sidecar_open`
- `test_ingest_and_status_dispatch_only_trusted_paths`

Traces show `BlockingIOError` or explicit `memory_busy`, with downstream missing receipt IDs/PID files. The admission owner was not captured at the collision; post-run `lsof` found no holder. Therefore the source is not conclusively attributed to live capture or a fixture. Product contention refusals are preserved, and no production guard/admission semantics was changed. The root received the native slot between this run and any affected-only rerun; no worktree native descendants remained. The107 passing tests were not repeated. After returning the native slot to root for its independent reranker baseline and receiving the slot back, the affected-only original-semantics command was:

```sh
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 60 tests/test_memory_runtime.py --lf -s
```

Result: **10 passed,24 deselected in2.16s**, guarded aggregate114.5MiB,2.4s. Log `/tmp/castle-task2c-failed-only.log`. There was no test backoff, monkeypatch of original admission semantics, production guard relaxation or budget increase. A separate bounded read-only lsof/ps monitor observed the same global admission inode throughout this targeted rerun; all observed holders were expected diagnostic host/guardian/worker processes, with no external holder. This cannot retrospectively identify the first run's lock holder, so those10 original refusal failures remain explicitly recorded and unattributed. Monitor log `/tmp/castle-task2c-admission-owners.log`. The diagnostic monitor was stopped after the run, and process inventory showed no worktree guardian/model/storage children. Native slot was released to root promptly.

Combined result: **117 distinct focused regression tests passed**, plus the separately run **1 actual pinned-model/Lance end-to-end fixture**. The117 include existing pressure, descendant cleanup, slow preflight, IPC/deadline, exact replay/corruption, queue continuity/fairness and worker boundary tests. No full-suite success is claimed.

Pinned `ruff check` and `ruff format --check` on the ten scoped code/test files passed; `git diff --check` passed. No full repository suite was run, per the explicit focused-test instruction.


## Files and self-review

Scoped code/tests only:

- `cognitive_castle/semantic_intents.py`
- `cognitive_castle/semantic_indexer.py`
- `cognitive_castle/lance_exact_store.py`
- `cognitive_castle/lance_exact_worker.py`
- `cognitive_castle/semantic_queue.py`
- `cognitive_castle/semantic_store_worker.py`
- `cognitive_castle/semantic_runtime.py`
- `cognitive_castle/memory_runtime.py`
- `tests/test_semantic_indexer.py`
- `tests/semantic_intent_fixture.py`

Self-review checked the canonical receipt extraction against the former inline replay proof, schema1 migration/read-only behavior, atomic outbox registration/completion, deterministic scope-bound group identities, resource stage allowlists/caps, final query validation spending the deadline, preemption cleanup/release, both vector and queue ACK lost-response boundaries, no SQLite canonical text, and no public dispatch/capture/service changes. Corrected issues were exposed by the red cases above. Root owns independent review and downstream integration. Report is a local task artifact; it is not included in the scoped code/test commit.

## Independent review fix round1 — pressure-probe preemption

Review: `task-2c-review.md`, Important finding: initial supervisor preflight and a running-stage synchronous pressure probe could consume the entire existing0.5s interactive admission wait after the last live-priority check. Verified against the actual `_pressure_ok` helper: `subprocess.check_output` accepted up to0.5s, killed/reaped on timeout, and `_stage_pressure_reason` had no post-probe priority check. Initial `_supervise` preflight bypassed that stage helper entirely.

Fix scope: `cognitive_castle/memory_runtime.py` and new `tests/test_memory_preemption.py` only. No guardian helper change was necessary. For trusted background work, preflight and periodic pressure probes now use min(stage remaining,50ms) through the existing deadline-aware helper, with the existing live advisory priority lock checked before and after each probe. Probe failure/short-probe exhaustion with no live waiter remains fail-closed `system_pressure_unavailable`; an exhausted absolute stage deadline remains `worker_deadline`. A live waiter yields `background_preempted` after the pressure subprocess has been killed/reaped. Existing supervisor process-group cleanup/reaping still precedes admission release. Ordinary callers still invoke the former `_pressure_reason(until,_pressure_ok)` unchanged. No scheduler, admission inode, ordinary wait, model profile, production stage/session deadline, RSS cap, service or public route changed.

RED commands:

```sh
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_memory_preemption.py --noconftest -s
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_memory_preemption.py -k exhaustion --noconftest -s
```

The first produced **2 expected failures in1.49s**: a warmed real interactive process arrived inside the already-entered pressure helper, took the live priority lock, and the actual helper launched a real delayed probe subprocess with its original0.5s timeout. Preflight and periodic waiters returned `memory_busy` at0.502017/0.501657s; periodic background elapsed0.7641s, peak35,291,136B task/71,335,936B aggregate. Probe and any launched worker were reaped before the eventual admission release, but too late for the waiter. Guard aggregate106.9MiB. Log `/tmp/castle-task2c-pressure-red.log`. The pure short-probe exhaustion RED returned `worker_deadline` after consuming the former whole budget instead of a fail-closed bounded pressure refusal.

GREEN commands:

```sh
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_memory_preemption.py --noconftest -s
/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 30 tests/test_memory_preemption.py tests/test_memory_runtime.py tests/test_semantic_runtime.py tests/test_semantic_indexer.py -k 'pressure or preflight or live_interactive_waiter or session_releases' --noconftest -s
```

First: **4 passed in0.60s**, guard92.8MiB/0.8s. Real preflight/periodic interactive admission acquired in0.070464/0.062874s with probe timeouts approximately50ms. The extra pure cases prove fail-closed short-probe exhaustion and preservation of a shorter absolute deadline.

Final affected-only qualification: **12 passed,62 deselected in1.14s**, guard94.7MiB/1.3s. This includes the4 new cases and8 existing pressure/preflight/priority checks. Preflight/periodic admission0.070386/0.070758s; periodic background elapsed0.315s, peak35,209,216B task/73,990,144B aggregate. Existing sleeping-worker priority test acquired in0.029069s, background peak35,307,520B task/74,153,984B aggregate. Both delayed probe subprocesses and any launched dummy worker were confirmed absent before admission release. Preflight launched no storage/model worker. All intentional RED `memory_busy` and timed-probe pressure refusals remain recorded; no unexpected pressure/RSS/admission refusal occurred in GREEN. Logs `/tmp/castle-task2c-pressure-green.log` and `/tmp/castle-task2c-pressure-regression.log`.

Pinned `ruff check`, `ruff format --check` on both scoped files and `git diff --check` passed. The prior117-test and actual-model E2E qualification was not repeated; only affected checks were rerun. Process inventory showed no worktree guardian/model/store children, and native slot was released to root before report/commit finalization. This closes the reviewed timing gap subject to root-managed independent re-review; sampled timing evidence does not claim an OS-level real-time scheduling guarantee.

Fix commit: `d4d6850` (`fix: bound background pressure probes for live priority`).
