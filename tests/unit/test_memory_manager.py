"""Tests unitaires de MemoryManager : gestion du cycle de vie de la session DB.

Bug corrigé : le scheduler périodique (`memory/scheduler.py`) instancie un
`MemoryManager()` par tick sans jamais fermer sa session, ce qui épuise le
pool de connexions Postgres au bout de quelques ticks (observé en usage réel :
connexions "idle in transaction" qui s'accumulent, scheduler qui se bloque).
"""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import text

from velmo.memory import MemoryManager
from velmo.memory.episode_vector_store import LocalEpisodeStore


def test_read_queries_episode_vector_store(monkeypatch):
    # read() doit interroger le vector store épisodique (en plus de
    # search_episodes) pour bénéficier du tri par similarité de sens.
    # CHROMA_URL désactivé explicitement : le test porte sur le câblage
    # read() -> episode_store.search(), pas sur le choix Chroma/local (qui
    # dépend de l'environnement réel — sinon ce test est fragile selon que
    # Chroma tourne ou non au moment de l'exécution).
    monkeypatch.delenv("CHROMA_URL", raising=False)
    mm = MemoryManager()
    user = "unit-read-episode-vector"

    with patch.object(
        LocalEpisodeStore, "search", return_value=["épisode trouvé via le vector store"]
    ) as mock_search:
        rendered = mm.read(user, "une requête").render()

    mock_search.assert_called_once_with(user, "une requête")
    assert "épisode trouvé via le vector store" in rendered
    mm.close()


def test_close_closes_the_underlying_session():
    mm = MemoryManager()
    session = mm._session
    # Ouvre une transaction pour vérifier qu'elle est bien libérée ensuite.
    session.execute(text("SELECT 1"))
    assert session.in_transaction()

    mm.close()

    assert not session.in_transaction()


def test_preload_facts_returns_known_and_vector_facts():
    # Préchargement au login : mêmes faits que read(), mais sans recherche
    # sémantique/épisodique (pas de message utilisateur au moment du login).
    mm = MemoryManager()
    user = "unit-preload-facts"
    mm.remember_fact(user, "pointure", "42")
    mm.remember_fact(user, "clubs", "OM")

    facts = mm.preload_facts(user)

    assert facts["pointure"] == "42"
    assert facts["clubs"] == "OM"
    mm.close()
