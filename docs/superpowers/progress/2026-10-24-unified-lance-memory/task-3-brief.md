## Task 3: migration and coverage reconciliation

Reuse pinned immutable historical evidence and existing canonical algorithms.
Import existing live and historical canonical records from SQLite as a protected
migration source; continue the remaining historical rows directly into Lance.
Preserve occurrence identities, aliases, metadata/column pages and source scopes.
Stage oversized occurrences without publishing partial content. Record durable
resumable receipts, capacity reservations and exact counts/hashes.

Reconcile all 519,641 pinned source rows, current capture backlog and every
canonical occurrence. Reuse old vectors only with verified profile evidence;
otherwise schedule a bounded, resumable re-embedding migration. Retain originals
and rollback stores. Coverage must expose pending, changed, unsupported and
refused work without hiding omissions.

