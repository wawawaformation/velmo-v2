"""Clients LLM : Azure AI Inference (Kimi-K2.6) et repli local hors-ligne.

L'import du SDK Azure est différé pour que le harness démarre et que les tests
tournent sans dépendre du SDK ni d'un endpoint joignable.
"""

from __future__ import annotations

import os
import time
from logging import getLogger
from typing import Protocol

from langchain_core.callbacks import BaseCallbackHandler

# Sans timeout explicite, le client Azure attend indéfiniment une réponse :
# un appel réseau bloqué gèle alors le tick du scheduler (memory/scheduler.py)
# et tous les ticks suivants sont skippés (max_instances=1), empilant les
# messages dans `message_brut` sans jamais les traiter.
LLM_TIMEOUT_SECONDS = 15

# Logger dédié (fichier séparé logs/llm_latency.log, câblé dans cli.py) :
# couvre tout appel LLM, chat principal comme classification/consolidation
# mémoire — via LangChainAdapter.invoke() (classifieur) ou
# LatencyCallbackHandler (chat principal, create_agent()).
_latency_logger = getLogger("velmo.llm.latency")


class LatencyCallbackHandler(BaseCallbackHandler):
    """Callback LangChain journalisant la latence des appels modèle.

    Nécessaire car `get_chat_model()` renvoie un `BaseChatModel` brut (exigé
    par `create_agent()`), non enveloppé par `LangChainAdapter` — sans ce
    callback, la latence du chat principal n'est plus journalisée depuis la
    migration vers `create_agent()`/`AgentMiddleware` (bug réel observé en
    rejouant `docs/script_presentation_demo_memoire.md`, Démo 3 : seul le
    classifieur, encore via `LangChainAdapter`, apparaissait dans le log).
    """

    def __init__(self) -> None:
        super().__init__()
        self._starts: dict = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        model_name = serialized.get("kwargs", {}).get("model_name", "unknown")
        self._starts[run_id] = (model_name, time.monotonic())

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        start = self._starts.pop(run_id, None)
        if start is None:
            return
        model_name, start_time = start
        latency_ms = (time.monotonic() - start_time) * 1000
        _latency_logger.info(
            "model=%s latency_ms=%.1f", model_name, latency_ms,
            extra={"latency_ms": latency_ms},
        )


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
        self._model_name = getattr(llm, "model", "unknown")
        # Template avec variables {system}, {context}, {message}
        prompt_template = PromptTemplate.from_template(
            "{system}\n"
            "{context}"
            "{message}"
        )
        self._chain = prompt_template | self._llm

    def invoke(self, system: str, context: str, message: str) -> str:
        """Appelle la chaîne Runnable avec les variables de prompt, logue la latence."""
        # Préparer les entrées pour le template
        context_str = f"Mémoire:\n{context}\n" if context else ""
        start = time.monotonic()
        result = self._chain.invoke({
            "system": system,
            "context": context_str,
            "message": message,
        })
        latency_ms = (time.monotonic() - start) * 1000
        _latency_logger.info(
            "model=%s latency_ms=%.1f", self._model_name, latency_ms,
            extra={"latency_ms": latency_ms},
        )
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
        timeout=LLM_TIMEOUT_SECONDS,
    )
    return LangChainAdapter(llm)


def get_chat_model():
    """Construit le vrai `BaseChatModel` Azure pour `create_agent()`, ou `None`.

    Distinct de `get_llm()` : `create_agent()` (tool-calling natif LangGraph)
    exige un `BaseChatModel` réel, pas le Protocol `LLM`/repli `EchoLLM` —
    un faux modèle ne peut pas décider quels outils appeler.
    """
    if not os.getenv("AZURE_AI_INFERENCE_ENDPOINT"):
        return None

    from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

    return AzureAIOpenAIApiChatModel(
        endpoint=os.environ["AZURE_AI_INFERENCE_ENDPOINT"],
        credential=os.environ["AZURE_AI_INFERENCE_API_KEY"],
        model=os.environ.get("AZURE_AI_INFERENCE_MODEL", "Kimi-K2.6"),
        timeout=LLM_TIMEOUT_SECONDS,
    )


def get_classifier_llm() -> LLM:
    """Construit le client Azure du classifier mémoire (modèle dédié), sinon `EchoLLM`.

    `max_retries=0` : le SDK OpenAI retente 2 fois par défaut, ce qui peut
    tripler la latence d'un échec (jusqu'à 3 × `LLM_TIMEOUT_SECONDS`, observé
    à 16-32s en usage réel). Ce classifieur est désormais appelé de façon
    synchrone dans le chemin critique de chaque réponse (`GuardrailMiddleware`,
    cascade de modération), pas seulement en tâche de fond — un échec doit
    retomber vite sur le repli règles plutôt que de bloquer l'utilisateur.
    """
    if not os.getenv("AZURE_AI_INFERENCE_ENDPOINT") or not os.getenv("AZURE_AI_CLASSIFIER_MODEL"):
        return EchoLLM()

    from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

    llm = AzureAIOpenAIApiChatModel(
        endpoint=os.environ["AZURE_AI_INFERENCE_ENDPOINT"],
        credential=os.environ["AZURE_AI_INFERENCE_API_KEY"],
        model=os.environ["AZURE_AI_CLASSIFIER_MODEL"],
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )
    return LangChainAdapter(llm)
