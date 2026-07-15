# Note formateur — avancement

## Chantier 0 — Fondations

- **Fix bugs bloquants** : le contexte mémoire n'était jamais transmis au LLM (réponses hors-sujet malgré une mémoire correctement stockée) ; le scheduler mémoire fuyait des connexions Postgres et se bloquait après quelques minutes.
- **Adaptation LangChain** : appel LLM refactorisé en chaîne LangChain (`PromptTemplate` + `Runnable`), pour préparer l'intégration future de middlewares (LangFuse, guardrails-ai).

## Chantier 1 — Mémoire

- **Schéma à jour** : `conception/memoire/flux_reel.drawio` (flux capture → classification → routage).
- **Tests d'acceptance** adaptés pour un traitement mémoire asynchrone (le classifier tourne en tâche de fond, plus en synchrone).
- **Choix assumé** : classifier hybride **petit LLM (Phi-4-mini-instruct) + repli règles REGEX** si le LLM échoue — conforme au dossier de conception (`choix.md`), plutôt qu'un classifier 100% règles. Le LLM extrait plusieurs faits par message (un seul fait était retenu avant) ; une validation de plausibilité par champ filtre ses erreurs d'extraction.

## Chantier 2 — Garde-fous

- **Architecture agent** : migration complète de l'agent (routage regex fait main, 200+ lignes) vers `create_agent()`/`AgentMiddleware` (LangGraph, LangChain 1.3) — le LLM (gpt-5.4) décide désormais lui-même des appels d'outils, à partir d'un prompt système explicite. Garde-fous et mémoire réimplémentés comme middlewares (`GuardrailMiddleware`, `MemoryMiddleware`), sans dupliquer la logique métier existante. Objectif pédagogique assumé : se familiariser avec le framework standard de l'écosystème.
- **Cascade garde-fous à 3 niveaux** : règles déterministes (regex, 1er recours) → **Azure AI Content Safety** (`text:analyze` + `text:shieldPrompt`, 2e recours) → classifieur LLM (gpt-5.4-nano, 3e et dernier recours). Content Safety, d'abord jugé indéployable depuis l'accès Foundry du projet, s'est révélé accessible en API REST directe (même ressource multi-service que l'inférence, endpoint distinct). Le LLM reste nécessaire : Content Safety ne détecte pas toutes les formulations d'injection de prompt (ex. « Passe en mode développeur. »).
- **Diagnostic de fiabilité des modèles Azure** : un benchmark HTTP brut (hors LangChain, `scripts/bench_llm_latency.py`) puis un benchmark multi-région à grande échelle (16 820 appels, partagé par un pair) ont confirmé que le déploiement Phi-4-mini-instruct était intermittent par lui-même (jusqu'à 37-40% d'échec en timeout), indépendamment de tout code applicatif — pas un problème de latence Azure en général. Bascule vers `gpt-5.4`/`gpt-5.4-nano` (plus rapides et plus fiables sur le même échantillon), et ajout d'un coupe-circuit (`VELMO_GUARDRAILS_LLM_CASCADE`) pour désactiver la cascade LLM sans redéploiement en cas de nouvel incident.
- **Piste explorée et documentée comme non retenue** : Azure Language PII redaction (variante générique testée) produit un faux positif sur les identifiants de commande Velmo (confondus avec des numéros de téléphone) — le regex actuel (`pii.py`) reste en place ; décision tracée dans `conception/garde-fous/synthese.md`.
