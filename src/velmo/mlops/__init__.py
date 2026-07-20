"""Évaluation et MLOps de l'agent Velmo : suites, note globale, seuil, rapport.

Surface publique stable consommée par la suite d'acceptance et la CI.
L'exécution des suites, le calcul de la note et la production du rapport sont à construire.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .guardrails_scoring import guardrails_score
from .memory_scoring import memory_score


class Evaluable(Protocol):
    """Agent évaluable : expose mémoire, garde-fous et une réponse."""

    def respond(self, user_id: str, message: str) -> str: ...


@dataclass(frozen=True)
class Scores:
    """Notes d'une exécution d'évaluation."""

    memory: float
    guardrails: float
    quality: float
    global_: float
    block_rate: float
    false_positive_rate: float
    latency_ms: float
    cost: float


class DeliveryBlocked(Exception):
    """Levée quand la note globale passe sous le seuil de livraison."""


def run_eval(agent: Evaluable) -> Scores:
    """Exécute les trois suites (mémoire, garde-fous, qualité) et calcule les notes."""
    # Phase 1 : Évaluation garde-fous
    guardrails_score_value = guardrails_score(agent)

    # Phase 2 : Évaluation mémoire
    memory_score_value = memory_score(agent)

    # Phase 3 : Qualité (TODO)
    quality_score = 0.8  # Placeholder

    # Pondération : garde-fous plus lourd (0.4), mémoire et qualité (0.3 chacun)
    w_memory = 0.3
    w_guardrails = 0.4
    w_quality = 0.3
    global_score = (
        w_memory * memory_score_value
        + w_guardrails * guardrails_score_value
        + w_quality * quality_score
    )

    # Extraire block_rate et false_positive_rate depuis l'évaluation
    # (pour maintenant, on les place à 0 — à affiner après)
    block_rate = 0.0
    false_positive_rate = 0.0

    return Scores(
        memory=memory_score_value,
        guardrails=guardrails_score_value,
        quality=quality_score,
        global_=global_score,
        block_rate=block_rate,
        false_positive_rate=false_positive_rate,
        latency_ms=0.0,
        cost=0.0,
    )


def enforce_threshold(scores: Scores, min_score: float) -> None:
    """Bloque la livraison (lève `DeliveryBlocked`) si la note globale est trop basse."""
    if scores.global_ < min_score:
        raise DeliveryBlocked(
            f"Global score {scores.global_:.2f} is below threshold {min_score}"
        )


def write_report(scores: Scores, path: Path) -> None:
    """Écrit le rapport de suivi (note mémoire, blocage, faux positifs, latence, coût)."""
    report = f"""# Rapport MLOps Velmo 2.0

## Scores

- **Memoire** : {scores.memory:.2%}
- **Garde-fous** : {scores.guardrails:.2%}
- **Qualite** : {scores.quality:.2%}
- **Global** : {scores.global_:.2%}

## Signaux de monitorage

- **Note memoire** : {scores.memory:.2%}
- **Taux de blocage** : {scores.block_rate:.2%}
- **Taux de faux positif** : {scores.false_positive_rate:.2%}
- **Latence moyenne** : {scores.latency_ms:.1f} ms
- **Cout par conversation** : ${scores.cost:.2f}

## Version

Version courante : {current_version()}
"""
    path.write_text(report, encoding="utf-8")


def current_version() -> str:
    """Renvoie la version courante de l'agent évaluée."""
    return "2.0.0"
