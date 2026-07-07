# Note formateur — avancement

## Chantier 0 — Fondations

- **Fix bugs bloquants** : le contexte mémoire n'était jamais transmis au LLM (réponses hors-sujet malgré une mémoire correctement stockée) ; le scheduler mémoire fuyait des connexions Postgres et se bloquait après quelques minutes.
- **Adaptation LangChain** : appel LLM refactorisé en chaîne LangChain (`PromptTemplate` + `Runnable`), pour préparer l'intégration future de middlewares (LangFuse, guardrails-ai).

## Chantier 1 — Mémoire

- **Schéma à jour** : `conception/memoire/flux_reel.drawio` (flux capture → classification → routage).
- **Tests d'acceptance** adaptés pour un traitement mémoire asynchrone (le classifier tourne en tâche de fond, plus en synchrone).
- **Choix assumé** : classifier hybride **petit LLM (Phi-4-mini-instruct) + repli règles REGEX** si le LLM échoue — conforme au dossier de conception (`choix.md`), plutôt qu'un classifier 100% règles. Le LLM extrait plusieurs faits par message (un seul fait était retenu avant) ; une validation de plausibilité par champ filtre ses erreurs d'extraction.
