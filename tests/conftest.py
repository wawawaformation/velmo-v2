"""Fixtures de test : base SQLite seedée, FAQ locale, agents — tout hors-ligne."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from velmo.agent import Agent
from velmo.db import fresh_sqlite_session
from velmo.guardrails import Decision, GuardrailEngine
from velmo.kb_store import LocalKB
from velmo.llm import EchoLLM
from velmo.memory import MemoryManager
from velmo.sampledata import seed

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"

_AZURE_ENV_VARS = (
    "AZURE_AI_INFERENCE_ENDPOINT",
    "AZURE_AI_INFERENCE_API_KEY",
    "AZURE_AI_INFERENCE_MODEL",
    "AZURE_AI_CLASSIFIER_MODEL",
)


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch):
    """Neutralise les identifiants Azure pour forcer le repli `EchoLLM` (tests hors-ligne).

    Sans ceci, `get_classifier_llm()`/`get_llm()` appellent le vrai Azure dès que ces
    variables sont présentes dans l'environnement (ex. via `.env`), rendant les tests
    lents (appels réseau réels) et non déterministes.
    """
    for var in _AZURE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def load_jsonl(name: str) -> list[dict]:
    text = (EVAL_DIR / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def seeded_session():
    session = fresh_sqlite_session()
    seed(session)
    return session


class AllowAllGuardrails:
    """Garde-fous neutralisés (agent dégradé pour le test de régression)."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def check_input(self, message: str) -> Decision:
        return Decision(allowed=True, action="allow")

    def check_output(self, text: str) -> Decision:
        return Decision(allowed=True, action="allow")


def build_reference_agent() -> Agent:
    return Agent(
        llm=EchoLLM(),
        memory=MemoryManager(),
        guardrails=GuardrailEngine(),
        session=seeded_session(),
        kb=LocalKB(),
    )


def build_degraded_agent() -> Agent:
    return Agent(
        llm=EchoLLM(),
        memory=MemoryManager(),
        guardrails=AllowAllGuardrails(),
        session=seeded_session(),
        kb=LocalKB(),
    )


@pytest.fixture
def db_session():
    session = seeded_session()
    yield session
    session.close()


@pytest.fixture
def kb() -> LocalKB:
    return LocalKB()


@pytest.fixture
def reference_agent() -> Agent:
    return build_reference_agent()


@pytest.fixture
def degraded_agent() -> Agent:
    return build_degraded_agent()
