# Task1b focused preparation evidence

Recorded from actual prior tool outputs; no test reruns were performed to create this artifact. No Task1b native execution has occurred. Frozen packet/config/helper remain unchanged by this note.

## P2 uncharged cold-result regression — RED then GREEN

Exact command, both runs:

`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_lance_owner_stream.py -k large_cold_refusal --noconftest -x -q`

RED used the prior unconditional cold-result write. The test supplied a refused cold tick and exercised real filesystem output plus the existing allocated4KiB refusal slot. Actual failure:

```text
FAILED tests/test_lance_owner_stream.py::test_large_cold_refusal_does_not_create_uncharged_result
assert not harness.result_path(config, "cold-result").exists()
E AssertionError: assert not True
[guard] sampled aggregate peak 37.3 MiB; 0.4s; completed
```

Retained pure fixture in that output: `pytest-585/test_large_cold_refusal_does_n0/run/evidence/cold-result-aaaaaaaaaaaa.json`. This is test-only synthetic metadata, not the large source or destination.

Restored the narrow fix: failed cold ticks return their original result in bounded stdout and write only the preallocated first-refusal slot; they do not create a new cold-result file. Actual GREEN:

```text
.                                                                        [100%]
[guard] sampled aggregate peak 41.9 MiB; 0.2s; completed
```

One test passed; exit0. It checks the actual refusal-slot JSON reason and absence of any newly created cold-result file.

## External raw seal chain — focused positive and negative checks

Exact command:

`/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py --timeout 20 tests/test_lance_owner_stream.py -k large_external_seal --noconftest -x -q`

Actual result:

```text
.                                                                        [100%]
[guard] sampled aggregate peak 43.2 MiB; 0.4s; completed
```

One test passed; exit0. It checks exact raw worker/helper/config byte attestations through the fixed private0400 pin/seal, changes the seal bytes while retaining the original pin digest and requires rejection, and requires rejection when config tries to select a different trusted pin location. It confirms config does not contain the worker hash, avoiding a circular digest. No separate failing RED run was recorded for this seal test; this is a truthful GREEN positive/expected-rejection test result, not a claimed seal RED/GREEN cycle. Earlier startup missing-freeze/qualification construction did have a separate observed missing-feature RED and two-test GREEN (31.7MiB/0.2s), as reported in the task chronology.

## Other current preparation evidence

The new Task1b pure suite was run with `-k large_` (18 cases before adding the seal case):18 passed, sampled aggregate48.5MiB/0.4s. The focused seal case above adds one independently passing case. No unchanged Task1a pure/native case was rerun. File-scoped Ruff and diff whitespace checks passed before packet assembly. Hosts in these tests imported no SQLite/Lance/Arrow/model engine; native/private operator entry remained disabled with the unset freeze literal.

## Corrected normal artifact arithmetic

T is **382**: one temporary-family root +one coord-source directory +380 exact logical phase directories. The metadata builder's printed381/combined1358 omitted the temporary root; retain its original output/artifact rather than alter the candidate packet. Correct normal total is **1359 =122 source +610 destination +245 harness +382 temp**. Hard group caps remain128+1024+256+1024=2432; byte limits and candidateC/H are unchanged. Actual census counts the temporary root, so this is a static documentation arithmetic correction, not an enforcement change.

The owned512MiB envelope covers the named eight retained source families, dedicated destination, private packet/harness/coordination/evidence, exact/common temp families, fixed code baseline and explicit basetemp. Outer safe-wrapper transient HOME/cache/admission infrastructure and the sleeping pytest ancestor are distinguished from this owned-storage envelope. Outer safe-runner aggregate RSS includes its observed descendants and remains separately reported; inner source128/192MiB and exact192/256MiB continue to mean each existing supervised task plus its immediate host. Queue/source transient open-unlinked disk peaks remain unmeasured; exact own-fd/temp peaks are sampled tripwires, not kernel quotas.
