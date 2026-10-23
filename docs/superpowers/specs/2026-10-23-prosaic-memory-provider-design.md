# Castle as an optional Prosaic memory provider

Date: 2026-10-23. Status: proposed design and implementation sequence requested by the user. The user selected the optional-provider direction; implementation and release have not been requested. Baseline: Castle `940daa216c2a31750e9823bdfb91880465ce4a59` (3.4.1), Core 0.4.1, Runtime 0.9.3, Harness 0.8.2. Preserve unrelated work in all repositories.

## Intent

Provide retrievable project history and exact source passages across coding/agent sessions. Repair data-preservation and isolation defects before making Castle a shared application dependency. Keep memory optional and replaceable. Preserve the useful SUE requirements-review semantics without embedding an unaccounted workflow inside a memory read.

User decisions: Castle will be an optional memory provider; evaluate critical repairs, explicit Castle/Runtime/Harness ownership, SUE and whether SOAR is justified. The concrete interfaces, package location, limits and staging below are recommendations made in this design.

## Ownership

| Owner | Responsibilities | Excluded responsibilities |
|---|---|---|
| Castle | Source capture/import, revision fidelity, local indexes and encoders, source provenance, scoped search/fetch, immutable source bundles, index maintenance | Application identity/consent, workflow authority, hidden generative calls in provider reads |
| Runtime | Model execution, configured endpoints, execution budgets, usage evidence and granted tool execution | Memory storage/index implementation, deciding what becomes accepted shared knowledge |
| Harness | Durable workflow state, admission, pending-call recovery, explicit retries/choices and workflow receipts | Castle storage, product-specific SUE algorithms, implicit memory writes on every event |
| Host/application adapter | Authentication, authorization, approved palace/project binding, input snapshots, publication policy, outbox/reconciliation | Reimplementing Runtime/Harness internals or claiming atomic commit across their stores |
| Prosaic Core | Canonical prose, packages and read-only catalogue descriptions | Executing Castle manifests/MCP or adding Castle to base dependencies |

Local embedding/cross-encoder inference is Castle retrieval infrastructure. Generative judging, extraction and SUE calls use Runtime when invoked inside the Prosaic integration. Existing standalone Castle commands remain a separately configured compatibility surface.

## SOAR decision

SOAR is unnecessary for the proposed memory profile. The current Castle rule file emits four tags: recent source, same project, KG entity match and query-intent/type match. Python assigns fixed multipliers (1.25, 1.15, 1.30, 1.25). The bridge enables EpMem/SMem but does not use those subsystems for Castle recall or demonstrate learned ranking. A full cognitive architecture is not required to evaluate these predicates.

Evidence: `cognitive_castle/rules/castle-boost.soar`; `soar_bridge.py` constants, `_get_agent`, `_push_working_memory`, `_apply_soar_to_reranked`. Soar itself supports substantially broader cognitive functionality; this recommendation concerns Castle's current use, not the architecture's general usefulness. Primary reference: https://soar.eecs.umich.edu/soar_manual/03_SyntaxOfSoarPrograms/.

The new `memory-v1` profile uses dense + FTS + optional scoped KG, existing fusion/recency, and cross-encoder relevance. It never imports or calls SOAR, the quality analyzer, an LLM judge or SUE. It reports degradation explicitly when a configured recall signal is unavailable. Failure of all signals is an unavailable error, not an authoritative empty search.

Preserve the existing `fast/standard/boosted/max` CLI/MCP contracts during this additive rollout. Repair composition and drawer identity for existing users. Deprecate SOAR as an experimental legacy ranking engine in current documentation; preserve custom `.soar` behavior rather than silently translating arbitrary rules. Physical removal is a later breaking release decision. Do not add a replacement Python boost framework until held-out production-pipeline evaluation demonstrates useful gains; the four predicates could be implemented directly if that evidence appears.

Historical removal/restore plans under `docs/superpowers/` are evidence, not instructions for this implementation. They describe older code and must remain unchanged.

## SUE decision

SUE is independent of SOAR. Retain it as an optional requirements-review application, outside ordinary search and capture. Its useful core is the deterministic operator policy, nine lens orderings, exact quote/premise checks, claim-version resets, revision budget, source mappings and conservative stop states. It does not certify truth or implementation correctness.

Current Castle SUE starts its own process, chooses transports/models, runs a bounded dialogue and writes `.sue/runs` lifecycle state. This is acceptable as the existing standalone application; the Prosaic memory adapter must not expose `castle_sue_review`, spawn that worker or make a model call indirectly.

For a later explicit Prosaic SUE integration:

1. Castle produces an immutable, authorized source bundle with exact text/revision/hash mappings.
2. A separate consumer package owns pure SUE transition/validation policy and neutral reviewer prose. Preserve the pinned engine/license; do not edit vendored source in place or monkey-patch module globals in a shared process.
3. A versioned `RuntimeAdapter(max_attempts=1)` builds the current operator's prompt/schema guidance, invokes Runtime once with no tools, and returns an evidence-preserving candidate envelope. Failed transport results remain failures.
4. Harness owns an explicitly bounded sequence of at most 14 logical turn nodes. Each accepted output contains the full canonical SUE state; a trusted validator recomputes it from frozen inputs and candidate output. Gates route only on that validated host-derived state. No model-selected operator or terminal, mutable closure checkpoint, or second SUE worker state machine.
5. Harness `max_attempts=2` owns corrective retries only after completed transport output fails semantic validation. Interrupted/failed model requests block for normal recovery; no automatic transport retry. There is no nested retry loop.
6. The host renders/exports derived reports after accepted state. Optional publication to Castle requires explicit application policy and uses the host outbox; original drawers are never rewritten.

One lens runs per review. Defaults: 7 logical turns, maximum 14; at most 2 completed-output attempts per turn; 120 seconds per invocation; 1,800-second total run deadline; 50,000 reported tokens across the run; no tools. These are proposed pilot bounds, not claims about model context capacity. Enforce the actual input-byte/model-context policy before dispatch. The 2 MiB legacy source bound is a byte bound, not a universal token-fit guarantee. A bounded stop is not a successful substantive verdict.

Current API constraints inform this design: RuntimeAdapter permits 1–8 executions per invocation, so wrapping a whole 14/28-call SUE review in one adapter is invalid. Harness validators return issues, not transformed state; therefore the trusted adapter projects state, and the validator independently verifies it. A nonzero Runtime result blocks rather than entering Harness's semantic-output retry path. Keep exact candidate stdout and its digest in receipts/evidence because adapter aggregate metadata alone does not preserve raw text.

SUE delivery is a separate optional milestone and is not required to ship the read-only memory provider.

## Compatibility and data invariants

- Castle remains Python >=3.10; the Prosaic adapter requires Python >=3.11.
- Use `apply_patch`; preserve historic evidence and unrelated user changes.
- Keep existing public Python signatures callable and existing on-disk records readable. Prosaic serialized camelCase contracts remain unchanged.
- New metadata is additive and versioned. Missing legacy representation/provenance is `unknown`; never invent authorship, revision completeness or accepted-decision authority.
- Original and derived representations are distinct. A selective extraction never supersedes verbatim source text.
- Pruning retains every distinct original source revision (`project`, `exchange`, `diary`, `sweep`) and unknown legacy revision. In this rollout it may remove only explicitly classified derived revisions and their index pointers. Search deduplication does not delete history. Physical compaction/purge of originals is a separate retention feature, outside this plan; this intentionally tightens the old prune command's unsafe semantics.
- Import identity includes canonical source, wing and representation (`project`, `exchange`, `general`, `diary`, `sweep`). Existing IDs remain stable; new revision IDs may include representation policy version.
- Partial writes do not publish a complete revision. Drawer/closet completion must be consistent; optional graph enrichment can be explicitly degraded without invalidating stored original text.
- Mutating maintenance and all ingestion entry points use the same per-palace lock. Do not unlink lock inodes while another process may hold them.
- Reindex regenerates vectors/indexes from stored records, preserving IDs, text, metadata, history and derived artifacts. It must not reconstruct history only from current source files.
- No automatic deletion, migration, re-embedding or model download when opening the provider.
- Snapshot/read operations cannot approve knowledge, mutate source text, start review jobs or publish results.

## Explicit palace context

Add `PalacePaths` and `CastleContext` in `cognitive_castle/context.py`. The existing future source-adapter `sources.context.PalaceContext` remains a separate facade. The service context owns explicit config, backend, graph, registries, lock paths and lifecycle. It must not consult changing ambient globals after construction.

`PalacePaths.resolve(palace_path, *, config_dir=None) -> PalacePaths` resolves the canonical root and discovers a versioned path manifest. New palaces keep graph, registries and provider artifacts under their own root. Existing default `~/.castle/palace` remains readable with its recognized legacy locations. Ambiguous custom-palace layouts fail with a read-only migration diagnostic. An explicit migration copies the chosen state into private root-owned locations under a lock and writes a manifest; never silently merge sibling-palace data or delete legacy files.

`CastleContext.open(paths, *, config, create=False, read_only=True) -> CastleContext` owns handles and offers `close()`. Add optional explicit `context=`/`config=` parameters at library seams while preserving old call forms. No MCP import is necessary for library use. A default legacy adapter may resolve existing configuration at CLI construction time; the provider requires explicit construction.

Read-only prohibits persistent housekeeping too: no table creation, identity stamping, schema migration, FTS rebuild, directory chmod or SQLite journal-mode change. An unverified legacy embedder disables dense recall; a readable FTS index may serve an explicitly degraded result. An old graph schema may disable KG. If no verified signal is usable, return `incompatible_store` until explicit preparation. Existing source rows remain readable through exact fetch when the table schema supports it. `castle provider prepare --palace PATH --namespace ID` performs authorized writable setup/migration under the palace lock before serving; it never downloads weights implicitly.

## Memory provider contract v1

Keep a narrow Castle-owned public service API in `cognitive_castle/memory.py`. The Prosaic adapter is a separately installable package at `adapters/prosaic/`, proposed distribution `b3-prosaic-memory-castle`, import `prosaic_memory_castle`. It depends on Runtime, not Castle or Harness. The host separately provisions the Castle worker in its own environment. No reverse dependency from base Castle/Core/Runtime/Harness to the adapter. V1 retains Castle's existing dependency installation; a slim Castle distribution is deferred rather than claiming an extra can subtract mandatory spaCy dependencies.

One palace belongs to exactly one trust-domain namespace. Explicit preparation writes `<palace>/.provider/identity.json` with that opaque binding under a lock. A provider checks it on open and refuses absent/mismatched identity; opening cannot create or change it. The trusted host grants filesystem access and selects the approved root; the label itself is not authentication. Multiple tenants do not share one palace in v1. Host construction additionally binds a nonempty allowed-wing set. Neither tool arguments nor model-supplied invocation IDs select paths, namespace, actor, credentials or wider wing access. Fetch and snapshots enforce the same scope as search.

Legacy rows without a usable wing remain readable through existing standalone APIs but are not provider-visible until an explicit operator mapping assigns their approved project scope. Do not derive authorization from a basename, transcript claim or model-supplied label.

Public operations (Python dataclasses are defined in `memory_types.py`; wire version is 1):

```python
MemoryService(context, *, namespace: str, allowed_wings: frozenset[str])
search(query: str, *, limit: int = 5) -> SearchResult
fetch(record_id: str, *, start_char: int = 0, max_chars: int = 8000) -> MemorySlice
snapshot(record_ids: tuple[str, ...], *, expected: dict[str, SourceExpectation] | None = None,
         maximum_bytes: int = 262144) -> SourceBundle
health() -> ProviderHealth
```

`search`: query <=4,096 UTF-8 bytes, limit 1–20, at most 512-character excerpts labelled as excerpts. Every hit has record ID, exact stored-text SHA-256, actual source revision or null, representation, wing, capture time or null, finite relevance score and 1-based final rank. Scores are not probabilities. Deduplicate exact repeated passages across revisions by default, retaining newest complete occurrence plus alternate provenance; historical versions remain fetchable. Do not collapse different text or conflicting claims.

`fetch`: exact Unicode-code-point slice, max 8,000 characters (<=32,000 UTF-8 bytes), full-text digest plus slice digest, `start_char`, `next_start_char` or null, `complete` flag and bounded provenance. It must never silently truncate or summarize. A source locator is an opaque ID/approved URI rather than an arbitrary local absolute path.

Search/fetch payload <=49,152 UTF-8 bytes before Runtime wrapping. Oversized queries/metadata/results fail with a bounded typed error rather than leaking exception text. `SourceExpectation(text_sha256, revision)` lets search-selected snapshots reject a changed record rather than freeze different text silently. Snapshot preserves exact selected revisions and rejects a bundle over its encoded manifest+text JSON byte limit. It returns in-memory data without writing the read-only palace; the host persists it. It does not re-query by similarity on resume.

Errors: `invalid_request`, `not_found` (also used for out-of-scope IDs), `unavailable`, `deadline_exceeded`, `cancelled`, `result_limit`, `incompatible_store`. A successful empty search is distinguishable from provider failure. Availability/degradation fields cannot reveal other namespaces.

## Process and Runtime adapter

Use one private, persistent local worker per bound trust domain; no HTTP server or generic shared service is required for v1. Add `castle-provider` / `cognitive_castle.provider_worker`. Newline JSON request/response envelopes carry version, request ID, operation and bounded payload; stdout is protocol-only. Operations are `hello`, `health`, `search`, `fetch`, `snapshot`, `close`. The worker has no generic execute operation, tool discovery, SUE, delete or settings endpoints.

The host supplies `WorkerCommand(argv: tuple[str, ...])` naming an absolute executable in a separately provisioned Castle environment (for example `/opt/castle/bin/python -m cognitive_castle.provider_worker`); no implicit PATH search, shared-interpreter import or installation from a tool call. The host starts it with explicit path/config grants, outside model arguments. Keep warm encoders within that process. Serialize requests per worker. Startup timeout defaults to 120 seconds for host-side `health()`/prewarm; read-operation timeout defaults to 30 seconds and is narrowed to `ToolExecutionContext.remaining_timeout(30)`. If a tool starts a cold worker, its parent deadline also bounds startup; it cannot claim another 120 seconds. Cancellation/deadline expiry terminates and drains the worker, invalidates it and returns a typed error; a later read may create a fresh worker. Do not automatically replay writes. Bound stdout frames at 1 MiB and exposed search/fetch at their lower payload cap; terminate oversized or mismatched responses. No downloads on serving traffic; operator provisioning/prewarm is explicit.

`CastleMemoryProvider` wraps transport and presents the same read API; `memory_tools(provider, *, authorize)` returns `memory_search` and `memory_fetch` Runtime `CustomTool`s. Closed schemas; explicit semantic version; `with_context=True`; required trusted authorizer; 8,192-byte argument bound; 65,536-byte Runtime result bound. Authorization failures must dispatch zero worker requests.

One small generic Runtime prerequisite is needed: extend/export `ToolExecutionError` with closed codes `tool_not_found`, `tool_unavailable`, `tool_invalid_request`, `tool_result_limit`, `tool_incompatible`, `tool_timeout`, and advertise `custom_tool_errors_v1`. Current codes are CLI-only; do not reuse them or accidentally return `status=ok/result.error`. The adapter requires the capability before registering tools. Its Python/worker API retains domain errors; model-visible errors map to these safe generic codes. Actual parent cancellation/deadline propagates Runtime control exceptions. Existing CLI errors and journaled effect-uncertainty behavior stay unchanged. This is an independent upstream SDK patch, not Castle-specific routing logic.

Host-side `snapshot` is not a model tool. It supports deterministic pre-retrieval and native coding execution by placing exact source bundles in unprivileged assignment inputs. Existing NativeRuntime rejects custom API tools; do not relax ambient MCP restrictions to make Castle appear automatically.

## Harness and publication

The v1 adapter has no required Harness dependency. An optional example/test extra demonstrates `WorkflowBindings` and `ConversationBindings` with the read tools. Trusted host mapping resolves identity; conversation scope does not universally contain run ID. Recalled content goes in tool/user input, never privileged artifact system resources.

Host-prepared inputs and persisted receipts freeze the selected records. Do not retrieve again during resume and silently change evidence. No generic new Harness node is needed for the memory pilot.

Memory writes are a subsequent milestone: host outbox with immutable approved content, source references, stable operation key, content signature and explicit pending/unknown/completed state; Castle append deduplicates that operation and rejects signature conflicts. Publication derives only from committed/approved host state, not observer callbacks or a model claim. No exactly-once cross-store promise. No publication API is exposed in v1.

## Delivery and release gates

Separate implementation plans:

1. `../plans/2026-10-23-castle-memory-hardening.md`: preservation, maintenance, context, retrieval/provenance and reproducible packaging.
2. `../plans/2026-10-23-prosaic-memory-provider.md`: Castle service, bounded worker, optional Runtime adapter and Harness/native consumption tests.
3. `../plans/2026-10-23-prosaic-sue-review.md`: independent optional SUE controller/Runtime/Harness integration after the source-bundle boundary is stable.

Ship order: immediate preservation fixes; context and maintenance; retrieval/packaging; read-only provider; production-pipeline evaluation; optional SUE review; later publication. Core/Runtime/Harness require no Castle-specific engine changes. Any generic SDK defect found gets an upstream regression and separate fix.

Required gates: synthetic regression RED/GREEN; whole Castle suite with models provisioned; dependency-free unit lane; clean wheel install/smoke; real worker scope/deadline/kill tests; API Runtime and Harness receipt/recovery tests; native snapshot test; held-out actual-pipeline evaluation. All optional-provider reads must pass with SOAR, spaCy quality analysis, SUE and external LLM transports forbidden. Existing legacy users retain readable stores and explicit existing advanced modes.

Pilot evaluation: at least 40 versioned synthetic/project-history questions, including exact decisions, rejected approaches, multi-source answers, conflicts, wrong-project matches and unanswerable questions; freeze 10 dev/30 held-out before tuning. Compare text/FTS baseline and actual `memory-v1` with identical corpus/metrics. Record evidence completeness, source fidelity, conflict/abstention behavior, context bytes and cold/warm p50/p95 latency on named hardware. Functional gates have zero cross-scope disclosures, byte mismatches or hidden model calls. No recall/latency target is claimed met before measurement; enable rollout only with a reviewed pilot report, while keeping provider feature disabled by default.

## Prior evidence and limits

The preceding audit reproduced six storage defects against temporary real LanceDB and several retrieval/configuration defects without live models. 697 selected tests passed; the full model-dependent suite was not established because weights were unavailable. Ruff and wheel build passed. Those are baseline observations, not evidence that the planned fixes exist. See the accompanying plan regressions; do not relabel historical benchmark results as production-pipeline qualification.
