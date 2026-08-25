"""API REST (FastAPI) — couche HTTP au-dessus de `Agent.respond()`.

Pas d'authentification réelle à ce stade (POC, périmètre acté avec
l'utilisateur) : `user_id` est passé en clair dans le payload. Destinée au
futur front Vue.js ; testée manuellement avec Bruno.

Une session DB par requête (dépendance FastAPI `get_session`), agent
reconstruit à la volée à chaque appel — pas d'état partagé entre requêtes,
cohérent avec `Agent.respond()` qui reconstruit déjà le graphe LangGraph à
chaque tour.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import Agent
from .db import Customer, session_factory
from .guardrails import GuardrailEngine
from .kb_store import get_kb
from .llm import get_chat_model
from .logging_config import configure_logging
from .memory import MemoryManager
from .memory import scheduler as memory_scheduler

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.kb = get_kb()
    app.state.chat_model = get_chat_model()
    if app.state.chat_model is None:
        raise RuntimeError(
            "Identifiants Azure requis pour démarrer l'API — configurez "
            "AZURE_AI_INFERENCE_ENDPOINT/AZURE_AI_INFERENCE_API_KEY."
        )
    job = memory_scheduler.start()
    yield
    job.shutdown(wait=True)


app = FastAPI(title="Velmo 2.0 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://velmo-client.koabana.fr",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session():
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


class MessageRequest(BaseModel):
    user_id: str
    message: str


class MessageResponse(BaseModel):
    reply: str
    latency_ms: float
    guardrail_category: str | None = None


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    segment: str


@app.post("/messages")
def post_message(request: MessageRequest, session=Depends(get_session)) -> MessageResponse:
    guardrails = GuardrailEngine()
    agent = Agent(
        model=app.state.chat_model,
        memory=MemoryManager(),
        guardrails=guardrails,
        session=session,
        kb=app.state.kb,
    )
    # Latence perçue par le client (garde-fous + mémoire + LLM inclus) —
    # mesurée ici plutôt que dans Agent.respond(), pour ne rien changer au
    # reste du code. Distincte de logs/llm_latency.log, qui détaille chaque
    # appel LLM individuel (potentiellement plusieurs par message).
    start = time.monotonic()
    reply = agent.respond(request.user_id, request.message)
    latency_ms = (time.monotonic() - start) * 1000
    # guardrails est une instance neuve par requête (pas de session partagée) :
    # un event dans .events signifie forcément un blocage survenu ce tour-ci.
    guardrail_category = guardrails.events[-1]["category"] if guardrails.events else None
    return MessageResponse(reply=reply, latency_ms=latency_ms, guardrail_category=guardrail_category)


@app.get("/users")
def get_users(session=Depends(get_session)) -> list[UserResponse]:
    customers = session.query(Customer).order_by(Customer.full_name).all()
    return [
        UserResponse(
            id=c.id, full_name=c.full_name, email=c.email, segment=c.segment.value,
        )
        for c in customers
    ]

