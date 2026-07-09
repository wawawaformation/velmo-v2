"""Tests d'acceptance — chantier Mémoire (contexte boutique collector)."""

from __future__ import annotations

from velmo.agent import Agent
from velmo.guardrails import GuardrailEngine
from velmo.memory import MemoryManager


class CapturingLLM:
    """LLM factice qui renvoie tel quel le contexte reçu (pour vérifier qu'il n'est pas vide)."""

    def invoke(self, system: str, context: str, message: str) -> str:
        return context


def test_recall_over_30_turns():
    # Critère R1 : info du 1er tour restituée après 30+ tours.
    mm = MemoryManager()
    user = "acc-recall"
    mm.write(user, "Ma commande prioritaire est O-2024-0101.", "C'est noté.")
    mm.run_pending_job(user)  # distille vers le long terme avant que le fil court terme ne tronque
    for i in range(30):
        mm.write(user, f"Question de suivi {i} sur un maillot.", f"Réponse {i}.")

    rendered = mm.read(user, "Quelle était ma commande prioritaire ?").render()
    assert "O-2024-0101" in rendered


def test_cross_session_persistence():
    # Critère R2 : pointure, clubs et segment retrouvés une session plus tard.
    session1 = MemoryManager()
    session1.remember_fact("acc-marc", "pointure", "L")
    session1.remember_fact("acc-marc", "clubs", "OM et Brésil")
    session1.remember_fact("acc-marc", "segment", "revendeur")

    session2 = MemoryManager()  # nouvelle session, même client
    rendered = session2.read("acc-marc", "Tu te souviens de moi ?").render()
    assert "L" in rendered
    assert "OM" in rendered
    assert "revendeur" in rendered


def test_isolation_between_customers():
    # Critère R3 : Marc ne voit jamais les commandes de Sophie.
    mm = MemoryManager()
    mm.remember_fact("acc-marc", "commande", "O-2024-0103")
    mm.remember_fact("acc-sophie", "commande", "O-2024-0107")

    rendered_sophie = mm.read("acc-sophie", "Mes commandes ?").render()
    assert "O-2024-0107" in rendered_sophie
    assert "O-2024-0103" not in rendered_sophie


def test_right_to_be_forgotten():
    # Critère R5 : « oublie mon adresse » supprime effectivement l'information.
    mm = MemoryManager()
    user = "acc-forget"
    mm.write(user, "Mon adresse de livraison est 12 rue des Lilas.", "C'est noté.")
    # Simule le passage du job périodique (cf. choix.md : capture synchrone,
    # traitement asynchrone) qui classe/route le message vers le long terme.
    mm.run_pending_job(user)

    assert "rue des Lilas" in mm.read(user, "Mon adresse ?").render()

    removed = mm.forget(user, "adresse")
    assert removed >= 1
    assert "rue des Lilas" not in mm.read(user, "Mon adresse ?").render()


def test_forget_removes_consolidated_episode_even_without_text_match():
    # R5 : un épisode consolidé doit être purgé par sa clé de consolidation,
    # pas seulement par correspondance textuelle — le texte nettoyé par le LLM
    # ne contient pas forcément le mot cible ("pointure" n'apparaît nulle part).
    from velmo.memory import episodic as episodic_module
    from velmo.memory import semantic as semantic_module

    mm = MemoryManager()
    user = "acc-forget-consolidated-episode"
    semantic_module.set_known_fact(mm._session, user, "pointure", "43")
    episodic_module.add_episode(
        mm._session, user, "Chausse du 43", consolidated_key="pointure"
    )

    removed = mm.forget(user, "pointure")

    assert removed >= 1
    remaining = episodic_module.list_episodes(mm._session, user, include_consolidated=True)
    assert remaining == []


def test_agent_injects_memory_context_into_llm_fallback():
    # Non-régression : Agent.respond() doit transmettre le contexte mémoire au
    # LLM pour toute question hors routage déterministe (sinon R1 est tenu par
    # MemoryManager mais invisible pour l'utilisateur final, cf. bug agent.py
    # où `self.memory.read(...)` était appelé puis son résultat jeté).
    agent = Agent(
        llm=CapturingLLM(),
        memory=MemoryManager(),
        guardrails=GuardrailEngine(),
    )
    user = "acc-agent-context"

    agent.respond(user, "Bonjour, j'ai 50 ans, je suis né le 07/09/1975.")
    reply = agent.respond(user, "Une question quelconque hors commande.")

    assert "50 ans" in reply
