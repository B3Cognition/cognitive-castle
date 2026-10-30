## Task 1: atomic exact-record Lance store

Create `cognitive_castle/lance_exact_store.py`,
`cognitive_castle/lance_exact_worker.py` and `tests/test_lance_exact_store.py`.
Reuse the tested `canonical_records.py`; do not change existing public routes.

Implement `LanceExactStore(directory: Path, *, writable: bool = False)` with
`remember(request_id, text, provenance=None, *, namespace='operator')`,
`read_sources(ids)`, and `page(source_id, *, offset=0, limit=2048,
expected_hash=None)` matching MemoryStore receipts/pages. Add
`import_sources(batch_id, sources, *, namespace='migration')` for at most eight
full canonical sources per batch, preserving prior provenance exactly.

Use one private Lance dataset, with record and publication-receipt row kinds so
one atomic append can publish records and its durable replay receipt together.
IDs for receipt rows occupy a distinct prefix derived from namespace/request key;
record IDs remain unchanged. Choose a small explicit Arrow schema and bounded
projection/scans. Never materialize the entire dataset. Query expressions contain
only validated canonical IDs or hex digests; do not concatenate caller text.

Serialize writes with a private nonblocking per-store lock in addition to the
runtime's global admission. Validate owner, symlinks, modes and known schema;
reject duplicate/corrupt IDs, receipts or mismatched canonical content. A repeated
identical request returns its original receipt after reopening; changed content
under the same request key conflicts. Reusing identical canonical records in a
different import batch must not duplicate them. Verify receipt-referenced records
before acknowledging replay. Publish before acknowledgement; no checkpoint is
advanced by this store. Read-only operations must create nothing, stamp nothing
and never open the legacy backend.

The worker has a bounded JSON frame and fixed operation allowlist. Deny models,
network, child processes and optional Pandas; permit only the native exact-store
dependencies. Use a trusted bootstrap into this checkout so isolated test workers
cannot accidentally load the installed older checkout. Require the existing
supervisor process chain before storage access. Do not add a production route or
an unrestricted public command in this task.

TDD: use explicit disposable fixture workers under the existing supervisor and
the exact diagnostic profile above. Host tests must not import native libraries.
Cover create/append/reopen; replay/conflict; committed write followed by a lost
response and successful replay; record reuse across import batches; corruption
and duplicate rejection; Unicode/NUL/chunk boundaries; page hash/offset behavior;
read-only missing-store/no-mutation; unsafe paths and absent supervisor. Preserve
the previously passing canonical codec tests. Native test aggregate may use the
existing guarded-test default ceiling; all native children retain the fixed
192/256 MiB profile, and tests are sequential. Record every resource refusal.

Do not add premature indexes or claim full-corpus performance from this fixture.
The later migration/read qualification determines index and publication sizing.

