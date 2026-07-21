"""Empreintes des prompts réellement chargés — traçabilité qui ne peut pas mentir.

Le manifeste déclare une version par prompt (intention : semver, rollback).
Mais une version saisie à la main se périme dès qu'on modifie un prompt sans
penser à l'incrémenter, et un rapport affichant une version fausse est pire
qu'un rapport sans version.

L'empreinte est dérivée du texte réellement chargé : elle **constate** au lieu
de déclarer. Si le rapport montre une version inchangée mais une empreinte
différente, c'est qu'un prompt a bougé sans être versionné.
"""

from __future__ import annotations

import hashlib

# 8 caractères : assez pour distinguer deux révisions, assez court pour rester
# lisible dans un tableau de rapport.
_FINGERPRINT_LENGTH = 8


def fingerprint(text: str) -> str:
    """Empreinte courte et stable d'un texte de prompt."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]


def prompt_fingerprints() -> dict[str, str]:
    """Empreinte du texte réel de chacun des quatre prompts de l'agent.

    Imports différés : `agent` tire LangChain/LangGraph, inutile de le charger
    quand on ne fait que lire le manifeste.
    """
    from ..agent import SYSTEM_PROMPT
    from ..guardrails.moderation_llm import _MODERATION_LLM_SYSTEM_PROMPT
    from ..memory.classifier import _LLM_SYSTEM_PROMPT
    from ..memory.consolidation import _CONSOLIDATION_SYSTEM_PROMPT

    return {
        "agent": fingerprint(SYSTEM_PROMPT),
        "guardrails_moderation": fingerprint(_MODERATION_LLM_SYSTEM_PROMPT),
        "memory_consolidation": fingerprint(_CONSOLIDATION_SYSTEM_PROMPT),
        "memory_classifier": fingerprint(_LLM_SYSTEM_PROMPT),
    }
