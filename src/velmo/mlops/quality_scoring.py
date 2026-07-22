"""Évaluation et scoring de la qualité."""

import json
from pathlib import Path


def quality_score(agent) -> float:
    """Évalue la qualité sur 8 cas : questions métier courantes.

    Args:
        agent: objet Agent avec respond(user_id, message) -> str

    Returns:
        Taux de réussite dans [0.0, 1.0]
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    cases_file = project_root / "eval" / "quality_cases.jsonl"

    cases = []
    with open(cases_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    total = 0
    passed = 0

    for case in cases:
        user_id = case["user_id"]
        question = case["question"]
        expected_substring = case["expected_substring"]

        # Appelle l'agent pour obtenir une réponse
        reply = agent.respond(user_id, question)

        # Vérifie que l'info attendue apparaît dans la réponse
        total += 1
        if expected_substring.lower() in reply.lower():
            passed += 1

    if total == 0:
        return 0.0
    return passed / total
