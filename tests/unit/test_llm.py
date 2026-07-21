"""Tests unitaires de `get_chat_model` — le vrai `BaseChatModel` Azure pour l'agent.

Distinct de `get_llm()`/`get_classifier_llm()` (repli `EchoLLM`, contrat
`.invoke(system, context, message)`) : `create_agent()` exige un vrai
`BaseChatModel` (tool-calling natif), pas le Protocol `LLM` historique.
"""

from __future__ import annotations

from velmo.llm import get_chat_model, get_classifier_llm


def test_get_chat_model_returns_none_without_azure_credentials(monkeypatch):
    monkeypatch.delenv("AZURE_AI_INFERENCE_ENDPOINT", raising=False)

    assert get_chat_model() is None


def test_get_chat_model_returns_azure_chat_model_when_configured(monkeypatch):
    monkeypatch.setenv("AZURE_AI_INFERENCE_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_AI_INFERENCE_API_KEY", "fake-key")
    monkeypatch.setenv("AZURE_AI_INFERENCE_MODEL", "Kimi-K2.6")

    from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

    model = get_chat_model()

    assert isinstance(model, AzureAIOpenAIApiChatModel)


def test_get_chat_model_sets_temperature_when_requested(monkeypatch):
    # `conception/LMOPS/chantier3-reponses.md` (Réponse 2) retient
    # `temperature=0` en évaluation, et écarte le rejeu 3-5× des cas
    # *parce que* la température est à 0. Sans ça, la note varie d'un run à
    # l'autre sans changement de code (observé : qualité 0.875 → 0.750 → 0.625)
    # et le gate CI peut basculer sur du bruit.
    monkeypatch.setenv("AZURE_AI_INFERENCE_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_AI_INFERENCE_API_KEY", "fake-key")
    monkeypatch.setenv("AZURE_AI_INFERENCE_MODEL", "gpt-5.4")

    assert get_chat_model(temperature=0).temperature == 0
    # Sans argument, on ne force rien (production inchangée).
    assert get_chat_model().temperature is None


def test_get_classifier_llm_disables_automatic_retries(monkeypatch):
    # Bug réel observé : le SDK OpenAI retente 2 fois par défaut (max_retries=2).
    # Avec LLM_TIMEOUT_SECONDS=15 par tentative, un échec systématique peut
    # prendre jusqu'à 45s avant d'abandonner — inacceptable maintenant que
    # GuardrailMiddleware appelle ce classifieur de façon synchrone dans le
    # chemin critique de chaque réponse utilisateur (avant : uniquement en
    # tâche de fond via le scheduler mémoire).
    monkeypatch.setenv("AZURE_AI_INFERENCE_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_AI_INFERENCE_API_KEY", "fake-key")
    monkeypatch.setenv("AZURE_AI_CLASSIFIER_MODEL", "Phi-4-mini-instruct")

    llm = get_classifier_llm()

    assert llm._llm.max_retries == 0
