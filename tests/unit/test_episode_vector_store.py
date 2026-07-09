"""Tests unitaires du vector store épisodique (regroupement d'épisodes par sens).

Skill semantic-episodic-memory : « base de données relationnelle + vector store
associé pour regrouper les épisodes par unité de sens » — en plus de la
recherche par mots-clés déjà fournie par `episodic.search_episodes`.

Le repli local réutilise `memory_episodes` (pas de nouvelle table) : `add`/
`delete_matching` sont des no-op côté `LocalEpisodeStore`, la persistance est
déjà assurée par `episodic.add_episode`/`delete_matching`. Seul `search` ajoute
une valeur propre : un tri par recouvrement de tokens.
"""

from __future__ import annotations

from velmo.db import fresh_sqlite_session
from velmo.memory import episodic
from velmo.memory.episode_vector_store import LocalEpisodeStore


def _session():
    return fresh_sqlite_session()


def test_search_ranks_episodes_by_token_overlap():
    session = _session()
    episodic.add_episode(session, "u1", "Client a acheté un maillot du PSG édition 1998")
    store = LocalEpisodeStore(session)

    results = store.search("u1", "maillot")

    assert results == ["Client a acheté un maillot du PSG édition 1998"]


def test_search_is_isolated_per_user():
    session = _session()
    episodic.add_episode(session, "u1", "Client a acheté un maillot du PSG")
    episodic.add_episode(session, "u2", "Client a acheté un maillot de l'OM")
    store = LocalEpisodeStore(session)

    results = store.search("u1", "maillot")

    assert results == ["Client a acheté un maillot du PSG"]


def test_search_excludes_consolidated_episodes_by_default():
    session = _session()
    episodic.add_episode(session, "u1", "Client a acheté un maillot du PSG")
    episodic.add_episode(session, "u1", "Pointure du client : 43", consolidated_key="pointure")
    store = LocalEpisodeStore(session)

    results = store.search("u1", "pointure")

    assert results == []
