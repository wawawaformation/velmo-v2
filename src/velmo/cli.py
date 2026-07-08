"""REPL de conversation Velmo 2.0 (commandes, dispo, FAQ) — démarre après seed."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from .agent import build_default_agent
from .memory import scheduler as memory_scheduler

LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "memory.log"


def _configure_logging() -> None:
    """Redirige les logs (scheduler mémoire, APScheduler) vers un fichier :
    évite de polluer le prompt interactif du CLI (cf. bug #skipped: maximum
    number of running instances)."""
    LOG_FILE.parent.mkdir(exist_ok=True)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def main() -> None:
    load_dotenv()
    _configure_logging()
    parser = argparse.ArgumentParser(description="Chat support Velmo 2.0")
    parser.add_argument("--user", default="C-marc-dubois", help="Identifiant client authentifié")
    args = parser.parse_args()

    agent = build_default_agent()
    job = memory_scheduler.start()
    print(f"Velmo 2.0 prêt (client {args.user}). Posez votre question (Ctrl+C pour quitter).")
    try:
        while True:
            try:
                message = input("\nVous : ").strip()
                if not message:
                    continue
                print(f"\nVelmo : {agent.respond(args.user, message)}")
            except (KeyboardInterrupt, EOFError):
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
