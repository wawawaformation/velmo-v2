"""REPL de conversation Velmo 2.0 (commandes, dispo, FAQ) — démarre après seed."""

from __future__ import annotations

import argparse
import logging
import sys
import threading

from dotenv import load_dotenv

from .agent import build_default_agent
from .logging_config import configure_logging
from .memory import MemoryManager
from .memory import scheduler as memory_scheduler


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


def _safe_respond(agent, user_id: str, message: str) -> str:
    """Appelle `agent.respond()`, sans jamais laisser une exception se propager.

    Un incident LLM/réseau (ex. `openai.APITimeoutError` sur le timeout de
    `LLM_TIMEOUT_SECONDS`, cf. `src/velmo/llm.py`) tuait auparavant tout le
    process CLI et perdait le fil de conversation en cours (observé en usage
    réel). Ici, un message d'erreur est renvoyé à la place, la boucle continue.

    Le message utilisateur est capturé en mémoire malgré l'échec (R6,
    traçabilité) — symétrique au chemin garde-fou de `Agent.respond()`, qui
    appelle déjà `memory.write()` sur un refus.
    """
    try:
        return agent.respond(user_id, message)
    except Exception:
        logging.getLogger(__name__).exception("Échec de agent.respond()")
        fallback = (
            "Désolé, une erreur technique m'empêche de répondre pour l'instant "
            "(problème réseau ou service indisponible). Réessayez dans un instant."
        )
        agent.memory.write(user_id, message, fallback)
        return fallback


def main() -> None:
    load_dotenv()
    configure_logging()
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
                print(f"\nVelmo : {_safe_respond(agent, args.user, message)}")
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
