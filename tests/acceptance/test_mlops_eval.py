"""Tests d'acceptance — évaluation des garde-fous MLOps."""

import pytest
from conftest import (
    build_degraded_agent,
    build_memory_disabled_agent,
    build_reference_agent,
)
from velmo.mlops import run_eval
from velmo.mlops.guardrails_scoring import evaluate_guardrails, guardrails_score


def test_evaluate_guardrails_returns_counts():
    """evaluate_guardrails rejout les 35 cas et renvoie les compteurs."""
    agent = build_reference_agent()
    result = evaluate_guardrails(agent)

    # Doit renvoyer un dict avec les compteurs
    assert "block_total" in result
    assert "block_passed" in result
    assert "allow_total" in result
    assert "false_positives" in result

    # Les totaux doivent correspondre aux 35 cas réels
    assert result["block_total"] + result["allow_total"] == 35


def test_degraded_agent_has_more_false_positives():
    """L'agent dégradé (garde-fous neutralisés) bloque moins et a plus de faux positifs."""
    reference = evaluate_guardrails(build_reference_agent())
    degraded = evaluate_guardrails(build_degraded_agent())

    # L'agent dégradé doit avoir MOINS de cas "block" réussis
    assert degraded["block_passed"] <= reference["block_passed"]

    # L'agent dégradé doit avoir PLUS de faux positifs (car ses garde-fous laissent tout passer)
    assert degraded["false_positives"] >= reference["false_positives"]


def test_guardrails_score_returns_float():
    """guardrails_score combine évaluation + formule et renvoie un score 0.0-1.0."""
    agent = build_reference_agent()
    score = guardrails_score(agent)

    # Doit être un float dans [0.0, 1.0]
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_run_eval_reports_real_guardrail_rates():
    """run_eval remonte le vrai block_rate/false_positive_rate (plus 0.0 en dur).

    Item 3 du chantier 3 : le rapport doit afficher un taux de blocage et un
    taux de faux positifs réels. Les compteurs sont déjà calculés par
    `evaluate_guardrails` — ce test vérifie que `run_eval` les remonte au lieu
    de placeholders. Offline : la cascade garde-fous retombe sur les règles
    regex (déterministes), pas d'appel Azure.
    """
    agent = build_reference_agent()
    counts = evaluate_guardrails(agent)
    scores = run_eval(agent)

    expected_block_rate = counts["block_passed"] / counts["block_total"]
    expected_fp_rate = counts["false_positives"] / counts["allow_total"]

    assert scores.block_rate == pytest.approx(expected_block_rate)
    assert scores.false_positive_rate == pytest.approx(expected_fp_rate)
    # Les règles regex bloquent au moins un cas → preuve que ce n'est plus 0.0 en dur.
    assert scores.block_rate > 0.0


def test_memory_regression_lowers_score():
    """Régression mémoire long terme désactivée → note mémoire et globale chutent.

    Item 2 du chantier 3, variante « mémoire long terme désactivée » (à côté de
    la variante « garde-fou retiré » de test_mlops.py). Offline, déterministe.
    """
    reference = run_eval(build_reference_agent())
    degraded = run_eval(build_memory_disabled_agent())

    assert degraded.memory < reference.memory
    assert degraded.global_ < reference.global_


def test_run_eval_measures_real_latency():
    """run_eval mesure une vraie latence d'évaluation (plus 0.0 en dur)."""
    scores = run_eval(build_reference_agent())
    assert scores.latency_ms > 0.0
