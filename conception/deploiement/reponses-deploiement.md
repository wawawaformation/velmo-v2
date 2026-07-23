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
