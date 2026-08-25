"""Agent Velmo 2.0 : agent LangGraph à tool-calling (`create_agent()`).

Garde-fous (`GuardrailMiddleware`) et mémoire (`MemoryMiddleware`) sont
implémentés comme `AgentMiddleware`, câblés autour du LLM et des outils
métier. Le routage n'est plus déterministe (regex) : c'est le LLM qui
décide quels outils appeler, à partir du prompt système et de la
conversation.
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from .guardrails import GuardrailEngine
from .guardrails.middleware import GuardrailMiddleware
from .llm import LatencyCallbackHandler
from .memory import MemoryManager
from .memory.middleware import MemoryMiddleware
from .tools.binding import bound_tools

SYSTEM_PROMPT = (
    "Tu es l'assistant de support de Velmo, boutique de maillots de foot collector. "
    "Tu traites la gestion de commandes de niveau 1 avec courtoisie et précision.\n\n"
    "Périmètre : suivi de commande, statut, modification (taille, adresse) tant que "
    "la commande n'est pas expédiée, annulation, retour/échange, remboursement, "
    "disponibilité en stock, questions FAQ (livraison, retours, authenticité, "
    "paiement, garantie). Toute autre demande (valorisation financière, conseil "
    "juridique, authentification d'un article acheté ailleurs) est hors périmètre : "
    "décline poliment et propose ton aide sur ce que tu couvres.\n\n"
    "Questions FAQ : appuie-toi sur les extraits renvoyés par `search_kb` et reste "
    "FIDÈLE à leur contenu — reprends leurs termes et leurs chiffres tels quels. Ne "
    "les contredis jamais, ne les complète pas par tes propres estimations et "
    "n'extrapole pas au-delà de ce qu'ils affirment. Si un extrait indique qu'une "
    "chose n'existe pas ou n'est pas possible, dis-le clairement au lieu de la "
    "nuancer. Si la base de connaissances ne couvre pas la question, dis-le plutôt "
    "que d'inventer une réponse.\n\n"
    "Avant toute action qui modifie une commande (annulation, changement d'adresse, "
    "changement de taille, retour, remboursement), tu dois demander une confirmation "
    "explicite au client et ne PAS appeler l'outil correspondant tant que le message "
    "du client ne contient pas à la fois l'intention et une formule de confirmation "
    "(« je confirme », « oui, vas-y », etc.) dans le MÊME message.\n\n"
    "Exception : le droit à l'oubli. Si le client demande d'oublier une information "
    "le concernant (« oublie mon adresse », « oublie mon numéro de commande »), "
    "appelle immédiatement l'outil `forget_memory` avec l'information visée, SANS "
    "demander de confirmation — c'est un droit RGPD, pas une action à négocier."
)


class Agent:
    """Assistant de support adossé à un agent LangGraph à tool-calling."""

    def __init__(self, model, memory: MemoryManager, guardrails: GuardrailEngine, session=None, kb=None) -> None:
        self.model = model
        self.memory = memory
        self.guardrails = guardrails
        self.session = session
        self.kb = kb

    def respond(self, user_id: str, message: str) -> str:
        tools_list = bound_tools(self.session, user_id, self.kb, self.memory)
        graph = create_agent(
            model=self.model,
            tools=tools_list,
            system_prompt=SYSTEM_PROMPT,
            middleware=[
                GuardrailMiddleware(self.guardrails),
                MemoryMiddleware(self.memory, user_id),
            ],
        )
        result = graph.invoke(
            {"messages": [HumanMessage(message)]},
            config={"callbacks": [LatencyCallbackHandler()]},
        )
        return result["messages"][-1].content


def build_default_agent(session=None, kb=None, temperature: float | None = None) -> Agent:
    """Assemble un agent avec composants par défaut, base et FAQ.

    `temperature` est transmis à `get_chat_model()` : `None` en production
    (défaut du modèle), `0` pour l'évaluation MLOps (note reproductible).
    """
    from .db import session_factory
    from .kb_store import get_kb
    from .llm import get_chat_model

    if session is None:
        session = session_factory()()
    if kb is None:
        kb = get_kb()
    model = get_chat_model(temperature=temperature)
    if model is None:
        raise RuntimeError(
            "Identifiants Azure requis pour démarrer l'agent — configurez "
            "AZURE_AI_INFERENCE_ENDPOINT/AZURE_AI_INFERENCE_API_KEY."
        )
    return Agent(
        model=model,
        memory=MemoryManager(),
        guardrails=GuardrailEngine(),
        session=session,
        kb=kb,
    )
