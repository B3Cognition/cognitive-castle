# Durable memory evidence — 2026-10-24

This report distinguishes exact storage, retrieval and interpretation. It does not
claim universal recall, complete historical capture or independent semantic understanding.
Private source material and generated private fixtures are excluded from this repository.

## Actual historical capture probe

A private, separate palace processed four original Sixth Sense Claude JSONL files
through the production supervised worker. Original files were not modified.
The 122.4-second probe completed 377 of 377 operations successfully. It processed
134,193,709 of 649,706,818 bytes observed during the run; 515,513,109 bytes remained
pending in one of four sources. One original continued to grow during measurement.
These are last-observed counts, not a frozen whole-corpus snapshot.

It indexed 2,446,555 exact text bytes. All 22 retrieved results (21 unique chunks)
were independently checked against bounded original-record reads: record hash,
whole decoded text-block hash, exact chunk hash and returned text hash matched.
A fresh worker restored eight context excerpts in 6,866 encoded bytes.

Sampled peak task RSS was 50.7 MiB; parent plus task was 73.4 MiB. Context restore
took 147.6 ms: within the two-second deadline but above the repository's 100 ms
startup target. Sampling is a tripwire measurement, not a hard allocation ceiling.
The internal recall worker hydrates full chunks; its 12,096-byte maximum observed
frame is separate from the public adapter's 8 KiB response bound.

Observed omissions included 13,950 tool blocks, 44 attachments, 20,489 unsupported
records and eight oversized records. A bounded key-only sample showed both
operational metadata and meaningful additional prompts/context among unknown
records. They must not be relabelled wholesale as harmless metadata. This probe
proves incremental progress and exact returned evidence, not full knowledge capture.

## Selected excerpt replay

An independently prepared private fixture contains ten questions, five source
files and 28 exact hashed spans. The public evaluator verifies source and span
hashes before replaying selected excerpts. This is explicitly labelled a replay
and cannot substitute for the real-history test above.

The initial deliberately limited lexical baseline used the first four content
words, one result per lookup and 8 KiB across the entire question. All 28 spans
(28,304 UTF-8 bytes) survived exact capture and reopened storage, but complete
expected-span recall was 25% on two questions and zero on eight. Persistence
success therefore does not establish adequate retrieval quality. A separate,
question-derived query-plan profile must retain the baseline and disclose its
per-call and per-question budgets; expected spans must not select search results.

## Independent review

Review reproduced workspace reassignment across source generations, a context
transport overflow after resource metadata, and unsupported-platform fallback to
legacy model-backed capture. Dedicated regressions must pass before release.

Reproduce the public synthetic evaluation with:

```sh
python scripts/bounded_memory_evaluation.py
```

Private fixture runs are operator-controlled and must keep generated reports private.
Full model-dependent repository validation runs in CI; local checks use the guarded
focused test runner, which denies model and network imports and monitors memory.

## Final local regression evidence

The integrated bounded-memory suite passed 232 tests in13.5 seconds with a
271.9MiB sampled aggregate test-process peak. This includes pytest and multiple
owned test processes; production worker limits remain128MiB and192MiB combined.
Independent re-review passed19 focused reproductions and found no remaining
blocker in the reviewed delta. Global Ruff check/format and diff checks passed.
Full repository CI and installed activation remain separate release gates.

The unchanged frozen-query OR counterfactual found39/39 candidate instances,
but only19/39 complete evidence instances; all ten aggregate question budgets
were exhausted by indiscriminate paging. Prefix-OR offered no complete-evidence
gain. Production therefore adds only explicit literal `match=any`, preserving
`all` by default. These measured results do not prove adaptive host competence
or complete recall in a larger mixed-project corpus.

A final accounting regression found that event-only Codex message text had been
assumed duplicate without proof of a canonical counterpart. User/agent event-only
records now remain explicit unsupported omissions; old unverified duplicate
counters also block a completeness claim. Three failing regressions drove the fix.
