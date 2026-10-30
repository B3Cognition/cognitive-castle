# Task3 source planning seams (static only)

Inspected source at feature HEAD ee0c9a0. No imports, tests, database/native
access, product edits or Castle calls. The sole Task3 writer owns implementation.

Minimal extension points:

- `sqlite_source_export.Source.owner` (623) already streams all four field
  summaries and original ordered membership/text hashes. `next_unit` (895)
  selects the same next owner; `entries` (766), `_export_owner` (951) and
  `export_slice` (1066) retain the existing one-owner export and pre/post source
  checks. A plan uses selection+owner summary, returns only the owner reference
  and scalar expansion, and leaves both cursor and migration counters unchanged.
- Native equivalents are `Source.open` (161), `owner` (298), `entries` (336),
  `_export_owner` (374), `export_slice` (461). Preserve `raw_before` for staged
  continuation and `following` as the finalized owner's original source key;
  do not replace them with a layout cursor or infer one from the other.
- Extend the two `*_source_runtime.source_request` boundaries and fixed worker
  `main` field whitelists with a separate closed versioned layout window.
  Existing descriptor/cursor-only requests remain byte-compatible. Add strict
  plan/result validation in the source codecs/layout codec; original
  `migration.validate_export` rejects extra fields, so do not append planning
  fields to its v1 export result. A typed layout wrapper can carry the unchanged
  export. Before emitting, recompute/check the single admitted plan hash.
- `SemanticSession.layout_source` should dispatch to these same workers through
  `_run_stage`: SQLite128/192MiB, native512/640MiB,2s; preserve the same absolute5s
  session and post-result deadline check. Do not call top-level SQLite
  `export_slice`, which acquires a separate lease. Existing worker import bans,
  heap/profile checks and source1.65s internal clock remain unchanged.

Let F=sum(field.pages), M=members, L=1 for an original LIVE receipt else0.
Existing summaries determine E=F+2M data rows exactly (one membership page and
one canonical row per member), plus one owner row and L original receipt rows.
With B reserved batch receipts, no-dedup physical expansion is E+1+L+B.
No canonical reuse savings are available during planning.

Existing hash/length summaries alone do not determine JSON ASCII bytes or the
number of greedy packed frames. During the existing bounded field/member loops,
accumulate per-row decoded/encoded byte sizes or conservative escape/row-header
bounds, including membership JSON, provenance and original receipt overhead.
Only scalar counters survive each bounded page/record. If exact packing is not
counted with the same fixed layout framing rule, reserving B=E+1 gives a valid
one-entry-per-frame plus separate-finalization upper bound, provided every single
entry fits the complete unchanged envelope. Include each batch's proof/receipt
row; raw text bytes are not an encoded or retained-byte reservation. Exact
packing needs the complete outer512KiB and prospective192KiB ACK constraints,
not merely256 entries/384KiB decoded/480KiB body limits.

Concrete qualification dependency: source facts cannot determine Lance fragment,
version, artifact, cumulative index-output/index-byte, retained-byte or temporary
charges. The current envelope has only an opaque qualification hash and ceilings;
the current export window supplies only allowed plan hashes. Bind one closed,
trusted qualified numerical charge model/profile to produce/recompute all ten
positive expansion dimensions. Do not invent defaults, use text length as disk
size, or trust arbitrary caller-provided charges. This is the same cost-model
decision already raised by the Task3 writer.

Do not add a second whole-owner `entries` scan just to plan: native projection
counts/bytes are cumulative per call (64 projections/2MiB), and both exporters
already spend their fixed clock validating the whole owner. New counting cost
is unqualified until the separately approved fixture measures it; refusal must
return no plan/progress, without persisted bodies or SHA progress. Native's
existing prefix replay cost remains a possible refusal, not permission for
Task4 coalescing or a cap increase.

Known LIVE admission prerequisite remains: SQLite `TABLES` still contains15
names and rejects actual `discovery_dirs`/`discovery_roots`. The narrowly reviewed
source-schema preservation work is separate from a planning wrapper; do not skip
unknown tables or claim the52MiB history fixture qualifies installed LIVE export.
