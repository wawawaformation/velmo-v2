"""Mémoire sémantique à clé connue d'avance : colonnes directes sur `MemoryUser` (R2).

Lecture immédiate, oubli trivial (colonne remise à NULL) — réservé aux clés
identifiées à l'avance. Les clés imprévisibles relèvent de `vector_store.py`.
"""

from __future__ import annotations

from velmo.db import MemoryUser

KNOWN_KEYS = ("pointure", "segment", "tutoiement", "langue", "canal_contact")


def set_known_fact(session, user_id: str, key: str, value: str) -> None:
    if key not in KNOWN_KEYS:
        raise ValueError(f"clé inconnue: {key}")
    user = session.get(MemoryUser, user_id)
    if user is None:
        user = MemoryUser(id=user_id)
        session.add(user)
    setattr(user, key, value)
    session.commit()


def get_known_facts(session, user_id: str) -> dict[str, str]:
    user = session.get(MemoryUser, user_id)
    if user is None:
        return {}
    return {k: getattr(user, k) for k in KNOWN_KEYS if getattr(user, k) is not None}


def clear_matching(session, user_id: str, target: str) -> int:
    """Vide les colonnes connues dont le nom matche `target` (R5)."""
    user = session.get(MemoryUser, user_id)
    if user is None:
        return 0
    removed = 0
    target_low = target.lower()
    for key in KNOWN_KEYS:
        if target_low in key.lower() and getattr(user, key) is not None:
            setattr(user, key, None)
            removed += 1
    if removed:
        session.commit()
    return removed
