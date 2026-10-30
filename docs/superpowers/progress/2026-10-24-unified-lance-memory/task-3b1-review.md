### Spec Compliance

- ❌ Issues found: the exporter does not consistently clear completion flags on a refused interval, and it does not detect historical occurrences whose required attempt receipt is missing. Both violate this task's validation/refusal contract; details below.
- ✅ The change stays within the inactive protected SQLite exporter scope: fixed source supervision is retained at 128/192MiB and 2s (`cognitive_castle/sqlite_source_runtime.py:58`); the worker installs existing guards and the fixed SQLite heap limit before importing the adapter (`cognitive_castle/sqlite_source_worker.py:18`). No existing public route or source publication/checkpoint writer is changed.
- ⚠️ Production backup/WAL qualification, complete representative-source movement, capacity/index scale, orchestration and policy projection remain later task gates. The report explicitly leaves them unqualified; this review does not treat its one successful 52MiB source interval as complete export qualification (`tests/test_sqlite_source_export.py:846`).

### Strengths

- The adapter reuses the existing verified source formatter rather than reconstructing exposure-bearing provenance, and checks original deterministic IDs, caller bindings, offsets, whole text hashes and live request digests (`cognitive_castle/sqlite_source_export.py:389`, `cognitive_castle/sqlite_source_export.py:615`).
- Source/manifest binding includes full descriptor identity and registered hashes; source files are read-only and sidecars are refused. Streaming fields retain separate character/byte offsets and ordinary SHA256 summaries (`cognitive_castle/sqlite_source_export.py:111`, `cognitive_castle/sqlite_source_export.py:136`, `cognitive_castle/sqlite_source_export.py:212`, `cognitive_castle/sqlite_source_export.py:615`).
- Scope pages retain historical candidates, exact caller strings, immutable chunk mapping rows and generation state. AUDIT uses the expressly approved zero-member owner representation, while pending stages omit unverified text/carry (`cognitive_castle/sqlite_source_export.py:465`, `cognitive_castle/sqlite_source_export.py:552`).
- The behavioral tests compare to the existing source formatter and original public metadata references, exercise real bulk destination publication, and distinguish history/AUDIT counters (`tests/test_sqlite_source_export.py:569`, `tests/test_sqlite_source_export.py:781`, `tests/test_sqlite_source_export.py:915`). The report accurately limits the native and scale evidence and discloses the earlier failed assertions/refusals.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

1. **Refused intervals can still claim finalization or complete export.** `cognitive_castle/sqlite_source_export.py:1084` clears entries, finalizations and cursor progress after a `Refusal`, but leaves `phase_complete` and `complete` untouched. The other ordinary exception handlers have the same omission (`cognitive_castle/sqlite_source_export.py:1091`, `cognitive_castle/sqlite_source_export.py:1099`, `cognitive_castle/sqlite_source_export.py:1107`, `cognitive_castle/sqlite_source_export.py:1123`). `_export_owner` has already set `phase_complete=True` at line 1016, or the exhausted-phase branch has set both flags at line 1068, before the required post-slice full-file validation at line 1072. A legitimate `summary_slice_deadline` during that validation therefore returns `qualification_required`, no entries/finalizations and the original cursor, while claiming phase completion; the exhausted-phase case also claims `complete=True`. Reset both flags in every refusal envelope, preferably through one common refusal normalization path, and cover failures after finalization and after phase exhaustion. This is exporter contract correctness even though a future coordinator must independently reject every non-ok result.

   **Focused observed evidence:** with root's explicit authorization, an AST-isolated execution of the actual `export_slice` function used a fake Source that raises `Refusal('qualification_required', 'summary_slice_deadline')` during post-validation. No SQLite/native module was imported and no storage was opened. The owner case returned `complete=False, phase_complete=True`; the exhausted case returned `complete=True, phase_complete=True`. Both had empty entries/finalizations, unchanged cursors and zero owner counts. No reported passing test was rerun.

2. **Missing historical attempt receipts are silently accepted.** Historical owner validation loads the occurrence's `cursor_key`, but does not require or validate a corresponding `history_attempts` row (`cognitive_castle/sqlite_source_export.py:644`). `validate_audit` validates only attempt rows encountered while enumerating the audit phase (`cognitive_castle/sqlite_source_export.py:826`); an absent row has no audit unit, and an absent audit table is skipped (`cognitive_castle/sqlite_source_export.py:892`). Opening requires only `chunks` and `receipts`, so a populated history inventory with no attempt table is accepted as well (`cognitive_castle/sqlite_source_export.py:266`).

   **Concrete scenario:** take the existing valid small fixture, delete the indexed `history_attempts` row for its first historical occurrence before sealing the disposable protected manifest, and leave the occurrence, alias and canonical chunks unchanged. Every occurrence hash, deterministic ID, membership and alias check still succeeds. The missing row is never visited, orphan scanning sees all chunks owned, and export can exhaust with indexed-only coverage. Existing production publication writes occurrence and attempt together (`cognitive_castle/memory_history.py:1467`, `cognitive_castle/memory_history.py:1500`; staged publication does so at lines 1904/1920), and the existing inventory reconciler explicitly requires the history attempts/occurrences/gaps table set for a populated history inventory (`cognitive_castle/memory_history.py:1235`). This is corrupted lineage, not a valid historical source. Add a bounded reverse check for each occurrence's required indexed attempt, reuse the existing receipt validator, and test a deleted attempt row plus a populated history source missing its required audit table. No native fixture was run for this finding; the deletion scenario follows directly from the enumerator and owner checks.

#### Minor (Nice to Have)

- None.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** The separation between pure host, guarded source worker and streaming adapter is sound, and the changed tests provide substantial preservation evidence. The two unhandled contract cases above prevent this scoped task from being trusted as a complete validation/refusal boundary until fixed.

### Review checks and limits

- Read the supplied brief/report and the supplied diff once. The first tool response truncated its middle, so only the unread middle ranges were fetched afterward; no independent git diff or whole changed-file reread was performed.
- Named unchanged-code check: bounded chunk projections must reject truncation rather than normalize it. Checked `MemoryStore._source/_provenance` (`cognitive_castle/fast_memory.py:296`) and `CanonicalRecord.from_source`/construction (`cognitive_castle/canonical_records.py:56`); over-limit text/caller projections are rejected by existing byte/hash validation.
- Named unchanged-code check: historical cursor/receipt lineage must remain valid when audit rows are absent. Checked `_validate_inventory_receipt` and `_valid_repair_cursor` (`cognitive_castle/memory_history.py:1027`, `cognitive_castle/memory_history.py:2373`), the production historical publication transaction and inventory table-presence rules cited in finding 2. This confirmed that enumerating existing attempts alone cannot establish reverse occurrence linkage.
- Named unchanged-code check: emitted envelopes must fit the existing bulk contract. Checked `validate_owner`, integer limits and `entry_batches` (`cognitive_castle/bulk_exact_codec.py:38`, `cognitive_castle/bulk_exact_codec.py:218`, `cognitive_castle/bulk_exact_codec.py:399`); the adapter uses those unchanged validators directly.
- No real data, MCP, service, native/storage test, broad suite, source snapshot creation, branch/index mutation or product edit was performed. The sole executable check was the authorized pure control-flow reproduction described above. This report is the only checkout artifact written by the reviewer.
