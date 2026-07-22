"""Détection de demandes hors périmètre (cote/valorisation, finance, juridique,
authentification tierce) — règles par motifs (v1, hors-ligne).

Repli déterministe : vérification de périmètre via un petit LLM
(cf. conception/garde-fous/synthese.md, Phi-4-mini-instruct) pourra être
branchée en v2 pour généraliser au-delà des motifs listés ici.
"""

from __future__ import annotations

import re
import unicodedata

_OUT_OF_SCOPE_PATTERNS = [
    r"combien\s+vaut\s+mon\s+maillot",
    r"cote\s+de\s+mon\s+maillot",
    r"a\s+la\s+revente",
    r"placement\s+en\s+bourse",
    r"authentifier\s+ce\s+maillot.*autre\s+site",
    r"conseil\s+juridique",
]


def _normalize(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return stripped.lower()


def detect_out_of_scope(text: str) -> bool:
    """Renvoie True si la demande sort du périmètre support (valorisation, finance, juridique, authentification tierce)."""
    normalized = _normalize(text)
    return any(re.search(pattern, normalized, re.I) for pattern in _OUT_OF_SCOPE_PATTERNS)
