"""Détection d'injection de prompt — règles par motifs (v1, hors-ligne).

Repli déterministe : Azure AI Content Safety Prompt Shields (cf.
conception/garde-fous/synthese.md) pourra être branché en v2.
"""

from __future__ import annotations

import re
import unicodedata

_INJECTION_PATTERNS = [
    r"ignore\s+tes?\s+instructions?",
    r"oublie\s+tes?\s+consignes?",
    r"tu\s+n'as\s+plus\s+de\s+regles?",
    r"developer\s+mode",
    r"prompt\s+systeme",
    r"obeis\s+a\s+mes\s+ordres?",
]


def _normalize(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return stripped.lower()


def detect_prompt_injection(text: str) -> bool:
    """Renvoie True si le texte tente de désactiver/contourner les instructions système."""
    normalized = _normalize(text)
    return any(re.search(pattern, normalized, re.I) for pattern in _INJECTION_PATTERNS)
