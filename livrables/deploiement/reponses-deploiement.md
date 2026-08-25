# Déploiement Velmo 2.0 sur Azure — Dossier de déploiement

*Réponses aux 3 axes de conception du brief 2, décisions actées au fil de la
conception (méthode identique aux chantiers 1-3 : questions/réponses avant
rédaction finale).*

---

# Réponse 1 — Choix des services Azure pour héberger l'agent et sa mémoire

## Question

**Comparer les options d'hébergement de l'agent (App Service vs conteneur).
Choisir un service de stockage persistant pour la mémoire long terme
répondant à R2 (persistance) et R3 (isolation par utilisateur).**

## Hébergement de l'agent

| Critère | App Service | Container Instances (ACI) |
|---|---|---|
| Facilité | Très managé (HTTPS, domaine, redémarrage auto) | Basique, pas de scaling/domaine automatique |
| Coût | Tarif fixe mensuel (Basic ~13 €/mois) | Facturation à la seconde d'exécution |
| Adéquation | App web en continu | Tâches ponctuelles |

**Retenu : App Service**, en mode **conteneur** (pas code natif) — parité
stricte dev/CI/prod (même `Dockerfile`/`uv.lock` qu'en local et en CI),
traçabilité par tag SHA (`ghcr.io/.../velmo-v2:<sha>`), portabilité.

**Précision (provisioning)** : Chroma tourne dans son propre conteneur,
séparé de celui de l'agent (déjà acté ci-dessous, « Conteneur
auto-hébergé »). Le portail Azure crée aujourd'hui toute Web App conteneur en
mode *Site Containers* ; plutôt que d'ajouter Chroma comme second conteneur
sur `velmo-basic`, il tourne dans sa **propre App Service** (`velmo-chroma`),
sur le même plan (`david-velmo-basic`, donc sans coût de plan
supplémentaire) — navigation plus simple dans le portail, résultat
équivalent (conteneur séparé de l'agent).

## Stockage de la mémoire long terme (R2, R3)

Deux stockages distincts (cf. `conception/memoire/choix.md`) :

| Stockage | Contenu | Choix Azure |
|---|---|---|
| Relationnel (`MemoryUser`) | Faits à clé connue d'avance | **Azure Database for PostgreSQL — Flexible Server** |
| Vectoriel (Chroma) | Faits à clé imprévisible + épisodes | **Conteneur auto-hébergé** + volume **Azure Files** |

- **Postgres** : R2 satisfaite par construction (service managé) ; R3 déjà
  assurée par le code (`WHERE user_id = ...`), seule `DB_URL` change.
- **Chroma** : pas de service Azure natif équivalent → auto-hébergé pour ne
  pas réécrire l'intégration vectorielle (interdiction de dégrader la
  mémoire). Persistance via Storage Account + partage Azure Files monté sur
  `/chroma/chroma` (même mécanisme que le volume Docker local).

## Position retenue

| Composant | Service Azure | Statut |
|---|---|---|
| Agent (API) | App Service, plan Basic, Linux, **conteneur** | Déployé et vérifié (`velmo-basic`, France Central) — image `ghcr.io/wawawaformation/velmo-v2:dev` en cours d'exécution |
| Registre d'image | GitHub Container Registry (`ghcr.io`) | Opérationnel (`docker-build` en CD), image publique (pull anonyme) |
| Mémoire relationnelle | Azure Database for PostgreSQL — Flexible Server | Provisionné et peuplé (`velmo-pg`, base `velmo`) |
| Mémoire vectorielle | App Service dédiée, conteneur Chroma | Provisionné et peuplé (`velmo-chroma`, 16 documents FAQ) |
| Persistance Chroma | Storage Account + Azure Files, monté sur `/chroma/chroma` | Provisionné et monté (`velmostorageprod`, partage `chroma-data`) |
| Secrets | Azure Key Vault + identité managée | Provisionné (`velmo-kv`) — `AZURE_AI_INFERENCE_API_KEY` et `DB_URL` résolus par `velmo-basic` |

**Écart au provisioning initial** : Chroma tourne finalement dans sa propre
App Service (`velmo-chroma`), pas dans un second conteneur sur `velmo-basic`
— cf. précision ci-dessus (mode *Site Containers* du portail).

---

# Réponse 2 — Gestion des secrets et de la configuration

## Question

**Lister les secrets et paramètres à externaliser (clé et endpoint du
service d'IA, connexion au stockage mémoire, seuils des garde-fous).
Décrire où et comment ils seront stockés côté Azure, sans jamais figurer
dans le dépôt Git.**

## Inventaire (vérifié dans le code et le `.env`)

### A. Vrais secrets (sensibles)

| Secret | Pourquoi c'est sensible |
|---|---|
| `AZURE_AI_INFERENCE_API_KEY` | Donne accès au LLM **et** à Content Safety (`content_safety.py:65`) — clé partagée |
| `DB_URL` | Chaîne de connexion avec identifiant **et** mot de passe intégrés |

### B. Paramètres de configuration (pas secrets)

| Paramètre | Rôle |
|---|---|
| `AZURE_AI_INFERENCE_ENDPOINT` | URL du LLM |
| `AZURE_AI_INFERENCE_MODEL` | Nom du modèle (`gpt-5.4`) |
| `AZURE_AI_CLASSIFIER_MODEL` | Nom du modèle classifieur |
| `AZURE_CONTENT_SAFETY_ENDPOINT` | URL Content Safety |
| `CHROMA_URL` | Adresse du conteneur Chroma — changera pour pointer vers Azure |
| `EMBEDDING_MODEL` | Nom du modèle d'embeddings |

### C. Seuils des garde-fous : délibérément non externalisés

`REFUND_CAP` (`tools/_common.py`), `_SEVERITY_THRESHOLD`
(`guardrails/content_safety.py`) et `mlops/eval_manifest.yaml` restent des
constantes/fichiers versionnés en Git, pas des variables d'environnement —
cohérent avec la Réponse 3 du chantier 3. Une variable Azure se modifie
silencieusement sans trace ; un seuil versionné ne change que via un commit
revu (`git log`), traçabilité jugée prioritaire pour ce type de décision.

### D. Variable obsolète

`EVAL_MIN_SCORE` — plus lue nulle part (remplacée par
`mlops/eval_manifest.yaml`), à retirer du `.env`.

## Stockage des vrais secrets (A) côté Azure

| Option | Limite |
|---|---|
| **App Settings** | Visibles en clair par tout accès Lecteur/Contributeur, pas de rotation native |
| **Azure Key Vault** | Accès finement contrôlé, versionnage natif |

**Retenu : Azure Key Vault** (recommandation *Well-Architected Framework*
Microsoft pour ce cas), via **identité managée** de l'App Service — pas de
credential supplémentaire à protéger. Paramètres (B) restent en App
Settings.

## Position retenue

| Catégorie | Où | Mécanisme |
|---|---|---|
| Vrais secrets (A) : clé API, `DB_URL` | Azure Key Vault | Identité managée de l'App Service, lecture seule |
| Paramètres de config (B) : endpoints, noms de modèles, `CHROMA_URL` | App Settings (App Service) | Variables d'application classiques |
| Seuils des garde-fous (C) | Git (code + `mlops/eval_manifest.yaml`) | Commit + revue, jamais une variable d'environnement |
| `EVAL_MIN_SCORE` | — | Obsolète, à retirer du `.env` |

Aucun secret, à aucun moment, ne figure dans le dépôt Git ni dans le code
source.
