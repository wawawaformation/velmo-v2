"""Tests unitaires de l'outil d'oubli (R5) — robustesse et honnêteté du verdict.

Bug réel observé contre le vrai LLM : sur « Oublie mon adresse de livraison »,
le modèle appelle `forget_memory(target="adresse de livraison")` alors que la
mémoire stocke le texte brut du client (« Mon adresse est 12 rue des Lilas a
Paris. »). Le matching littéral ne trouvait rien (`removed=0`), mais l'outil
renvoyait quand même une forme de succès — l'agent confirmait à l'utilisateur
une suppression RGPD qui n'avait pas eu lieu.
"""

from __future__ import annotations

from velmo.tools.memory import forget_memory


class FakeMemory:
    """Mémoire simulée : `forget` supprime par sous-chaîne, comme la vraie."""

    def __init__(self, contents: list[str]) -> None:
        self.contents = list(contents)

    def forget(self, user_id: str, target: str) -> int:
        matches = [c for c in self.contents if target.lower() in c.lower()]
        self.contents = [c for c in self.contents if target.lower() not in c.lower()]
        return len(matches)


def test_forget_matches_natural_language_target():
    # Le LLM formule « adresse de livraison » ; la mémoire stocke la phrase brute.
    memory = FakeMemory(["Mon adresse est 12 rue des Lilas a Paris."])

    result = forget_memory(memory, "u1", "adresse de livraison")

    assert result["removed"] == 1
    assert result["action"] == "forgotten"
    assert memory.contents == []


def test_forget_reports_not_found_instead_of_false_success():
    # Rien à supprimer : l'outil ne doit PAS laisser croire à une suppression.
    memory = FakeMemory(["Ma pointure est du 43."])

    result = forget_memory(memory, "u1", "numero de contrat")

    assert result["removed"] == 0
    assert result["action"] == "not_found"
    assert memory.contents == ["Ma pointure est du 43."]


def test_forget_expands_even_when_literal_match_is_partial():
    # Piège réel observé en éval : un match littéral trouvait UN élément, ce qui
    # court-circuitait l'expansion en mots porteurs — la donnée réellement visée
    # (« Mon adresse est 12 rue des Lilas… ») restait en mémoire alors que
    # l'agent confirmait la suppression.
    memory = FakeMemory(
        [
            "Preference : adresse de livraison par defaut.",  # matche litteralement
            "Mon adresse est 12 rue des Lilas a Paris.",  # la vraie cible
        ]
    )

    result = forget_memory(memory, "u1", "adresse de livraison")

    assert result["removed"] == 2
    assert memory.contents == []


def test_forget_literal_target_still_works():
    # Cas simple : le terme figure littéralement.
    memory = FakeMemory(["Ma commande O-2024-0199 me pose souci."])

    result = forget_memory(memory, "u1", "O-2024-0199")

    assert result["removed"] == 1
    assert result["action"] == "forgotten"
