# Velmo 2.0 — Contexte projet

Agent de support pour boutique de maillots de foot collector (stock limité, clientèle de passionnés). Reconstruction complète : mémoire, garde-fous, MLOps. Certification RNCP — Dev IA Agentique.

## Stack imposée

- **Langage** : Python + `uv` (gestion de dépendances/venv — ne pas utiliser `pip install` directement, toujours `uv add` / `uv sync`)
- **LLM principal** : `gpt-5.4` (Azure AI Foundry) — génération de réponse
- **LLM léger** : `Phi-4-mini-instruct` — vérification de périmètre, classification/distillation mémoire
- **Modération/PII** : Azure AI Content Safety (haine/violence/sexuel + Prompt Shields) + Azure Language Conversational PII redaction
- **Base de données** : PostgreSQL + extension `pgvector`, **2 schémas séparés** : `metier` (produits/commandes, peuplé par `seed.py` fourni) et `memoire` (le nôtre, vide au départ)
- **KB** : ChromaDB (fourni par le formateur, sert `search_kb`)
- **Observabilité** : Langfuse Cloud (plan Hobby)

## Règles d'architecture non négociables

- Le **métier** (schéma `metier`) n'est **jamais** mélangé avec la **mémoire de l'agent** (schéma `memoire`)
- Isolation stricte par `user_id` sur **toute** entité mémoire — aucune lecture croisée entre utilisateurs
- Outils d'**action** (`cancel_order`, `trigger_refund`, `update_order_item`, `create_return`, `escalate_to_human`) : confirmation explicite obligatoire + seuils métier (remboursement > 50 € → escalade humaine)
- Outils de **lecture** (`get_order`, `track_shipment`, `check_stock`, `search_kb`) : filtrage `user_id`, pas de confirmation nécessaire
- Aucune donnée sensible recopiée dans les logs (`GuardrailEvent.excerpt_redacted`, jamais la donnée brute)
- Gate bloquant : un échec sur PII/secrets/isolation (R3)/oubli (R5) bloque la livraison immédiatement, **avant** tout calcul de moyenne pondérée
- Branches : `feature/*` (dev IA), `feature/tools-*` (CRUD outils métier, isolé), `dev` (staging), `main` (prod) — merge **toujours** manuel (PR + review), jamais automatique

## Conventions de code

- Code en anglais, **commentaires en français**
- Tests unitaires (`pytest`) écrits avant le code métier des tools
- Tests des tools : toujours contre une base Postgres **éphémère** (seedée via `seed.py` fourni), jamais contre une base persistante
- Linter : `ruff check .` doit passer avant tout commit

## Fichiers de référence (lire avant de coder, ne pas régénérer)

- `synthese.md` — conception garde-fous (Chantier 2)
- `chantier3-reponses.md` — évaluation & MLOps (Chantier 3)
- `choix.md` — conception mémoire (Chantier 1)


## Exigences
- docs/reco_expert