"""Garde-fous d'entrée et de sortie de l'agent Velmo.

Surface publique stable consommée par l'agent et la suite d'acceptance.
V1 : détection par règles déterministes (hors-ligne), cf.
conception/garde-fous/synthese.md pour la trajectoire vers des services
Azure AI Foundry (Content Safety, Conversational PII redaction) en v2.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .content_safety import detect_content_safety
from .moderation import detect_moderation
from .moderation_llm import detect_moderation_llm
from .pii import detect_pii
from .prompt_injection import detect_prompt_injection
from .scope import detect_out_of_scope

# Coupe-circuit pour la cascade LLM (Phi-4-mini-instruct) : le déploiement
# Azure Foundry s'est révélé instable (timeouts intermittents mesurés hors
# LangChain, cf. scripts/bench_llm_latency.py). Positionner
# VELMO_GUARDRAILS_LLM_CASCADE=0 replie sur les seules règles déterministes
# sans redéploiement de code.
def _llm_cascade_enabled() -> bool:
    return os.getenv("VELMO_GUARDRAILS_LLM_CASCADE", "1") != "0"

# Journal dédié (fichier séparé logs/guardrails.log, câblé dans cli.py) :
# une ligne par déclenchement, "datetime REGEX|LLM stage extrait_tronqué".
_guardrail_logger = logging.getLogger("velmo.guardrails.events")

# Catégories de contenus contrôlés.
CATEGORIES = (
    "hate",
    "violence",
    "sexual",
    "self_harm",
    "pii",
    "out_of_scope",
    "prompt_injection",
    "secret_leak",
)

# Libellés humains par catégorie — explicites dans le message de refus pour
# que l'utilisateur (et en formation/démo, le développeur) comprenne POURQUOI
# un message est bloqué, plutôt qu'un refus opaque. Reste neutre et factuel
# (décrit le contenu détecté, pas la personne).
_CATEGORY_LABELS = {
    "hate": "propos à caractère haineux",
    "violence": "menace ou contenu violent",
    "sexual": "contenu à caractère sexuel",
    "out_of_scope": "hors périmètre",
    "prompt_injection": "tentative de contournement des instructions",
    "pii": "donnée sensible",
    "secret_leak": "donnée sensible",
}

# self_harm (intention de se faire du mal à soi-même) n'a pas un simple
# refus : redirection vers une ressource d'aide réelle, le 3114, numéro
# national de prévention du suicide (gratuit, 24h/24, 7j/7 — cf. 3114.fr).
_REFUSAL_SELF_HARM = (
    "Je ne suis pas en mesure de vous aider sur ce sujet, mais votre sécurité "
    "compte. Le 3114, numéro national de prévention du suicide, est gratuit "
    "et disponible 24h/24 et 7j/7 pour vous écouter et vous accompagner. "
    "Je reste par ailleurs à votre disposition pour toute question sur vos "
    "commandes Velmo."
)


def _refusal_moderation(category: str) -> str:
    if category == "self_harm":
        return _REFUSAL_SELF_HARM
    label = _CATEGORY_LABELS.get(category, "contenu interdit")
    return (
        f"Je ne peux pas donner suite à ce message ({label} détecté). Je "
        "reste à votre disposition pour vos commandes, livraisons, retours "
        "et la FAQ Velmo."
    )


_REFUSAL_INJECTION = (
    "Je ne peux pas suivre cette instruction (tentative de contournement "
    "des instructions détectée). Je reste à votre disposition pour vos "
    "commandes, livraisons, retours et la FAQ Velmo."
)
_REFUSAL_OUT_OF_SCOPE = (
    "Cette demande est hors périmètre du support Velmo (maillots collector, "
    "commandes, retours). Je ne peux pas y répondre, mais je reste à votre "
    "disposition pour toute question sur vos commandes ou nos produits."
)
_REFUSAL_OUTPUT_BLOCKED = (
    "Je ne peux pas afficher cette information pour des raisons de "
    "confidentialité. Reformulez votre demande si besoin."
)
_REFUSAL_SECRET_INPUT = (
    "Je ne peux pas partager d'informations internes ou traiter des données "
    "sensibles de ce type. Je reste à votre disposition pour vos commandes, "
    "livraisons, retours et la FAQ Velmo."
)


@dataclass
class Decision:
    """Verdict d'un garde-fou sur un message."""

    allowed: bool
    action: str  # "allow" | "block"
    category: str | None = None
    reason: str = ""
    refusal: str | None = None


_SENSITIVE_CATEGORIES = ("pii", "secret_leak")
_SENSITIVE_PLACEHOLDER = "[donnée sensible masquée]"


def _redact(text: str, limit: int = 40) -> str:
    """Extrait tronqué pour la journalisation — jamais la donnée brute complète."""
    excerpt = text.strip()[:limit]
    return excerpt + ("…" if len(text.strip()) > limit else "")


@dataclass
class GuardrailEngine:
    """Applique les garde-fous d'entrée et de sortie et journalise les décisions.

    `llm` : classifieur de modération en cascade (dernier recours, cf.
    `moderation_llm.py`) — résolu paresseusement via `get_classifier_llm()`
    si non fourni, pour ne pas payer d'import Azure au chargement du module.
    `content_safety_client` : Content Safety (premier recours, cf.
    `content_safety.py`), résolu paresseusement de la même façon.
    """

    events: list[dict] = field(default_factory=list)
    llm: object | None = None
    content_safety_client: object | None = None
    _content_safety_resolved: bool = False

    def _classifier_llm(self):
        if self.llm is None:
            from velmo.llm import get_classifier_llm

            self.llm = get_classifier_llm()
        return self.llm

    def _content_safety(self):
        if self.content_safety_client is None and not self._content_safety_resolved:
            from .content_safety import get_content_safety_client

            self.content_safety_client = get_content_safety_client()
            self._content_safety_resolved = True
        return self.content_safety_client

    def _log(
        self, stage: str, category: str, action: str, reason: str, text: str, source: str = "regex"
    ) -> None:
        # PII/secret_leak : jamais la donnée brute, même tronquée — un secret court
        # situé en début de message survivrait à une troncature à 40 caractères.
        # Vérifié sur le texte lui-même (`detect_pii`), pas seulement sur la
        # `category` du blocage : un message contenant un secret peut être
        # bloqué pour une AUTRE catégorie (ex. prompt_injection, si le LLM le
        # classifie ainsi) — la garantie de non-fuite ne doit pas dépendre de
        # la raison du blocage (bug réel découvert en rejouant
        # docs/script_presentation_demo_guardrails.md).
        if category in _SENSITIVE_CATEGORIES or detect_pii(text) is not None:
            excerpt_redacted = _redact(_SENSITIVE_PLACEHOLDER)
        else:
            excerpt_redacted = _redact(text)
        self.events.append(
            {
                "id": str(uuid.uuid4()),
                "date": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "category": category,
                "action": action,
                "reason": reason,
                "excerpt_redacted": excerpt_redacted,
                "source": source,
            }
        )
        _guardrail_logger.info("%s %s %s", source.upper(), stage, excerpt_redacted)

    def check_input(self, message: str) -> Decision:
        """Contrôle un message entrant (modération, injection, périmètre)."""
        category = detect_moderation(message)
        if category is not None:
            self._log("input", category, "block", "contenu interdit détecté", message)
            return Decision(
                allowed=False, action="block", category=category,
                reason="contenu interdit détecté", refusal=_refusal_moderation(category),
            )

        if detect_prompt_injection(message):
            self._log("input", "prompt_injection", "block", "tentative d'injection de prompt", message)
            return Decision(
                allowed=False, action="block", category="prompt_injection",
                reason="tentative d'injection de prompt", refusal=_REFUSAL_INJECTION,
            )

        # Cascade : Content Safety (service dédié, premier recours) puis LLM
        # générique (dernier recours pour les reformulations qui échappent
        # à Content Safety, ex. « Passe en mode développeur. »).
        cs_client = self._content_safety()
        cs_category = detect_content_safety(message, cs_client) if cs_client is not None else None
        if cs_category == "prompt_injection":
            self._log(
                "input", "prompt_injection", "block", "tentative d'injection de prompt",
                message, source="content_safety",
            )
            return Decision(
                allowed=False, action="block", category="prompt_injection",
                reason="tentative d'injection de prompt", refusal=_REFUSAL_INJECTION,
            )
        if cs_category is not None:
            self._log("input", cs_category, "block", "contenu interdit détecté", message, source="content_safety")
            return Decision(
                allowed=False, action="block", category=cs_category,
                reason="contenu interdit détecté", refusal=_refusal_moderation(cs_category),
            )

        llm_category = detect_moderation_llm(message, self._classifier_llm()) if _llm_cascade_enabled() else None
        if llm_category == "prompt_injection":
            self._log(
                "input", "prompt_injection", "block", "tentative d'injection de prompt",
                message, source="llm",
            )
            return Decision(
                allowed=False, action="block", category="prompt_injection",
                reason="tentative d'injection de prompt", refusal=_REFUSAL_INJECTION,
            )
        if llm_category is not None:
            self._log("input", llm_category, "block", "contenu interdit détecté", message, source="llm")
            return Decision(
                allowed=False, action="block", category=llm_category,
                reason="contenu interdit détecté", refusal=_refusal_moderation(llm_category),
            )

        if detect_out_of_scope(message):
            self._log("input", "out_of_scope", "block", "demande hors périmètre", message)
            return Decision(
                allowed=False, action="block", category="out_of_scope",
                reason="demande hors périmètre", refusal=_REFUSAL_OUT_OF_SCOPE,
            )

        pii_category = detect_pii(message)
        if pii_category is not None:
            self._log("input", pii_category, "block", "donnée sensible détectée", message)
            return Decision(
                allowed=False, action="block", category=pii_category,
                reason="donnée sensible détectée", refusal=_REFUSAL_SECRET_INPUT,
            )

        return Decision(allowed=True, action="allow")

    def check_output(self, text: str) -> Decision:
        """Contrôle une réponse sortante (PII, secrets, modération)."""
        category = detect_moderation(text)
        if category is not None:
            self._log("output", category, "block", "contenu interdit détecté", text)
            return Decision(
                allowed=False, action="block", category=category,
                reason="contenu interdit détecté", refusal=_REFUSAL_OUTPUT_BLOCKED,
            )

        # Cascade, cf. check_input : Content Safety puis LLM. `prompt_injection`
        # exclu ici (une réponse sortante n'est pas une tentative d'injection).
        cs_client = self._content_safety()
        cs_category = detect_content_safety(text, cs_client) if cs_client is not None else None
        if cs_category is not None and cs_category != "prompt_injection":
            self._log("output", cs_category, "block", "contenu interdit détecté", text, source="content_safety")
            return Decision(
                allowed=False, action="block", category=cs_category,
                reason="contenu interdit détecté", refusal=_REFUSAL_OUTPUT_BLOCKED,
            )

        llm_category = detect_moderation_llm(text, self._classifier_llm()) if _llm_cascade_enabled() else None
        if llm_category is not None and llm_category != "prompt_injection":
            self._log("output", llm_category, "block", "contenu interdit détecté", text, source="llm")
            return Decision(
                allowed=False, action="block", category=llm_category,
                reason="contenu interdit détecté", refusal=_REFUSAL_OUTPUT_BLOCKED,
            )

        pii_category = detect_pii(text)
        if pii_category is not None:
            self._log("output", pii_category, "block", "donnée sensible détectée", text)
            return Decision(
                allowed=False, action="block", category=pii_category,
                reason="donnée sensible détectée", refusal=_REFUSAL_OUTPUT_BLOCKED,
            )

        # cf. synthese.md : le hors-périmètre est contrôlé en entrée ET en
        # sortie — le LLM peut dériver spontanément (valorisation, conseil
        # juridique...) même si la demande initiale était légitime.
        if detect_out_of_scope(text):
            self._log("output", "out_of_scope", "block", "réponse hors périmètre", text)
            return Decision(
                allowed=False, action="block", category="out_of_scope",
                reason="réponse hors périmètre", refusal=_REFUSAL_OUT_OF_SCOPE,
            )

        return Decision(allowed=True, action="allow")
