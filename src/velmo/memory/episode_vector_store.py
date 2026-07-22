"""Vector store épisodique : regroupement des épisodes par unité de sens.

Skill semantic-episodic-memory : la mémoire épisodique combine base
relationnelle (recherche par mots-clés, `episodic.py`) et vector store associé
(recherche par similarité de sens). Backend Chroma si `CHROMA_URL` est
configuré et joignable ; sinon repli local par recouvrement de tokens (même
pattern que `vector_store.py`, garantit un fonctionnement hors-ligne).
"""

from __future__ import annotations

import logging
import os
import uuid
from urllib.parse import urlparse

from . import episodic
from .vector_store import _tokens

logger = logging.getLogger(__name__)


class LocalEpisodeStore:
    """Repli hors-ligne : réutilise `memory_episodes` (pas de nouvelle table),
    avec un tri par recouvrement de tokens (plus proche d'une similarité de
    sens que `search_episodes`, qui ne fait que filtrer sans classer)."""

    def __init__(self, session) -> None:
        self._session = session

    def add(self, user_id: str, contenu: str, consolidated: bool = False) -> None:
        """No-op : l'épisode est déjà persisté par `episodic.add_episode`."""

    def search(self, user_id: str, query: str, k: int = 5) -> list[str]:
        """Renvoie les `k` épisodes non consolidés les plus proches de `query`."""
        q_tokens = _tokens(query)
        candidates = episodic.list_episodes(self._session, user_id)
        if not q_tokens:
            return candidates[:k]
        scored = [(len(q_tokens & _tokens(c)), c) for c in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored[:k] if score > 0]

    def delete_matching(self, user_id: str, target: str) -> int:
        """No-op : la suppression est déjà gérée par `episodic.delete_matching`."""
        return 0


class ChromaEpisodeStore:
    """Backend Chroma dédié aux épisodes : embeddings + métadonnées `user_id`/`consolidated`."""

    def __init__(self, collection) -> None:
        self._collection = collection

    def add(self, user_id: str, contenu: str, consolidated: bool = False) -> None:
        """Indexe un épisode dans Chroma."""
        self._collection.add(
            ids=[str(uuid.uuid4())],
            documents=[contenu],
            metadatas=[{"user_id": user_id, "consolidated": consolidated}],
        )

    def search(self, user_id: str, query: str, k: int = 5) -> list[str]:
        """Renvoie les `k` épisodes non consolidés les plus proches de `query`."""
        result = self._collection.query(
            query_texts=[query],
            n_results=k,
            where={"$and": [{"user_id": user_id}, {"consolidated": False}]},
        )
        docs = result.get("documents", [[]])[0]
        return list(docs)

    def delete_matching(self, user_id: str, target: str) -> int:
        """Supprime les épisodes indexés dont le contenu correspond à `target` (R5)."""
        result = self._collection.get(where={"user_id": user_id})
        ids = result.get("ids", [])
        docs = result.get("documents", [])
        target_low = target.lower()
        to_delete = [id_ for id_, doc in zip(ids, docs) if target_low in doc.lower()]
        if to_delete:
            self._collection.delete(ids=to_delete)
        return len(to_delete)


def get_episode_store(session):
    """Renvoie le backend Chroma si configuré/disponible, sinon le repli local."""
    chroma_url = os.getenv("CHROMA_URL")
    if not chroma_url:
        return LocalEpisodeStore(session)
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        return LocalEpisodeStore(session)

    from velmo.chroma_embedding import SilentSentenceTransformerEmbeddingFunction

    parsed = urlparse(chroma_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 8000)
    ssl = parsed.scheme == "https"

    try:
        settings = Settings(
            anonymized_telemetry=False,
            chroma_product_telemetry_impl="velmo.chroma_telemetry.NoOpProductTelemetry",
            chroma_telemetry_impl="velmo.chroma_telemetry.NoOpProductTelemetry",
        )
        client = chromadb.HttpClient(host=host, port=port, ssl=ssl, settings=settings)
        embedder = SilentSentenceTransformerEmbeddingFunction(
            model_name=os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        )
        collection = client.get_or_create_collection("velmo_episodes", embedding_function=embedder)
    except Exception:
        logger.warning(
            "Chroma (CHROMA_URL=%s) injoignable ou en échec — repli sur "
            "LocalEpisodeStore (relationnel, mémoire épisodique)", chroma_url,
            exc_info=True,
        )
        return LocalEpisodeStore(session)
    return ChromaEpisodeStore(collection)
