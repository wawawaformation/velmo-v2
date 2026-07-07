"""Tests unitaires du détecteur hors-périmètre.

Cas réels tirés de eval/guardrail_cases.jsonl (catégorie out_of_scope).
"""

from __future__ import annotations

from velmo.guardrails.scope import detect_out_of_scope


def test_detects_out_of_scope():
    samples = [
        "Combien vaut mon maillot Maradona 86 aujourd'hui ?",
        "Quelle est la cote de mon maillot Bresil 1970 a la revente ?",
        "Sur quel placement en bourse investir mes gains de revente ?",
        "Peux-tu authentifier ce maillot que j'ai achete sur un autre site ?",
        "Donne-moi un conseil juridique pour attaquer un autre vendeur.",
    ]
    for message in samples:
        assert detect_out_of_scope(message) is True


def test_allows_legitimate_messages():
    samples = [
        "Quel est le statut de ma commande O-2024-0101 ?",
        "Vos maillots sont-ils authentiques avec certificat ?",
        "Comment retourner un maillot qui ne me va pas ?",
        "Faites-vous du reassort sur le maillot France 1998 ?",
    ]
    for message in samples:
        assert detect_out_of_scope(message) is False
