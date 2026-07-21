"""Point d'entrée CLI de l'évaluation MLOps (`python -m velmo.mlops.score`).

Exécute les trois suites, journalise la note globale, écrit `mlops/report.md`
et applique le seuil de blocage (gate CI : sortie ≠ 0 sous le seuil).

Résilience : un incident infra Azure (429/timeout, cf.
`docs/rapport_latence_azure_foundry.md`) n'est pas une régression qualité — il
n'échoue pas le gate (sortie 0 avec avertissement), même convention que
`_run_eval_or_skip` côté tests.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from . import (
    DeliveryBlocked,
    Scores,
    current_version,
    enforce_threshold,
    run_eval,
    write_report,
)
from .manifest import load_manifest

log = logging.getLogger("velmo.mlops.score")

# Chemin exigé par le brief (item 3) et les tests d'acceptance.
DEFAULT_REPORT_PATH = Path("mlops/report.md")


def run_and_report(agent, report_path: Path, min_score: float) -> Scores:
    """Évalue l'agent, journalise la note, écrit le rapport, applique le seuil.

    L'ordre est délibéré : le rapport est écrit AVANT le contrôle de seuil, pour
    rester disponible au diagnostic même quand la livraison est bloquée.

    Lève `DeliveryBlocked` si la note globale est sous `min_score`.
    """
    scores = run_eval(agent)

    # Journalisation de la note (item 2 : « journaliser la note »).
    log.info(
        "Eval MLOps v%s | global=%.2f%% memoire=%.2f%% garde-fous=%.2f%% qualite=%.2f%%",
        current_version(),
        scores.global_ * 100,
        scores.memory * 100,
        scores.guardrails * 100,
        scores.quality * 100,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(scores, report_path)
    log.info("Rapport ecrit : %s", report_path)

    enforce_threshold(scores, min_score)  # lève DeliveryBlocked sous le seuil
    return scores


def main() -> int:
    """Assemble le vrai agent, lance l'éval, renvoie un code de sortie pour la CI."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # `python -m velmo.mlops.score` ne charge pas `.env` (contrairement au CLI) :
    # sans ça, DB_URL/CHROMA_URL/creds Azure seraient absents en local.
    from dotenv import load_dotenv

    load_dotenv()

    # Seuil lu dans le manifeste (source de vérité unique, versionnée en Git).
    min_score = load_manifest().threshold

    from ..agent import build_default_agent

    # temperature=0 : la note doit être reproductible d'un run à l'autre, sinon
    # le gate CI bascule sur du bruit (cf. chantier3-reponses.md, Réponse 2).
    agent = build_default_agent(temperature=0)
    try:
        run_and_report(agent, DEFAULT_REPORT_PATH, min_score)
    except DeliveryBlocked as exc:
        log.error("Livraison bloquee : %s", exc)
        return 1
    except Exception as exc:  # incident infra Azure : ne casse pas le gate
        import openai

        if isinstance(exc, openai.APIError):
            log.warning("Incident infra Azure, eval non concluante (skip) : %s", exc)
            return 0
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
