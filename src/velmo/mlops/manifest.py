"""Chargement du manifeste d'évaluation (seuil, pondérations, version).

Source de vérité unique du gate qualité : le seuil vivait auparavant dans cinq
endroits (deux tests, `score.py`, deux fois `ci.yml`) et les pondérations en dur
dans `run_eval` — un ajustement pouvait en oublier un et laisser la CI valider
contre l'ancienne valeur.

La validation est stricte et échoue fort : des poids saisis à `0.3/0.4/0.4`
donneraient une note globale supérieure à 1 **sans le moindre avertissement**,
rendant le seuil dénué de sens.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# Racine du dépôt : src/velmo/mlops/manifest.py -> remonter de 4 niveaux.
DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[3] / "mlops" / "eval_manifest.yaml"

# Les trois suites du chantier 3 : toute absence est une erreur, pas un défaut.
_REQUIRED_SUITES = ("memory", "guardrails", "quality")

# Tolérance sur la somme des poids (flottants : 0.3 + 0.4 + 0.3 != 1.0 exactement).
_SUM_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Manifest:
    """Paramètres versionnés du gate qualité."""

    version: str
    threshold: float
    weights: dict[str, float]


def load_manifest(path: Path | None = None) -> Manifest:
    """Charge et valide le manifeste. Lève `ValueError` si incohérent."""
    manifest_path = Path(path) if path is not None else DEFAULT_MANIFEST_PATH
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"Manifeste illisible (objet YAML attendu) : {manifest_path}")

    version = data.get("version")
    if not version:
        raise ValueError(f"Manifeste sans version : {manifest_path}")

    threshold = data.get("threshold")
    if not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
        raise ValueError(
            f"Manifeste : seuil invalide ({threshold!r}), attendu un nombre dans [0, 1]."
        )

    raw_weights = data.get("weights") or {}
    weights: dict[str, float] = {}
    for suite in _REQUIRED_SUITES:
        value = raw_weights.get(suite)
        if not isinstance(value, (int, float)):
            raise ValueError(f"Manifeste : poids manquant ou invalide pour « {suite} ».")
        weights[suite] = float(value)

    total = sum(weights.values())
    if abs(total - 1.0) > _SUM_TOLERANCE:
        raise ValueError(
            f"Manifeste : la somme des poids vaut {total}, elle doit valoir 1 "
            "(sinon la note globale n'est plus comparable au seuil)."
        )

    return Manifest(version=str(version), threshold=float(threshold), weights=weights)
