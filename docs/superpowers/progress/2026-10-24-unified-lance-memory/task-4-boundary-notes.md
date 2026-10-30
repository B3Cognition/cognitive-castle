# Task 4 retrieval boundary — narrow preparation

2026-10-24. Read-only source inspection; this note is the only write. No tests,
native/model imports, database opens, real palace access, git or service changes.
Read AGENTS.md, Task 4/global constraints, shared-retrieval spec, selected 3a brief
and its minimal appendix. The earlier capture/context audit remains authoritative;
this does not repeat its route/SQL inventory. Root owns design decisions.

## Conclusion and load-bearing 3a constraints

**Keep the selected six-string exact format.** Canonical scope/descriptor pages
are sufficient preservation, but are not a scalable search predicate. Add a
rebuildable, versioned typed retrieval projection later; canonical hydration and
text/metadata paging still come only from committed Lance exact records. Nothing
found requires 3a to adopt its rejected seven-kind schema or a spool framework.

The following preserved data is essential to building that projection:

- Original canonical ID, exact text/provenance and exposure hash; published owner
  identity, member ordinal/offsets, membership pointer and hashes. Enumerate all
  committed owner memberships, including owners reusing existing visible records;
  a record's first owner pointer alone is not the occurrence inventory.
- Full original scope inputs with their origins: historical columns, metadata,
  caller fallback; separately immutable capture assignment, source key/generation,
  attribution, first-workspace/conflict boundaries and source time. Missing,
  empty, non-string and conflicting inputs must remain distinguishable. A source
  later entering conflict does **not** revoke its previously assigned chunks.
- Exact original drawer alias, occurrence ID and immutable archive/snapshot/source
  version/fragment/row-address binding. Alias is a many-occurrence relation. Keep
  zero-chunk occurrences in the inventory. Do not normalize the stored alias or
  replace it with a canonical chunk ID.
- Exact metadata/columns pages already retain `ts`, novelty, role and other
  configured ranking inputs. These need not enter exposure-bearing provenance.

The brief requires these already. Their detailed page codec must allow a trusted
bounded iterator to recover them, including reused records and large scope pages.
No extra small caller envelope may become authoritative.

## Concrete current interfaces and reuse

`LanceExactStore.read_sources(ids)` remains the visibility/hydration gate; its
shared bulk-owner check must also protect derived publication. `page` and private
descriptor/membership reads supply exact evidence. Build indexes only from a
pinned committed exact version, acknowledge their own generation after publication,
and report lag separately. Reads never build indexes or open old exact SQLite.

`LanceVectorStore.nearest(vector, profile, generation, scope,
allowed_source_hashes, limit)` already has typed `canonical_id`, `source_hash`,
`exposure_hash`, workspace/wing/room and profile fields. It uses Arrow expressions,
`prefilter=True`, bounded output and explicit generation checking. Reuse that
pattern, its compact/input checks, and `semantic_indexer.query_exact` hydration
checks; the latter is an internal helper, not the ordinary coordinator.

**Policy mismatch requiring a Task 4 fix:** `BrainAPI.policy()` calls its grant
list `allowed_source_hashes`, but these are hashes of **ID + complete exact text +
original provenance**. `nearest` currently compares its identically named argument
with **text-only `source_hash`**. Filter `exposure_hash` before nearest ranking.
Use an unambiguous private `allowed_exposure_hashes` name and deliberately adapt
the existing public policy field. Same text in another source is not a grant.

The current vector scope validator requires one complete nonempty bounded tuple
(2048/512/512 UTF-8 bytes); it does not support omitted query axes, absent scopes,
long scopes or the capture workspace alternative. Thus it is not yet the general
policy provider. Keep Task 2 publication compatibility; introduce a reviewed
versioned projection/query extension when those cases are implemented. Never
reinterpret existing raw scope fields as hashes or mutate compact unit identity.
Until supported, disclose the affected semantic coverage/refusal explicitly.

Reuse `fusion.CandidateRef` with **canonical IDs in `drawer_id`**, `weighted_rrf`,
recency and configured information weighting. Deduplicate each signal by canonical
ID before assigning its final rank list: multiple windows, KG edges or aliases
must not receive repeated RRF contributions. Preserve distinct canonical IDs even
when their text/alias is identical. Retain winning unit offsets in a side map.
`weighted_rrf` itself does not deduplicate repeated entries.

## Minimal typed projection and provider contract

One lexical document per canonical chunk avoids duplicate-document BM25 effects.
A derived Lance projection can contain the following bounded fields:

| Fields | Purpose |
| --- | --- |
| `canonical_id, source_hash, exposure_hash` | Exact evidence binding and selected grants |
| `owner_id, member_page_id, member_ordinal, scope_binding` | Revalidate committed membership and full canonical scope pages |
| `workspace_key, capture_workspace_key, wing_key, room_key` (nullable), explicit scope/assignment state | Filter every requested axis before ranking |
| `text` | Exact ≤8 KiB chunk copy used only to build/query the derived FTS index; never a hydration fallback |
| `timestamp_unix, novelty` (nullable) | Preserve configured fusion inputs from their original recorded fields |

Generation/format/exact-version bindings belong in the projection manifest, not
necessarily repeated in every row. Context additionally needs typed source key,
source generation/time, role and record/chunk offsets; immutable chunk references
join the separately versioned current-source/work-state coordination. Reuse the
existing audit's context contract, including pinned older evidence.

Use fixed-width domain-separated digests of complete, type-tagged scope values for
`*_key` if arbitrary-length canonical strings would break bounded projection.
Keep the full original values and binding in exact pages; do not truncate, fold
case, resolve paths or substitute empty strings. Null is absence, never a wildcard
matching a requested value. Hash keys are derived lookup keys, not new evidence IDs.
Bounded exact scope verification remains necessary when hydrating candidates.

Current `_selection` semantics matter: the principal scope follows historical
columns → metadata → caller precedence; workspace can also match the immutable
capture assignment. A single overwritten workspace loses that OR branch. Existing
`capture_chunk_scopes` is primary-keyed by chunk ID, so two nullable workspace
keys suffice for the **current** contract without a giant membership array.
Do not infer a new multi-scope authorization model from future owner reuse.

Private provider shape, not a new public framework:

```
snapshot -> generation_id, exact_version, lexical_version, vector_version,
            kg_version, scope_revision, coverage
candidates(query, match, scope_predicate, exposure_grants, snapshot, limit)
  -> bounded canonical references + signal rank/score + offsets + stage status
hydrate(ids, snapshot) -> committed exact sources, checked hashes/scope bindings
```

Resolve trusted host policy once before providers, re-read its epoch before
returning, and reject changed policy. Bind cursors/cache entries to query, match,
all scope axes, sorted exposure grants, policy epoch, immutable source generation
and every participating index version. Context cache also binds work-state
revision. One coordinator serves ordinary CLI/Python/MCP/brain/context callers;
model-free context is a coordinator operation, not a separate canonical store.

## Bounded lexical strategy and actual installed API evidence

Inspected files as text under `~/.echelon/venv/lib/python3.12/site-packages`:
`pylance 4.0.1`, `lancedb 0.30.2`; no imports. Native Lance already exposes:

- `LanceDataset.scanner(columns, filter, full_text_query, prefilter, limit,
  batch_size, strict_batch_size, batch_readahead, fragment_readahead,
  io_buffer_size, use_scalar_index, fast_search, order_by)`.
- `create_scalar_index(column, "INVERTED"/"FTS"/"BTREE"/"BITMAP", ...)`,
  `list_indices()`, `index_statistics()`, and versioned dataset opening.
- `lance.query.MatchQuery(..., operator=FullTextOperator.AND/OR, fuzziness=0)`;
  plain string FTS defaults to OR, so it cannot silently replace `match=all`.

Candidate implementation: supervised explicitly maintained INVERTED index on the
derived `text`, suitable scalar indexes on typed scope/exposure keys, bounded
projected scanner, and the **combined authorization predicate inside that same
search**. No corpus-wide eligible-ID array, Python JSON scope scan, or global
top-K followed by filtering. The installed scanner docs explicitly guarantee
`prefilter` ordering for vectors, not FTS: FTS filter-before-top-K semantics still
need a focused native fixture/query-plan qualification before this is adopted.
The Python signature alone is not proof. Refuse that subrequest if it cannot be
established under restricted policy; do not substitute postfiltering.

FTS build defaults are unsuitable: docs specify 2 GiB **per worker** when unset,
CPU-count workers, English stemming/stopwords, accent folding and removal of
tokens longer than 40. Use explicit bounded maintenance settings and qualify
Unicode/literal matching against the present FTS5 semantics. Do not invent a
memory allowance here. Track indexed fragments and bounded append tails; include
tails where qualified or expose `lexical_pending`. `fast_search=True` explicitly
omits unindexed data. Neither that option nor an empty result proves completeness.

The existing `LanceCollection` wrapper is unsuitable unchanged: collection open
can create FTS/stamp identity, and `fts_search` swallows failures as `[]`. Current
vector reads also disable indexes and scan all vectors; bounded result count is
not corpus-scale latency qualification. Reuse worker guards, not these defaults.

## KG bridge: preserve original graph and occurrence multiplicity

`KnowledgeGraph.find_drawers_by_entities` filters subject OR object, groups by
original `source_drawer_id`, ranks by **COUNT(DISTINCT subject)** then
`MAX(extracted_at)` then drawer ID. Its docstring's “distinct queried entities” is
not exactly the SQL calculation. Preserve observable semantics unless separately
reviewed. `KnowledgeGraph()` writes/migrates on open; ordinary reads need a fixed,
read-only adapter, not this constructor. Entity matching is reusable, but current
`EntityRegistry.lookup_in_text` scans people/project names; it does not justify
inventing broader alias matching or rebuilding the registry during reads.

The minimal bridge is a derived relation:

```
(graph_generation, triple_id, subject_id, object_id, original_source_drawer_id,
 extracted_at, validity/provenance binding)
    -> (archive/snapshot/source version, occurrence_id)
    -> (canonical_id, member ordinal, exposure_hash, typed scope keys)
```

Preserve original graph rows/aliases and every matching committed occurrence;
do not dictionary-collapse `alias -> one memory ID`. A legacy edge naming only an
alias cannot prove which duplicate occurrence produced the edge. Retain that
ambiguity as derived association, use available source-file/version provenance
to disambiguate, and never present a new graph fact as verified source evidence.

Apply scope/grants on canonical mappings **before KG grouping/order/limit**.
Then expand bounded canonical candidates with deterministic occurrence/member
tie-breaks and deduplicate per signal. Legacy paging of 100 global aliases until
enough scoped rows happen to match is not a bounded substitute.

For exact SQL aggregation semantics, a metadata-only derived join/index alongside
the existing KG is the smallest reuse option for root to evaluate: edges,
occurrence/canonical references, hashes and typed policy keys, **no canonical
text/metadata bodies**. It must be rebuilt/version-bound from Lance and protected
graph evidence, with indexed joins, deadline/row-work bounds and explicit pending
coverage. It must never answer exact reads. Native Lance scanner has no exposed
group/join API here; do not pretend `scanner(limit=...)` implements that contract.
If root requires all derived indexes in Lance too, qualify a bounded graph
aggregation projection separately before enabling KG; this is not a reason to
redesign 3a or silently drop configured KG.

## Confidentiality and remaining gates

Preserve `coverage="indexed_only"`, bounded exact previews and whole-source
exposure hashing before preview mutation. Selected-source grants authorize only
ID/text/provenance: suppress top-level metadata descriptors, deny metadata/columns
pages and context/work-state operations as `BrainAPI` does today. Do not return
scope pages, graph properties, alias inventories or unrelated source counts as
new grant side channels. Every KG candidate needs an authorized canonical binding;
unbound graph facts are not ordinary memory evidence.

Keep semantic/KG/reranker availability, profile/index generation, pending work
and refusal reasons through public envelope adapters; `BrainAPI` currently copies
only a short result-key allowlist. Do not turn failures into successful empty
lists. Reranker quality/resource qualification remains its separate pending
diagnostic; this note proposes no change to it.

Before cutover, independently qualify FTS authorization-before-limit, exposure
grant identity, duplicate aliases/windows, absent/long/conflicting scope handling,
staged owner exclusion, version/policy changes, indexed tails and corpus-scale
work under the unchanged supervised ceilings. These are later integration gates,
not claims made by this source-only preparation.
