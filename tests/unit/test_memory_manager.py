"""Tests unitaires de MemoryManager : gestion du cycle de vie de la session DB.

Bug corrigé : le scheduler périodique (`memory/scheduler.py`) instancie un
`MemoryManager()` par tick sans jamais fermer sa session, ce qui épuise le
pool de connexions Postgres au bout de quelques ticks (observé en usage réel :
connexions "idle in transaction" qui s'accumulent, scheduler qui se bloque).
"""

from __future__ import annotations

from sqlalchemy import text

from velmo.memory import MemoryManager


def test_close_closes_the_underlying_session():
    mm = MemoryManager()
    session = mm._session
    # Ouvre une transaction pour vérifier qu'elle est bien libérée ensuite.
    session.execute(text("SELECT 1"))
    assert session.in_transaction()

    mm.close()

    assert not session.in_transaction()
