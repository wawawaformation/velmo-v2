"""Tests unitaires de la mémoire épisodique (source de vérité vs trace d'audit).

Un épisode consolidé (fait sémantique dérivé) reste en base mais n'est plus
restitué par défaut via list_episodes/search_episodes — le sémantique devient
la source de vérité pour la lecture, l'épisode devient une trace d'audit (R6).
"""

from __future__ import annotations

from velmo.db import fresh_sqlite_session
from velmo.memory import episodic


def _session():
    return fresh_sqlite_session()


def test_add_episode_without_consolidation_is_listed_by_default():
    session = _session()
    episodic.add_episode(session, "u1", "Client a acheté un maillot PSG")

    assert episodic.list_episodes(session, "u1") == ["Client a acheté un maillot PSG"]


def test_add_episode_with_consolidated_key_is_excluded_by_default():
    session = _session()
    episodic.add_episode(session, "u1", "Pointure du client : 43", consolidated_key="pointure")

    assert episodic.list_episodes(session, "u1") == []


def test_add_episode_with_consolidated_key_is_included_with_flag():
    session = _session()
    episodic.add_episode(session, "u1", "Pointure du client : 43", consolidated_key="pointure")

    assert episodic.list_episodes(session, "u1", include_consolidated=True) == [
        "Pointure du client : 43"
    ]


def test_search_episodes_excludes_consolidated_by_default():
    session = _session()
    episodic.add_episode(session, "u1", "Client a acheté un maillot PSG")
    episodic.add_episode(session, "u1", "Pointure du client : 43", consolidated_key="pointure")

    assert episodic.search_episodes(session, "u1", "maillot") == [
        "Client a acheté un maillot PSG"
    ]
    assert episodic.search_episodes(session, "u1", "pointure") == []


def test_delete_by_consolidated_key_removes_only_matching_episode():
    session = _session()
    episodic.add_episode(session, "u1", "Pointure du client : 43", consolidated_key="pointure")
    episodic.add_episode(session, "u1", "Langue du client : français", consolidated_key="langue")

    removed = episodic.delete_by_consolidated_key(session, "u1", "pointure")

    assert removed == 1
    remaining = episodic.list_episodes(session, "u1", include_consolidated=True)
    assert remaining == ["Langue du client : français"]
