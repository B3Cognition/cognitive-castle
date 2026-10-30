# Task3 integrated native coverage preparation

Preparation only. The core/metadata implementation and concrete fixture envelope are still changing. This is a case matrix for `tests/test_layout_native_integration.py`, not a native grant, a sealed schedule, or Task3 acceptance. Basis: layout plan lines 164–238, existing coordinator/runtime, and the listed test helpers. No engines, tests, databases, or product edits were used for this audit.

## Sessions and start accounting

Use the real `SemanticSession(..., interactive=False)` and actual product dispatch. Its absolute five-second deadline starts in the constructor (`semantic_runtime.py:25–38`); every stage inherits that deadline. One publication attempt cannot open another session to finish its proof/ACK. A later cold retry is a new attempt with newly regenerated source and actual replay proof.

Keep the existing distinct profiles: exact read 2s/write 3s at 192/256 MiB; queue read 2s/write 3s at 128/192 MiB; SQLite source 2s at 128/192 MiB; native source 2s at 512/640 MiB. The existing native synthetic builder is a separate, counted setup operation, up to 5s at 512/640 MiB. Do not apply exact caps to the source builder, or treat the builder's limits as publication authority. Actual setup charge/geometry/output bounds must be frozen separately.

Count every supervised worker start, including setup, source, queue, fault, observation and refused calls. For the implemented pending branch (`migration_coordinator.py:67–199`):

`state + source + I imports + F owner reads + L original LIVE reads + ACK = 3 + I + F + L`

| Pending attempt | Maximum starts in the same 5s session |
|---|---:|
| Fresh final LIVE owner (I=2,F=1,L=1) | 7 |
| Cold identical Existing final LIVE owner | 6 |
| Fresh / Existing final historical or AUDIT owner | 6 / 5 |
| Fresh / Existing non-final staging interval | 5 / 4 |

The first import may return FreshAppend; only a separate actual reopened ExistingVerified result permits proof/ACK. A first-call ExistingVerified already performs the full current proof and needs no second import. State/visibility/stat observations after the tick are additional counted calls, never an extension of its five seconds.

The no-pending plan/allocation branch was unfinished when inspected. Before launch, enumerate its actual queue/source/partition starts from final code, including every prepare and trusted registration call. The formulas below intentionally exclude that explicitly counted setup; no complete suite maximum can honestly be sealed before those paths and the fixture geometry are fixed.

## Minimal runtime cases

These are distinct assertions that can share a small retained fixture where their preconditions are met. Avoid re-running the 52MiB Task1 migration or the whole Task2 metadata suite.

| Case | Required actual behavior / evidence | Worker-start allowance after its registered pending/setup precondition |
|---|---|---|
| Plan then fresh publication | Actual source plan does not advance source/frontier or publish; trusted bind fixes one home. Fresh append → separate process Existing → owner + original LIVE proof → real atomic ACK, all within one session. Public read_sources/page/receipt preserve original content and envelopes. | LIVE tick ≤7; separately one final state + three public reads =4. Planning/allocation starts enumerated separately. |
| Lost append response and missing ACK | Suppress the response only after real append. Pending intent/window/home/reservation and completed frontier remain unchanged. Before recovery, ordinary BulkExactStore bulk_owner/read_sources/receipt at that registered home and a context-free facade read refuse. New cold tick regenerates the exact intent, returns actual Existing with zero append, performs private pinned owner/LIVE proof and ACKs once. | Loss attempt ≤3; four pre-ACK reads; cold LIVE tick ≤6; one final state: ≤14. |
| Lost ACK response | Suppress the response after the real queue transaction commits. Observe pending=None and exactly one frontier/count update. Replay the exact committed ACK identity idempotently; do not use retained proof to ACK a different/new pending intent. | Fresh LIVE tick ≤7; state + committed-ACK retry =2: ≤9. |
| Late proof result | Let actual fresh replay and owner proof execute, then a fixed host test boundary exhausts only that session's remaining time. The real readiness check must prevent starting LIVE/ACK. Pending/frontier remain unchanged; no replacement session in the attempted tick. Retain the expected deadline observation distinctly from accidental pressure/resource refusal. | Up to 5 starts through fresh LIVE owner proof, then zero starts; one separate final state: ≤6. Existing pure late tests remain useful but are not this runtime observation. |
| Prior-version remote reuse | Publish A in partition0, then unrelated B in the same partition so A's published route retains V while the registered partition advances to V+1. Publish C in partition1 with identical canonical IDs from a different source binding/owner. Actually resolve/validate A's original row and first-owner exposure, append no duplicate canonical row, preserve C's descriptor/owner and A's bytes. Track home plus one remote, bounded distinct opens, and no unrelated-partition walk. | Three one-interval historical ticks ≤18; one routed source read + one new batch proof + one fixed two-partition physical check =3: ≤21. Deduct already established A/B steps rather than duplicate them. |
| Refused reuse / reservation | Two focused negative variants: same canonical ID with changed provenance/exposure; foreign staged canonical ID. The actual first rejecting product boundary is recorded; no new canonical rows, ACK, partition retargeting or completed-frontier movement. Apply the same pattern to the required underestimated reservation/selected-path refusal, using existing pure coverage for additional combinatorics. | For each already pending variant, state/source/import prefix ≤3 plus one state comparison: ≤4. If refusal is at prepare, count that actual queue call instead; do not force an import. |
| Bounded directory recovery | Remove only derived routes in a fixed fixture fault; retained authoritative claim makes lookup unavailable, never absent. Explicit rebuild remains incomplete, blocks unqualified absence, and advances only contiguous pinned physical cursors. Exercise interruption, exact duplicate page/reconcile, stale-version refusal and completion with no source frontier/owner-gate change. Whole authority loss stays unavailable, not inferred from the directory. | For a two-page fixture: page+reconcile pairs=4 starts, plus at most eight explicit control/fault/negative/final observations=12. Each pair has its own ≤5s session; enumerate those eight operations in the frozen runner. General bound is 2P+8, P=max(1,ceil(physical_rows/32)). Verify final page limit against frozen code. |
| Explicit tail maintenance | With real admitted fragments, bootstrap one BTREE segment, append a real tail and explicitly optimize the existing index. A prospective reservation exceeding the registered/global tail allowance refuses before append. Reads never maintain. Suppress one maintenance response after commit; a separate fresh pinned read and queue reconciliation establish persistence, without blindly rebuilding or deleting retained output. | Each normal prepare→maintain→fresh directory proof→reconcile cycle=4 starts. Two cycles + one lost-response state + one final read + one refusal + one final state ≤12, plus explicitly counted setup/fill publication ticks. Do not lower/raise production tail limits for a convenient test. |

For recovery and maintenance, names/signatures and exact control counts must be checked against the final metadata implementation. A preparation-only formula is not permission for an unbounded loop. Fixture setup, all fill ticks, legacy selectors and optional fault variants remain in the eventual global start ledger; no hidden helper starts or retries.

## Existing helpers and targeted parity

- `test_sqlite_source_export.fixture` (line 561) constructs a real protected SQLite fixture in one supervised 128/192 MiB, 2s call, with no engine imported in the host. Reuse its descriptor/original data assertions and small source shape; count setup. Existing pruning modes are not a ready-made LIVE-only fixture.
- `test_native_source_export.make_fixture(...,"single")` / `fixture_call` (lines 213–235) creates real Lance/PyArrow source artifacts in the separate 5s, 512/640 MiB setup worker. `test_native_canonical_reuse_keeps_original_exposure_across_bindings` (line 550) supplies the useful two-snapshot/same-ID, different-binding assertion pattern. Its legacy flat-destination tick is not a Task3 facade proof.
- `test_migration_coordinator.ObservedSession` (line 140) already wraps actual calls and loses/stops replies after real operations. A narrow Task3 observer must additionally forward `layout_source` and `remaining`, retain original `_ready`/deadline, and record a fresh metric for each stage. Do not reuse stale `resources[-1]` when no new stage ran.
- Task2 `_fixture_worker` in `test_lance_layout_directory.py` supplies narrow rollback/lost-ACK/route-loss fault ideas. Its `_proof` is deliberately synthetic and must never enter Task3 acceptance. Its `_invoke` creates a fresh session per call, so cannot prove publication within one shared session. The sealed Task1 FixedSession/QualificationBook/DiskLedger are large-fixture-specific; reuse principles, not their frozen run/configuration.
- Keep pure protocol tests in `test_layout_coordinator.py`, `test_partitioned_exact_store.py`, `test_layout_authority.py` and resolver/source tests separate from actual native evidence. A pure success does not satisfy a missing runtime case.

Minimal unchanged legacy selectors, if these touched-path parity checks are included in the root's frozen run:

| Selector | Supervised starts |
|---|---:|
| test_lance_exact_store::test_create_append_reopen_replay_and_conflict | 6 |
| test_lance_exact_store::test_unicode_nul_chunk_pages_and_hash_binding | 5 |
| test_lance_exact_store::test_commit_with_lost_response_replays_durable_receipt | 3 |
| test_bulk_exact_store::test_visible_legacy_record_reused_without_exposure_or_kind_change | 5 |
| test_bulk_exact_store::test_migrated_ninth_live_chunk_uses_original_receipt | 3 |
| Total | 22 |

The legacy exact helper includes its old admission wait; this is separate parity setup, not permission to add a retry loop to Task3. Retain stdout/resource evidence and fail on unexpected pressure/admission/memory/deadline refusal rather than counting it as an expected conflict/unavailable case. Late-result and deliberately lost-frame cases need explicit expected reasons. All final assertions must distinguish actual writes/proofs from labels, verify unchanged original sources, and retain failures. Exact bytes/artifacts/temp/headroom, setup geometry, full call ceiling and outer duration await the actual frozen candidate; none are invented here.
