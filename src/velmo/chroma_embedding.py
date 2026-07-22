"""Embedding function Chroma sans barre de progression tqdm.

`SentenceTransformerEmbeddingFunction.__call__` (chromadb) appelle
`encode()` sans `show_progress_bar=False`, ce qui affiche une barre tqdm
("Batches: 100%|...") dans le CLI interactif à chaque recherche mémoire.
"""

from __future__ import annotations

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


class SilentSentenceTransformerEmbeddingFunction(SentenceTransformerEmbeddingFunction):
    """Identique à la classe parente, sans barre de progression tqdm."""

    def __call__(self, input):
        return [
            embedding
            for embedding in self._model.encode(
                list(input),
                convert_to_numpy=True,
                normalize_embeddings=self._normalize_embeddings,
                show_progress_bar=False,
            )
        ]
