"""Accès DB dédié à la mémoire long terme (partagé entre instances `MemoryManager`)."""

from __future__ import annotations

from velmo.db import memory_session_factory


def new_session():
    """Ouvre une session sur le stockage mémoire partagé (SQLite fichier ou Postgres)."""
    factory = memory_session_factory()
    return factory()
