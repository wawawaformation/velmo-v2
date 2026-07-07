"""Scheduler périodique (APScheduler) déclenchant le traitement de la mémoire.

Point d'entrée prod pour le découplage capture/traitement décrit dans
`conception/memoire/choix.md` : capture synchrone dans `write()`, traitement
asynchrone via ce job, exécuté à intervalle fixe plutôt que par lot de taille
fixe (aucun reliquat possible, cf. le document de conception).

Démarré explicitement par le process hôte (CLI, futur serveur) — pas activé
par défaut à l'import de `velmo.memory`, pour ne pas surprendre les tests.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from . import MemoryManager

logger = logging.getLogger(__name__)


def start(*, interval_seconds: int = 60) -> BackgroundScheduler:
    """Démarre le job périodique en tâche de fond et renvoie le scheduler.

    Le scheduler tourne dans un thread du process courant (pas de nouveau
    service Docker) : adapté au conteneur `app` déjà persistant. Appeler
    `.shutdown()` sur l'objet renvoyé pour l'arrêter proprement.
    """
    scheduler = BackgroundScheduler()

    def _tick() -> None:
        mm = MemoryManager()
        try:
            mm.run_pending_job_all_users()
        except Exception:
            logger.exception("Échec du traitement mémoire périodique")
        finally:
            mm.close()

    scheduler.add_job(_tick, "interval", seconds=interval_seconds, id="memory_processing")
    scheduler.start()
    return scheduler
