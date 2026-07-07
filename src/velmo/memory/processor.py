"""Traitement du tampon `MessageBrut` : classe, distille, route, purge.

v1 : déclenché inline en fin de `MemoryManager.write()` (simplicité, testabilité).
L'architecture reste compatible avec un déclenchement par job planifié en v2
(APScheduler/Celery beat) sans changer cette fonction : seul l'appelant change.
"""

from __future__ import annotations

from . import buffer, episodic, semantic
from .classifier import classify_and_distill
from .vector_store import get_fact_store
from velmo.llm import get_classifier_llm


def process_pending(session, user_id: str) -> None:
    rows = buffer.pending_for(session, user_id)
    if not rows:
        return

    store = get_fact_store(session)
    llm = get_classifier_llm()
    for row in rows:
        results = classify_and_distill(row.contenu, llm=llm)
        for result in results:
            if result.destination == "semantic_column" and result.key and result.value:
                semantic.set_known_fact(session, user_id, result.key, result.value)
            elif result.destination == "semantic_vector" and result.value:
                store.add(user_id, result.key or "fait", result.value)
            elif result.destination == "episodic" and result.value:
                episodic.add_episode(session, user_id, result.value)
            # "none" : rien à retenir.

    buffer.delete(session, rows)
