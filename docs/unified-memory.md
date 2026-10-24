# Unified exact memory

Ordinary `castle search`, Python `search_memories`, MCP `castle_search`,
`castle_brain_recall` and workspace context use the same exact SQLite memory
catalog. The catalog includes continuously captured text and committed historical
imports. Queries do not open Lance files, import models or initiate backfill.

An explicit old `--mode fast|standard|boosted|max` selects the older diagnostic
pipeline. Its response is labeled `legacy_index_only`: it does not contain new
SQLite-only captures and may load native libraries, embeddings and rerankers.
Omitting `--mode` selects the unified route. Old scoring options require an
explicit legacy mode; they are not silently ignored by unified search.

## Trusted reads

Use existing trusted launch configuration and a private host policy. A query
argument cannot select or grant a more privileged host. For example, with a
previously configured `codex` policy:

```sh
CASTLE_BRAIN_HOST=codex castle --palace /absolute/palace search "Sixth Sense"
```

Full local-source grants or selected complete-source hashes are applied before
ranking and checked again after reading. Workspace, wing and room filters narrow
results; they never grant access. Historical unknown scope is not a scoped match.
No-host ordinary recall is refused rather than falling back to native history.

Responses retain canonical `memory:<sha256>` IDs, source hashes and exact paged
text. Use `castle_memory_read` with `expected_hash` for exact text pages. Imported
sources also expose a metadata descriptor: `field="metadata"` returns exact
original metadata JSON, and `field="columns"` returns stored nonvector columns;
use the corresponding descriptor hash. Offsets are codepoints, not UTF-8 bytes.

Ranks are interleaved by each store's lexical ordinal, with deterministic ties;
raw FTS scores across different corpora are not comparable. Continuation cursors
bind the query, scope, authorization and store generation. A stale cursor requires
a fresh search. Distinct historical occurrences are preserved even when old
drawer IDs or text are equal.

## Historical conversion

The optional `history` installation extra declares the supervised native reader
(`pylance 4.0.1` and `psutil`). Ordinary memory reads require no native reader.
The `memory` extra declares `psutil` for bounded process supervision.

Only an operator initiates conversion, using an original local drawer archive:

```sh
castle --palace /absolute/palace memory history prepare --source /absolute/palace/lancedb/castle_drawers.lance
castle --palace /absolute/palace memory history index
castle --palace /absolute/palace memory history status
```

`prepare` and `index` each perform one bounded slice. Repeat `prepare` until its
state is `prepared`, then repeat `index` while progress is pending. Refusals and
blocked rows remain visible. There is no implicit background miner or migration
triggered by a search. An operator scheduler may invoke slices, with admission
released between them; normal capture keeps its existing schedule.

An earlier converter rejected text over 1 MiB even when it fit the independently
bounded native batch. Exact text fitting that unchanged 2,162,688-byte batch is
now stored in 8 KiB chunks. Metadata retains its 1 MiB limit. For a large row,
the history worker first reads bounded projected text pages (at most 131,072
codepoints per page) from the pinned snapshot and stages exact chunks privately.
Each worker slice copies at most four projected pages before releasing the native
process, in addition to the existing time and RSS guards. This bounds repeated
native projections within one process even when decoding a large source row.
The public occurrence and its cursor receipt are committed together in one SQLite
transaction only after all pages are staged and the complete source-text hash
matches the native header hash; the scan checkpoint advances after that receipt.
A durable stage resumes across slices; readers
do not see a partial occurrence. The complete source hash is retained even
though the public text is represented by bounded chunks. Existing recorded
`row_size` gaps may be repaired individually using their original immutable
cursor and registered store ID:

```sh
castle --palace /absolute/palace memory history repair --store-id SHA256 --fragment N --offset N --row-address N
```

The offset is the cursor **before** the rejected row; omit `--row-address` only
when the original cursor omitted it. Repair verifies the pinned snapshot, row
identity and existing receipt. It preserves the original gap in a resolution
audit, commits exact text atomically in the same store, and leaves the main scan
cursor unchanged. Identical retries reconcile durable completion. A full store,
unmatched cursor, different gap reason or resource refusal leaves the gap visible;
repair never expands limits or silently moves data to another store.

The converter uses a private immutable copy and pinned version. It projects no
vectors, writes exact chunks and metadata, and commits receipts before advancing
its durable cursor. Large-row staging is private until the atomic public
handoff; interrupted staging is resumable and its progress or blocked failure
is visible in job status. Projection bounds returned values, but native decoder
allocations remain subject to the existing guardian, IO/cache controls and
installed-stack qualification. Duplicate aliases cannot overwrite distinct source rows.
Original archives and transcripts are preserved. A stopped or failed conversion
can leave useful committed imports searchable with explicit partial coverage.

Fast jobs retain 128 MiB aggregate task / 192 MiB including the caller. History
jobs use 512 / 640 MiB and at most ten seconds including cleanup. Both share one
per-user admission lock and require normal macOS memory pressure. These are
sampled RSS tripwires, not kernel-enforced allocation ceilings. Other platforms
fail closed where the required supervision is unavailable.

Historical storage is separate from live capture: up to eight bounded stores,
8 GiB aggregate output, 4 GiB snapshots and at least 2 GiB free headroom. Exhausting
capacity reports a gap; it never deletes originals or summarizes them to fit.

## Coverage and activation

`coverage_detail` reports absent, partial or blocked history and unavailable
stores. An empty search does not prove that the original history contains no
match. Search results are evidence of what a source said, not verified truth.

Implementation tests and small native fixtures are not full-corpus qualification.
Before live cutover, validate actual archive capacity, bounded progress, restart
recovery and new-plus-historical exact recall. The integration is not complete
until the declared readable historical inventory is reconciled. Existing clients
must reconnect to load changed code; this work does not silently authorize another
host, change source grants or enable the old nightly miner.
