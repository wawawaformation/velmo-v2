"""Tests du logging de latence des appels LLM (fichier dédié logs/llm_latency.log).

Couvre tous les appels LLM (chat principal et classification/consolidation
mémoire), car tous passent par `LangChainAdapter.invoke()`.
"""

from __future__ import annotations

import logging

from velmo.llm import LangChainAdapter

LATENCY_LOGGER_NAME = "velmo.llm.latency"


class FakeContent:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChain:
    """Simule le Runnable LangChain (prompt | llm) sans dépendre du SDK Azure."""

    def __init__(self, response: str = "réponse factice") -> None:
        self.response = response

    def invoke(self, inputs: dict) -> FakeContent:
        return FakeContent(self.response)


def _make_adapter() -> LangChainAdapter:
    # Contourne __init__ (qui construit un vrai PromptTemplate LangChain) :
    # seul le comportement de `invoke()` sur `_chain` nous intéresse ici.
    adapter = LangChainAdapter.__new__(LangChainAdapter)
    adapter._chain = FakeChain()
    return adapter


def test_invoke_logs_latency_with_model_name(caplog):
    adapter = _make_adapter()
    adapter._model_name = "Kimi-K2.6"

    with caplog.at_level(logging.INFO, logger=LATENCY_LOGGER_NAME):
        adapter.invoke("system", "context", "message")

    records = [r for r in caplog.records if r.name == LATENCY_LOGGER_NAME]
    assert len(records) == 1
    assert "Kimi-K2.6" in records[0].message


def test_invoke_logs_latency_as_numeric_milliseconds(caplog):
    adapter = _make_adapter()
    adapter._model_name = "Kimi-K2.6"

    with caplog.at_level(logging.INFO, logger=LATENCY_LOGGER_NAME):
        adapter.invoke("system", "context", "message")

    record = next(r for r in caplog.records if r.name == LATENCY_LOGGER_NAME)
    assert record.latency_ms >= 0
