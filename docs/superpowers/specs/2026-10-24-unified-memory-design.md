# Unified exact memory and guarded historical indexing

Status: user directed implementation on 2026-10-24; implementation and qualification in progress. Live configuration is unchanged.
Baseline: B3Cognition/cognitive-castle `67996f0` (`develop`).

## User outcome and constraints

User-set goal, verbatim:

> Za cílové řešení považuji sjednocené vyhledávání nové i historické paměti, s doslovným průběžným zápisem a odděleným, hlídaným pomalým indexováním. Dvě různě aktuální vyhledávací cesty zatím znamenají nedokončenou integraci.

Earlier explicit constraint:

> I need this Cognitive Castle be your memory like SLow/Fast but with all respect to low memory usage

The user wants durable continuity and understanding without machine-wide memory
pressure, misleading completeness claims, lossy summaries, or excessive complexity.
New and historical evidence must be discoverable through one ordinary query route.
Source words are preserved exactly; interpretation, work state and SUE judgments
remain separately attributed. A stored claim is not verified truth.

## Verified starting point

- Bounded capture writes exact supported conversation text into private SQLite
  `.memory/memory.sqlite3`. Both original Claude and Codex roots are registered.
  Unsupported records, old accounting gaps and pending work remain explicit.
- `castle memory recall` and configured `castle_brain_recall` use that sidecar.
  `castle search`, `search_memories` and MCP `castle_search` use the older LanceDB
  pipeline. Even its existing `fast` mode embeds and reranks.
- The user reports approximately 519,641 legacy drawers. This design audit did
  not native-open the live archive to recount it. Its size and decoded text volume
  must be measured under supervision before enabling a migration.
- A subsequent bounded filesystem-metadata observation found 14 files, one
  manifest, no symlink entries, and 1,980,580,641 logical bytes in the legacy
  drawer archive. The largest file was 1,806,716,289 bytes; free disk space was
  22,251,536,384 bytes at observation. This supports the proposed 4 GiB snapshot
  allowance for that observed inventory only. It does not establish a stable
  snapshot, decoded row sizes, converted index size, native RSS, or row count.
- The existing safe native reader requires a special fixed-width schema and
  copies at most 64 MiB. It cannot safely read the ordinary legacy palace as-is.
- Native backend constructors can create indexes or stamp metadata. Existing
  `iter_columns` has a whole-table fallback and converts batches to Python values.
  Neither is an acceptable unchanged read-only historical converter.
- PR106 is closed without merge. PR107–109 are a separate draft stack. Verified
  PR108 provider code reads prepared LanceDB, not the SQLite capture sidecar.
  It therefore does not already implement this unification. Publication is outside
  this work; shared hardening must be reconciled without reintroducing native SOAR.
- Existing Codex client refresh and Claude startup-context integration remain
  separate unfinished host activation tasks. This design does not silently enable
  another host or claim those tasks are solved by indexing.

## Chosen architecture

Builder choice for review: keep SQLite FTS5 as the common exact-text query layer.
Continuous capture remains the immediate source of fresh searchable text. A
separate supervised converter imports immutable historical archive snapshots
incrementally into bounded historical SQLite stores. Ordinary queries never load
Lance, an embedder, a reranker or an LLM, and never trigger capture or backfill.

Original transcripts and Lance archives remain unchanged. The SQLite stores hold
exact source chunks and their identities; the FTS tables are derived indexes.
One logical query service searches the live store and every registered historical
store under one output/time/resource budget. Missing or unfinished stores are
reported as incomplete coverage, not silently replaced with an empty successful
search. No ordinary native-Lance query fallback is allowed.

Why this choice: native federation on every query couples recall to native import
cost, large variable-length rows and mutable archive state. Re-enabling legacy
nightly mining does not join the indexes or enforce the bounded-memory contract.
Keeping historical stores separate physically also prevents backfill from filling
the live-capture store. Physical partitioning must not produce separate public
search APIs or different source freshness rules.

## Public query and compatibility contract

Introduce one internal query service shared by default CLI search, Python
`search_memories`, MCP `castle_search`, `castle_brain_recall` and workspace context
selection. Existing response envelopes may remain adapters, but must expose the
same canonical references, coverage and limitations. A filtered workspace context
is a view over the same data, not another independent archive.

- Query supports literal all/any matching, explicit workspace/wing/room filters,
  a bounded result count and a validated opaque continuation cursor. Unknown scope
  is not a match for a requested scope. Scope is never inferred from a keyword.
- Default ranking is deterministic lexical ranking with an explicit stable tie
  rule. Historical and live FTS scores must not be compared as calibrated values
  across different corpora; use a documented deterministic rank fusion. File mtime,
  ingestion time and known event time are separate fields, not interchangeable.
- At most eight exact previews fit the existing 8 KiB inner response budget;
  adapters preserve the separate 32 KiB MCP envelope bound. Exact pages retain
  codepoint offsets, hashes and truncation markers. Reaching a time, result,
  fan-out or output budget reports the limitation and a resumable position where
  possible. It never reports an exhaustive search.
- Cursors bind query, filters, authorization epoch and a catalog/index generation.
  A changed or expired generation requires an explicit restart; offset pagination
  must not silently duplicate or skip hits after concurrent capture.
- Preserve distinct source occurrences and conflicting revisions. Text equality
  alone does not identify a memory. Deduplicated presentation retains all selected
  occurrence references; it must not erase a correction or equate recency with truth.
- Existing `memory:<sha256>` IDs, hashes and exact-read behavior remain valid.
  Historical occurrences get deterministic IDs incorporating archive identity,
  pinned version, physical row identity and chunk position. Duplicate old drawer
  IDs cannot overwrite each other. Old drawer IDs are explicit potentially
  one-to-many aliases, not canonical unique keys.
- Canonical reads hydrate and validate source text before returning it. A hash or
  provenance collision is an error. SUE binds canonical memory IDs so mixed
  historical/live evidence can be examined through the existing bounded workflow.

Change the omitted search mode to the common model-free route. Distinguish omitted
mode from explicitly supplied old options in parsers and Python signatures; do not
silently reinterpret an explicit model-backed request as equivalent lexical search.
Retain old mode semantics only behind an explicit documented legacy diagnostic
route, visibly marked as legacy-index-only. Compatibility tests cover envelopes,
filters, IDs, option rejection and absence of hidden model loading. The ordinary
entry points must all see freshly captured data without legacy mining.

Existing trusted-launch host policy is required on assistant-accessible reads and
is rechecked after work. Requests cannot nominate a more privileged host. Namespace
is attribution/state isolation, not a per-user access-control boundary. A source
filter never grants exposure. Selected-hash grants must be applied before ranking
and limit accounting to prevent unauthorized candidates displacing authorized
ones; preserve their existing ID/text/provenance hash meaning. Never auto-authorize
Claude or expand a host's source policy during migration. CLI documentation must
show explicit trusted launch configuration rather than silently infer a host.

## Continuous capture and historical conversion

Keep current exact supported-text capture, original root restrictions, append-only
history and per-source checkpoints. Historical work must not consume the reserve
needed to record fresh messages, failures and retry state. Successful processing
of transcript bytes remains distinct from complete supported-text capture.

Historical conversion is an operator-enabled job with these durable stages:

1. Register the original archive and persist a versioned inventory/pending job.
2. Create and verify a private immutable working snapshot without native-opening
   originals. Pin the exact manifest/version and referenced files. Use filesystem
   cloning when supported or bounded streaming copies with disk admission; no
   links back to mutable originals. Revalidate identities/manifests around copy.
   Concurrent change invalidates the attempt and preserves the last completed pin.
3. Native-read only the private snapshot in a disposable supervised worker.
   Project text/identity/required metadata, never vectors. Require a validated
   streaming scanner with bounded prefetch and no whole-table fallback. A row-count
   batch size alone is not a bound on a variable-length row's decoding allocation.
4. Persist exact UTF-8 chunks plus an archive-specific provenance registry and
   receipt. Commit destination data before advancing the source checkpoint;
   retries are idempotent. Keep large original metadata in exact paged storage,
   not in a silently truncated 512-byte caller-provenance field.
5. Validate committed source/chunk hashes and account for every inventory item:
   pending, indexed, changed, unsupported or blocked. Publication of a completed
   historical store/catalog generation is atomic; incomplete durable work remains
   identifiable. Queries can use committed imports with explicit partial coverage.

Physical row/fragment cursors bind the immutable snapshot, not offsets in the
mutable live archive. Resume after process death without rescanning from row zero
for each batch. Do not reuse a cursor after source compaction/version change.
Do not promote archived agent prose or embedded `user_input` fields into trusted
user messages or current instructions.

A huge row, invalid metadata, memory rejection or unsupported native format gets
a durable pending/blocked identity and explicit coverage gap. Repeated attempts
must not loop forever or be counted as success. Other independent source items may
progress only when the unresolved item remains in the ledger. Storage-full errors
must remain visible even when a failure record cannot be written; never invent a
durable receipt. No pruning, summarization or deletion is used to make a budget fit.

## Resource and capacity policy

Builder choices for review; these are sampled tripwires, not hard kernel ceilings:

- Fast operations retain 128 MiB aggregate task / 192 MiB parent-plus-task limits,
  two-second read deadlines, bounded SQLite caches and no mmap.
- Historical native conversion uses a separate 512 MiB aggregate task limit,
  matching the existing native-reader ceiling, plus a new 640 MiB parent-plus-task
  tripwire. It has a ten-second total slice deadline including import and cleanup.
  It must be qualified on the actual native stack before live activation. If the
  baseline or a row does not fit, report blocked work; do not increase limits.
- Every job checks normal macOS memory pressure, uses owned process-group cleanup
  and retained process identity, and releases admission only after descendants
  terminate. No resident model or worker. One per-user admission mechanism prevents
  overlapping native indexing/capture/read workers. Scheduling gives interactive
  reads and fresh capture priority; a queued backlog must not imply an infinite
  exclusive job. Backoff and deadline refusal preserve progress.
- Keep the existing 1 GiB physical live-store envelope, including rollback and
  temporary-work reserve. Its page quota is roughly one third of that envelope.
  Do not fill it with legacy imports.
- The original historical per-store allowance is superseded by the
  [historical capacity and completion design](2026-10-24-history-capacity-completion-design.md):
  historical stores have a 2 GiB physical envelope each, at most eight stores and an
  unchanged 8 GiB aggregate output budget; live storage remains 1 GiB. Historical
  storage also has a separate bounded snapshot allowance up to
  4 GiB. These are operator-controlled maxima, not reservations or allocations.
  Admission requires measured source/output projections and at least 2 GiB free
  headroom beyond the admitted operation. Stop visibly before exhausting capacity.
  A source too large for this policy remains pending; quota exhaustion is not a
  completed migration. Do not create unlimited shards to evade storage limits.
- Query fan-out includes at most the live store plus eight historical stores,
  sequentially with a shared deadline and output budget. The small private catalog
  is atomically updated and bounded; avoid a resident cache or loading all records.

The builder may choose schema details and batch/prefetch sizes within these bounds.
Resource limits, authority, source fidelity and treatment of gaps are not optional.
The existing 100 ms startup target remains a measured target, not a claim already
met. Record all latency samples, including refused and slow starts.

### Installed native-scanner preflight

Source-only inspection identified `pylance 4.0.1`, `lancedb 0.30.2` and
`pyarrow 24.0.0` in the current installation. No native module or live archive
contents were loaded for this inspection. The installed Python API supports an
explicit integer dataset version, byte-based metadata/index cache budgets,
disabled repetition-index caching, explicit nonvector projection, selected
fragments, physical row addresses and direct `scanner.to_batches()` iteration.
The existing backend's whole-table fallback is unnecessary for that candidate.

However, installed `lance/dataset.py` documents a **2 GiB default v2 I/O buffer**,
states that it is not a hard RAM bound, and warns of deadlock when a single batch
exceeds a smaller buffer. V2 ignores `batch_readahead`; returned batches can exceed
the requested target row count. Therefore zero readahead or `batch_size=1` does
not qualify the converter. Set an explicit I/O budget, validate effective cache
settings and qualify both oversized decoding and watchdog cleanup on the exact
installed native stack. Unsupported controls fail closed without fallback.

Physical row addresses encode fragment and row offset, but efficient restart
without decoding earlier rows was not established by source inspection. The
qualification must verify deletion-aware cursors and durable progress as well as
vector exclusion, import baseline, maximum-row RSS and cancellation. These are
implementation entry gates; this preflight proves candidate controls exist, not
that the 512/640 MiB resource proposal already works on the historical corpus.

## Slow semantic indexing and existing integrations

This project must ship safe historical text conversion/indexing and common reads;
simply adding another optional endpoint is insufficient. Native vector and KG
indexes remain derived optional enhancements. They never become the sole storage
of new messages or a prerequisite for ordinary recall. No existing nightly miner
is enabled as a shortcut.

The common interface may accept explicitly selected semantic candidate references,
but every candidate must be revalidated/hydrated against canonical exact memory.
Stale or missing semantic coverage cannot hide fresh lexical evidence. No new
embedding model, external provider or package publication is enabled by this work.
Any later semantic-index job must use the same durable scheduling, lineage,
pressure and independent resource qualification contract. Existing SUE examination
and article-form assessment stay outside retrieval; native SOAR stays removed.

PR107–109 and local status commit `63c8f2b` must be reviewed as separate workstreams.
Do not treat their prior green checks as evidence for a newly combined tree.
Avoid rewriting another contributor's draft branches. Reconcile compatible
hardening where needed; integration with PR108 must use the common interface or
remain explicitly described as a separate legacy provider until adapted.

## Evidence, rollout and definition of completion

Public synthetic tests must cover fresh plus historical retrieval through every
ordinary entry point, exact Unicode/whitespace/NUL preservation, duplicate drawer
IDs and source occurrences, source revisions/corrections, filtered scopes and
revoked policies, cursor invalidation, restart and crash boundaries, concurrent
capture, disk-full handling, blocked giant rows, source mutation, caller/worker
RSS refusal, deadline/pressure refusal and parent/descendant death. Prove legacy
originals remain unchanged and that queries import no models/native archive code.

Keep resource integration tests in fresh processes; the current main-suite
documentation must match CI's actual split. No production guard is relaxed to
make a heavyweight pytest process pass. Local tests use guarded explicit selections;
full model-dependent platform verification stays in CI.

Use the existing private Sixth Sense evidence, plus a tiny genuinely new captured
message and a previously unindexed historical occurrence, to show both appear in
the same response and remain exact/readable after restart. Measure complete
evidence delivery under fixed budgets, not only candidate hits. A separate bounded
native pilot qualifies the proposed converter/scanner; if it fails, revise the
design rather than declare an incomplete metadata scan a migration.

Rollout preserves original backups, capture pause markers and unrelated client
settings. Cut over only verified catalog generations, with an explicit rollback
that keeps captured data and imported exact chunks. Reinstallation and actual
host dispatch are separate checks; do not restart another active session blindly.

Implementation release requires review, all required checks green on the exact
integrated head, authorized merge/install, a working default unified query with
real new/history evidence, resumable supervised indexing, and recorded
coverage/resource/rollback proof. A successful tiny pilot is not sufficient to
claim the user's goal achieved.

Before live cutover, qualify a feasible path for the entire declared historical
inventory: its snapshot must fit, projected text/index/metadata output must fit
with headroom, and the scanner must make durable progress under the resource
policy. If a capacity or decoding limit permanently prevents that, revise the
approach or obtain an explicit policy decision; do not ship that permanent gap as
a completed integration. Do not reclassify an inconvenient row as unsupported to
pass the gate.

A staged release may report a progressing historical backlog, but the user goal
remains incomplete until the declared historical inventory is reconciled and its
readable text is searchable through the common default route alongside fresh
capture. Blocked, unsupported or corrupted source items need an explicit resolved
disposition or a user-approved exclusion; accounting for them alone is not complete
recall. Coverage distinguishes that declared snapshot from later unseen history.
Outstanding host activation remains a separately stated integration limitation.

## Design review disposition

A fresh builder's only material question was whether a permanently quota-blocked
migration could satisfy completion. The user asked for unified historical memory,
so the answer is no: the qualification and completion gates above require a
feasible full-inventory path, and distinguish a staged release from achieving the
goal. No additional user preference was needed to resolve that question.
