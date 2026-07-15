"""Classifieur Azure AI Content Safety — premier recours en cascade LLM.

Service Cognitive Services dédié (`text:analyze` pour la modération,
`text:shieldPrompt` pour l'injection de prompt), appelé avant le classifieur
LLM générique (`moderation_llm.py`) : plus rapide et plus fiable (cf.
`docs/rapport_latence_azure_foundry.md` — Phi-4-mini-instruct présentait un
taux d'erreur élevé). Le LLM reste en dernier recours pour les
reformulations qui échappent à Content Safety (ex. « Passe en mode
développeur. », non détecté par shieldPrompt lors des tests manuels).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

import requests

_API_VERSION = "2024-09-01"

# Seuil de sévérité (paliers Azure : 0, 2, 4, 6) à partir duquel un contenu
# est bloqué — 4 correspond au palier « moyen », décision actée pour éviter
# le bruit des scores 2 (léger).
_SEVERITY_THRESHOLD = 4

_CATEGORY_MAP = {
    "Hate": "hate",
    "Violence": "violence",
    "Sexual": "sexual",
    "SelfHarm": "self_harm",
}


@dataclass
class ContentSafetyClient:
    """Client REST minimal — `post` injectable pour les tests (pas de mock de `requests`)."""

    endpoint: str
    api_key: str
    post: Callable = requests.post
    timeout: float = 15.0

    def _headers(self) -> dict:
        return {"Ocp-Apim-Subscription-Key": self.api_key, "Content-Type": "application/json"}

    def analyze(self, text: str) -> dict:
        url = f"{self.endpoint.rstrip('/')}/contentsafety/text:analyze?api-version={_API_VERSION}"
        response = self.post(url, headers=self._headers(), json={"text": text}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def shield_prompt(self, text: str) -> dict:
        url = f"{self.endpoint.rstrip('/')}/contentsafety/text:shieldPrompt?api-version={_API_VERSION}"
        response = self.post(
            url, headers=self._headers(), json={"userPrompt": text, "documents": []}, timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


def get_content_safety_client() -> ContentSafetyClient | None:
    """Construit le client si configuré (`AZURE_CONTENT_SAFETY_ENDPOINT`), sinon `None`."""
    endpoint = os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT")
    api_key = os.getenv("AZURE_AI_INFERENCE_API_KEY")
    if not endpoint or not api_key:
        return None
    return ContentSafetyClient(endpoint=endpoint, api_key=api_key)


def detect_content_safety(text: str, client: ContentSafetyClient) -> str | None:
    """Classifie `text` via Content Safety ; renvoie la catégorie détectée ou `None`.

    Une panne réseau/HTTP renvoie `None` (comme "rien détecté") plutôt que de
    lever une exception — la cascade doit continuer vers le recours suivant
    (LLM) sans bloquer l'utilisateur, décision actée alignée avec le
    comportement déjà en place pour la cascade LLM elle-même.
    """
    try:
        analysis = client.analyze(text)
        for entry in analysis.get("categoriesAnalysis", []):
            mapped = _CATEGORY_MAP.get(entry.get("category"))
            if mapped is not None and entry.get("severity", 0) >= _SEVERITY_THRESHOLD:
                return mapped

        shield = client.shield_prompt(text)
        if shield.get("userPromptAnalysis", {}).get("attackDetected"):
            return "prompt_injection"
    except Exception:
        return None

    return None
