"""Tests unitaires pour les formules de scoring MLOps."""

from velmo.mlops.guardrails_scoring import score_guardrails_f1


def test_score_guardrails_f1_perfect():
    """Score F1 = 1.0 quand tous les cas sont justes."""
    # 25 cas "block" attendus, 25 réussis → rappel = 1.0
    # 12 cas "allow" attendus, 0 faux positifs → précision = 1.0
    # F1 = 2 * (1.0 * 1.0) / (1.0 + 1.0) = 1.0
    f1 = score_guardrails_f1(
        block_total=25,
        block_passed=25,
        allow_total=12,
        false_positives=0
    )
    assert f1 == 1.0


def test_score_guardrails_f1_partial():
    """Score F1 avec résultats partiels."""
    # 25 cas "block", 20 réussis → rappel = 20/25 = 0.8
    # 12 cas "allow", 2 faux positifs → précision = 1 - (2/12) = 10/12 ≈ 0.8333
    # F1 = 2 * (0.8 * 0.8333) / (0.8 + 0.8333) ≈ 0.8163
    f1 = score_guardrails_f1(
        block_total=25,
        block_passed=20,
        allow_total=12,
        false_positives=2
    )
    assert abs(f1 - 0.8163) < 0.001


def test_score_guardrails_f1_zero():
    """Score F1 = 0.0 si aucun cas block n'est réussi."""
    f1 = score_guardrails_f1(
        block_total=25,
        block_passed=0,
        allow_total=12,
        false_positives=0
    )
    assert f1 == 0.0
