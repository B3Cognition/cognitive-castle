# Castle Memory Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task after design review. Steps use checkbox syntax for tracking. This document does not authorize implementation or release.

**Goal:** Repair preservation, isolation, retrieval and installation defects before exposing Castle as an optional Prosaic memory provider.

**Architecture:** Keep current stores readable and public call forms compatible. Add representation-aware revisions and one explicit palace context; serialize mutation; build the provider on a generative-call-free relevance profile. Existing advanced modes remain explicit compatibility surfaces.

**Tech Stack:** Existing Python >=3.10 Castle, LanceDB/PyArrow, SQLite, sentence-transformers, pytest, Ruff and Hatchling. No new service framework or SOAR installation.

**Spec:** `../specs/2026-10-23-prosaic-memory-provider-design.md`.

## Global Constraints

- Castle remains Python >=3.10; Prosaic adapter requires Python >=3.11.
- Use `apply_patch`; preserve unrelated changes and historic evidence.
- Existing IDs, text, public call forms and stored records remain readable; metadata changes are additive/versioned.
- Unknown legacy representation/provenance stays unknown; pruning retains all original/unknown revisions and removes only explicitly derived revisions and their pointers. Selective extraction never supersedes original text.
- No automatic deletion, migration, re-embedding or model downloads on provider open.
- Mutating maintenance and every ingestion entry point share the per-palace lock.
- `memory-v1` never imports/calls SOAR, quality analysis, an LLM judge or SUE.
- Preserve existing `fast/standard/boosted/max` interfaces; physical SOAR removal is outside this plan.
- No release/push, live inference, real-palace maintenance or private transcript import without the corresponding execution authority.

## Review Focus

1. Same file imported under another wing/representation must not be skipped or pruned by the first import: H1.
2. Failures between drawer, closet and completion writes must leave old history and retry eligibility intact: H2/H3.
3. Alias paths, aged held locks and reindex interruption must not allow concurrent mutation or erase the active index: H4.
4. Missing optional dependencies or failed recall signals must not look like authoritative empty memory: H6.
5. Offset timestamps, late messages, huge metadata and legacy ambiguous paths must preserve data and fail boundedly: H3/H5/H7.

## File map and dependencies

New small modules: `cognitive_castle/revisions.py` (representation identity), `context.py` (explicit paths/handles), `reindex.py` (staging/recovery). Existing import/search modules keep orchestration rather than gaining another generic plugin framework.

H1 → H2/H3; H1 → H4; H4 → H5; H5 → H6/H7; H8 follows final dependency changes. H1 is the first independently releasable safety patch. Each task gets focused review and a scoped commit after verification; never include unrelated changes.

### H1: Stop cross-representation pruning and incorrect incremental skips

**Files:** Create `cognitive_castle/revisions.py`; modify `palace.py`, `miner.py`, `convo_miner.py`, `prune_revisions.py`; tests `test_prune_revisions.py`, `test_memory_integrity.py`, new `test_revision_identity.py`.

**Interfaces:** `RevisionIdentity(source_file: str, wing: str, representation: str)`; `revision_identity(source_file: str, metadata: dict) -> RevisionIdentity | None`; extend `file_already_mined(..., wing=None, representation=None)` without removing old arguments. New internal imports always pass the intended identity.

- [ ] Add regressions named `test_general_extraction_never_prunes_exchange`, `test_same_source_in_other_wing_is_not_skipped`, `test_same_source_in_other_representation_is_not_skipped`, `test_unknown_legacy_representation_is_preserved`. Use actual miners, 4-dimensional deterministic embeddings and real temporary LanceDB. Assert the neutral original passage and original drawer IDs survive plan/apply; assert both intended imports exist.
- [ ] Run `.venv/bin/python -m pytest tests/test_revision_identity.py tests/test_prune_revisions.py -q`; retain observed failures before editing production code.
- [ ] Implement grouping by canonical source + wing + representation. New project imports explicitly stamp `representation=project`; conversations stamp `exchange`/`general`, interpreting existing `ingest_mode=convos` + `extract_mode` when available. Prune only explicitly derived representations (`general` in this rollout); retain all original `project/exchange/diary/sweep` and unknown rows. Do not infer `project` solely from a missing field.
- [ ] Include identity in completion checks and revision policy; preserve existing recorded IDs. New revisions may add a policy-versioned identity component. No change to parser text or historical rows.
- [ ] Update old tests that expected deletion of unclassified legacy rows to assert conservative retention. Document the narrower cleanup semantics and migration diagnostic.
- [ ] Run focused tests, then the model-independent unit lane. Review the dry-run plan shape and commit `fix: preserve source representations during revision pruning`.

### H2: Make drawer and closet revision completion consistent

**Files:** `miner.py`, `palace.py`, `prune_revisions.py`, `revisions.py`; tests `test_memory_integrity.py`, `test_closets.py`, `test_prune_revisions.py`.

**Interfaces:** Add `RevisionManifest` to `revisions.py`, containing identity, revision, drawer/closet counts and sorted-ID digests, and completion state; `publish_revision(collection, closets, manifest, *, palace_path) -> None` verifies required writes and atomically persists a checksummed completion manifest under `<palace>/.castle/revisions/<identity-digest>/<revision>.json` while holding the mutation lock. Use additive metadata; no distributed-transaction claim.

- [ ] Add `test_prune_removes_derived_closets_with_derived_drawers`, `test_original_revision_keeps_drawers_and_closets`, `test_closet_failure_does_not_publish_revision`, `test_retry_after_completion_marker_failure_preserves_history`, and `test_partial_revision_is_not_provider_visible`. Use explicit derived fixtures for deletion and actual project imports for preservation. Check original bytes and pointer targets after every injected failure.
- [ ] Run `.venv/bin/python -m pytest tests/test_memory_integrity.py tests/test_closets.py tests/test_prune_revisions.py -q` and observe the relevant RED failures.
- [ ] Stamp identical representation/revision identity on drawers and closets. Publish the completion manifest only after all required writes; row-level completion hints are not authoritative for new revisions. Keep IDs deterministic so retry repairs partial state.
- [ ] Expose `completed_revision_ids(collection, identity, *, palace_path) -> frozenset[str]` for the new provider to gate visibility. Handle old last-drawer completion markers through a compatibility resolver; unknown legacy/manual rows stay readable, not falsely certified as a completed revision.
- [ ] Plan derived-only deletion across both tables before deleting any rows; remove closet references before their derived drawer targets; retain a checksummed apply plan until completion so retry is idempotent. Original source revisions are never deletion candidates in this rollout.
- [ ] Verify injected failure/retry, pointer integrity and existing closet APIs. Commit `fix: reconcile drawer and closet revision completion`.

### H3: Repair diary fidelity and sweeper idempotency

**Files:** `diary_ingest.py`, `sweeper.py`, `revisions.py`; new `tests/test_diary_revisions.py`, existing `test_sweeper.py`, `test_sweep_workflows.py`.

**Interfaces:** Diary state gains `text_sha256`, identity and completed revision; existing `ingest_diaries()` return keys remain. Extend `sweep(jsonl_path, palace_path, source_label=None, *, wing=None)` and `get_palace_cursor(collection, session_id, *, source_file=None)`; cursor becomes an optimization/diagnostic, not proof that every earlier message exists. Explicitly scoped new sweeps stamp `wing`; old unclassified records require operator mapping before provider visibility.

- [ ] Add `test_equal_length_diary_edit_creates_new_revision`, `test_diary_append_preserves_morning_and_evening_indexes`, `test_two_diary_roots_same_day_do_not_collide`, `test_diary_crash_does_not_advance_state`. Assert CRLF/Unicode/whitespace bytes and both historical versions survive.
- [ ] Add `test_second_unchanged_sweep_has_zero_embedding_calls`, `test_equal_timestamp_messages_resume_without_loss`, `test_late_message_before_cursor_is_ingested`, `test_timestamp_offsets_compare_as_instants`, `test_sweep_read_failure_does_not_rewrite_existing_rows`. Preserve original `filed_at` for identical messages.
- [ ] Run `.venv/bin/python -m pytest tests/test_diary_revisions.py tests/test_sweeper.py tests/test_sweep_workflows.py -q`; observe RED.
- [ ] Use content hashes and source-root-inclusive revision IDs for diary drawers/closets. Build closets from the complete new day revision; publish completion then atomically replace state. Keep stable historic diary IDs readable; no purge of prior source versions.
- [ ] Replace unsupported `session_id` filtering with supported source-file filtering plus paginated metadata selection (or full paginated metadata compatibility fallback when source is unspecified). No whole-table schema rewrite is needed for this repair. Batch deterministic message-ID existence/content checks; skip identical rows without embedding/upsert. Preserve changed content as a new version rather than silently overwrite it. Parse offsets for cursor reporting and never skip an unseen late ID solely by timestamp.
- [ ] Verify existing counters accurately distinguish new, unchanged and updated messages; document any additive counters. Run focused tests and commit `fix: preserve diary revisions and avoid repeated sweep writes`.

### H4: Unify mutation locking and make reindex recoverable

**Files:** `palace.py`, `prune_revisions.py`, `diary_ingest.py`, `sweeper.py`, `optimize.py`, `cli.py`, `mcp_server.py`, `kg_enricher.py` and registry writes where they are top-level mutations; create `reindex.py`; tests `test_palace_locks.py`, `test_clean_locks.py`, `test_prune_revisions.py`, new `test_reindex_recovery.py`.

**Interfaces:** Retain `mine_palace_lock(path)`; introduce internal `MutationSession` token so nested helpers validate a held lock instead of reacquiring it. `reindex_palace(palace_path, *, config, source_paths=(), cancelled=lambda: False) -> ReindexResult`; `recover_reindex(palace_path) -> ReindexResult`.

- [ ] Add two-process tests: aged held lock blocks another writer even after cleanup; symlink aliases share one lock; prune/manual import and reindex/sweep cannot run together; MCP add/update/delete cannot write into an index being replaced. `--force` may bypass a PID warning, never an active OS lock.
- [ ] Add reindex crash points before staging, before moving old index, after moving old index and after promotion. Assert one verifiable active/recoverable index, exact retained historical/manual IDs/text/metadata, and no removal of pre-existing backups. A missing source path must fail before active mutation.
- [ ] Run `.venv/bin/python -m pytest tests/test_palace_locks.py tests/test_clean_locks.py tests/test_reindex_recovery.py -q`; observe RED.
- [ ] Keep lock inodes in place: acquire/release to assess stale state and clean payload only; do not unlink a lock inode. All in-tree mutating entry points, including MCP writes and standalone enrichment/registry setup, acquire the same palace lock and pass a session token downward. Plan/apply revalidates under the held lock. Direct external backend writes remain outside this supported mutation-session contract and must be documented.
- [ ] Rebuild staged `lancedb` tables from stored records, not just current source files; re-embed at the selected identity without changing IDs/text/metadata. Leave graph, `.sue` and future bundles untouched. Optional source supplementation is a separate import after safe activation, not the mechanism for recovering history.
- [ ] Write a checksummed recovery intent before index-directory rename; retain the original index under a unique backup. Promotion/recovery verifies identity and manifests; never describe multiple renames as an atomic swap. Failures cannot print successful completion or delete the only good copy.
- [ ] Run focused process tests, full maintenance tests and review rollback evidence. Commit `fix: serialize maintenance and recover staged reindex operations`.

### H5: Introduce explicit palace paths and context

**Files:** Create `context.py`; modify `config.py`, `palace.py`, `knowledge_graph.py`, `kg_enricher.py`, `entity_registry.py`, `miner.py`, `convo_miner.py`, `diary_ingest.py`, `sweeper.py`, `searcher.py`, `mcp_server.py`; tests new `test_context_isolation.py`, existing config/MCP/graph tests.

**Interfaces:** `PalacePaths.resolve(palace_path, *, config_dir=None)` and `CastleContext.open(paths, *, config, create=False, read_only=True)` as defined in the spec; `close()`. Existing `sources.context.PalaceContext` is not renamed. Add optional `context=`/`config=` seams instead of removing old signatures.

- [ ] Add `test_custom_palace_cli_mcp_search_share_graph`, `test_sibling_palaces_do_not_share_registry`, `test_explicit_config_ignores_ambient_provider_changes`, `test_default_legacy_layout_remains_readable`, `test_ambiguous_layout_requires_migration`, `test_read_only_open_has_no_storage_mutation`. Include malicious manifests, alias paths and absent roots.
- [ ] Run `.venv/bin/python -m pytest tests/test_context_isolation.py tests/test_config.py tests/test_mcp_server.py -q`; observe RED for new context behavior.
- [ ] Resolve all root/config/graph/registry/state/lock/log paths once. New context reads cannot create/migrate tables, chmod source parents, enable SQLite WAL or rebuild FTS. Add actual read-only backend/SQLite connection paths as necessary; index mutation remains a separate operator action.
- [ ] Pass explicit config to embedding and reranking calls and key caches by model/config identity. Ensure configured CPU selection reaches query embeddings. Do not isolate tenants by changing process-global environment variables or by importing `mcp_server` into a multiuser process.
- [ ] Support recognized default legacy paths; create a read-only migration plan for ambiguous custom roots. Explicit migration copies selected graph/registries into the new private context, verifies counts/hashes, and retains legacy files. No automatic merge or irreversible move.
- [ ] Normalize actual supported LLM settings to documented `config.json` + environment + CLI precedence; remove false `castle.yaml` provider instructions. Persist explicitly selected init settings without writing keys into project YAML.
- [ ] Verify isolation using two real temporary palaces and both `--palace`/environment entry points. Commit `refactor: bind castle operations to explicit palace context`.

### H6: Repair ranking composition and add the provider relevance profile

**Files:** `searcher.py`, `reranker.py`, `embedding.py`, `soar_bridge.py`, `quality_rerank.py`, `config.py`; tests `test_pipeline_order.py`, `test_searcher.py`, `test_soar_bridge_failures.py`, new `test_memory_profile.py`.

**Interfaces:** Add `search_memories(..., context=None, config=None, profile=None)` preserving old positional/default behavior. `profile="memory-v1"` is incompatible with explicit legacy advanced-mode selection. Internal `RetrievalDiagnostics` records available/failed signals and model identities; new service surfaces a bounded projection.

- [ ] Add `test_judge_order_survives_final_serialization`, `test_unavailable_soar_does_not_resort_judged_hits`, `test_soar_keys_distinguish_chunks`, `test_memory_profile_forbids_optional_engines`, `test_all_recall_failures_are_unavailable`, `test_one_signal_failure_is_explicit_degradation`. Test composition with signed/zero/nonfinite model scores and stable ties.
- [ ] Run `.venv/bin/python -m pytest tests/test_pipeline_order.py tests/test_memory_profile.py tests/test_soar_bridge_failures.py -q`; observe RED.
- [ ] Keep `memory-v1` relevance-only: no judge, quality, SOAR or SUE; existing RRF/recency/cross-encoder only. Require finite scores; preserve raw model score identity and expose final rank separately. Do not advertise arbitrary thresholds as calibrated similarity.
- [ ] Fix legacy `max` composition by applying optional score adjustments before the final judge permutation, then serialize without sorting again. Document corrected order and retain audit fields. Failed judge retains the incoming adjusted order. No manufactured judge numeric score.
- [ ] Key legacy SOAR WMEs/tags by actual drawer ID. For legacy quality/SOAR multiplier stages, define a nonnegative rank-derived base for signed-score models, retain original relevance separately, and version/document that behavior; never apply a multiplier directly to an unverified signed score. Test neutral adjustment preserves order and positive boost cannot demote a hit.
- [ ] Replace hostname prefix heuristics in `llm_client.py` with parsed IP/local-host checks; add `test_public_hostname_prefix_is_external`. Keep externally configured endpoints explicit and do not silently fall back.
- [ ] Test original CLI/MCP mode call forms and corrected audit output; run optional-engine-forbidden tests in a subprocess. Commit `fix: compose ranking stages and add isolated memory relevance profile`.

### H7: Preserve graph evidence and source-complete retrieval

**Files:** `knowledge_graph.py`, `kg_enricher.py`, `searcher.py`, `palace.py`; tests `test_knowledge_graph.py`, `test_kg_hop.py`, `test_kg_enricher.py`, new `test_provenance.py`.

**Interfaces:** Add additive SQLite `triple_sources` table keyed by triple ID and source identity; retain `add_triple()` return type and old columns. Add `sources_for_triple(triple_id) -> list[dict]`. Repeated observations append provenance without arbitrarily changing an existing validity interval.

- [ ] Add `test_repeated_fact_retains_both_sources`, `test_distinct_queried_entities_control_kg_rank`, `test_new_temporal_claim_does_not_silently_overwrite_old_interval`, `test_search_exposes_actual_revision_and_text_digest`, `test_exact_duplicate_revisions_do_not_fill_top_k`, `test_conflicting_versions_remain_distinct`, `test_closet_topics_reference_relevant_chunks`.
- [ ] Run `.venv/bin/python -m pytest tests/test_provenance.py tests/test_knowledge_graph.py tests/test_kg_hop.py -q`; observe RED.
- [ ] Migrate graph provenance additively during explicit writable setup; preserve original triple IDs and backfill their recorded source. New repeated evidence inserts a source row. Count intersection with queried entities, not arbitrary subjects.
- [ ] Expose actual metadata/revision/digest through an additive internal rich-hit shape. Legacy serializers preserve existing fields. The new profile groups exact text hashes across completed revisions, selects newest known capture, and retains alternate source identities; different text never deduplicates merely by file/topic.
- [ ] Remove the universal first-three-drawer closet pointer shortcut. Build pointers from each relevant source span/chunk set, retaining all targets required by the indexed topic. Do not change original drawer text to make pointers convenient.
- [ ] Bound metadata projection and pagination; adversarial metadata cannot expose filesystem paths or grow provider payloads unboundedly. Verify migration retains old graph queries and commit `fix: retain memory provenance across graph and source revisions`.

### H8: Reproducible packaging and actual-pipeline qualification

**Files:** `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `README.md`, `docs/sue-scope.md`, `docs/RELEASING.md`; create `tests/test_memory_packaging.py`, `benchmarks/memory_provider_bench.py`, versioned synthetic fixtures under `tests/fixtures/memory_eval/`.

**Interfaces:** Maintain current base Castle installation compatibility and provision that worker environment separately from the Runtime-only adapter. Defer slim distribution/dependency subtraction to a separate packaging change; an extra cannot remove mandatory base dependencies. All lint entry points use exactly Ruff 0.15.12 until an explicit coordinated upgrade. Benchmark calls the actual `memory-v1` path.

- [ ] Add clean-wheel smoke assertions that source JSON/rules/licenses are present, provider imports do not initialize optional engines, and installed worker search/fetch succeeds with spaCy/SUE/SML imports actively forbidden. The worker may have legacy dependencies installed; the Runtime-only adapter environment must not contain Castle, torch or spaCy. Test core Castle imports remain compatible.
- [ ] Replace stale MemPalace/Chroma lock metadata with a lock resolved from current project metadata, align Ruff pins, and make model provisioning an explicit qualification step. Do not call a wheel build a full-dependency/live-model smoke.
- [ ] Correct SUE's three-provider documentation and byte/context claims; document generative-free provider reads and legacy advanced modes. Preserve historical benchmark evidence unchanged.
- [ ] Create a versioned 40-question corpus with 10 dev/30 held-out split frozen before tuning; include conflict, multi-source, no-answer and wrong-scope cases. Implement `recall_any`, `recall_all`, precision and correctly normalized NDCG using the full relevant set. Keep answer accuracy distinct from retrieval metrics.
- [ ] Run `.venv/bin/python -m pytest tests/ -v --ignore=tests/benchmarks`, coverage at the configured 85% threshold, `ruff check .`, `ruff format --check .`, `.venv/bin/python -m build`, and a clean installed-wheel smoke. Record provisioned model revisions, hardware, versions and exclusions. Missing mandatory qualification dependencies must fail that lane, not skip.
- [ ] Run the actual model-dependent benchmark only with provisioned weights/authorized compute; report cold/warm p50/p95, evidence completeness and context bytes. Synthetic mock runs qualify mechanics only. Review results before enabling the adapter in a consuming application.
- [ ] Commit `build: qualify reproducible castle memory provider dependencies` with exact verification evidence; release is a separate action.

## Handoff

Complete this plan before the provider release gate. A temporary read-only adapter spike may use an unshipped branch for contract tests, but cannot be called qualified while preservation/isolation gates fail. The SUE plan is independent after source bundles stabilize and must not delay the core read-only pilot.
