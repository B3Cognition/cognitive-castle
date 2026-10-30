# Task 3 fifth native case and start accounting

Static review only; no imports, tests, engines, databases or fixture execution. This is preparation, not native qualification.

Reviewed candidate `tests/test_layout_native_integration.py`: 34956 bytes, SHA256 `f3343f7c05f48fe31f0df1af4f7671463729148936e32bf04bf48eb309e18c1c`.

Referenced unchanged coordinator `c6fe14a27907c1fbb0c956745893cd818419012f66f878555970479e61589f6c`, runtime `eb02df8403c1820349bff4957c8226f00173a0dd5b76669ea055fce84729ca39`, and existing native fixture helper `02c808b7eee85f7e1aee9b4339db5edbc6b6ffd74358a85a85166dfb787a18bb`.

## Fifth-case scope

`_setup(native=True)` calls the existing single-source native builder once under its separate 512/640 MiB, five-second setup supervisor. That setup allowance is not transferred to source export. The real plan and export requests use the unchanged native 512/640 MiB, two-second profile, within one shared five-second publication tick. No engine is imported by the host fixture.

The case checks the original physical following key, independently known text hash/character/byte lengths, fresh append followed by identical reopened existing replay, same-version pending-context owner proof and real ACK. It then obtains actual source EOF, hides the successful terminal ACK response, and requires a subsequent tick to return the stored result after only the queue-state call. Count/frontier equality and before/after source artifact fingerprints guard against recount and mutation.

One narrow preparation finding remains in this candidate: it does not compare captured exported canonical record IDs and full provenance with the independent original fixture records. Text hash, lengths, member count and physical following key alone cannot detect an internally consistent occurrence/provenance rewrite. Compare the captured `bulk_record` entries' `id`, `text` and decoded `provenance` to `source['rows'][0]['records']`; no additional worker call is needed. The parent owns the correction. No other blocker found in the fifth-case/helper delta.

## Exact start maxima

These are logical attempted worker starts on the fixed successful paths, including explicit fixture construction and fault/metadata calls. Early refusal stops sooner. They do not authorize retries or native execution.

| Case | Decomposition | Starts |
|---|---|---:|
| First LIVE owner | setup 2 + new LIVE tick 10 + state 1 + public receipt 1 | 14 |
| Lost append | setup 2 + fresh tick stopped after append 6 + state 1 + legacy reads 3 + context-free read 1 + cold LIVE tick 6 + state 1 | 20 |
| Lost ACK | setup 2 + full new LIVE tick 10 + before state 1 + exact ACK replay 1 + after state 1 | 15 |
| Rebuild debt and cross-partition reuse | setup 2 + LIVE tick 10 + lost new HISTORY append 6 + rebuild prepare 1 + cold HISTORY tick 5 + reconstruction/observation sequence 20 + second-source setup/attach 2 + new LIVE tick 10 + final physical/routes/public/state observations 5 | 61 |
| Native source and terminal ACK | native setup/register 2 + new non-LIVE tick 9 + state 1 + EOF/lost-terminal-ACK tick 3 + terminal replay tick 1 + final state 1 | 17 |
| Total | Five current cases only | 127 |

The fourth case's 20 middle calls are: debt absence; before state; lose route; missing route lookup; rebuild prepare; stale page read; old-token page read; rebuild restart; stale reconcile; current first page; partial reconcile; identical page replay; incomplete absence; interrupted state; second page; complete reconcile; certified absence; restored route; original public source; after state.

Current `_MAX_CALLS = 150` therefore leaves 23 unused starts. That spare arithmetic is not permission to add tail, negative, retry or fixture stages. The separate finite tail/negative preparation and any selected legacy cases need their own reviewed count before a combined run is frozen.

Tick formulas from the reviewed coordinator: a new LIVE owner uses state, source plan, bind, source export, prepare, Fresh, Existing, owner, LIVE receipt, ACK (10). A new non-LIVE owner omits the LIVE receipt (9). Pending cold LIVE/non-LIVE ticks use 6/5. An EOF planning tick uses state, source plan and terminal ACK (3); stored terminal replay uses state only (1). Each tick retains the unchanged shared five-second deadline, rather than multiplying it by its number of stages.

## Correction closure

Re-read the parent-owned correction in `tests/test_layout_native_integration.py`, now 35236 bytes, SHA256 `6d370c06ff75d0091a3a8a6d181b16a9a505f01bd99748dda9b74659be196300`. The test compares every captured `bulk_record` entry's ID, exact text and raw canonical provenance string, in order, with the independent original record list. This closes the sole assertion finding without an additional worker call. The start table remains 14 + 20 + 15 + 61 + 17 = 127.

Decision: scoped fifth-case/helper preparation review approved; no remaining blocker found in that delta. This is still unexecuted preparation, conditional on the final whole-fixture resource/scope freeze and root's native grant. Earlier candidate and finding are retained above as review history.
