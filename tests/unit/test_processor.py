"""Tests unitaires de process_pending : capture épisodique systématique + consolidation.

Modèle retenu (skill semantic-episodic-memory) : chaque message en attente est
toujours écrit en épisodique (nettoyage léger) ; un seul appel LLM (via
`consolidate`) décide en plus si un fait sémantique généralisable doit être
consolidé (colonne connue ou vecteur), en plus de l'épisode — pas à sa place.
"""

from __future__ import annotations

from velmo.db import fresh_sqlite_session
from velmo.memory import buffer, episodic, processor, semantic
from velmo.memory.episode_vector_store import LocalEpisodeStore


class FakeLLM:
    """LLM factice renvoyant une réponse fixe (format consolidation JSON)."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def invoke(self, system: str, context: str, message: str) -> str:
        self.calls += 1
        return self.response


def _session():
    return fresh_sqlite_session()


def test_process_pending_always_creates_an_episode():
    session = _session()
    buffer.capture(session, "u1", "user", "Où en est ma commande O-2024-0103 ?")
    llm = FakeLLM(
        '{"episode": "Client demande le statut de sa commande O-2024-0103", "semantic": null}'
    )

    processor.process_pending(session, "u1", llm=llm)

    assert episodic.list_episodes(session, "u1") == [
        "Client demande le statut de sa commande O-2024-0103"
    ]


def test_process_pending_consolidates_semantic_fact_alongside_episode():
    session = _session()
    buffer.capture(session, "u1", "user", "Ma pointure de chaussure c'est du 43.")
    llm = FakeLLM(
        '{"episode": "Pointure du client : 43",'
        ' "semantic": {"destination": "semantic_column", "key": "pointure", "value": "43"}}'
    )

    processor.process_pending(session, "u1", llm=llm)

    assert semantic.get_known_facts(session, "u1") == {"pointure": "43"}
    # L'épisode source reste en base (trace d'audit) mais n'est plus listé par défaut.
    assert episodic.list_episodes(session, "u1") == []
    assert episodic.list_episodes(session, "u1", include_consolidated=True) == [
        "Pointure du client : 43"
    ]


def test_process_pending_marks_consolidated_episode_with_its_key():
    session = _session()
    buffer.capture(session, "u1", "user", "Ma pointure de chaussure c'est du 43.")
    llm = FakeLLM(
        '{"episode": "Pointure du client : 43",'
        ' "semantic": {"destination": "semantic_column", "key": "pointure", "value": "43"}}'
    )

    processor.process_pending(session, "u1", llm=llm)

    removed = episodic.delete_by_consolidated_key(session, "u1", "pointure")
    assert removed == 1


def test_process_pending_clears_buffer_after_processing():
    session = _session()
    buffer.capture(session, "u1", "user", "Un message quelconque")
    llm = FakeLLM('{"episode": "Un message quelconque", "semantic": null}')

    processor.process_pending(session, "u1", llm=llm)

    assert buffer.pending_for(session, "u1") == []


def test_process_pending_episode_is_searchable_via_episode_vector_store():
    session = _session()
    buffer.capture(session, "u1", "user", "Où en est ma commande O-2024-0103 ?")
    llm = FakeLLM(
        '{"episode": "Client demande le statut de sa commande O-2024-0103", "semantic": null}'
    )

    processor.process_pending(session, "u1", llm=llm)

    episode_store = LocalEpisodeStore(session)
    assert episode_store.search("u1", "commande") == [
        "Client demande le statut de sa commande O-2024-0103"
    ]


class FlakyLLM:
    """LLM factice qui échoue sur les messages contenant `fail_marker`."""

    def __init__(self, response: str, fail_marker: str) -> None:
        self.response = response
        self.fail_marker = fail_marker

    def invoke(self, system: str, context: str, message: str) -> str:
        if self.fail_marker in message:
            raise TimeoutError("Request timed out.")
        return self.response


def test_process_pending_isolates_failures_between_messages():
    # Bug réel observé : un timeout LLM (openai.APITimeoutError en usage réel)
    # sur UN message du batch bloquait indéfiniment TOUS les messages en
    # attente du même utilisateur — buffer.delete() n'était appelé qu'après
    # la boucle complète, jamais atteint si un message échouait avant la fin.
    session = _session()
    buffer.capture(session, "u1", "user", "Message qui va échouer")
    buffer.capture(session, "u1", "user", "Message qui doit réussir")
    llm = FlakyLLM(
        '{"episode": "Message qui doit réussir", "semantic": null}',
        fail_marker="échouer",
    )

    processor.process_pending(session, "u1", llm=llm)

    # Le message réussi est traité et purgé du tampon...
    assert episodic.list_episodes(session, "u1") == ["Message qui doit réussir"]
    pending = [row.contenu for row in buffer.pending_for(session, "u1")]
    assert "Message qui doit réussir" not in pending
    # ...le message en échec reste en attente pour être retenté au tick suivant.
    assert "Message qui va échouer" in pending


def test_process_pending_links_episode_to_semantic_by_key_not_text_match():
    # Le texte épisodique nettoyé par le LLM ne contient PAS littéralement "pointure"
    # (le mot n'apparaît nulle part) — seul consolidated_key permet de relier
    # l'épisode source au fait sémantique dérivé pour un oubli complet (R5).
    session = _session()
    buffer.capture(session, "u1", "user", "Je porte du 43 comme godasses.")
    llm = FakeLLM(
        '{"episode": "Chausse du 43",'
        ' "semantic": {"destination": "semantic_column", "key": "pointure", "value": "43"}}'
    )

    processor.process_pending(session, "u1", llm=llm)

    episode_text = episodic.list_episodes(session, "u1", include_consolidated=True)[0]
    assert "pointure" not in episode_text.lower()
    removed = episodic.delete_by_consolidated_key(session, "u1", "pointure")
    assert removed == 1
