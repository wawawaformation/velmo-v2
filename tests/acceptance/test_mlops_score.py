"""Tests d'acceptance — point d'entrée CLI de l'évaluation (`velmo.mlops.score`).

Offline : agent de référence (modèle echo, garde-fous en repli regex), donc
pas d'appel Azure. `run_and_report` orchestre éval → rapport → seuil.
"""

import pytest
from conftest import build_reference_agent

from velmo.mlops import DeliveryBlocked
from velmo.mlops.score import run_and_report


def test_run_and_report_writes_report_with_signals(tmp_path):
    """run_and_report écrit un mlops/report.md contenant les 5 signaux de suivi."""
    report = tmp_path / "report.md"
    run_and_report(build_reference_agent(), report, min_score=0.0)

    text = report.read_text(encoding="utf-8").lower()
    for signal in ["memoire", "blocage", "faux positif", "latence", "cout"]:
        assert signal in text


def test_run_and_report_blocks_below_threshold(tmp_path):
    """Sous le seuil, run_and_report lève DeliveryBlocked (gate) après avoir écrit le rapport."""
    report = tmp_path / "report.md"
    # Offline, la qualité est nulle (modèle echo) → note globale ~0.65 < 0.99.
    with pytest.raises(DeliveryBlocked):
        run_and_report(build_reference_agent(), report, min_score=0.99)

    # Le rapport est écrit même quand la livraison est bloquée (pour diagnostic).
    assert report.exists()


def test_run_and_report_returns_scores_above_threshold(tmp_path):
    """Au-dessus du seuil, run_and_report ne lève pas et renvoie les notes."""
    report = tmp_path / "report.md"
    scores = run_and_report(build_reference_agent(), report, min_score=0.5)

    assert scores.global_ >= 0.5
    assert scores.block_rate > 0.0  # vrai taux de blocage remonté
