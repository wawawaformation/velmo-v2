"""Tests unitaires de MemoryMiddleware (hooks LangChain, sans graphe réel).

`before_agent` lit le contexte mémoire une seule fois par tour utilisateur et
le met en cache dans l'état (`memory_context`) ; `wrap_model_call` lit cette
valeur mise en cache et l'injecte dans le prompt système à chaque appel modèle
interne (sans refaire de lecture mémoire à chaque étape du tool-calling).
`after_agent` écrit le tour complet en mémoire une seule fois.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from velmo.memory import MemoryManager
from velmo.memory.middleware import MemoryMiddleware


def _runtime():
    return Runtime()


def test_before_agent_caches_rendered_memory_context():
    memory = MemoryManager()
    user = "unit-mw-before-agent"
    memory.remember_fact(user, "pointure", "43")
    middleware = MemoryMiddleware(memory, user_id=user)
    state = {"messages": [HumanMessage("Tu te souviens de moi ?")]}

    result = middleware.before_agent(state, _runtime())

    assert result is not None
    assert "43" in result["memory_context"]
    memory.close()


def test_wrap_model_call_injects_cached_context_into_system_prompt():
    memory = MemoryManager()
    user = "unit-mw-wrap-model"
    middleware = MemoryMiddleware(memory, user_id=user)

    captured_requests = []

    class FakeRequest:
        def __init__(self, system_prompt):
            self.system_prompt = system_prompt

        def override(self, **kwargs):
            captured_requests.append(kwargs)
            new = FakeRequest(kwargs.get("system_prompt", self.system_prompt))
            return new

    def handler(request):
        return "handled"

    request = FakeRequest(system_prompt="Tu es Velmo.")
    state = {"messages": [], "memory_context": "fact: pointure=43"}
    # wrap_model_call reçoit request/handler ; l'état est accessible via request.state
    request.state = state

    middleware.wrap_model_call(request, handler)

    assert len(captured_requests) == 1
    assert "pointure=43" in captured_requests[0]["system_prompt"]
    assert "Tu es Velmo." in captured_requests[0]["system_prompt"]
    memory.close()


def test_after_agent_writes_turn_to_memory():
    memory = MemoryManager()
    user = "unit-mw-after-agent"
    middleware = MemoryMiddleware(memory, user_id=user)
    state = {
        "messages": [
            HumanMessage("Ma pointure de chaussure c'est du 43."),
            AIMessage("C'est noté."),
        ]
    }

    middleware.after_agent(state, _runtime())

    from velmo.memory import short_term

    turns = short_term.get_turns(user)
    assert ("user", "Ma pointure de chaussure c'est du 43.") in turns
    assert ("assistant", "C'est noté.") in turns
    memory.close()
