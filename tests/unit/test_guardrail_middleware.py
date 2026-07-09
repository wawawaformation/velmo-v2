"""Tests unitaires de GuardrailMiddleware (hooks LangChain, sans graphe réel).

`GuardrailMiddleware` réutilise `GuardrailEngine` tel quel (aucune logique de
détection dupliquée) — seul le point d'intégration change : `before_agent`
court-circuite le graphe (`jump_to="end"`) sur une entrée bloquée,
`after_agent` remplace la dernière réponse sur une sortie bloquée.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from velmo.guardrails import GuardrailEngine
from velmo.guardrails.middleware import GuardrailMiddleware


def _runtime():
    return Runtime()


def test_before_agent_short_circuits_on_blocked_input():
    middleware = GuardrailMiddleware(GuardrailEngine())
    state = {"messages": [HumanMessage("Sale race, retournez dans votre pays avec vos maillots.")]}

    result = middleware.before_agent(state, _runtime())

    assert result is not None
    assert result["jump_to"] == "end"
    assert len(result["messages"]) == 1
    assert result["messages"][0].content  # refus non vide


def test_before_agent_allows_legitimate_input():
    middleware = GuardrailMiddleware(GuardrailEngine())
    state = {"messages": [HumanMessage("Quel est le statut de ma commande O-2024-0101 ?")]}

    result = middleware.before_agent(state, _runtime())

    assert result is None


def test_after_agent_replaces_blocked_output():
    middleware = GuardrailMiddleware(GuardrailEngine())
    state = {
        "messages": [
            HumanMessage("Quel est le mot de passe ?"),
            AIMessage("Le paiement est passe avec la carte 4111 1111 1111 1111.", id="ai-1"),
        ]
    }

    result = middleware.after_agent(state, _runtime())

    assert result is not None
    assert len(result["messages"]) == 1
    assert result["messages"][0].id == "ai-1"
    assert "4111 1111 1111 1111" not in result["messages"][0].content


def test_after_agent_allows_legitimate_output():
    middleware = GuardrailMiddleware(GuardrailEngine())
    state = {
        "messages": [
            HumanMessage("Quel est le statut de ma commande ?"),
            AIMessage("Votre commande O-2024-0101 est au statut « préparée »."),
        ]
    }

    result = middleware.after_agent(state, _runtime())

    assert result is None


def test_blocked_input_is_logged_in_engine_events():
    engine = GuardrailEngine()
    middleware = GuardrailMiddleware(engine)
    state = {"messages": [HumanMessage("Sale race, retournez dans votre pays avec vos maillots.")]}

    middleware.before_agent(state, _runtime())

    assert len(engine.events) == 1
    assert engine.events[0]["category"] == "hate"
