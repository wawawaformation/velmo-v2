"""Tests d'acceptance — évaluation des garde-fous MLOps."""

from conftest import build_reference_agent, build_degraded_agent
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
