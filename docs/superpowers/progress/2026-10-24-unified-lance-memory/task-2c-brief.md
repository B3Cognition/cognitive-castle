# Task2c — integrate durable exact publication and bounded semantic indexing

Read this first: requirements for final Task2 substep. Base7fab79c; Task1 exact
store, Task2a staged model and Task2b queue/vector primitives independently reviewed.
This delivers an inactive working pipeline; production routing/migration remain
Tasks3/4/5. No whole-goal completion claim from fixtures.

## Own work

Create focused `semantic_indexer.py` and, if useful, `semantic_intents.py` plus
their tests. Extend exact store/worker only for read-only durable receipt lookup;
extend semantic_store_worker/queue for intent operations; extend semantic_runtime
and memory_runtime for fixed storage stages and background preemption. Cover those
changes with focused tests. Do not refactor unrelated modules, change current
public routes/installed checkout/services, access real palace or delete originals.
No subagents. Root handles review and native-slot coordination.

## Resource/trust contract

Only trusted internal code selects generation path, offline pinned profile and
namespace/scopes. No public model paths, commands, budgets or providers. Host and
test host import no native/model/SQLite storage runtimes; workers do storage.
One shared admission and absolute5s lifetime spans background/query semantic
work; model stages512/640MiB. Native exact/vector stages192/256,read2s/write3s;
queue-only128/192,read2s/write3s. Each stage uses min(remaining,its fixed cap).
Standalone exact-publication workflow has a3s absolute budget across intent,
exact append and coordination; no model work there. Existing production budgets
and dispatch remain unchanged. Preserve pressure refusal and descendant cleanup.
No higher-resource retry, no permanently resident process/model, no SQLite text.

Reuse SemanticSession admission/absolute deadline and fixed executables. Expose
only internal methods selecting the exact/store worker from fixed operations;
do not introduce a second scheduler or caller-selected process command. A shorter
exact-workflow deadline may be imposed internally; callers cannot increase limits.

## Exact publication -> durable semantic intent

Provide an internal exact remember/publication workflow preserving the original
canonical IDs, caller provenance, receipt/hash and replay/conflict semantics.
Before committing exact content, durably record a bounded coordination intent
containing request namespace/key/digest, expected canonical references/scopes and
index profile. Store no source body, raw token arrays or vectors in SQLite.
Then publish through exact Lance. Only a verified durable exact receipt authorizes
registration of index groups (<=8refs each; remember can yield9chunks). Group keys
are deterministic. Queue acknowledgement/intent completion after exact publication
is idempotent. A successful exact commit must survive loss of its response or
loss of later SQLite acknowledgement; recovery must not need the original caller
body. Add bounded read-only exact receipt lookup that validates stored receipt
and referenced records, reusing existing replay proof logic rather than bypassing
it. Intent recovery compares the expected digest/IDs/source hashes before queueing.

If time expires after exact commit, retain the intent for recovery; never claim
semantic publication occurred. Exact receipt success may report pending durable
intent if model/queue work is pending. If no exact receipt exists, don't advance
intent or source checkpoint. A reused key with changed content/scopes conflicts.
Return explicit exact/semantic pending status without silently treating index lag
as failure of the already committed text. Later capture integration uses this same
protocol; do not wire current capture in this task.

## Bounded background index driver

Implement one-tick `index_one`/equivalent: recover bounded pending intents, select
a fair queue group, hydrate the ENTIRE ordered exact source/ref/scopes set and
verify text/exposure/input/reference bindings, tokenize its current continuation,
infer at most32windows, publish vector+receipt, recover/verify durable receipt,
then acknowledge queue progress. Only contiguous verified publications complete
the group. Preserve per-source scopes. Use existing PROFILE_ID/model/tokenizer;
no historical-vector compatibility guess. Terminal page is enumeration exhausted,
not proof that prior pages exist. Lost response after vector commit must recover
without requiring another inference. Failed/refused phases retain last durable
position and an honest reason; a spent deadline cannot launch cleanup work with
a new budget. Returned group/phase/progress and resource metrics are bounded.
The queue's3new:1history page fairness remains; new facts must progress while an
old long group is incomplete. No native worker may spawn another worker.

Add trusted optional background preemption to the existing supervisor, default
unchanged for ordinary callers. A LIVE interactive waiter arriving during a long
background stage must make it stop/kill/reap and release admission promptly enough
for existing0.5s interactive admission. A stale marker file alone does not count.
Use the existing priority/admission inode, never a second lock/scheduler or a
longer public wait. Model/vector interruption is replay-safe via receipts.

## End-to-end fixture proof

TDD with scripts/safe_brain_tests and separately supervised workers. Pure/fault
fixtures cover request conflict; intent before exact commit; exact commit with
lost response; queued registration/intent-ack interruption; vector commit with
lost response; duplicate retries; stale source/profile/scope; continuation+total
consistency; deadlines across ALL stages; refusal preserving state. Reopen fresh
processes to prove recovery. New code never silently reads SQLite canonical text.

Actual pinned offline model fixture: store multiple exact sources through the
new publication path, drive indexing, then embed a Czech/German/Spanish paraphrase
with SemanticSession and query actual Lance nearest to recover the expected exact
source/hash after restart. Include a new fact while history lane is pending and
a long-source final page; don't claim a synthetic test proves real corpus recall.
Query helper may remain internal/fixture until Task4 adds ordinary lexical/KG/
rerank/policy coordinator. Keep actual query embedding+Lance candidate retrieval+
bounded exact hydration under one5s deadline, not5s per stage. No public lexical
fallback pretending semantics succeeded. Tokenizer must not truncate long inputs.

Add a real supervised priority test: background worker starts, live interactive
waiter arrives, background is reaped and admission is acquired within existing
wait; preserve original process-cleanup/pressure tests. No actual model needed
for the priority fixture. Test-only admission backoff may handle normal capture
contention before a diagnostic; no production guard relaxation. Explicitly record
every resource/admission refusal and observed peaks/latency.

Coordinate native/model tests with root. Focus covering tests; no broad/repeated
suites absent a new concern. Use pinned ~/.echelon/venv/bin/ruff. Commit scoped
code/tests only, no push. Full report task-2c-report.md: interfaces, exact red/green
commands/results, failure recovery, metrics/refusals, files and limitations.
Return short status/commits/test summary/concerns/report path.
