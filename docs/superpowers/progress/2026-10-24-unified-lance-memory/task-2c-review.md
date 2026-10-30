### Spec Compliance

- ❌ Issues found: live background preemption does not cover a synchronous pressure probe already in progress. The probe can occupy the complete 0.5-second interactive admission window before the background session can reap/release admission (`cognitive_castle/memory_runtime.py:318`; detailed finding below).
- ✅ The inspected durable publication and indexing paths implement the task's intended inactive protocol: body-free intent before exact append, verified exact receipt before group registration, atomic idempotent registration/completion, full ordered source binding, durable vector recovery before inference, and fixed shared stage budgets (`cognitive_castle/semantic_indexer.py:46`, `cognitive_castle/semantic_indexer.py:97`, `cognitive_castle/semantic_indexer.py:139`, `cognitive_castle/semantic_queue.py:393`, `cognitive_castle/semantic_runtime.py:204`).
- ⚠️ Cross-task boundaries remain unverified: actual migration/capture wiring, ordinary public routing/policy coordination, real-backlog throughput/freshness, broad corpus recall, and production activation. These are deliberately outside Task2c; the actual multilingual fixture does not establish them. No public route/service changes appear in the reviewed package.

### Strengths

- Durable exact lookup reuses the same extracted replay proof as append rather than trusting receipt-shaped input; the proof checks canonical receipt encoding, durable records, provenance-derived request digest, and the ninth-chunk remember case (`cognitive_castle/lance_exact_store.py:212`, `cognitive_castle/lance_exact_store.py:329`).
- Intent metadata binds request identity, exact digest/receipt, ordered references, scopes, profile and deterministic group identities without storing source text. Completed intents remain conflict witnesses, while pending-intent rotation prevents abandoned requests from permanently hiding later recovery (`cognitive_castle/semantic_intents.py:14`, `cognitive_castle/semantic_intents.py:74`, `cognitive_castle/semantic_queue.py:414`).
- Indexing hydrates the complete reference set and verifies a stored vector receipt before invoking tokenization/inference. Acknowledgement follows receipt/profile/input/reference/start/total validation; lost vector responses can resume without loading a model (`cognitive_castle/semantic_indexer.py:17`, `cognitive_castle/semantic_indexer.py:166`, `cognitive_castle/semantic_indexer.py:215`). The focused unchanged vector proof checks confirmed that durable receipts also validate compact records against exact sources and scopes (`cognitive_castle/lance_vector_store.py:432`, `cognitive_castle/lance_vector_store.py:478`).
- Fixed exact/storage entry points preserve stage RSS caps and pass the same absolute deadline to supervision; late exact coordination refusal is reported separately from an already confirmed exact commit (`cognitive_castle/semantic_runtime.py:100`, `cognitive_castle/semantic_runtime.py:204`, `cognitive_castle/semantic_indexer.py:124`).
- The tests include real separately supervised exact/vector lost-response recovery, a real live priority waiter with stale-marker checks, and actual pinned multilingual Lance retrieval after worker restarts. The implementation report clearly separates these from synthetic corpus coverage and records the initial admission refusals rather than suppressing them (`tests/test_semantic_indexer.py:95`, `tests/test_semantic_indexer.py:206`, `tests/test_semantic_indexer.py:443`, `tests/test_semantic_indexer.py:570`).

### Issues

#### Critical (Must Fix)

- None found.

#### Important (Should Fix)

- **Live priority can miss its 0.5-second window during pressure checking.** `cognitive_castle/memory_runtime.py:318` checks `_background_waiting` before calling `_pressure_reason`, then blocks until the pressure probe returns. The existing helper permits a synchronous `sysctl` call to consume 0.5 seconds (`cognitive_castle/brain_reader_guardian.py:15`). A waiter arriving immediately after that priority check cannot be observed until the probe finishes, after which killing/reaping the background process and closing its admission descriptor still take additional time. Initial `_supervise` preflight has the same uninterruptible probe. The interactive caller independently expires after 0.5 seconds (`cognitive_castle/semantic_runtime.py:59`), so a live waiter can receive `memory_busy` despite the new preemption support. This violates the task's explicit live-interactive preemption requirement; the current priority fixture only injects the waiter while the worker sleeps and does not exercise an in-progress slow probe (`tests/test_semantic_indexer.py:206`). Make background pressure checking observe live priority within a bounded interval comfortably below the existing admission wait, including initial preflight, while retaining fail-closed pressure checks, cleanup and default ordinary-caller behavior. Before implementation, add a focused delayed-pressure-probe/live-waiter RED fixture that proves acquisition within the unchanged 0.5-second wait and reaping of any launched worker; cover both initial preflight and a running-stage periodic probe. No reviewer runtime experiment was run.

#### Minor (Nice to Have)

- None requiring code changes. The 10 original admission-refusal regression failures remain an explicitly recorded, unattributed validation limitation; the unchanged affected-only rerun passed, and the report does not claim that retrospectively identifies the original lock holder.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** Durable publication, receipt recovery and bounded worker staging are well separated and supported by meaningful fault/native evidence. The remaining priority-probe blocking window prevents approval against the load-bearing 0.5-second live-preemption contract.

**Review scope/checks:** Read the supplied `review-7fab79c..bb9afee.diff` once in consecutive sections; no git commands, test reruns, model/native execution, product changes or subagents. Read the clipped `SemanticSession` initialization/admission and `_supervise` function context to assess absolute deadlines and release ordering. Two focused outside-diff risk checks: (1) whether synchronous pressure checks can block live preemption, checked `brain_reader_guardian._pressure_ok/_pressure_reason`; (2) whether the existing vector receipt contract really verifies durable source/scope bindings before queue ACK, checked `LanceVectorStore._receipt/receipt`. Reported 117 distinct focused passes and the separately qualified actual pinned end-to-end pass were not rerun.
