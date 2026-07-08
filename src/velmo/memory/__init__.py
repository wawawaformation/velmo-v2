"""Mémoire de l'agent Velmo : contexte court terme et mémoire long terme.

Quatre briques (cf. `conception/memoire/choix.md`) :
- court terme (RAM, fil de la session) : `short_term.py`
- tampon de capture synchrone (`MessageBrut`) : `buffer.py`
- long terme sémantique (colonne connue ou vectoriel) : `semantic.py` / `vector_store.py`
- long terme épisodique (relationnel, recherche par mots-clés) : `episodic.py`

Isolation stricte par `user_id` sur toutes les opérations (R3).

Capture vs traitement (R2) : `write()` ne fait que la capture synchrone dans
`MessageBrut` (aucun appel LLM, latence quasi nulle). Le classement/routage vers
le long terme (colonne connue, vectoriel ou épisodique) est un job séparé,
`run_pending_job()`, à déclencher explicitement — un vrai scheduler périodique
(APScheduler/Celery beat) l'appellerait à intervalle régulier en prod ; en tests
et en dev, on l'appelle à la demande pour simuler ce passage. Ce découplage
explicite (pas d'appel caché dans `write()`) reflète fidèlement l'architecture
« capture synchrone / traitement asynchrone » décrite dans `choix.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import buffer, episodic, semantic, short_term, storage
from .processor import process_pending
from .vector_store import get_fact_store

Turn = tuple[str, str]  # (role, content)


@dataclass
class MemoryContext:
    """Contexte mémoire restitué pour une requête utilisateur."""

    history: list[Turn] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)
    episodic: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Sérialise le contexte en texte (injectable dans un prompt)."""
        parts: list[str] = []
        for role, content in self.history:
            parts.append(f"{role}: {content}")
        for key, value in self.facts.items():
            parts.append(f"fact:{key}={value}")
        parts.extend(self.episodic)
        return "\n".join(parts)


class MemoryManager:
    """Orchestre la mémoire court terme et long terme, isolée par utilisateur."""

    def __init__(self) -> None:
        self._session = storage.new_session()

    def read(self, user_id: str, message: str) -> MemoryContext:
        """Reconstitue le contexte mémoire pertinent pour `message`."""
        history = short_term.get_turns(user_id)
        known_facts = semantic.get_known_facts(self._session, user_id)

        store = get_fact_store(self._session)
        vector_hits = store.search(user_id, message)

        episodes = episodic.search_episodes(self._session, user_id, message)

        return MemoryContext(history=history, facts=known_facts, episodic=vector_hits + episodes)

    def write(self, user_id: str, user_message: str, assistant_message: str) -> None:
        """Met à jour la mémoire à partir d'un échange (capture synchrone uniquement).

        Le classement/routage vers le long terme n'a pas lieu ici : voir `run_pending_job`.
        """
        short_term.append(user_id, "user", user_message)
        short_term.append(user_id, "assistant", assistant_message)

        buffer.capture(self._session, user_id, "user", user_message)

    def run_pending_job(self, user_id: str) -> None:
        """Déclenche le traitement du tampon en attente pour `user_id`.

        En prod, un scheduler périodique (APScheduler/Celery beat) appellerait ceci
        à intervalle régulier, par utilisateur. Ici, le déclenchement est explicite.
        """
        process_pending(self._session, user_id)

    def run_pending_job_all_users(self) -> None:
        """Traite le tampon en attente pour tous les utilisateurs distincts.

        Point d'entrée appelé par le scheduler périodique (`memory/scheduler.py`) :
        contrairement à `run_pending_job`, ne cible pas un `user_id` précis — il
        balaie tout `MessageBrut`, mais traite chaque utilisateur séparément
        (isolation R3, aucun mélange de contenu entre deux clients dans un même appel).
        """
        for user_id in buffer.pending_user_ids(self._session):
            process_pending(self._session, user_id)

    def remember_fact(self, user_id: str, key: str, value: str) -> None:
        """Persiste un fait durable sur l'utilisateur (écriture directe, sans passer par le tampon)."""
        if key in semantic.KNOWN_KEYS:
            semantic.set_known_fact(self._session, user_id, key, value)
        else:
            store = get_fact_store(self._session)
            store.add(user_id, key, value)

    def forget(self, user_id: str, target: str) -> int:
        """Supprime les souvenirs correspondant à `target`. Renvoie le nombre supprimé."""
        removed = 0
        removed += short_term.purge_matching(user_id, target)
        removed += semantic.clear_matching(self._session, user_id, target)
        store = get_fact_store(self._session)
        removed += store.delete_matching(user_id, target)
        removed += episodic.delete_matching(self._session, user_id, target)
        removed += buffer.delete_matching(self._session, user_id, target)
        return removed

    def close(self) -> None:
        """Ferme la session DB sous-jacente (libère la connexion du pool)."""
        self._session.close()

    def inspect(self, user_id: str) -> dict:
        """Renvoie l'état mémoire d'un utilisateur (faits + souvenirs épisodiques)."""
        known_facts = semantic.get_known_facts(self._session, user_id)
        store = get_fact_store(self._session)
        vector_facts = store.all_facts(user_id) if hasattr(store, "all_facts") else []
        episodes = episodic.list_episodes(self._session, user_id)
        return {
            "facts": {**known_facts, **dict(vector_facts)},
            "episodic": episodes,
        }
