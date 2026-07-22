"""Mémoire épisodique : événements en texte + date, recherchés par mots-clés (LIKE)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from velmo.db import MemoryEpisode


def add_episode(
    session, user_id: str, contenu: str, consolidated_key: str | None = None
) -> None:
    """Enregistre un événement épisodique daté pour l'utilisateur.

    `consolidated_key` marque l'épisode comme source d'un fait sémantique
    dérivé (ex. "pointure") : il reste en base comme trace d'audit (R6) mais
    n'est plus restitué par défaut via `list_episodes`/`search_episodes`.
    """
    session.add(
        MemoryEpisode(
            id_episode=str(uuid.uuid4()),
            user_id=user_id,
            contenu=contenu,
            date=datetime.now(timezone.utc).replace(tzinfo=None),
            consolidated=consolidated_key is not None,
            consolidated_key=consolidated_key,
        )
    )
    session.commit()


def list_episodes(
    session, user_id: str, include_consolidated: bool = False
) -> list[str]:
    """Liste les épisodes non consolidés d'un utilisateur (tous si `include_consolidated`)."""
    stmt = select(MemoryEpisode.contenu).where(MemoryEpisode.user_id == user_id)
    if not include_consolidated:
        stmt = stmt.where(MemoryEpisode.consolidated == False)  # noqa: E712
    rows = session.execute(stmt).all()
    return [r[0] for r in rows]


def search_episodes(
    session, user_id: str, query: str, include_consolidated: bool = False
) -> list[str]:
    """Recherche plein texte simple : renvoie les épisodes qui partagent un mot avec `query`."""
    words = [w for w in query.lower().split() if len(w) > 2]
    episodes = list_episodes(session, user_id, include_consolidated=include_consolidated)
    if not words:
        return episodes
    return [ep for ep in episodes if any(w in ep.lower() for w in words)]


def delete_by_consolidated_key(session, user_id: str, key: str) -> int:
    """Supprime l'épisode source d'un fait consolidé donné (R5, cf. `forget`)."""
    rows = session.execute(
        select(MemoryEpisode).where(
            MemoryEpisode.user_id == user_id, MemoryEpisode.consolidated_key == key
        )
    ).scalars().all()
    for row in rows:
        session.delete(row)
    if rows:
        session.commit()
    return len(rows)


def delete_matching(session, user_id: str, target: str) -> int:
    """Supprime les épisodes dont le contenu correspond à `target` (R5)."""
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
