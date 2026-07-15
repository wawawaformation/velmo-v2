"""Tests d'acceptance de l'API REST (FastAPI) — couche HTTP au-dessus de `Agent.respond()`.

Pas d'authentification réelle à ce stade (POC) : `user_id` est passé en clair
dans le payload. Modèle scriptable hors-ligne (`ScriptedToolCallingModel`),
pas d'appel Azure réel — même approche que `test_agent_graph.py`.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage
from fastapi.testclient import TestClient

from support.fake_chat_model import ScriptedToolCallingModel
from velmo.api import app, get_session
from velmo.db import fresh_sqlite_session
from velmo.kb_store import LocalKB
from velmo.sampledata import seed


def _seeded_session():
    session = fresh_sqlite_session()
    seed(session)
    return session


def _client_with_model(model):
    session = _seeded_session()
    app.dependency_overrides[get_session] = lambda: session
    app.state.chat_model = model
    app.state.kb = LocalKB()
    client = TestClient(app)
    return client, session


def test_post_messages_returns_agent_reply():
    model = ScriptedToolCallingModel(responses=[AIMessage("Bonjour, comment puis-je vous aider ?")])
    client, _ = _client_with_model(model)

    response = client.post("/messages", json={"user_id": "C-marc-dubois", "message": "Bonjour"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Bonjour, comment puis-je vous aider ?"
    assert body["latency_ms"] >= 0


def test_post_messages_reports_positive_latency():
    # Latence perçue par le client : le temps total de la requête HTTP
    # (garde-fous + mémoire + LLM inclus), pas seulement le dernier appel LLM
    # — mesurée directement dans la route, sans instrumenter Agent.respond().
    model = ScriptedToolCallingModel(responses=[AIMessage("Bonjour !")])
    client, _ = _client_with_model(model)

    response = client.post("/messages", json={"user_id": "C-marc-dubois", "message": "Bonjour"})

    assert response.json()["latency_ms"] > 0


def test_post_messages_runs_tool_call_against_real_db():
    model = ScriptedToolCallingModel(responses=[
        AIMessage(
            content="",
            tool_calls=[{"name": "get_order", "args": {"order_id": "O-2024-0101"}, "id": "call_1"}],
        ),
        AIMessage("Votre commande O-2024-0101 est au statut préparée."),
    ])
    client, _ = _client_with_model(model)

    response = client.post(
        "/messages",
        json={"user_id": "C-marc-dubois", "message": "Quel est le statut de ma commande O-2024-0101 ?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Votre commande O-2024-0101 est au statut préparée."
    assert body["latency_ms"] >= 0


def test_post_messages_rejects_missing_fields():
    model = ScriptedToolCallingModel(responses=[AIMessage("peu importe")])
    client, _ = _client_with_model(model)

    response = client.post("/messages", json={"user_id": "C-marc-dubois"})

    assert response.status_code == 422


def test_get_users_lists_customers_from_db():
    model = ScriptedToolCallingModel(responses=[AIMessage("peu importe")])
    client, _ = _client_with_model(model)

    response = client.get("/users")

    assert response.status_code == 200
    users = response.json()
    ids = [u["id"] for u in users]
    assert "C-marc-dubois" in ids
    marc = next(u for u in users if u["id"] == "C-marc-dubois")
    assert marc["full_name"] == "Marc Dubois"
    assert marc["email"] == "marc.dubois@example.com"
