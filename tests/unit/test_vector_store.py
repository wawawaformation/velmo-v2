"""Tests unitaires du vector store sémantique (faits à clé imprévisible).

Symétrique à `test_episode_vector_store.py` : mêmes garanties attendues côté
`get_fact_store`.
"""

from __future__ import annotations

import logging

from velmo.db import fresh_sqlite_session
from velmo.memory.vector_store import LocalFactStore, get_fact_store


def _session():
    return fresh_sqlite_session()


def test_get_fact_store_logs_warning_when_falling_back_to_local(monkeypatch, caplog):
    # Bug corrigé : CHROMA_URL configuré mais injoignable/en échec retombait
    # silencieusement sur LocalFactStore, sans aucune trace.
    monkeypatch.setenv("CHROMA_URL", "http://localhost:1")  # port fermé, échec de connexion
    session = _session()

    with caplog.at_level(logging.WARNING, logger="velmo.memory.vector_store"):
        store = get_fact_store(session)

    assert isinstance(store, LocalFactStore)
    assert any("Chroma" in r.message for r in caplog.records)
