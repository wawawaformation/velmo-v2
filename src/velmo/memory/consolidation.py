"""Consolidation épisodique → sémantique (skill semantic-episodic-memory).

Un message est toujours capturé en épisodique (nettoyage léger, vocabulaire
préservé). Un seul appel LLM combiné décide en plus si le message révèle un
fait sémantique généralisable (clé connue ou imprévisible) à consolider.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .classifier import (
    _VALID_DESTINATIONS,
    _VALUE_VALIDATORS,
    ClassificationResult,
    _extract_known_column,
)
from .semantic import KNOWN_KEYS


@dataclass
class ConsolidationResult:
    """Épisode nettoyé + fait sémantique optionnel dérivé du même message."""

    episode: str
    semantic: ClassificationResult | None = None


_CONSOLIDATION_SYSTEM_PROMPT = """Tu es un extracteur de mémoire pour un agent de support.

Analyse le message utilisateur et renvoie UNIQUEMENT un objet JSON (aucun texte
autour) de la forme :
{{"episode": "...", "semantic": {{"destination": "...", "key": "...", "value": "..."}} ou null}}

"episode" : le message nettoyé (bruit conversationnel coupé), vocabulaire du
client préservé (noms, numéros, termes exacts).

"semantic" : si le message révèle une connaissance générale, vraie et
indépendante du contexte (ex. pointure, préférence durable, secret, numéro de
contrat), un objet {{"destination": "semantic_column" ou "semantic_vector",
"key": "...", "value": "..."}}. "semantic_column" seulement si la clé est
l'une de : {known_keys}. Sinon, `null`.
""".format(known_keys=", ".join(KNOWN_KEYS))


_UNPREDICTABLE_KEY_HINTS = re.compile(r"\bsecret\b|\bnum[ée]ro\b|\bcontrat\b|\bcode\s+postal\b", re.I)


def _consolidate_with_rules(message: str) -> ConsolidationResult:
    """Repli déterministe (sans LLM) : épisode = message brut, règles existantes pour le fait."""
    known = _extract_known_column(message)
    semantic = None
    if known is not None:
        validator = _VALUE_VALIDATORS.get(known.key)
        if validator is None or validator(known.value):
            semantic = known
    elif _UNPREDICTABLE_KEY_HINTS.search(message):
        semantic = ClassificationResult("semantic_vector", key="fait", value=message.strip())
    return ConsolidationResult(episode=message.strip(), semantic=semantic)


def consolidate(message: str, llm=None) -> ConsolidationResult:
    """Nettoie un message en épisode et détecte un éventuel fait à consolider."""
    if llm is None:
        return _consolidate_with_rules(message)

    response = llm.invoke(_CONSOLIDATION_SYSTEM_PROMPT, "", message)
    block = re.search(r"\{.*\}", response, re.S)
    if block is None:
        return _consolidate_with_rules(message)
    try:
        data = json.loads(block.group(0))
    except json.JSONDecodeError:
        return _consolidate_with_rules(message)

    semantic_data = data.get("semantic")
    semantic = None
    if semantic_data is not None and semantic_data.get("destination") in _VALID_DESTINATIONS:
        key = semantic_data.get("key")
        value = semantic_data.get("value")
        validator = _VALUE_VALIDATORS.get(key)
        if validator is None or validator(value):
            semantic = ClassificationResult(semantic_data["destination"], key, value)

    return ConsolidationResult(episode=data["episode"], semantic=semantic)
