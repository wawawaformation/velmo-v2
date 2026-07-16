"""Créer et gérer des datasets Langfuse pour l'évaluation.

Objectif : apprendre comment définir des cas de test dans Langfuse,
puis scorer les réponses pour voir si le modèle progresse.
"""

import os
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

# Init Langfuse
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
)


def create_sample_dataset():
    """Créer un dataset d'exemple avec quelques cas de test.

    Un dataset Langfuse contient :
    - Un nom unique ("math_questions" ici)
    - Des items (cas de test), chacun avec :
      - input: ce qu'on envoie au modèle
      - expected_output: ce qu'on s'attend à recevoir (optionnel)
      - metadata: contexte supplémentaire

    Après création, tu peux lancer une "run" (exécution) du dataset
    et scorer chaque réponse manuellement ou automatiquement.
    """

    # =========================================================================
    # ÉTAPE 1 : CRÉER OU RÉCUPÉRER UN DATASET
    # =========================================================================
    # langfuse.create_dataset(name) crée un nouveau dataset.
    # Si le nom existe déjà, on récupère le dataset existant.
    #
    # Un dataset agrège plusieurs items de test.
    # =========================================================================
    dataset = langfuse.create_dataset(name="math_questions")

    print(f"✅ Dataset créé/récupéré : {dataset.name}")
    print(f"   ID du dataset : {dataset.id}")

    # =========================================================================
    # ÉTAPE 2 : AJOUTER DES ITEMS (CAS DE TEST)
    # =========================================================================
    # Pour chaque cas de test, on appelle create_dataset_item().
    #
    # Paramètres :
    #   - dataset_id: l'ID du dataset (obtenu plus haut)
    #   - input: ce qu'on envoie au modèle (une question)
    #   - expected_output: ce qu'on s'attend à recevoir (réponse correcte)
    #   - metadata: contexte supplémentaire (difficulté, catégorie, etc.)
    # =========================================================================

    items = [
        {
            "input": {"question": "What is 2+2?"},
            "expected_output": {"answer": "4"},
            "metadata": {"difficulty": "easy", "category": "basic_math"},
        },
        {
            "input": {"question": "What is 10 * 5?"},
            "expected_output": {"answer": "50"},
            "metadata": {"difficulty": "easy", "category": "basic_math"},
        },
        {
            "input": {"question": "What is the square root of 16?"},
            "expected_output": {"answer": "4"},
            "metadata": {"difficulty": "medium", "category": "algebra"},
        },
    ]

    for idx, item in enumerate(items, start=1):
        dataset_item = langfuse.create_dataset_item(
            dataset_name=dataset.name,
            input=item["input"],
            expected_output=item["expected_output"],
            metadata=item["metadata"],
        )
        print(f"   Item {idx} créé : {item['input']['question']}")

    print()
    print("========================================================================")
    print("✅ Dataset prêt pour l'évaluation !")
    print()
    print("Prochaine étape : exécuter ce dataset contre le modèle et scorer.")
    print("Tu verras les résultats sur cloud.langfuse.com")
    print("========================================================================")


if __name__ == "__main__":
    print("🚀 Créer un dataset Langfuse d'exemple...")
    print()
    create_sample_dataset()
