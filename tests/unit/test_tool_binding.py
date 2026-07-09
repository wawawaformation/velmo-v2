"""Tests unitaires de la fabrique de liaison d'outils (tool-calling LangChain).

`bound_tools(session, user_id, kb)` doit lier `session`/`user_id` par fermeture
Python, sans jamais les exposer comme arguments pilotables par le LLM (risque
d'injection : un LLM ne doit jamais pouvoir choisir lui-même `user_id`) — seule
la clé métier (ex. `order_id`) reste visible dans le schéma de l'outil.
"""

from __future__ import annotations

from velmo.db import fresh_sqlite_session
from velmo.sampledata import seed
from velmo.tools.binding import bound_tools


def _seeded_session():
    session = fresh_sqlite_session()
    seed(session)
    return session


def _find_tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_bound_tools_returns_a_list_of_tools():
    session = _seeded_session()
    tools = bound_tools(session, user_id="C-marc-dubois", kb_store=None)

    assert len(tools) > 0
    names = {t.name for t in tools}
    assert "get_order" in names


def test_get_order_schema_does_not_expose_user_id_or_session():
    session = _seeded_session()
    tools = bound_tools(session, user_id="C-marc-dubois", kb_store=None)
    get_order = _find_tool(tools, "get_order")

    schema_fields = set(get_order.get_input_schema().model_fields)

    assert "user_id" not in schema_fields
    assert "session" not in schema_fields
    assert schema_fields == {"order_id"}


def test_get_order_tool_returns_same_result_as_direct_call():
    session = _seeded_session()
    tools = bound_tools(session, user_id="C-marc-dubois", kb_store=None)
    get_order = _find_tool(tools, "get_order")

    from velmo import tools as raw_tools

    direct = raw_tools.get_order(session, "O-2024-0101", "C-marc-dubois")
    via_tool = get_order.invoke({"order_id": "O-2024-0101"})

    assert via_tool == direct


def test_get_order_tool_enforces_isolation_for_other_owners_order():
    # user_id est fixé à la construction (fermeture) — même si le LLM tente de
    # cibler la commande de Sophie, owned_order() refuse toujours l'accès.
    session = _seeded_session()
    tools = bound_tools(session, user_id="C-marc-dubois", kb_store=None)
    get_order = _find_tool(tools, "get_order")

    result = get_order.invoke({"order_id": "O-2024-0107"})

    assert result == {"error": "not_found_or_forbidden", "order_id": "O-2024-0107"}


def test_escalate_to_human_is_not_exposed():
    # Décision actée : pas de nouvelle capacité métier lors de cette migration.
    session = _seeded_session()
    tools = bound_tools(session, user_id="C-marc-dubois", kb_store=None)

    names = {t.name for t in tools}

    assert "escalate_to_human" not in names
