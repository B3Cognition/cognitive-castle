# Castle hardening and optional memory provider verification

Implemented on isolated branches; nothing is published or enabled in a consuming
application. Original checkouts and unrelated changes were retained.

- Castle: `/private/tmp/castle-memory-provider-work`, branch
  `codex/optional-memory-provider`, baseline `940daa216c2a31750e9823bdfb91880465ce4a59`.
- Runtime: `/private/tmp/prosaic-runtime-memory-work`, branch
  `codex/memory-tool-errors`, generic patch commit `e63983a` over
  `5c2c2be4c0e496997422db1fd6c8be882fbc0514`.
- Prosaic Core and Harness production code are unchanged. Their public installed
  APIs are exercised through the adapter's consumer tests.

## Delivered boundaries

Castle owns exact records, revision preservation, indexes, scoped reads and the
private `castle-provider` worker. The optional `b3-prosaic-memory-castle` adapter
owns transport and two Runtime tool bindings. Runtime owns execution, grants,
deadlines and safe errors; Harness owns durable state and resume. The host owns
identity, allowed wings, authorization, memory policy and snapshot persistence.

The provider has search/fetch and host-only snapshots. It exposes no write,
publication, delete, settings or SUE endpoint. Its relevance profile never imports
SOAR, SUE, quality analysis or a generative judge. Legacy standalone modes remain
available. No live user palace, transcript import, external inference or SOAR
installation was used for this qualification.

## Preservation and correctness repairs

| Area | Result |
| --- | --- |
| Representation identity | Same source in another wing or representation is not incorrectly skipped or pruned; original and unknown legacy revisions are retained. |
| Completion | Drawer and closet writes are verified before row hints and a checksummed membership manifest; partial writes stay retryable and hidden. Verification and hint updates use bounded backend requests. |
| Same-content retries | Touched sources and forced diary retries reuse completed evidence. Failed signature bookkeeping cannot unpublish old text. |
| Diaries and sweeps | Exact CRLF/Unicode/whitespace history survives correction and growth. Identical sweeps do no embedding/write; late messages and corrected versions are retained. |
| Mutation and reindex | Shared palace locks cover ingestion, maintenance and MCP record writes. Lock cleanup retains inodes. Reindex stages stored records, preserves raw metadata/history, retains unique backups and supports recovery. |
| Context | Explicit paths/config isolate sibling palaces. CLI enrichment, MCP and search agree on graph paths. Long-lived read-only handles see committed ingests without writes. |
| Auxiliary migration | Explicit selected copies capture WAL commits and verify counts/hashes. Originals and unselected local bindings survive; ambiguity and overwrite conflicts fail before publication. |
| Graph evidence | Repeated facts retain all source evidence; validity intervals remain distinct; entity-intersection ranking is corrected. |
| Ranking | Legacy boosts precede the final judge permutation. SOAR tags use actual drawer IDs. Signed-score adjustments keep raw relevance and a versioned nonnegative ranking base. |
| Provider recall | Scope is applied before caps and after fetch. Exact passages group before reranker capacity, choose the newest capture and retain bounded alternate sources. Conflicting text remains distinct. |
| Preflight | Missing recall signals and malformed registry/graph schemas cannot masquerade as authoritative empty memory. Preparation may explicitly repair FTS; serving never does. |
| Packaging | Developer Ruff versions agree; the optional adapter installs without Castle, torch, spaCy or Harness. |

New captures use aware UTC timestamps. For deterministic ordering only, legacy
naive captures are interpreted as UTC; their stored/public strings are unchanged.
Alternate-source completeness describes the known scoped recall pool, not an
exhaustive scan of every source in the palace.

## Test and installed-package evidence

Python 3.11.15 on macOS arm64, with explicitly provisioned local CPU models:

| Gate | Observed result |
| --- | --- |
| Unmodified Castle baseline | 2,008 passed, 11 skipped, 3 deselected; coverage 86.03% |
| Final Castle suite | 2,180 passed, 11 skipped, 3 deselected; coverage 86.64%, above the 85% gate |
| Runtime full suite | 1,169 passed, 2 skipped |
| Adapter source qualification | 66 passed |
| Adapter final installed qualification | 66 passed, 9.14 seconds |
| Fresh independent review | All reported preservation, migration, deduplication and health issues fixed; independent focused rechecks passed |
| Lint/build | Ruff checks and formatting; Castle, Runtime and adapter wheel/sdist builds |
| Runtime installed smoke | Core 0.4.1, Runtime candidate 0.9.3, recorder 0.3.0; public installed APIs |
| Adapter installed smoke | Runtime-only environment; no Castle/models/Harness dependency or imports |
| Real installed worker + adapter | Exact Unicode/CRLF and digests, scoped search/fetch/snapshot, denied foreign ID, unchanged palace bytes/mtimes/modes, no optional-engine imports/network, child reaped |

Castle's normal suite excludes its marked benchmark/slow/stress lanes; the new
real-model benchmark runs separately. Optional SOAR tests remain skipped because
SML is not installed. Mocked legacy-mode tests passed, but no claim of arbitrary
custom SOAR production equivalence is made. Existing deprecation warnings are
retained in logs. Initial intermediate failures and concurrent benchmark runs
are retained as evidence rather than substituted for final qualification.

Reproduce the separate-environment smoke with:

```sh
HF_HOME=/path/to/provisioned/models python scripts/verify_memory_install.py \
  --worker-python /opt/castle/bin/python --adapter-python /opt/prosaic/bin/python
```

The script creates only synthetic temporary stores and an isolated test home.
It checks the production worker and adapter with real encoders/reranker and
blocks network connections and optional engine imports.

## Adoption limits

The adapter requires POSIX process groups. Runtime's unchanged `0.9.3` candidate
version alone is insufficient: registration checks `custom_tool_errors_v1`.
Select a distinct published Runtime version before deployment. These candidates
have not been released, pushed or merged.

Preparation binds one palace to one namespace and requires an approved wing set.
Legacy ambiguous auxiliary layouts require explicit migration. Strict read-only
SQLite cannot open closed WAL stores that need sidecar creation: the operator
must checkpoint/select DELETE journaling while writers are quiescent. This is an
explicit maintenance choice, never a serving-time repair.

Capture is limited to sources actually ingested. The provider does not silently
capture every Prosaic execution. Writes/publication outboxes, slim Castle worker
packaging and optional SUE workflow integration remain separate milestones.
Snapshots must be persisted as unprivileged owned inputs and reused on resume.

SOAR replacement is unnecessary for the provider. If legacy built-in boosts are
needed without SOAR, qualify an explicitly selected Python predicate policy
against real SOAR tag/order fixtures. Four built-in rules do not replace custom
productions. See [the operational boundary document](../memory-provider.md).

Detailed RED/GREEN and final logs are retained under
`.superpowers/sdd/2026-10-23-castle-memory-hardening/`; Runtime and adapter reports
live in their respective `docs/` directories. Benchmark evidence and candidate
checksums follow below.

## Actual-model pilot result

[Final serial evidence](memory-pilot-v1.json) records stable source hashes, local
model snapshot/file hashes and every ranking. The frozen fixture has 36 invented
records and 40 questions, split into 10 development and 30 held-out questions
before the first run. No labels, retrieval settings or thresholds were tuned to
the results. No KG is provisioned in this comparison.

| Held-out metric | FTS baseline | memory-v1 |
| --- | ---: | ---: |
| Recall@5 | 98.67% | 98.67% |
| Mean reciprocal rank | 1.000 | 0.980 |
| Recall of all relevant sources | 96% | 96% |
| NDCG@5 | 0.9869 | 0.9731 |
| Warm p50 / p95, all 80 queries | 5.96 / 6.86 ms | 485 / 836 ms |
| Cold p50 / p95, three processes | 1.35 / 1.56 s | 9.50 / 12.36 s |
| Process peak RSS | 138.9 MiB | 3,110.5 MiB |

All integrity/scope/provenance checks and six actual empty-store checks passed.
Network/DNS/optional-engine attempts and initialized forbidden modules were zero.
All five unanswerable questions returned candidates in both methods: retrieval
does not implement an answer-abstention decision. Timing excludes the subsequent
exact fetches used for integrity checks. Parent test workloads were paused for
this run; unrelated host load and warm OS caches remain uncontrolled.

**Adoption decision:** the provider is functionally qualified for an explicit
pilot, not promoted to an application default. This fixture shows no recall
gain from dense retrieval/reranking and substantial cost. Its warm p95 exceeds
Castle's 500 ms hook budget; prewarming addresses cold startup, not that tail.
Evaluate an explicitly versioned FTS-first profile before broad deployment if
application data behaves similarly. That additional profile is not silently
substituted here. A small synthetic lexical corpus does not establish general
retrieval quality or private project-history performance.

## Qualified candidate artifacts

Built and installed locally; not published. The worker environment installed all
78 declared dependencies from the provisioned cache. The consumer environment
contains Core/Runtime/adapter and excludes Castle, torch, spaCy and Harness.

```text
1dd1422b30bdca87511777472a8e09fab179cf1093347e2c0ebbb5595e1aff77  cognitive_castle-3.4.1-py3-none-any.whl
9b132ab9456b8f6a85944a629cd02f8eef19049efa2284a081c64ee0662cce21  cognitive_castle-3.4.1.tar.gz
a0970de47ce8e064168e1143d7cc8133d35c0be867fd790166271c4da2cdacb5  b3_prosaic_runtime-0.9.3-py3-none-any.whl
49183d9c1f0ec2d87ad40b5582603295c4134ca6b17e957ac5dc78554f9442c5  b3_prosaic_memory_castle-0.1.0-py3-none-any.whl
a807ed5822c2dd06978e70a0f40b73a2544b8e19a8e48bc256f8421505f6c83a  b3_prosaic_memory_castle-0.1.0.tar.gz
```
