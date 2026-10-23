# Bounded Understanding Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. User authorized execution on 2026-10-23; do not ask for another plan approval.

**Goal:** Deliver model-free article assessment and a durable host-assisted SUE loop with explicit source, issue, obligation and operational bounds.
**Architecture:** Independent article profile; supervised read-only source reader; pure SUE reducer behind a separate SQLite controller; strict CLI/MCP integration. Provider SUE remains unchanged. Use the active assistant for responses, never launch a model automatically.
**Tech Stack:** Python 3.12 runtime, standard-library SQLite/JSON/process controls, existing LanceDB only in isolated reads, bundled SUE unchanged.
**Spec:** ../specs/2026-10-23-bounded-understanding-loop-design.md

## Global constraints

- Preserve paused hooks and original archive. All tests synthetic/temporary; no model downloads/imports/provider calls.
- One test runner at a time under external system-pressure/RSS/time watchdog. Agents may write independent files concurrently.
- 8 evidence records, 64 KiB text + 8 KiB provenance; problem/interpretation8KiB each; response16KiB; 14 turns;2 total examinations;2 invalid answers per turn;64 automatic requests/root.
- Input wire1MiB/depth32; output actual MCP envelope32KiB; compact state64KiB; artifacts1MiB/exam,2MiB/root with16KiB terminal reserve.
- Keep vendored engine unchanged; advisory and controller ledger may be stricter than engine terminal.
- Default host mode cloud/unknown: no disclosure of local-only archive sources without trusted policy. Caller origin labels are not verified authority.
- No install/switch of live editable package, push, merge or hook activation as part of implementation.

## Review focus

- Exact replay after cancel/purge/revocation must not return stale actionable advice or content (controller).
- Native read must not create an index and must retain admission until owned worker exit (sources).
- Same-run SUE addresses cannot close multiple controller issues (controller).
- Direct article API and import path must satisfy bounds even without MCP framing (article).
- Unknown/missing protocol versions and oversized frames fail before effects (integration).

## Tasks and interfaces

### 1. Article assessment and NLP lifecycle
Files: understanding/article_metrics.py, nlp_runtime.py, understanding consumers/__init__, quality_rerank.py, tests/test_article_metrics.py, tests/test_understanding_nlp_runtime.py, tests/test_quality_rerank.py.
Produces `analyze_article_quality(text: str, *, language: str='unknown', scope: str='article', provenance: dict|None=None) -> dict`. No models;64/8KiB limits;null unsupported quality;explicit profile routing.
- [x] Write failing import/model-free/article/routing tests with literal extraction/applicability expectations.
- [x] Implement profile/shared lazy loader and strict opt-out.
- [x] Verify with serialized `python scripts/safe_brain_tests.py <test files>`; independent diff review.

### 2. Safe source capability
Files: brain_sources.py, brain_reader.py, tests/test_brain_sources.py. Own these files only.
Produces `capabilities() -> dict`, `recall(palace_path: str, query: str, *, limit: int=8) -> dict`, `read_sources(palace_path: str, ids: list[str]) -> dict`. Success `{status:'ok', sources:[{id,text,provenance}], ...}`; failure structured `{status:'unavailable',reason:...}`. Backend-open read-only; version pinned; no model/index/table writes. Provenance marks archive identity but not truth.
- [x] Write tests with fake native backend plus tiny temporary Lance tables using supplied vectors.
- [x] Implement bounded worker/admission/guardian, platform capability and read interfaces; fail closed for unprovable legacy reads.
- [x] Verify serialized safety suite; reviewer checks real missing-index path and orphan behavior.

### 3. Durable SUE controller
Files: brain_loop.py, brain_engine.py, tests/test_brain_loop.py, tests/test_brain_engine.py. Own these files only.
Produces `BrainLoop(store_dir, *, exposure_policy=None, clock=None)` methods:
`begin(request_id, problem, interpretation, sources, obligations, *, parent_id=None, expected_revision=None, revision_reason=None, protocol_version=1)`,
`respond(session_id, request_id, expected_revision, response, *, dispositions=None, commitment_map=None, protocol_version=1)`,
`status(session_id, *, automatic=True)`, `page(session_id, kind, *, offset=0, limit=2048, automatic=True)`,
`cancel(session_id, request_id, expected_revision, *, reason='cancelled', protocol_version=1)`,
`correct(session_id, request_id, expected_revision, correction, *, protocol_version=1)`,
`purge_source(source_hash)` (trusted direct operator only, not caller permission change).
Inputs sources = `{id,text,provenance}`; inline are caller_attributed. Obligations = `{id,text,source_id,start,end}` exact spans. exposure_policy trusted dict `{allow_local_sources: bool, policy_epoch: str}` or callable returning that dict; default False. Current policy applies to every disclosure; cannot be overridden by tool args.
Return bounded JSON-compatible dict with session/root/revision, execution_state, engine_terminal, advisory, counts/budgets, current question/schema refs and next action. Exceptions ValueError for bad requests, structured fail-closed state for capability/storage constraints. Pure engine reducer must preserve raw engine parity; separate issue ledger tightens advisory.
- [x] Write failing pure engine parity/ledger/race/replay tests; use fake answers, never provider.
- [x] Implement separate SQLite store transactions/CAS/content-free receipts, root budgets/lifecycle/version pinning, immutable sources/events and compact pages.
- [x] Verify deterministic parity all9lenses; temporary SQLite crash/race/permission limits; independent review.

### 4. Strict boundary, safety runner, CLI/MCP and host workflow
Files: brain_api.py, bounded_json.py, mcp_server.py, cli.py, scripts/safe_brain_tests.py, tests/test_brain_api.py, tests/test_bounded_json.py; supported skills/AGENTS/CLAUDE/docs.
Consumes interfaces above. Produces tool registry for castle_brain_capabilities, castle_article_assess, castle_brain_recall, castle_problem_begin/respond/status/page/cancel/correct. CLI `castle brain <action>` accepts bounded JSON files/stdin and writes JSON; no implicit provider. Runtime-owned store below configured palace, unknown protocol rejected.
- [x] TDD bounded raw frames/parser/types/actual envelope; serialized model-denying test runner.
- [x] Integrate API after interfaces land; no source-bearing policy flags from tool caller; policy read from trusted local config separately.
- [x] Update shared/Claude/OpenClaw skill instructions with bounded recall→assessment→interpretation→challenge→revision and honest readiness/exposure limits; keep hooks off.
- [x] Integration tests actual handler/CLI on temp palaces, no models; sources unavailable fallback remains explicit.

### 5. Whole-branch verification and traceability
- [x] Map all84 review rows to automated tests or explicitly unavailable capability; no simulated proof of semantic competence.
- [x] Run safe relevant suites, lint/format/diff checks, fresh independent branch review and fixes.
- [x] Commit completed implementation and report validation, capability gaps and live activation status accurately. Do not delete the user's worktree or touch other worktrees.
