# Velmo V2

Assistant de support pour **Velmo**, boutique en ligne de maillots de foot collector (rééditions vintage, pièces signées, éditions limitées en stock très limité). L'agent traite la gestion de commandes de niveau 1 — statut et suivi, disponibilité, modification/annulation avant expédition, retours, remboursements simples, FAQ — en gardant le contexte du client dans le temps.

## 🚧 Projet en construction

Le développement se fait sur `dev` (voir `docs/CHANGELOG.md` pour le détail
commit par commit) et `main` reçoit des merges ponctuels — `main` n'est pas
développée séparément faute de temps disponible en parallèle.

**Construit et testé** : mémoire (court + long terme, isolation, droit à
l'oubli), garde-fous (entrée/sortie, cascade règles → Content Safety → LLM),
évaluation MLOps (3 suites, note globale versionnée, gate CI bloquant,
rapport de suivi).

**Explicitement en attente / non résolu** :

- **Langfuse** (observabilité, coût réel par conversation, versionnage natif
  des prompts) — en attente de la décision de cible de déploiement (cloud ou
  auto-hébergé), question RGPD non tranchée à ce stade.
- **Coût par conversation** dans `mlops/report.md` : placeholder à `0.0` tant
  que Langfuse n'est pas branché.
- **Contamination connue entre suites d'évaluation** : un même client de test
  est utilisé par la suite mémoire et la suite qualité, ce qui peut fausser
  légèrement la note qualité isolée (documenté dans `docs/CHANGELOG.md`).
- **Cible de déploiement production** non tranchée (dépend d'une décision
  externe au projet).

## Features

- Outils métier connectés à la base : commandes, suivi, stock, retours, remboursements, escalade
- Garde-fous métier intégrés : isolation par client, blocage des modifications après expédition, plafond de remboursement (50 €) avec escalade
- FAQ par recherche sémantique (RAG) sur la base de connaissances Velmo
- Mémoire durable et isolée par client (court terme, long terme sémantique/épisodique, droit à l'oubli conversationnel)
- Garde-fous de contenu en entrée/sortie (haine, violence, sexuel, self-harm, injection de prompt, PII/secrets, hors périmètre)
- Chaîne qualité MLOps : 3 suites d'évaluation, note globale versionnée (`mlops/eval_manifest.yaml`), seuil bloquant en CI, rapport de suivi (`mlops/report.md`)

## Stack

- Python 3.11 (géré avec `uv`)
- PostgreSQL + SQLAlchemy 2 + Alembic (état des commandes, clients, catalogue)
- Chroma + `intfloat/multilingual-e5-small` pour la FAQ et la mémoire vectorielle (extra `vector` + `embeddings`)
- Azure AI Inference (`gpt-5.4` / `gpt-5.4-nano`) pour le LLM (extra `llm`)
- GitHub Actions pour l'intégration continue

Le coeur tourne sans service externe (repli hors-ligne : SQLite en mémoire pour les
tests, FAQ locale, LLM en écho). Les intégrations s'activent via les extras :

```bash
uv sync                                                    # coeur + base + outils de dev
uv sync --extra llm --extra vector --extra embeddings --extra api   # usage réel complet
```

## Démarrage

```bash
make up           # docker compose : app + postgres + chroma
make seed         # peuple Postgres (catalogue, clients, ~14 commandes)
make chat         # REPL — répond déjà aux questions métier de base
```

Exemple de session (`make chat`, client `C-marc-dubois` par défaut) :

```
Vous : Quel est le statut de ma commande O-2024-0101 ?
Velmo : Votre commande O-2024-0101 est au statut « prepared ».
Vous : Le maillot france-1998 en taille L est-il disponible ?
Velmo : Le maillot France 1998 — Zidane en taille L est disponible.
Vous : Quels sont les frais de port en France ?
Velmo : D'après notre FAQ (frais-de-port.md) : France métropolitaine : 6,90 € …
```

L'agent tient la mémoire du client d'un tour à l'autre et d'une session à
l'autre, applique ses garde-fous en entrée et en sortie, et honore une demande
d'oubli formulée en conversation (« oublie mon adresse »).

## Layout

```text
src/velmo/
  cli.py            REPL de conversation (--user)
  agent.py          Orchestration : garde-fous → mémoire → outils → réponse
  llm.py            Client Azure AI Inference (+ repli hors-ligne)
  db.py             Schéma SQLAlchemy + sessions
  sampledata.py     Jeu de données de référence
  tools/            Outils métier (accès Postgres + FAQ) + forget_memory (RGPD)
  memory/           Court terme, sémantique, épisodique, vectoriel, scheduler
  guardrails/       Cascade règles → Content Safety → LLM, entrée/sortie
  mlops/            Suites d'évaluation, manifeste, gate, rapport (score.py)
mlops/eval_manifest.yaml   Version, seuil, pondérations, versions de prompts
docs/reco_expert.md        Note de recommandations (stack + exigences)
docs/CHANGELOG.md          Historique détaillé, décision par décision
conception/                Dossier de conception (mémoire, garde-fous, MLOps)
kb/docs/                   Base de connaissances FAQ
scripts/                   seed.py (Postgres) + seed_kb.py (Chroma)
alembic/                   Migrations
eval/                      Jeux de cas (mémoire, garde-fous, qualité)
tests/unit/, tests/acceptance/   Tests hors-ligne + suite d'acceptance
.github/workflows/         Intégration continue
```

## Commandes utiles

```bash
make migrate    # alembic upgrade head
make seed-kb    # ingestion FAQ dans Chroma
make test       # suite d'acceptance + tests métier
make eval       # évaluation MLOps réelle (vrai agent Azure) + rapport
make fmt        # ruff format + autofix
make typecheck  # mypy
make down       # arrête les services
```

## License

Propriétaire — Velmo.
