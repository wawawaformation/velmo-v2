"""Tests unitaires de `check_stock` — robustesse à la casse de la référence.

Bug réel révélé par la suite qualité : à la question « Le maillot om-1993 en
taille L est-il disponible ? », l'agent appelle l'outil avec `OM-1993`. Or la
recherche se faisait par clé primaire exacte (`session.get`) — la référence
n'était pas trouvée et le client s'entendait répondre que le produit n'existe
pas, alors qu'il était en stock. Une vente perdue sur une faute de casse.
"""

from __future__ import annotations

import pytest
from conftest import seeded_session

from velmo.tools.catalog import check_stock


@pytest.fixture
def session():
    s = seeded_session()
    yield s
    s.close()


@pytest.mark.parametrize("ref", ["om-1993", "OM-1993", "Om-1993", " om-1993 "])
def test_check_stock_is_case_insensitive(session, ref):
    result = check_stock(session, ref, "L")

    assert result.get("error") is None, f"référence {ref!r} non trouvée"
    assert result["available"] is True
    assert result["stock"] == 1
    # La référence canonique de la base est renvoyée, pas la saisie du client.
    assert result["product_ref"] == "om-1993"


def test_check_stock_still_reports_unknown_product(session):
    # La tolérance à la casse ne doit pas transformer une vraie erreur en succès.
    result = check_stock(session, "ref-qui-nexiste-pas", "L")

    assert result["error"] == "unknown_product"


def test_check_stock_reports_out_of_stock_size(session):
    # Variante épuisée (stock 0) : disponible=False, sans fabuler.
    result = check_stock(session, "OM-1993", "M")

    assert result.get("error") is None
    assert result["available"] is False
    assert result["stock"] == 0
