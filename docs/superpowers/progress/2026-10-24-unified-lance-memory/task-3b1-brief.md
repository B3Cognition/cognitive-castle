# Task3b1 — protected SQLite source export, inactive

Read first. Task3a supplies bulk-v1 codecs/private destination operations; root
will provide its independently reviewed final commit and report. This subtask
adds only bounded export from an already completed protected SQLite snapshot.
Native archive continuation and cross-store operator orchestration follow in3b2;
snapshot creation/WAL qualification, capacity, index scale and real movement are
gated in3c. Do not start the stopped converter or touch real data/services.

Reference task-3b-design-notes.md for the exact existing source table shapes and
formatter mappings, plus frozen task-3a-report.md for actual codec signatures.
Those notes are guidance; this narrowed brief is the implementation scope.
Read AGENTS.md. One product writer, no subagents. Preserve original sources,
canonical IDs, caller/public provenance, exposure hashes and source metadata.

## Pure host and fixed source worker

Create focused source-export codec/cursor and SQLite source-worker modules/tests.
Host imports no SQLite/native/model runtimes. Fixed supervised source worker may
reuse existing MemoryStore._source/_provenance and history formatting/validation
helpers directly. Do not duplicate their logic; extract a shared pure helper only
where host orchestration demonstrably needs it. Never call existing converter
write/index/repair methods. No new ordinary/public route or selectable command.

Source worker profile stays128MiB task/192MiB aggregate, at most2s per read slice,
inside the existing admission/pressure/deadline/cleanup supervision. No caller
budget/provider/model. Keep512KiB request/response frames; decoded and actual ASCII
transport escaping must both be bounded. No native Lance in SQLite source worker.

Input is a trusted internal registered protected-source descriptor: source/store
identity, immutable snapshot path, expected file identity, schema/content manifest
binding and original archive/catalog/version facts. Source binding is a stable
digest of this descriptor, never mtime alone. Validate private owner/mode/no-link
ancestors, exact file identity and registered manifest before and after every
slice; reject replaced/stale/unsupported/corrupt snapshots. Open read-only with
query_only, bounded SQLite cache/heap/progress handling. Never create tables,
change source journal mode, checkpoint source WAL or copy a live main file.

This module consumes a COMPLETE protected view. It cannot bless an arbitrary
changing database as immutable or mark an incomplete backup complete. Test fixtures
create/close/fsync disposable source snapshots in a separately supervised fixture
worker; production snapshot construction/verification is a3c obligation. No
snapshot-creation shortcut or fabricated production capacity permit in this task.

## Streaming export contract

Provide private export_slice(descriptor,cursor) returning bounded source_binding,
cursor_before/cursor_after,entries,finalizations,counts,phase-complete/reason.
Exact names may follow existing internal conventions, but document them. Cursor
is versioned and binds immutable source snapshot, table phase, original key,
owner, field/member ordinal, byte/character offsets and stable packing version.
Validate all types/ranges/phase relationships. Use keyset pagination and existing
indexes; no whole-table/occurrence fetchall, giant ID arrays or string joins.

Emit records/pages/membership/manifests compatible with3a, through byte-aware
entry_batches/validate_batch. One live owner per original request; one historical
owner per original occurrence. Never re-chunk already canonical chunks. Recover
public envelopes using existing verified formatter, including immutable legacy
storage_format provenance. Full scopes/attribution stay in exact paged scopes,
not truncated caller fields or new exposure-bearing data.

Live receipts: preserve namespace/key/digest, ordered original IDs (including
nine-chunk remembers), text bytes/hash and original-format receipt. Reject missing
or duplicate IDs, incompatible caller/offset/hash/digest. Historical occurrences:
preserve original identity/cursor/physical address/alias, exact metadata/columns
strings, hashes and metadata_id. Handle both ids JSON order and oversized
history_occurrence_chunks order; conflicting dual membership is corruption.
Validate contiguous offsets and original deterministic historical chunk IDs.
Empty original text is a real zero-member occurrence. Repeated aliases retain
every original occurrence and alias relation.

Preserve exact source scope facts with origins: historical columns/metadata/caller
precedence, immutable per-chunk capture mapping, generation assignment/state,
source time, first-workspace/conflict offsets. Missing/null/empty/nonstring/conflict
remain distinct. A later conflict cannot reassign old chunk mappings. Preserve
chunk-specific scopes in a live owner; no invented null fallback.

Use bounded byte slices plus <=3byte UTF8 carry for long metadata/columns/scope/
descriptor fields; track byte and character offsets independently. No whole large
field Python decode. Membership and whole-text/field summaries use streaming
ordinary hashlib. On resume, bounded reread may reconstruct summaries; no custom
SHA state or digest-of-page-hashes substitution. Repeated inability to complete a
summary pass under fixed limits is an explicit qualification gate, never guessed
hashes or a cursor advance. Small complete owners may share a batch; large owners
stage and only emit finalization after all original summaries are verified.

## Audit evidence and coverage

Account for attempts, gaps/repair lineage, unpublished stages, capture source/
checkpoint/generation facts and coverage observations. Preserve exact relevant
audit evidence in paged descriptors. Use a domain-separated AUDIT owner descriptor
with explicit kind and original table/key/version, no metadata_id/live receipt,
and zero canonical members. This is an audit artifact, NOT a historical source
occurrence: counters and public eligibility must distinguish it. It reuses3a's
existing opaque descriptor/owner format, not a new row kind. If3a validation cannot
express this faithfully, report the exact conflict before changing its format.

Do not publish source staged chunks/carry as complete evidence; retain a bounded
pending-stage descriptor referencing its original snapshot/cursor for later raw
archive recovery. Derived FTS data is not canonical output. Detect orphan chunks,
unresolved/missing members and duplicate identities; report explicit incomplete
coverage, never invent a source owner to make counts match. Cross-store duplicate
reconciliation belongs3c but export must provide the needed exact identities.

Every returned slice describes export progress only, never committed destination
or semantic progress. No source publication checkpoint advances here.3b2 will
persist metadata-only intent, regenerate exact entries after interruption, verify
destination receipts and advance the frontier in order. Current source-local
rowid/high-water may describe snapshot deltas; it never becomes canonical scope.
Live scope changes without new chunks require later snapshot/delta reconciliation.

## Tests, reports, limits

TDD under scripts/safe_brain_tests with a clean no-SQLite host and separately
supervised fixture/source/destination workers. Core fixtures: live nine-chunk
receipt/hash parity and original retry; both historical membership forms and
conflict; empty occurrence; repeated alias; Unicode/NUL/whitespace/large paged
metadata; long/absent/conflicting/per-chunk scopes; gap versus repaired gap and
audit owner counters; unpublished stage remains pending; malformed/missing chunks
and original hash/ID mismatch; replacement/stale cursor; retry of the same slice
produces identical bounded bytes and does not mutate source; real3a publication
preserves exact public source/exposure, descriptor pages and original receipt.

Compare to existing source formatter, not self-generated expected output only.
Record measured read latency/RSS, response/frame sizes, exact refused phases and
all incomplete coverage. Respect all fixed limits; no production source access,
backup creation, movement, capacity/index-scale bypass or public routing. No model
tests needed. Coordinate native destination fixtures with root. Commit scoped
code/tests only; report task-3b1-report.md with interfaces, RED/GREEN commands,
metrics/refusals, remaining gates and SHA. No push. Root handles independent review.
