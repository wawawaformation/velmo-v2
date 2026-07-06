"""Classification + distillation d'un message brut vers sa destination mémoire.

Repli par règles déterministes par défaut (hors-ligne, sans LLM) : suffisant pour
les 12 cas d'évaluation (le mot-clé du fait réapparaît quasi tel quel). Un vrai
LLM (`velmo.llm.get_llm`) peut être branché en v2 pour généraliser au-delà des règles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .semantic import KNOWN_KEYS

Destination = Literal["semantic_column", "semantic_vector", "episodic", "none"]


@dataclass
class ClassificationResult:
    destination: Destination
    key: str | None = None
    value: str | None = None


# (regex, colonne connue, groupe de valeur) — évaluées dans l'ordre.
_KNOWN_COLUMN_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpointure\s+(?:est\s+)?(?:du\s+)?(\w+)", re.I), "pointure"),
    (re.compile(r"taille\s+(?:de\s+)?(?:pointure\s+)?(\d{2}|[SMLX]{1,3})\b", re.I), "pointure"),
    (re.compile(r"\btu(?:toie|toyer|toies)\b", re.I), "tutoiement"),
    (re.compile(r"\bclient\s+pro\b|\bcompte\s+pro(?:fessionnel)?\b|\bSIRET\b", re.I), "segment"),
    (re.compile(r"\bfran[çc]ais\b", re.I), "langue"),
    (re.compile(r"\bemail\b|\bt[ée]l[ée]phone\b|\bcontact(?:ez)?\b", re.I), "canal_contact"),
]

_EPISODIC_HINTS = re.compile(
    r"adresse|command[ée]|rue\s+des|achet[ée]|casque|maillot|colis|livr[ée]|retour",
    re.I,
)


def _extract_known_column(message: str) -> ClassificationResult | None:
    low = message.lower()
    if re.search(r"tu(?:toie|toyer|toies)", low):
        return ClassificationResult("semantic_column", "tutoiement", "tutoiement")
    if re.search(r"client\s+pro|compte\s+pro(?:fessionnel)?|siret", low):
        return ClassificationResult("semantic_column", "segment", "pro")
    if re.search(r"fran[çc]ais", low):
        return ClassificationResult("semantic_column", "langue", "français")
    if re.search(r"email", low) and "telephone" not in low and "téléphone" not in low:
        return ClassificationResult("semantic_column", "canal_contact", "email")
    if re.search(r"pointure\s+(?:est\s+)?(?:du\s+)?(\w+)", low):
        m = re.search(r"pointure\s+(?:est\s+)?(?:du\s+)?(\w+)", low)
        return ClassificationResult("semantic_column", "pointure", m.group(1))
    return None


def classify_and_distill(message: str) -> ClassificationResult:
    """Classe un message et distille sa valeur, par règles (v1, hors-ligne)."""
    known = _extract_known_column(message)
    if known is not None:
        assert known.key in KNOWN_KEYS
        return known

    if _EPISODIC_HINTS.search(message):
        return ClassificationResult("episodic", value=message.strip())

    if re.search(r"\bsecret\b|\bnum[ée]ro\b|\bcontrat\b|\bcode\s+postal\b", message, re.I):
        return ClassificationResult("semantic_vector", key="fait", value=message.strip())

    return ClassificationResult("none")
