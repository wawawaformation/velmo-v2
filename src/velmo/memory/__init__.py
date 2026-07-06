"""Mémoire de l'agent Velmo : contexte court terme et mémoire long terme.

Quatre briques (cf. `conception/memoire/choix.md`) :
- court terme (RAM, fil de la session) : `short_term.py`
- tampon de capture synchrone (`MessageBrut`) : `buffer.py`
- long terme sémantique (colonne connue ou vectoriel) : `semantic.py` / `vector_store.py`
- long terme épisodique (relationnel, recherche par mots-clés) : `episodic.py`

Isolation stricte par `user_id` sur toutes les opérations (R3).
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

    def __init__(self, *, token_budget: int = 2000) -> None:
        self.token_budget = token_budget
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
        """Met à jour la mémoire à partir d'un échange."""
        short_term.append(user_id, "user", user_message)
        short_term.append(user_id, "assistant", assistant_message)

        buffer.capture(self._session, user_id, "user", user_message)
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
