"""Tests d'acceptance — chantier Évaluation & MLOps."""

from __future__ import annotations

import pytest
from conftest import build_degraded_agent, build_reference_agent

from velmo.mlops import (
    DeliveryBlocked,
    current_version,
    enforce_threshold,
    run_eval,
    write_report,
)

# L'évaluation MLOps mesure le vrai agent (LLM Azure réel), pas un modèle scripté :
# un faux modèle ne peut ni raisonner ni appeler les outils, donc la note qualité
# n'aurait aucun sens. Skip automatique hors CI si les identifiants sont absents.
pytestmark = pytest.mark.real_llm


def test_scores_produced_and_versioned(real_model):
    # Critère : note globale + notes mémoire / garde-fous / qualité, versionnées.
    scores = run_eval(build_reference_agent(model=real_model))
    assert scores.global_ is not None and 0.0 <= scores.global_ <= 1.0
    assert scores.memory is not None
    assert scores.guardrails is not None
    assert scores.quality is not None
    assert current_version()


def test_regression_blocks_delivery(real_model):
    # Critère : une régression fait chuter la note et bloque la livraison.
    good = run_eval(build_reference_agent(model=real_model))
    degraded = run_eval(build_degraded_agent(model=real_model))

    assert degraded.global_ < good.global_
    enforce_threshold(good, 0.8)  # ne doit pas lever
    with pytest.raises(DeliveryBlocked):
        enforce_threshold(degraded, 0.8)


def test_report_contains_signals(tmp_path, real_model):
    # Critère : note mémoire, taux de blocage, taux de faux positifs, latence, coût visibles.
    scores = run_eval(build_reference_agent(model=real_model))
    report = tmp_path / "report.md"
    write_report(scores, report)

    text = report.read_text(encoding="utf-8").lower()
    for signal in ["memoire", "blocage", "faux positif", "latence", "cout"]:
        assert signal in text
