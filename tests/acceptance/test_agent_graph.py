"""Tests d'acceptance bout-en-bout de l'agent `create_agent()`.

Preuve que le graphe LangGraph, les middlewares (garde-fous, mémoire) et les
outils bindés fonctionnent ensemble, via un modèle scriptable hors-ligne
(`ScriptedToolCallingModel`) — pas d'appel Azure réel.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from support.fake_chat_model import ScriptedToolCallingModel
from velmo.agent import Agent
from velmo.db import fresh_sqlite_session
from velmo.guardrails import GuardrailEngine
from velmo.kb_store import LocalKB
from velmo.memory import MemoryManager
from velmo.sampledata import seed


def _seeded_session():
    session = fresh_sqlite_session()
    seed(session)
    return session


def _build_agent(model, session=None, kb=None):
    return Agent(
        model=model,
        memory=MemoryManager(),
        guardrails=GuardrailEngine(),
        session=session or _seeded_session(),
        kb=kb or LocalKB(),
    )


def test_simple_greeting_returns_scripted_reply_and_runs_memory_guardrails():
    model = ScriptedToolCallingModel(responses=[AIMessage("Bonjour, comment puis-je vous aider ?")])
    agent = _build_agent(model)

    reply = agent.respond("C-marc-dubois", "Bonjour")

    assert reply == "Bonjour, comment puis-je vous aider ?"
    from velmo.memory import short_term

    turns = short_term.get_turns("C-marc-dubois")
    assert ("user", "Bonjour") in turns
    assert ("assistant", "Bonjour, comment puis-je vous aider ?") in turns


def test_tool_call_executes_against_real_db():
    model = ScriptedToolCallingModel(responses=[
        AIMessage(
            content="",
            tool_calls=[{"name": "get_order", "args": {"order_id": "O-2024-0101"}, "id": "call_1"}],
        ),
        AIMessage("Votre commande O-2024-0101 est au statut préparée."),
    ])
    agent = _build_agent(model)

    reply = agent.respond("C-marc-dubois", "Quel est le statut de ma commande O-2024-0101 ?")

    assert reply == "Votre commande O-2024-0101 est au statut préparée."


def test_respond_logs_latency_for_the_chat_model(caplog):
    # Bug réel observé en rejouant docs/script_presentation_demo_memoire.md
    # (Démo 3) : depuis la migration vers create_agent(), le modèle de chat
    # principal (get_chat_model(), BaseChatModel brut) n'était plus enveloppé
    # par LangChainAdapter — sa latence disparaissait de logs/llm_latency.log.
    import logging

    model = ScriptedToolCallingModel(responses=[AIMessage("Bonjour !")])
    agent = _build_agent(model)

    with caplog.at_level(logging.INFO, logger="velmo.llm.latency"):
        agent.respond("C-marc-dubois", "Bonjour")

    records = [r for r in caplog.records if r.name == "velmo.llm.latency"]
    assert len(records) == 1


def test_blocked_input_never_invokes_the_model():
    model = ScriptedToolCallingModel(responses=[AIMessage("ne devrait jamais être renvoyé")])
    agent = _build_agent(model)

    reply = agent.respond(
        "C-marc-dubois", "Sale race, retournez dans votre pays avec vos maillots."
    )

    assert reply != "ne devrait jamais être renvoyé"
    assert model.i == 0  # jamais invoqué (le compteur n'a pas avancé)
