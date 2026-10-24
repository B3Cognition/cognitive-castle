# Memory provider pilot

`memory_provider_bench.py` compares actual LanceDB full-text retrieval with the
production `MemoryService.search()` profiles: `memory-fts-v1` (no neural models)
and explicit hybrid `memory-v1`, including real BAAI/bge-m3 embeddings and
BAAI/bge-reranker-base scores. It creates disposable
palaces from `tests/fixtures/memory_eval/coding_decisions_v1.json`; it does not
open a user's palace. Model weights must already exist in the supplied cache.

```bash
HF_HOME=/path/to/provisioned/cache \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python benchmarks/memory_provider_bench.py \
  --output docs/verification/memory-pilot-raw-fts-v1.json

python -m pytest tests/benchmarks/test_memory_provider_metrics.py -q
```

The versioned fixture contains 36 invented source records and 40 questions,
split into 10 development and 30 held-out questions before its first run. It
includes old/current database and cache decisions, multi-source questions,
five unanswerable questions, and three wrong-wing distractors. Labels and
retrieval configuration are not adjusted after observing results. All three methods
use the same corpus, wing scope and five-hit limit; no KG is provisioned.
The FTS provider preserves raw FTS ordering by default, with recency explicitly
off. This is the user-requested follow-up to the recency-enabled FTS pilot;
previous labels and evidence remain unchanged.

Recall, reciprocal rank, recall-any/all and NDCG exclude unanswerable questions
from their denominators. Precision uses a five-position denominator and also
counts unanswerable questions. NDCG's ideal ordering uses the full relevant set,
including relevant records that a method failed to retrieve. Empty-result rate
for unanswerable queries is reported separately. Returning candidates is not an
answer or an abstention decision; the pilot does not introduce a score threshold.

Three fresh interpreter processes per method measure model-cold search of the
same development query. The first process also runs two warm passes over all 40
questions. OS file caches may be warm. Search latency excludes subsequent exact
fetches used to check text, digest, revision, capture time and source provenance.
The evidence includes all per-query rankings, context/payload byte counts,
process peak RSS, package versions, model snapshot/file hashes and source hashes.
The raw FTS timing covers its index query; both provider timings also include
service validation and serialization. Their payload schemas differ, so use the
separate context-text byte counts to compare retrieved context size directly.

Network connections and optional engine imports are actively blocked in the
children. Exact fetch must reject every wrong-wing record. A separate empty
palace must produce a successful empty search. These functional checks do not
establish production recall, factual correctness or generated-answer quality.
If source files change during a run, the JSON records that fact; rerun against
settled sources before treating its measurements as reproducible evidence.
Neural imports are additionally blocked in raw FTS and `memory-fts-v1` children,
while permitting dependency availability probes that do not initialize modules.
Previous evidence is retained unchanged in `memory-pilot-v1.json` (two-way) and
`memory-pilot-fts-v1.json` (recency-enabled FTS provider).

For a separate I/O diagnosis, run
`python benchmarks/memory_provider_profile.py --output /tmp/fts-profile.json`.
It uses the same invented text with zero vectors, forbids neural/network access,
and captures cProfile call counts/timings for 80 raw FTS and provider queries.
This diagnostic is not a substitute for the actual-model qualification run.

Exact duplicate passages select the newest completed capture. Legacy capture
strings without a timezone are interpreted as UTC solely for deterministic
ordering; their stored text and public capture strings remain unchanged. Aware
timestamps compare as instants, and unknown or malformed timestamps use a stable
record-ID fallback. Alternate-source completeness refers to the known scoped
recall pool, with at most eight source descriptors per hit; it does not claim an
exhaustive palace scan.

Keep the provider disabled pending review of the recorded pilot and the broader
storage, packaging, worker and adapter qualification gates. A small invented
corpus can favor lexical retrieval and does not justify claims about private
project history or general retrieval superiority.
