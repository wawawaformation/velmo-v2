"""Modèle de chat factice pour tester `create_agent()` hors-ligne.

`FakeMessagesListChatModel` (LangChain) cycle à travers une liste de réponses
scriptées, mais ne supporte pas `bind_tools()` par défaut (lève
`NotImplementedError`), ce qui bloque tout usage avec `create_agent()` dès
qu'un outil est enregistré. `ScriptedToolCallingModel` surcharge `bind_tools`
pour un no-op (le choix d'appeler un outil est déjà déterminé par le script
des réponses, pas par un vrai raisonnement du modèle).
"""

from __future__ import annotations

from pydantic import Field

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel


class ScriptedToolCallingModel(FakeMessagesListChatModel):
    """`FakeMessagesListChatModel` utilisable avec `create_agent()` (tools liés)."""

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


class CapturingToolCallingModel(ScriptedToolCallingModel):
    """Variante qui garde en mémoire les messages reçus à chaque appel.

    Sert à vérifier que le contexte mémoire (injecté par `MemoryMiddleware`
    dans le prompt système) atteint bien le modèle à chaque tour — sans
    dépendre du texte de réponse produit par le LLM.
    """

    captured_messages: list = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.captured_messages.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
