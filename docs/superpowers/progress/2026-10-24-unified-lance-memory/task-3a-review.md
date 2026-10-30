### Spec Compliance

- ✅ Spec compliant for the confirmed Task 3a source set: installed production `MemoryStore.remember` receipts and historical converter occurrences (which bypass receipts), followed by the remaining old `castle_drawers` archive. The controller explicitly confirmed that prototype Lance `import_sources` receipts are fixture/internal format and are not protected migration input. No regression in the existing `import_sources` API was found. The unsupported new migration capability is recorded below as an out-of-scope gate.
- ✅ The other reviewed Task 3a requirements are implemented within the narrowed six-string schema and fixed-frame design: strict codec (`bulk_exact_codec.py:107`), byte/count admission (`bulk_exact_codec.py:365`), batched indexed existence checks (`bulk_exact_store.py:58`), owner-gated visibility (`bulk_exact_store.py:180`), streaming original hashes (`bulk_exact_store.py:210`), durable proof replay (`bulk_exact_store.py:289`), and one atomic append (`bulk_exact_store.py:428`). All seven scoped files in the report have corresponding diff changes.
- ⚠️ Source truth and full real-source attribution remain Task 3b gates. Capacity reservation, sustained fragment growth, maintenance above the 16,384-row candidate ceiling, larger whole-hash/deadline qualification and actual 500k readiness remain Task 3c gates. Semantic coalescing/completion remains Task 3d; typed policy projection and scope filtering before ranking/limits remain Task 4. The implementation report accurately leaves these unqualified.

### Strengths

- `cognitive_castle/bulk_exact_codec.py:107` preserves canonical ID/text/provenance while placing owner pointers and exact metadata/scope pages outside exposure-bearing provenance. `bulk_exact_store.py:210` verifies original concatenated text and field SHA256 values with bounded projected reads rather than substituting page-hash digests.
- `cognitive_castle/bulk_exact_store.py:346` validates before writer/path creation, compares existing canonical content, refuses staged-owner rebinding, and appends final markers, optional old-format receipts and the batch receipt together. `tests/test_bulk_exact_store.py:145` verifies 12 owners in one actual dataset version and replay/reuse without duplicate content.
- `cognitive_castle/bulk_exact_store.py:180` supplies a shared visibility gate. `tests/test_bulk_exact_store.py:384` exercises actual Task 2 hydration before and after publication. The existing text-page method delegates to `read_sources` (`lance_exact_store.py:386`), so it also receives this gate.
- `cognitive_castle/bulk_exact_store.py:19` reports index coverage and bounds unindexed-tail work without read-time maintenance; `bulk_exact_store.py:441` makes BTREE construction explicit. `tests/test_bulk_exact_store.py:283` covers nine commits, indexed late-ID retrieval, an appended tail and duplicate identity spanning indexed/tail data.
- `cognitive_castle/lance_exact_store.py:248` extracts existing receipt validation rather than creating a competing remember receipt shape. Nine-chunk remember migration has a real native regression (`tests/test_bulk_exact_store.py:494`). Fixed 2s/3s and 192/256 MiB admission remains covered by `tests/test_bulk_exact_codec.py:227`; read-only artifact checks and hardlink refusal are exercised at `tests/test_bulk_exact_store.py:449`.

### Issues

#### Critical

- None found.

#### Important

- None within the confirmed Task 3a source set.

#### Minor

- No additional unresolved quality findings. The combined-run SQLite collection failure and two initial wire-frame refusals are disclosed historical failures with subsequent focused green evidence; they should remain visible in the handoff, as they are now.

### Explicit capability boundary and cross-task gate

- `cognitive_castle/bulk_exact_store.py:249` requires owner members’ original chunk offsets to be contiguous from zero. Consequently, `owner.live` cannot migrate a pre-existing prototype Lance `import_sources` receipt over independent sources whose original offsets restart at zero (or begin at a nonzero offset). A focused pure probe confirmed that the old receipt verifier accepts two independently prepared records while new owner finalization rejects their combined owner. This does **not** demonstrate a regression in `LanceExactStore.import_sources` (`lance_exact_store.py:191`): that API still accepts independent offsets, and its shared visibility gate permits already-published bulk records.
- The controller’s explicit source-set ruling excludes those prototype import receipts from this migration. This is therefore an out-of-scope capability limitation, not a reason to add an unused owner variant. Task 3b1 must validate actual production remember digests and refuse unsupported receipt shapes; broad import-receipt migration would require its own design/qualification if later requested. The existing nine-chunk remember path remains in scope and covered (`tests/test_bulk_exact_store.py:494`).

### Checks and evidence

- Reviewed `review-d4d6850..0278524.diff` once in three contiguous sections; no git commands or broad source crawl. Extracted destination line numbers from the review package solely for citations.
- Named outside check **original-import compatibility**: read the `import_sources` body because its diff context ended mid-function, and the unchanged `canonical_records.py` validation/preparation contract. Ran one focused pure in-memory probe with pinned Python `-B`: original two-source receipt validation returned `True`, bulk `_verify_owner` returned `corrupt`, original starts were `[0, 0]`, and no Lance/Arrow/SQLite module was loaded. No dataset/path/native operation was executed.
- Named outside check **page visibility bypass**: read the existing text-page tail because its diff hunk ended at the method declaration; confirmed delegation to the gated `read_sources` method. No other product files were inspected outside the diff.
- Inspected reported logs, without rerunning passing checks. `/tmp/castle-task3a-proof-red.log` records incomplete proof incorrectly accepted; the green log records refusal and 1 pass. `/tmp/castle-task3a-whole.log` and `whole-green.log` retain the two actual 0.0475s/0.0455s frame refusals. The fixed-wire log records 870,400 original text bytes, 128 chunks, eight staging commits, and finalization adding only two rows (296→298), at 0.6821s and 153,747,456/194,019,328 task/aggregate RSS bytes.
- `/tmp/castle-task3a-index.log` confirms index version/coverage and a six-row unindexed tail. The interrupted final log contains 98 completed fixture stages; independent log aggregation agrees with the report's statuses and maxima: 154,386,432 task RSS bytes, 207,470,592 aggregate RSS bytes and 0.9846s. Its `KeyboardInterrupt` is not a green full-suite result.
- The clean-host log records 1 pass; exact-remaining records 25 passes; caps/runtime records 9 passes. These support the reported combined 67 distinct checks (10 codec, 19 bulk, 30 exact, 7 runtime, 1 fixed-stage), with the report's explicit stopped-run qualification. No native suite, already-passing test, or service operation was repeated for this review.

### Assessment

**Task quality: Approved for the confirmed Task 3a scope.**

The publication, visibility, bounded lookup and supervision design is cohesive, and the reported scale limitations are honest. Actual-source adaptation, unsupported receipt-shape refusal and the stated scale/semantic/policy gates remain downstream requirements; this approval does not claim them complete.
