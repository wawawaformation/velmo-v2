"""Détection de PII / secrets internes en sortie — règles par motifs (v1, hors-ligne).

Repli déterministe : Azure Language Conversational PII redaction
(cf. conception/garde-fous/synthese.md) pourra être branché en v2 pour
généraliser au-delà des motifs listés ici (formulations dictées, etc.).
"""

from __future__ import annotations

import re
import unicodedata

_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?\d{4}){2,6}[ ]?\d{1,4}\b")
_PASSWORD_RE = re.compile(r"mot\s+de\s+passe\s+(?:du\s+compte\s+client\s+)?est\s+\S+", re.I)

_PII_PATTERNS = [_CARD_RE, _IBAN_RE, _PASSWORD_RE]

_SECRET_PATTERNS = [
    r"cle\s+api",
    r"variables?\s+d'environnement",
    r"tokens?\s+internes?",
    r"secret\s+de\s+configuration",
]


def _normalize_secret(text: str) -> str:
    """Normalise le texte pour la détection de secrets (Unicode NFD + suppression diacritiques)."""
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return stripped.lower()


def detect_pii(text: str) -> str | None:
    """Renvoie "pii" (carte/IBAN/mot de passe), "secret_leak" (secrets internes), ou None."""
    for pattern in _PII_PATTERNS:
        if pattern.search(text):
            return "pii"
    normalized = _normalize_secret(text)
    if any(re.search(pattern, normalized, re.I) for pattern in _SECRET_PATTERNS):
        return "secret_leak"
    return None
