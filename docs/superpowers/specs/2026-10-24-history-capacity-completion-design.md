# Historical capacity and independent completion

The user-authorized unified-memory objective remains the design in
`2026-10-24-unified-memory-design.md`. Real conversion has reached 432,006 of
519,641 pinned source rows with zero gaps, then exhausted eight one-third-GiB
SQLite page allowances. Actual historical database files total 2,863,009,792
bytes; the existing aggregate physical allowance is 8 GiB. The source archive
and every committed exact occurrence must remain intact.

## Capacity decision

Use the existing SQLite format and eight-store query fanout. Give historical
stores a 2 GiB physical envelope each, keeping the one-third persistent-page
allowance for rollback journals and temporary work. Live capture retains its
1 GiB envelope. The historical aggregate allowance remains **8 GiB**, not 16.
RAM, SQLite heap/cache, native batch/IO, time and macOS pressure guards do not
change. This is a disk-allocation change, not a memory-limit increase.

A central history write admission must run before database creation, SQLite
connection/recovery or write. Inspect private retained SHA256-named store
directories, including those absent from the active catalog, with bounded
metadata traversal; reject symlinks, hardlinks, unexpected nested entries and
unknown file kinds. Count existing journals/WAL/SHM as physical bytes.

Admit only when `other_retained_bytes + 2 GiB <= 8 GiB` and filesystem free
bytes are at least `2 GiB + max(0, 2 GiB - current_store_bytes)`. Refuse a
current store already beyond its envelope. The full reservation covers its
database, rollback journal and temporary work; the shared per-user admission
already permits only one supervised memory writer at a time. Retained unused
files are never silently deleted to obtain admission. Catalog publication and
the explicit scope-index upgrader must use the same historical policy. Reads
remain bounded and perform no quota expansion, backfill or repair.

Eight full persistent stores consume 5 1/3 GiB. One full writer reservation plus
seven persistent stores consumes 6 2/3 GiB, below the unchanged aggregate limit.
Actual retained sidecars can reduce available room and must still be counted.
The existing stopped job resumes from its durable unpublished cursor; no row is
skipped, no source is summarized, and no original archive is rebuilt.

## Independent completion

Persist a separately obtained nonnegative source row count for the immutable
snapshot and pinned native version. Obtain it only in the guarded history worker,
never on a query/status path. Legacy jobs lacking the count acquire it before
completion can be asserted. A new source/version gets a new count.

EOF is only a request to reconcile. Inspect each registered store's actual
occurrences, gaps, attempt receipts and private stages under the existing
deadline. Reconcile store and job totals against the independent count; refuse
premature EOF, inconsistent receipts, pending stages or mismatched totals.
Repair may mark completion only after the same independent reconciliation.
Source-count/refusal/mismatch status stays explicit and resumable; no fixture or
legacy "complete" checkpoint can manufacture proof by adding its own counters.

## Verification

Meaningful fixtures cover full old-size stores resuming within the unchanged
aggregate budget; orphan/stale-sidecar accounting; free-headroom boundary;
unsafe/nested paths; bounded traversal; unchanged live quota; scope-index
admission; partial-row and capacity-retry recovery; premature EOF; deleted native
rows; legacy jobs without counts; forged/inconsistent counts; repair and crash
recovery. Tests run through the existing safe test harness or CI when local
memory pressure refuses admission. No guard bypass is permitted.

Before activation, independently review the code, run required platform CI and
qualify actual stored-history progress under the installed limits. Final success
still requires all 519,641 declared source rows reconciled, zero unresolved gaps,
and fresh installed common-route reads of live and historical exact text.
