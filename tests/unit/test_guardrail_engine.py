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
