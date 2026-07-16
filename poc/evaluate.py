"""Évaluer le modèle en utilisant un dataset Langfuse + LLM-as-a-Judge.

Objectif : charger un dataset, lancer chaque cas contre le modèle,
et scorer avec un juge IA (LLM-as-a-Judge).

Le juge évalue la qualité de la réponse selon :
- Pertinence, Clarté, Exactitude, Complétude, Concision
"""

import os
import requests
import json
from dotenv import load_dotenv
from langfuse import Langfuse
from judge import judge_response

load_dotenv()

# Init Langfuse
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
)

# URL de l'API Flask locale
API_URL = "http://127.0.0.1:5000/ask"


def evaluate_dataset(dataset_name: str):
    """Évaluer un dataset en envoyant chaque item au modèle.

    Flux :
    1. Charger le dataset
    2. Pour chaque item :
       a. Envoyer la question à app.py
       b. Récupérer la réponse
       c. Comparer avec expected_output
       d. Scorer sur Langfuse
    """

    print(f"🚀 Évaluation du dataset : {dataset_name}")
    print()

    # =========================================================================
    # ÉTAPE 1 : CHARGER LE DATASET
    # =========================================================================
    # langfuse.get_dataset(name) récupère un dataset existant.
    # =========================================================================
    try:
        dataset = langfuse.get_dataset(name=dataset_name)
    except Exception as e:
        print(f"❌ Dataset not found: {dataset_name}")
        print(f"   Erreur : {e}")
        return

    print(f"✅ Dataset chargé : {dataset.name}")
    print()

    # =========================================================================
    # ÉTAPE 2 : ITÉRER SUR LES ITEMS ET ÉVALUER
    # =========================================================================
    # Pour chaque item du dataset :
    # 1. Envoyer la question au modèle
    # 2. Comparer la réponse avec expected_output
    # 3. Scorer automatiquement (1.0 si correct, 0.0 sinon)
    # =========================================================================
    scores = []
    run_name = f"eval_run_{dataset_name}"

    print(f"📊 Évaluation en cours...")
    print()

    # Accéder aux items du dataset
    for idx, item in enumerate(dataset.items, start=1):
        question_text = item.input.get("question", "")
        expected_answer = item.expected_output.get("answer", "") if item.expected_output else None

        print(f"[{idx}] Question : {question_text}")

        try:
            # =================================================================
            # APPEL AU MODÈLE
            # =================================================================
            # On envoie la question à app.py via HTTP.
            # app.py retourne la réponse + trace_id.
            # =================================================================
            response = requests.post(
                API_URL,
                json={"question": question_text},
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            model_answer = data.get("answer", "")
            trace_id = data.get("trace_id", "")

            print(f"    Réponse : {model_answer}")
            print(f"    Attendu : {expected_answer}")

            # =================================================================
            # ÉVALUATION AVEC LE JUGE (LLM-AS-A-JUDGE)
            # =================================================================
            # Au lieu de faire un simple exact match, on demande à un juge IA
            # d'évaluer la qualité de la réponse.
            #
            # Le juge considère :
            # - Pertinence, Clarté, Exactitude, Complétude, Concision
            #
            # Il retourne un score 0.0-1.0 (pas juste 0 ou 1).
            # =================================================================
            print(f"    🤔 Judge is evaluating...")
            score = judge_response(question_text, model_answer)
            print(f"    Judge Score : {score:.2f} ")

            # Interpréter le score pour affichage visuel
            if score >= 0.8:
                status = "✅ Excellent"
            elif score >= 0.6:
                status = "👍 Bon"
            elif score >= 0.4:
                status = "⚠️  Passable"
            else:
                status = "❌ Mauvais"
            print(f"    {status}")

            print(f"    Trace ID : {trace_id}")

            # =================================================================
            # ENREGISTRER LE SCORE DU JUGE DANS LANGFUSE
            # =================================================================
            # On enregistre le score du juge (pas un simple 0/1).
            #
            # Paramètres :
            #   - name: "judge_score" (pour différencier du scoring simple)
            #   - value: score du juge (0.0-1.0, nuancé)
            #   - trace_id: l'ID de la trace (créée par app.py)
            #   - data_type: "NUMERIC"
            #   - comment: explications pour déboguer
            #
            # Le score nuancé du juge apparaît dans Langfuse Cloud.
            # =================================================================
            if trace_id:
                print(f"    📊 Posting judge score to Langfuse...")
                langfuse.create_score(
                    name="judge_score",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                    comment=f"Judge evaluated: {model_answer[:100]}...",
                )
                print(f"    ✅ Score posted")

            scores.append(score)

        except requests.exceptions.RequestException as e:
            print(f"    ❌ Erreur requête : {e}")
            scores.append(0.0)

        print()

    # =========================================================================
    # ÉTAPE 3 : RÉSUMÉ
    # =========================================================================
    if scores:
        avg_score = sum(scores) / len(scores)
        print("=" * 70)
        print(f"📊 RÉSUMÉ")
        print(f"   Items évalués : {len(scores)}")
        print(f"   Score moyen : {avg_score:.2%}")
        print(f"   Réussis : {sum(1 for s in scores if s > 0)} / {len(scores)}")
        print("=" * 70)
        print()
        print(f"✅ Traces créées sur cloud.langfuse.com (voir la section Traces)")
    else:
        print("❌ Aucun item évalué.")


if __name__ == "__main__":
    print("========================================================================")
    print("ÉVALUATION LANGFUSE")
    print("========================================================================")
    print()
    print("⚠️  Assure-toi que app.py tourne sur http://127.0.0.1:5000")
    print()

    # Évaluer le dataset "math_questions" créé par datasets.py
    evaluate_dataset("math_questions")
