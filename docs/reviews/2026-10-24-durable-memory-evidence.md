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
legacy model-backed capture. Those defects were fixed and dedicated regressions
passed before release.

Reproduce the public synthetic evaluation with:

```sh
python scripts/bounded_memory_evaluation.py
```

Private fixture runs are operator-controlled and must keep generated reports private.
Full model-dependent repository validation runs in CI; local checks use the guarded
focused test runner, which denies model and network imports and monitors memory.

## Final local regression evidence

The integrated bounded-memory suite passed 232 tests in 13.5 seconds with a
271.9 MiB sampled aggregate test-process peak. This includes pytest and multiple
owned test processes; production worker limits remain 128 MiB and 192 MiB combined.
Independent re-review passed 19 focused reproductions and found no remaining
blocker in the reviewed delta. Global Ruff check/format and diff checks passed.
The subsequent CI and installed activation evidence is recorded below.

The unchanged frozen-query OR counterfactual found 39/39 candidate instances,
but only 19/39 complete evidence instances; all ten 32 KiB aggregate question
budgets were exhausted by indiscriminate paging. Individual public responses
remain limited to 8 KiB. Prefix-OR offered no complete-evidence
gain. Production therefore adds only explicit literal `match=any`, preserving
`all` by default. These measured results do not prove adaptive host competence
or complete recall in a larger mixed-project corpus.

A final accounting regression found that event-only Codex message text had been
assumed duplicate without proof of a canonical counterpart. User/agent event-only
records now remain explicit unsupported omissions; old unverified duplicate
counters also block a completeness claim. Three failing regressions drove the fix.

## Merged release and installed verification

[PR #110](https://github.com/B3Cognition/cognitive-castle/pull/110) merged into
`develop` as `d25faca29b2f3fb6e027ab89b02574a4b30c93d0`. All nine checks passed,
including Linux Python 3.10–3.13, Windows, macOS, lint, version validation and
the unchanged 85% coverage gate. Combined coverage was 86% in the
[release CI run](https://github.com/B3Cognition/cognitive-castle/actions/runs/40087334475).

A final selected-original Sixth Sense probe processed all 1,000,890 observed
bytes of one transcript, indexed 25,075 exact text bytes and restored the same
eight source IDs after a fresh worker restart. All eight returned chunks matched
original record, text-block and chunk hashes. Its 64 tool blocks and 204 unsupported
records remained explicit gaps. This is a completed byte scan of one source,
not complete historical or semantic capture.

The merged installation was exercised through a fresh MCP process and the actual
hook CLI. Measurements from the private `installed-live-proof.json` artifact:

| Installed operation | Sources | Encoded output | Elapsed | Sampled parent plus task RSS |
| --- | ---: | ---: | ---: | ---: |
| MCP context | 6 | 5,278 bytes | 148.1 ms supervised operation | 105.4 MiB |
| SessionStart hook CLI | 6 | 6,016 bytes | 359.2 ms whole command | 79.4 MiB |

Sampled task peaks were 45.2 MiB and 44.8 MiB respectively. Production tripwires
remain 128 MiB for the task and 192 MiB for parent plus task. These observations
meet the two-second read deadline and 500 ms hook budget. The **100 ms startup
target remains missed**.

Bounded capture is enabled with a 60-second timer and five-second ticks. The
legacy nightly job is disabled and its capture pause is preserved. Private
configuration backups and rollback artifacts were retained. The recorded live
status had no spooled events or pending source bytes, but discovery of both
registered conversation roots was incomplete. It also reported an old checkpoint
with incomplete accounting, eight unscoped chunks and explicit omissions.
Overall historical coverage remains **partial**.

A live rollback restored the four managed configuration files and unloaded the
bounded timer while keeping legacy mining disabled. Reactivation then passed
the same configuration, policy and installation checks. All six source IDs from
the installed MCP proof remained readable afterward. The private
`live-rollback-proof.json` records this check; original sources and indexed data
were retained.

## Compaction lifecycle verification and remaining gates

The supported lifecycle is PreCompact capture followed by context restoration in
SessionStart with `source: "compact"`. Codex delivers that SessionStart context
before the next model request, including continuation within a turn. PreCompact
does not provide additional-context output. See the [official hook documentation](https://learn.chatgpt.com/docs/hooks).

The private `compaction-lifecycle-proof.json` records actual CLI calls using those
event payloads. PreCompact returned in 137 ms and durably queued its event while
the coordinator lock was busy. A subsequent tick queued one source and completed
one slice. SessionStart with `source: "compact"` then returned six sources in a
6,498-byte hook envelope in 266.7 ms. This checks the CLI handoff and retry path;
background work need not finish before every context read.

**Dispatch by the active Codex client and reconnect remain unverified.** A fresh
MCP process and manually supplied hook payloads do not prove that the existing
client has loaded the new tools or invokes these hooks. The final completion
audit remains open for that client verification and the missed startup target.
Client verification must also check hook trust: current Codex documentation
requires review of changed non-managed hook definitions through `/hooks` before
they can run. CLI invocation alone does not exercise that host gate.
The measured 19/39 complete evidence instances remain a retrieval limitation;
39/39 candidate availability must not be reported as 100% recall.
