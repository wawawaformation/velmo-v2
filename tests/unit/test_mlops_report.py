"""Tests unitaires de `write_report` — honnêteté du signal coût.

`cost` est codé en dur à `0.0` dans `run_eval` (pas de suivi de tokens tant que
Langfuse n'est pas branché, cf. docs/CHANGELOG.md). Afficher « $0.00 » laisse
croire à une vraie mesure ; le rapport doit dire explicitement que le coût
n'est pas mesuré, pas afficher un montant qui ressemble à un résultat.
"""

from __future__ import annotations

from velmo.mlops import Scores, write_report


def _scores(**overrides) -> Scores:
    base = dict(
        memory=1.0,
        guardrails=1.0,
        quality=1.0,
        global_=1.0,
        block_rate=1.0,
        false_positive_rate=0.0,
        latency_ms=100.0,
        cost=0.0,
    )
    base.update(overrides)
    return Scores(**base)


def test_report_states_cost_is_not_measured_instead_of_a_dollar_amount(tmp_path):
    report = tmp_path / "report.md"
    write_report(_scores(), report)

    text = report.read_text(encoding="utf-8").lower()
    assert "cout" in text
    assert "$0.00" not in text
    assert "non mesure" in text
