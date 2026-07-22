# Chantier 3 — Évaluation & MLOps Velmo 2.0

*Réponses aux 4 questions de réflexion du brief, décisions actées au fil de la conception.*

---

# Réponse 1 — Suites d'évaluation

## Question

**Quelles suites d'évaluation mettre en place pour prouver la non-régression de Velmo 2.0 ?**

## Réponse synthétique

Trois suites complémentaires. Chacune teste une dimension différente, pour identifier précisément l'origine d'une régression.

## 1. Suite mémoire — `memory_cases.jsonl`

Rappel d'une information donnée en début de conversation, persistance entre sessions, isolation stricte entre utilisateurs, droit à l'oubli.

```text
expected_substring   → l'information attendue doit apparaître dans la réponse
forbidden_substring  → l'information oubliée ne doit plus apparaître
```

| Exigence | Ce qui est testé |
|---|---|
| R1 | Retrouver un numéro de contrat donné au début de l'échange |
| R2 | Se souvenir d'une préférence durable (ex. le tutoiement) |
| R3 | Ne jamais mélanger les souvenirs de deux utilisateurs |
| R5 | Ne pas ressortir une donnée explicitement oubliée |

## 2. Suite garde-fous — `guardrail_cases.jsonl`

Bloquer les demandes interdites **sans bloquer inutilement** les demandes légitimes.

```text
category         → type de risque testé
where            → input ou output
expected_action  → allow ou block (redact prévu dans l'architecture, absent du jeu de test fourni)
```

Sur 37 cas, un tiers (12, catégorie `legitimate`) mesure spécifiquement les faux positifs :

| | Nombre |
|---|---|
| `block` attendu | 25 |
| `allow` attendu | 12 |

## 3. Suite qualité générale — `quality_cases.jsonl`

Vérifie que Velmo reste utile sur les demandes support courantes (statut commande, retour, remboursement, etc.).

```text
question            → demande utilisateur
expected_substring  → élément attendu dans la réponse
```

## Synthèse

| Suite | Fichier | Objectif principal |
|---|---|---|
| Mémoire | `memory_cases.jsonl` | Rappel, persistance, isolation, oubli |
| Garde-fous | `guardrail_cases.jsonl` | Blocage, autorisation, faux positifs |
| Qualité générale | `quality_cases.jsonl` | Pertinence des réponses support |

## Position retenue

Velmo 2.0 n'est pas évalué avec un score unique et flou. Les tests sont séparés par domaine, ce qui permet de comparer les versions et d'identifier rapidement quelle partie régresse.

---

# Réponse 2 — Métriques, note globale et seuil de blocage

## Question

**Quelles métriques et quelle note globale comparable d'une version à l'autre ? Quel seuil de blocage de la livraison (et comment éviter de bloquer pour du bruit) ?**

## Métriques par suite

| Suite | Métrique | Formule |
|---|---|---|
| Mémoire | Taux de réussite | cas réussis / 12 |
| Qualité générale | Taux de réussite | cas réussis / 8 |
| Garde-fous | Taux de blocage | cas `block` réussis / 25 |
| Garde-fous | Taux de faux positifs | cas `allow` échoués / 12 |

## Score garde-fous — moyenne harmonique (F1)

```text
taux_blocage      = cas block réussis / 25   (rappel)
taux_non_faux_pos = 1 - (faux positifs / 12) (précision)

score_gardefous = 2 × (taux_blocage × taux_non_faux_pos) / (taux_blocage + taux_non_faux_pos)
```

Pénalise plus fort qu'une moyenne simple si l'un des deux taux est mauvais.

## Note globale — moyenne pondérée

```text
note_globale = w_mémoire × score_mémoire + w_gardefous × score_gardefous + w_qualité × score_qualité
```

Garde-fous pondéré plus lourd (catégorie « non négociable » du brief). Poids exacts à affiner en développement.

**Le brief exige les deux niveaux** : *« une note globale et des notes mémoire/garde-fous/qualité sont produites et versionnées »* — la note globale s'ajoute aux sous-notes, ne les remplace pas.

## Éviter de bloquer pour du bruit

**Retenu : `temperature=0` en évaluation + seuil de blocage avec marge** (pas de blocage au moindre point perdu, seulement sur chute significative vs version précédente).

*Écarté : rejouer chaque cas 3-5× — coût multiplié à chaque commit pour une valeur ajoutée faible une fois la température à 0.*

## CI en étages (fail fast)

```text
① Linter (ruff)  →  ② Tests unitaires (pytest)  →  ③ 3 suites d'éval LLM  →  Note globale + seuil
   gratuit, rapide     gratuit, rapide                lent, coûteux (appels API)
   boîte blanche        boîte blanche                  boîte noire
```

Un échec en ① ou ② arrête tout net, sans gaspiller d'appels API sur ③.

## Position retenue — budget bas et simplicité

| Décision | Alternative écartée | Pourquoi |
|---|---|---|
| `temperature=0` seul | Rejouer 3-5× chaque cas | Coût multiplié à chaque commit |
| Moyenne harmonique (F1) | Score sur-mesure pondéré par gravité | Formule standard, une ligne de calcul, pas de système propriétaire |
| Moyenne pondérée simple | Modèle ML de scoring | Reste lisible et recalculable à la main |

---

# Réponse 3 — Définition d'une version et stockage

## Question

**Qu'est-ce qu'une version de Velmo 2.0 (prompt + config mémoire + config garde-fous) ? Où stockez-vous la note de chaque version ?**

## Versionnage sémantique — `major.minor.patch`

| Niveau | Déclencheur | Exemple |
|---|---|---|
| **Majeur** | Changement d'architecture — un mécanisme entier change | Écriture synchrone par lot → pipeline `MessageBrut` + traitement asynchrone |
| **Mineur** | Changement de composant interchangeable, architecture inchangée | `Phi-4-mini-instruct` → `Ministral-3B` pour la vérification de périmètre |
| **Patch** | Ajustement de paramètre, logique inchangée | Seuil remboursement 50 € → 60 € ; correction d'une regex |

**Test de tranchage** : la façon dont les pièces s'articulent change-t-elle (majeur), ou juste une pièce interchangeable (mineur) ?

## Une version = un paquet concret

Le numéro (`2.1.3`) est une étiquette humaine qui doit pointer vers un paquet **figé** de fichiers réels — comme un tag Git pointant vers un commit précis.

## Stockage — DVC jugé disproportionné

Les fichiers d'une version (prompt, configs) et les jeux d'éval (12+37+8 lignes) sont du texte léger — le problème que DVC résout (gros binaires) ne se pose pas. *Piste v2 uniquement si le volume de données réelles grossit fortement.*

## Architecture retenue — Git + Langfuse (imposé par le brief)

| Composant | Stockage |
|---|---|
| Config mémoire (`.yaml`) | Git — structurel |
| Config garde-fous (`.yaml`) | Git — structurel |
| Prompt | **Langfuse** — versionné nativement, rollback en un clic |
| Notes / scores de chaque run | **Langfuse** — datasets + scores, comparables entre versions |
| Étiquette `major.minor.patch` | Relie un commit Git + une version de prompt Langfuse |

## Point ouvert

Langfuse en cloud ou self-hosted ? Les traces contiennent des conversations clients — question RGPD à trancher avec le formateur.

---

# Réponse 4 — Signaux de monitorage en exploitation

## Question

**Quels signaux de monitorage en exploitation : note mémoire, taux de blocage garde-fous, taux de faux positifs, latence, coût par conversation ?**

## Éval (CI) vs monitorage (prod)

| | Éval (Réponses 1-3) | Monitorage (Réponse 4) |
|---|---|---|
| Quand | Avant mise en prod, à chaque version | En continu, sur le vrai trafic |
| Sur quoi | Cas de test fixes et connus (12+37+8) | Vraies conversations, jamais vues à l'avance |
| Analogie | `phpunit` avant de merger | New Relic / Datadog une fois en ligne |

## Les 5 signaux exigés (`mlops/report.md`)

| Signal | Comment on le mesure en prod |
|---|---|
| Note mémoire | Pas de `expected_substring` connu → **LLM-as-judge** |
| Taux de blocage garde-fous | % de conversations réelles ayant déclenché un blocage |
| Taux de faux positifs | Réclamations / signalements de blocages abusifs |
| Latence | Trackée automatiquement par Langfuse (par trace) |
| Coût par conversation | Tracké automatiquement par Langfuse (tokens/appel) |

## LLM-as-judge — réservé au monitorage, pas à la CI

- **CI** : `expected_substring` déjà déterministe et gratuit — pas de juge, aucune valeur ajoutée pour le coût.
- **Monitorage prod** : seule solution réaliste pour noter une conversation réelle sans réponse connue à l'avance.

**Déclenchement retenu : conversations à risque uniquement** (score bas, réclamation) — pas exhaustif, pour rester budget bas.

## Exposition des signaux — double, comme exigé

| Canal | Rôle |
|---|---|
| **Dashboards Langfuse** | Temps réel, exploration |
| **`mlops/report.md`** | Snapshot périodique — exigé par les tests d'acceptance |

---

# Réponse 5 — Branches, environnements, Docker et infrastructure

*Complément aux 4 questions du brief, issu du brainstorming CI/CD.*

## Branches → environnements → contrôle croissant

| Branche | Environnement | CI exécutée | Déploiement |
|---|---|---|---|
| `feature/*` | dev (éphémère) | ①② Linter + tests unitaires | Auto, chaque push |
| `dev` | staging | ①②③ + build Docker | Auto si seuil respecté |
| `main` | production | Vérif score staging + approbation humaine | Manuel |

**Principe retenu** : automatiser la vérification (CI), garder la décision finale humaine — même doctrine que les garde-fous Velmo (*lire librement, agir après confirmation*). Le merge vers chaque branche est **toujours manuel** (PR + review), jamais automatique ; tout ce qui suit le merge est automatisé (CD/GitOps).

## Un seul `quality.yml`, jobs conditionnés par branche

Pas 3 fichiers CI — un seul, avec des jobs qui se déclenchent selon `github.ref`. Cohérent avec le nommage singulier du brief.

```yaml
jobs:
  lint-and-unit:      # toujours (feature/*, dev, main)
  eval-suites:        # seulement dev et main (coûteux, LLM)
  docker-build:       # seulement dev (build once)
  promote-prod:       # seulement main (retag, jamais de rebuild)
```

## Docker — build once, promote everywhere

L'image Docker est construite **une seule fois** (sur `dev`, après ③ validé), taguée `velmo-agent:X.Y.Z-rc1`. Le déploiement en prod **retague** cette même image (`docker tag`, pas `docker build`) — jamais reconstruite, pour éviter le *"ça marchait en staging"*.

| Tag | Rôle |
|---|---|
| Docker `X.Y.Z-rc1` (staging) | Image candidate |
| Git tag `vX.Y.Z` + Docker `X.Y.Z` (prod) | Version officielle |

## Branche séparée pour les tools métier

Le formateur fournit le **dataset** mais pas les **9 tools** (`get_order`, `cancel_order`...) — à coder. Décision : `feature/tools-*` isolé, pour deux raisons complémentaires :

1. **Technique** : les tools d'action écrivent réellement en base → risque de corrompre le dataset fourni pendant les tests.
2. **Organisation** : sépare visuellement le code CRUD classique du code IA (mémoire, garde-fous).

**Solution technique au risque de corruption : base Postgres éphémère en CI**, repeuplée à chaque run via le `seed.py` du formateur, détruite après les tests — aucune trace, quelle que soit la branche.

## Docker Compose — infrastructure locale

Deux bases distinctes, un principe simple : **le métier n'est pas la mémoire de l'agent** (règle posée dès le Chantier 1, appliquée ici à l'infra).

```yaml
services:
  agent:
    build: .
  db:
    image: pgvector/pgvector:pg16
    # 2 schémas dans le même conteneur :
    #   - "metier"  → produits, commandes (peuplé par seed.py du formateur)
    #   - "memoire" → User, Session, MessageBrut, FaitSémantique, Épisode (le nôtre, vide au départ)
  chromadb:
    image: chromadb/chroma
    # Base de connaissance (KB) fournie par le formateur — sert search_kb
```

`seed.py` (fourni) ne peuple que le schéma `metier` — le schéma `memoire` reste vide au départ, l'agent la construit par l'usage. Nos futurs tests unitaires mémoire auront leurs propres fixtures, séparées de `seed.py`.

## pgvector confirmé suffisant

Le vectoriel de Velmo (faits sémantiques imprévisibles, quelques-uns par client) est très loin du seuil où pgvector montre ses limites (10-50M vecteurs). Un seul service Postgres+pgvector couvre le relationnel et le vectoriel — pas besoin d'un moteur dédié séparé (Qdrant etc.), contrairement à la KB (ChromaDB) qui est fournie telle quelle par le formateur.

## Langfuse — Cloud (Hobby), pas self-hosted

| | Cloud Hobby | Self-hosted |
|---|---|---|
| Coût | Gratuit | Infra à gérer (6 services) |
| Setup | Minutes | Heures à jours |

Retenu pour l'exercice : volume largement sous la limite gratuite, complexité de self-host disproportionnée (même verdict que DVC). **Limite documentée, pas résolue** : une vraie prod avec de vraies données clients justifierait le self-host (RGPD — données jamais hors infra).

## Aucun ML local pour les classifieurs

Confirmé : Azure AI Content Safety (①②④) et Phi-4-mini-instruct (③) suffisent, tous deux hébergés sur Azure AI Foundry. Pas de modèle à héberger soi-même.

---

# Synthèse globale

| # | Question | Décision clé |
|---|---|---|
| 1 | Suites d'évaluation | 3 suites (mémoire, garde-fous, qualité), séparées pour diagnostiquer précisément |
| 2 | Métriques / note globale / seuil | F1 pour garde-fous, moyenne pondérée globale, `temperature=0` + marge anti-bruit |
| 3 | Version / stockage | Semver `major.minor.patch`, Git (configs) + Langfuse (prompt + scores) |
| 4 | Monitorage prod | 5 signaux, LLM-as-judge ciblé sur le risque, double exposition Langfuse + `report.md` |
| 5 | Branches / environnements / infra | Semver + branches→environnements, Docker build-once-promote, `feature/tools-*` isolé + base éphémère, Langfuse Cloud, pgvector confirmé suffisant, aucun ML local |

## Point non résolu à faire remonter au formateur

Contradiction entre les deux versions du brief : *« travail en équipe de 2 à 3 »* (brief initial) vs *« assignation individuelle »* (document le plus récent). Sans impact sur l'architecture, mais à clarifier pour l'organisation du travail restant.
