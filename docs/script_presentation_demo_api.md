# Script de présentation — API REST Velmo 2.0 (8-10 min)

But de ce document : dérouler la présentation de la couche API (FastAPI)
au-dessus de l'agent, avec Bruno pour envoyer les requêtes, en montrant que
c'est bien le même agent (mémoire + garde-fous inclus) qui répond, juste
exposé en HTTP plutôt qu'en REPL.

Ordre retenu : **démo live d'abord** (Bruno + Swagger), **puis le schéma
d'architecture** (ce qu'on vient de voir), **puis le code** (pour qui veut
creuser).

Durée cible : **5-6 min** de démo live (4 requêtes Bruno) + **3-4 min**
schéma/code.

**Prérequis** :

- **Bruno** installé, une collection vide ou importée depuis
  `http://localhost:8000/openapi.json` (Bruno sait importer un schéma
  OpenAPI directement — évite de retaper les 2 endpoints à la main).
- Un terminal pour lancer l'API et suivre ses logs.
- `docker compose up -d` déjà fait (Postgres/Chroma joignables).

---

## Étape 0 — Démarrage (1 min)

```bash
docker compose ps
```

→ **Attendu** : `postgres` en `healthy`.

Lancer l'API :

```bash
make api
```

→ **Attendu** :
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Si `RuntimeError: Identifiants Azure requis...` apparaît à la place :
`AZURE_AI_INFERENCE_ENDPOINT`/`AZURE_AI_INFERENCE_API_KEY` manquent dans
`.env` — l'API en a besoin dès le démarrage (contrairement au CLI qui
échoue plus tard), car `get_chat_model()` est résolu dans le `lifespan`.

Dans le navigateur, ouvrir `http://localhost:8000/docs` (Swagger généré
automatiquement par FastAPI à partir des modèles Pydantic — rien à écrire
pour l'obtenir) : montrer les deux endpoints `POST /messages` et
`GET /users`, avec leurs schémas de requête/réponse déjà documentés.

---

## Partie 1 — Démo live avec Bruno (5-6 min)

Dire : *"On va envoyer les mêmes types de messages que dans les démos
précédentes (mémoire, garde-fous) — mais cette fois via HTTP, comme le
fera bientôt le front Vue.js."*

### Requête 1 — GET /users (liste pour peupler le futur front)

Dans Bruno, créer/ouvrir une requête **GET** :

```
GET http://localhost:8000/users
```

→ **Attendu** : `200 OK`, un tableau JSON de clients (id, full_name, email,
segment) — extrait réel observé :

```json
[
  {
    "id": "C-emma-roux",
    "full_name": "Emma Roux",
    "email": "emma.roux@example.com",
    "segment": "particulier"
  },
  {
    "id": "C-hugo-moreau",
    "full_name": "Hugo Moreau",
    "email": "hugo.moreau@example.com",
    "segment": "particulier"
  }
]
```

Dire : *"C'est la table `customers`, pas la mémoire — même un client qui
n'a jamais écrit un message apparaît ici, c'est le référentiel client, pas
l'historique de conversation."*

### Requête 2 — POST /messages : suivi de commande (tool-calling réel)

Créer une requête **POST**, body JSON :

```
POST http://localhost:8000/messages
Content-Type: application/json

{
  "user_id": "C-marc-dubois",
  "message": "Quel est le statut de ma commande O-2024-0101 ?"
}
```

→ **Attendu** : `200 OK`, réponse réelle observée :

```json
{
  "reply": "Votre commande **O-2024-0101** est actuellement au statut **préparée**.\n\nDétail rapide :\n- **Statut** : préparée\n- **Total** : **250,00 €**\n- **Article** : maillot taille **L**\n- **Adresse de livraison** : 12 rue du Stade, 69003 Lyon, France\n\nSi vous voulez, je peux aussi vous aider à :\n- vérifier si elle a déjà été expédiée,\n- modifier la **taille** ou l'**adresse** si l'expédition n'a pas encore eu lieu,\n- ou demander une **annulation**."
}
```

Dire : *"Le champ `reply` contient du Markdown — le rendu joli, c'est au
front de le faire, l'API renvoie juste le texte tel quel."* Pointer que
c'est exactement le même agent qu'en CLI : mémoire et garde-fous tournent
de la même façon, juste appelés via `POST` plutôt que via un `input()`.

### Requête 3 — POST /messages : message bloqué par un garde-fou

Même requête, body modifié :

```json
{
  "user_id": "C-marc-dubois",
  "message": "Sale race, retournez dans votre pays avec vos maillots."
}
```

→ **Attendu** : toujours `200 OK` (pas une erreur HTTP — un refus de
l'agent n'est pas un échec de l'API), réponse réelle observée :

```json
{
  "reply": "Je ne peux pas donner suite à ce message. Je reste à votre disposition pour vos commandes, livraisons, retours et la FAQ Velmo."
}
```

Dire : *"La cascade de garde-fous tourne exactement comme dans le CLI —
l'API n'a rien à faire de spécial, `Agent.respond()` gère ça en interne."*
Si un terminal `tail -f logs/guardrails.log` est ouvert à côté, montrer la
ligne `REGEX input ...` qui apparaît en même temps.

### Requête 4 — POST /messages : payload invalide (422)

Body volontairement incomplet :

```json
{
  "user_id": "C-marc-dubois"
}
```

→ **Attendu** : `422 Unprocessable Entity`, réponse réelle observée :

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "message"],
      "msg": "Field required",
      "input": {"user_id": "C-marc-dubois"}
    }
  ]
}
```

Dire : *"C'est FastAPI/Pydantic qui valide le format automatiquement, avant
même que le code de la route ne s'exécute — aucune validation manuelle à
écrire pour un champ manquant."*

---

## Partie 2 — Schéma d'architecture (2 min)

Dire, en dessinant ou en pointant un schéma simple (pas de fichier drawio
dédié pour l'instant — un schéma à main levée suffit à ce stade) :

```
Bruno / (futur) Vue.js
        │  HTTP (JSON)
        ▼
   FastAPI (api.py)
   ├── POST /messages ──► Agent.respond(user_id, message)
   │                         (même agent que le CLI : garde-fous + mémoire)
   └── GET /users ────────► table customers (référentiel client)

   lifespan (démarrage) : scheduler mémoire démarré une fois pour tout le
   process — sinon les messages captures via l'API resteraient dans
   message_brut sans jamais être consolidés.

   Une session DB par requête (Depends(get_session)) : pas d'état partagé
   entre deux appels HTTP concurrents.
```

Dire : *"Le point important : l'API n'a pas de logique métier à elle —
c'est une fine couche HTTP autour de `Agent.respond()`, qui existait déjà
pour le CLI. Rien n'a été dupliqué."*

---

## Partie 3 — Code de base (1-2 min)

Support : le tableau ci-dessous, en référence rapide.

| Élément | Fichier | Rôle |
|---|---|---|
| App FastAPI + lifespan | `src/velmo/api.py` | Démarre le scheduler mémoire, résout `get_chat_model()`/`get_kb()` une fois au démarrage |
| `POST /messages` | `api.py::post_message` | Construit un `Agent` avec une session par requête, appelle `respond()` |
| `GET /users` | `api.py::get_users` | Liste `Customer` (table `customers`, pas `memory_users`) |
| Session par requête | `api.py::get_session` | Dépendance FastAPI (`Depends`), fermée après chaque requête |
| Logging partagé | `src/velmo/logging_config.py` | Extrait de `cli.py`, utilisé par le CLI **et** l'API (mêmes 3 fichiers de log) |

*Pas d'authentification à ce stade (`user_id` en clair dans le payload) —
décision actée pour ce POC, la vraie auth viendra avec le front Vue.js.*

---

## Nettoyage après la démo

Arrêter l'API (Ctrl+C dans le terminal `make api`).

---

## Si quelque chose se passe mal pendant la démo

- **`RuntimeError: Identifiants Azure requis...` au lancement** :
  `AZURE_AI_INFERENCE_ENDPOINT`/`AZURE_AI_INFERENCE_API_KEY` absents de
  `.env` — contrairement au CLI, l'API échoue **au démarrage**, pas au
  premier message (résolu dans le `lifespan`).
- **`Connection refused` dans Bruno** : l'API n'est pas lancée, ou lancée
  sur un autre port — vérifier `make api` tourne bien et écoute sur
  `:8000` (`Uvicorn running on http://127.0.0.1:8000` dans le terminal).
- **`POST /messages` répond très lentement ou time-out** : instabilité
  Azure possible (cf. `docs/rapport_latence_azure_foundry.md`) — vérifier
  `logs/llm_latency.log` pour voir si l'appel a bien abouti côté serveur.
- **`GET /users` renvoie une liste vide** : la base n'a pas été seedée —
  lancer `make seed` avant de reprendre la démo.
