"""Tests unitaires de `get_kb()` — vérifie l'absence de la barre tqdm en mode Chroma.

Bug réel observé en usage (rejeu du script de démo mémoire) : `search_kb`
(question FAQ) affichait une barre `Batches: 100%|...` dans le CLI interactif,
alors que ce bruit avait déjà été corrigé pour `get_episode_store`/
`get_fact_store` (`chroma_embedding.py`). `get_kb()` utilisait encore la
classe bruyante standard — la recherche FAQ passe bien par un chemin
interactif (`search_kb` appelé pendant la conversation), pas seulement par
l'indexation hors-ligne (`seed_kb.py`) comme supposé initialement.
"""

from __future__ import annotations

import pytest

pytest.importorskip("chromadb")

from velmo.kb_store import get_kb, ChromaKB


def test_get_kb_uses_silent_embedding_function(monkeypatch):
    monkeypatch.setenv("CHROMA_URL", "http://localhost:8001")

    kb = get_kb()

    # Skip if Chroma is not accessible (returns LocalKB fallback)
    if not isinstance(kb, ChromaKB):
        pytest.skip("ChromaDB not accessible, using LocalKB fallback")

    from velmo.chroma_embedding import SilentSentenceTransformerEmbeddingFunction

    assert isinstance(kb._collection._embedding_function, SilentSentenceTransformerEmbeddingFunction)
