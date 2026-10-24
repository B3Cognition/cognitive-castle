# Release packaging split verification — 2026-10-24

Third stacked change: shared hardening #107 → optional provider #108 → release
packaging. Original combined PR #106 and its historical receipts remain retained.
Memory is disabled by default; no tag, merge or publication is included.

Local final packaging stage (Python 3.11.15, macOS ARM64, offline cached CPU
models, same test-only MPS-disabling launcher): main **2516 passed**, 11 existing
skips/two benchmark deselections, 90.25s; fresh supervision **48 passed**, 10.54s;
combined **85.31%**, unchanged 85% gate. Adapter **76 passed**, 10.16s, including
source-archive contents. Adapter tests use the qualified tool-capable candidate
SDK environment, not public Runtime model-tool certification.

Both wheel/sdist pairs build; strict Twine checks pass all four. Rebuilding each
sdist reproduces every original wheel payload except generated RECORD: worker
136 files, adapter nine files. Local archive digests are retained in the report
bundle; authoritative release candidate bytes will come from the locked native
CI build of the final selected source commit. Historical candidate digests are
not silently replaced by these local builds.

The same frozen benchmark ran three cold processes and two warm passes for raw
FTS, FTS provider and opt-in dense provider: 36 documents, ten dev/thirty heldout
questions, fixture SHA-256
`96e8092bc96f7f1a46ff67072f59f19f59cbca3d1912aeadf83f91eb3726f111`.

| Path | Warm p50 | Warm p95 | Heldout recall@5 |
| --- | ---: | ---: | ---: |
| Raw LanceDB FTS | 3.73 ms | 4.39 ms | 0.9867 |
| FTS provider, default raw order | 12.85 ms | 14.09 ms | 0.9867 |
| Explicit dense profile | 287.16 ms | 311.40 ms | 0.9867 |

All functional/integrity gates passed, no forbidden engine/network attempt was
observed, and measured retrieval-source hashes stayed unchanged during the run.
Raw JSON SHA-256 is
`a607173de7f25890a26af2ff754470fd1583ece27bca0fef9e1eb5f36b800e17`.
This synthetic fixture does not establish production recall, answer accuracy or
abstention; every path returned nonempty results for its unanswerable questions.

Fresh CI exposed nineteen Windows fixture assumptions after all six platform
jobs completed without timeout. Their original failing logs are retained. The
test-fixture corrections and a fully green matrix remain required before release,
as do fresh installed native AMD64/ARM64 × PostgreSQL 16/18 candidate receipts.
The watchdog prevents a stalled pytest process from exhausting the whole job
without diagnostic retention; the original stall's exact blocking call remains
unproven. Do not present instrumentation alone as a root-cause explanation.
