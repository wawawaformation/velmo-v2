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

import logging

from velmo.db import fresh_sqlite_session
from velmo.memory import episodic
from velmo.memory.episode_vector_store import LocalEpisodeStore, get_episode_store


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


def test_get_episode_store_logs_warning_when_falling_back_to_local(monkeypatch, caplog):
    # Bug corrigé : CHROMA_URL configuré mais injoignable/en échec retombait
    # silencieusement sur LocalEpisodeStore, sans aucune trace — impossible de
    # détecter que la mémoire n'utilisait jamais Chroma malgré la config.
    monkeypatch.setenv("CHROMA_URL", "http://localhost:1")  # port fermé, échec de connexion
    session = _session()

    with caplog.at_level(logging.WARNING, logger="velmo.memory.episode_vector_store"):
        store = get_episode_store(session)

    assert isinstance(store, LocalEpisodeStore)
    assert any("Chroma" in r.message for r in caplog.records)
