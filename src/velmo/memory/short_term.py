"""Mémoire court terme (RAM) : fenêtre glissante des derniers tours (R1, R4).

Portée au process courant, par `user_id`. Pas de persistance : c'est le rôle
du long terme (colonnes `MemoryUser`, vectoriel, épisodes) de survivre à la session
et de porter l'information au-delà de la fenêtre (cf. `conception/memoire/choix.md`).
"""

from __future__ import annotations

Turn = tuple[str, str]  # (role, content)

MAX_TURNS = 30

_HISTORY: dict[str, list[Turn]] = {}


def append(user_id: str, role: str, content: str) -> None:
    turns = _HISTORY.setdefault(user_id, [])
    turns.append((role, content))
    del turns[:-MAX_TURNS]


def get_turns(user_id: str) -> list[Turn]:
    return list(_HISTORY.get(user_id, []))


def purge_matching(user_id: str, target: str) -> int:
    """Retire du fil court terme les tours contenant `target` (R5)."""
    turns = _HISTORY.get(user_id, [])
    kept = [t for t in turns if target.lower() not in t[1].lower()]
    removed = len(turns) - len(kept)
    _HISTORY[user_id] = kept
    return removed
