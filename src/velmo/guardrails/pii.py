"""Détection de PII / secrets internes en sortie — règles par motifs (v1, hors-ligne).

Repli déterministe : Azure Language Conversational PII redaction
(cf. conception/garde-fous/synthese.md) pourra être branché en v2 pour
généraliser au-delà des motifs listés ici (formulations dictées, etc.).
"""

from __future__ import annotations

import re
import unicodedata

# Numero de carte : groupes de 4 chiffres (format carte reel, ex. "4111 1111 1111 1111"),
# et non plus n'importe quelle suite de 13-19 chiffres (trop de faux positifs sur des
# references clients/commandes non groupees).
_CARD_CHAIN_RE = re.compile(r"\b\d{4}(?:[ -]\d{4}){1,4}\b")
# Prefixe du type "AB12 " (code lot/reference alphanumerique) : si la suite de groupes de
# 4 chiffres est precedee d'un tel code, ce n'est pas un numero de carte isole.
_ALNUM_CODE_PREFIX_RE = re.compile(r"[A-Za-z]{2}\d{2}[ -]$")

_IBAN_COUNTRY_CODES = "FR|DE|BE|ES|IT|NL|LU|GB"
_IBAN_RE = re.compile(rf"\b(?:{_IBAN_COUNTRY_CODES})\d{{2}}(?:[ ]?\d{{4}}){{2,6}}[ ]?\d{{1,4}}\b")
_PASSWORD_RE = re.compile(r"mot\s+de\s+passe\s+(?:du\s+compte\s+client\s+)?est\s+\S+", re.I)

_PII_PATTERNS = [_IBAN_RE, _PASSWORD_RE]


def _has_card_number(text: str) -> bool:
    """Detecte un numero de carte : au moins 3 groupes de 4 chiffres, non precedes d'un code alphanumerique."""
    for match in _CARD_CHAIN_RE.finditer(text):
        groups = re.split(r"[ -]", match.group())
        if len(groups) < 3:
            continue
        prefix = text[: match.start()]
        if _ALNUM_CODE_PREFIX_RE.search(prefix):
            continue
        return True
    return False


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
    if _has_card_number(text):
        return "pii"
    for pattern in _PII_PATTERNS:
        if pattern.search(text):
            return "pii"
    normalized = _normalize_secret(text)
    if any(re.search(pattern, normalized, re.I) for pattern in _SECRET_PATTERNS):
        return "secret_leak"
    return None
