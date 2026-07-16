# POC LangFuse — Minimal

Comprendre LangFuse Cloud en 30 min.

## Setup

### 1. Créer compte Langfuse Cloud

https://cloud.langfuse.com → Sign up gratuit

### 2. Récupérer clés

Dashboard → Settings → API Keys
- Copier `Public Key`
- Copier `Secret Key`

### 3. Remplir `.env`

```bash
cp .env.example .env
# Éditer .env : coller tes clés Langfuse
```

### 4. Installer dépendances

```bash
pip install flask langfuse langchain langchain-openai python-dotenv
# Ou avec uv:
uv pip install flask langfuse langchain langchain-openai python-dotenv
```

### 5. Lancer l'app

```bash
python app.py
```

Devrait afficher :
```
 * Running on http://127.0.0.1:5000
```

## Test

### Via curl

```bash
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is 2+2?"}'
```

Réponse attendue :
```json
{
  "answer": "...",
  "trace_id": "..."
}
```

### Vérifier trace Langfuse

1. Aller sur https://cloud.langfuse.com
2. Voir ta trace dans Traces
3. Explorer : input, output, model, tokens, latence

## Fichiers

- `app.py` — Flask app + LangFuse tracing
- `.env.example` — Template env vars
- `README.md` — Ce fichier

## Points clés à observer

- ✅ Trace créée automatiquement (Langfuse capture tout)
- ✅ Input/output visible
- ✅ Tokens comptés
- ✅ Latence mesurée
- ✅ Modèle identifié

C'est ça, l'observabilité LLM. Demain on fera pareil sur Velmo.
