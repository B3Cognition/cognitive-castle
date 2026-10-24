# FTS-first optional memory provider verification

Follow-up to [Castle hardening and provider qualification](2026-10-23-prosaic-memory-provider.md),
implemented on `codex/optional-memory-provider` from `e9bf3ab`. The original
checkouts, previous benchmark evidence, stored vectors and on-disk formats are
unchanged. No consuming application is enabled by this change.

## Selected behavior

`MemoryService`, `castle-provider` and `CastleMemoryProvider` now default to
`memory-fts-v1`. It requires usable FTS and performs scoped recall, sparse RRF,
recency, exact-passage grouping, source revalidation and bounded responses.
Dense and KG recall are disabled, and neither embedding nor cross-encoder code
is imported or loaded. Missing dense identity is not degraded FTS health.
Unusable FTS fails health/search rather than selecting another retrieval profile.

Hosts opt into the existing hybrid pipeline with
`CastleMemoryProvider(..., profile="memory-v1")`, or worker
`--profile memory-v1`. The adapter binds this setting in trusted worker argv and
checks the handshake. Tool schemas cannot select profiles or broaden grants.
Hybrid serving retains explicit offline model prewarming and its existing
recall/reranking behavior. Standalone `fast`, `standard`, `boosted` and `max`
defaults and optional stages are unchanged.

FTS recency reads a valid legacy epoch `ts`, then falls back to `filed_at`.
Legacy naive captures assume UTC solely for ordering; source values remain exact.
Unknown captures receive no boost. This fallback is specific to the new profile;
the existing hybrid and standalone timestamp behavior is preserved.

The FTS profile considers up to 100 recall candidates before grouping/hydration,
independent of neural reranker budgets. Its fingerprint includes the profile and
active sparse ranking/recency settings, and excludes neural model choices.
Scores from different profiles are not comparable.

Castle owns retrieval and provenance; the adapter owns process transport and
Runtime bindings. Runtime owns execution, grants, deadlines and safe errors.
Harness and the host own durable snapshots and resume policy. Core, Runtime and
Harness production code receive no changes in this follow-up. SUE and SOAR remain
separate and are forbidden in both provider serving paths.

## Verification

Python 3.11.15, macOS arm64; only invented temporary stores and explicitly
provisioned local model snapshots were used. No real user palace or external
inference endpoint was accessed.

| Gate | Observed result |
| --- | --- |
| Castle full normal suite with coverage | 2,186 passed, 11 skipped, 3 deselected; coverage 86.63% (85% required) |
| Runtime full suite | 1,169 passed, 2 skipped; 381.22 seconds |
| Adapter source suite | 69 passed |
| Adapter installed-wheel suite outside checkout | 69 passed |
| Benchmark metrics and frozen fixture checks | 5 passed |
| Final serial three-way benchmark | All functional gates passed; source hashes unchanged; no network or forbidden engine/model initialization |
| Castle and adapter builds | Wheel and sdist builds passed |
| Artifact/source parity | All 94 Castle and four adapter Python files in the new wheels match current source bytes |
| Runtime-only adapter wheel smoke | Installed ownership, no Castle/model/Harness imports, worker and tool execution passed |
| Separate installed Castle worker + adapter | Both profiles passed exact Unicode/CRLF/digest, scoped search/fetch/snapshot, denied foreign ID, unchanged palace bytes/mtimes/modes and worker reaping |
| Independent read-only review | Recency fallback and benchmark output preservation findings fixed and rechecked; no remaining findings |

The default worker was additionally exercised in a fresh process with embedding,
reranker, Torch and sentence-transformers initialization forbidden. Availability
probes by LanceDB are allowed; actual imports/initialization are not. Tests cover
exact-copy grouping with alternate provenance, distinct conflicting passages,
incomplete revisions, scope injection, explicit hybrid selection and handshake
mismatch rejection. Existing model prewarm and native-stdout isolation tests now
select hybrid explicitly, preserving their original coverage.

The first broad run found the native-stdout test's old implicit-hybrid assumption
(2,185 passed, one failed). The fixture now explicitly selects hybrid; its focused
rerun and the final full suite pass. Initial RED tests and all run logs are
retained under `/private/tmp/castle-fts-*` and
`/private/tmp/castle-adapter-fts-*`. Castle's marked benchmark/slow/stress lanes
are excluded by its normal suite. Existing SML-dependent tests remain skipped;
no arbitrary SOAR-production equivalence is claimed. Existing dependency
deprecation warnings remain in the logs.

## Frozen benchmark result

[Three-way evidence](memory-pilot-fts-v1.json) uses the same 36 invented records,
40 questions (10 development, 30 held out), wing scope, five-hit limit, existing
configuration and local model snapshots as the previous pilot. The fixture SHA-256
remains `96e8092bc96f7f1a46ff67072f59f19f59cbca3d1912aeadf83f91eb3726f111`.
There was no label/configuration tuning after this run. Tests, builds and other
qualification model loads finished before the serial benchmark began.

| Measure | Raw Lance FTS | FTS provider (`memory-fts-v1`) | Explicit hybrid (`memory-v1`) |
| --- | ---: | ---: | ---: |
| Held-out Recall@5 | 0.986667 | 0.986667 | 0.986667 |
| Held-out MRR@5 | 1.000000 | 0.940000 | 0.980000 |
| Held-out recall-all | 0.960000 | 0.960000 | 0.960000 |
| Held-out NDCG@5 | 0.986855 | 0.938533 | 0.973119 |
| Warm p50 / p95 | 4.799 / 6.020 ms | 93.086 / 113.422 ms | 407.508 / 450.717 ms |
| Cold-process p50 / p95 | 1.035 / 1.061 s | 1.164 / 1.565 s | 8.434 / 8.439 s |
| Peak RSS | 139.0 MiB | 142.7 MiB | 3,113.3 MiB |

The FTS provider uses about 22 times less peak process memory and has about
4.4 times lower warm median latency than hybrid in this fixture. Its warm median
is substantially slower than raw FTS because it includes grouping, hydration,
repeated exact-record/scope/completion validation and bounded service payloads.
It is not a claim that the provider performs a single 5 ms FTS lookup.

Equal Recall@5 does not mean ranking parity: the recency-ranked FTS profile has
lower MRR/NDCG than both raw FTS and hybrid here. The new capture-time recency
fallback can move more recent passages ahead of lexical rank. Existing hybrid
ranking remains available by explicit selection. No ranking parameters were
changed in response to these results. This pilot does not establish semantic
recall on real project history or generated-answer quality.

Each method has three fresh-process cold samples and 80 warm observations (two
passes over 40 questions). OS caches may be warm and host workloads are not
controlled. Cold timing is first search in a fresh process, not an end-to-end
adapter startup SLA. All five unanswerable questions still return candidates in
every method; no answer-abstention policy is implemented. Nine empty-store probes
and all source, digest, provenance, scope and forbidden-import/network checks
passed. Source hashes remained stable during the 92.8-second run.

The previous two-way JSON and artifacts are unchanged. The benchmark's default
output now names `memory-pilot-fts-v1.json`, preventing accidental overwrite of
that historical evidence. Reproduce using the command in
[the benchmark guide](../../benchmarks/MEMORY_PROVIDER_PILOT.md).

Evidence SHA-256:

```text
46174414853775726bfc81bcf84b353e7368efa0783b93cd3f8b401399061b6c  memory-pilot-fts-v1.json
```

## Limits

FTS can miss paraphrases without lexical overlap; hybrid remains an explicit
option for that tradeoff. The new default does not use graph-only evidence.
Neither profile provides an answer-abstention or truth-assessment policy.
Capture coverage remains limited to ingested sources. Source preservation,
snapshot persistence requirements and POSIX adapter constraints are unchanged.

Castle still declares its existing neural installation dependencies. This is a
serving profile change, not slim packaging or a change to ingestion. Model caches
are unnecessary for FTS serving but remain necessary for hybrid and embedding
ingestion. No SOAR replacement is required by either provider profile.

These are unpublished candidate wheels with unchanged candidate versions; the
adapter still requires the qualified Runtime `custom_tool_errors_v1` capability.
Use distinct published release versions before deployment. Nothing is pushed,
merged or published by this work.

## Candidate artifact SHA-256

New artifacts live under `dist/fts-v1/` and `adapters/prosaic/dist/fts-v1/`;
previous artifacts and their recorded checksums are retained.

```text
d13e113785eddf96b8f78a9ea711169f42312bff1409eb4440c6ca456b9f3c16  cognitive_castle-3.4.1-py3-none-any.whl
e27f320503d641ff7c4dda8ada19e1e4e7ee1c52642961dfc435eafd4565cce7  cognitive_castle-3.4.1.tar.gz
3ac6216cc4ba4f3f30db9a063df4a65b3517cf0437db2127bc78ea5938a74208  b3_prosaic_memory_castle-0.1.0-py3-none-any.whl
8a447b3401ed23cc3d5883b32b4bc44296bdef274c65d6ff050079f979e6ea22  b3_prosaic_memory_castle-0.1.0.tar.gz
```
