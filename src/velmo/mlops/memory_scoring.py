"""Évaluation et scoring de la mémoire."""

import json
from pathlib import Path


def memory_score(agent) -> float:
    """Évalue la mémoire sur 12 cas : rejout tours, vérifie contexte.

    Args:
        agent: objet Agent avec memory et guardrails

    Returns:
        Taux de réussite dans [0.0, 1.0]
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    cases_file = project_root / "eval" / "memory_cases.jsonl"

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
        turns = case["turns"]
        evaluation = case["evaluation"]
        expected_substring = evaluation["expected_substring"]

        # Rejout chaque tour utilisateur pour construire la mémoire
        for turn in turns:
            if turn["role"] == "user":
                agent.respond(user_id, turn["content"])

        # Vérifie que le contexte mémoire contient l'info attendue
        memory_context = agent.memory.read(user_id, evaluation["question"]).render()
        total += 1
        if expected_substring.lower() in memory_context.lower():
            passed += 1

    if total == 0:
        return 0.0
    return passed / total
