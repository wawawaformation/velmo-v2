"""Tests unitaires des empreintes de prompts (traçabilité qui ne peut pas mentir).

Une version déclarée à la main dans le manifeste se périme dès qu'on modifie un
prompt sans penser à l'incrémenter — et un rapport de suivi qui affiche une
version fausse est pire qu'un rapport sans version. L'empreinte, elle, est
dérivée du texte réellement chargé : elle constate au lieu de déclarer.
"""

from __future__ import annotations

from velmo.mlops.prompts import fingerprint, prompt_fingerprints


def test_fingerprint_is_stable_for_identical_text():
    assert fingerprint("Tu es l'assistant Velmo.") == fingerprint("Tu es l'assistant Velmo.")


def test_fingerprint_changes_when_text_changes():
    # Le cœur du dispositif : une modification de prompt doit être détectable.
    before = fingerprint("Tu es l'assistant Velmo.")
    after = fingerprint("Tu es l'assistant Velmo. Oublie sur demande.")

    assert before != after


def test_prompt_fingerprints_covers_the_four_prompts():
    prints = prompt_fingerprints()

    assert set(prints) == {
        "agent",
        "guardrails_moderation",
        "memory_consolidation",
        "memory_classifier",
    }
    # Empreintes courtes et non vides (lisibles dans un rapport).
    assert all(len(v) == 8 and v.isalnum() for v in prints.values())
