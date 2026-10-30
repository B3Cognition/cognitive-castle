# Source resume performance task review

Reviewed range: `6fa66595c16fd71c7ec388831c199b839bf93683` →
`c6fca0f9937d0499f315eb52e5e50fe7e0264fff`.

**Decision: approved for the narrow code change, conditional on the separate
retained 52 MiB changed-code integration/performance gate. No blocking or
nonblocking code findings. Task 1b is not complete.**

The review read the complete two-file diff and stat in
`source-resume-review.diff`, the brief, decision and implementation report, the
affected exporter paths, the shared packing/page contracts, and the relevant
existing native assertions. This was a focused specification and quality review
of the source resume optimization, not a review of the old exporter or the
whole development branch. Product, tests and git were not modified. No runtime,
engine, model, diagnostic or test was launched or rerun.

## Specification and correctness

- `sqlite_source_export.py:395–480`: `member_ids()` retains array/type/identity
  validation, relational missing-member detection, relational counts and exact
  dual-representation order comparison. `members()` still hydrates and validates
  every canonical record when called by the full owner proof; its suffix option
  skips only canonical text hydration for preceding identities. The relational
  missing-member query precedes its joined enumeration, so moving hydration out
  of that path does not conceal missing relationships.
- `sqlite_source_export.py:483–548`: scope output still uses the original member
  identity, raw original provenance and original capture/generation mapping.
  Removing canonical text reconstruction here does not change emitted scope
  bytes or remove the later complete canonical verification in `owner()`.
- `sqlite_source_export.py:620–764, 946–959`: every `_export_owner()` call still
  invokes complete same-call `owner()` before seeking. Every original field is
  hashed and summarized, every member is canonicalized and checked, and original
  text/member/identity/hash/offset bindings remain enforced. No proof cache or
  cross-call summary authorizes a seek.
- `sqlite_source_export.py:766–812`: cumulative verified page counts skip whole
  fields while preserving metadata/columns/scopes/descriptor order. Partial
  fields retain original page ordinals and Unicode byte/character offsets.
  Member arithmetic handles both membership and record halves, the exact end,
  zero-page fields and past-end cursors without renumbering the suffix.
- `sqlite_source_export.py:960–1055`: one existing `entry_batches()` stream
  supplies the selected bounded batch. Its one-row overflow lookahead records
  the correct next ordinal/position, and generators are closed after selection.
  Total entries come from the freshly verified manifest. Cursor validation still
  precedes result mutation; finalization admission, separate finalization-only
  cursors and the unchanged outer refusal normalization preserve progress/frame
  semantics. No duplicated packing formula, new format or cap increase appears.

The snapshot/file checks, immutable read connection, full pre/post file hashes,
final identity checks, source deadline and resource guard settings are outside
the patch and unchanged. This review does not newly qualify their broader design.

## Evidence and test quality

The new pure tests exercise the actual exporter methods through AST extraction,
with independently codec-prepared rows/positions and complete frame-byte
comparisons. They cover empty owners/fields, Unicode/NUL text, field and member
boundaries, a packet split between membership and record, encoded/decoded/count
packing boundaries, separate finalization, malformed/past-end cursors, one packer
invocation per proof, and absence of repeated full prefix text hydration. The
mocked owner in those checks is appropriately supplemented by five real native
skipped-prefix corruption refusals and the existing native public-envelope,
capture-mapping, large-field, original-hash, membership and lineage assertions.

Retained evidence was read, not rerun:

- `source-resume-actual-pure-green.log`: 12 passing pure cases, aggregate sampled
  peak 43.6 MiB, 0.7 s (the log uses quiet dots rather than a numeric summary).
- `source-resume-native-focused-v1.log`: 8 passed; the next case stopped on
  `unavailable/memory_busy` before any worker resource record. That failure is
  retained and does not establish a product correctness failure.
- `source-resume-native-remaining-v2-nodeids.json` and
  `source-resume-native-remaining-v2.log`: only the failed case and eight
  previously unexecuted cases were selected; 9 passed. Together the two runs
  provide 17 successful selected native cases without repeating a passing case.

These small focused results support source contract preservation; they do not
qualify actual retained large-owner performance. The report correctly retains
that limitation. A separately reviewed changed-code harness and successful
retained 52 MiB geometry/tail qualification are still required before claiming
the integration gate or Task 1b complete. Existing sealed diagnostics/results
must remain unchanged.
