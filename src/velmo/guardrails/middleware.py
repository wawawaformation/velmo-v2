"""Garde-fous en tant que middleware LangChain (`create_agent()`).

Réutilise `GuardrailEngine` tel quel — aucune logique de détection dupliquée.
`before_agent` court-circuite le graphe (une seule fois par tour utilisateur,
avant tout appel modèle) sur une entrée bloquée ; `after_agent` remplace la
réponse finale sur une sortie bloquée (une fois par tour, après la boucle
complète de tool-calling).
"""

from __future__ import annotations

from typing import TypeVar

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from . import GuardrailEngine

DEFAULT_REFUSAL = (
    "Désolé, je ne peux pas traiter cette demande. Je reste à votre disposition "
    "pour vos commandes, livraisons, retours et la FAQ Velmo."
)

_M = TypeVar("_M", bound=BaseMessage)


def _last_message_of_type(messages: list[BaseMessage], message_type: type[_M]) -> _M | None:
    for message in reversed(messages):
        if isinstance(message, message_type):
            return message
    return None


def _text_content(message: BaseMessage) -> str:
    """Contenu textuel d'un message — toujours `str` dans ce projet (pas de
    multimodal), mais `BaseMessage.content` est typé `str | list` chez
    LangChain (support des blocs multimodaux d'autres providers)."""
    content = message.content
    return content if isinstance(content, str) else str(content)


class GuardrailMiddleware(AgentMiddleware):
    """Applique `GuardrailEngine.check_input`/`check_output` autour du graphe."""

    def __init__(self, engine: GuardrailEngine) -> None:
        super().__init__()
        self.engine = engine
        # Un refus généré par before_agent (ex. « propos à caractère haineux
        # détecté ») peut lui-même être reclassifié comme contenu interdit
        # par check_output (le libellé de catégorie contient le mot-clé qui
        # a servi à le détecter) — after_agent ne doit jamais re-vérifier un
        # message qui est déjà le refus produit ce tour-ci, sans quoi le
        # second blocage écrase le premier par un message incohérent.
        self._blocked_input_this_turn = False

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state, runtime):
        message = _last_message_of_type(state["messages"], HumanMessage)
        if message is None:
            return None
        decision = self.engine.check_input(_text_content(message))
        if not decision.allowed:
            self._blocked_input_this_turn = True
            refusal = decision.refusal or DEFAULT_REFUSAL
            return {"messages": [AIMessage(refusal)], "jump_to": "end"}
        return None

    def after_agent(self, state, runtime):
        if self._blocked_input_this_turn:
            return None
        last_ai = _last_message_of_type(state["messages"], AIMessage)
        if last_ai is None:
            return None
        decision = self.engine.check_output(_text_content(last_ai))
        if not decision.allowed:
            refusal = decision.refusal or DEFAULT_REFUSAL
            return {"messages": [AIMessage(refusal, id=last_ai.id)]}
        return None
