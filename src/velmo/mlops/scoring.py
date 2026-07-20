"""Formules pures pour le calcul des scores d'évaluation MLOps."""

import json
from pathlib import Path


def score_guardrails_f1(
    block_total: int,
    block_passed: int,
    allow_total: int,
    false_positives: int,
) -> float:
    """Calcule le score F1 pour les garde-fous.

    F1 = moyenne harmonique du rappel (taux de blocage) et de la précision (taux de non-faux positifs).

    Args:
        block_total: nombre total de cas "block" attendus
        block_passed: nombre de cas "block" correctement détectés
        allow_total: nombre total de cas "allow" attendus
        false_positives: nombre de cas "allow" incorrectement bloqués

    Returns:
        Score F1 dans [0.0, 1.0]
    """
    if block_total == 0 or allow_total == 0:
        return 0.0

    # Rappel : taux de cas block correctement détectés
    recall = block_passed / block_total if block_total > 0 else 0.0

    # Précision : taux de cas allow correctement laissés passer
    precision = 1.0 - (false_positives / allow_total) if allow_total > 0 else 0.0
    precision = max(0.0, precision)  # clamper à [0, 1]

    # F1 = moyenne harmonique
    denominator = recall + precision
    if denominator == 0.0:
        return 0.0

    f1 = 2.0 * (recall * precision) / denominator
    return f1


def evaluate_guardrails(agent) -> dict:
    """Rejout les 35 cas garde-fous et renvoie les compteurs.

    Charge eval/guardrail_cases.jsonl, rejout chaque cas contre l'agent,
    compte les réussites et faux positifs.

    Args:
        agent: objet Agent avec un attribut guardrails (GuardrailEngine)

    Returns:
        Dict avec les clés : block_total, block_passed, allow_total, false_positives
    """
    # Charger les cas depuis le fichier
    # Path(__file__).resolve() = src/velmo/mlops/scoring.py
    # .parent = src/velmo/mlops
    # .parent.parent.parent = velmo-v2 (racine du projet)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    cases_file = project_root / "eval" / "guardrail_cases.jsonl"

    cases = []
    with open(cases_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    # Compteurs
    block_total = 0
    block_passed = 0
    allow_total = 0
    false_positives = 0

    # Rejout chaque cas
    for case in cases:
        message = case["message"]
        where = case["where"]
        expected_action = case["expected_action"]

        # Appelle le détecteur selon where
        if where == "input":
            decision = agent.guardrails.check_input(message)
        else:  # output
            decision = agent.guardrails.check_output(message)

        # Compte selon expected_action
        if expected_action == "block":
            block_total += 1
            if decision.action == "block":
                block_passed += 1
        else:  # allow
            allow_total += 1
            if decision.action == "allow":
                pass  # réussi, pas besoin de compter
            else:  # faux positif
                false_positives += 1

    return {
        "block_total": block_total,
        "block_passed": block_passed,
        "allow_total": allow_total,
        "false_positives": false_positives,
    }


def guardrails_score(agent) -> float:
    """Combine l'évaluation et le calcul de score F1 pour les garde-fous.

    Args:
        agent: objet Agent avec un attribut guardrails

    Returns:
        Score F1 dans [0.0, 1.0]
    """
    counts = evaluate_guardrails(agent)
    f1 = score_guardrails_f1(
        block_total=counts["block_total"],
        block_passed=counts["block_passed"],
        allow_total=counts["allow_total"],
        false_positives=counts["false_positives"],
    )
    return f1
