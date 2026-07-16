"""POC LangFuse — Flask + Azure OpenAI (sans tracing pour l'instant)."""

import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

load_dotenv()

# Init Azure OpenAI (via LangChain, comme Velmo)
model = AzureAIOpenAIApiChatModel(
    endpoint=os.getenv("AZURE_AI_INFERENCE_ENDPOINT"),
    credential=os.getenv("AZURE_AI_INFERENCE_API_KEY"),
    model=os.getenv("AZURE_AI_INFERENCE_MODEL", "gpt-5.4"),
)

app = Flask(__name__)


@app.route("/ask", methods=["POST"])
def ask():
    """Endpoint : pose une question, get une réponse."""
    data = request.get_json()
    question = data.get("question", "")

    if not question:
        return jsonify({"error": "question required"}), 400

    try:
        # Appel LLM via Azure (LangChain)
        from langchain_core.messages import HumanMessage

        message = HumanMessage(content=question)
        response = model.invoke([message])
        answer = response.content

        return jsonify({"answer": answer}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    print("🚀 Flask app starting...")
    print("   Endpoint: POST http://127.0.0.1:5000/ask")
    print("   Example: curl -X POST http://127.0.0.1:5000/ask \\")
    print('             -H "Content-Type: application/json" \\')
    print('             -d \'{"question": "What is 2+2?"}\'')
    print()
    app.run(debug=True, port=5000)
