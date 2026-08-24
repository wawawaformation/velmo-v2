"""Ingestion de la FAQ Velmo (kb/docs/*.md) dans Chroma.

Usage : uv run python scripts/seed_kb.py
Nécessite l'extra `vector` (chromadb + sentence-transformers) et un service Chroma.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

KB_DOCS_DIR = Path(__file__).resolve().parent.parent / "kb" / "docs"


def main() -> None:
    load_dotenv()

    import chromadb
    from chromadb.utils import embedding_functions

    chroma_url = os.getenv("CHROMA_URL")
    if chroma_url:
        # Même logique que kb_store.get_kb() : host/port/ssl dérivés de l'URL
        # (nécessaire pour Chroma exposé en HTTPS, ex. Azure App Service).
        parsed = urlparse(chroma_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 8000)
        ssl = parsed.scheme == "https"
    else:
        host = os.getenv("CHROMA_HOST", "chroma")
        port = int(os.getenv("CHROMA_PORT", "8000"))
        ssl = False

    client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
    embedder = embedding_functions.SentenceTransformerEmbeddingFunction(  # type: ignore[attr-defined]
        model_name=os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    )
    collection = client.get_or_create_collection("velmo_faq", embedding_function=embedder)

    docs, ids, metas = [], [], []
    for path in sorted(KB_DOCS_DIR.glob("*.md")):
        docs.append(path.read_text(encoding="utf-8"))
        ids.append(path.stem)
        metas.append({"source": path.name})

    collection.upsert(documents=docs, ids=ids, metadatas=metas)
    print(f"FAQ ingérée dans Chroma : {len(docs)} documents.")


if __name__ == "__main__":
    main()
