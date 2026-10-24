# Bounded hook startup measurements

The follow-up to the durable-memory release reduces unrelated work during cold
startup. The console entry point parses only supported Codex hook forms and
delegates everything else, including diagnostics, to the existing CLI. Process
supervision filters raw PIDs by group before constructing checked identities,
then rechecks membership to reject the identified PID-reuse race.

## Comparable local measurement

Eighteen fresh Python subprocesses used the same private, previously verified
Sixth Sense fixture and SessionStart payload without a transcript submission.
Each subprocess used a console-equivalent launcher. Six samples per variant ran
in rotating order against the baseline `19d258a` and the candidate worktree.
All returned the same six source IDs and identical evidence packets after
excluding variable resource measurements. Output remained below 8 KiB.

| Variant | Successful samples | Minimum | Median | Maximum | Sampled peak task / parent plus task |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 6/6 | 174.74 ms | 187.85 ms | 236.33 ms | 45.3 / 74.6 MiB |
| Process scan only | 6/6 | 169.65 ms | 175.83 ms | 246.43 ms | 45.4 / 79.5 MiB |
| Scan and console route | 6/6 | 155.83 ms | 164.06 ms | 218.13 ms | 44.5 / 70.5 MiB |

The combined median was 12.7% lower in this small local comparison. These samples
are not a latency-distribution guarantee. The **100 ms startup target remains
unmet**. No resident process or cache was introduced. Production sampled RSS
tripwires remain 128 MiB for the task and 192 MiB for parent plus task; sampling
does not establish a hard kernel allocation ceiling. Pressure checks, deadlines,
parent-death handling, process-group cleanup and exposure policy remain in force.

Private reports retain every sample, code hashes and evidence-packet hashes.
Organization transcripts and source text are not published with these results.

## Regression and review scope

The original guardian failed three new regressions; deliberately removing the
new post-identity membership check failed the PID-reuse case. Restored code passed
47 focused guardian/runtime/source checks. The original console entry point
failed all 14 initial route tests. The new route passed those tests and a further
enabled-capture cold subprocess regression that verifies exact source text,
escaped output size and absence of unrelated CLI imports. Unsupported argument
forms retain the full CLI, including legacy harnesses and palace positioning.

Independent review found no blocking correctness defect. Its identified proof
gap—initial cold tests exercised paused legacy handling—was addressed by that
enabled-capture regression. Actual installed console-script verification follows
reinstallation because changing package metadata alone does not replace a
previously generated console script. Active-client hook dispatch and complete
retrieval coverage remain separate from this performance comparison.
