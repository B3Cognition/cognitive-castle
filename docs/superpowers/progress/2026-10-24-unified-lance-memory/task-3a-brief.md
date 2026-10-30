# Task3a — compatible byte-bounded bulk exact publication

Read this first. This is the first implementation substep of Task3, not an
operator migration or activation. Task1/2 exact/semantic mechanics are reviewed
dependencies; preserve their signatures and behavior. Root provides the base
commit after Task2c review. Product changes only in this isolated worktree.

## Binding scope and minimal design

Implement the narrowed appendix of task-3-design-notes.md (starting at
"Appendix: minimal Task 3a ruling"); its earlier seven-kind/typed-schema/spool
proposal is NOT selected. The root ruling is to reuse the six-string Lance schema,
existing fixed512KiB worker frame, CanonicalRecord, writer/admission guards and
existing small remember/import receipts. Add byte-bounded bulk batching and exact
metadata/membership publication with explicit atomic visibility. No alternate
canonical SQLite, new public routes, real palace/source movement, new provider,
production profile/service change, spool framework or custom SHA implementation.

Create focused pure bulk codec and supervised native bulk-store implementation
modules/tests. Extend LanceExactStore/worker only where needed for batched indexed
lookups, fixed private bulk/maintenance operations and shared visible-source
hydration. Avoid duplicating existing receipt/safety/canonical logic. Root owns
other tasks/reviews; no subagents. Current Task2c interfaces are in its report.

Preserve id,text,original public provenance and exposure hashes exactly. Preserve
original request namespace/key/digest/receipt and historical occurrence identity,
alias/cursors, exact metadata/columns bytes/hash, full scope/attribution (including
absent/conflicting values). Metadata/scope/membership live in canonical Lance,
outside exposure-bearing provenance. Do not guess scope from truncated caller
data. New private IDs use domain-separated receipt:<sha256> identifiers.

Use the appendix's three strict private kinds: bulk_record, bulk_page,
bulk_receipt with versioned format discriminator. bulk_record retains canonical
identity/text/provenance and a bounded owner/membership pointer. bulk_page holds
bounded exact UTF8 metadata/columns or membership/scope payload and validated
owner/field/ordinal/offset/hash header. bulk_receipt distinguishes staged batch,
published owner and committed batch; only a verified published owner grants
visibility. Existing record/receipt rows and schema remain compatible. Pure
codec validation must reject malformed/noncanonical envelopes and ambiguous IDs.
Implement exact page splitting without losing whitespace, Unicode or NUL; allow
large scope content through pages rather than inventing a smaller scope limit.

## Bulk protocol and durability

Add a trusted internal import_batch(batch_id,source_binding,entries,finalizations)
operation and compact/paged receipt, owner-membership and metadata-page reads.
All operations use fixed workers, not caller-selected commands/paths/budgets.
Keep512KiB total encoded frame ceiling. Start with a hard upper bound256entries
AND a decoded-byte bound within that frame; these are candidate fixture limits,
not production qualification. Refuse oversize before native mutation. Aggregate
many small complete owners in one append; large occurrences stage over repeated
bounded batches. Return compact counts/digest/receiptID, never every corpus ID.

Validate duplicate incoming IDs, existing duplicate IDs, identical-record reuse
and conflicting content. Serialize with existing writer lock. Append new pages,
records, verified final owner markers and batch receipt atomically. Repeated
identical batch returns durable original receipt after validating referenced
proof; changed key/body/sourcebinding conflicts. A staged receipt is not an
occurrence/source checkpoint. Lost response before/after finalization must resume
from durable receipts without duplicating or re-copying whole occurrences.

Before owner publication, stream ordered membership/content/descriptor pages,
validate contiguous offsets, deterministic IDs, source/exposure hashes, page
counts/digests and original whole-text/metadata/columns hashes and lengths. Empty
text may produce a valid zero-chunk occurrence. Use ordinary streaming hashlib,
bounded projected batches and the existing deadline; interrupted verification
may restart. Never equate digest-of-page-hashes with original text hash. Report
actual repeated deadline failure rather than adding speculative resumable SHA
or raising caps. Finalization appends a small marker, not another copy of text.

All exact read_sources/page/receipt hydration paths must check committed owner
and its membership pointer at the pinned dataset version before exposing a
bulk_record. An incomplete staged owner remains invisible to Task2 hydration.
Existing visible records reused by a new batch stay visible. Never rebind a
staged record to another owner. Source page/metadata descriptors retain current
contract; exposure calculations use only original id/text/provenance.

Migrated live requests publish original-format receipt at original key-derived
ID together with owner finalization. Current remember/receipt retries must read
these without learning a new bulk receipt shape. Preserve nine-chunk remember
handling and existing import_sources <=8 contract. No live exporter in this task.

## Bounded lookup and native qualification

Batch projected existence checks by validated IDs; do not loop one corpus scan
per record. Add explicit supervised BTREE maintenance and indexed lookup with
unindexed-tail participation, separate from ordinary reads. BTREE is not a
uniqueness constraint. Record index coverage/version, bound tail work, and refuse
when it cannot be safely checked. No read-time build or optimization. Keep
recursive artifact safety initially unless a measured failure requires a
separately reviewed bounded validation change; don't weaken owner/mode/link guards.

Native stages remain192MiB task/256MiB aggregate, reads2s/writes3s; pressure,
global admission and descendant cleanup apply. No native/SQLite/model import in
host tests. Fixtures only, explicit safe_brain_tests commands; native workers
supervised. Candidate entry counts/index settings may be reduced after a recorded
failure, not increased budgets. Coordinate native slot with root before tests.

## Required evidence

TDD meaningful boundaries: >8 tiny sources in one actual append; byte-bound
refusal without artifacts; reopen/replay/conflict; existing/incoming duplicates;
reuse without ID/exposure changes; staged invisibility via exact and semantic
hydration; interruption before/after final marker/ack; malformed/missing/reordered
membership; exact metadata whitespace/Unicode/NUL and long/absent/conflicting
scope pages; zero-chunk occurrence; original live receipt replay; changed pinned
generation; read-only no mutation; owner/mode/symlink/hardlink rejection.

Separately qualify several bounded commits, late-ID lookup, explicit BTREE build
and appended unindexed tails, plus a representative multi-batch whole-hash fixture
under unchanged caps. Increase fixture scale only when answering an unresolved
scale question; never claim500k readiness from small fixtures. Capture observed
RSS/time/bytes/fragments and every refusal. Existing52MB conversion evidence
supports streaming hash as initial design but used a different memory profile.

No operator bulk mover/capacity reservation/source adapters/real migration yet;
these are Task3b/3c. No ordinary scope-search/public routing yet (Task4). No full
semantic completion or whole-goal claim. Commit scoped code/tests only, no push.
Report task-3a-report.md with APIs/schema, exact RED/GREEN evidence, resource
measurements/refusals, limitations and commitSHA. Use pinned ~/.echelon/venv tools.
