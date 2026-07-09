"""Traitement du tampon `MessageBrut` : capture épisodique + consolidation, purge.

Modèle retenu (skill semantic-episodic-memory) : chaque message est toujours
écrit en épisodique (nettoyage léger, vocabulaire préservé) ; la consolidation
détecte en plus, dans le même appel LLM, un éventuel fait sémantique
généralisable — l'épisode source reste en base comme trace d'audit (R6), le
fait sémantique devient la source de vérité pour la lecture (`MemoryManager.read`).

v1 : déclenché inline en fin de `MemoryManager.write()` (simplicité, testabilité).
L'architecture reste compatible avec un déclenchement par job planifié en v2
(APScheduler/Celery beat) sans changer cette fonction : seul l'appelant change.
"""

from __future__ import annotations

import logging

from . import buffer, episodic, semantic
from .consolidation import consolidate
from .episode_vector_store import get_episode_store
from .vector_store import get_fact_store
from velmo.llm import get_classifier_llm

logger = logging.getLogger(__name__)


def process_pending(session, user_id: str, llm=None, episode_store=None) -> None:
    """Consolide le tampon en attente d'un utilisateur (épisode + fait dérivé), puis le purge.

    Chaque message est traité isolément : un échec (ex. timeout LLM) sur l'un
    d'eux ne bloque pas les autres — seul le message fautif reste en attente,
    retenté au tick suivant (sans ce garde-fou, un timeout ponctuel bloquait
    indéfiniment tout le tampon de l'utilisateur, observé en usage réel).
    """
    rows = buffer.pending_for(session, user_id)
    if not rows:
        return

    store = get_fact_store(session)
    if episode_store is None:
        episode_store = get_episode_store(session)
    if llm is None:
        llm = get_classifier_llm()
    processed_rows = []
    for row in rows:
        try:
            result = consolidate(row.contenu, llm=llm)
            semantic_fact = result.semantic
            consolidated_key = None
            if semantic_fact is not None and semantic_fact.value:
                if semantic_fact.destination == "semantic_column" and semantic_fact.key:
                    semantic.set_known_fact(session, user_id, semantic_fact.key, semantic_fact.value)
                    consolidated_key = semantic_fact.key
                elif semantic_fact.destination == "semantic_vector":
                    store.add(user_id, semantic_fact.key or "fait", semantic_fact.value)
                    consolidated_key = semantic_fact.key or "fait"
            episodic.add_episode(
                session, user_id, result.episode, consolidated_key=consolidated_key
            )
            episode_store.add(user_id, result.episode, consolidated=consolidated_key is not None)
        except Exception:
            logger.exception(
                "Échec de consolidation d'un message pour user_id=%s — laissé en "
                "attente pour retenter au tick suivant", user_id,
            )
            continue
        processed_rows.append(row)

    buffer.delete(session, processed_rows)
