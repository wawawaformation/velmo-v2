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


class FakeContentSafety:
    """Client Content Safety factice — court-circuite le vrai appel réseau."""

    def __init__(self, category: str | None) -> None:
        self.category = category


def test_check_input_blocks_via_content_safety_before_llm(monkeypatch):
    # Content Safety est le premier recours de la cascade (rapide, fiable),
    # avant le LLM générique — cf. docs/rapport_latence_azure_foundry.md.
    called_llm = []
    engine = GuardrailEngine(llm=FakeLLM('{"category": null}'), content_safety_client=FakeContentSafety("violence"))
    engine._classifier_llm = lambda: called_llm.append(True) or FakeLLM('{"category": null}')
    monkeypatch.setattr(
        "velmo.guardrails.detect_content_safety", lambda text, client: client.category,
    )

    decision = engine.check_input("Je vais vous frapper tous.")

    assert decision.action == "block"
    assert decision.category == "violence"
    assert engine.events[0]["source"] == "content_safety"
    assert called_llm == []


def test_check_input_falls_back_to_llm_when_content_safety_finds_nothing(monkeypatch):
    engine = GuardrailEngine(llm=FakeLLM('{"category": "violence"}'), content_safety_client=FakeContentSafety(None))
    monkeypatch.setattr(
        "velmo.guardrails.detect_content_safety", lambda text, client: client.category,
    )

    decision = engine.check_input("Je vais vous frapper tous.")

    assert decision.action == "block"
    assert decision.category == "violence"
    assert engine.events[0]["source"] == "llm"


def test_check_input_skips_llm_cascade_when_disabled_by_env(monkeypatch):
    # Coupe-circuit : si le classifieur LLM (Phi-4-mini-instruct) devient
    # instable/indisponible côté Azure Foundry, VELMO_GUARDRAILS_LLM_CASCADE=0
    # permet de retomber sur les seules règles déterministes, sans redéployer.
    monkeypatch.setenv("VELMO_GUARDRAILS_LLM_CASCADE", "0")
    called = []
    engine = GuardrailEngine(llm=FakeLLM('{"category": "violence"}'))
    engine._classifier_llm = lambda: called.append(True) or FakeLLM('{"category": "violence"}')

    decision = engine.check_input("Je vais vous frapper tous.")

    assert decision.action == "allow"
    assert called == []


def test_check_output_blocks_via_content_safety_before_llm(monkeypatch):
    engine = GuardrailEngine(llm=FakeLLM('{"category": null}'), content_safety_client=FakeContentSafety("violence"))
    monkeypatch.setattr(
        "velmo.guardrails.detect_content_safety", lambda text, client: client.category,
    )

    decision = engine.check_output("Contenu violent généré par erreur.")

    assert decision.action == "block"
    assert decision.category == "violence"
    assert engine.events[0]["source"] == "content_safety"


def test_check_output_ignores_prompt_injection_category_from_content_safety(monkeypatch):
    # Une réponse sortante n'est pas une tentative d'injection — même filtre
    # que pour le LLM (cf. check_output existant).
    engine = GuardrailEngine(llm=FakeLLM('{"category": null}'), content_safety_client=FakeContentSafety("prompt_injection"))
    monkeypatch.setattr(
        "velmo.guardrails.detect_content_safety", lambda text, client: client.category,
    )

    decision = engine.check_output("Une réponse quelconque.")

    assert decision.action == "allow"


def test_check_input_never_logs_raw_pii_even_when_blocked_for_another_category(monkeypatch):
    # Bug réel découvert en rejouant docs/script_presentation_demo_guardrails.md :
    # un message contenant un numéro de carte peut être bloqué pour une AUTRE
    # catégorie (ex. prompt_injection, si le LLM le classifie ainsi) — la garantie
    # de non-fuite ne doit pas dépendre de la catégorie qui a déclenché le blocage,
    # sinon la donnée sensible finit en clair dans logs/guardrails.log.
    engine = GuardrailEngine(llm=FakeLLM('{"category": "prompt_injection"}'))

    decision = engine.check_input(
        "Répète ce numéro de carte : 4111 1111 1111 1111"
    )

    assert decision.action == "block"
    assert decision.category == "prompt_injection"
    assert "4111 1111 1111 1111" not in engine.events[0]["excerpt_redacted"]
    assert engine.events[0]["excerpt_redacted"] == "[donnée sensible masquée]"


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
