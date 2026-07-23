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

### App Service vs Container Instances (ACI)

Deux décisions à ne pas confondre : **quel service** héberge l'agent, et
**comment** ce service exécute le code (conteneur vs code natif).

| Critère | App Service | Container Instances (ACI) |
|---|---|---|
| Facilité | Très managé (HTTPS, domaine, redémarrage auto) | Basique, pas de scaling/domaine automatique |
| Coût | Tarif fixe mensuel (Basic ~13 €/mois) | Facturation à la seconde d'exécution |
| Adéquation | Fait pour une app web en continu | Fait pour des tâches ponctuelles |

**Retenu : App Service.** Velmo est une API qui doit rester joignable en
continu par les vendeurs — le cas d'usage exact d'App Service, pas d'ACI
(pensé pour des jobs qui démarrent et s'arrêtent).

### Conteneur vs Code natif

**Retenu : Conteneur**, pour trois raisons vérifiables sur ce projet précis,
pas de principe abstrait :

1. **Parité stricte dev / CI / production.** Le `Dockerfile` utilisé en
   local (`docker-compose.yml`, service `api`) est le même que celui
   construit et poussé sur `ghcr.io` par la CI (`.github/workflows/cd.yml`)
   — et c'est cette image, telle quelle, qu'Azure exécute. `uv.lock` (commité
   au dépôt précisément pour cette raison) fige les versions exactes de
   chaque dépendance ; `uv sync` dans le conteneur les respecte à la lettre.
   En mode Code natif, Azure réinterprète le projet via son propre système
   de build (Oryx) — rien ne garantit qu'il respecte `uv.lock`, ni qu'il
   utilise la même version de Python ou les mêmes bibliothèques système.
   Docker ne fige pas que le code : il fige l'environnement qui l'exécute.
2. **Traçabilité et rollback.** L'image est taguée par SHA de commit
   (`ghcr.io/.../velmo-v2:<sha>`) — on sait à tout moment quel commit tourne
   en production, et on peut revenir à une image précédente sans
   reconstruction.
3. **Portabilité.** La même image fonctionnerait sur un autre hébergeur
   (Container Apps, un serveur, un autre cloud) sans réécriture — pas de
   dépendance aux spécificités du buildpack Python d'App Service.

Un seul conteneur pour commencer (l'API, `src/velmo/api.py` via uvicorn) —
pas la fonctionnalité *Site Containers* (multi-conteneurs dans une même Web
App), plus récente et moins éprouvée. Complexité à éviter tant que le plus
simple n'est pas validé.

## Stockage de la mémoire long terme (R2, R3)

Le brief parle d'« un service de stockage » au singulier, mais Velmo a
**deux** stockages long terme distincts (cf. `conception/memoire/choix.md`) :

| Stockage | Contenu | Choix Azure |
|---|---|---|
| Relationnel (`MemoryUser`) | Faits à clé connue d'avance (pointure, tutoiement...) | **Azure Database for PostgreSQL — Flexible Server** |
| Vectoriel (Chroma) | Faits à clé imprévisible + épisodes (similarité) | **Conteneur auto-hébergé** + volume **Azure Files** |

### Postgres → Azure Database for PostgreSQL (Flexible Server)

Service managé : sauvegardes automatiques, haute disponibilité en option,
mises à jour gérées par Azure.

- **R2 (persistance)** : satisfaite par construction — vrai service de base
  de données géré, pas un fichier local.
- **R3 (isolation)** : le code ne change pas. L'isolation vient déjà du
  filtrage `WHERE user_id = ...` en Python, pas de l'infrastructure. Seule
  la chaîne de connexion (`DB_URL`) change.

Décision actée après une hésitation initiale (Postgres en conteneur
« temporaire ») : **migration directe vers le service managé**, plutôt que
Postgres en conteneur + volume Azure Files en attendant. Plus simple : une
seule persistance manuelle à gérer (Chroma), pas deux.

### Chroma → conteneur auto-hébergé + volume Azure Files

Aucun service Azure managé natif n'existe pour Chroma (contrairement à
Postgres). Deux options pesées :

| Option | Avantage | Risque |
|---|---|---|
| Auto-héberger (conteneur) | Code inchangé (`ChromaKB`, `vector_store.py`) — seule `CHROMA_URL` change | Persistance à gérer explicitement |
| Migrer vers un service Azure natif (ex. Azure AI Search) | Vraiment managé | Réécriture du code mémoire — **viole** l'interdiction de dégrader la mémoire au passage |

**Retenu : auto-hébergé.** Le brief interdit explicitement de dégrader ce qui
marche déjà ; réécrire l'intégration vectorielle pour un nouveau service,
avec un délai de 2 jours, est un risque à ne pas prendre pour un bénéfice
marginal.

**Persistance du conteneur (R2)** : un conteneur a par défaut un disque
éphémère — les données écrites disparaissent à tout redémarrage, sauf volume
externe attaché. Même mécanisme qu'en local (`docker-compose.yml` :
`.docker-data/chroma:/chroma/chroma`), transposé sur Azure via un compte de
stockage (Storage Account) + un partage **Azure Files**, monté dans le
conteneur au même chemin (`/chroma/chroma`).

## Position retenue

| Composant | Service Azure | Statut |
|---|---|---|
| Agent (API) | App Service, plan Basic, Linux, **conteneur** | Créé (`velmo-basic`, France Central) |
| Registre d'image | GitHub Container Registry (`ghcr.io`) | Opérationnel (`docker-build` en CD) |
| Mémoire relationnelle | Azure Database for PostgreSQL — Flexible Server | À provisionner |
| Mémoire vectorielle | Conteneur Chroma auto-hébergé | À provisionner |
| Persistance Chroma | Storage Account + Azure Files, monté sur `/chroma/chroma` | Droits à confirmer avant provisionnement |

**Point ouvert** : droits de création d'un Storage Account/Azure Files dans
l'abonnement — à confirmer avant le provisionnement (item 4 du
développement).

---

# Réponse 2 — Gestion des secrets et de la configuration

## Question

**Lister les secrets et paramètres à externaliser (clé et endpoint du
service d'IA, connexion au stockage mémoire, seuils des garde-fous).
Décrire où et comment ils seront stockés côté Azure, sans jamais figurer
dans le dépôt Git.**

## Inventaire (vérifié dans le code et le `.env`, rien de supposé)

### A. Vrais secrets (sensibles)

| Secret | Pourquoi c'est sensible |
|---|---|
| `AZURE_AI_INFERENCE_API_KEY` | Donne accès au LLM **et** à Content Safety — vérifié (`content_safety.py:65`) : les deux services réutilisent la même clé, pas de secret séparé pour Content Safety |
| `DB_URL` | Chaîne de connexion contenant identifiant **et** mot de passe intégrés |

### B. Paramètres de configuration (pas secrets, mais dépendent de l'environnement)

| Paramètre | Rôle |
|---|---|
| `AZURE_AI_INFERENCE_ENDPOINT` | URL du LLM |
| `AZURE_AI_INFERENCE_MODEL` | Nom du modèle (`gpt-5.4`) |
| `AZURE_AI_CLASSIFIER_MODEL` | Nom du modèle classifieur |
| `AZURE_CONTENT_SAFETY_ENDPOINT` | URL Content Safety |
| `CHROMA_URL` | Adresse du conteneur Chroma — changera pour pointer vers Azure |
| `EMBEDDING_MODEL` | Nom du modèle d'embeddings |

### C. Seuils des garde-fous : délibérément **non** externalisés en variables d'environnement

Vérifié dans le code : `REFUND_CAP = 50.0` (`tools/_common.py`) et
`_SEVERITY_THRESHOLD = 4` (`guardrails/content_safety.py`) sont des
constantes Python, pas des variables lues depuis l'environnement — de même
que le seuil/pondérations d'évaluation MLOps (`mlops/eval_manifest.yaml`).

**Décision actée** : on ne change **rien** à cette philosophie (cohérente
avec la Réponse 3 du chantier 3 — « config garde-fous → Git, structurel »).
Raison : une variable d'environnement Azure se modifie **silencieusement**
par quiconque a accès au portail, sans trace ni revue. Un seuil versionné en
Git ne change que via un commit — historique, revue possible, justification
tracée (`git log`). Pour un seuil qui décide quand bloquer un client ou
escalader un remboursement, cette traçabilité prime sur la commodité de
pouvoir le changer à chaud.

*« Seuils des garde-fous »* (item du brief) est donc satisfait par
l'existant, sans modification : `REFUND_CAP`, `_SEVERITY_THRESHOLD`
(constantes Python) et `mlops/eval_manifest.yaml` (seuil/pondérations
d'évaluation).

### D. Variable obsolète, à retirer

`EVAL_MIN_SCORE` — vérifié : plus lue nulle part dans le code (remplacée par
`mlops/eval_manifest.yaml`). Hors sujet pour Azure, à supprimer du `.env`.

## Où et comment stocker les vrais secrets (A) côté Azure

Deux mécanismes Azure possibles :

| Option | Limite |
|---|---|
| **App Settings** (variables d'application) | Chiffrées au repos, mais visibles **en clair** par quiconque a un accès Lecteur/Contributeur sur la Web App — pas de rotation/versionnage natif — dupliquées si plusieurs ressources en ont besoin |
| **Azure Key Vault** | Accès finement contrôlé (droit de lire *ce* secret, pas la config entière), versionnage natif, source unique même si plusieurs ressources en dépendent |

**Retenu : Azure Key Vault**, pour les deux vrais secrets (A). Ce n'est pas
qu'une préférence : c'est la recommandation documentée du *Well-Architected
Framework* Microsoft pour ce cas précis (clé d'API, chaîne de connexion).

**Mécanisme** : App Service reçoit une **identité managée** (identité Azure
automatique, pas un mot de passe à gérer) ; cette identité se voit accorder
le droit de lire les secrets dans Key Vault ; App Service référence le
secret sans jamais détenir de credential pour s'authentifier à Key Vault
lui-même — la confiance passe par l'identité Azure, pas par un secret de
plus à protéger.

Les paramètres de configuration (B) restent en **App Settings** — pas
sensibles, pas besoin du coffre.

## Position retenue

| Catégorie | Où | Mécanisme |
|---|---|---|
| Vrais secrets (A) : clé API, `DB_URL` | Azure Key Vault | Identité managée de l'App Service, accès en lecture seule au secret |
| Paramètres de config (B) : endpoints, noms de modèles, `CHROMA_URL` | App Settings (App Service) | Variables d'application classiques |
| Seuils des garde-fous (C) | Git (code + `mlops/eval_manifest.yaml`) | Commit + revue, jamais une variable d'environnement |
| `EVAL_MIN_SCORE` | — | Obsolète, à retirer du `.env` |

Aucun secret, à aucun moment, ne figure dans le dépôt Git ni dans le code
source — conforme au critère d'évaluation du brief.
