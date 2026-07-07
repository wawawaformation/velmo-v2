"""Détection de contenu haineux/violent/sexuel — règles par mots-clés (v1, hors-ligne).

Repli déterministe : Azure AI Content Safety (cf. conception/garde-fous/synthese.md)
pourra être branché en v2 pour généraliser au-delà des motifs listés ici.
"""

from __future__ import annotations

import re
import unicodedata

_HATE_PATTERNS = [
    r"sous[\s-]?(?:etres?|humains?)",
    r"sale\s+race",
    r"je\s+les?\s+hais",
    r"devraient?\s+dispara[iî]tre",
]

_VIOLENCE_PATTERNS = [
    r"\bje\s+vais\s+(?:te\s+)?(?:frapper|tuer|tabasser|cogner)",
    r"\bc'est\s+une\s+menace\b",
    r"\bcomment\s+me\s+faire\s+du\s+mal\b",
]

_SEXUAL_PATTERNS = [
    r"contenu\s+sexuel\s+explicite",
    r"scene?\s+de\s+nudite",
]

_CATEGORY_PATTERNS = {
    "hate": _HATE_PATTERNS,
    "violence": _VIOLENCE_PATTERNS,
    "sexual": _SEXUAL_PATTERNS,
}


def _normalize(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return stripped.lower()


def detect_moderation(text: str) -> str | None:
    """Renvoie la catégorie détectée (hate/violence/sexual), ou None si le texte est sain."""
    normalized = _normalize(text)
    for category, patterns in _CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized, re.I):
                return category
    return None
