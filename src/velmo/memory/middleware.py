"""Mémoire en tant que middleware LangChain (`create_agent()`).

Le contexte mémoire est lu une seule fois par tour utilisateur (`before_agent`)
et mis en cache dans l'état du graphe (`memory_context`) — pas une lecture par
étape interne de tool-calling. `wrap_model_call` relit cette valeur mise en
cache et l'injecte dans le prompt système à chaque appel modèle interne.
`after_agent` écrit le tour complet en mémoire une seule fois, une fois le
graphe terminé.
"""

from __future__ import annotations

from typing import NotRequired

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain_core.messages import AIMessage, HumanMessage

from . import MemoryManager


def _last_message_of_type(messages, message_type):
    for message in reversed(messages):
        if isinstance(message, message_type):
            return message
    return None


class MemoryAgentState(AgentState):
    """Étend l'état de l'agent avec le contexte mémoire mis en cache par tour."""

    memory_context: NotRequired[str]


class MemoryMiddleware(AgentMiddleware):
    """Injecte le contexte mémoire et écrit chaque tour via `MemoryManager`."""

    state_schema = MemoryAgentState

    def __init__(self, memory: MemoryManager, user_id: str) -> None:
        super().__init__()
        self.memory = memory
        self.user_id = user_id

    def before_agent(self, state, runtime):
        message = _last_message_of_type(state["messages"], HumanMessage)
        context = self.memory.read(self.user_id, message.content).render()
        return {"memory_context": context}

    def wrap_model_call(self, request, handler):
        context = request.state.get("memory_context", "")
        base_prompt = request.system_prompt or ""
        merged = f"{base_prompt}\nMémoire:\n{context}" if context else base_prompt
        return handler(request.override(system_prompt=merged))

    def after_agent(self, state, runtime):
        human = _last_message_of_type(state["messages"], HumanMessage)
        ai = _last_message_of_type(state["messages"], AIMessage)
        self.memory.write(self.user_id, human.content, ai.content)
        return None
