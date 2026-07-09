"""REPL de conversation Velmo 2.0 (commandes, dispo, FAQ) — démarre après seed."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

from .agent import build_default_agent
from .memory import MemoryManager
from .memory import scheduler as memory_scheduler

LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "memory.log"
LLM_LATENCY_LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "llm_latency.log"


def _configure_logging() -> None:
    """Redirige les logs (scheduler mémoire, APScheduler) vers un fichier :
    évite de polluer le prompt interactif du CLI (cf. bug #skipped: maximum
    number of running instances). La latence des appels LLM part dans un
    fichier dédié (pas de propagation vers le root logger)."""
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


def _preload_facts_in_background(user_id: str) -> None:
    """Précharge les faits connus d'un utilisateur au login (thread dédié).

    Réduit la latence perçue du premier `MemoryManager.read()` en cours de
    conversation : une session DB séparée est nécessaire (non partageable
    entre threads), fermée à la fin du préchargement.
    """
    mm = MemoryManager()
    try:
        mm.preload_facts(user_id)
    finally:
        mm.close()


def _read_line(stream) -> str | None:
    """Lit une ligne depuis un flux binaire, tolérante aux octets UTF-8 invalides.

    `input()` plante avec `UnicodeDecodeError` sur un octet invalide (ex.
    touche morte mal interceptée par le terminal) — ici, l'octet fautif est
    remplacé plutôt que de tuer le process et perdre le fil de conversation.
    Renvoie `None` en fin de flux (équivalent EOF).
    """
    raw = stream.readline()
    if not raw:
        return None
    return raw.decode("utf-8", errors="replace").rstrip("\n")


def main() -> None:
    load_dotenv()
    _configure_logging()
    parser = argparse.ArgumentParser(description="Chat support Velmo 2.0")
    parser.add_argument("--user", default="C-marc-dubois", help="Identifiant client authentifié")
    args = parser.parse_args()

    threading.Thread(
        target=_preload_facts_in_background, args=(args.user,), daemon=True
    ).start()

    agent = build_default_agent()
    if agent.memory._session.get_bind().dialect.name != "postgresql":
        print(
            "ATTENTION : Postgres (DB_URL) injoignable au démarrage — la mémoire "
            "utilise un repli SQLite local (.velmo_memory.db), pas la base "
            "docker-compose. Vérifiez `docker compose ps postgres`."
        )
    job = memory_scheduler.start()
    print(f"Velmo 2.0 prêt (client {args.user}). Posez votre question (Ctrl+C pour quitter).")
    try:
        while True:
            try:
                print("\nVous : ", end="", flush=True)
                line = _read_line(sys.stdin.buffer)
                if line is None:
                    print("\nÀ bientôt !")
                    break
                message = line.strip()
                if not message:
                    continue
                print(f"\nVelmo : {agent.respond(args.user, message)}")
            except KeyboardInterrupt:
                print("\nÀ bientôt !")
                break
    finally:
        # wait=True : si un tick est en cours (appel LLM, routage, purge du
        # tampon), on le laisse terminer avant de couper le process — sinon
        # le message reste indéfiniment dans `message_brut` (LLM appelé mais
        # `buffer.delete` jamais atteint).
        job.shutdown(wait=True)


if __name__ == "__main__":
    main()
