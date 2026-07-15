"""Câblage des logs applicatifs, partagé entre le CLI et l'API.

Redirige les logs (scheduler mémoire, APScheduler) vers un fichier dédié —
évite de polluer la sortie standard (prompt interactif du CLI, ou stdout du
serveur ASGI). La latence LLM et les décisions garde-fous partent chacune
dans un fichier séparé, sans propagation vers le root logger.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "memory.log"
LLM_LATENCY_LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "llm_latency.log"
GUARDRAILS_LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "guardrails.log"


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Un appel LLM toutes les ~20s (tick scheduler) : rotation à 1 Mo, 3
    # fichiers de sauvegarde conservés (llm_latency.log.1/.2/.3), pour éviter
    # une croissance illimitée du fichier en usage prolongé.
    latency_handler = RotatingFileHandler(
        LLM_LATENCY_LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    latency_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    latency_logger = logging.getLogger("velmo.llm.latency")
    latency_logger.addHandler(latency_handler)
    latency_logger.setLevel(logging.INFO)
    latency_logger.propagate = False

    guardrails_handler = logging.FileHandler(GUARDRAILS_LOG_FILE, encoding="utf-8")
    guardrails_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    guardrails_logger = logging.getLogger("velmo.guardrails.events")
    guardrails_logger.addHandler(guardrails_handler)
    guardrails_logger.setLevel(logging.INFO)
    guardrails_logger.propagate = False
