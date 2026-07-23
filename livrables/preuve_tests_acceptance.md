# Preuve d'exécution des tests d'acceptance

Deux sources, complémentaires :

1. **Suite hors-ligne complète** (unitaire + acceptance, déterministe) — sortie
   intégrale capturée ci-dessous, exécutée localement le 2026-07-23.
2. **Suite d'acceptance contre le vrai agent Azure** (`pytest.mark.real_llm`,
   `tests/acceptance/test_mlops.py`) — exécutée par la CI GitHub Actions, run
   qui a validé le merge vers `main` (commit `6665153`).

Commit de référence : `6665153`.

---

## 1. Suite hors-ligne (unitaire + acceptance)

```
195 passed, 3 deselected, 1 warning in 162.56s (0:02:42)
```

Les 3 tests désélectionnés sont les tests `real_llm` (voir section 2) —
volontairement exclus de cette suite hors-ligne pour rester rapides et
déterministes (aucun appel réseau).

Sortie complète (`pytest -v -m "not real_llm"`) :

```text
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-8.4.2, pluggy-1.6.0 -- /media/david/projets/formation_dev_ia_agentique/lab/velmo2/velmo-v2/.venv/bin/python
cachedir: .pytest_cache
rootdir: /media/david/projets/formation_dev_ia_agentique/lab/velmo2/velmo-v2
configfile: pyproject.toml
testpaths: tests
plugins: langsmith-0.9.7, cov-6.3.0, anyio-4.14.1
collecting ... collected 198 items / 3 deselected / 195 selected

tests/acceptance/test_agent_graph.py::test_simple_greeting_returns_scripted_reply_and_runs_memory_guardrails PASSED [  0%]
tests/acceptance/test_agent_graph.py::test_tool_call_executes_against_real_db PASSED [  1%]
tests/acceptance/test_agent_graph.py::test_respond_logs_latency_for_the_chat_model PASSED [  1%]
tests/acceptance/test_agent_graph.py::test_blocked_input_never_invokes_the_model PASSED [  2%]
tests/acceptance/test_api.py::test_post_messages_returns_agent_reply PASSED [  2%]
tests/acceptance/test_api.py::test_post_messages_reports_positive_latency PASSED [  3%]
tests/acceptance/test_api.py::test_post_messages_runs_tool_call_against_real_db PASSED [  3%]
tests/acceptance/test_api.py::test_post_messages_reports_null_guardrail_category_when_allowed PASSED [  4%]
tests/acceptance/test_api.py::test_post_messages_reports_guardrail_category_when_blocked PASSED [  4%]
tests/acceptance/test_api.py::test_post_messages_rejects_missing_fields PASSED [  5%]
tests/acceptance/test_api.py::test_get_users_lists_customers_from_db PASSED [  5%]
tests/acceptance/test_business.py::test_cannot_modify_shipped_order PASSED [  6%]
tests/acceptance/test_business.py::test_can_modify_unshipped_order PASSED [  6%]
tests/acceptance/test_business.py::test_refund_above_cap_escalates PASSED [  7%]
tests/acceptance/test_business.py::test_refund_below_cap_is_auto PASSED  [  7%]
tests/acceptance/test_business.py::test_isolation_other_customer_order PASSED [  8%]
tests/acceptance/test_business.py::test_no_fabulation_when_out_of_stock PASSED [  8%]
tests/acceptance/test_business.py::test_escalation_recorded_on_shipped_modification PASSED [  9%]
tests/acceptance/test_guardrails.py::test_blocks_hate_violence_sexual PASSED [  9%]
tests/acceptance/test_guardrails.py::test_resists_prompt_injection PASSED [ 10%]
tests/acceptance/test_guardrails.py::test_output_pii_is_blocked PASSED   [ 10%]
tests/acceptance/test_guardrails.py::test_out_of_scope_valuation_refused PASSED [ 11%]
tests/acceptance/test_guardrails.py::test_legitimate_messages_not_blocked PASSED [ 11%]
tests/acceptance/test_memory.py::test_recall_over_30_turns PASSED        [ 12%]
tests/acceptance/test_memory.py::test_cross_session_persistence PASSED   [ 12%]
tests/acceptance/test_memory.py::test_isolation_between_customers PASSED [ 13%]
tests/acceptance/test_memory.py::test_right_to_be_forgotten PASSED       [ 13%]
tests/acceptance/test_memory.py::test_forget_removes_consolidated_episode_even_without_text_match PASSED [ 14%]
tests/acceptance/test_memory.py::test_agent_injects_memory_context_into_llm_fallback PASSED [ 14%]
tests/acceptance/test_memory.py::test_agent_forgets_on_user_request PASSED [ 15%]
tests/acceptance/test_mlops_eval.py::test_evaluate_guardrails_returns_counts PASSED [ 15%]
tests/acceptance/test_mlops_eval.py::test_degraded_agent_has_more_false_positives PASSED [ 16%]
tests/acceptance/test_mlops_eval.py::test_guardrails_score_returns_float PASSED [ 16%]
tests/acceptance/test_mlops_eval.py::test_run_eval_reports_real_guardrail_rates PASSED [ 17%]
tests/acceptance/test_mlops_eval.py::test_memory_regression_lowers_score PASSED [ 17%]
tests/acceptance/test_mlops_eval.py::test_run_eval_measures_real_latency PASSED [ 18%]
tests/acceptance/test_mlops_score.py::test_run_and_report_writes_report_with_signals PASSED [ 18%]
tests/acceptance/test_mlops_score.py::test_run_and_report_blocks_below_threshold PASSED [ 19%]
tests/acceptance/test_mlops_score.py::test_run_and_report_returns_scores_above_threshold PASSED [ 20%]
tests/unit/test_catalog_stock.py::test_check_stock_is_case_insensitive[om-1993] PASSED [ 20%]
tests/unit/test_catalog_stock.py::test_check_stock_is_case_insensitive[OM-1993] PASSED [ 21%]
tests/unit/test_catalog_stock.py::test_check_stock_is_case_insensitive[Om-1993] PASSED [ 21%]
tests/unit/test_catalog_stock.py::test_check_stock_is_case_insensitive[ om-1993 ] PASSED [ 22%]
tests/unit/test_catalog_stock.py::test_check_stock_still_reports_unknown_product PASSED [ 22%]
tests/unit/test_catalog_stock.py::test_check_stock_reports_out_of_stock_size PASSED [ 23%]
tests/unit/test_chroma_embedding.py::test_call_passes_show_progress_bar_false_to_encode PASSED [ 23%]
tests/unit/test_chroma_telemetry.py::test_no_op_product_telemetry_module_imports_without_raising PASSED [ 24%]
tests/unit/test_classifier.py::test_classify_extracts_multiple_facts_from_llm_response PASSED [ 24%]
tests/unit/test_classifier.py::test_classify_falls_back_to_rules_on_invalid_json PASSED [ 25%]
tests/unit/test_classifier.py::test_classify_parses_json_surrounded_by_extra_text PASSED [ 25%]
tests/unit/test_classifier.py::test_classify_without_llm_returns_list_of_single_rule_result PASSED [ 26%]
tests/unit/test_classifier.py::test_classify_without_llm_returns_empty_list_when_no_rule_matches PASSED [ 26%]
tests/unit/test_classifier.py::test_classify_sends_system_prompt_describing_json_schema_and_known_keys PASSED [ 27%]
tests/unit/test_classifier.py::test_classify_ignores_single_invalid_item_but_keeps_valid_ones PASSED [ 27%]
tests/unit/test_classifier.py::test_classify_rejects_implausible_pointure_value PASSED [ 28%]
tests/unit/test_classifier.py::test_classify_accepts_plausible_pointure_values PASSED [ 28%]
tests/unit/test_classifier.py::test_classify_rejects_implausible_segment_value PASSED [ 29%]
tests/unit/test_classifier.py::test_classify_accepts_plausible_segment_values PASSED [ 29%]
tests/unit/test_classifier.py::test_classify_rejects_implausible_tutoiement_value PASSED [ 30%]
tests/unit/test_classifier.py::test_classify_accepts_plausible_tutoiement_values PASSED [ 30%]
tests/unit/test_classifier.py::test_classify_rejects_implausible_canal_contact_value PASSED [ 31%]
tests/unit/test_classifier.py::test_classify_accepts_plausible_canal_contact_values PASSED [ 31%]
tests/unit/test_classifier.py::test_classify_rejects_implausible_langue_value PASSED [ 32%]
tests/unit/test_classifier.py::test_classify_accepts_plausible_langue_values PASSED [ 32%]
tests/unit/test_cli_read_line.py::test_read_line_decodes_valid_utf8 PASSED [ 33%]
tests/unit/test_cli_read_line.py::test_read_line_replaces_invalid_utf8_bytes_instead_of_raising PASSED [ 33%]
tests/unit/test_cli_read_line.py::test_read_line_returns_none_on_eof PASSED [ 34%]
tests/unit/test_cli_safe_respond.py::test_safe_respond_returns_agent_answer_on_success PASSED [ 34%]
tests/unit/test_cli_safe_respond.py::test_safe_respond_returns_fallback_message_on_exception_instead_of_raising PASSED [ 35%]
tests/unit/test_cli_safe_respond.py::test_safe_respond_does_not_propagate_exception PASSED [ 35%]
tests/unit/test_cli_safe_respond.py::test_safe_respond_captures_message_in_memory_on_exception PASSED [ 36%]
tests/unit/test_cli_safe_respond.py::test_safe_respond_does_not_double_write_on_success PASSED [ 36%]
tests/unit/test_consolidation.py::test_consolidate_extracts_semantic_fact_alongside_episode PASSED [ 37%]
tests/unit/test_consolidation.py::test_consolidate_returns_episode_only_when_no_generalizable_fact PASSED [ 37%]
tests/unit/test_consolidation.py::test_consolidate_calls_llm_exactly_once PASSED [ 38%]
tests/unit/test_consolidation.py::test_consolidate_without_llm_uses_rules_for_both_episode_and_semantic PASSED [ 38%]
tests/unit/test_consolidation.py::test_consolidate_without_llm_returns_episode_only_when_no_rule_matches PASSED [ 39%]
tests/unit/test_consolidation.py::test_consolidate_without_llm_detects_unpredictable_key_secret PASSED [ 40%]
tests/unit/test_consolidation.py::test_consolidate_falls_back_to_rules_when_llm_response_has_no_json PASSED [ 40%]
tests/unit/test_consolidation.py::test_consolidate_falls_back_to_rules_when_llm_response_is_invalid_json PASSED [ 41%]
tests/unit/test_consolidation.py::test_consolidate_falls_back_to_rules_when_episode_is_null PASSED [ 41%]
tests/unit/test_consolidation.py::test_consolidate_falls_back_to_rules_when_episode_key_is_missing PASSED [ 42%]
tests/unit/test_consolidation.py::test_consolidate_falls_back_to_rules_when_episode_is_empty_string PASSED [ 42%]
tests/unit/test_consolidation.py::test_consolidate_rejects_implausible_semantic_value PASSED [ 43%]
tests/unit/test_content_safety.py::test_detect_content_safety_blocks_when_severity_meets_threshold PASSED [ 43%]
tests/unit/test_content_safety.py::test_detect_content_safety_maps_self_harm_category PASSED [ 44%]
tests/unit/test_content_safety.py::test_detect_content_safety_allows_when_severity_below_threshold PASSED [ 44%]
tests/unit/test_content_safety.py::test_detect_content_safety_detects_prompt_injection_via_shield PASSED [ 45%]
tests/unit/test_content_safety.py::test_detect_content_safety_allows_legitimate_message PASSED [ 45%]
tests/unit/test_content_safety.py::test_detect_content_safety_returns_none_on_network_error PASSED [ 46%]
tests/unit/test_content_safety.py::test_content_safety_client_sends_correct_headers_and_urls PASSED [ 46%]
tests/unit/test_episode_vector_store.py::test_search_ranks_episodes_by_token_overlap PASSED [ 47%]
tests/unit/test_episode_vector_store.py::test_search_is_isolated_per_user PASSED [ 47%]
tests/unit/test_episode_vector_store.py::test_search_excludes_consolidated_episodes_by_default PASSED [ 48%]
tests/unit/test_episode_vector_store.py::test_get_episode_store_logs_warning_when_falling_back_to_local PASSED [ 48%]
tests/unit/test_episodic.py::test_add_episode_without_consolidation_is_listed_by_default PASSED [ 49%]
tests/unit/test_episodic.py::test_add_episode_with_consolidated_key_is_excluded_by_default PASSED [ 49%]
tests/unit/test_episodic.py::test_add_episode_with_consolidated_key_is_included_with_flag PASSED [ 50%]
tests/unit/test_episodic.py::test_search_episodes_excludes_consolidated_by_default PASSED [ 50%]
tests/unit/test_episodic.py::test_delete_by_consolidated_key_removes_only_matching_episode PASSED [ 51%]
tests/unit/test_guardrail_engine.py::test_check_input_blocks_and_logs_hate_speech PASSED [ 51%]
tests/unit/test_guardrail_engine.py::test_check_input_self_harm_redirects_to_help_resource PASSED [ 52%]
tests/unit/test_guardrail_engine.py::test_check_input_refusal_names_the_detected_category PASSED [ 52%]
tests/unit/test_guardrail_engine.py::test_check_input_refusal_names_out_of_scope_category PASSED [ 53%]
tests/unit/test_guardrail_engine.py::test_check_input_refusal_names_prompt_injection_category PASSED [ 53%]
tests/unit/test_guardrail_engine.py::test_check_input_allows_legitimate_message_without_logging PASSED [ 54%]
tests/unit/test_guardrail_engine.py::test_check_output_redacts_never_logs_raw_secret PASSED [ 54%]
tests/unit/test_guardrail_engine.py::test_check_output_short_password_near_start_never_logged_verbatim PASSED [ 55%]
tests/unit/test_guardrail_engine.py::test_check_input_short_secret_leak_near_start_never_logged_verbatim PASSED [ 55%]
tests/unit/test_guardrail_engine.py::test_check_input_blocks_via_llm_cascade_when_rules_miss_reformulation PASSED [ 56%]
tests/unit/test_guardrail_engine.py::test_check_input_blocked_by_rules_logs_source_regex PASSED [ 56%]
tests/unit/test_guardrail_engine.py::test_check_input_llm_cascade_not_triggered_when_rules_already_matched PASSED [ 57%]
tests/unit/test_guardrail_engine.py::test_check_input_blocks_via_content_safety_before_llm PASSED [ 57%]
tests/unit/test_guardrail_engine.py::test_check_input_falls_back_to_llm_when_content_safety_finds_nothing PASSED [ 58%]
tests/unit/test_guardrail_engine.py::test_check_input_skips_llm_cascade_when_disabled_by_env PASSED [ 58%]
tests/unit/test_guardrail_engine.py::test_check_output_blocks_via_content_safety_before_llm PASSED [ 59%]
tests/unit/test_guardrail_engine.py::test_check_output_ignores_prompt_injection_category_from_content_safety PASSED [ 60%]
tests/unit/test_guardrail_engine.py::test_check_input_never_logs_raw_pii_even_when_blocked_for_another_category PASSED [ 60%]
tests/unit/test_guardrail_engine.py::test_check_output_blocks_out_of_scope_drift PASSED [ 61%]
tests/unit/test_guardrail_middleware.py::test_before_agent_short_circuits_on_blocked_input PASSED [ 61%]
tests/unit/test_guardrail_middleware.py::test_before_agent_allows_legitimate_input PASSED [ 62%]
tests/unit/test_guardrail_middleware.py::test_after_agent_replaces_blocked_output PASSED [ 62%]
tests/unit/test_guardrail_middleware.py::test_after_agent_allows_legitimate_output PASSED [ 63%]
tests/unit/test_guardrail_middleware.py::test_after_agent_does_not_reverify_a_refusal_from_before_agent PASSED [ 63%]
tests/unit/test_guardrail_middleware.py::test_blocked_input_is_logged_in_engine_events PASSED [ 64%]
tests/unit/test_guardrails_moderation.py::test_detects_hate_speech PASSED [ 64%]
tests/unit/test_guardrails_moderation.py::test_detects_violence PASSED   [ 65%]
tests/unit/test_guardrails_moderation.py::test_detects_self_harm PASSED  [ 65%]
tests/unit/test_guardrails_moderation.py::test_detects_sexual_content PASSED [ 66%]
tests/unit/test_guardrails_moderation.py::test_allows_legitimate_messages PASSED [ 66%]
tests/unit/test_guardrails_moderation_llm.py::test_detects_hate_category_from_llm_response PASSED [ 67%]
tests/unit/test_guardrails_moderation_llm.py::test_detects_violence_category_from_llm_response PASSED [ 67%]
tests/unit/test_guardrails_moderation_llm.py::test_detects_self_harm_category_from_llm_response PASSED [ 68%]
tests/unit/test_guardrails_moderation_llm.py::test_returns_none_when_llm_says_none PASSED [ 68%]
tests/unit/test_guardrails_moderation_llm.py::test_returns_none_when_llm_response_has_no_json PASSED [ 69%]
tests/unit/test_guardrails_moderation_llm.py::test_returns_none_when_llm_response_is_invalid_json PASSED [ 69%]
tests/unit/test_guardrails_moderation_llm.py::test_returns_none_when_category_is_not_a_known_category PASSED [ 70%]
tests/unit/test_guardrails_moderation_llm.py::test_calls_llm_exactly_once PASSED [ 70%]
tests/unit/test_guardrails_pii.py::test_detects_card_number PASSED       [ 71%]
tests/unit/test_guardrails_pii.py::test_detects_password PASSED          [ 71%]
tests/unit/test_guardrails_pii.py::test_detects_iban PASSED              [ 72%]
tests/unit/test_guardrails_pii.py::test_detects_secret_leak PASSED       [ 72%]
tests/unit/test_guardrails_pii.py::test_allows_legitimate_output PASSED  [ 73%]
tests/unit/test_guardrails_pii.py::test_card_regex_does_not_match_ungrouped_reference_numbers PASSED [ 73%]
tests/unit/test_guardrails_pii.py::test_iban_regex_does_not_match_non_country_alnum_codes PASSED [ 74%]
tests/unit/test_guardrails_prompt_injection.py::test_detects_prompt_injection PASSED [ 74%]
tests/unit/test_guardrails_prompt_injection.py::test_allows_legitimate_messages PASSED [ 75%]
tests/unit/test_guardrails_scope.py::test_detects_out_of_scope PASSED    [ 75%]
tests/unit/test_guardrails_scope.py::test_allows_legitimate_messages PASSED [ 76%]
tests/unit/test_kb_store.py::test_get_kb_uses_silent_embedding_function PASSED [ 76%]
tests/unit/test_latency_callback.py::test_on_llm_end_logs_latency_after_chat_model_start PASSED [ 77%]
tests/unit/test_latency_callback.py::test_on_llm_end_without_matching_start_does_not_crash PASSED [ 77%]
tests/unit/test_latency_callback.py::test_tracks_independent_runs_separately PASSED [ 78%]
tests/unit/test_llm.py::test_get_chat_model_returns_none_without_azure_credentials PASSED [ 78%]
tests/unit/test_llm.py::test_get_chat_model_returns_azure_chat_model_when_configured PASSED [ 79%]
tests/unit/test_llm.py::test_get_chat_model_sets_temperature_when_requested PASSED [ 80%]
tests/unit/test_llm.py::test_get_classifier_llm_disables_automatic_retries PASSED [ 80%]
tests/unit/test_llm_latency.py::test_invoke_logs_latency_with_model_name PASSED [ 81%]
tests/unit/test_llm_latency.py::test_invoke_logs_latency_as_numeric_milliseconds PASSED [ 81%]
tests/unit/test_memory_manager.py::test_read_queries_episode_vector_store PASSED [ 82%]
tests/unit/test_memory_manager.py::test_close_closes_the_underlying_session PASSED [ 82%]
tests/unit/test_memory_manager.py::test_preload_facts_returns_known_and_vector_facts PASSED [ 83%]
tests/unit/test_memory_middleware.py::test_before_agent_caches_rendered_memory_context PASSED [ 83%]
tests/unit/test_memory_middleware.py::test_wrap_model_call_injects_cached_context_into_system_prompt PASSED [ 84%]
tests/unit/test_memory_middleware.py::test_after_agent_writes_turn_to_memory PASSED [ 84%]
tests/unit/test_mlops_manifest.py::test_load_manifest_reads_version_threshold_and_weights PASSED [ 85%]
tests/unit/test_mlops_manifest.py::test_load_manifest_reads_prompt_versions PASSED [ 85%]
tests/unit/test_mlops_manifest.py::test_load_manifest_rejects_missing_prompt_version PASSED [ 86%]
tests/unit/test_mlops_manifest.py::test_load_manifest_rejects_weights_not_summing_to_one PASSED [ 86%]
tests/unit/test_mlops_manifest.py::test_load_manifest_rejects_threshold_out_of_range PASSED [ 87%]
tests/unit/test_mlops_manifest.py::test_load_manifest_rejects_missing_suite_weight PASSED [ 87%]
tests/unit/test_mlops_manifest.py::test_shipped_manifest_is_valid PASSED [ 88%]
tests/unit/test_mlops_prompts.py::test_fingerprint_is_stable_for_identical_text PASSED [ 88%]
tests/unit/test_mlops_prompts.py::test_fingerprint_changes_when_text_changes PASSED [ 89%]
tests/unit/test_mlops_prompts.py::test_prompt_fingerprints_covers_the_four_prompts PASSED [ 89%]
tests/unit/test_mlops_scoring.py::test_score_guardrails_f1_perfect PASSED [ 90%]
tests/unit/test_mlops_scoring.py::test_score_guardrails_f1_partial PASSED [ 90%]
tests/unit/test_mlops_scoring.py::test_score_guardrails_f1_zero PASSED   [ 91%]
tests/unit/test_processor.py::test_process_pending_always_creates_an_episode PASSED [ 91%]
tests/unit/test_processor.py::test_process_pending_consolidates_semantic_fact_alongside_episode PASSED [ 92%]
tests/unit/test_processor.py::test_process_pending_marks_consolidated_episode_with_its_key PASSED [ 92%]
tests/unit/test_processor.py::test_process_pending_clears_buffer_after_processing PASSED [ 93%]
tests/unit/test_processor.py::test_process_pending_episode_is_searchable_via_episode_vector_store PASSED [ 93%]
tests/unit/test_processor.py::test_process_pending_isolates_failures_between_messages PASSED [ 94%]
tests/unit/test_processor.py::test_process_pending_links_episode_to_semantic_by_key_not_text_match PASSED [ 94%]
tests/unit/test_tool_binding.py::test_bound_tools_returns_a_list_of_tools PASSED [ 95%]
tests/unit/test_tool_binding.py::test_get_order_schema_does_not_expose_user_id_or_session PASSED [ 95%]
tests/unit/test_tool_binding.py::test_get_order_tool_returns_same_result_as_direct_call PASSED [ 96%]
tests/unit/test_tool_binding.py::test_get_order_tool_enforces_isolation_for_other_owners_order PASSED [ 96%]
tests/unit/test_tool_binding.py::test_escalate_to_human_is_not_exposed PASSED [ 97%]
tests/unit/test_tools_memory.py::test_forget_matches_natural_language_target PASSED [ 97%]
tests/unit/test_tools_memory.py::test_forget_reports_not_found_instead_of_false_success PASSED [ 98%]
tests/unit/test_tools_memory.py::test_forget_expands_even_when_literal_match_is_partial PASSED [ 98%]
tests/unit/test_tools_memory.py::test_forget_literal_target_still_works PASSED [ 99%]
tests/unit/test_vector_store.py::test_get_fact_store_logs_warning_when_falling_back_to_local PASSED [100%]

=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/fastapi/testclient.py:1
  /media/david/projets/formation_dev_ia_agentique/lab/velmo2/velmo-v2/.venv/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========== 195 passed, 3 deselected, 1 warning in 162.56s (0:02:42) ===========
```

---

## 2. Suite d'acceptance contre le vrai agent (Azure)

Exécutée en CI (job `lint-and-unit`, étape `Test suite (pytest)`), sur le run
qui a validé le merge de `dev` vers `main` :

- **Run** : https://github.com/wawawaformation/velmo-v2/actions/runs/29906194048
- **Commit** : `f35d640` (merge de `6665153` vers `main`)

Résultat (les 3 critères Gherkin du chantier 3) :

```
tests/acceptance/test_mlops.py::test_scores_produced_and_versioned PASSED
tests/acceptance/test_mlops.py::test_regression_blocks_delivery PASSED
tests/acceptance/test_mlops.py::test_report_contains_signals PASSED
```

Note globale produite par cette exécution (voir aussi
[`report.md`](report.md)) :

```
Eval MLOps v2.0.0 | global=100.00% memoire=100.00% garde-fous=100.00% qualite=100.00%
```

Le gate a par ailleurs été observé bloquant **en conditions réelles** lors
d'un run antérieur (base de données non peuplée → note à 0.70 → `CI` en
échec) — voir `docs/CHANGELOG.md` pour le détail de cet incident.
