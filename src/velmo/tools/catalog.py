"""Outils de catalogue : disponibilité et stock."""

from __future__ import annotations

from sqlalchemy import func

from ..db import Product, ProductVariant
from ._common import select


def check_stock(session, product_ref: str, size: str) -> dict:
    """Indique si une référence est disponible dans une taille donnée (stock souvent 1).

    La recherche tolère la casse et les espaces : le LLM (comme un client)
    écrit volontiers « OM-1993 » alors que la base stocke « om-1993 ». Une
    recherche par clé primaire exacte renvoyait alors `unknown_product` pour un
    article pourtant en stock.
    """
    normalized = product_ref.strip()
    product = session.scalars(
        select(Product).where(func.lower(Product.ref) == normalized.lower())
    ).first()
    if product is None:
        return {"error": "unknown_product", "product_ref": product_ref}
    # On repart de la référence canonique de la base, pas de la saisie du client.
    variant = session.scalars(
        select(ProductVariant).where(
            ProductVariant.product_ref == product.ref, ProductVariant.size == size
        )
    ).first()
    if variant is None:
        return {"product_ref": product.ref, "size": size, "available": False, "stock": 0}
    return {
        "product_ref": product.ref,
        "title": product.title,
        "size": size,
        "available": variant.stock > 0,
        "stock": variant.stock,
    }
