# Script de présentation — Interface Vue.js Velmo 2.0 (8-10 min)

But de ce document : dérouler la présentation du front Vue.js (Vite + Sass)
au-dessus de l'API FastAPI, en montrant que l'utilisateur final voit le même
agent (mémoire + garde-fous inclus) que dans les démos CLI/API précédentes,
cette fois dans une vraie interface web.

Ordre retenu : **démo live d'abord** (navigateur), **puis le schéma
d'architecture**, **puis le code** (pour qui veut creuser).

Durée cible : **5-6 min** de démo live + **3-4 min** schéma/code.

**Prérequis** :

- `docker compose up -d` déjà fait (Postgres/Chroma joignables).
- Deux terminaux : un pour l'API, un pour le front.
- Navigateur ouvert sur `http://localhost:5173`.

---

## Étape 0 — Démarrage (1-2 min)

```bash
docker compose ps
```

→ **Attendu** : `postgres` en `healthy`.

Terminal 1 — l'API :

```bash
make api
```

→ **Attendu** :
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Terminal 2 — le front :

```bash
make frontend
```

→ **Attendu** :
```
  VITE v5.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

Ouvrir `http://localhost:5173` dans le navigateur.

Si la page reste blanche ou affiche une erreur `ECONNREFUSED` au premier
envoi de message : l'API n'est pas lancée — le proxy Vite (`vite.config.js`)
relaie `/api/...` vers `http://localhost:8000`, sans API en face la requête
échoue silencieusement côté fetch.

---

## Partie 1 — Démo live dans le navigateur (5-6 min)

Dire : *"C'est la même chose que les démos CLI et API précédentes — même
agent, mêmes garde-fous, même mémoire — mais cette fois avec l'interface que
verrait un vrai client."*

### Écran 1 — Chargement de la liste des clients

Au chargement, montrer que le sélecteur de profil (icône en haut à droite de
la nav) est déjà peuplé.

Dire : *"Au montage du composant (`onMounted`), le front appelle `GET
/api/users` pour peupler ce menu — c'est le même endpoint que dans la démo
API, juste consommé par `fetch()` au lieu de Bruno."*

Montrer le bandeau discret en haut de page (« Vous échangez avec une IA »,
orange) : *"C'est l'obligation de transparence du Règlement européen sur
l'IA (risque limité, art. 50) — le lien renvoie vers la page de la CNIL."*

### Écran 2 — Message légitime (tool-calling réel)

Sélectionner le client **Marc Dubois** via le dropdown profil.

Dans la zone de texte :

```
Quel est le statut de ma commande O-2024-0101 ?
```

Cliquer sur **Envoyer**.

→ **Attendu** : bouton en état de chargement (spinner) le temps de l'appel,
puis la réponse s'affiche dans la zone de réponse (Markdown brut, non
rendu — décision actée : le rendu Markdown n'est pas dans le périmètre de ce
POC), et l'indicateur de latence apparaît juste au-dessus de la réponse
(en secondes, ex. `1.8 s`).

Dire : *"Le champ `latency_ms` renvoyé par l'API est juste divisé par 1000
et affiché — aucune mesure côté front, la source de vérité c'est le serveur
(`time.monotonic()` autour de `Agent.respond()`)."*

### Écran 3 — Message bloqué par un garde-fou

Toujours sur Marc Dubois, remplacer le message par :

```
Sale race, retournez dans votre pays avec vos maillots.
```

Envoyer.

→ **Attendu** : la réponse s'affiche normalement dans la même zone (pas
d'erreur HTTP, pas de style rouge) — le refus de l'agent est traité comme une
réponse normale par le front, exactement comme il l'est par l'API.

Dire : *"Le front ne sait même pas qu'un garde-fou a tourné — il affiche le
`reply` tel quel, qu'il vienne du LLM ou d'un refus. C'est `Agent.respond()`
qui absorbe toute cette logique, l'API et le front n'en ont pas connaissance."*

### Écran 4 — Message pour un client différent (isolation mémoire)

Changer de client via le dropdown (ex. **Emma Roux**), envoyer un message
neutre :

```
Bonjour, avez-vous des maillots rétro ?
```

Dire : *"Changer de client dans le menu change juste le `user_id` envoyé au
`POST /messages` suivant — la mémoire et l'historique de Marc Dubois ne
fuient jamais vers Emma Roux, l'isolation par `user_id` tient au niveau de
l'agent, pas du front."*

### Écran 5 — API indisponible (état d'erreur)

Couper l'API (Ctrl+C dans le terminal `make api`), puis renvoyer un message
depuis le front.

→ **Attendu** : la zone de réponse passe en style d'erreur (fond/texte
rouge) avec le message *"Une erreur est survenue en contactant l'assistant.
Réessayez dans un instant."*

Dire : *"C'est le seul cas où le front distingue vraiment un échec — `fetch`
qui lève ou une réponse non-`ok`, catché dans `submitMessage()`."*

Relancer l'API (`make api`) pour la suite si besoin.

---

## Partie 2 — Schéma d'architecture (2 min)

Dire, en dessinant ou en pointant un schéma simple :

```
Navigateur (Vue 3 + Vite)
        │  fetch('/api/...')
        ▼
   Proxy Vite (dev only, vite.config.js)
        │  réécrit /api/* → http://localhost:8000/*
        ▼
   FastAPI (api.py)
   ├── POST /messages ──► Agent.respond(user_id, message)
   └── GET /users ────────► table customers

   Aucune logique métier dans le front : App.vue ne fait que du fetch +
   affichage. Le sélecteur de profil pilote juste le user_id envoyé.
```

Dire : *"En dev, le proxy Vite évite tout souci CORS — aucune URL en dur
dans le code JS, le front appelle toujours `/api/...` en relatif. En prod,
ce serait un reverse proxy (nginx) qui jouerait ce rôle."*

---

## Partie 3 — Code de base (1-2 min)

Support : le tableau ci-dessous, en référence rapide.

| Élément | Fichier | Rôle |
|---|---|---|
| Orchestration principale | `frontend/src/App.vue` | State (users, message, reply, latencyMs...), `loadUsers()`/`submitMessage()` |
| Logo + titre | `frontend/src/components/AppHeader.vue` | Logo SVG maillot de foot |
| Nav + sélecteur de profil | `frontend/src/components/AppNav.vue` | Dropdown pour changer de `selectedUserId` |
| Pied de page | `frontend/src/components/AppFooter.vue` | Liens factices + copyright |
| Tokens de thème | `frontend/src/styles/_tokens.scss` | Couleurs clair/sombre en custom properties CSS |
| Proxy dev | `frontend/vite.config.js` | Relaie `/api/...` vers `http://localhost:8000` |

*Pas d'authentification à ce stade (sélection du client via un simple menu
déroulant) — même décision actée que pour l'API, la vraie auth n'est pas
dans le périmètre de ce POC.*

---

## Nettoyage après la démo

Arrêter le front (Ctrl+C dans le terminal `make frontend`) et l'API (Ctrl+C
dans le terminal `make api`).

---

## Si quelque chose se passe mal pendant la démo

- **Page blanche ou `ECONNREFUSED` au premier envoi** : l'API n'est pas
  lancée sur `:8000`, ou lancée sur un autre port — vérifier `make api`
  tourne (`Uvicorn running on http://127.0.0.1:8000`).
- **Le sélecteur de profil reste vide** : `GET /api/users` a échoué ou la
  base n'est pas seedée — lancer `make seed` avant de reprendre la démo.
- **La réponse met longtemps à s'afficher** : instabilité Azure possible
  (cf. `docs/rapport_latence_azure_foundry.md`) — vérifier
  `logs/llm_latency.log` côté serveur API.
- **Port `5173` déjà utilisé** : un `npm run dev` précédent tourne encore en
  arrière-plan — le tuer ou relancer `make frontend` qui choisira un port
  libre (Vite l'indique dans sa sortie).
