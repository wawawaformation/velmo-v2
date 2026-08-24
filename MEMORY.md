# Velmo 2.0 — Mémoire de continuité projet

**Date dernière mise à jour** : 2026-08-24  
**État branche** : `dev` stable & vert  
**Cible déploiement** : Azure (décidée)

---

## État global

### ✅ Réalisé (Chantiers 1, 2, 3 Phase 1 terminés)

**Chantier 1 — Mémoire** (R1–R6 conformes)
- Épisodique (Postgres) + Vectorielle (Chroma) opérationnels
- Consolidation sémantico-épisodique (gpt-5.4-nano)
- Droit à l'oubli (R5) **enfin** connecté au LLM (outil `forget_memory` exposé)
- Isolation par `user_id` vérifiée
- Traçabilité complète (logs mémoire + structurés)

**Chantier 2 — Garde-fous** (déterministes + cascade LLM)
- Cascade 3 niveaux : regex → Azure Content Safety → gpt-5.4-nano
- 6 catégories : hate/violence/sexual/injection/out_of_scope/self_harm
- Self-harm redirige vers **3114** (prévention suicide FR)
- Messages de refus explicites (catégorie nommée)
- Traçabilité : logs dédiés, source (REGEX|LLM), données sensibles jamais loggées

**Chantier 3 Phase 1 — MLOps & Évaluation** ✅ (POC LangFuse)
- 3 suites d'évaluation : mémoire (12 cas), garde-fous (37 cas), qualité (8 cas)
- Reproductibilité atteinte : `temperature=0` appliquée (Réponse 2)
- Score global : **96,25 %** (mémoire 100 % / garde-fous 100 % / qualité 87,5 %)
- Gate CI bloquant (seuil 80 %) sur `dev`/`main`
- Manifeste YAML (source unique : versions, poids, seuils)
- 7 défauts critiques découverts & corrigés via éval réelle
- Rapport `mlops/report.md` versionné en Git

**Infra & API**
- Frontend Vue.js (Vite, Sass, thèmes clair/sombre) ✅
- API REST (FastAPI) `POST /messages`, `GET /users` ✅
- Docker Compose : postgres + chroma + app + api ✅
- CD workflow (GitHub Container Registry, ghcr.io) ✅

### 🔴 **BLOCAGE CRITIQUE** — Agent DOWN en production (2026-08-24)

Commit `a52230c` (Langfuse integration) déployé avec succès mais **agent crash immédiatement après** :
- `POST /messages` timeout 80+ sec (attendu : 5-13s)
- Infrastructure gelée, impossible de pull images de ghcr.io
- Service complètement inaccessible (`https://velmo.koabana.fr/users` → hang)

**État infra (avant crash)** ✅ :
- `velmo-basic` (App Service, Site Containers) : image déployée
- `velmo-pg` (Postgres Flexible Server) : base `velmo` peuplée ✅
- `velmo-chroma` (App Service, Site Containers) : FAQ ingérée, 16 documents ✅
- `velmo-kv` (Key Vault) : secrets configurés ✅
- `velmostorageprod` + partage Azure Files (`chroma-data`) : persistance montée ✅

**Verified before crash** (session du matin 24/08) ✅:
- `GET /openapi.json`, `GET /users` — connectivité de bout en bout
- `POST /messages` + tool-calling + garde-fous fonctionnels (tests rapides)
- R2/R3 mémoire vérifiés (persistance + isolation par `user_id`)
- Cas garde-fous validés (injection, violence, légitime)

**Incident root cause** : Probablement callback Langfuse blocking ou deadlock dans `Agent.respond()`. Rollback vers images précédentes échoué car images supprimées du registry ghcr.io (retention policy).

**Remaining brief points (5-9 — tous blocqués par ce downtime)** :
- Point 5 : Conversation en ligne ❌ (service down)
- Point 6 : R2/R3 validation complète ❌ (service down)
- Point 7 : Garde-fous validation complète ❌ (service down)
- Point 8 : Signaux de suivi ❌ (service down)
- Point 9 : Documentation & présentation ❌ (service down)

### ⚠️ Pépins corrigés récemment

| Défaut | Impact | État |
|--------|--------|------|
| R5 (oubli) non branché LLM | Utilisateur ne pouvait pas oublier | ✅ Fixé (outil exposé) |
| Chroma jamais utilisé (bug `@override`) | RGPD broken : oubli incomplet | ✅ Fixé + test acceptance |
| Modèle gpt-5.4-nano pas assez few-shot | Consolidation mémoire à 0 % | ✅ Fixé (3 exemples) |
| Temperature bruitée en éval | Score variait 62–88 % sans changement | ✅ Fixé (`temperature=0`) |
| CLI timeout LLM → crash + perte contexte | Usage réel bloqué | ✅ Fixé (`_safe_respond`) |
| Double-blocage garde-fous | Message refus remplacé par générique | ✅ Fixé (flag `_blocked_this_turn`) |
| PII loggée même si catégorie ≠ pii | RGPD violation | ✅ Fixé (masquage inconditionnel) |

---

## Commandes utiles

```bash
# État qualité
make lint              # ruff check .
make test              # pytest (offline)
make eval              # Éval réelle (Azure, Postgres, Chroma) → mlops/report.md
make eval-workflow     # Déclencher manuellement : gh workflow run quality --ref dev

# Frontend
make frontend          # Vite dev server (http://localhost:5173)
make frontend-build    # Build production

# API
make api               # uvicorn --reload (http://localhost:8000)

# Docker
docker compose up -d   # Démarre postgres + chroma + app + api
docker compose down    # Arrête tout

# Demo/Vérification
# Voir : docs/script_presentation_demo_memoire.md
# Voir : docs/script_presentation_demo_guardrails.md
# Voir : docs/checklist_test_manuel_garde_fous.md
```

---

## Fichiers clés à consulter avant modification

1. **Conception** (ne pas modifier sans raison)
   - `conception/memoire/choix.md` → archive (new: `conception/memoire/evolution_consolidation.md`)
   - `conception/garde-fous/synthese.md` → règles garde-fous
   - `conception/LMOPS/chantier3-reponses.md` → specifications éval

2. **Architecture**
   - `src/velmo/agent.py` → LangGraph agent (create_agent + middlewares)
   - `src/velmo/memory/` → Episodic + consolidation (gpt-5.4-nano)
   - `src/velmo/guardrails/` → Engine + cascade (regex → Content Safety → LLM)
   - `src/velmo/mlops/` → Évaluation + scoring + rapport

3. **Tests**
   - `tests/acceptance/test_mlops.py` → Suite d'évaluation (avec `real_llm` coûteux)
   - `tests/unit/` → 134 tests offline (sqlite + LocalKB)

---

## Modèles Azure actuels

| Utilisation | Modèle | Note |
|-------------|--------|------|
| Chat principal | `gpt-5.4` | Kimi-K2.6 remplacé (plus rapide, fiable) |
| Classifieur | `gpt-5.4-nano` | Phi-4-mini-instruct remplacé (37% d'erreur) |
| Content Safety | API REST (pas un modèle) | Détection automatique |

---

## Limites connues documentées

1. **Contamination mémoire entre suites** : `C-marc-dubois` utilisé par mémoire + qualité → qualité polluée par état mémoire antérieur (8/8 isolé, 7/8 complet)
2. **Non-déterminisme résiduel** : Même avec `temperature=0`, Chroma (ANN) + Azure peuvent donner 96,25 % ou 100 % selon le run
3. **Bug concurrence SQLAlchemy** : `bind_tools(session)` partagée entre outils, échecs si LLM émet 2+ appels parallèles (non reproduit en CI, découvert localement)
4. **Chroma `0.5.23`** : Incompatible avec versions plus récentes (pinné en `docker-compose.yml`)

---

## Prochaines étapes prioritaires

### Phase déploiement (bloquante pour prod)
1. Postgres Azure Database for PostgreSQL Flexible Server
2. Chroma : second conteneur ou service Azure (TBD)
3. Variables d'env : DB_URL, CHROMA_URL, secrets (API keys Azure)
4. Job `promote-prod` : retag image depuis `dev` → `main` (jamais rebuild)
5. Test déploiement staging avant prod

### MLOps Phase 2 (monitoring prod, post-déploiement)
- Intégration LangFuse complète (traces + coûts réels)
- Monitoring continu (éval temps réel vs benchmark)
- Alertes sur régression

### Améliorations quality
- Isoler suites d'évaluation (reset mémoire entre elles)
- Corriger bug concurrence SQLAlchemy (session par outil ?)
- Ajouter tests d'acceptance sur API (validation 422, tool-calling réel)

---

## Conventions strictes à respecter

- **Code** : anglais | **Commentaires** : français
- **Commits** : titre EN, contenu FR (`Co-Authored-By: Claude Haiku 4.5...`)
- **Modèle par défaut** : `gpt-5.4` (chat) / `gpt-5.4-nano` (classifieur)
- **Temperature d'éval** : `0` uniquement (pas en prod)
- **Dépendances** : `uv add` / `uv sync` (jamais `pip`)
- **Garde-fous** : Jamais de donnée brute loggée (PII/secrets = `[donnée sensible masquée]`)
- **Outils** : Jamais exposer `user_id`/`session` (liés par fermeture Python)

---

## Session précédente : ce qui a été cherché à faire

**Avant vacances** : Consolidation MLOps complète (éval réelle, gate CI, manifeste YAML)  
**Pendant** : Aucune activité (vacances 2 semaines)  
**Retour** : `~/.claude` changé → perte historique. Contexte reconstitué de CHANGELOG + source.
