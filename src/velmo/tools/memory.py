"""Outil mémoire : droit à l'oubli (R5, RGPD).

`MemoryManager.forget()` existait déjà et purgeait bien toutes les briques
(court terme, sémantique, vectoriel, épisodique, tampon), mais n'était
appelable qu'en Python — le LLM n'avait aucun moyen d'honorer une demande
« oublie mon adresse » formulée en conversation.

Cette couche traduit la formulation du LLM en termes de purge. Observé en
conditions réelles : sur « Oublie mon adresse de livraison », le modèle appelle
`forget_memory(target="adresse de livraison")` alors que la mémoire stocke la
phrase brute du client (« Mon adresse est 12 rue des Lilas a Paris. ») — le
matching littéral ne trouvait rien. `MemoryManager.forget()` reste la primitive
précise ; c'est ici qu'on retombe sur les mots porteurs de sens.
"""

from __future__ import annotations

import re

# Mots vides français : purger sur « de » ou « mon » viderait toute la mémoire.
_STOPWORDS = frozenset(
    {"de", "du", "des", "la", "le", "les", "mon", "ma", "mes", "un", "une",
     "au", "aux", "en", "et", "ou", "sur", "pour", "mes", "cette", "ce"}
)


def _content_words(target: str) -> list[str]:
    """Mots porteurs de sens d'une formulation (« adresse de livraison » → adresse, livraison)."""
    words = re.findall(r"[\w-]+", target.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def forget_memory(memory, user_id: str, target: str) -> dict:
    """Supprime les souvenirs correspondant à `target` pour un utilisateur.

    Renvoie `action="not_found"` quand rien n'a été supprimé : sans ça, l'agent
    confirmait à l'utilisateur une suppression RGPD qui n'avait pas eu lieu.
    """
    removed = memory.forget(user_id, target)

    # Expansion SYSTÉMATIQUE (pas un simple repli) : conditionner cette boucle à
    # `removed == 0` laissait passer le cas réel où la formulation littérale
    # supprimait un élément annexe tout en laissant la donnée visée en place —
    # l'agent confirmait alors une suppression incomplète.
    for word in _content_words(target):
        removed += memory.forget(user_id, word)

    if removed == 0:
        return {"action": "not_found", "target": target, "removed": 0}
    return {"action": "forgotten", "target": target, "removed": removed}
