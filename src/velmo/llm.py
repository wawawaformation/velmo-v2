"""Clients LLM : Azure AI Inference (Kimi-K2.6) et repli local hors-ligne.

L'import du SDK Azure est différé pour que le harness démarre et que les tests
tournent sans dépendre du SDK ni d'un endpoint joignable.
"""

from __future__ import annotations

import os
from typing import Protocol


class LLM(Protocol):
    """Interface minimale d'un client de complétion."""

    def invoke(self, system: str, context: str, message: str) -> str: ...


class EchoLLM:
    """Repli déterministe et hors-ligne : renvoie un accusé de réception.

    Permet au harness de conversation de démarrer sans identifiants Azure.
    """

    def invoke(self, system: str, context: str, message: str) -> str:
        return f"[velmo] J'ai bien reçu : {message}"


class LangChainAdapter:
    """Encapsule ChatAzureOpenAI + LangChain Runnable à l'interface LLM."""

    def __init__(self, llm) -> None:
        from langchain_core.prompts import PromptTemplate

        self._llm = llm
        # Template avec variables {system}, {context}, {message}
        prompt_template = PromptTemplate.from_template(
            "{system}\n"
            "{context}"
            "{message}"
        )
        self._chain = prompt_template | self._llm

    def invoke(self, system: str, context: str, message: str) -> str:
        """Appelle la chaîne Runnable avec les variables de prompt."""
        # Préparer les entrées pour le template
        context_str = f"Mémoire:\n{context}\n" if context else ""
        result = self._chain.invoke({
            "system": system,
            "context": context_str,
            "message": message,
        })
        return result.content


def get_llm() -> LLM:
    """Construit le client Azure si configuré, sinon le repli `EchoLLM`."""
    if not os.getenv("AZURE_AI_INFERENCE_ENDPOINT"):
        return EchoLLM()

    from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

    llm = AzureAIOpenAIApiChatModel(
        endpoint=os.environ["AZURE_AI_INFERENCE_ENDPOINT"],
        credential=os.environ["AZURE_AI_INFERENCE_API_KEY"],
        model=os.environ.get("AZURE_AI_INFERENCE_MODEL", "Kimi-K2.6"),
    )
    return LangChainAdapter(llm)


def get_classifier_llm() -> LLM:
    """Construit le client Azure du classifier mémoire (modèle dédié), sinon `EchoLLM`."""
    if not os.getenv("AZURE_AI_INFERENCE_ENDPOINT") or not os.getenv("AZURE_AI_CLASSIFIER_MODEL"):
        return EchoLLM()

    from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

    llm = AzureAIOpenAIApiChatModel(
        endpoint=os.environ["AZURE_AI_INFERENCE_ENDPOINT"],
        credential=os.environ["AZURE_AI_INFERENCE_API_KEY"],
        model=os.environ["AZURE_AI_CLASSIFIER_MODEL"],
    )
    return LangChainAdapter(llm)
