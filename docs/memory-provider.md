# Optional Prosaic memory provider

Castle supplies local, read-only evidence retrieval. The provider defaults to
`memory-fts-v1`: raw FTS ordering, exact-passage deduplication and source
validation. Recency boosting is opt-in. Dense and graph recall are disabled in this
profile; no embedding or cross-encoder model is imported or loaded. FTS failure
is unavailable memory, with no automatic profile switch.

Hosts can explicitly select `memory-v1` for dense + FTS + scoped graph recall
and cross-encoder reranking. Both profiles exclude SUE, SOAR, the quality
analyzer and a generative judge. Standalone Castle mode defaults are unchanged.
Capture coverage is limited to material explicitly ingested by an operator.
Stored text is evidence of what a source said; a ranking score is not a truth
assessment or probability.

| Component | Owns |
| --- | --- |
| Castle | Original records, revisions, indexes, scope checks, search/fetch/snapshot, private worker |
| Optional adapter | Worker lifecycle, bounded transport, Runtime custom-tool bindings |
| Runtime | Model execution, granted tool execution, cancellation, deadlines, safe tool errors |
| Harness | Durable workflow/conversation state, receipts, persisted frozen inputs and resume |
| Host application | Trust-domain identity, allowed wings, authorization, memory policy and snapshot persistence |
| Prosaic Core | Markdown distribution and read-only catalogue discovery |

The adapter has no Castle or Harness dependency. Install Castle in a separate
worker environment; model weights are needed only for the hybrid serving profile
and ingestion paths that create embeddings. Install the adapter only in consumers
that select memory. Core, Runtime and Harness do not import Castle. Runtime
needs the generic `custom_tool_errors_v1` capability; the candidate patch is
qualified separately before any release version is selected.
Castle's distribution still declares its existing neural dependencies. This
change avoids their serving-time import and model loading for FTS; it does not
introduce a separate slim worker package or change ingestion behavior.

## Operator setup

Use an absolute worker executable and absolute palace/config paths. The worker
reads the supplied JSON config file and freezes its resolved settings. The FTS
default needs an existing prepared FTS index and no model cache. For hybrid
serving, provision models explicitly beforehand; its model loading is forced
offline. CPU selection applies to embeddings and reranking.

```sh
castle provider prepare --palace /srv/castle/project --namespace project-opaque-id --config-dir /srv/castle/config
castle-provider --palace /srv/castle/project --namespace project-opaque-id --config /srv/castle/config/config.json --wing approved_project
# Explicit hybrid opt-in: add --profile memory-v1 to the worker command.
# Explicit FTS recency opt-in: add --recency-boost (without hybrid selection).
```

In the Prosaic adapter, use `CastleMemoryProvider(..., profile="memory-v1")`
to opt in. Omitting `profile` selects `memory-fts-v1`. The host binds the profile
in worker argv and verifies it during handshake; model tool arguments cannot
select it. Health reports the selected profile and a fingerprint of its active
ranking configuration. Scores from the two profiles are not comparable.
To opt into FTS recency, pass `recency_boost=True` to `CastleMemoryProvider`.
The default is `False`, independent of existing Castle recency/fusion settings.
The host binds the flag in argv and verifies the boolean in health/handshake;
model arguments cannot select it. Workers predating this explicit flag metadata
are rejected by the updated adapter, preventing silent use of their older
recency-enabled default. Deploy the matching candidate worker and adapter together.

Preparation binds one palace to one opaque namespace in `.provider/identity.json`.
It refuses rebinding. A namespace label is not authentication: the host grants
filesystem access and authorizes the caller. Allowed wings must be nonempty.
No path, namespace, actor or credentials can come from model arguments.

Serving opens existing stores read-only. It never migrates, stamps an embedder
identity, creates a table, rebuilds FTS or changes source permissions. In the FTS
profile, an unverified dense identity does not degrade health; unusable FTS fails
health and search. Hybrid serving preserves its existing degraded-signal behavior
and requires a provisioned reranker at startup. Preparation explicitly repairs
FTS if needed, verifies it and binds the namespace. Use `castle optimize` as an
explicit maintenance operation if an old FTS index needs repair.

FTS recall takes up to 100 scoped candidates before grouping and hydration.
Strictly decreasing ordinal scores preserve backend FTS order, including ties,
through scope filtering and exact-passage grouping. Each group retains its best
FTS position while selecting the newest identical source as primary provenance.
Legacy fusion weights/smoothing, neural reranker budgets, information weighting
and mode policies do not change this ordering. Scores express rank, not raw BM25.

With explicit FTS recency enabled, the configured recency timescale/maximum apply.
The profile reads valid legacy `ts` values and falls back to `filed_at` capture
time; unknown captures receive no boost. Hybrid and standalone recency behavior
is unchanged. This profile trades semantic/paraphrase and graph-only recall for lower serving cost;
it makes no completeness or truth guarantee. Storage formats and vectors are
retained, so selecting hybrid later requires no migration of provider data.

Search re-reads primary and bounded alternate IDs in one authoritative batch
after recall/hydration. Every row still receives scope, registry-sentinel,
revision completion/membership, exact-text digest and provenance validation.
Malformed batch shapes, duplicate IDs and unrequested IDs fail closed. Missing,
foreign or incomplete sources remain hidden, and changed/missing alternates mark
provenance incomplete. The batch is request-local; no text, authorization or
completion result is cached across requests. Reads still observe committed
changes through the read-only backend. Fetch and snapshot retain exact-source
validation and their existing output bounds.

New custom palaces keep auxiliary state inside their own `.castle/` directory.
Recognized default legacy paths stay readable. An ambiguous custom layout with
sibling graph/registry files requires an explicit operator choice; do not merge
customer palaces or point them at a shared developer registry. A reviewed
`.castle/paths.json` can select relative in-palace graph and registry paths:

```json
{"version":1,"knowledge_graph":".castle/knowledge_graph.sqlite3","entity_registry":".castle/entity_registry.json"}
```

Use explicit migration to copy selected state, verify hashes/counts and retain
the originals. It never implicitly imports an unselected sibling store:

```sh
castle provider migrate --palace /srv/castle/project --legacy-graph /reviewed/knowledge_graph.sqlite3 --legacy-registry /reviewed/entity_registry.json
```

Migration uses SQLite's backup API to capture committed WAL records, publishes
new private files without overwriting different files and writes the path
manifest last. A closed WAL database without existing
sidecars cannot be opened under the strict no-write contract; an operator must
checkpoint it and select DELETE journaling while no writer holds it.

## Read and execution boundaries

`memory_search` accepts query/limit; `memory_fetch` accepts record ID and exact
character offsets. The trusted authorizer runs before dispatch. Guessed foreign
IDs return the same `not_found` result as absent IDs. Search returns excerpts;
fetch returns exact Unicode slices with full and slice SHA-256 digests. No local
source paths or raw metadata are exposed. Search/fetch payloads are capped at
49,152 encoded bytes. Queries are capped at 4,096 UTF-8 bytes, limits at 20, and
fetch slices at 8,000 characters. Oversized results fail explicitly.

Host-side snapshots freeze ordered exact text and source identity into immutable
values. Supply the search-selected digest/revision expectations; changed sources
are refused. Persist the bundle as unprivileged workflow input and reuse it on
resume. Native coding execution receives that frozen bundle as assignment data;
it does not acquire API custom tools or ambient Castle MCP access.

Always treat memory as untrusted source material. Never install retrieved text
as system instructions, infer authorization from it, silently broaden scope, or
re-query during resume and replace the frozen evidence. Optional-memory policy
may continue with an explicit unavailable label; required-memory policy blocks.
No write, publication, delete, settings or SUE tools are exposed.

## Preservation and maintenance

New project, conversation and diary revisions publish checksummed drawer/closet
completion manifests. Partial revisions remain retryable and hidden from the
provider. Diary corrections/appends retain historical exact text and indexes.
Sweeps skip identical records without re-embedding; unseen late messages are
ingested, and corrected messages retain the original version. Sweep imports
need an explicit approved wing for provider visibility. Unknown legacy wings
remain available through standalone APIs until an operator maps them explicitly.

Pruning now deletes only explicitly derived `general` revisions. Original
project/exchange/diary/sweep text and unclassified legacy records are retained.
All supported ingestion, maintenance and MCP record mutations share a palace
lock; direct third-party backend writes must provide their own coordination.
Stale-lock cleanup clears payloads without unlinking lock inodes.

`castle reindex --palace PATH` re-embeds stored records with their IDs, exact text
and raw metadata preserved. Graph, registry, SUE reviews and older backups stay
in place. Two recoverable directory renames promote a verified staged index;
this is not an atomic directory swap. Use `castle reindex --palace PATH --recover`
after interruption. Discard old collection handles after maintenance.

## SOAR and SUE

Legacy `fast`, `standard`, `boosted` and `max` interfaces remain available.
`max` applies boosts before the final judge permutation. SOAR uses real drawer
IDs, preventing multiple chunks from sharing boost tags. Signed relevance
scores use a documented nonnegative rank base when a boost is active; original
scores remain auditable. Neutral/unavailable SOAR preserves the incoming order.

No SOAR replacement is needed for either provider profile. If a consumer later needs the four
built-in symbolic boosts, an explicitly selected pure Python policy can replace
their predicates and compound/clamp rules: recent ×1.25, same project ×1.15,
entity match ×1.30, matching memory type ×1.25. Qualify it against a real SOAR
installation on captured tag/order fixtures before switching legacy callers.
Custom `.soar` productions require separate migration; a four-rule implementation
cannot claim general equivalence. Keep SOAR available for those users meanwhile.

SUE remains an independent optional review workflow. The provider neither runs
it nor treats its output as certified memory. A future SUE integration should
consume an explicit frozen bundle and persist derived review evidence separately.
