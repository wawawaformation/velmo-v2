"""Mémoire court terme (RAM) : fil complet de la conversation en cours (R1).

Portée au process courant, par `user_id`. Pas de persistance : c'est le rôle
du long terme (colonnes `MemoryUser`, vectoriel, épisodes) de survivre à la session.
"""

from __future__ import annotations

Turn = tuple[str, str]  # (role, content)

_HISTORY: dict[str, list[Turn]] = {}


def append(user_id: str, role: str, content: str) -> None:
    _HISTORY.setdefault(user_id, []).append((role, content))


def get_turns(user_id: str) -> list[Turn]:
    return list(_HISTORY.get(user_id, []))


def purge_matching(user_id: str, target: str) -> int:
    """Retire du fil court terme les tours contenant `target` (R5)."""
    turns = _HISTORY.get(user_id, [])
    kept = [t for t in turns if target.lower() not in t[1].lower()]
    removed = len(turns) - len(kept)
    _HISTORY[user_id] = kept
    return removed
