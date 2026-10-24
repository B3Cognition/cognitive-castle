# Bounded understanding loop: implementation verification

Date: 2026-10-23. Scope: the implementation worktree, against the
[84-case acceptance matrix](2026-10-23-understanding-loop-edge-cases.md) and
[approved design](../superpowers/specs/2026-10-23-bounded-understanding-loop-design.md).

This is a traceability record, not proof of semantic competence, factual truth,
complete archive recall, or supported-host activation. **Final combined guarded
run: 439 passed, four warnings, 11.02 seconds of pytest time.** The external guard
reported 11.4 seconds and sampled aggregate peak 341.7 MiB. The selected suites
cover the new feature plus related SUE, CLI, MCP and search-routing regressions;
this was not the repository's model-dependent full suite. Both standalone
`scripts/test_safe_brain_runner.py` checks also passed: cleanup after pytest exits
and aggregate RSS accounting for a reparented descendant. A fresh independent
read-only review reported no remaining critical or important findings in scope.

All execution uses `scripts/safe_brain_tests.py`: serialized, externally supervised,
with synthetic/temporary data and model/network denial. Native fixtures use tiny
Lance tables with supplied vectors. No live archive scan, provider/model run,
editable-package installation, MCP restart, or hook activation is part of this
verification. Preserving paused capture is an operational constraint, not a claim
that a test installed or exercised the live host.

## Evidence notation and limits

`Automated` identifies a concrete regression oracle, not universal correctness.
`Partial` identifies a narrower tested invariant and names the missing scenario.
`Host-dependent` or `Unavailable` means the implementation does not establish that
capability; a passing neighboring test must not be read as doing so. References
below use these file aliases, followed by the actual test function name:

| Alias | Test file |
| --- | --- |
| L | [test_brain_loop.py](../../tests/test_brain_loop.py) |
| E | [test_brain_engine.py](../../tests/test_brain_engine.py) |
| S | [test_brain_sources.py](../../tests/test_brain_sources.py) |
| B | [test_brain_api.py](../../tests/test_brain_api.py) |
| J | [test_bounded_json.py](../../tests/test_bounded_json.py) |
| A | [test_article_metrics.py](../../tests/test_article_metrics.py) |
| N | [test_understanding_nlp_runtime.py](../../tests/test_understanding_nlp_runtime.py) |
| Q | [test_quality_rerank.py](../../tests/test_quality_rerank.py) |

Native source capability is **macOS only**, for explicitly bounded Arrow
`castle_brain_format=fixed-v1` records and an already existing FTS index for recall.
Ordinary variable-width legacy drawers are **unavailable before payload
materialization**. Nothing implicitly migrates or replaces the palace schema.
The reader admits a private snapshot of at most 64 MiB/512 entries; source text and
provenance have separate 64/8 KiB aggregate limits. Linux/Windows native supervision
is unavailable until its failure behavior is actually validated there. Inline
sources remain usable independently of native recall.

The 512-MiB aggregate RSS check, 10-second native deadline, and macOS memory-pressure
checks are sampled tripwires, not prevention of every transient allocation or a
whole-machine memory ceiling. Tests cover owned-process failure on the current
platform; they do not establish guarantees for arbitrary native code, unsupported
filesystems, kernel stalls, or simultaneous failure of both supervisors.

Session-bound recall is charged to the existing root before native access.
Standalone recall has only per-call limits, because there is no root to charge.
The host must bind subsequent workflow recall to its session. Exact original-problem
hashes prevent obtaining a fresh root budget for the identical task, including
after restart; semantic paraphrases and a caller's assertion of new user
authorization are not independently verified.

## Epistemic and scope cases

| ID | Coverage | Concrete evidence and remaining limit |
| --- | --- | --- |
| E01 | Automated | L.`test_two_questions_do_not_close_via_engine_addresses`; L.`test_explicit_item_disposition_closes_one_question_only`. Turn references cannot close both controller items. |
| E02 | Partial | L.`test_changed_claim_reopens_individually_answered_dependency` covers claim revision. A live-source replacement affecting a previously closed item is not separately raced against extraction; frozen sources and successors remain the supported boundary. |
| E03 | Automated | L.`test_missing_map_rejects_revision_and_never_drops_obligation`; L.`test_successor_freezes_original_request_and_keeps_original_spans`; L.`test_unrepresented_request_remains_visible_despite_resolved_engine`. Completeness of the host's initial obligation interpretation is still unverified. |
| E04 | Partial / semantic verification unavailable | L.`test_full_represented_request_resolves_with_explicit_limits` requires `independent_checks=not_performed`. The engine accepts attributed arguments; a dedicated opposite-claim/negation-stripping regression is not present. Exact quotation is not entailment. |
| E05 | Partial / host-dependent | L.`test_original_request_is_a_citable_source_with_other_evidence` covers source-map inclusion; L.`test_begin_returns_action_and_restart_pages` checks unverified independence. Relevance of an inferred premise to a cited line is not independently judged. |
| E06 | Partial | L.`test_original_request_is_a_citable_source_with_other_evidence` exercises typed source mapping. Generated separators/metadata are not source text, but an explicit `approved=true` metadata-as-assent negative fixture is not present. |
| E07 | Host-dependent | No authority/supersession adjudicator or newer-brainstorm-versus-approved-policy semantic test is claimed. Provenance remains attributed; the host must retain and identify the ambiguity rather than infer newest-wins authority. |
| E08 | Host-dependent | No automatic entity/time/scope reconciliation capability is claimed. Exact source text and provenance can be retained, but distinguishing tenants or effective periods requires host interpretation and evidence. |
| E09 | Partial | L.`test_begin_returns_action_and_restart_pages` checks `caller_attributed`; B.`test_strict_problem_schema_rejects_before_effect` rejects caller policy fields. A forged URL/user-role label is not authenticated by the controller; a dedicated forgery fixture is not present. |
| E10 | Host-dependent, bounded output tested | L.`test_full_represented_request_resolves_with_explicit_limits` retains unperformed independent checks after RESOLVED. Root cause, performance diagnosis, and empirical truth verification are unavailable from this examination alone. |
| E11 | Partial | E.`test_reducer_matches_unchanged_vendor` includes silence/UNKNOWN for all lenses. Separate UNKNOWN-context citations without answer support are not directly exercised by a controller fixture. |
| E12 | Partial | L.`test_successor_freezes_original_request_and_keeps_original_spans` covers inherited scope; the controller adds a source-exclusion issue when parent hashes disappear. A direct eight-source counterevidence-omission fixture is not present; relevance/completeness remains host-dependent. |
| E13 | Independence capability unavailable | L.`test_begin_returns_action_and_restart_pages` and L.`test_full_represented_request_resolves_with_explicit_limits` keep independent checks unperformed. Repeated sources/lenses are not independent corroboration; no semantic independence estimator is supplied. |
| E14 | Host-dependent | E.`test_reducer_matches_unchanged_vendor` preserves raw terminal outcomes. There is no controller operation that turns a user override into epistemic resolution; prototype-only authorization and its downstream scope remain the host's responsibility. |
| E15 | Partial | S.`test_native_bounded_read_preserves_exact_bytes_and_snapshot`; A.`test_excerpt_identity_and_provenance_do_not_imply_whole_article`; L.`test_many_quoted_unicode_pages_fit_actual_mcp_envelope`. Combining forms, CRLF, emoji, and exact hashes are covered across fixtures; overlapping controller excerpts are not separately tested. |
| E16 | Partial | L.`test_successor_keeps_obligations_and_slots_correction_invalidates` checks stale advisory and no next action after correction. The same lifecycle guard applies to historical outcomes, but a dedicated correction-after-RESOLVED trace is not present. |

## Transactions, lifecycle, and budgets

| ID | Coverage | Concrete evidence and remaining limit |
| --- | --- | --- |
| T01 | Automated | L.`test_two_concurrent_responses_commit_exactly_one` synchronizes competing responses and checks one accepted turn. |
| T02 | Automated | L.`test_process_crash_exposes_complete_old_or_new_state` covers retry after commit; L.`test_trusted_wire_fingerprint_replays_without_resnapshotting`; B.`test_archive_begin_exact_wire_retry_never_reopens_changed_or_missing_archive` covers archive-ID wire retry. Final combined run must include the latter regressions. |
| T03 | Automated | L.`test_same_request_different_payload_conflicts_without_turn`; L.`test_trusted_wire_fingerprint_replays_without_resnapshotting` checks changed-fingerprint conflict. |
| T04 | Automated invariant | L.`test_idempotent_invalid_replay_then_second_invalid_stops` checks one semantic rejection on replay; L.`test_automatic_budget_cannot_be_bypassed_by_false_flag` checks the separate request cap. No 100-retry load benchmark is claimed. |
| T05 | Automated | L.`test_idempotent_invalid_replay_then_second_invalid_stops` checks that a valid third submission cannot reactivate the terminated examination. |
| T06 | Automated | L.`test_successor_race_reserves_only_one_slot` checks a synchronized successor race and the exhausted second slot. |
| T07 | Partial | L.`test_same_exact_task_cannot_mint_new_root_budget_after_restart` checks identical-problem hash reuse and retained slots. Rephrased tasks and authenticity of a purported new user task are not verified. |
| T08 | Partial | L.`test_process_crash_exposes_complete_old_or_new_state` injects process exit at receipt and after-commit boundaries; L.`test_ledger_invalid_submission_leaves_no_partial_artifacts` checks rollback. This is not crash/power-loss injection at every SQLite/filesystem boundary. |
| T09 | Partial | L.`test_busy_and_corrupt_storage_are_fail_closed`; L.`test_storage_commit_failure_never_acknowledges_success` injects a disk-full-like commit error. Actual disk exhaustion, read-only mounts, and failing fsync devices are not exercised. |
| T10 | Partial | L.`test_cancel_response_race_never_reactivates_cancelled_session` races cancel against a response and rejects later activity. The raced response is not specifically the final resolving turn. |
| T11 | Automated | L.`test_successor_keeps_obligations_and_slots_correction_invalidates` preserves correction invalidation after both examination slots are consumed. |
| T12 | Automated clock/restart simulation | L.`test_expiry_and_backward_clock_resume_retains_budgets`; L.`test_begin_returns_action_and_restart_pages`. Physical laptop suspend and filesystem recovery are not live-tested. |
| T13 | Automated | L.`test_version_change_allows_bounded_inspection_but_no_response`; L.`test_incompatible_engine_cannot_regenerate_historical_prompt`. Incompatible engines cannot generate a fresh historical question/schema. |
| T14 | Automated | L.`test_busy_and_corrupt_storage_are_fail_closed`; L.`test_missing_committed_event_is_corrupt_not_ready`. |
| T15 | Partial | E.`test_invalid_reducer_does_not_mutate_input` and parameterized E.`test_reducer_matches_unchanged_vendor` exercise independent pure states. There is no two-evidence-session, every-operator interleaving fixture. |
| T16 | Automated | L.`test_begin_returns_action_and_restart_pages`; B.`test_resume_from_status_and_pages`; B.`test_cursor_passes_unchanged_through_host_api`. Resume uses persisted snapshots and references. |
| T17 | Partial | E.`test_reducer_matches_unchanged_vendor` covers revision and exhaustion scenarios against the vendor; L.`test_prospective_artifact_exhaustion_stops_before_accepting` checks bounded stop. A revision immediately before the 14-turn boundary is not separately scripted. |
| T18 | Automated component invariants | L.`test_idempotent_invalid_replay_then_second_invalid_stops`; L.`test_two_concurrent_responses_commit_exactly_one`; J.`test_bounded_syntax_error_does_not_corrupt_next_frame`. Structural transport failures do not dispatch semantic responses. |
| T19 | Automated | L.`test_replay_after_cancel_is_current_and_content_free`; L.`test_revocation_and_purge_block_all_source_bearing_pages`; L.`test_old_page_cursor_cannot_cross_revision_or_exposure_epoch`; L.`test_trusted_wire_replay_uses_current_revocation_cancel_and_purge`. |
| T20 | Partial | Transactional snapshot construction is implemented; L.`test_cancel_response_race_never_reactivates_cancelled_session` tests related serialization. No deterministic pause between status root/session reads is injected, so that exact race oracle remains outstanding. |
| T21 | Automated with explicit standalone limit | L.`test_automatic_budget_cannot_be_bypassed_by_false_flag`; L.`test_trusted_inspection_still_works_after_automatic_cap`; B.`test_scoped_recall_counts_root_budget_before_native_access`. Standalone pre-begin recall has no root budget; the host must bind in-loop recall to its session. |

## Resource, storage-read, and transport cases

| ID | Coverage | Concrete evidence and remaining limit |
| --- | --- | --- |
| R01 | Automated bounded path | Guarded suites deny real model imports/network. S.`test_public_capabilities_import_without_native_or_models`, S.`test_native_fts_recall_uses_existing_index`, N.`test_explicit_opt_out_reaches_parser_semantics_and_entities`, and B.`test_mcp_strict_dispatch_and_actual_envelope` exercise the distinct model-free path. No full live-host/model evaluation is claimed. |
| R02 | Automated | S.`test_missing_palace_never_created`; S.`test_legacy_native_table_rejected_without_archive_mutation`; S.`test_missing_fts_explicitly_unavailable_and_no_index_created` fingerprint the synthetic archive before/after. |
| R03 | Automated; legacy unavailable | S.`test_size_admission_precedes_native_payload_projection` uses a fake boundary to reject giant text/metadata before payload projection; S.`test_legacy_native_table_rejected_without_archive_mutation` exercises actual unsupported Lance storage. |
| R04 | Partial | S.`test_version_change_aborts_before_payload_projection` injects a version change at the native boundary; S.`test_native_bounded_read_preserves_exact_bytes_and_snapshot` checks a real pinned version/hash. A concurrent real Lance writer during snapshot copying is not exercised. |
| R05 | Automated | S.`test_missing_fts_explicitly_unavailable_and_no_index_created`; S.`test_native_fts_recall_uses_existing_index`. B.`test_resume_from_status_and_pages` starts from inline/no archive evidence. |
| R06 | Automated | J.`test_actual_encoded_envelope_is_bounded`; L.`test_many_quoted_unicode_pages_fit_actual_mcp_envelope`; B.`test_large_rpc_id_cannot_bypass_strict_error_wire_limit`. Bounds cover the actual double-encoded MCP envelope. |
| R07 | Automated | J.`test_duplicate_keys_nonfinite_and_surrogate_are_rejected`; J.`test_depth_and_bytes_are_checked_even_for_unknown_fields`; L.`test_native_json_bounds_reject_aggregate_before_serializing`; L.`test_native_json_bounds_reject_cycles_and_shared_graph_expansion`. |
| R08 | Automated | J.`test_frames_do_not_execute_oversized_tail_as_another_request`; B.`test_actual_mcp_loop_recovers_syntax_error_and_closes_invalid_tail`. Framing failures close the stream; bounded syntax errors can recover. |
| R09 | Partial | L.`test_prospective_artifact_exhaustion_stops_before_accepting`; L.`test_collection_excess_stops_instead_of_silently_dropping_issues`. Logical quotas/reserve are exercised, but not a complete 14-turn trace with every legal payload/issue at maximum size. |
| R10 | Partial | B.`test_cursor_passes_unchanged_through_host_api`; L.`test_many_quoted_unicode_pages_fit_actual_mcp_envelope` test lossless pages and envelope sizes. An oversized generated REVISE question is not a dedicated fixture. |
| R11 | Partial | L.`test_committed_receipts_contain_no_response_or_source_text`; L.`test_idempotent_invalid_replay_then_second_invalid_stops` cover content-free receipts/rejection idempotency. Repeated maximum-size private invalid bodies are not a dedicated stress fixture. |
| R12 | Automated on macOS | S.`test_memory_tripwire_kills_owned_reader`; S.`test_reparented_reader_descendant_remains_in_aggregate_rss`; S.`test_reader_deadline_stops_owned_descendants`; S.`test_system_pressure_prevents_reader_spawn`; S.`test_system_pressure_stops_running_reader`. Pressure is faked, not induced; sampled checks cannot prevent every transient peak. |
| R13 | Automated admission invariant | S.`test_admission_is_per_user_not_per_tmpdir`; S.`test_guardian_death_kills_reader_before_admission_released`; S.`test_host_death_kills_reader_and_releases_inherited_lock`. The lock is independent of palace/TMPDIR and inherited through actual reader exit. |
| R14 | Automated bounds | S.`test_invalid_recall_is_rejected_before_worker`; S.`test_reader_deadline_stops_owned_descendants`; A.`test_maximum_unbroken_unicode_input_has_bounded_result`; A.`test_isolated_compute_deadline_reaps_its_worker`. This is not exhaustive hostile-input fuzzing. |
| R15 | Partial | L.`test_prospective_artifact_exhaustion_stops_before_accepting`; L.`test_storage_commit_failure_never_acknowledges_success`; L.`test_trusted_inspection_still_works_after_automatic_cap`. Actual low-free-space reserve activation and cancellation on a physically full disk are not tested. |
| R16 | Partial | B.`test_capability_and_denied_recall_have_no_storage_side_effect`; B.`test_missing_protocol_and_coerced_page_rejected`; J.`test_actual_encoded_envelope_is_bounded`. No live older-client compatibility matrix is claimed. |
| R17 | Automated | A.`test_standalone_input_rejected_before_worker_admission`; A.`test_standalone_provenance_rejects_cycles_and_excessive_depth`; A.`test_maximum_unbroken_unicode_input_has_bounded_result`; A.`test_isolated_compute_deadline_reaps_its_worker`. |
| R18 | Automated on macOS; other platforms unavailable | S.`test_guardian_death_kills_reader_before_admission_released`; S.`test_host_death_kills_reader_and_releases_inherited_lock`; S.`test_unsupported_platform_does_not_start_worker`. Tests cover single-supervisor death, ownership, bounded cleanup, and retained admission. |
| R19 | Automated | J.`test_partial_frame_has_receive_deadline`; J.`test_threaded_pipe_fallback_has_the_same_deadline_and_frame_bounds`; S.`test_partial_guardian_frame_has_first_byte_deadline`. |

## Article and optional NLP cases

| ID | Coverage | Concrete evidence and remaining limit |
| --- | --- | --- |
| A01 | Automated | A.`test_article_keeps_surrounding_prose_and_reports_only_measurements`; A.`test_nested_list_prose_is_not_mistaken_for_indented_code`. |
| A02 | Automated fixture | A.`test_decimal_abbreviation_url_and_unicode_boundaries` compares exact sentence/word sequences. This is a declared deterministic tokenizer, not a language-universal parser. |
| A03 | Automated fixture | A.`test_markdown_extraction_policy_distinguishes_excluded_content`; A.`test_reference_links_keep_labels_and_exclude_destinations` compare exact prose and exclusions. |
| A04 | Automated | A.`test_nonprose_is_not_an_invented_zero_quality_article` covers empty, whitespace, both fence forms, and table-only inputs. |
| A05 | Automated applicability | A.`test_english_formulas_need_declared_applicable_language`; A.`test_unknown_language_has_no_syllable_work_or_grade_estimate`. Language is declared, not automatically certified. |
| A06 | Automated boundary | A.`test_smog_minimum_analyzed_sentences` compares 29 and 30 English sentences. |
| A07 | Automated | A.`test_excerpt_identity_and_provenance_do_not_imply_whole_article` preserves supplied revision/range provenance, exact hash, and incomplete scope. Origin/range assertions are not authenticated. |
| A08 | Automated | Q.`test_untyped_drawers_do_not_even_import_analyzers`; Q.`test_mixed_profiles_only_explicit_requirements_receive_existing_boost`. |
| A09 | Automated | Q.`test_requirement_profile_is_available_after_prior_assessment`; Q.`test_explicit_profile_reads_lancedb_metadata_json`; Q.`test_mixed_profiles_only_explicit_requirements_receive_existing_boost`. |
| A10 | Automated limits, calibration unavailable | A.`test_article_keeps_surrounding_prose_and_reports_only_measurements` checks null aggregate and boost 1.0. Article truth/completeness and a calibrated quality aggregate are not provided. |
| A11 | Automated with fake optional pipeline | N.`test_parser_and_consumers_import_without_optional_model`; N.`test_explicit_opt_out_reaches_parser_semantics_and_entities`; N.`test_concurrent_consumers_share_one_complete_pipeline`. No real NLP model is loaded. |
| A12 | Automated with fake missing model | N.`test_missing_model_cached_until_explicit_reset` checks failure caching and explicit reset. Actual model installation/download is deliberately not performed. |
| A13 | Automated selected boundaries | A.`test_decimal_abbreviation_url_and_unicode_boundaries`; A.`test_excerpt_identity_and_provenance_do_not_imply_whole_article`; A.`test_maximum_unbroken_unicode_input_has_bounded_result`. Counts are descriptive; these fixtures do not validate every language. |

## Host, disclosure, and rollout cases

| ID | Coverage | Concrete evidence and remaining limit |
| --- | --- | --- |
| H01 | Automated | B.`test_capability_and_denied_recall_have_no_storage_side_effect`; B.`test_archive_bind_checks_current_policy_and_has_exact_snapshots`; L.`test_revocation_and_purge_block_all_source_bearing_pages`. Unknown/cloud hosts receive no implicit locality grant. |
| H02 | Automated | L.`test_selected_grant_does_not_authorize_successor_expansion`; B.`test_recall_filters_grants_and_bounds_preview`. A selected content-hash grant does not become broad archive permission. |
| H03 | Partial / host-dependent | B.`test_strict_problem_schema_rejects_before_effect` rejects caller policy/control fields; controller outputs use allowlisted actions. No comprehensive hostile-evidence prompt-injection fixture or immunity claim for the active host model is supplied. |
| H04 | Partial | L.`test_symlink_store_fails_without_touching_target`; S.`test_symbolic_archive_path_rejected`; L.`test_old_page_cursor_cannot_cross_revision_or_exposure_epoch`; B.`test_policy_is_local_private_and_reloaded`. SQL/path/cross-session fuzzing is not exhaustive. |
| H05 | Automated protocol gate, host-dependent participation | B.`test_strict_problem_schema_rejects_before_effect`; B.`test_missing_protocol_and_coerced_page_rejected`. A stale/absent skill that never calls the tools cannot be detected by those tools. |
| H06 | Live activation unavailable in this work | B.`test_cli_roundtrip_uses_same_strict_api` and B.`test_mcp_strict_dispatch_and_actual_envelope` exercise this checkout with temporary data. They do not inventory or switch the installed CLI/editable package/running MCP process. |
| H07 | Operational constraint | Guarded synthetic tests and no install/hook/provider/archive commands preserve the intended rollout boundary. No test claims to activate paused capture; final live-path/pause inventory is an operator check, not inferred from unit success. |
| H08 | Automated fields, host-dependent reporting | L.`test_begin_returns_action_and_restart_pages`; L.`test_full_represented_request_resolves_with_explicit_limits` retain unperformed independent checks. Host-assisted answers remain structured self-examination, never second-model verification. |
| H09 | Host-dependent frequency; direct action tested | L.`test_begin_returns_action_and_restart_pages` checks the immediate next operator; B.`test_resume_from_status_and_pages` covers resumption. Skill instructions skip trivial work, but host compliance is not enforced or live-evaluated. |
| H10 | Automated deterministic parity | E.`test_reducer_matches_unchanged_vendor` compares all nine lenses × success/silence/partial/revision/exhaustion, including raw turns, terminal and coverage. Answers are scripted; controller issue-ledger strictness has separate L tests. |
| H11 | Automated logical controller purge | L.`test_revocation_and_purge_block_all_source_bearing_pages`; L.`test_purge_problem_hash_prevents_reintroduction_as_a_new_root`; L.`test_trusted_wire_replay_uses_current_revocation_cancel_and_purge`. This covers the controller's derived records, not forensic erasure of original archives/backups. |
| H12 | Live freshness unavailable; safe historical boundary | S.`test_unknown_source_is_not_substituted`; L.`test_begin_returns_action_and_restart_pages` retains frozen sources. No live pruning monitor is supplied: availability/currentness remains unknown rather than inferred from a stored hash. |
| H13 | Partial / host ordering required | L.`test_successor_keeps_obligations_and_slots_correction_invalidates` checks known correction invalidation. The host must record a newly received correction before advancing; the runtime cannot detect a correction it has not received. |
| H14 | Host-dependent / activation unverified | B.`test_capability_and_denied_recall_have_no_storage_side_effect` checks discovery output only. Missing tools or ignored skills remain unsupported/inactive host integration, not a behavioral guarantee from installation. |
| H15 | Automated participating-client gate | B.`test_missing_protocol_and_coerced_page_rejected`; B.`test_strict_problem_schema_rejects_before_effect`. Missing/unknown/mistyped protocol versions fail before mutation; absent participation remains a host limitation. |

## Review findings represented by fixes

These regressions identify the implemented correction; the final combined run above
must include them before recording a final green result.

| Finding | Correction and regression evidence |
| --- | --- |
| Unsupported withdrawal could erase a substantive issue | Reject unsupported `withdrawn_premise` dispositions; L.`test_withdrawn_premise_cannot_erase_a_question_without_evidence`. Claim changes reopen disposed dependencies in L.`test_changed_claim_reopens_individually_answered_dependency`. |
| A new request ID could reset an identical task's root budget | Reuse the original exact-problem root across restart; L.`test_same_exact_task_cannot_mint_new_root_budget_after_restart`. Paraphrase equivalence is explicitly unverified. |
| Incompatible pins could generate a new historical prompt | Fail closed for generated question/schema pages; L.`test_incompatible_engine_cannot_regenerate_historical_prompt`. |
| Article worker spawn could execute host top-level code again | Launch the dedicated worker without rerunning the host entry point; A.`test_article_worker_never_reexecutes_host_top_level`. |
| Aggregate direct inputs were serialized before total admission | Cumulative prospective byte accounting rejects large alias expansion/cycles before serialization; L.`test_native_json_bounds_reject_aggregate_before_serializing`; L.`test_native_json_bounds_reject_cycles_and_shared_graph_expansion`. |
| Oversized JSON-RPC IDs bypassed strict error output bounds | Reject/bound IDs before dispatch; B.`test_large_rpc_id_cannot_bypass_strict_error_wire_limit`. |
| In-loop recall bypassed the root request counter | Charge session-bound recall before source access; B.`test_scoped_recall_counts_root_budget_before_native_access`. Standalone calls remain per-call only. |
| Reparented native children disappeared from RSS accounting | Sample the retained owned process group rather than only current ancestry; S.`test_reparented_reader_descendant_remains_in_aggregate_rss` reproduces the old deadline-only stop with a small test allocation. S.`test_process_group_scan_does_not_treat_kernel_pid_zero_as_own_group` excludes the macOS PID0 sentinel. |
| Exact archive-ID retries reopened changed/missing live sources | Bind replay to a trusted wire fingerprint and regenerate the current disclosure-safe controller envelope without rereading archive data; B.`test_archive_begin_exact_wire_retry_never_reopens_changed_or_missing_archive`; L.`test_trusted_wire_replay_uses_current_revocation_cancel_and_purge`; L.`test_concurrent_same_wire_fingerprint_commits_one_snapshot`. |
| A successor could ignore a correction or retain it after purge | Exact correction records become citable inherited issues/obligations and immediate purge dependencies; L.`test_successor_carries_exact_correction_and_cannot_ignore_it`; L.`test_correction_is_a_purge_dependency_before_a_successor_exists`; L.`test_correction_issue_resolution_must_cite_its_exact_correction`. |
| Equal text could authorize different confidential source metadata | Grants bind canonical ID/text/provenance; L.`test_exposure_grant_binds_source_identity_and_metadata`; B.`test_same_text_with_different_private_provenance_is_not_granted`. |
| Missing store tables or version pins were silently rebuilt | Existing store schema is validated before initialization; L.`test_existing_store_missing_schema_or_pins_is_not_reinitialized`. |
| Spent or repeatedly failed archive begins escaped request accounting | Preflight rejects spent known roots before native work; failed admitted attempts charge once; B.`test_spent_root_begin_never_materializes_archive_before_budget_check`; B.`test_failed_archive_successor_attempts_count_once_and_stop`; L.`test_successor_rechecks_admission_after_preflight`. |
| A passing test runner could leave descendants outside supervision | Retain leader identity until group cleanup and count reparented group members; both real subprocess checks in `scripts/test_safe_brain_runner.py` pass. |

The partial and host-dependent rows remain limits of the evidence. None is a claim
that an assistant's interpretation, citations, obligation selection, authority
assessment, or proposed next action has been independently proven correct.
