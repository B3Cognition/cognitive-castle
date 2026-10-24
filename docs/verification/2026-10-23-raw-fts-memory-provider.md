# Raw FTS ordering and provider I/O verification

Follow-up to [the FTS-first profile qualification](2026-10-23-fts-memory-provider.md),
from commit `b205082` on `codex/optional-memory-provider`. This change preserves
backend FTS passage ordering by default and makes capture-recency boosting an
explicit host option. It also reduces repeated authoritative record I/O.
Previous fixture labels, benchmark reports, artifacts and source records remain
unchanged. No consuming application is enabled, and nothing is published.

## Ordering and component boundaries

The default `memory-fts-v1` uses strictly decreasing ordinal scores to preserve
backend FTS order, including equal BM25 scores. Scope/completion filtering and
exact-passage deduplication remain mandatory. A duplicate group retains its best
FTS position and selects the newest identical source as primary provenance;
distinct or conflicting text remains distinct. Scores express passage rank,
not raw BM25 values or probabilities. Existing Castle fusion weights and
smoothing do not reorder the FTS default.

Hosts opt in with `CastleMemoryProvider(..., recency_boost=True)`,
`MemoryService(..., recency_boost=True)`, or worker `--recency-boost`. Only the FTS
profile accepts this flag. Opt-in uses the existing configured recency timescale
and maximum boost, valid epoch timestamps and capture-time fallback. Hybrid
`memory-v1` and standalone Castle modes retain their existing ranking policies.
Dense retrieval stays explicit; neither FTS path loads neural models.

The worker reports a literal `recency_boost` boolean, and the adapter verifies
it against trusted host argv. Missing, nonboolean or mismatching metadata fails
closed. Matching new worker and adapter candidates must be deployed together:
mixed operation with an older worker is deliberately unsupported to prevent its
older recency-enabled default from being accepted silently. Model tool arguments
cannot select ranking flags, profiles, namespaces or scope. Fingerprints include
the selected flag and only active ranking settings.

Castle owns retrieval/provenance; the adapter owns worker transport and tool
bindings; Runtime owns execution/grants/deadlines; Harness and the host own
durable snapshots and resume. Core, Runtime and Harness production code are
unchanged. SUE and SOAR remain outside both provider paths.

## Overhead investigation

The original 93 ms warm median prompted an independent cProfile diagnostic on
the same frozen invented text, with zero vectors and neural/network imports
forbidden. This isolates serving I/O without measuring embedding ingestion.
Eighty queries use two passes over the existing 40-question fixture. These
instrumented diagnostic timings are separate from the qualification benchmark.

| Diagnostic measure, 80 provider queries | Before | After |
| --- | ---: | ---: |
| Median search with cProfile | 104.85 ms | 20.75 ms |
| Authoritative backend `get` calls | 1,600 | 80 |
| Collection wrapper/identity checks | 1,680 | 160 |
| Revision completion checks | 6,880 | 6,880 |
| Exact source descriptor constructions | 1,600 | 1,600 |

Before, final per-record reads consumed 7.21 of 8.45 cumulative seconds. Each
read reopened a collection wrapper, rechecked stored embedder identity and ran
a separate record query. This repeated for up to 20 candidate passages even
when the requested output limit was five.

Search now gathers primary IDs and at most eight alternates per candidate,
then performs one authoritative batch read after recall/hydration. It still
checks every returned row's wing, internal-registry exclusion, revision completion
and manifest membership, then constructs exact-text digests and source provenance.
Recall text/provenance blobs are never trusted as authoritative. Malformed result
shapes, duplicate IDs and unexpected IDs cause `unavailable`; absent, foreign and
incomplete records remain hidden. Invalid/missing/changed alternates retain the
existing incomplete-provenance behavior. Fetch and snapshots still validate exact
sources, and output limits are unchanged.

The batch is local to one request. No text, scope decision, completion result or
collection identity is cached across requests. Subsequent reads recheck current
committed storage; tests mutate scope between requests and verify exclusion.
Filesystem manifest reads remain outside an atomic Lance transaction, as before.
The optimization removes round trips rather than validation. Remaining overhead
includes recall/hydration, live collection checks, authoritative batch retrieval,
per-record validation and bounded serialization that raw FTS alone does not do.

Diagnostic evidence: [before](memory-fts-overhead-before.json),
[after](memory-fts-overhead-after.json). Reproduce with
`python benchmarks/memory_provider_profile.py --output /tmp/fts-profile.json`.

## Regression and packaging checks

Python 3.11.15 on macOS arm64. All stores are synthetic and disposable; no real
user palace, transcript or external inference endpoint is used.

| Gate | Observed result |
| --- | --- |
| Castle full normal suite | 2,190 passed, 11 skipped, 3 deselected; coverage 86.63% (85% gate) |
| Runtime full suite | 1,169 passed, 2 skipped |
| Adapter source suite | 75 passed |
| Adapter installed-wheel suite outside checkout | 75 passed |
| Benchmark metrics/frozen fixture checks | 5 passed |
| Serial actual-model benchmark | All functional gates passed; source hashes unchanged; no forbidden network/engine/model initialization |
| Independent read-only review | No blockers or P2 findings; 107 focused checks passed |
| Castle/adapter builds | Wheel and sdist builds passed |
| Wheel/source parity | All 94 Castle and four adapter Python files match current source |
| Runtime-only adapter smoke | Installed ownership, no Castle/model/Harness imports, private worker and tool execution passed |
| Separate installed worker/adapter smoke | Default FTS, recency-opt-in FTS and hybrid passed exact Unicode/CRLF/digests, scoped search/fetch/snapshot, denied foreign IDs, unchanged palace bytes/mtimes/modes and worker reaping |

New regression coverage includes raw-order BM25 ties, zero legacy sparse weights,
recency opt-in and fingerprint isolation; one final batch including bounded
alternates; forged recall metadata; foreign, incomplete and changed sources;
malformed authoritative batches; per-request scope changes; and missing,
nonboolean or mismatching handshake metadata. Worker protocol tests reject model
recency/profile settings. Earlier default-order and per-record-I/O tests were
observed failing before the changes and passing afterward.

## Same frozen benchmark

[Final evidence](memory-pilot-raw-fts-v1.json) retains the same 36 invented source
records, 40 questions (10 development, 30 held out), labels, wing scope, five-hit
output limit and provisioned local model snapshots. The user-requested FTS
recency-off policy and batched I/O were fixed before this run; no labels or
settings were tuned afterward. Each method has three fresh-process cold samples
and 80 warm observations. Other qualification suites and model loads finished
before this serial 74.3-second run.

| Measure | Raw FTS | FTS provider, recency off | Explicit hybrid |
| --- | ---: | ---: | ---: |
| Held-out Recall@5 | 0.986667 | 0.986667 | 0.986667 |
| Held-out MRR@5 | 1.000000 | 1.000000 | 0.980000 |
| Held-out recall-all | 0.960000 | 0.960000 | 0.960000 |
| Held-out NDCG@5 | 0.986855 | 0.983644 | 0.973119 |
| Warm p50 / p95 | 4.206 / 5.069 ms | 14.468 / 16.515 ms | 296.748 / 329.575 ms |
| Cold-process p50 / p95 | 0.970 / 0.982 s | 1.052 / 1.057 s | 8.269 / 8.561 s |
| Peak RSS | 138.7 MiB | 142.7 MiB | 3,112.7 MiB |

Against the previous qualified FTS provider, warm median falls from 93.086 to
14.468 ms (about 84% lower, 6.4 times faster) and p95 from 113.422 to 16.515 ms.
The same-run provider overhead above raw FTS is approximately 10.3 ms at median,
instead of the previous 88.3 ms. The diagnostic call counts explain the I/O
reduction without dropping validation. Host load and OS caches remain uncontrolled,
so these observations are not a production latency SLA or a general recall claim.
Hybrid also uses batched validation while retaining its existing ranking policy.

MRR and Recall@5 now match raw FTS in this fixture. The small NDCG difference is
an equal-score backend tie, not recency boosting. For `held25`, raw five-hit FTS
returns `unicode, evidence, dedup, ...`, while the provider's 100-candidate recall
returns `unicode, dedup, evidence, ...`. A separate read-only diagnostic with the
same frozen text/metadata and index rebuild reproduces this directly in LanceDB:
`evidence` and `dedup` both have BM25 score `3.2190582752227783`, and their order
changes with the retrieval limit. [All-question score evidence](memory-fts-tie-order.json)
is retained. The provider preserves its backend recall order, including ties;
it cannot promise identical tie ordering to a separate request with a different
candidate limit. The larger pool remains necessary for filtering and passage
deduplication without sacrificing the output budget.

All five unanswerable questions still return candidates in every method; no
answer-abstention or truth-assessment policy is introduced. Nine empty-store
probes and all exact-text/digest, provenance, scope and forbidden-import/network
gates passed. The fixture SHA-256 remains
`96e8092bc96f7f1a46ff67072f59f19f59cbca3d1912aeadf83f91eb3726f111`.
Previous two-way and recency-enabled three-way evidence is unchanged. The default
benchmark output is now `memory-pilot-raw-fts-v1.json` to preserve those runs.

```text
a74317a8a30d3c312aee03fb95170f101b62c1db198d968ac4a5186b5b4b52bc  memory-pilot-raw-fts-v1.json
```

Castle's normal command excludes marked benchmark/slow/stress lanes. Existing
SML-dependent skips and dependency deprecation warnings remain; arbitrary SOAR
production equivalence is not claimed. Logs are retained under
`/private/tmp/castle-raw-fts-*`, `/private/tmp/castle-fts-overhead-*`, and
`/private/tmp/runtime-raw-fts-full.log`.

## Candidate artifacts

Artifacts live under `dist/raw-fts-v1/` and
`adapters/prosaic/dist/raw-fts-v1/`. Existing candidates remain in place. Versions
remain unpublished Castle 3.4.1 and adapter 0.1.0; select distinct release versions
before deployment, and retain the Runtime `custom_tool_errors_v1` capability gate.
POSIX process groups and explicit host snapshot persistence remain required.

```text
565b2a13d6dc45dd56a4b3aaaed4ece9282218c92297a36643fd59a554f025ac  cognitive_castle-3.4.1-py3-none-any.whl
d8ac8e05753132b2f4db12d27aa5e7b05b77e2bdaa80f8ffcc1ec4128e0f823c  cognitive_castle-3.4.1.tar.gz
7cb839563436c8105fad08deee128bbe108d44ac40eb09dd00d53285315d11fd  b3_prosaic_memory_castle-0.1.0-py3-none-any.whl
06d9e959dca0087f0419b477c7ab12334139ae8e48fcd493a4b0adb286c6fd98  b3_prosaic_memory_castle-0.1.0.tar.gz
18347181766dc4584aab701af31fff9470bdbab8545423558a340d2060c105c2  memory-fts-overhead-before.json
516809db67caf99073e7eec39ab1a3ee061285a9ca3cb2703e5c631a28af8d0e  memory-fts-overhead-after.json
```
