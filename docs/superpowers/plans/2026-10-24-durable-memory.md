# Durable memory implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; independent SOAR replacement and evidence collection may be delegated to avoid duplicate context. One final whole-branch review.

**Goal:** Reliable bounded capture, context restoration, honest coverage and removal of native SOAR, demonstrated on Sixth Sense.

**Architecture:** Extend the existing SQLite memory store with a durable observed-source queue and workspace references. A bounded coordinator drives existing ingestion and context reads through the supervised worker. Pure Python replaces native symbolic ranking.

**Tech Stack:** Python >=3.10, SQLite FTS5, existing guardian/psutil, existing CLI/MCP/hook protocol.

**Spec:** docs/superpowers/specs/2026-10-24-durable-memory-design.md

**Release audit:** [Measured outcomes and remaining gates](../../reviews/2026-10-24-durable-memory-evidence.md).
Implementation and regression checks below are complete in merged `d25faca`.
Checked verification items describe fresh workers, installed MCP/CLI commands
and the recorded live rollback/reactivation; they do not establish active client dispatch.
The final audit remains open for client reconnect/dispatch verification and the
missed 100 ms startup target.

## Global Constraints
- Exact originals; no model/provider loads, lossy replacement or legacy mining.
- Runtime worker aggregate RSS 128 MiB and parent-plus-task 192 MiB sampled tripwires; 2 seconds reads / 3 seconds writes.
- Recall/startup packet <=8 KiB encoded, <=8 excerpts; MCP envelope <=32 KiB.
- Python >=3.10; private local data never committed; unrelated dirty worktrees and host settings preserved.
- Guarded focused local tests; full suite and 85% coverage gate in CI.

## Review Focus
- Duplicate, interrupted and rotated source deliveries must neither lose text nor falsely report completion.
- Unsupported attachment/tool material must remain visible in coverage rather than disappear from the denominator.
- Workspace changes and restart must not expose unrelated context or reactivate cancelled/completed work as current commands.
- Simultaneous hooks, pressure and deadlines must leave a retryable queue and no orphan workers.
- Replacing SOAR must not silently ignore custom rules or alter current Fast/Slow routes.

### Task 1: Source state and coverage
**Files:** memory_ingest.py, fast_memory.py, new memory_capture.py, tests/test_memory_capture.py.
**Interfaces:** queue_source(store, path, root, format, workspace); coverage(store, after, limit); existing ingest_slice checkpoints remain authoritative.
- [x] Write/run regression tests for queued source visibility, current versus historical coverage, excludes, tail completion, retry and generation change.
- [x] Implement transactional source state, bounded queue operations and categorized record accounting without altering originals.
- [x] Run guarded ingest/store/capture tests; commit.

### Task 2: Coordinator, discovery and capture hooks
**Files:** memory_capture.py, memory_worker.py, memory_runtime.py, brain_api.py, codex_hooks.py, hooks configuration, tests/test_memory_capture.py and hook tests.
**Interfaces:** bounded capture/reconcile tick, operator CLI capture controls, registered-root validation; context task consumes source workspace associations.
- [x] Exercise hook capture failures and recovery with isolated synthetic originals and stores.
- [x] Add durable bounded discovery/queue processing, independent enable/pause/status and Codex hook integration; keep legacy pause intact.
- [x] Verify busy retry, pressure, parent death, source traversal, crash resume and actual subprocess hook response; commit.

### Task 3: Context restoration
**Files:** new memory_context.py, memory_worker.py, brain_api.py, codex_hooks.py, skills/castle/SKILL.md and mirrored plugin skill, tests/test_memory_context.py.
**Interfaces:** context(workspace, limit) returns exact excerpts plus source IDs/hashes, state attribution and coverage under existing exposure policy.
- [x] Write/run cold-start, same-workspace, correction, completed-work, empty/missing index and budget regressions.
- [x] Implement evidence packet and source-backed active-work references with bounded exact pages; connect PreCompact capture to SessionStart context, including `source: "compact"`, and CLI/MCP interfaces.
- [x] Verify installed hook CLI output, fresh worker restoration and policy denial; commit. Active client dispatch is a separate final-audit gate.

### Task 4: Remove native SOAR
**Files:** soar_bridge.py replacement, searcher.py, config.py, rules/, relevant tests and documentation.
**Interfaces:** legacy boosted/max use deterministic Python rules; audit field compatibility retained; custom native rules explicitly unsupported/migrated.
- [x] Write/run rule and absence-of-native-import regressions.
- [x] Replace kernel with pure rules; migrate tests and descriptions.
- [x] Verify ranking, modes, custom configuration and audit fields; commit.

### Task 5: Sixth Sense proof, review and activation
**Files:** public synthetic integration tests, scripts/bounded_memory_evaluation.py, docs/brain-loop.md, AGENTS.md/CLAUDE.md, private verification fixtures/reports.
- [x] Build hashed private Sixth Sense evidence set; establish current baseline and representative expected evidence.
- [x] Run actual capture -> restart -> restored context -> scoped recall; report omissions, exclusions, corrections, complete evidence recall, bytes, latency and RSS.
- [x] Independent whole-branch review, focused regression fixes, full CI and unchanged coverage gate: all nine checks passed; combined coverage 86%.
- [x] Merge and install checked commit; enable only new bounded capture/context with private backups; verify installed CLI/MCP behavior and a live rollback/reactivation. Six previously returned source IDs remained readable afterward.
- [ ] Audit every goal requirement and verify active client reconnect/dispatch; resolve the missed startup target before marking the goal complete.


## Evidence-driven adjustment

The frozen ten-question plan exposed vocabulary mismatch in literal conjunctive
recall. A private fixed-query counterfactual found 39/39 candidate instances with
OR but only 19/39 complete evidence instances due irrelevant paging. Add only an
explicit bounded `match=any` option to the existing recall interface; preserve
`all` default, limits and policy. Teach preview selection before exact paging.
No prefix heuristic or model load is supported by this evidence. Keep candidate
availability, complete evidence delivery and understanding as separate metrics.
