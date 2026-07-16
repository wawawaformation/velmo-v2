"""POC LangFuse — Flask + Azure OpenAI + tracing.

Objectif : apprendre les traces Langfuse.
Une trace = un conteneur pour grouper tous les événements d'une requête utilisateur.
"""

import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langfuse import Langfuse
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import HumanMessage

load_dotenv()

# ==============================================================================
# INIT LANGFUSE
# ==============================================================================
# Langfuse Cloud = service d'observabilité pour LLM applications.
# On crée une instance avec nos clés (public + secret).
# Cette instance nous permet de créer des traces manuellement.
#
# Une trace est juste un conteneur : elle a un nom, des inputs, des outputs.
# À l'intérieur, on peut logger des "generations" (appels LLM) et d'autres events.
# ==============================================================================
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
)

# ==============================================================================
# INIT AZURE OPENAI
# ==============================================================================
# On utilise AzureAIOpenAIApiChatModel de LangChain (pas la lib OpenAI basique).
# C'est la même que dans Velmo.
# ==============================================================================
model = AzureAIOpenAIApiChatModel(
    endpoint=os.getenv("AZURE_AI_INFERENCE_ENDPOINT"),
    credential=os.getenv("AZURE_AI_INFERENCE_API_KEY"),
    model=os.getenv("AZURE_AI_INFERENCE_MODEL", "gpt-5.4"),
)

app = Flask(__name__)


@app.route("/ask", methods=["POST"])
def ask():
    """Endpoint : pose une question, reçoit une réponse tracée en Langfuse.

    Flux complet :
    1. Créer une trace Langfuse
    2. Appeler le LLM
    3. Logger la génération (what was sent, what was returned)
    4. Clore la trace (fin du contexte)
    """
    # ===========================================================================
    # ÉTAPE 0 : Parser la requête
    # ===========================================================================
    data = request.get_json()
    question = data.get("question", "")

    if not question:
        return jsonify({"error": "question required"}), 400

    # ===========================================================================
    # ÉTAPE 1 : CRÉER UNE TRACE
    # ===========================================================================
    # langfuse.trace() crée un nouveau conteneur pour tous les événements
    # qui vont suivre.
    #
    # Paramètres :
    #   - name: identifiant lisible ("ask_endpoint" ici)
    #   - input: dict de ce qui rentre (la question de l'utilisateur)
    #
    # Une trace a un ID unique (trace.id) et une URL visible sur cloud.langfuse.com.
    # ===========================================================================
    trace = langfuse.trace(
        name="ask_endpoint",
        input={"question": question},
    )

    try:
        # =======================================================================
        # ÉTAPE 2 : APPELER LE LLM
        # =======================================================================
        # On crée un HumanMessage (format LangChain standard).
        # On l'envoie au modèle.
        # Le modèle répond.
        #
        # Attention : à ce stade, Langfuse ne voit rien.
        # On n'a pas encore enregistré l'appel LLM nulle part.
        # =======================================================================
        message = HumanMessage(content=question)
        response = model.invoke([message])
        answer = response.content

        # =======================================================================
        # ÉTAPE 3 : LOGGER LA GÉNÉRATION
        # =======================================================================
        # trace.generation() = "une génération s'est produite dans cette trace".
        # C'est ce qui créera une "span" visuelle dans Langfuse.
        #
        # Paramètres :
        #   - name: nom de cette génération ("gpt-5.4_completion" ici)
        #   - input: ce qu'on a envoyé au modèle (messages)
        #   - output: ce que le modèle a retourné (réponse)
        #   - model: quel modèle on a utilisé (pour agrégation Langfuse)
        #
        # Cet enregistrement apparaît ensuite dans Langfuse Cloud sous la trace.
        # =======================================================================
        trace.generation(
            name="gpt-5.4_completion",
            input={"messages": [{"role": "user", "content": question}]},
            output={"message": answer},
            model=os.getenv("AZURE_AI_INFERENCE_MODEL", "gpt-5.4"),
        )

        # =======================================================================
        # ÉTAPE 4 : CLORE LA TRACE
        # =======================================================================
        # trace.end() = "on a terminé ce contexte".
        # On passe la réponse finale (output).
        #
        # Une fois end() appelé, Langfuse envoie la trace au serveur (en async).
        # Elle devient visible sur cloud.langfuse.com.
        # =======================================================================
        trace.end(output={"answer": answer})

        # Retourner la réponse + l'ID de la trace pour que le client puisse s'y référer.
        return jsonify({"answer": answer, "trace_id": trace.id}), 200

    except Exception as e:
        # En cas d'erreur, clore quand même la trace pour documenter le problème.
        trace.end(output={"error": str(e)})
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    print("🚀 POC LangFuse — Flask app starting...")
    print("   Endpoint: POST http://127.0.0.1:5000/ask")
    print("   Example: curl -X POST http://127.0.0.1:5000/ask \\")
    print('             -H "Content-Type: application/json" \\')
    print('             -d \'{"question": "What is 2+2?"}\'')
    print()
    print("📊 Traces seront visibles sur https://cloud.langfuse.com")
    print()
    app.run(debug=True, port=5000)
