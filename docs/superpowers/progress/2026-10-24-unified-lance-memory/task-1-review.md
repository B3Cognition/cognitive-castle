# Task 1 independent review

Reviewed `8b08b53..f9751c9` using the complete supplied diff, Task 1 brief/report, repository `AGENTS.md`, and the implementation plan's Global constraints. Inspected the canonical codec and existing store/runtime/guardian dependencies where needed. This is a task-scoped spec and code-quality review, not an integrated-system or full-corpus qualification.

## Spec verdict: changes required

The implementation meets the main structural requirements: one dataset and one append for records plus receipt; unchanged canonical codec; bounded identity-filtered projections; durable receipt/key/content checks before replay; record reuse without duplicate publication; private nonblocking writer lock; read-only paths without intentional filesystem mutation; fixed worker operations and supervised native fixture execution; no public-route, model, network, checkpoint, or legacy-backend additions.

One accepted-input boundary violates the required identical-request replay and lost-response recovery contracts.

## Code-quality verdict: changes required

The implementation is compact, keeps native imports out of the host path, and has focused fixture coverage. The blocking issue is an inconsistent cardinality assumption between the reused codec and durable receipt validation. Fix this before treating Task 1 as complete.

## Finding

### P2 — A valid nine-chunk remember receipt is rejected on every replay

**Location:** `cognitive_castle/lance_exact_store.py:233` (receipt ID-count check; publication begins at line 187).

**Concrete case:** `remember("request", "€" * 21845)` is valid under `prepare_remember`: its UTF-8 size is 65,535 bytes, below the 65,536-byte input ceiling. Each full 8,192-byte chunk holds 2,730 euro signs (8,190 bytes), so the codec returns eight full chunks and a ninth chunk containing the remaining five signs. This follows directly from `canonical_records.py:129` and its chunking loop at lines 136–146.

The first call has no maximum-eight check on `prepared.records` and publishes all nine records plus the receipt. On reopening, the identical call encounters the stored receipt and rejects `len(stored_ids) == 9` as `corrupt`. Therefore a successful publication followed by a lost response cannot be acknowledged through retry; even an ordinary identical retry fails. A changed request with that key also reports corruption instead of the expected conflict. This is valid data created by this store itself, not a malformed import.

**Required correction:** make durable receipt validation support the complete output range of the existing remember codec while retaining the explicit eight-source limit for `import_sources` and bounded individual reads. Preserve accepted text limits and canonical identities. Add a supervised regression for this nine-chunk multibyte boundary covering first publication, reopening/identical replay, changed-input conflict, and lost-response recovery. Reading all nine records can use multiple bounded `read_sources` calls.

**Coverage gap:** current Unicode tests cover two chunks; the codec's maximum-size test uses a two-byte character that divides 8,192 evenly and yields only eight chunks. Neither exercises UTF-8 boundary slack at the maximum accepted text size.

## Concurrency, privacy, and receipt binding assessment

- Within the intended supervised worker path, writes acquire the nonblocking per-store lock before opening the dataset and keep it through publication. The tests exercise a held lock and concurrent read permission. Global admission remains in the existing runtime; the test-only bounded retry does not change production admission or worker deadlines.
- Existing store/artifact checks reject unsafe ownership/modes, symlinks, nonregular artifacts and hard-linked files; the worker sets a private umask before native access. Read paths do not create a missing store or lock. These are pathname-based checks within the existing local worker threat boundary, not an OS sandbox or proof against hostile concurrent filesystem replacement.
- Receipt lookup is tied to namespace/key; its digest is recomputed from durable sources and that key, and replay checks source existence, canonical validation, receipt totals/hash, and incoming equality. No additional concrete receipt-binding defect was found in this scope.
- Filesystem traversal and identity scans still require later scale qualification, as the report explicitly acknowledges. The fixture results do not establish full-corpus latency, migration completeness, or installed-system readiness.

## Evidence and limits

The supplied report records 89 passing tests (28 exact-store, 25 codec, 36 existing fast-memory), the pinned Ruff checks, a 189.8 MiB final guarded aggregate peak, and the earlier admission refusal. Those are implementer-reported results; this review did not rerun them. The finding above is established by static control-flow and exact byte/chunk arithmetic. No native/model/database operation, product edit, or subagent was used during this review.
