"""Tests unitaires du classifieur de modération LLM (Phi-4-mini-instruct).

Repli en cascade : les règles déterministes (moderation.py, prompt_injection.py)
restent le premier filtre, rapide et hors-ligne. Ce classifieur LLM n'intervient
qu'en second recours, pour attraper les reformulations qui échappent aux motifs
(ex. "Je vais vous frapper tous.", limite connue documentée dans
docs/checklist_test_manuel_garde_fous.md).
"""

from __future__ import annotations

from velmo.guardrails.moderation_llm import detect_moderation_llm


class FakeLLM:
    """LLM factice renvoyant une réponse fixe (contrôlée par le test)."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str, str]] = []

    def invoke(self, system: str, context: str, message: str) -> str:
        self.calls.append((system, context, message))
        return self.response


def test_detects_hate_category_from_llm_response():
    llm = FakeLLM('{"category": "hate"}')

    result = detect_moderation_llm("Je vais vous frapper tous.", llm=llm)

    assert result == "hate"


def test_detects_violence_category_from_llm_response():
    llm = FakeLLM('{"category": "violence"}')

    result = detect_moderation_llm("Je vais vous frapper tous.", llm=llm)

    assert result == "violence"


def test_returns_none_when_llm_says_none():
    llm = FakeLLM('{"category": null}')

    result = detect_moderation_llm("Quel est le statut de ma commande ?", llm=llm)

    assert result is None


def test_returns_none_when_llm_response_has_no_json():
    # Cas réel : EchoLLM (repli hors-ligne, sans identifiants Azure) renvoie
    # du texte sans JSON — ne doit jamais produire un faux "block".
    llm = FakeLLM("[velmo] J'ai bien reçu : test")

    result = detect_moderation_llm("Quel est le statut de ma commande ?", llm=llm)

    assert result is None


def test_returns_none_when_llm_response_is_invalid_json():
    llm = FakeLLM('{"category": "hate"')

    result = detect_moderation_llm("test", llm=llm)

    assert result is None


def test_returns_none_when_category_is_not_a_known_category():
    llm = FakeLLM('{"category": "spam"}')

    result = detect_moderation_llm("test", llm=llm)

    assert result is None


def test_calls_llm_exactly_once():
    llm = FakeLLM('{"category": null}')

    detect_moderation_llm("un message quelconque", llm=llm)

    assert len(llm.calls) == 1
