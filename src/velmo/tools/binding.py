"""Liaison des outils métier au tool-calling LangChain (`create_agent()`).

`session`/`user_id` sont liés par fermeture Python à la construction (par
requête), jamais exposés comme arguments pilotables par le LLM — un LLM ne
doit jamais pouvoir choisir lui-même quel `user_id` interroger (risque
d'injection). Les corps des outils métier restent inchangés (`orders.py`,
`refunds.py`, `returns.py`, `catalog.py`, `kb.py`) ; seule cette couche les
enveloppe en `BaseTool`.
"""

from __future__ import annotations

from langchain_core.tools import tool

from . import catalog, kb, orders, refunds, returns


def bound_tools(session, user_id: str, kb_store) -> list:
    """Construit la liste des outils exposés au LLM pour un utilisateur donné."""

    @tool
    def get_order(order_id: str) -> dict:
        """Renvoie le détail et le statut d'une commande appartenant au client."""
        return orders.get_order(session, order_id, user_id)

    @tool
    def track_shipment(order_id: str) -> dict:
        """Renvoie le suivi transporteur et la date estimée de livraison d'une commande."""
        return orders.track_shipment(session, order_id, user_id)

    @tool
    def update_order_item(order_id: str, new_size: str) -> dict:
        """Change la taille d'un article tant que la commande n'est pas expédiée."""
        return orders.update_order_item(session, order_id, user_id, new_size)

    @tool
    def update_shipping_address(order_id: str, address: dict) -> dict:
        """Modifie l'adresse de livraison tant que la commande n'est pas expédiée."""
        return orders.update_shipping_address(session, order_id, user_id, address)

    @tool
    def cancel_order(order_id: str) -> dict:
        """Annule une commande tant qu'elle n'est pas expédiée."""
        return orders.cancel_order(session, order_id, user_id)

    @tool
    def trigger_refund(order_id: str, amount: float, reason: str) -> dict:
        """Rembourse une commande si le montant est sous le plafond, sinon escalade."""
        return refunds.trigger_refund(session, order_id, user_id, amount, reason)

    @tool
    def create_return(order_id: str, reason: str) -> dict:
        """Ouvre une demande de retour/échange si la commande est dans la fenêtre de retour."""
        return returns.create_return(session, order_id, user_id, reason)

    @tool
    def check_stock(product_ref: str, size: str) -> dict:
        """Indique si une référence est disponible dans une taille donnée (stock souvent 1)."""
        return catalog.check_stock(session, product_ref, size)

    @tool
    def search_kb(query: str) -> dict:
        """Cherche une réponse dans la FAQ Velmo et renvoie des extraits sourcés."""
        return kb.search_kb(kb_store, query)

    return [
        get_order,
        track_shipment,
        update_order_item,
        update_shipping_address,
        cancel_order,
        trigger_refund,
        create_return,
        check_stock,
        search_kb,
    ]
