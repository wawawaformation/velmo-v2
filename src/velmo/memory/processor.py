"""Traitement du tampon `MessageBrut` : classe, distille, route, purge.

v1 : déclenché inline en fin de `MemoryManager.write()` (simplicité, testabilité).
L'architecture reste compatible avec un déclenchement par job planifié en v2
(APScheduler/Celery beat) sans changer cette fonction : seul l'appelant change.
"""

from __future__ import annotations

from . import buffer, episodic, semantic
from .classifier import classify_and_distill
from .vector_store import get_fact_store


def process_pending(session, user_id: str) -> None:
    rows = buffer.pending_for(session, user_id)
    if not rows:
        return

    store = get_fact_store(session)
    for row in rows:
        result = classify_and_distill(row.contenu)
        if result.destination == "semantic_column" and result.key and result.value:
            semantic.set_known_fact(session, user_id, result.key, result.value)
        elif result.destination == "semantic_vector" and result.value:
            store.add(user_id, result.key or "fait", result.value)
        elif result.destination == "episodic" and result.value:
            episodic.add_episode(session, user_id, result.value)
        # "none" : rien à retenir, la ligne est simplement retirée du tampon.

    buffer.delete(session, rows)
