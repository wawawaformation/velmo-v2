"""Tests de la protection contre un incident LLM/réseau en pleine conversation.

Bug corrigé : un timeout réseau (`openai.APITimeoutError`, cf.
`LLM_TIMEOUT_SECONDS` dans `src/velmo/llm.py`) remontait tel quel depuis
`agent.respond()`, tuant tout le process CLI et perdant le fil de
conversation en cours (observé en usage réel).
"""

from __future__ import annotations

import pytest

from velmo.cli import _safe_respond


class FakeMemory:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, str]] = []

    def write(self, user_id: str, user_message: str, assistant_message: str) -> None:
        self.writes.append((user_id, user_message, assistant_message))


class FakeAgent:
    def __init__(self, exc: Exception | None = None, answer: str = "réponse ok") -> None:
        self._exc = exc
        self._answer = answer
        self.memory = FakeMemory()

    def respond(self, user_id: str, message: str) -> str:
        if self._exc is not None:
            raise self._exc
        return self._answer


def test_safe_respond_returns_agent_answer_on_success():
    agent = FakeAgent(answer="voici la réponse")
    assert _safe_respond(agent, "user-1", "salut") == "voici la réponse"


def test_safe_respond_returns_fallback_message_on_exception_instead_of_raising():
    agent = FakeAgent(exc=TimeoutError("Request timed out."))
    result = _safe_respond(agent, "user-1", "salut")
    assert isinstance(result, str)
    assert result  # un message non vide est renvoyé, pas de propagation


def test_safe_respond_does_not_propagate_exception():
    agent = FakeAgent(exc=RuntimeError("boom"))
    try:
        _safe_respond(agent, "user-1", "salut")
    except RuntimeError:
        pytest.fail("_safe_respond ne doit jamais laisser une exception se propager")


def test_safe_respond_captures_message_in_memory_on_exception():
    # Traçabilité (R6) : même en cas d'incident LLM, le message utilisateur
    # ne doit pas disparaître silencieusement — symétrique au chemin garde-fou
    # (agent.respond() appelle déjà memory.write() sur un refus).
    agent = FakeAgent(exc=TimeoutError("Request timed out."))

    result = _safe_respond(agent, "user-1", "Mon numéro de contrat est CT-4521.")

    assert len(agent.memory.writes) == 1
    user_id, user_message, assistant_message = agent.memory.writes[0]
    assert user_id == "user-1"
    assert user_message == "Mon numéro de contrat est CT-4521."
    assert assistant_message == result


def test_safe_respond_does_not_double_write_on_success():
    # Sur succès, agent.respond() a déjà appelé memory.write() en interne
    # (FakeAgent ne le simule pas ici, mais _safe_respond ne doit rien
    # écrire de plus dans ce cas — la responsabilité reste à respond()).
    agent = FakeAgent(answer="tout va bien")

    _safe_respond(agent, "user-1", "salut")

    assert agent.memory.writes == []
