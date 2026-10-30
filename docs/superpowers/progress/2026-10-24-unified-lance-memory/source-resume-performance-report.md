# Source resume performance prerequisite — implemented and focused checks passed

Current status: root released the source-write hold. The exact reviewed patch
`130398e443145b5a629e45a133c84edf47188398ac4a240374873a91771daf4f` is applied.
The actual product file exactly matches the candidate: **50,367 bytes**, SHA256
`d94f157c359f6367d4c86107257579ac09da224ec52ac1d824ee6a450de83109`.
Actual-file engine-free checks passed: **12 passed**, aggregate peak **43.6 MiB**,
**0.7s**, log `source-resume-actual-pure-green.log`. Actual product/test lint,
format, compilation and `git diff --check` pass. Focused native coverage is
**17 passed across two explicitly authorized runs**: 8 retained v1 passes and
9 v2 passes. V1 stopped on one pre-worker `unavailable/memory_busy` refusal;
root separately authorized only that failed case and the eight unexecuted cases.
No product/test change or automatic retry occurred between runs. Both logs and
basetemps remain; the native slot is released. The retained 52 MiB changed-code
performance qualification and independent review remain separate pending gates.

Actual-file command:

```text
PY scripts/safe_brain_tests.py --timeout 20 tests/test_sqlite_source_resume.py -k 'not native' --noconftest --basetemp=/tmp/castle-source-resume-actual-pure-20261025-v1 -q
```

The sections below preserve the preparation evidence and proposed native command.

Base: `6fa6659`, existing isolated `design/semantic-preservation` checkout.
Product source is still byte-identical to HEAD. Root imposed a source-write hold
because inventory v3 pins its hash. No native/SQLite/runtime/fixture/model/service
operation was launched, no commit was made, and no sealed bundle was modified.

## Prepared changes

- `source-resume-performance.patch` applies only to
  `cognitive_castle/sqlite_source_export.py`; `source-resume-candidate.py` is the
  full proposed source in this workspace. Patch SHA256:
  `130398e443145b5a629e45a133c84edf47188398ac4a240374873a91771daf4f`.
- The only checkout change is the new focused test file
  `tests/test_sqlite_source_resume.py` (SHA256
  `399a86569016082c490e2d1a8b42e0afd48217ac6a7170e0c5b334553c2d403e`).
- Extract ordered `member_ids()` from `members()`, retaining JSON-array validation,
  missing-row checks, relational counts, and dual representation order checks.
  Scope serialization reads each identity's original provenance/capture mapping
  without hydrating canonical text. The complete unchanged `owner()` still reads
  and validates every canonical member and every original field/hash per call.
- Emission receives `start_entry` only after that call's `owner()`. Fresh verified
  page counts skip whole fields; partial fields preserve page ordinals and both
  byte/character offsets. Member enumeration still checks prefix identities while
  canonical text hydration starts at the selected pair. Starting on the record
  half of a pair preserves its exact record and position.
- `_export_owner()` invokes the unchanged streaming `bulk.entry_batches` exactly
  once. Its input iterator records the first position and overflow position. The
  packer and entry generators are closed after selecting one batch. No duplicate
  packing formulas, second batch, retained source body, cached proof, format, or
  pending-intent behavior is introduced. Finalization admission is unchanged.

## Evidence

The retained actual 52 MiB RED is authoritative performance evidence:
`layout52-final-member-diagnostic-20261025/results.json` completed full owner proof
and refused `emit_entries` / `membership`, elapsed 1.7995s, task RSS 55,705,600 B,
aggregate RSS 78,790,656 B. Its final real member pair starts at entry 13522.
No recreation, old diagnostic replay, or modification of that result occurred.

New tests were written before the candidate. All commands below used
`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py`,
explicit paths, `--noconftest`, and unique basetemp directories.

- `source-resume-pure-red.log`: 7 failed / 2 passed; old source lacked seek support
  and invoked the packer 18 / 47 / 256 times instead of once. Old interval bytes
  matched the independent codec-produced reference before the pack-count failure.
  Aggregate peak 44.6 MiB, 1.8s.
- `source-resume-extra-red.log`: 2 failed; old member API lacked suffix hydration
  and old scope serialization attempted canonical text hydration. Aggregate peak
  37.2 MiB, 0.2s.
- `source-resume-preview-final.log`: **12 passed**, aggregate peak 43.4 MiB, 0.7s.
  These execute the exact candidate's AST-selected real methods, using an exact
  copy of the checkout tests under `source-resume-preview/`; importing SQLite or
  native/model engines is unnecessary and checked absent. This is candidate-only
  GREEN, not a claim that the tracked source or retained 52 MiB run has passed.

Final candidate command:

```text
PY scripts/safe_brain_tests.py --timeout 20 .superpowers/sdd/2026-10-24-unified-lance-memory/source-resume-preview/tests/test_sqlite_source_resume.py -k 'not native' --noconftest --basetemp=/tmp/castle-source-resume-pure-final-20261025 -q
```

Tests compare rows and positions with independently codec-prepared original
records/fields, compare full interval/cursor/finalization bytes with the existing
packing contract, cover Unicode/NUL and empty fields/owners, decoded and encoded
packet boundaries, count-limited separate finalization, and a packet ending between
membership and record. Additional checks cover full identity enumeration with
suffix-only hydration, original scope bytes without text hydration, and unchanged
results on malformed/past-end cursor refusals. Each `_export_owner` call is checked
to invoke its proof and exactly one packer.

`ruff check`, `ruff format --check`, candidate compilation, and `git diff --check`
passed. The final tracked source SHA256 remains
`114ae74080085007f217dda5dc369f155653ea1973a5f963a4286df4c0277e78`, exactly HEAD.

## Self-review and pending gates

- Reviewed both original membership paths and their missing/count/dual order
  checks. JSON members use a bounded existence query where scope rendering no
  longer needs full text; the relational path retains its complete missing-member
  query and sorted original order keys. Full owner canonical checks remain intact.
- Reviewed partial-field offsets, zero-page fields, final record half-pairs,
  count/byte overflow lookahead, generator closure, finalization-only cursors,
  and past-end refusal ordering. No load-bearing issue found in this self-review.
- Read-only snapshot opening, transaction, pre/post complete file hashes and
  identity checks are untouched. The 32 MiB heap, 128/192 MiB supervision, 2s /
  internal 1.65s source deadline and shared 5s coordination deadline are unchanged.
- Native SQL behavior and performance remain unverified for this candidate.
  The additional JSON existence query and retained full owner proof need the
  approved supervised checks; pure tests cannot qualify real 52 MiB performance.

Root must release the source-write hold, then resume this agent to apply the exact
patch and run the approved focused native selection. No commit before those
checks and root's review. Proposed native basetemp was verified absent:
`/tmp/castle-source-resume-native-focused-20261025-v1` (recheck before launch).

```text
PY scripts/safe_brain_tests.py --timeout 40 \
  tests/test_sqlite_source_resume.py::test_native_corrupt_skipped_prefix_refuses_without_advancing \
  tests/test_sqlite_source_export.py::test_nine_chunk_and_history_exact_public_envelopes_and_audit_coverage \
  tests/test_sqlite_source_export.py::test_large_fields_resume_wire_offsets_and_stale_replacement \
  tests/test_sqlite_source_export.py::test_corrupt_members_and_original_hashes_refuse_without_advancing \
  tests/test_sqlite_source_export.py::test_empty_original_alias_is_preserved_for_each_occurrence \
  tests/test_sqlite_source_export.py::test_history_owner_requires_original_attempt_and_table_set \
  tests/test_sqlite_source_export.py::test_repaired_history_owner_and_resolution_keep_valid_lineage \
  --noconftest --basetemp=/tmp/castle-source-resume-native-focused-20261025-v1 -x -s
```

The five new native cases put a corrupt owner behind a tail cursor and require
full owner-summary refusal before any cursor-progress claim. Existing native
cases cover real original array/relational membership, exact public envelopes,
capture scope bytes, large fields, corruption, empty owners/aliases and lineage.
No destination, whole-package, model or retained-fixture test is included.

Any later retained 52 MiB changed-code qualification requires a separately
reviewed sibling fixed harness, fresh code hashes, the already established actual
source hash and exact descriptor, and explicit native-slot authorization. It must
preserve every old sealed bundle and result rather than rebinding them. The known
actual final member-pair cursor remains entry 13522 / ordinal 6655; it is a lower
work bound and must not be mislabeled the actual scheduled last packed interval.
Layout Task 1b remains blocked until the required geometry/tail qualification is
independently obtained. No such harness has been written or launched here.


## Native v1 run — stopped on pre-worker admission refusal

Root explicitly granted the seven-selector 40s command. Immediately before
launch, the actual source hash matched d94f157c..., pressure was normal (1),
interactive_waiting was false, an admission check acquired/released its fd, and
`/tmp/castle-source-resume-native-focused-20261025-v1` was absent. Evidence:
`source-resume-native-preflight.json` and `source-resume-native-focused-v1.log`.

The command exited 1 at its first unexpected result: **8 passed, 1 failed in
6.56s**, safe-runner sampled aggregate peak **87.9 MiB**, elapsed **6.8s**.
The five new skipped-prefix corruption cases all passed, as did the existing
nine-chunk/full-envelope test, large-field resume/stale-replacement test, and
missing-member corruption case.

The next original corruption case `[digest-live]` built its fixture successfully,
then its source call returned `unavailable/memory_busy` with no worker resource
record. The runtime returns this refusal before source-worker launch. The exact
admission-holder versus interactive-waiter cause was not observed. No source
contract failure, limit failure or code defect is established by this result.
Across the 61 resource-bearing responses, maximum task RSS was **53,854,208 B**,
maximum aggregate RSS **96,485,376 B**, and maximum per-worker elapsed **0.1516s**.

No automatic retry, expectation change, retry-logic change, product edit, commit,
or additional native operation occurred. The v1 log and entire basetemp remain.
The native slot was explicitly released to root after the command exited.

Only the failed and eight unexecuted cases are proposed next. Exact nine node IDs
are retained in `source-resume-native-remaining-v2-nodeids.json`. Proposed command
uses the same safe runner, `--timeout 40`, exactly those node IDs, `--noconftest`,
`-x -s`, and fresh basetemp
`/tmp/castle-source-resume-native-remaining-20261025-v2`, checked absent during
preparation. It needs a new root grant and fresh preflight. No passing case or
engine-free check will be repeated.


## Native v2 completion and final self-review

Root authorized exactly the nine explicit node IDs in
`source-resume-native-remaining-v2-nodeids.json`. The same preflight passed with
unchanged product source d94f157c..., normal pressure, no interactive waiter,
free admission and absent `/tmp/castle-source-resume-native-remaining-20261025-v2`.
Preflight is retained in `source-resume-native-v2-preflight.json`.

`source-resume-native-remaining-v2.log`: **9 passed in 2.48s**; safe-runner sampled
aggregate peak **87.0 MiB**, elapsed **2.7s**. Across 23 resource-bearing responses,
maximum task RSS **52,264,960 B**, total RSS **91,586,560 B**, elapsed **0.1261s**.
The native slot was explicitly released immediately after completion. All 17
selected native cases are therefore covered by successful results, with the
initial unrelated admission refusal preserved rather than overwritten.

Final self-review: checked the exact two deliverable files and verified both
hashes remained unchanged from the tested candidate. The shared identity path
retains all original membership checks; complete owner validation precedes every
seek; source transaction/hash/identity/resource guards remain outside and
unchanged by the optimization. Entry order, field offsets, member-pair splits,
finalization separation, one-pass packing and no-progress refusal behavior have
the focused evidence above. `git diff --check` passed. No additional change,
source recreation, frozen-bundle mutation, destination operation, model/service,
whole-suite run or retained 52 MiB runtime qualification occurred.

No known implementation issue remains from this self-review. Actual retained
large-owner performance is unqualified until root completes the separate reviewed
changed-code harness. No broader migration/layout readiness is claimed.

Commit: `c6fca0f9937d0499f315eb52e5e50fe7e0264fff` (`fix: stream verified SQLite export resume intervals`). Only the exporter and new focused test file were committed. Working tree was clean after commit. Root independent review is next.
