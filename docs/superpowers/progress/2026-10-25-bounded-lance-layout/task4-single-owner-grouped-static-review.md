# Single-owner grouped verification — independent static review

Verdict: no blocking issue found in the bound candidate. Approved as a static preparation only. RED/GREEN and all grouped native execution remain deferred/unrun; this is not Task3 acceptance, a timing qualification, or completion of the full Task4 multiowner work.

Review scope was the four changed product files, two affected pure test files, and two native fixture adaptations against `task4-grouped-static-baseline-1` and the previously reviewed tail. No product/test imports, engines, DB reads, tests, probes, or native execution were performed. Only source reads and stdlib file hashes/literal size arithmetic were used. No implementation files were edited.

## Exact bindings

- Candidate diff: `task4-single-owner-grouped-static-1.diff`, 30,273 bytes, SHA256 `a4947a35ea451ec2b87810234a8c10391bd92c65183de11be99ac08991164558`.
- Candidate report: `task4-single-owner-grouped-static-results-1.json`, 5,098 bytes, SHA256 `5ece9572b0f2c6a1dec3653b6eb8ae925c18fe1fed0d2cd6d785ff641c9d2532`.
- Preserved baseline manifest: SHA256 `7e3991a72bd802ff898e3f1b053a5c8bedbae70d5f1e6101912043199b1a665c`.

All eight candidate size/hash bindings and all eight archived baseline size/hash bindings were independently checked and matched. The runtime file remains byte-identical to its archived baseline.

| Candidate file | SHA256 |
|---|---|
| `cognitive_castle/lance_layout_codec.py` | `5644db99c9cd58feb8cb9ad76be7287ce59de0982d38cefdd278476a44881476` |
| `cognitive_castle/partitioned_exact_store.py` | `aefa2e25327bb398f3e6e75df57fc0d915d4cc499e256263e97a6e9205fc2de7` |
| `cognitive_castle/lance_exact_worker.py` | `9e31ccbe59c0c4ebeece7fdc695029348ffe400ad1ddcd93ecf1219f17947946` |
| `cognitive_castle/migration_coordinator.py` | `d102ad94dae5a53a6b484a05a697f16e551f14d91ebc06502d15ba780eb9c7ea` |
| `tests/test_partitioned_exact_store.py` | `1f2f576775d0c3c9c62809616722761e6118de028407b74351c4adf7943e3db0` |
| `tests/test_layout_coordinator.py` | `2c17f902b5c2fd64eb33cc78680ec56bd4591e3babe11e278154134e2b020da1` |
| `tests/test_layout_native_integration.py` | `d6b66aa9da3b6694e5a9b7b84162fa8b8a540b4a3365a5e4dbceac048a68f821` |
| `tests/test_layout_native_tail.py` | `f6c9d5c0c7e9f58b7158e5ed7173a1ef736834678003b64d3fdecd70ff47c5a8` |

## Proof and resource path

`layout_verify_owners` requires the actual registered pending intent, exactly one final owner, and a positive exact-integer version. It performs one inherited home `_read(version=...)`; that path retains namespace supervision, actual geometry/index/version validation, and the existing actual batch-receipt check. Owner and LIVE receipt locations must use the current home/gate/version. Actual owner decoding and the inherited `_verify_receipt` execute on this same dataset. Canonical hydration still uses the existing bounded resolver and first-owner visibility rules, including home plus at most one remote handle. Remote references release in `finally`.

There is no new cache and no third whole-owner scan. The separate actual Existing replay and complete original-byte proof remain mandatory and unchanged. Existing bounded `_context_batch` rechecks on the same handle are retained.

The closed summary binds the intent hash, actual manifest hash, owner, partition, exact positive version, original memory IDs and actual LIVE digest/receipt hash. The coordinator compares it with freshly regenerated source, registered pending intent, and the replay version. Its final `verified_summary` uses the validated returned owner observations; the earlier source-derived references serve only to preflight replay routes. Non-ok, missing/extra fields, wrong/partial observations, invalid numeric shapes and late responses stop before ACK. Zero-owner staging skips the operation; multiple owners refuse.

The body-free summary bound accommodates the original domains: namespace/key are each at most 128 UTF-8 bytes, original LIVE has at most nine fixed-width memory IDs, and partition/version are bounded int64. Literal worst-case serialization with 128 maximally escaped one-byte controls in each string, nine IDs, and maximum integers is 2,833 bytes with default JSON spacing (2,800 compact), below 4,096. This was stdlib arithmetic, not an executed product test.

The new closed worker operation is read-only. Unchanged `semantic_runtime` assigns read 2s and exact 192/256MiB; the original shared 5s session remains. No source profiles, frame bounds, artifact ceilings or deadline mechanisms were changed by this packet.

## Fixture and completion limits

The native adaptations replace the original owner/LIVE pair with one grouped observation and preserve separate Fresh/Existing imports, original source/record/provenance assertions, pinned proofs, atomic ACK/frontier checks, pre-ACK legacy refusal, lost response recovery and actual source EOF behavior. Fourth-case original HISTORY selection, four real index maintenance calls, remote route V2 under current home pin V3, no duplicate canonical ID, and original public-source equality remain intact. Tail source-byte/frontier and maintenance refusal assertions remain intact.

The schedule delta is consistent: first five `13/19/14/63/17 = 126` starts; tail `33/8/10/23/47 = 121`. Only LIVE finalizations save one call; HISTORY/audit retain one owner observation. The fourth-case outer 55s requirement and all original source/native/shared/frame gates remain mandatory. These counts are static preparation, not measured successful execution.

The preserved v3 first-LIVE qualification remains failed at the shared deadline, with ACK commit state unknown/unasserted. This review does not relabel that run or establish that grouping now fits 5s. The prepared 77 pure cases (29 grouped) and any newly bound native scope still require root-admitted runtime verification before commit/merge/install claims.
