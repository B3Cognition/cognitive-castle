# Lance canonical memory qualification and first implementation

**Goal:** preserve exact memory identities while qualifying a shared Lance store
and semantic retrieval for live and historical records.

**Architecture:** canonical text and vectors in Lance; separate lightweight
coordination; short-lived supervised workers; one public retrieval coordinator.

**Tech stack:** existing Python, Lance/PyArrow, SQLite coordination and the existing
guardian. No production model or dependency change is approved by a diagnostic.

**Spec:** `docs/superpowers/specs/2026-10-24-semantic-preservation-design.md`.

**Global constraints:** preserve originals, IDs, provenance, grants and pending
capture. Do not resume historical SQLite conversion. Do not change production
limits or activate a replacement without completed qualification. Synthetic
192/256 MiB diagnostic approval is not production approval. Model tests must use
an explicitly bounded offline worker and a pinned model profile; quantized output
must not be silently treated as identical to historical embeddings.

**Review focus:** exact identity/exposure-hash parity, durable publication before
acknowledgement, no hidden native/model imports, and precise qualification scope.

## Task 1 — resource and historical profile qualification

Status: small exact-store and synthetic semantic diagnostics passed under their
explicitly approved diagnostic budgets. The semantic test needed separate
tokenizer and inference workers sharing one deadline; three multilingual queries
passed over eight synthetic documents in 1.0194 seconds, with 422.6 MiB task /
443.3 MiB aggregate sampled peaks. Full-corpus Lance retrieval, historical vector
compatibility, long-input coverage and production resource selection remain open.

- Preserve the completed five-row 192/256 MiB diagnostic and original 128 MiB
  refusal as evidence; ordinary production limits remain unchanged.
- Validate immutable archive schema and original-file metadata drift separately.
- Read declared embedding identity without opening the mutating legacy backend.
- Prepare a pinned, offline semantic probe with synthetic multilingual examples;
  verify its actual RAM, latency and retrieval behavior before adapter activation.

## Task 2 — pure canonical record contract

Status: implemented but inactive and uncommitted. Guarded red/green evidence:
25 tests initially failed for the missing codec, then all 25 passed. The final
focused run peaked at 43.2 MiB aggregate RSS. Ruff check/format and diff checks
passed. Independent static review found no issues in exact ID/text/provenance
parity. Separate historical metadata descriptors remain outside this pure codec.

- Add `cognitive_castle/canonical_records.py` and
  `tests/test_canonical_records.py`; leave existing public routes unchanged.
- Read `fast_memory.py` and preserve current validation, request digest, exact
  UTF-8 chunk boundaries, canonical IDs, provenance and receipts.
- Write meaningful parity tests against `MemoryStore` first, including Unicode,
  NUL, CRLF, chunk boundaries, namespace separation and request conflicts.
- Add only the pure codec needed by a later Lance adapter. Existing source
  provenance is immutable lineage; backend location is a separate concern.
- Run the explicit test file through `scripts/safe_brain_tests.py` under its
  resource/pressure supervision. Record red and green evidence.

## Task 3 — inactive Lance adapter, conditional on the first milestones

- Implement a private-path exact-record adapter and fixed worker; no CLI/MCP,
  capture or production dispatcher activation in this milestone.
- Test deterministic replay, conflicting publication, commit-before-receipt
  recovery, read-only no-mutation and exact paged reads in a disposable fixture.
- Verify real larger batches and the intended resource profile before requesting
  activation. The current 128/192 MiB production profile is not yet qualified.
- Review the final code and evidence before any push/merge/activation decision.
