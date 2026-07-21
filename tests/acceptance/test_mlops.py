"""Tests d'acceptance — chantier Évaluation & MLOps."""

from __future__ import annotations

import openai
import pytest
from conftest import build_degraded_agent, build_reference_agent

from velmo.mlops import (
    DeliveryBlocked,
    current_version,
    enforce_threshold,
    run_eval,
    write_report,
)
from velmo.mlops.manifest import load_manifest

# L'évaluation MLOps mesure le vrai agent (LLM Azure réel), pas un modèle scripté :
# un faux modèle ne peut ni raisonner ni appeler les outils, donc la note qualité
# n'aurait aucun sens. Skip automatique hors CI si les identifiants sont absents.
pytestmark = pytest.mark.real_llm


def _run_eval_or_skip(agent):
    """Exécute `run_eval` ; skip sur incident infra Azure (429/timeout/5xx).

    Le benchmark `docs/rapport_latence_azure_foundry.md` a mesuré que ces échecs
    sont côté déploiement Azure Foundry, hors de notre code (instabilité
    intermittente). Un incident infra n'est donc PAS une régression qualité : on
    skip plutôt que de bloquer le gate (convention repo : infra indisponible →
    skip). Une vraie régression (l'agent répond, mais mal) fait toujours échouer.
    """
    try:
        return run_eval(agent)
    except openai.APIError as exc:  # RateLimitError, APITimeoutError, APIConnectionError…
        pytest.skip(f"Incident infra Azure (non déterministe, hors régression) : {exc}")


def test_scores_produced_and_versioned(real_model):
    # Critère : note globale + notes mémoire / garde-fous / qualité, versionnées.
    scores = _run_eval_or_skip(build_reference_agent(model=real_model))
    assert scores.global_ is not None and 0.0 <= scores.global_ <= 1.0
    assert scores.memory is not None
    assert scores.guardrails is not None
    assert scores.quality is not None
    assert current_version()


def test_regression_blocks_delivery(real_model):
    # Critère : une régression fait chuter la note et bloque la livraison.
    good = _run_eval_or_skip(build_reference_agent(model=real_model))
    degraded = _run_eval_or_skip(build_degraded_agent(model=real_model))

    # Seuil lu dans le manifeste : coder 0.8 en dur ici laissait les tests
    # valider contre l'ancienne valeur quand le seuil était ajusté ailleurs.
    threshold = load_manifest().threshold

    assert degraded.global_ < good.global_
    enforce_threshold(good, threshold)  # ne doit pas lever
    with pytest.raises(DeliveryBlocked):
        enforce_threshold(degraded, threshold)


def test_report_contains_signals(tmp_path, real_model):
    # Critère : note mémoire, taux de blocage, taux de faux positifs, latence, coût visibles.
    scores = _run_eval_or_skip(build_reference_agent(model=real_model))
    report = tmp_path / "report.md"
    write_report(scores, report)

    text = report.read_text(encoding="utf-8").lower()
    for signal in ["memoire", "blocage", "faux positif", "latence", "cout"]:
        assert signal in text
