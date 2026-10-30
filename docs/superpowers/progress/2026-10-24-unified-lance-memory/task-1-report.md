# Task 1 implementation report

Base: `8b08b53` in `/Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse`.
Scope: only `cognitive_castle/lance_exact_store.py`, `cognitive_castle/lance_exact_worker.py`, and `tests/test_lance_exact_store.py`; this report is left for the root's ledger and is not part of the scoped code commit. No subagents/helpers/reviewers were used. No push, public route, runtime policy/service change, checkpoint, legacy backend access, real palace access, models, or network.

## Implementation and self-review

- Reuses the unchanged pure `canonical_records.py`; preserves existing canonical IDs, receipts, exact Unicode/NUL text and complete prior provenance.
- `LanceExactStore(directory, writable=False)` exposes `remember`, `import_sources` (one to eight canonical sources), `read_sources` (one to eight IDs), and `page` with the existing receipt/page contract. Explicit writable permission is required for writes.
- A single private `records.lance` dataset has a six-string-column, nonnullable, version-tagged schema. Record and receipt rows are appended together in one atomic Lance version. Receipt IDs use `receipt:` plus a namespace/request-key digest, distinct from `memory:` record IDs. Replay checks durable receipt structure, hashes/digest and every referenced record before acknowledgment. Changed content conflicts; reused matching records are not appended again.
- A private nonblocking per-store `.write.lock` supplements the existing global admission. Store directory/native artifacts/lock reject symlinks, wrong owner, unsafe modes, nonregular files and hard links. The known Arrow schema is checked on every open. Read-only calls create neither directories nor lock files, and the fixture verifies no file mode/size/mtime mutation.
- Native reads use bounded caches, explicit projections, a validated ID equality filter, `limit=2`, two-row batches, zero read-ahead and a 1 MiB scan I/O buffer. Duplicate queried identities are corruption; all returned canonical records are independently validated. No whole-dataset materialization, premature index, or whole-corpus audit/performance claim.
- The worker accepts a maximum 512 KiB JSON frame, fixed operation/argument allowlist and bounded output. Its trusted absolute-file bootstrap inserts this checkout before package imports, avoiding the installed older editable checkout. Both worker admission and store storage access verify the existing guardian process/session chain; admission measures fixed 192 MiB task / 256 MiB aggregate. Optional Pandas, legacy backend/models/providers, Python networking and child processes are denied. No new registered command or production dispatch.
- Self-review found that valid-hex receipt-digest tampering originally looked like a request conflict. Added a red test and changed replay to derive valid digests from durable content/key before classifying an incoming request conflict.

## TDD and verification evidence

All test invocations used `scripts/safe_brain_tests.py`; native fixture operations ran sequentially through the existing runtime `_supervise`, retaining 192/256 MiB and 2 s reads / 3 s writes. Fixture-only corruption/count/lost-response/guard operations are in the test module, never production command dispatch. Native libraries are absent from the pytest host (explicitly asserted). Unsupervised worker tests reject before storage/native imports.

1. RED: `python scripts/safe_brain_tests.py --timeout 40 tests/test_lance_exact_store.py -x` → expected create assertion failed (`worker_invalid_frame` because the worker did not yet exist); 1 failed in 0.13 s; aggregate 42.8 MiB / 0.5 s.
2. Initial GREEN: `python scripts/safe_brain_tests.py --timeout 50 tests/test_lance_exact_store.py -x` → 23 passed in 30.44 s; aggregate 185.7 MiB / 30.8 s. The initial test's independently hand-counted byte expectation was corrected from 17 to 15 before this run.
3. Regression RED: `python scripts/safe_brain_tests.py --timeout 15 tests/test_lance_exact_store.py -k 'bad_digest' -x` → 1 failed, 25 deselected in 2.04 s (`conflict` instead of `corrupt`); aggregate 171.5 MiB / 2.3 s.
4. Coordination refusal: `python scripts/safe_brain_tests.py --timeout 65 tests/test_lance_exact_store.py tests/test_canonical_records.py` → 24 failed / 27 passed in 0.37 s, aggregate 55.6 MiB / 0.6 s. Every failure was the same `BlockingIOError` at global `_admission()` before any native worker launch: all 24 native-invoking cases in that revision. The two unsupervised/direct cases and all 25 codec cases passed. Root confirmed no remaining diagnostic, identified the existing every-minute live capture as a possible owner, and subsequently observed no lock holder. Per explicit root instruction, only the TEST invocation helper now waits at most eight seconds for admission using 0.1 s backoff; it logs refusals and fails/defer if still busy. This wait is outside each fixed worker deadline. Production admission and live capture are unchanged.
5. Post-fix GREEN: `python scripts/safe_brain_tests.py --timeout 70 tests/test_lance_exact_store.py tests/test_canonical_records.py -x -s` → **53 passed in 34.92 s: exactly 28 exact-store cases plus the prior 25 canonical codec cases**; aggregate 188.5 MiB / 35.2 s. No admission/RSS/pressure/deadline refusal appeared.
6. Default PATH `ruff format ...` and `ruff check ...` refused to run: installed PATH Ruff 0.15.5 does not satisfy repository-pinned 0.15.12. Located the already-existing `/Users/ladislavbihari/.echelon/venv/bin/ruff` 0.15.12; `ruff format` formatted the three scoped files, then `ruff check` passed. Later `/Users/ladislavbihari/.echelon/venv/bin/ruff format --check cognitive_castle/lance_exact_store.py cognitive_castle/lance_exact_worker.py tests/test_lance_exact_store.py` → 3 files already formatted; corresponding `ruff check` → All checks passed. No install or configuration override.

Final regression command was already running when root requested no additional broadening: `python scripts/safe_brain_tests.py --timeout 75 tests/test_lance_exact_store.py tests/test_canonical_records.py tests/test_fast_memory.py -x -s`. → **89 passed in 39.32 s** (28 exact-store + 25 canonical codec + 36 existing fast-memory tests); guarded aggregate peak **189.8 MiB / 39.7 s**, no admission/RSS/pressure/deadline refusals. This final run began after formatting and no tested code changed during it.

The 28 exact-store cases cover create/append/reopen, replay and conflict, response loss after commit, import record reuse/provenance, duplicate record/receipt IDs, invalid text/receipt/digest/schema and missing referenced records, Unicode/NUL/chunk boundaries, page hash/offset behavior, absent/existing read-only stores without mutation, unsafe paths/modes/lock, absent supervisor, invalid operation/arguments and oversize frames, private lock contention, read-only write refusal and denial of Pandas/models/network/children.

## Concerns and limits

- This is Task 1 fixture qualification only. No full-corpus latency/scale, migration, integrated cutover, or installed-system completion is claimed. Targeted identity scans validate accessed records and replay dependencies; no entire-corpus uniqueness/content audit was added. Filesystem privacy checks traverse native artifacts, so later scale qualification must assess metadata traversal and ID scan cost under fixed deadlines.
- Supervision is macOS-specific and sampled RSS is a tripwire, as in the existing runtime. Native tests are skipped on other platforms. Python audit/import guards preserve the existing worker threat boundary; they are not an OS sandbox against arbitrary malicious native code.
- The unrestricted whole project suite was not run because the explicit task forbids host native/model/real-palace work and requires selected guarded test files. Existing public-route integration and broader safe qualification remain root/later-task responsibilities.
- Every observed resource/admission refusal is recorded above. No native worker exceeded its RSS, aggregate, pressure or fixed operation deadline profile in completed fixture runs.

## Commit

`f9751c9` — `feat: add supervised atomic Lance exact record store`. Exactly the three scoped files were committed. `git diff --cached --check` passed before commit. Report is intentionally outside the scoped commit; no push.

## Review fix round 1 of 5 — nine-chunk remember replay

Review source: `.superpowers/sdd/2026-10-24-unified-lance-memory/task-1-review.md`; base `f9751c9`. The P2 finding is confirmed: 65,535 bytes of `€` consume eight 8,190-byte chunks plus a ninth five-character chunk. The original durable receipt's eight-ID ceiling rejected this accepted codec output on replay.

The scoped correction permits up to nine IDs during durable receipt validation. A nine-record receipt is accepted only when its digest and full records match a valid `prepare_remember` output for that namespace/key; import digest validation remains restricted to at most eight sources. `import_sources` and each `read_sources` call retain their existing eight-item limit. No accepted text range, canonical codec, IDs, schema, worker, runtime limits, routes, or test admission coordination changed.

Added two supervised regression variants for ordinary and deliberately lost-response publication. Both verify nine IDs, the exact 65,535-byte receipt/hash, fresh-process identical replay, changed-request conflict, complete exact text reconstructed through separate eight-record/one-record reads, rejection of nine-source read/import requests, and ten physical rows after all retries (nine records plus one receipt).

Exact commands/results:

- RED: `python scripts/safe_brain_tests.py --timeout 30 tests/test_lance_exact_store.py -k nine_chunk -x -s` → **1 failed, 28 deselected in 1.87 s**, expected fresh-process identical replay failure (`corrupt` vs successful first receipt); guarded aggregate peak **183.9 MiB**, 2.1 s. First publication and receipt's nine-ID/byte/hash checks passed before the replay assertion failed.
- Formatting/lint: `/Users/ladislavbihari/.echelon/venv/bin/ruff format cognitive_castle/lance_exact_store.py tests/test_lance_exact_store.py` → one file reformatted, one unchanged; `/Users/ladislavbihari/.echelon/venv/bin/ruff check cognitive_castle/lance_exact_store.py tests/test_lance_exact_store.py` → **All checks passed**.
- GREEN plus amended receipt/import/conflict coverage: `python scripts/safe_brain_tests.py --timeout 60 tests/test_lance_exact_store.py -k 'nine_chunk or import_preserves or replay_refuses or create_append or commit_with_lost' -x -s` → **12 passed, 18 deselected in 33.15 s**; guarded aggregate peak **188.4 MiB**, 33.4 s. This comprises both new nine-chunk variants, create/replay/conflict, ordinary lost-response recovery, import replay/reuse/provenance/conflict, and all seven duplicate/corrupt receipt/record/schema variants.
- `git diff --check` passed. All native work remained sequential under the original fixed 192/256 MiB, 2 s read/3 s write profiles. No admission, RSS, pressure or deadline refusals were observed in this fix round. No unrelated suite was run.

Self-review: only the receipt cardinality and import-digest eligibility changed. No remaining concern from this P2 finding; the original fixture-only/scale qualification limits remain.

Fix commit: `3208aea` (`fix: replay nine-chunk canonical remember receipts`), exactly store and test changes; no push.
