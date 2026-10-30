# Task3b1 fix round1

Base `2235078869563b6c2be360b4b772182e683d34d9`. Both Important findings in `task-3b1-review.md` were reproduced and fixed. Sole product writer; no subagents, push, services, real sources, destination/model work or broad suite. Source format, public API, guards, capacity and all fixed limits remain unchanged.

## Finding1: refused intervals claiming completion

Added `_normalize_refusal`, called from the common `finally` path whenever a result is non-ok. It clears `complete` and `phase_complete`, entries/finalizations, cursor advance, owner/member counts and staged frame-size claims. It preserves explicit orphan accounting/incomplete coverage. The same normalization covers `Refusal`, ordinary validation/memory/SQLite/OS exceptions and post-slice identity failure, including failures after a successful result was prepared for return.

Pure AST-isolated tests execute the actual `export_slice`/normalizer code without importing the SQLite-only adapter module. Fake storage boundaries inject postchecks after an owner has been finalized or after export phases are exhausted. The tests assert both flags false, unchanged cursor, empty content and zero owner counts across Refusal, ValueError, MemoryError, SQLite error, OSError and final identity failure. This adds no production test hook or public operation.

RED:10failed/2passed. Refusal/value/memory/SQLite/OS paths retained stale completion flags in both owner/done cases; the preexisting identity-failure cases already cleared flags. GREEN:12passed. No SQLite/Lance/Arrow/model module was imported and no storage was opened for these tests.

## Finding2: missing original historical receipts

- Protected-source opening now applies the existing inventory rule: if any attempts/occurrences/gaps table is populated, the full required table set must exist. Missing tables return `corrupt/missing_history_lineage_tables`; empty/live-only inventories do not acquire invented history tables.
- Extracted the existing forward audit receipt lookup into shared `validate_attempt`. Each historical occurrence now requires its original cursor-keyed indexed attempt. Missing rows return `corrupt/missing_history_attempt` before entries or finalization can be emitted. The lookup remains one indexed attempt query with indexed occurrence/gap joins, bounded scalar projections and no collection/scan. Original `_validate_inventory_receipt` still verifies encoding lengths, following cursor, archive/snapshot/version-derived identity, physical address and absence of unresolved gap. Reverse use additionally binds outcome/occurrence/address to the selected owner. Forward audit calls the same helper.
- Tests delete one original indexed receipt, drop the attempts table and drop the gaps table inside separately supervised disposable fixture construction before sealing its registered manifest. All3 initially exported the historical owner: RED3. After the fix all3 refuse with unchanged cursors, false completion flags, empty content and zero published-unit counts: GREEN3.
- A narrow valid repaired occurrence and its resolution AUDIT owner both pass. The occurrence retains1 historical count; resolution retains1 repaired-gap/1 AUDIT count with0 historical count, null metadata_id and0 canonical members. No unrelated audit sweep or destination test was needed.

The52MiB fixture was checked by reading its builder: init already calls existing `_schema(conn)`, and seal atomically inserts its original occurrence plus indexed attempt with matching original cursor/following physical address. The new reverse lookup therefore does not require fixture repair. No old registered snapshot was mutated/blessed, and no52MiB or broad run was repeated merely for reassurance. Earlier52MiB evidence remains one bounded source interval; full export/destination finalization/throughput are still unqualified.

## Commands and measured results

Pinned Python/ruff under `/Users/ladislavbihari/.echelon/venv/bin/`; all pytest commands used the safe wrapper and `--noconftest`.

```sh
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_export_codec.py -k postcheck_refusals --noconftest -q
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_source_export.py -k requires_original_attempt --noconftest -s
PY scripts/safe_brain_tests.py --timeout 15 tests/test_sqlite_export_codec.py tests/test_sqlite_source_export.py -k 'postcheck_refusals or requires_original_attempt or repaired_history_owner' --noconftest -s
```

Logs:

- `/tmp/castle-task3b1-fix1-flags-red.log`:10failures/2passes, exact stale-flag reproductions.
- `fix1-flags-green.log`:12passes; no storage imports.
- `fix1-lineage-red.log`:3failures, all3 corrupted source scenarios wrongly returned ok/finalization.
- `fix1-lineage-green.log`:3passes, all3 explicit corrupt refusals.
- `fix1-affected.log`: **16passed,21deselected in1.34s**, the complete affected selection after both fixes.

The final selection had5 source reads and4 fixture stages, all at unchanged **128MiB task/192MiB aggregate/2s**, with existing32MiB SQLite heap and admission/pressure/deadline/cleanup. Maximum source read0.1633s,50,855,936B task/106,430,464B aggregate; maximum fixture0.1631s,52,428,800B task/108,003,328B aggregate. Valid repaired owner/AUDIT ASCII responses11,094B/4,513B. The3 `corrupt` statuses were intentional missing-lineage refusals. There was no admission, preemption, pressure, RSS, heap or deadline refusal this round, and no increased-budget retry.

## Scope and handoff

Only `cognitive_castle/sqlite_source_export.py`, `tests/test_sqlite_export_codec.py` and `tests/test_sqlite_source_export.py` changed. No format/profile/public route/coordination/destination changes. Original Task3b2 orchestration, Task3c protected backup/WAL/capacity/cross-store/full-scale qualification and Task4 policy projection gates remain unchanged. Root owns scoped independent rereview.

Commit and final checks follow below.

Commit: **`48107d5bc9be551dcfb71642f10c1c0ecaba5c95`** — `fix: validate SQLite export refusal and history lineage`.

Pinned ruff check/format checks and unstaged/staged `git diff --check` passed immediately before commit. Scoped commit contains only the3 named files; worktree is clean. Final process inventory found no remaining worktree source/exact/guardian/fixture worker. Report excluded from commit. No push.
