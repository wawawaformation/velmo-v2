"""Tests métier spécifiques au domaine (au-delà des 11 du brief).

Ces règles vivent dans les outils fonctionnels : elles passent sur `main` comme
sur `instructor` (l'agent est sûr par construction, avant même les garde-fous de
contenu).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from conftest import build_reference_agent
from velmo.db import Escalation, Order, OrderStatus, Refund, RefundStatus
from velmo.tools import get_order, trigger_refund, update_order_item
from velmo.tools._common import select
from support.fake_chat_model import ScriptedToolCallingModel


def test_cannot_modify_shipped_order(db_session):
    # Une commande expédiée n'est pas modifiable : escalade, pas de changement.
    result = update_order_item(db_session, "O-2024-0103", "C-marc-dubois", "M")
    assert result["action"] == "escalate"

    order = db_session.get(Order, "O-2024-0103")
    assert order.status == OrderStatus.shipped
    assert order.items[0].size.value == "L"  # taille inchangée


def test_can_modify_unshipped_order(db_session):
    result = update_order_item(db_session, "O-2024-0101", "C-marc-dubois", "XL")
    assert result["action"] == "updated"
    order = db_session.get(Order, "O-2024-0101")
    assert order.items[0].size.value == "XL"


def test_refund_above_cap_escalates(db_session):
    # Remboursement > 50€ : escalade, aucun remboursement auto.
    result = trigger_refund(db_session, "O-2024-0110", "C-sophie-martin", 200, "Litige")
    assert result["action"] == "escalate"
    autos = db_session.scalars(
        select(Refund).where(Refund.order_id == "O-2024-0110", Refund.status == RefundStatus.auto)
    ).all()
    assert autos == []


def test_refund_below_cap_is_auto(db_session):
    result = trigger_refund(db_session, "O-2024-0110", "C-sophie-martin", 30, "Geste commercial")
    assert result["action"] == "refunded"


def test_isolation_other_customer_order(db_session):
    # Marc ne peut pas accéder à la commande de Sophie.
    result = get_order(db_session, "O-2024-0107", "C-marc-dubois")
    assert result.get("error") == "not_found_or_forbidden"


def test_no_fabulation_when_out_of_stock():
    # Variante om-1993 / M est à 0 : l'agent appelle bien check_stock (pas de
    # fabulation) et l'outil renvoie available=False — comportement vérifié,
    # pas le texte libre rédigé par le LLM.
    model = ScriptedToolCallingModel(responses=[
        AIMessage(
            content="",
            tool_calls=[
                {"name": "check_stock", "args": {"product_ref": "om-1993", "size": "M"}, "id": "call_1"}
            ],
        ),
        AIMessage("Ce maillot est indisponible en taille M."),
    ])
    agent = build_reference_agent(model=model)

    import velmo.tools.catalog as catalog_module

    original_check_stock = catalog_module.check_stock
    calls = []

    def spy_check_stock(session, product_ref, size):
        result = original_check_stock(session, product_ref, size)
        calls.append((product_ref, size, result))
        return result

    catalog_module.check_stock = spy_check_stock
    try:
        agent.respond("C-marc-dubois", "Le maillot om-1993 en taille M est-il disponible ?")
    finally:
        catalog_module.check_stock = original_check_stock

    assert len(calls) == 1
    product_ref, size, result = calls[0]
    assert product_ref == "om-1993"
    assert size == "M"
    assert result["available"] is False


def test_escalation_recorded_on_shipped_modification(db_session):
    before = len(db_session.scalars(select(Escalation)).all())
    update_order_item(db_session, "O-2024-0103", "C-marc-dubois", "M")
    after = len(db_session.scalars(select(Escalation)).all())
    assert after == before + 1
