"""Tests unitaires de GuardrailEngine : refus, journalisation, non-régression PII."""

from __future__ import annotations

from velmo.guardrails import GuardrailEngine


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
