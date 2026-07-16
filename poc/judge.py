"""LLM-as-a-Judge — utiliser un modèle pour évaluer les réponses.

Objectif : pour les questions ouvertes (sans expected_output fixe),
faire juger la qualité de la réponse par un modèle IA.

Concept :
- Question utilisateur : "Pourquoi le ciel est bleu ?"
- Réponse du modèle : "Le ciel est bleu car..."
- Judge (LLM) : évalue la réponse → score 0.0-1.0

Utile en production quand on ne connaît pas la "bonne" réponse à l'avance.
"""

import os
from dotenv import load_dotenv
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

# ==============================================================================
# INIT LE JUGE (un modèle dédié à l'évaluation)
# ==============================================================================
# Le juge est un modèle Azure (gpt-5.4 par défaut).
# Il va recevoir un prompt système et une question à évaluer.
#
# On utilise le même modèle que l'agent principal (gpt-5.4), mais avec
# un rôle différent : juger la qualité, pas répondre directement.
# ==============================================================================
judge_model = AzureAIOpenAIApiChatModel(
    endpoint=os.getenv("AZURE_AI_INFERENCE_ENDPOINT"),
    credential=os.getenv("AZURE_AI_INFERENCE_API_KEY"),
    model=os.getenv("AZURE_AI_JUDGE_MODEL", "gpt-5.4"),
)

# ==============================================================================
# SYSTÈME PROMPT POUR LE JUGE
# ==============================================================================
# Ce prompt définit le rôle et les instructions du juge.
#
# Le juge doit :
# 1. Évaluer la qualité de la réponse (pas juste correcte/incorrect)
# 2. Donner une note NUMÉRIQUE (pas du texte)
# 3. Être cohérent d'une évaluation à l'autre
#
# Format attendu : un nombre entre 0.0 et 1.0
# ==============================================================================
JUDGE_SYSTEM_PROMPT = """Tu es un évaluateur d'IA. Ton travail est de noter la qualité des réponses.

Critères d'évaluation :
- Pertinence : la réponse répond-elle à la question ?
- Clarté : la réponse est-elle compréhensible ?
- Exactitude : l'information est-elle correcte ?
- Complétude : manque-t-il des éléments importants ?
- Concision : la réponse est-elle succincte ou trop verbeux ?

Réponds UNIQUEMENT avec un nombre entre 0.0 et 1.0.
- 1.0 = réponse excellente, complète, correcte et concise
- 0.7 = réponse bonne, mais quelques manques ou légèrement verbeux
- 0.5 = réponse correcte mais incomplète, peu claire ou trop long
- 0.3 = réponse partiellement correcte, confuse ou redondante
- 0.0 = réponse incorrecte ou hors sujet

Ne réponds QUE avec le nombre. Pas de texte supplémentaire.
"""


def judge_response(question: str, model_answer: str) -> float:
    """Juger une réponse de modèle et retourner un score.

    Paramètres :
        question (str) : la question posée à l'utilisateur
        model_answer (str) : la réponse du modèle à évaluer

    Retour :
        float : score entre 0.0 et 1.0

    Processus :
    1. Construire le prompt pour le juge
    2. Appeler le juge (via le modèle Azure)
    3. Parser la réponse (doit être un nombre)
    4. Cliper le score entre 0.0 et 1.0 (au cas où le juge répond mal)
    5. Retourner le score
    """

    # =========================================================================
    # ÉTAPE 1 : CONSTRUIRE LE PROMPT POUR LE JUGE
    # =========================================================================
    # On crée un message au juge avec :
    # - Le système prompt (rôle et instructions)
    # - La question utilisateur
    # - La réponse du modèle à évaluer
    #
    # Format : "Évalue cette réponse : [question] [réponse]"
    # =========================================================================
    judge_prompt = f"""Évalue cette réponse :

QUESTION : {question}

RÉPONSE DU MODÈLE : {model_answer}

Donne un score entre 0.0 et 1.0. Rien que le nombre."""

    # =========================================================================
    # ÉTAPE 2 : APPELER LE JUGE
    # =========================================================================
    # On envoie le prompt au juge via le modèle Azure.
    # Les messages LangChain sont des objets : SystemMessage + HumanMessage.
    #
    # SystemMessage = instructions du juge (son rôle)
    # HumanMessage = la tâche à accomplir (évaluer la réponse)
    # =========================================================================
    messages = [
        SystemMessage(content=JUDGE_SYSTEM_PROMPT),
        HumanMessage(content=judge_prompt),
    ]

    try:
        response = judge_model.invoke(messages)
        judge_output = response.content.strip()

        # =====================================================================
        # ÉTAPE 3 : PARSER LA RÉPONSE
        # =====================================================================
        # Le juge doit répondre avec juste un nombre (0.0-1.0).
        # On essaie de le convertir en float.
        #
        # Si la conversion échoue (le juge a répondu autre chose),
        # on loggue une erreur et on retourne 0.5 par défaut.
        # =====================================================================
        try:
            score = float(judge_output)
        except ValueError:
            print(f"⚠️  Judge output not numeric: {judge_output}")
            print(f"    Defaulting to 0.5")
            return 0.5

        # =====================================================================
        # ÉTAPE 4 : CLIPER LE SCORE
        # =====================================================================
        # Au cas où le juge répond un nombre en dehors de [0.0, 1.0],
        # on le force dans cette plage.
        #
        # Exemple : si le juge répond 1.5 ou -0.2, on ajuste.
        # =====================================================================
        score = max(0.0, min(1.0, score))

        return score

    except Exception as e:
        # En cas d'erreur (réseau, modèle indisponible, etc.),
        # on loggue et on retourne 0.5 par défaut.
        print(f"❌ Judge error: {e}")
        return 0.5


if __name__ == "__main__":
    # =========================================================================
    # EXEMPLE D'USAGE
    # =========================================================================
    # Tester le juge avec quelques exemples.
    # =========================================================================

    print("=" * 70)
    print("LLM-AS-A-JUDGE TEST")
    print("=" * 70)
    print()

    # Exemple 1 : Une très bonne réponse
    question_1 = "Pourquoi le ciel est bleu ?"
    answer_1 = """Le ciel apparaît bleu à cause de la diffusion Rayleigh.
    La lumière du soleil contient toutes les couleurs du spectre visible.
    Lorsque la lumière traverse l'atmosphère, elle se heurte aux molécules
    d'azote et d'oxygène. Les ondes courtes (bleu et violet) se diffusent
    plus facilement que les ondes longues (rouge et orange). C'est pourquoi
    le ciel apparaît bleu pendant le jour."""

    print(f"[1] Question: {question_1}")
    print(f"    Answer: {answer_1[:60]}...")
    score_1 = judge_response(question_1, answer_1)
    print(f"    Judge Score: {score_1} ✅")
    print()

    # Exemple 2 : Une réponse partiellement correcte
    question_2 = "Pourquoi le ciel est bleu ?"
    answer_2 = "Le ciel est bleu parce que c'est comme ça."

    print(f"[2] Question: {question_2}")
    print(f"    Answer: {answer_2}")
    score_2 = judge_response(question_2, answer_2)
    print(f"    Judge Score: {score_2} ⚠️")
    print()

    # Exemple 3 : Une réponse hors sujet
    question_3 = "Pourquoi le ciel est bleu ?"
    answer_3 = "Les pommes sont rouges."

    print(f"[3] Question: {question_3}")
    print(f"    Answer: {answer_3}")
    score_3 = judge_response(question_3, answer_3)
    print(f"    Judge Score: {score_3} ❌")
    print()

    print("=" * 70)
    print(f"Test complet. Scores : {score_1:.2f}, {score_2:.2f}, {score_3:.2f}")
    print("=" * 70)
