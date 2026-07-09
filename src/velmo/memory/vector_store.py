"""Mémoire sémantique à clé imprévisible : recherche par similarité (R2).

Backend Chroma si `CHROMA_URL` est configuré et joignable ; sinon repli sur un
backend relationnel local (`MemoryFact`) recherché par recouvrement de mots —
garantit un fonctionnement hors-ligne (CI sans réseau, sans extra `vector`).
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
import uuid
from urllib.parse import urlparse

from sqlalchemy import select

from velmo.db import MemoryFact

logger = logging.getLogger(__name__)


def _tokens(text: str) -> set[str]:
    """Normalise un texte en un ensemble de tokens (sans accents, courts exclus)."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return {t for t in re.findall(r"[a-z0-9]+", stripped.lower()) if len(t) > 1}


class LocalFactStore:
    """Repli relationnel, hors-ligne : recherche par recouvrement de tokens."""

    def __init__(self, session) -> None:
        self._session = session

    def add(self, user_id: str, key: str, value: str) -> None:
        """Persiste un fait à clé imprévisible pour l'utilisateur."""
        self._session.add(
            MemoryFact(id=str(uuid.uuid4()), user_id=user_id, key=key, value=value)
        )
        self._session.commit()

    def all_facts(self, user_id: str) -> list[tuple[str, str]]:
        """Renvoie tous les faits (clé, valeur) enregistrés pour l'utilisateur."""
        rows = self._session.execute(
            select(MemoryFact.key, MemoryFact.value).where(MemoryFact.user_id == user_id)
        ).all()
        return [(k, v) for k, v in rows]

    def search(self, user_id: str, query: str, k: int = 5) -> list[str]:
        """Renvoie les `k` faits les plus proches de `query` (recouvrement de tokens)."""
        q_tokens = _tokens(query)
        facts = self.all_facts(user_id)
        if not q_tokens:
            return [v for _, v in facts[:k]]
        scored = []
        for key, value in facts:
            overlap = len(q_tokens & _tokens(f"{key} {value}"))
            scored.append((overlap, value))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [v for score, v in scored[:k] if score > 0] or [v for _, v in facts[:k]]

    def delete_matching(self, user_id: str, target: str) -> int:
        """Supprime les faits dont la clé ou la valeur correspond à `target` (R5)."""
        rows = self._session.execute(
            select(MemoryFact).where(MemoryFact.user_id == user_id)
        ).scalars().all()
        removed = 0
        target_low = target.lower()
        for row in rows:
            if target_low in row.key.lower() or target_low in row.value.lower():
                self._session.delete(row)
                removed += 1
        if removed:
            self._session.commit()
        return removed


class ChromaFactStore:
    """Backend Chroma : embeddings + métadonnées `user_id`/`key`."""

    def __init__(self, collection) -> None:
        self._collection = collection

    def add(self, user_id: str, key: str, value: str) -> None:
        """Indexe un fait dans Chroma avec ses métadonnées `user_id`/`key`."""
        self._collection.add(
            ids=[str(uuid.uuid4())],
            documents=[value],
            metadatas=[{"user_id": user_id, "key": key}],
        )

    def search(self, user_id: str, query: str, k: int = 5) -> list[str]:
        """Renvoie les `k` faits les plus proches de `query` par similarité d'embeddings."""
        result = self._collection.query(
            query_texts=[query], n_results=k, where={"user_id": user_id}
        )
        docs = result.get("documents", [[]])[0]
        return list(docs)

    def all_facts(self, user_id: str) -> list[tuple[str, str]]:
        """Renvoie tous les faits (clé, valeur) indexés pour l'utilisateur."""
        result = self._collection.get(where={"user_id": user_id})
        docs = result.get("documents", [])
        metas = result.get("metadatas", [])
        return [((meta or {}).get("key", ""), doc) for doc, meta in zip(docs, metas)]

    def delete_matching(self, user_id: str, target: str) -> int:
        """Supprime les faits dont la clé ou le contenu correspond à `target` (R5)."""
        result = self._collection.get(where={"user_id": user_id})
        ids = result.get("ids", [])
        docs = result.get("documents", [])
        metas = result.get("metadatas", [])
        target_low = target.lower()
        to_delete = [
            id_
            for id_, doc, meta in zip(ids, docs, metas)
            if target_low in (meta or {}).get("key", "").lower() or target_low in doc.lower()
        ]
        if to_delete:
            self._collection.delete(ids=to_delete)
        return len(to_delete)


def get_fact_store(session):
    """Renvoie le backend Chroma si configuré/disponible, sinon le repli local."""
    chroma_url = os.getenv("CHROMA_URL")
    if not chroma_url:
        return LocalFactStore(session)
    try:
        import chromadb
        from chromadb.config import Settings
        from chromadb.utils import embedding_functions
    except ImportError:
        return LocalFactStore(session)

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
        embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        )
        collection = client.get_or_create_collection("velmo_memory", embedding_function=embedder)
    except Exception:
        logger.warning(
            "Chroma (CHROMA_URL=%s) injoignable ou en échec — repli sur "
            "LocalFactStore (relationnel, mémoire sémantique clé libre)", chroma_url,
            exc_info=True,
        )
        return LocalFactStore(session)
    return ChromaFactStore(collection)
