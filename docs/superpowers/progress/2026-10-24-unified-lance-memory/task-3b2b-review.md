# Task 3b2b review — a610fad57ce3ee4946b5d863f52bc9390d6d480e

## Spec Compliance

- ❌ Issues found: the fixed native executable does not perform the full established live session-chain validation required by the brief. Its checks omit both session IDs and both effective UIDs (`cognitive_castle/native_source_worker.py:24`). See Important I1.
- The reviewed implementation otherwise follows the inactive source-only boundary: explicit native registration/domain and fixture entry, original occurrence/cursor identities, exact historical formatting, fixed source profile, bounded streaming, and refusal cleanup. No production activation or converter dispatch is added by this diff.
- ⚠️ Cannot verify from this diff: qualification of any real snapshot's original lineage/content hashes, reconciliation of shards/attempts/gaps, the production start cursor, giant native decode/destination finalization, or maintenance/index scale. The report correctly reserves these for Task 3c/later qualification; `native_source_export.py:99` performs registered identity/inventory checking, not independent proof of historical coverage.
- ⚠️ Cannot verify operational claims that the old converter remains stopped and production originals/rollback data remain unchanged. This patch adds no route that starts that converter; root must retain the existing operational controls/evidence.

## Strengths

- The pure codec preserves the original pre-row JSON representation and validates active-owner positions, while migration validation explicitly binds native finalizations to original archive/snapshot/version/physical address (`native_export_codec.py:204`, `migration_codec.py:298`). Native sources get a separate migration domain and one explicit fixture path without duplicating prepare/import/replay/ACK (`migration_codec.py:52`, `migration_coordinator.py:22`).
- Source work uses the existing session's absolute lease with a fixed two-second stage and 512/640 MiB profile (`semantic_runtime.py:253`). Projection count and UTF8 bytes are shared across summary and emission passes (`native_source_export.py:206`, `native_source_export.py:211`); ordinary streaming hashes and bounded chunk packing retain original canonical text and provenance (`native_source_export.py:197`, `native_source_export.py:298`).
- Snapshot identity/inventory and native schema/version/fragment evidence are checked before and after an opened slice; postcheck failures clear tentative entries, finalizations, counters and cursor progress (`native_source_export.py:99`, `native_source_export.py:145`, `native_source_export.py:446`, `native_source_export.py:500`). The worker also explicitly refuses SQLite connections (`native_source_worker.py:43`).
- The narrow exhaustion primitive preserves legacy `header()` failure behavior and distinguishes a genuine no-row result from invalid statistics (`history_projection.py:116`, `tests/test_native_export_codec.py:424`). Shared historical formatting preserves exact raw JSON and candidate type precedence without instantiating a SQLite Source (`historical_export_evidence.py:15`, `sqlite_source_export.py:471`).
- Synthetic coverage exercises original helper parity, Unicode/chunk boundaries, deletions/empty text, immutable artifact refusals, deterministic multi-batch replay, invisible staging and lost final ACK (`tests/test_native_source_export.py:259`, `tests/test_native_source_export.py:361`, `tests/test_native_source_export.py:431`). The report states measured cold tick/resource bounds and distinguishes injected refusals from real pressure events and small-fixture qualification from production readiness.

## Issues

### Critical (Must Fix)

None found in this task-scoped static review.

### Important (Should Fix)

**I1 — Full session/identity admission is missing from the new native executable.** `cognitive_castle/native_source_worker.py:24` checks the guardian command, process group and parent PID, but never checks `os.getsid(0) == guardian.pid`, `os.getsid(guardian.pid) == guardian.pid`, or that the guardian and host effective UIDs equal the worker's UID. The delegated `_admit_storage` checks only platform, parent relationship and the history RSS limits (`memory_history_worker.py:57`); it supplies none of the missing checks. The established semantic worker's session-chain admission includes all four (`semantic_worker.py:89`). Consequently, a guardian launched as a process-group leader in an existing session, or a mismatched-UID chain, is accepted by this entry even though the fixed supervisor's established admission contract rejects it. This violates the brief's explicit full session-chain requirement and makes the report's claim of full chain validation inaccurate. Add the missing checks while retaining the history 512/640 MiB profile, or extract a profile-independent shared chain validator. Extend the existing pure fault test (`tests/test_native_export_codec.py:184`), which currently tests only command/group/parent, to cover both session IDs and both UIDs. No native runtime is necessary to establish this static omission.

### Minor (Nice to Have)

None independently blocking or actionable beyond I1.

## Assessment

**Task quality: Needs fixes.** The implementation is otherwise focused and well tested for its inactive synthetic scope, with careful exact evidence handling and conservative refusal behavior. Approval is blocked on the new executable matching the required complete admission chain.

## Review evidence and scope

- Read the frozen brief, implementer report, AGENTS.md, reviewer template and the complete supplied 2,903-line diff once in bounded chunks. Reviewed base `253227ffa10dcd35a3b737ef19cd7e04a9913845` through head `a610fad57ce3ee4946b5d863f52bc9390d6d480e` only; later untracked Task 3c design work was excluded.
- Named concrete risk: source artifact privacy and structural validation. Inspected only the existing `_safe_ancestors`, `_private`, and `_validate_snapshot` helpers to establish what the new adapter's reuse actually checks (`memory_history.py:66`, `memory_history.py:72`, `memory_history.py:602`).
- Named concrete risk: exact old identities, columns, scope precedence and chunk/projection parity. Inspected the read-only `_stage_header`, `_stage_caller`, `_valid_repair_cursor`, `_chunks`, `_json` helpers, plus the omitted constructor/scanner/page context around the changed `NativeProjectedRow` hunk (`memory_history.py:1615`, `memory_history.py:1824`, `memory_history.py:2373`, `memory_history.py:1356`, `canonical_records.py:16`, `history_projection.py:23`). The diff alone cut off the projection function's supporting context, so this focused surrounding read was necessary.
- Named concrete risk: source response normalization and batch packing. Inspected unchanged `source_refusal`/`source_result` and `entry_batches` (`sqlite_source_runtime.py:29`, `sqlite_source_runtime.py:50`, `bulk_exact_codec.py:399`).
- Named concrete risk: claimed full session-chain admission. Inspected existing `_admit_storage`, semantic `_admit`, `_run_stage`, and the guardian launch boundary (`memory_history_worker.py:57`, `semantic_worker.py:74`, `semantic_runtime.py:97`, `brain_reader_guardian.py:146`, `memory_runtime.py:403`). This produced I1.
- No tests, engines, models, native/storage reads, git mutations, or subagents were run. Test outcomes and measurements above are assessed from the supplied report and test code, not independently reproduced. No new focused runtime was requested because the finding is a direct static omission.
