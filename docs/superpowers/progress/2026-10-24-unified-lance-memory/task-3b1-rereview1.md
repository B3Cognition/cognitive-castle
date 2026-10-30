### Spec Compliance

- ✅ Spec compliant within this fix-round scope. Both original Important findings are addressed; no introduced regression was found in the supplied diff.
- ⚠️ This is a scoped re-review of `2235078869563b6c2be360b4b772182e683d34d9..48107d5bc9be551dcfb71642f10c1c0ecaba5c95`, covering the original two findings and regressions introduced by their fixes. The existing later-task qualification gates remain unchanged.

### Original Findings

1. **Addressed — refused intervals claiming finalization/completion.** `_normalize_refusal` now clears both completion flags, entries/finalizations, cursor progress, counts and staged frame-size claims (`cognitive_castle/sqlite_source_export.py:1060`). The common `finally` path applies it to every non-ok result, including a failure after a result was prepared for return or a post-slice identity failure (`cognitive_castle/sqlite_source_export.py:1151`). Explicit orphan evidence remains distinguished. The test executes actual exporter/normalizer code without storage imports and injects six failure classes at both owner and exhausted-phase boundaries (`tests/test_sqlite_export_codec.py:108`). This covers the control-flow defect reproduced in the original review.

2. **Addressed — missing original historical attempt receipts accepted.** The opening check now requires the complete attempts/occurrences/gaps table set whenever a present member of that inventory is populated (`cognitive_castle/sqlite_source_export.py:265`), matching the existing source rule reviewed previously. Every historical occurrence calls the shared receipt validator using its original cursor key before any owner entries/finalization can be emitted (`cognitive_castle/sqlite_source_export.py:656`). `validate_attempt` performs a cursor-keyed query with bounded scalar projections, rejects missing attempts, reuses `_validate_inventory_receipt`, and additionally requires indexed outcome plus the selected occurrence's exact identity/address (`cognitive_castle/sqlite_source_export.py:832`). Forward audit uses the same helper rather than duplicating the query/validation block. The three negative fixtures delete the original receipt or remove the attempts/gaps table and assert unchanged cursors, false flags and empty output (`tests/test_sqlite_source_export.py:958`).

- ✅ Repair semantics are preserved: a repaired occurrence's indexed receipt has no unresolved gap and therefore satisfies the same original validator; the resolution remains a separate zero-member AUDIT owner. The focused positive test checks both paths and their distinct counters/metadata eligibility (`tests/test_sqlite_source_export.py:975`).

### Strengths

- The refusal fix consolidates shared cleanup rather than maintaining divergent exception envelopes (`cognitive_castle/sqlite_source_export.py:1060`).
- The reverse linkage fix reuses the existing bounded receipt lookup and validator without new source mutations, public routes, resource profiles or receipt formats (`cognitive_castle/sqlite_source_export.py:832`).

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None open within this fix-round scope.

#### Minor (Nice to Have)

- None.

### Assessment

**Task quality:** Approved for this scoped gate.

**Reasoning:** Both original defects have direct fixes and focused regression coverage. The new checks preserve valid repaired lineage, bounded source reads and the original failure/resource boundary.

### Review Checks and Limits

- Read `task-3b1-fix1-report.md` and the complete supplied fix diff once. No broad changed-file reread, additional unchanged-code search or broader review was performed.
- Inspected the already reported `/tmp/castle-task3b1-fix1-affected.log`: **16 passed, 21 deselected in 1.34s**. Its three missing-lineage refusals, two valid repaired-source/AUDIT responses and recorded resource/response sizes match the fix report. The log contains no unexpected refusal or warning.
- No passing test was rerun; no SQLite/native runtime, storage fixture, real data, MCP or service was invoked. No product, branch or index change was made. This report is the only checkout artifact written by the reviewer in this round.
