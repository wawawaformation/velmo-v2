# MLOPS Velmo 2.0 — État d'avancement

Document synthétique de la phase d'observabilité et évaluation.

---

## Phase 1 — POC LangFuse ✅

**État** : Complété et branché `poc-langfuse`

### Apprentissages

- ✅ Traces Langfuse : `create_trace_id()` + `create_event()`
- ✅ Datasets : créer, charger, itérer
- ✅ Scoring automatique : `create_score()` attaché aux traces
- ✅ LLM-as-a-Judge : évaluation nuancée 0.0-1.0
- ✅ Intégration Azure OpenAI (gpt-5.4)

### Fichiers du POC

| Fichier | Rôle |
|---------|------|
| `poc/app.py` | API Flask + tracing minimal |
| `poc/datasets.py` | Créer dataset exemple (math_questions) |
| `poc/evaluate.py` | Charger dataset, évaluer, scorer |
| `poc/judge.py` | LLM-as-a-Judge (5 critères : pertinence, clarté, exactitude, complétude, concision) |
| `poc/README.md` | Guide complet du workflow |
| `poc/.env.example` | Template Azure + Langfuse |

### Concepts clés compris

```
Trace = conteneur pour grouper événements LLM
  ↓
Dataset = cas de test fixes
  ↓
Évaluation = question → modèle → judge → score
  ↓
Langfuse Cloud = visualisation centralisée
```

---

## Phase 2 — Intégration Velmo (À faire)

### Suites d'évaluation (réponse 2 du brief)

| Suite | Cas | Objectif |
|-------|-----|----------|
| **Mémoire** | 12 | R1/R2/R3/R5 (rappel, persistance, isolation, oubli) |
| **Garde-fous** | 37 | 25 block + 12 allow (faux positifs mesurés) |
| **Qualité** | 8 | Support métier standard (commande, retour, FAQ) |

**Status** : À créer (20-30 cas minimum recommandé)

### Notation (réponse 2)

- **Mémoire** : taux réussi / 12
- **Garde-fous** : F1 harmonique (rappel × précision)
- **Qualité** : taux réussi / 8
- **Global** : moyenne pondérée (w_mem + w_gf + w_qual)

**Status** : Formules définies, implémentation pending

### CI/CD (réponse 5)

| Branche | Jobs | Conditions |
|---------|------|-----------|
| `feature/*` | lint + tests | Toujours |
| `dev` | + docker build | Si seuil passé |
| `main` | + promotion | Approbation humaine |

**Status** : Quality.yml cohérent, étapes 1-2 ready, étape 3 pending

---

## Documentation Mémoire

### Architecture (validée)

| Composant | Fichier | Statut |
|-----------|---------|--------|
| **MemoryMiddleware** | `src/velmo/memory/middleware.py` | ✅ Implémenté (plan chantier branche) |
| **MemoryManager.read()** | `src/velmo/memory/__init__.py` | ✅ Opérationnel |
| **MemoryManager.write()** | `src/velmo/memory/__init__.py` | ✅ Opérationnel |
| **Consolidation** | `src/velmo/memory/consolidation.py` | ✅ Implémenté |
| **Episodic store** | Chroma (KB) | ✅ Configuré |

### Schémas (documentés)

- `conception/memoire/flux_reel.drawio` : cycle complet (before_agent → wrap_model_call → after_agent)
- Nomenclature : User, Session, MessageBrut, FaitSémantique, Épisode

**Status** : Documentation à jour

---

## Documentation Garde-fous

### Cascade (validée)

| Niveau | Détecteur | Fichier | Statut |
|--------|-----------|---------|--------|
| **1** | Regex (4 détecteurs) | `src/velmo/guardrails/moderation.py` etc. | ✅ Opérationnel |
| **2** | Azure Content Safety | `src/velmo/guardrails/content_safety.py` | ✅ Opérationnel |
| **3** | LLM (gpt-5.4-nano) | `src/velmo/guardrails/moderation_llm.py` | ✅ Opérationnel |

### Schémas (documentés)

- `conception/garde-fous/velmo2-garde-fous-flux-reel.drawio` : cascade entrée/sortie avec few-shot exemples
- Filenames inclus dans chaque boîte (source traçable)

**Status** : Documentation à jour + simplifiée

---

## Documentation API/Frontend

### Schémas

- `conception/api-frontend/velmo2-api-frontend-flux-reel.drawio` : POST /messages → latency_ms + guardrail_category
- `conception/api-frontend/velmo2-architecture-globale.drawio` : 3 couches (interfaces → noyau → sous-systèmes)

**Status** : Documenté

### Implémentation

- `src/velmo/api.py` : MessageResponse inclut `guardrail_category`
- Tests : `test_api.py` vérifie champs complets

**Status** : Implémenté + testé

---

## Qualité.yml — Cohérence

### Avant

```yaml
# Ligne 56 (eval-suites)
uv sync --extra vector --extra llm
```

### Après

```yaml
# Ligne 56
uv sync --extra vector --extra llm --extra api
```

**Status** : ✅ Aligné avec Dockerfile (qui demande `--extra api`)

---

## Résumé pour Velmo demain

### Bloquant pour continuer

1. ✅ POC LangFuse validé (traces, datasets, judge)
2. ✅ Quality.yml cohérent (Docker + CI)
3. ⏳ Suites d'évaluation (mémoire, garde-fous, qualité)
4. ⏳ Scoring + CI gate
5. ⏳ Monitoring prod (LLM-as-judge)

### Non bloquant, documenté, réutilisable

- Mémoire (flux, middleware, consolidation)
- Garde-fous (cascade, few-shot, output)
- API/Frontend (contrat, schémas)

---

## Calendrier recommandé

| Jour | Tâche | Durée | Notes |
|------|-------|-------|-------|
| J1 | Suites d'eval (20-30 cas) | 3-4h | Ou moins si on simplifie (10 cas) |
| J1 | Notation + CI gate | 2-3h | Formules simples, pas F1 complexe |
| J2 | Intégration Velmo | 2-3h | Câbler evaluate.py au projet |
| J3+ | Monitoring prod + polish | 4-6h | LLM-as-judge, seuils |

---

**Branche POC** : `poc-langfuse` (7 commits, non pushée)
**Branche work** : `feature` (ready pour intégration)
**Next PR** : `poc-langfuse` → `feature` (avec CI skip)
