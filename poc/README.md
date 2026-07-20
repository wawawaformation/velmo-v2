# POC LangFuse — Observabilité LLM complète

Exploration pratique de Langfuse Cloud : traces, datasets, évaluation, LLM-as-a-Judge.

## Setup

### 1. Créer compte Langfuse Cloud

https://cloud.langfuse.com → Sign up gratuit

### 2. Récupérer clés API

Dashboard → Settings → API Keys
- Copier `Public Key`
- Copier `Secret Key`

### 3. Remplir `.env`

```bash
cp .env.example .env
# Éditer .env : coller tes clés Langfuse + Azure
```

### 4. Installer dépendances

```bash
uv sync
```

## Structure du POC

### `app.py` — API Flask + tracing
- Endpoint POST `/ask` : pose une question
- Appelle gpt-5.4 via Azure
- Crée une trace Langfuse automatiquement
- Retourne réponse + trace_id

```bash
uv run python app.py
```

Puis tester avec Bruno ou curl :
```bash
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is 2+2?"}'
```

### `datasets.py` — Créer des datasets d'évaluation
- Crée un dataset "math_questions" avec 3 items
- Chaque item : question + expected_output
- Prêt pour évaluation

```bash
uv run python datasets.py
```

### `evaluate.py` — Évaluer le modèle avec judge
- Charge le dataset
- Envoie chaque question à app.py
- Évalue la réponse avec LLM-as-a-Judge
- Poste les scores dans Langfuse

```bash
uv run python evaluate.py
```

### `judge.py` — LLM-as-a-Judge
- Évalue la qualité d'une réponse (pas juste correct/incorrect)
- Critères : Pertinence, Clarté, Exactitude, Complétude, Concision
- Retourne score nuancé 0.0-1.0

Peut être utilisé standalone :
```bash
uv run python judge.py
```

## Flux complet

1. **Setup** : `uv sync` + remplir `.env`
2. **Lancer API** : `uv run python app.py` (terminal 1)
3. **Créer dataset** : `uv run python datasets.py` (terminal 2)
4. **Évaluer** : `uv run python evaluate.py` (terminal 2)
5. **Observer** : Aller sur https://cloud.langfuse.com → Traces

## Points clés appris

✅ **Traces** : conteneur pour grouper les événements LLM
✅ **Datasets** : cas de test fixes pour éval
✅ **Scoring** : attach scores numérisés aux traces
✅ **LLM-as-a-Judge** : évaluation nuancée, pas binaire
✅ **Production-ready** : adapté pour monitoring réel

## Prochaines étapes

- Intégrer à Velmo (branches feature, suites d'éval CI)
- Monitoring prod avec LLM-as-judge
- Seuils de blocage CI (quality gates)
