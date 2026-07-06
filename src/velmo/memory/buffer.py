"""Tampon de capture synchrone (`MessageBrut`) : simple insertion, aucun appel LLM."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from velmo.db import MessageBrut


def capture(session, user_id: str, role: str, content: str) -> None:
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
    return list(
        session.execute(
            select(MessageBrut).where(MessageBrut.user_id == user_id)
        ).scalars().all()
    )


def delete(session, rows: list[MessageBrut]) -> None:
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
