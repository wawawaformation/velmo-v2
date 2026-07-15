"""Tests du callback de latence pour les appels modèle via `create_agent()`.

Bug réel observé en rejouant `docs/script_presentation_demo_memoire.md`
(Démo 3) : depuis la migration vers `create_agent()`, le modèle de chat
principal (`get_chat_model()`) est un `BaseChatModel` brut, plus enveloppé
par `LangChainAdapter` — sa latence n'était donc plus journalisée dans
`logs/llm_latency.log`, seul le classifieur (toujours via
`LangChainAdapter`) l'était encore. `LatencyCallbackHandler` comble ce trou
via le mécanisme de callback natif LangChain, sans modifier le
`BaseChatModel` lui-même (qui doit rester intact pour `create_agent()`).
"""

from __future__ import annotations

import logging
from uuid import uuid4

from velmo.llm import LatencyCallbackHandler

LATENCY_LOGGER_NAME = "velmo.llm.latency"


def test_on_llm_end_logs_latency_after_chat_model_start(caplog):
    handler = LatencyCallbackHandler()
    run_id = uuid4()

    with caplog.at_level(logging.INFO, logger=LATENCY_LOGGER_NAME):
        handler.on_chat_model_start(
            {"kwargs": {"model_name": "gpt-5.4"}}, [[]], run_id=run_id,
        )
        handler.on_llm_end(object(), run_id=run_id)

    records = [r for r in caplog.records if r.name == LATENCY_LOGGER_NAME]
    assert len(records) == 1
    assert "gpt-5.4" in records[0].message
    assert records[0].latency_ms >= 0


def test_on_llm_end_without_matching_start_does_not_crash(caplog):
    # Un run_id inconnu (ex. callback attaché après coup) ne doit pas planter.
    handler = LatencyCallbackHandler()

    with caplog.at_level(logging.INFO, logger=LATENCY_LOGGER_NAME):
        handler.on_llm_end(object(), run_id=uuid4())

    records = [r for r in caplog.records if r.name == LATENCY_LOGGER_NAME]
    assert records == []


def test_tracks_independent_runs_separately(caplog):
    handler = LatencyCallbackHandler()
    run_id_1, run_id_2 = uuid4(), uuid4()

    with caplog.at_level(logging.INFO, logger=LATENCY_LOGGER_NAME):
        handler.on_chat_model_start({"kwargs": {"model_name": "gpt-5.4"}}, [[]], run_id=run_id_1)
        handler.on_chat_model_start({"kwargs": {"model_name": "gpt-5.4-nano"}}, [[]], run_id=run_id_2)
        handler.on_llm_end(object(), run_id=run_id_1)
        handler.on_llm_end(object(), run_id=run_id_2)

    records = [r for r in caplog.records if r.name == LATENCY_LOGGER_NAME]
    assert len(records) == 2
    assert "gpt-5.4" in records[0].message
    assert "gpt-5.4-nano" in records[1].message
