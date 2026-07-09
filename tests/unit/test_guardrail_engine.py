"""Tests unitaires de GuardrailEngine : refus, journalisation, non-régression PII."""

from __future__ import annotations

from velmo.guardrails import GuardrailEngine


class FakeLLM:
    """LLM factice renvoyant une réponse fixe (contrôlée par le test)."""

    def __init__(self, response: str) -> None:
        self.response = response

    def invoke(self, system: str, context: str, message: str) -> str:
        return self.response


def test_check_input_blocks_and_logs_hate_speech():
    engine = GuardrailEngine()
    decision = engine.check_input("Sale race, retournez dans votre pays avec vos maillots.")

    assert decision.action == "block"
    assert decision.category == "hate"
    assert decision.refusal
    assert len(engine.events) == 1
    assert engine.events[0]["stage"] == "input"
    assert engine.events[0]["category"] == "hate"
    assert engine.events[0]["action"] == "block"


def test_check_input_allows_legitimate_message_without_logging():
    engine = GuardrailEngine()
    decision = engine.check_input("Quel est le statut de ma commande O-2024-0101 ?")

    assert decision.action == "allow"
    assert engine.events == []


def test_check_output_redacts_never_logs_raw_secret():
    engine = GuardrailEngine()
    decision = engine.check_output("Le paiement est passe avec la carte 4111 1111 1111 1111.")

    assert decision.action == "block"
    assert decision.category == "pii"
    assert "4111 1111 1111 1111" not in str(engine.events[0])


def test_check_output_short_password_near_start_never_logged_verbatim():
    # Un secret court en tout début de message survivrait à une troncature à 40
    # caractères : on vérifie qu'il n'apparaît jamais, même partiellement.
    engine = GuardrailEngine()
    decision = engine.check_output("Le mot de passe est abc.")

    assert decision.action == "block"
    assert decision.category == "pii"
    assert "abc" not in engine.events[0]["excerpt_redacted"]
    assert engine.events[0]["excerpt_redacted"] == "[donnée sensible masquée]"


def test_check_input_short_secret_leak_near_start_never_logged_verbatim():
    engine = GuardrailEngine()
    decision = engine.check_input("Cle API xyz789 exposee sur le depot public.")

    assert decision.action == "block"
    assert decision.category == "secret_leak"
    assert "xyz789" not in engine.events[0]["excerpt_redacted"]
    assert engine.events[0]["excerpt_redacted"] == "[donnée sensible masquée]"


def test_check_input_blocks_via_llm_cascade_when_rules_miss_reformulation():
    # Cas réel documenté (docs/checklist_test_manuel_garde_fous.md) : une
    # reformulation qui échappe aux règles regex (moderation.py) doit quand
    # même être bloquée grâce au second recours LLM.
    engine = GuardrailEngine(llm=FakeLLM('{"category": "violence"}'))
    decision = engine.check_input("Je vais vous frapper tous.")

    assert decision.action == "block"
    assert decision.category == "violence"
    assert decision.refusal
    assert len(engine.events) == 1
    assert engine.events[0]["category"] == "violence"
    assert engine.events[0]["source"] == "llm"


def test_check_input_blocked_by_rules_logs_source_regex():
    engine = GuardrailEngine()
    engine.check_input("Sale race, retournez dans votre pays avec vos maillots.")

    assert engine.events[0]["source"] == "regex"


def test_check_input_llm_cascade_not_triggered_when_rules_already_matched():
    # Si les règles ont déjà détecté, le LLM n'est jamais consulté (défense
    # en profondeur en cascade : rapide d'abord).
    engine = GuardrailEngine(llm=FakeLLM('{"category": null}'))
    decision = engine.check_input("Sale race, retournez dans votre pays avec vos maillots.")

    assert decision.action == "block"
    assert decision.category == "hate"


def test_check_output_blocks_out_of_scope_drift():
    # synthese.md : le hors-périmètre doit être contrôlé en entrée ET en
    # sortie — le LLM peut dériver spontanément vers un sujet hors périmètre
    # (valorisation, conseil juridique...) même si la demande était légitime.
    engine = GuardrailEngine()
    decision = engine.check_output("Votre maillot vaut environ 300€ à la revente sur le marché collector.")

    assert decision.action == "block"
    assert decision.category == "out_of_scope"
    assert decision.refusal
    assert len(engine.events) == 1
    assert engine.events[0]["stage"] == "output"
    assert engine.events[0]["category"] == "out_of_scope"
