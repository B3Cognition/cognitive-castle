# Task2b implementation report

Worktree: `/Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse`
Base: `fba868f` (reviewed shared absolute-deadline fix).
Implementation commit: `abbd8e82b72c98494e1f5655a610b3845f9d9016`
(`feat: add durable semantic vector and queue primitives`).

## Scope and files

New product modules only:

- `cognitive_castle/semantic_queue.py`
- `cognitive_castle/lance_vector_store.py`
- `cognitive_castle/semantic_store_worker.py`

Focused tests only:

- `tests/test_semantic_queue.py`
- `tests/test_lance_vector_store.py`
- `tests/test_semantic_store_worker.py`

No public routes, existing exact-store/runtime/profile/service files, installed
checkout, palace content, artifact manifests, models, downloads, or provider
calls changed. No subagents were spawned by the implementer. Native testing
started only after root released the numeric-audit slot. All native and queue
fixtures use existing global admission and guardian supervision. This report is
an internal local artifact under the existing ignored `.superpowers` directory.

## Actual interfaces and trust boundaries

Both constructors take a trusted generation directory and keyword-only
`writable=False`; the directory must already exist privately. Each checks its
private child and rejects unsafe modes, ownership, symlinks (including ancestor
symlinks), hardlinks, unexpected child artifacts, and unsupervised access.
`exact/` is read by the vector primitive through `LanceExactStore`; vectors never
create exact records. Writable queue/vector operations create their own private
`coordination/` and `vectors/` children only. Reading a missing store creates
nothing. Lance uses `vectors/units.lance`; SQLite uses
`coordination/queue.sqlite3`.

A canonical reference has exactly:

```python
{
    "canonical_id": "memory:" + lowercase_sha256,
    "source_hash": lowercase_sha256,
    "exposure_hash": lowercase_sha256,
    "scope": {"workspace": full_workspace, "wing": full_wing, "room": full_room},
}
```

References are ordered, unique by canonical ID, 1..8 per group. Each reference
carries its own full trusted scope, allowing groups to cross rooms/workspaces.
The caller is the trusted coordinator/authoritative registry; accepting a
reference does not itself prove publication or authorize a public caller.
Workspace is limited to 2048 UTF-8 bytes and wing/room to 512 bytes each.

`SemanticQueue` exposes:

```python
register(batch_key, references, profile, input_binding, lane)
select()
acknowledge(batch_key, receipt)
status()
retry(batch_key, *, refused=False)
```

Keys are nonempty <=128-byte strings. Profile is exactly `PROFILE_ID`; lane is
`new` or `history`. Registration binds the complete ordered references including
scopes, profile, semantic input binding, and lane. Matching retry returns current
durable group state; changed binding conflicts. `select` persists a dispatch
streak: three new-page selections followed by one history-page selection while
both lanes have work, or progresses the remaining lane. Selection preserves an
inflight group/position across worker exit. A failed selection/attempt may spend
a scheduling turn but cannot advance acknowledged position.

Ack is a low-level trusted-coordinator operation. Its caller MUST first recover
and verify the durable receipt using `LanceVectorStore.receipt`; a computed model
response cannot substitute for that receipt. Queue validation accepts only the
publication receipt shape and binds batch/profile/input/reference-scope hashes,
start/count/total/next cursor. It persists every acknowledged page in one SQLite
transaction, permitting identical historical-page acknowledgement retries while
rejecting gaps or changed totals/bindings. Only contiguous progress reaching the
bound total marks the group complete. `retry(refused=True)` records refusal;
retry without that flag requeues at the same durable position. Status returns
four state counts and at most 64 compact position records, plus explicit
`positions_truncated` and `coverage_complete=False`. SQLite stores no text,
tokens, or vectors. Transactions use synchronous FULL and nonblocking locking;
read uses mode=ro, zero mmap, and a 512 KiB page cache.

`LanceVectorStore` exposes:

```python
publish(batch_key, references, page, inference)
receipt(batch_key, start_window)
nearest(vector, profile, generation, scope, allowed_source_hashes, limit)
```

`prepare_publication(...)` is a pure validated compact handoff helper. Publication
uses `semantic_windows.validate_page`, exact pinned inference response fields,
ordered unit/vector alignment, finite normalized 384D vectors, and deterministic
little-endian float32 vector bytes. Durable vector digests and replay comparison
bind those float32 bytes, so JSON spellings that round identically remain an
identical retry. Duplicate unit records within one page are rejected.

Publication rehydrates the ENTIRE ordered canonical reference set from exact
storage before writing, even when a page only contains units from the first
source. It recomputes the semantic input binding and checks each immutable ID,
text hash, exact `unified_memory._exposure({id,text,provenance})`, source length,
chunk start, relative/absolute offsets and source membership. Missing/stale exact
sources refuse. The full refs/scopes binding is additional to the token-input
binding; scopes are never shortened or derived from caller display text.

One explicit version-1 Lance schema atomically appends all absent compact unit
rows and a receipt row in one dataset version. Stored units contain hashes,
source IDs, exact offsets, profile, exposure hash, full scope, nonsemantic marker,
and float32 vector, with no source text/raw tokens/raw offset arrays. Stable
unit storage IDs permit identical units shared by batches to be reused. Receipt
storage IDs have a separate `vector-receipt:` namespace, keyed by batch/start.
A nonblocking private writer lock protects append. Dataset reads validate schema
metadata, disable index use and bound caches to 1 MiB each; scanners use 32-row
batches, no readahead, and a 1 MiB I/O buffer. No indexes are built.

Stable acknowledgement receipt fields are exactly:

```python
status, receipt_id, batch_key, profile, input_binding, reference_binding,
start_window, total_units, count, next_continuation, unit_ids, vector_digests
```

`reference_binding = digest(ordered_references_including_per_source_scopes)`.
The private durable receipt proof also binds page handoff hash and referenced
compact record hashes. Replay/recovery validates the durable proof, schema,
referenced records/vectors, float32 digests, and exact source/exposure identity
before returning an acknowledgement. Changed valid content for the same page
conflicts; corrupt/missing/duplicate durable records refuse. Recovery needs no
model. Receipts remain unchanged when newer dataset versions are appended.

Nearest opens/pins one dataset object/profile. `generation=None` pins current
latest once inside that worker and returns the actual version; an explicit
positive generation must match latest or returns stale. No implicit old-profile
compatibility. Scope, kind, exact profile, nonsemantic exclusion and optional
source-hash grants are typed Arrow expression filters with explicit
`prefilter=True`, before nearest ranking and limit. `None` grants means trusted
full scope; `[]` denies all after schema/generation checks without running a
nearest scan. Other grants are <=256 lowercase SHA256 strings; limit is 1..100.
Candidates are compact identities/hashes/profile/offsets/distances, and response
includes actual generation. Candidate rehydration/exposure at the public
retrieval boundary remains Task2c's responsibility; this query does not return
source bodies.

`semantic_store_worker.py` accepts exactly `directory`, `operation`, `arguments`
and supervisor-injected `_host_pid`. Its fixed allowlist is `queue_register`,
`queue_select`, `queue_acknowledge`, `queue_status`, `queue_retry`,
`vector_publish`, `vector_receipt`, `vector_nearest`; arguments reject unknown
keys. It bootstraps only from its own absolute checkout location under `-I`,
uses strict 512 KiB decode/encode limits with duplicate-key/nonfinite rejection,
and verifies the pinned guardian/host/session/ownership chain before storage.
Admission reuses the reviewed semantic chain check, then applies local stricter
budgets without mutating shared runtime constants. Queue-only imports deny
Lance/Arrow/NumPy and all models/providers; vector imports permit native storage
but deny models/providers/Pandas/legacy backends. Both phases deny network and
children. SQLite's process-global 16 MiB hard heap limit is applied only in the
queue worker.

## Red/green commands and observed results

All commands below ran from this worktree with the existing Python and
`scripts/safe_brain_tests.py`; no installed package checkout was altered.

1. Pure queue RED:
   `python scripts/safe_brain_tests.py --timeout 20 tests/test_semantic_queue.py -k 'reference_contract or host_store'`
   -> 2 failures, missing `cognitive_castle.semantic_queue`; sampled aggregate
   peak 41.4 MiB. After module implementation the identical command returned
   2 passed / 3 deselected, peak 33.6 MiB.
2. Pure vector RED:
   `python scripts/safe_brain_tests.py --timeout 20 tests/test_lance_vector_store.py -k 'publication_contract or host_native'`
   -> 2 failures, missing `cognitive_castle.lance_vector_store`, peak 41.9 MiB.
   GREEN with timeout 25 and identical selection: 2 passed / 7 deselected,
   peak 33.3 MiB.
3. Initial guarded queue RED:
   `python scripts/safe_brain_tests.py --timeout 20 tests/test_semantic_queue.py`
   -> missing worker produced `worker_invalid_frame`; a fixture ref omitted its
   newly-required per-source scope and failed validation. Fixed the fixture and
   implemented the fixed worker. GREEN:
   `python scripts/safe_brain_tests.py --timeout 40 tests/test_semantic_queue.py`
   -> 5 passed in 3.41s, wrapper peak 89.5 MiB.
4. First guarded native covering run:
   `python scripts/safe_brain_tests.py --timeout 80 tests/test_lance_vector_store.py`
   -> 8 passed, 1 failed in 19.88s; peak 186.2 MiB. The remaining failure was
   fixture seed import-key reuse, correctly returning conflict on a different
   source. Fixture seeds now key on their immutable source ID.
5. Real prefilter RED/green:
   `python scripts/safe_brain_tests.py --timeout 35 tests/test_lance_vector_store.py -k prefilter`
   -> authorized lower-ranked candidate already selected correctly; empty grants
   failed because untyped empty Arrow membership did not produce candidates.
   Added explicit empty-grant deny-all branch after schema/version validation.
   GREEN with timeout 30: 1 passed / 9 deselected in 8.17s, peak 184.2 MiB.
6. Guard/private-path covering command:
   `python scripts/safe_brain_tests.py --timeout 50 tests/test_semantic_store_worker.py`
   -> 8 passed in 4.06s, peak 185.0 MiB, before adding the queue-phase and
   artifact-boundary cases to the final covering set.
7. Full-ref scope binding:
   `python scripts/safe_brain_tests.py --timeout 30 tests/test_lance_vector_store.py -k entire_ordered`
   -> 1 passed / 9 deselected in 2.66s, peak 186.5 MiB. Reordered refs refused
   stale; changed per-source scope with the same page conflicted.
8. Duplicate unit RED:
   `python scripts/safe_brain_tests.py --timeout 15 tests/test_lance_vector_store.py -k duplicate_unit_records`
   -> `DID NOT RAISE ValueError`; peak 37.8 MiB. Added duplicate-page unit
   rejection, covered by final run.
9. Intermediate covering GREEN:
   `python scripts/safe_brain_tests.py --timeout 80 tests/test_semantic_queue.py tests/test_lance_vector_store.py tests/test_semantic_store_worker.py`
   -> 30 passed in 43.21s, sampled wrapper aggregate peak 191.5 MiB.
10. Self-review reference-scope acknowledgement RED:
    `python scripts/safe_brain_tests.py --timeout 15 tests/test_semantic_queue.py -k contiguous`
    First attempt refused at global admission with `BlockingIOError` before any
    storage. No larger budget or guard change was used. The identical command
    after the prior run cleared returned the intended RED: changed
    `reference_binding` was rejected as an unknown receipt key rather than
    compared to the registered group (1 failed, 86.5 MiB peak). Added the stable
    reference binding to receipt and acknowledgement validation.
    GREEN:
    `python scripts/safe_brain_tests.py --timeout 30 tests/test_semantic_queue.py tests/test_lance_vector_store.py -k 'contiguous or publication_contract or prefilter'`
    -> 3 passed / 14 deselected in 9.10s, peak 187.6 MiB.
11. Entire group with a later source absent from page:
    `python scripts/safe_brain_tests.py --timeout 25 tests/test_lance_vector_store.py -k first_page_binds`
    -> 1 passed / 12 deselected in 4.35s, peak 189.9 MiB. A 32-unit first page
    refused until its second bound source existed; real vector receipts then
    advanced SQLite 0->32->33 and complete over two publications.
12. Final covering GREEN:
    `python scripts/safe_brain_tests.py --timeout 80 tests/test_semantic_queue.py tests/test_lance_vector_store.py tests/test_semantic_store_worker.py`
    -> 31 passed in 46.39s, sampled wrapper aggregate peak 191.3 MiB, 46.6s
    including wrapper. Native slot explicitly released to root after completion.
    Only a Ruff suppression comment moved after this run; no behavior changed.
13. Pinned static checks:
    `~/.echelon/venv/bin/ruff check cognitive_castle/semantic_queue.py cognitive_castle/lance_vector_store.py cognitive_castle/semantic_store_worker.py tests/test_semantic_queue.py tests/test_lance_vector_store.py tests/test_semantic_store_worker.py`
    `~/.echelon/venv/bin/ruff format --check cognitive_castle/semantic_queue.py cognitive_castle/lance_vector_store.py cognitive_castle/semantic_store_worker.py tests/test_semantic_queue.py tests/test_lance_vector_store.py tests/test_semantic_store_worker.py`
    Initial check found two unused test imports (removed) and a formatter-moved
    E712 suppression (moved to the typed Arrow equality expression). Final
    outputs and scoped commit are recorded below.

The initial native replay/storage scenarios were written before implementation,
but were not individually run to RED while the numeric audit held the native
slot. The observed initial REDs and fixture errors are reported above, rather
than claiming a separate observed failure for every native scenario.

## Resource limits, refusals, qualification limits

Native/vector child task RSS 192 MiB, combined host+owned group 256 MiB;
queue-only 128/192 MiB. Normal read workers use 2s and writes 3s; disposable
fixture setup/mutation workers use 3s at the same RSS limits. Tests run under a
separate sampled aggregate wrapper. Reported peaks are wrapper aggregate peaks,
not hard kernel memory ceilings; worker guards remain sampled RSS tripwires.
No worker memory, total memory, parent memory, pressure, or deadline refusal was
observed in these fixtures. One global admission-busy refusal was observed and
recovered using the same bounds after the competing work cleared. No retry
increased a resource budget.

Lost-response fixture deliberately commits then emits no frame; the supervisor
reports `worker_invalid_frame`. A new read-only receipt worker recovers the
original receipt, and replay does not duplicate rows. Explicit tests also cover
unsafe paths, readonly nonmutation, writer contention, native import absence in
the host/queue worker, model/provider/Pandas/network/child denial in vector
workers, duplicate/unknown/oversized frames, and no surviving worker/guardian
PIDs after the supervised fixture returns. Existing shared descendant-cleanup
implementation was reused unchanged; arbitrary child creation is denied in both
new worker phases.

Fixtures use only deterministic canonical text and normalized synthetic vectors.
No actual model inference, corpus/index building, palace scanning, throughput
qualification, retrieval-quality claim, or corpus-wide coverage claim was made.
The production outbox/automatic exact-publication coupling, authoritative registry
selection, model/index driver, active preemption, and shared 5s coordinator
integration remain Task2c. A low-level queue caller reference alone does not
prove exact publication; a low-level ack assumes trusted receipt verification.


## Final handoff verification

- Final covering result: **31 passed in 46.39s**, no failures/skips, wrapper
  aggregate sampled peak **191.3 MiB**. Command is item 12 above.
- Final pinned Ruff output: `All checks passed!`.
- Final pinned formatting output: `6 files already formatted`.
- `python -m py_compile cognitive_castle/semantic_queue.py cognitive_castle/lance_vector_store.py cognitive_castle/semantic_store_worker.py` exited 0.
- `git diff --check` and staged `git diff --cached --check` exited 0.
- Self-review checked ordered full-source rehydration, per-source scopes, stable
  float32 bytes, durable compact proof validation, contiguous queue progress,
  read-only/private boundaries, fixed worker allowlist, and scoped imports.
- Commit: `abbd8e82b72c98494e1f5655a610b3845f9d9016`.
- Commit contains only the six new scoped code/test files (1937 added lines).
  `git status --short` was empty after commit; report remains in the existing
  ignored internal report directory. No push.
- Native/queue-guarded slot explicitly released to root after the final covering
  command. No further native probes were started.

Task2b is ready for root-managed independent review. Task2 remains incomplete
until Task2c integration and its review. This implementation does not certify
corpus-wide completeness or qualify actual model/index runtime behavior.

## Round 1 fix — durable proof bound (Important finding 1)

Review source: `task-2b-review.md`, Important finding 1, against `abbd8e8`.
The finding was reproduced: an accepted eight-source publication with escaped
scope strings committed but `receipt()` returned `corrupt`, including after a
lost response. The accepted scope limits remain unchanged.

Changes are limited to `lance_vector_store.py`, the scope-limit constant in
`semantic_queue.py`, and the focused vector test file. The queue's existing
2048/512/512-byte scope limits are now named `SCOPE_LIMITS`, used by validation
and proof sizing. No scheduler, public API, storage schema, runtime budget,
profile, model, or service changed.

The single `MAX_PROOF_BYTES` bound is **160,734 UTF-8 bytes**. It is derived from
canonical JSON for the complete maximum structural shape (eight reference
objects, 32 compact-record proofs, 32 unit IDs and 32 vector digests, fixed-width
hash/identity fields, maximum cursor digit widths, and a nonterminal
continuation), plus:

```text
6 * (128 batch-key bytes + 8 * (2048 workspace + 512 wing + 512 room bytes))
```

Six encoded bytes per accepted UTF-8 input byte is sufficient even for control
characters such as NUL (`\u0000`); quotes and backslashes require only two.
The structural template includes string delimiters separately. The 128-byte
batch-key and total-unit constants are also reused by vector input validation.
`publish()` serializes and enforces this bound immediately after preparing the
validated compact handoff, before inspecting or creating any storage, and
writes exactly that validated string. Recovery enforces the same bound before
JSON decoding. Scope values are neither truncated nor restricted further.

Regression fixtures use eight distinct canonical sources, 32 distinct units,
maximum-length NUL scopes, and a 128-byte NUL batch key. They verify normal
publication, fresh-worker receipt recovery, identical replay without duplicate
rows, and commit-followed-by-lost-response recovery. A separate supervised
fault injection inflates the prepared proof before the real publication method
runs; rejection leaves the trusted generation directory empty, with no exact
or vector storage created. Fault injection is test-only; no product hooks were
added. The pure encoder also refuses an oversized proof.

Observed red/green commands, unchanged 192/256 MiB native task/aggregate caps,
2s reads and 3s writes/fixture steps:

1. RED:
   `python scripts/safe_brain_tests.py --timeout 35 tests/test_lance_vector_store.py -k 'maximally_escaped or oversized'`
   -> **4 failed / 13 deselected in 4.83s**; wrapper sampled aggregate peak
   **195.5 MiB**, 5.2s total. Both escaped-scope cases committed and then
   recovered `corrupt`; the encoder/limit did not exist; the injected oversized
   proof reached source reading rather than being rejected before storage.
2. GREEN, identical command and bounds:
   -> **4 passed / 13 deselected in 7.68s**; sampled aggregate peak
   **197.8 MiB**, 7.9s total. No memory/pressure/admission/deadline refusal.
3. Focused receipt/replay/corruption covering command:
   `python scripts/safe_brain_tests.py --timeout 50 tests/test_lance_vector_store.py -k 'maximally_escaped or oversized or atomic_publish or corrupt_receipts'`
   -> **10 passed / 7 deselected in 25.60s**, sampled wrapper aggregate peak
   **192.4 MiB**, 26.0s total. No broad suite rerun. No resource or admission
   refusal occurred. Native slot was explicitly released to root afterward.

Final static checks for all three touched files returned `All checks passed!`
and `3 files already formatted`; `git diff --check` exited 0. Self-review
confirmed all free strings are covered at six JSON bytes per input byte, all
bounded arrays and numeric digit widths are included, the precommit string and
recovery use the same constant, and unchanged valid scopes retain their full
content. The storage schema and stable receipt fields are unchanged.

Round 1 fix commit: `7fab79c583a66c05efb12a3306c08825558c65a3`
(`fix: align semantic receipt publication and recovery bounds`). Commit contains
only the three scoped files listed above. `git status --short` was empty after
commit. No push. The local ignored report remains available for root review.
