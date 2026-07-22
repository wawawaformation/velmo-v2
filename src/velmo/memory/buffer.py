"""Tampon de capture synchrone (`MessageBrut`) : simple insertion, aucun appel LLM."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from velmo.db import MessageBrut


def capture(session, user_id: str, role: str, content: str) -> None:
    """Insère un message brut dans le tampon, en attente de classification."""
    session.add(
        MessageBrut(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role=role,
            contenu=content,
            horodatage=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.commit()


def pending_for(session, user_id: str) -> list[MessageBrut]:
    """Renvoie les messages non encore traités d'un utilisateur."""
    return list(
        session.execute(
            select(MessageBrut).where(MessageBrut.user_id == user_id)
        ).scalars().all()
    )


def pending_user_ids(session) -> list[str]:
    """Liste les `user_id` distincts ayant au moins un message en attente."""
    rows = session.execute(select(MessageBrut.user_id).distinct()).all()
    return [r[0] for r in rows]


def delete(session, rows: list[MessageBrut]) -> None:
    """Supprime du tampon les lignes déjà routées vers le long terme."""
    for row in rows:
        session.delete(row)
    if rows:
        session.commit()


def delete_matching(session, user_id: str, target: str) -> int:
    """Purge le tampon non traité contenant `target` (fenêtre de risque R5)."""
    rows = pending_for(session, user_id)
    target_low = target.lower()
    matching = [r for r in rows if target_low in r.contenu.lower()]
    delete(session, matching)
    return len(matching)
