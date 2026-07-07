"""Garde-fous d'entrée et de sortie de l'agent Velmo.

Surface publique stable consommée par l'agent et la suite d'acceptance.
V1 : détection par règles déterministes (hors-ligne), cf.
conception/garde-fous/synthese.md pour la trajectoire vers des services
Azure AI Foundry (Content Safety, Conversational PII redaction) en v2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .moderation import detect_moderation
from .pii import detect_pii
from .prompt_injection import detect_prompt_injection
from .scope import detect_out_of_scope

# Catégories de contenus contrôlés.
CATEGORIES = (
    "hate",
    "violence",
    "sexual",
    "pii",
    "out_of_scope",
    "prompt_injection",
    "secret_leak",
)

_REFUSAL_MODERATION = (
    "Je ne peux pas donner suite à ce message. Je reste à votre disposition "
    "pour vos commandes, livraisons, retours et la FAQ Velmo."
)
_REFUSAL_INJECTION = (
    "Je ne peux pas suivre cette instruction. Je reste à votre disposition "
    "pour vos commandes, livraisons, retours et la FAQ Velmo."
)
_REFUSAL_OUT_OF_SCOPE = (
    "Cette demande sort du périmètre du support Velmo (maillots collector, "
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
    """Applique les garde-fous d'entrée et de sortie et journalise les décisions."""

    events: list[dict] = field(default_factory=list)

    def _log(self, stage: str, category: str, action: str, reason: str, text: str) -> None:
        # PII/secret_leak : jamais la donnée brute, même tronquée — un secret court
        # situé en début de message survivrait à une troncature à 40 caractères.
        if category in _SENSITIVE_CATEGORIES:
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
            }
        )

    def check_input(self, message: str) -> Decision:
        """Contrôle un message entrant (modération, injection, périmètre)."""
        category = detect_moderation(message)
        if category is not None:
            self._log("input", category, "block", "contenu interdit détecté", message)
            return Decision(
                allowed=False, action="block", category=category,
                reason="contenu interdit détecté", refusal=_REFUSAL_MODERATION,
            )

        if detect_prompt_injection(message):
            self._log("input", "prompt_injection", "block", "tentative d'injection de prompt", message)
            return Decision(
                allowed=False, action="block", category="prompt_injection",
                reason="tentative d'injection de prompt", refusal=_REFUSAL_INJECTION,
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

        pii_category = detect_pii(text)
        if pii_category is not None:
            self._log("output", pii_category, "block", "donnée sensible détectée", text)
            return Decision(
                allowed=False, action="block", category=pii_category,
                reason="donnée sensible détectée", refusal=_REFUSAL_OUTPUT_BLOCKED,
            )

        return Decision(allowed=True, action="allow")
