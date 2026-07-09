"""Tests unitaires de la consolidation épisodique → sémantique.

Modèle retenu (skill semantic-episodic-memory) : chaque message est d'abord
capturé en épisodique (nettoyage léger, vocabulaire préservé) ; un seul appel
LLM combiné décide, en plus, si le message révèle un fait sémantique
généralisable à consolider (clé connue ou imprévisible).
"""

from __future__ import annotations

from velmo.memory.classifier import ClassificationResult
from velmo.memory.consolidation import ConsolidationResult, consolidate


class FakeLLM:
    """LLM factice renvoyant une réponse fixe (contrôlée par le test)."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str, str]] = []

    def invoke(self, system: str, context: str, message: str) -> str:
        self.calls.append((system, context, message))
        return self.response


def test_consolidate_extracts_semantic_fact_alongside_episode():
    llm = FakeLLM(
        '{"episode": "Pointure du client : 43",'
        ' "semantic": {"destination": "semantic_column", "key": "pointure", "value": "43"}}'
    )

    result = consolidate("Ma pointure de chaussure c'est du 43.", llm=llm)

    assert result == ConsolidationResult(
        episode="Pointure du client : 43",
        semantic=ClassificationResult("semantic_column", "pointure", "43"),
    )


def test_consolidate_returns_episode_only_when_no_generalizable_fact():
    llm = FakeLLM(
        '{"episode": "Client demande le statut de sa commande O-2024-0103",'
        ' "semantic": null}'
    )

    result = consolidate("Où en est ma commande O-2024-0103 ?", llm=llm)

    assert result == ConsolidationResult(
        episode="Client demande le statut de sa commande O-2024-0103",
        semantic=None,
    )


def test_consolidate_calls_llm_exactly_once():
    llm = FakeLLM('{"episode": "peu importe", "semantic": null}')

    consolidate("Un message quelconque", llm=llm)

    assert len(llm.calls) == 1


def test_consolidate_without_llm_uses_rules_for_both_episode_and_semantic():
    result = consolidate("Ma pointure de chaussure c'est du 43.", llm=None)

    assert result == ConsolidationResult(
        episode="Ma pointure de chaussure c'est du 43.",
        semantic=ClassificationResult("semantic_column", "pointure", "43"),
    )


def test_consolidate_without_llm_returns_episode_only_when_no_rule_matches():
    result = consolidate("Où en est ma commande O-2024-0103 ?", llm=None)

    assert result == ConsolidationResult(
        episode="Où en est ma commande O-2024-0103 ?",
        semantic=None,
    )


def test_consolidate_without_llm_detects_unpredictable_key_secret():
    # Le repli règles (sans LLM) doit aussi détecter les faits à clé
    # imprévisible (numéro de contrat, secret...), comme le faisait l'ancien
    # classify_and_distill — pas seulement les colonnes connues.
    result = consolidate("Mon numéro de contrat est CT-4521.", llm=None)

    assert result == ConsolidationResult(
        episode="Mon numéro de contrat est CT-4521.",
        semantic=ClassificationResult(
            "semantic_vector", "fait", "Mon numéro de contrat est CT-4521."
        ),
    )


def test_consolidate_falls_back_to_rules_when_llm_response_has_no_json():
    # Cas réel : EchoLLM (repli hors-ligne) renvoie du texte sans JSON.
    llm = FakeLLM("[velmo] J'ai bien reçu : Ma pointure de chaussure c'est du 43.")

    result = consolidate("Ma pointure de chaussure c'est du 43.", llm=llm)

    assert result == consolidate("Ma pointure de chaussure c'est du 43.", llm=None)


def test_consolidate_falls_back_to_rules_when_llm_response_is_invalid_json():
    llm = FakeLLM('{"episode": "manque une accolade fermante"')

    result = consolidate("Où en est ma commande O-2024-0103 ?", llm=llm)

    assert result == consolidate("Où en est ma commande O-2024-0103 ?", llm=None)


def test_consolidate_rejects_implausible_semantic_value():
    # Cas réel observé : une année de naissance ne doit pas être consolidée
    # comme pointure, même si le LLM la propose comme telle.
    llm = FakeLLM(
        '{"episode": "Client né le 07/09/1975",'
        ' "semantic": {"destination": "semantic_column", "key": "pointure", "value": "1975"}}'
    )

    result = consolidate("Je suis né le 07/09/1975", llm=llm)

    assert result == ConsolidationResult(
        episode="Client né le 07/09/1975",
        semantic=None,
    )
