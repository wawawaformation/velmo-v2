"""Test de la barre de progression tqdm désactivée pour l'embedder mémoire.

Bug corrigé : `SentenceTransformerEmbeddingFunction.__call__` appelle
`SentenceTransformer.encode()` sans `show_progress_bar=False`, ce qui
affiche une barre `tqdm` ("Batches: 100%|...") dans le CLI interactif à
chaque recherche mémoire — effet de bord du fix Chroma (`chroma_telemetry.py`),
qui a rendu Chroma réellement sollicité à chaque `read()`/`write()`.
"""

from __future__ import annotations

from velmo.chroma_embedding import SilentSentenceTransformerEmbeddingFunction


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def encode(self, sentences, **kwargs):
        self.calls.append(kwargs)
        return [[0.1, 0.2] for _ in sentences]


def test_call_passes_show_progress_bar_false_to_encode():
    embedder = SilentSentenceTransformerEmbeddingFunction.__new__(
        SilentSentenceTransformerEmbeddingFunction
    )
    embedder._model = FakeModel()
    embedder._normalize_embeddings = False

    embedder(["un document"])

    assert embedder._model.calls[0]["show_progress_bar"] is False
