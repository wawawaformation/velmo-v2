"""Classification + distillation d'un message brut vers sa destination mémoire.

Repli par règles déterministes par défaut (hors-ligne, sans LLM) : suffisant pour
les 12 cas d'évaluation (le mot-clé du fait réapparaît quasi tel quel). Un vrai
LLM (`velmo.llm.get_llm`) peut être branché en v2 pour généraliser au-delà des règles.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from .semantic import KNOWN_KEYS

Destination = Literal["semantic_column", "semantic_vector", "episodic", "none"]
_VALID_DESTINATIONS = {"semantic_column", "semantic_vector", "episodic", "none"}

_POINTURE_RE = re.compile(r"^(?:[3-5]\d|[SMLX]{1,3})$", re.I)
_SEGMENT_VALUES = {"particulier", "pro", "revendeur"}
_TUTOIEMENT_VALUES = {"tutoiement", "vouvoiement"}
_CANAL_CONTACT_VALUES = {"email", "téléphone", "telephone", "sms"}
_LANGUE_RE = re.compile(r"^[a-zàâäéèêëîïôöùûüç]{3,20}$", re.I)


def _is_plausible_langue(value: str | None) -> bool:
    return bool(_LANGUE_RE.match((value or "").strip()))


# Validation de plausibilité par clé connue : évite qu'une valeur incohérente
# (ex. une année de naissance classée comme pointure par le LLM) soit persistée.
_VALUE_VALIDATORS = {
    "pointure": lambda v: bool(_POINTURE_RE.match(v or "")),
    "segment": lambda v: (v or "").lower() in _SEGMENT_VALUES,
    "tutoiement": lambda v: (v or "").lower() in _TUTOIEMENT_VALUES,
    "canal_contact": lambda v: (v or "").lower() in _CANAL_CONTACT_VALUES,
    "langue": _is_plausible_langue,
}


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

_LLM_SYSTEM_PROMPT = """Tu es un extracteur de faits pour la mémoire d'un agent de support.

Analyse le message utilisateur et identifie les faits qu'il contient, à mémoriser.
Réponds UNIQUEMENT avec un tableau JSON (aucun texte autour), où chaque élément a la forme :
{{"destination": "...", "key": "...", "value": "..."}}

Valeurs possibles pour "destination" :
- "semantic_column" : un fait dont la clé est l'une de : {known_keys}. "key" doit être l'une de ces valeurs exactement.
- "semantic_vector" : un fait important mais dont la clé n'est pas connue à l'avance (ex. secret, numéro de contrat).
- "episodic" : un événement ou une information contextuelle (commande, adresse, livraison, achat).
- "none" : si le message ne contient aucun fait à retenir (dans ce cas, réponds []).

Un même message peut contenir plusieurs faits : renvoie un élément par fait trouvé.
Si aucun fait n'est trouvé, réponds exactement : []
""".format(known_keys=", ".join(KNOWN_KEYS))


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


def _classify_with_rules(message: str) -> ClassificationResult:
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


def _classify_with_llm(message: str, llm) -> list[ClassificationResult] | None:
    """Classe un message via LLM ; renvoie None en cas d'échec (repli règles)."""
    response = llm.invoke(_LLM_SYSTEM_PROMPT, "", message)
    block = re.search(r"\[.*\]", response, re.S)
    if block is None:
        return None
    try:
        items = json.loads(block.group(0))
    except json.JSONDecodeError:
        return None

    results = []
    for item in items:
        destination = item.get("destination")
        key = item.get("key")
        if destination not in _VALID_DESTINATIONS:
            continue
        if destination == "semantic_column" and key not in KNOWN_KEYS:
            continue
        value = item.get("value")
        validator = _VALUE_VALIDATORS.get(key)
        if validator is not None and not validator(value):
            continue
        results.append(ClassificationResult(destination, key, value))
    return results


def classify_and_distill(message: str, llm=None) -> list[ClassificationResult]:
    """Classe un message et distille ses faits (LLM si fourni, sinon règles)."""
    if llm is not None:
        results = _classify_with_llm(message, llm)
        if results is not None:
            return results

    rule_result = _classify_with_rules(message)
    if rule_result.destination == "none":
        return []
    return [rule_result]
