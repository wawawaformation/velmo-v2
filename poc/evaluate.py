"""Évaluer le modèle en utilisant un dataset Langfuse.

Objectif : charger un dataset, lancer chaque cas contre le modèle,
et scorer automatiquement si la réponse est correcte.
"""

import os
import requests
import json
from dotenv import load_dotenv
from langfuse import Langfuse

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
            # ÉVALUATION
            # =================================================================
            # Comparaison simple : exact match (tu peux affiner plus tard).
            # Si ça correspond, score = 1.0, sinon 0.0.
            # =================================================================
            is_correct = expected_answer and expected_answer.lower() in model_answer.lower()
            score = 1.0 if is_correct else 0.0

            print(f"    Score : {score} {'✅' if is_correct else '❌'}")
            print(f"    Trace ID : {trace_id}")

            # =================================================================
            # ENREGISTRER LE SCORE DANS LANGFUSE
            # =================================================================
            # langfuse.create_score() attache un score à une trace existante.
            #
            # Paramètres :
            #   - name: nom du score ("correctness" ici)
            #   - value: score numérique (0.0-1.0)
            #   - trace_id: l'ID de la trace (créée par app.py)
            #   - data_type: type de la valeur (NUMERIC ici)
            #   - comment: optionnel, pour documenter
            #
            # Le score apparaît ensuite dans Langfuse Cloud attaché à la trace.
            # =================================================================
            if trace_id:
                print(f"    📊 Posting score to Langfuse...")
                langfuse.create_score(
                    name="correctness",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                    comment=f"Expected: {expected_answer}, Got: {model_answer}",
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
