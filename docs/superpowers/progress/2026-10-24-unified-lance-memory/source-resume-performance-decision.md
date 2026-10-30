# Source resume performance — pending actual tail evidence

This is a root design note, not implementation or runtime authorization.
The current real exporter verifies the complete immutable owner, then reconstructs
all field pages and canonical member records before dropping entries before the
cursor. The selected batch is additionally repacked after each appended entry.
`scopes()` loads a full CanonicalRecord for every member although its serialized
scope output uses only identity, caller provenance, and capture mapping.

If the fixed actual final-member diagnostic fails in `emit_entries`, the narrow
candidate is to preserve complete `owner()` verification inside every call and
avoid only repeated emission work after that proof. Factor original ordered
member identity enumeration without changing dual-membership/missing-member
checks; let scope rendering use identities/provenance without loading text.
Permit entry generation to start at the already verified cursor ordinal, skipping
whole fields by the freshly verified page counts, preserving exact original
field order and byte/character offsets. Skipped member IDs can still be streamed
and checked without reconstructing their already-verified text. No persisted
proof, SHA state, source-body spool or changed source/cursor/registration format.

Select the first packed batch through one invocation of the existing streaming
entry_batches implementation, retaining only its overflow entry position. Preserve
identical pending batches and finalization separation. Do not duplicate packing
rules or optimize away canonical validation. Reject malformed/past-end cursors
as before; a summary from another invocation cannot authorize seeking.

Required proof: byte-for-byte old/new interval and cursor parity over field and
membership/record boundaries, empty and Unicode/NUL-rich owners, finalization
boundaries, exact limits; corruption in a skipped prefix still refuses before
progress because owner verification remains complete. Preserve the unchanged
read transaction, full file hashes and final identities,32MiB heap,128/192MiB,
2s/1.65s and shared5s coordinator deadline. Focused ordinary source regressions
and one changed-code retained52MiB tail/geometry qualification follow pure RED
checks; no fixture recreation or repetition of unrelated accepted tests.

The actual tail outcome and operation must justify any dispatch. If it fails
inside owner_summary instead, do not assume seeking fixes that boundary.
