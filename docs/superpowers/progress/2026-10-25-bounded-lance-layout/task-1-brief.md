### Task 1: Ordinary ordered owner verification and the known large-owner gate

**Files:** Create `bulk_owner_stream.py`, `tests/test_bulk_owner_stream.py`, `tests/test_lance_owner_stream.py`; modify `bulk_exact_store.py` narrowly. Task 1's ordered dispatch is confined to the fixed supervised fixture worker in `tests/test_lance_owner_stream.py`; do not add an unregistered ordered operation to the ordinary exact worker/runtime. Reuse existing source and guardian/session mechanisms; no source conversion redesign.

**Interfaces:** Produce `verify_owner_rows(rows, manifest, pending, *, resolve_reused) -> None` in `bulk_owner_stream.py`; `rows` is an iterator of six-string canonical rows, `pending` a bounded current-frame ID map, and `resolve_reused(ids) -> dict[id,row]` is a bounded resolver. Failure uses existing corrupt/conflict store outcomes. Add internal `OrderedBulkExactStore(directory, *, qualification, writable=False)` as a `BulkExactStore` subclass, with `_owner_rows(dataset, owner, pending)` and an ordered `_verify_owner` override. Define strict `OrderedQualification` in `bulk_owner_stream.py`: `format="ordered-owner-qualification-v1"`, frozen manifest hash, exact private destination/parent identity, owner/source binding, expected pre-operation version (or explicitly authorized before/after pair for lost-reply reconciliation), and numerical ceilings for physical rows, fragments, versions, artifact entries/depth, total logical/allocated bytes and maximum individual file bytes. It admits a **dedicated one-owner dataset only** in Task 1; it is not a caller-selected public storage profile.

The hash-frozen fixture runner/worker binds the root-approved qualification manifest and its expected digest before execution. Its private `ordered_import_batch` action accepts the existing bulk arguments and a qualification reference/hash only; it rejects a mismatch with that frozen run binding and cannot accept replacement ceilings/destination paths from the request. It constructs the qualification, invokes the subclass's inherited **real** `import_batch`, and uses the existing exact guard/session chain at 3 s/192/256 MiB. Missing qualification refuses before mkdir, artifact enumeration or native open. Original `BulkExactStore`, ordinary worker operations and arbitrary legacy batch order remain unchanged. Task 3 derives equivalent qualification from its registered home/envelope rather than this fixture manifest. Keep full `_verify_batch` and canonical validators; no saved hash progress or fake publication boundary.

- [ ] Write pure RED assertions `test_stream_checks_original_bytes_and_pending_tail`, `test_stream_rejects_missing_duplicate_reordered_or_foreign_pages`, and `test_stream_uses_actual_reused_bytes`. Assert exact original text/membership/field digests and counts for Unicode, NUL, empty and multi-page fields; changed offsets/IDs/exposure or missing bytes must fail. A bounded single-pass iterator must work without materializing/sorting the owner.
- [ ] Run RED, then implement the pure verifier and rerun GREEN:
  `/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_bulk_owner_stream.py --noconftest -x -q`
- [ ] Implement Task 1 qualification enforcement **before native open**: retain every existing parent/private-file/no-symlink/no-hardlink/entry-type check, but replace this subclass's recursive `Path.iterdir()` walk with streaming `os.scandir()` and a depth/entry-bounded stack. Count directories, all retained manifests/indexes, regular files and orphan/temp artifacts; reject on the first ceiling+1 entry or bytes/depth violation. Check maximum individual file bytes, including manifests, before parsing native metadata. Never sort/materialize all names or call the unbounded base walk first. Revalidate the qualification/path/version under the existing writer lock before append. Fixture append/maintenance preflight reserves conservative resulting geometry within the frozen envelope; postchecks cannot retroactively authorize an overshoot. Unknown acknowledgment leaves the fixture charged and unqualified pending the frozen reconciliation case.
- [ ] Implement the pinned iterator over **all fragments of that admitted dedicated dataset**, in the opened manifest's insertion order: this complete dataset is Task 1's scan span, so no Task 2 registry, inferred owner span or arbitrary fragment selector is needed. After bounded native open, reject an unexpected version, schema/storage mode, fragment/physical-row count, deletion/rewrite or foreign-owner data before claiming verification. Use explicit projection, `scan_in_order=True`, strict bounded batches, zero readahead, existing bounded I/O settings and a physical-row ceiling+1 sentinel; count every scanned row, including recognized receipt rows. Validate field/ordinal/offset order and original hashes; skip only structurally validated bound receipts, and append genuinely pending final rows exactly once. No full scan of an arbitrary legacy/shared dataset is enabled. Compaction remains disabled.

  Source-order basis: both exporters emit descriptor fields followed by membership/record pairs. `import_batch` preserves the input order through `candidates` and `pending`, then appends the batch receipt last; matched rows are omitted. A split pair across batch boundaries must therefore survive interspersed receipt rows, while same-batch replay appends nothing. Task 1's native qualification contains no foreign-record reuse; pure resolver tests cover its semantics, and Task 3 separately qualifies real remote reuse. Any nonconforming physical layout fails closed rather than switching to a sort or an unbounded lookup path.
- [ ] Add supervised RED/GREEN `test_pinned_stream_finalization_and_replay` and `test_stream_layout_corruption_refuses`: actual fixture `ordered_import_batch` append/replay, split membership/record pair, late IDs, final pending rows, unchanged canonical files and version/fragment mismatch refusal. Include missing/changed qualification refusal before path/native access, first-extra-artifact/depth/oversize-manifest refusal before native open, physical row ceiling enforcement and foreign-owner refusal. Verify unchanged legacy `import_batch` acceptance of valid entries in a different physical order; the ordered path refuses its invalid ordered-layout claim. Acquire the native slot, then run:
  `/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 60 tests/test_lance_owner_stream.py -k 'pinned_stream or layout_corruption' --noconftest -x -s`
- [ ] After root freezes the large diagnostic manifest, stage its exact bulk representation in individually admitted calls, using existing explicit fixture maintenance before the tail becomes unreadable. This fixture support does not change the product maintenance ceiling. Add `test_52mib_finalization_and_cold_replay`: full finalization, then a fresh 5 s session performing source regeneration, actual identical replay, required owner/live checks and real metadata ACK. A retained first append may precede that tick; no saved verification offset may. Capture stage/tick RSS/time, frames, files, all physical rows and refusals. Run once:
  `/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 600 tests/test_lance_owner_stream.py::test_52mib_finalization_and_cold_replay --noconftest -x -s`
  GREEN requires exact 54,525,952-byte/6,656-member parity, small final marker/receipt only, successful full cold replay/ACK inside unchanged limits and no native imports in the host. Source-only or append-only success is insufficient. On failure stop dependent implementation and report the gate; do not introduce SHA-state machinery.
- [ ] Record evidence in SDD `layout-owner-stream-report.md`; run file-scoped Ruff and `git diff --check`; commit only this task's verified files with `feat: stream pinned bulk owner verification`. Root independently reviews before Task 2.


## Binding global constraints

- Baseline: independently approved `162a94f2e9fed205768fc3b6fa46d26bdeef900a` (Task 3b2b plus the focused full-session/UID admission fix). No source interface changed from `a610fad`. Do not redo or silently alter reviewed source contracts.
- Keep exact workers at 192 MiB task / 256 MiB aggregate, reads 2 s and writes 3 s. Source, exact, queue and verification stages consume the same 5 s session deadline.
- Source-specific profiles and transport limits remain unchanged: SQLite source 128/192 MiB and 2 s; native source 512/640 MiB and its current 2 s stage; native synthetic fixture stages at most 5 s. Preserve existing queue guards.
- Preserve 512 KiB complete frames, 256 combined entries/finalizations, 384 KiB decoded and 480 KiB ASCII body bounds; complete envelopes must fit too.
- Require at most 1,024 unindexed rows and 32 unindexed fragments after append. Count batch/live receipts; the current conservative maximum is 513 physical rows, not 256.
- Keep pressure refusal, global admission, preemption and descendant cleanup. Never increase limits to make qualification pass. Keep hosts engine/model-free and external networking disabled.
- Preserve original text, canonical IDs, provenance, exposure, metadata, receipts and source lineage. Preserve original archives, protected sources and SQLite rollback stores.
- SQLite stores coordination and derived metadata only: no text, source/metadata/scopes/caller JSON bodies, frames, durable text outbox, SHA state or partial-proof journal.
- Preserve `sqlite-migration-v1`, `native-migration-v1`, their registration/job ID derivation, existing source cursors and old exact/public request/receipt formats. Layout extensions have separate explicit versions; reject unsupported/mixed versions.
- Roll between admitted owners, never within a batch or halfway through an owner. Coalesce only within one source binding, source phase and home partition.
- One writable partition at a time; sealed partitions remain readable. No compaction, cleanup, source deletion, redistribution, new model, caller-selected executable/budget or generic provider framework.
- This plan adds private fixture/operator primitives only. No ordinary Task 4 retrieval routing, semantic coverage claim, production mover, installation, capture/service change, merge or activation.
- One product writer per task. Root grants the exclusive native slot for concrete SQLite/Lance test scope before execution. Pure contract checks need no native slot; every engine test uses supervised workers and explicit safe-runner selection.
- A resource refusal is evidence: retain intent/artifacts/accounting, stop that qualification sequence and report it. No automatic retry, tuning matrix, new cap or alternate fixture to manufacture a pass.


## Root dispatch scope and rulings

Base4ab746ef85ac3b132301c66bbdb9d193d607f10e (product still reviewed162a94f).
Work only in /Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse.
This Task1 is the only product writer. Do not spawn agents, install/activate,
change source/capture jobs, query Castle MCP, access palace data or run broad tests.
Root handles independent review and commits only approved architecture docs.

Begin pure TDD and implementation. Every pure test still uses the explicit safe
runner. Before any SQLite/Lance/model test, send root your exact small test
fixture/worker paths, qualification bounds, command and operation scope for
native-slot allocation. No native slot is granted by this dispatch. The large
52MiB run is separately gated on the root-frozen manifest and may not be improvised.
The prior retained source path is not available; root is preparing known-fixture
recreation and complete expansion evidence in parallel. This is not grounds for
creating a smaller substitute or skipping full cold replay/ACK.

Report full TDD commands/results, metrics, exact guarded boundaries, files,
self-review and concerns to this workspace's task-1-report.md. That file is the
single full Task1 report (use a pointer for the plan's layout-owner-stream-report.md
if needed). Return only DONE/DONE_WITH_CONCERNS/BLOCKED/NEEDS_CONTEXT, commits,
one-line test summary, concerns and report path. Do not mark full Task1 done
before the reviewed large gate succeeds; an interim needs-context is appropriate
while root freezes the required run inputs. Ask root about unclear contracts
before adding protocol or scope. No SHA serialization or partial verification.

### Root answers to qualification questions

Valid Task1 destination directories are precreated empty/private by fixed fixture
setup and then destination+parent dev/ino bound. Do not add absent-destination
rebinding. Qualification `expected_states` is one or at most two strict
{version, physical_rows, fragments} entries; a before/after lost-reply pair must
bind each version to its own exact geometry. Use an ephemeral set of receipt IDs
bounded by `max_batch_receipts` and the physical envelope; no unbounded metadata
set or saved text/hash state. Before append/maintenance charge root-frozen
conservative reservation for each resulting row/fragment/version/artifact/byte
category; if actual output exceeds it, preserve charged artifacts and refuse.
Base append hooks remain no-op for ordinary legacy paths. No runtime authority
is implied by these schema choices; root reviews concrete code/manifest first.

Reservation `file_bytes` is the largest regular-file ceiling for the resulting
whole destination, including retained files. It is not an incremental sum or a
new-file-only promise. Check current largest file before mutation and charged
result afterward. Qualified append/maintenance envelopes must cover retained
index files; do not enlarge a frozen allowance after refusal.

### Reviewable milestones, root ruling

Task1a is the streaming, strict qualification, append/reservation and explicit
qualified-maintenance primitives plus pure/small real-native evidence. Task1b
is the separate52MiB source→publication/fresh cold replay+metadata ACK integration
and qualification. Task1 remains incomplete until both pass independent review;
Task2 cannot start early. Root split the review surfaces to catch structural
issues before expensive construction while the fixed source fixture is prepared.
Task1a has no production activation authority or full-corpus/large-owner claim.
