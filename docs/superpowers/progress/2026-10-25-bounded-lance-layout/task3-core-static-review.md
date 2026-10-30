# Task 3 core static review

Decision: no remaining blocking defect found in the frozen seven-file core packet. This approves the reviewed core for the separately controlled integration qualification, conditional on the v5 metadata review. It does not accept Task 3 as complete or qualify native performance, full capacity, activation, or production use.

Review was read-only: source, diff, recorded pure assertions, and adjacent inherited verifier/metadata interfaces. No imports, tests, engines, databases, source inventory, or native operations were executed. The author's 40 pure passes are recorded evidence, not rerun results.

## Exact binding

Independently rehashed both packet artifacts and all seven files; byte counts and SHA256 matched the supplied report.

- `task3-core-2.diff`: 120389 bytes, `589b086ad54cfb475c92f82e924b8f287ebde27f42e6fe099d1a8357703a62af`.
- `task3-core-pure-results-2.json`: 4628 bytes, `4146a44610e27269927363f73d5a667794405c095809e1efc7c8de7c0f13c797`.
- `cognitive_castle/lance_layout_codec.py`: `720bb2ba87836905301a3ce1dbf79c8b8eddfffe7d3c88af1114de2f5a247bae`.
- `cognitive_castle/migration_coordinator.py`: `c6fe14a27907c1fbb0c956745893cd818419012f66f878555970479e61589f6c`.
- `cognitive_castle/semantic_runtime.py`: `eb02df8403c1820349bff4957c8226f00173a0dd5b76669ea055fce84729ca39`.
- `cognitive_castle/lance_exact_worker.py`: `be01ca549c120242d92558a98927fdc9aa94808324fc76cd5186f33846b4069a`.
- `cognitive_castle/partitioned_exact_store.py`: `897c0d1fcc136ea82ca0492d67416561e511b9606beb7c2a00219e39ea1baef1`.
- `tests/test_partitioned_exact_store.py`: `d48cd75c2b5af96237fb89cbe06c567fb3222d722ac5bbbf95082f652da66ece`.
- `tests/test_layout_coordinator.py`: `e51e41baa60fe9a10e950926b6c2f87a27aec36d64df096cb7022d20734610a0`.

## Reviewed invariants

- New-owner planning leaves the original source frontier unchanged. Binding selects the registered target; source regeneration and pending equality remain mandatory. First publication requires a fresh append followed by a separate actual existing replay. A cold identical existing replay can proceed directly to actual owner/LIVE checks and atomic ACK. Resource refusals and late owner/LIVE results stop before ACK.
- Facade entry validates the registered qualification and exact pending digest, source binding, candidate IDs and input row hashes. The durable branch retains the original full batch proof and exact canonical record equality, then checks foreign first-owner visibility. Route observations come from actual retrieved rows; an existing published route retains its original version and is checked against current pinned data.
- Ordinary reads pass the metadata publication gate before opening Lance. Pending owner/LIVE reads require the exact intent and after-version and an actual batch receipt with the expected receipt/source/proof ID set. Namespace hooks remain subject to the previously reviewed default legacy read/write refusal; the private facade override revalidates registered authority.
- Owner verification uses the registered bounded physical span, strict decoded rows, actual field/text/membership hashes, reused original record equality and original visibility. The existing strict decoder still checks receipt source binding, owner marker order/equality and LIVE receipt content; those checks are not removed by the new span wrapper.
- Resolver lookups are grouped in at most 32 IDs. The facade retains its home and one current remote dataset, releases all retained remote references before switching or writing, and counts actual remote acquisitions. Older published route versions are allowed only below the actual pin and with exact row hashes; future versions refuse. No persistent row/body cache is introduced.
- Physical rows, batch receipts, final owner/LIVE rows, encoded frames and index work enter the planning counters. Positive write charges, fixed geometry increments and the tail cadence condition are enforced. Actual append rows must equal the reserved new-ID set; inherited artifact pre/post checks remain active. Index maintenance is explicit, guarded, version/geometry checked and must end with one segment and no unindexed tail.
- Directory pages remain fixed-size actual physical observations, bound to epoch, rebuild token, partition pin and cursor. Confirmed rows use authoritative claims/gates; provisional append rows require the pending actual batch proof. The facade does not advance metadata reconstruction, source cursors or publication gates itself.
- Runtime profiles stay fixed: exact 192/256 MiB with 2-second reads and 3-second writes; SQLite source 128/192 MiB/2 seconds; native source 512/640 MiB/2 seconds. Coordinator stages share the existing five-second session and introduce no per-stage deadline reset.

## Integration limits

The core depends on the separately reviewed v5 authority for claim completeness, selected-partition identity, pending mutation shape, owner spans, rebuild debt, and atomic publication. The inspected method contracts are consistent; this review does not replace the root's full metadata review or prove real SQL transaction behavior. In particular, ACK after an unknown native commit must preserve prior rebuild debt, and route loss must remain unavailable until reconstruction completes.

Actual same-session timing, two-dataset RSS, Lance index optimization/version behavior, retained spill accounting and supervised end-to-end publication remain native qualification obligations. The current packet has no native execution evidence. The complete fixture must still prove real first publication, cold/lost-ACK recovery, pre-ACK legacy refusal, earlier-version canonical reuse and directory reconstruction with unchanged source progress. Full-corpus capacity and the known discovery-table preservation gap remain separate later gates.
