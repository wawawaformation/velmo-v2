"""Mémoire épisodique : événements en texte + date, recherchés par mots-clés (LIKE)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from velmo.db import MemoryEpisode


def add_episode(session, user_id: str, contenu: str) -> None:
    session.add(
        MemoryEpisode(
            id_episode=str(uuid.uuid4()),
            user_id=user_id,
            contenu=contenu,
            date=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.commit()


def list_episodes(session, user_id: str) -> list[str]:
    rows = session.execute(
        select(MemoryEpisode.contenu).where(MemoryEpisode.user_id == user_id)
    ).all()
    return [r[0] for r in rows]


def search_episodes(session, user_id: str, query: str) -> list[str]:
    """Recherche plein texte simple : renvoie les épisodes qui partagent un mot avec `query`."""
    words = [w for w in query.lower().split() if len(w) > 2]
    episodes = list_episodes(session, user_id)
    if not words:
        return episodes
    return [ep for ep in episodes if any(w in ep.lower() for w in words)]


def delete_matching(session, user_id: str, target: str) -> int:
    rows = session.execute(
        select(MemoryEpisode).where(MemoryEpisode.user_id == user_id)
    ).scalars().all()
    removed = 0
    target_low = target.lower()
    for row in rows:
        if target_low in row.contenu.lower():
            session.delete(row)
            removed += 1
    if removed:
        session.commit()
    return removed
