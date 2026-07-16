"""POC LangFuse — Flask + Azure OpenAI + tracing.

Objectif : apprendre les traces Langfuse.
Une trace = un conteneur pour grouper tous les événements d'une requête utilisateur.
"""

import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langfuse import Langfuse
from langfuse.types import TraceContext
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import HumanMessage

load_dotenv()

# ==============================================================================
# INIT LANGFUSE
# ==============================================================================
# Langfuse Cloud = service d'observabilité pour LLM applications.
# On crée une instance avec nos clés (public + secret).
# Cette instance nous permet de créer des events et des spans.
#
# Une trace est juste un conteneur : elle a un nom, des inputs, des outputs.
# À l'intérieur, on peut logger des "events" (appels LLM, outils, etc.)
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
    1. Créer un ID de trace et un TraceContext
    2. Appeler le LLM
    3. Logger l'événement avec le contexte de trace
    """
    # ===========================================================================
    # ÉTAPE 0 : Parser la requête
    # ===========================================================================
    data = request.get_json()
    question = data.get("question", "")

    if not question:
        return jsonify({"error": "question required"}), 400

    # ===========================================================================
    # ÉTAPE 1 : CRÉER UN ID ET CONTEXTE DE TRACE
    # ===========================================================================
    # langfuse.create_trace_id() génère un ID unique pour cette requête.
    # TraceContext est un conteneur qui relie tous les événements ensemble.
    #
    # Une trace = un conteneur pour grouper tous les événements relatifs
    # à une requête utilisateur (appels LLM, outils, etc.)
    #
    # L'ID est visible sur cloud.langfuse.com pour trouver ta trace.
    # ===========================================================================
    trace_id = langfuse.create_trace_id()
    trace_context = TraceContext(trace_id=trace_id)

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
        # ÉTAPE 3 : LOGGER L'ÉVÉNEMENT
        # =======================================================================
        # langfuse.create_event() = enregistrer un événement dans cette trace.
        #
        # Paramètres :
        #   - trace_context: le contexte de trace créé plus haut (pour grouper)
        #   - name: nom de cet événement ("ask_endpoint" ici)
        #   - input: ce qu'on a reçu (la question)
        #   - output: ce qu'on a retourné (la réponse)
        #
        # Cet enregistrement apparaît ensuite dans Langfuse Cloud sous le trace_id.
        # ===========================================================================
        langfuse.create_event(
            trace_context=trace_context,
            name="ask_endpoint",
            input={"question": question},
            output={"answer": answer},
        )

        # Retourner la réponse + l'ID de la trace pour que le client puisse s'y référer.
        return jsonify({"answer": answer, "trace_id": trace_id}), 200

    except Exception as e:
        # En cas d'erreur, enregistrer quand même l'erreur dans la trace.
        langfuse.create_event(
            trace_context=trace_context,
            name="ask_endpoint_error",
            input={"question": question},
            output={"error": str(e)},
        )
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
