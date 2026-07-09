# Script de présentation — Mémoire Velmo 2.0 (10-15 min)

But de ce document : dérouler la présentation sans improviser, avec une checklist
qui élimine la cause du dernier échec (repli SQLite silencieux quand Postgres
n'était pas encore prêt).

Ordre retenu : **démo live d'abord** (concret, accroche), **puis le schéma**
(explique ce qu'on vient de voir), **puis le code** (pour qui veut creuser).

Durée cible : **7-10 min** de démo live + **3-4 min** de schéma/code.

**Prérequis de terminal** : Terminator avec 3 panneaux (splits combinés
`Ctrl+Shift+O`/`Ctrl+Shift+E`), tous visibles à l'écran pendant toute la démo :

- **Panneau A** : shell `psql` déjà connecté à la base (`velmo=#`), utilisé pour
  toutes les requêtes SQL du script — pas de `docker compose exec` à répéter.
- **Panneau B** : shell normal, utilisé pour `make chat` /
  `uv run python -m velmo.cli`.
- **Panneau C** : `tail -f logs/memory.log`, pour montrer en direct le tick du
  scheduler (appel LLM, traitement) pendant les temps d'attente des démos —
  rend visible ce qui se passe pendant les 40 secondes d'attente.

Astuce Terminator : grossir la police avant de commencer (`Ctrl+` plusieurs
fois dans chaque panneau) pour que le public lise les trois panneaux sans
plisser les yeux.

Toutes les requêtes SQL ci-dessous sont à taper **directement dans le prompt
`velmo=#`** du Panneau A (ne pas les préfixer de `docker compose exec ...`).

---

## Étape 0 — Démarrage de l'environnement (avant d'ouvrir les panneaux, 1 min)

Dans un shell normal (n'importe quel panneau, avant de dédier A et B), tuer
d'éventuels CLI restés ouverts d'une session précédente (chacun fait tourner
son propre scheduler — plusieurs en parallèle brouillent les logs et peuvent
écrire dans des bases différentes selon l'environnement chargé à leur lancement) :

```bash
ps aux | grep "velmo.cli" | grep -v grep
```

→ si des lignes apparaissent, relever leurs PID et les arrêter proprement
(`kill <PID>`, ou `kill -9 <PID>` si `kill` seul ne suffit pas après quelques
secondes).

Puis démarrer l'environnement :

```bash
docker compose up -d
docker compose ps
```

→ **Attendu** : `postgres` en statut `healthy`, `chroma` et `app` en `Up`. Si
`postgres` n'est pas encore `healthy`, attendre quelques secondes et relancer
`docker compose ps` avant de continuer — ne pas lancer le CLI avant ce statut.

Ouvrir les 3 panneaux Terminator (`Ctrl+Shift+O`/`Ctrl+Shift+E`), puis dans le
**Panneau A**, se connecter à Postgres en interactif :

```bash
docker compose exec postgres psql -U app -d velmo
```

→ le prompt devient `velmo=#` : c'est ce panneau qui sert pour toutes les
requêtes SQL du reste du script.

Dans le **Panneau C**, suivre les logs mémoire en direct :

```bash
tail -f logs/memory.log
```

→ ce panneau restera ouvert pendant toute la démo ; il affichera les ticks du
scheduler (`Scheduler started`, l'appel LLM `httpx: ... 200 OK`) au fur et à
mesure qu'ils se produisent, sans action de votre part.

---

## Checklist pré-démo (à faire AVANT d'accueillir le public, 2 min)

Ne pas sauter cette étape — c'est elle qui a fait échouer la dernière démo.

Dans le Panneau A (`velmo=#`), vérifier que la connexion répond :

```sql
SELECT 1;
```

Nettoyer la base pour une démo propre (toujours dans `velmo=#`) :

```sql
DELETE FROM message_brut;
DELETE FROM memory_users;
DELETE FROM memory_episodes;
DELETE FROM memory_facts;
```

Dans le Panneau B, lancer le CLI une première fois à blanc pour vérifier
l'absence du warning SQLite :

```bash
make chat
```

→ **Attendu** : la ligne `Velmo 2.0 prêt (client C-marc-dubois)...` apparaît
**directement**, sans le message `ATTENTION : Postgres (DB_URL) injoignable...`
au-dessus. Si ce warning apparaît, ne pas continuer la démo — relancer
`docker compose up -d`, attendre que `postgres` soit `healthy`, réessayer.

Fermer ce CLI de test (Ctrl+C) avant de commencer réellement.

---

## Partie 1 — Démo live (7-10 min)

### Ouverture — vue d'ensemble des tables (~30 s)

Dans le Panneau A (`velmo=#`), lister les tables avant de commencer :

```sql
\dt
```

→ pointer à l'oral les 4 tables mémoire au milieu des tables métier
(`customers`, `orders`, `products`...) : `memory_users`, `message_brut`,
`memory_episodes`, `memory_facts`. Dire : *"La mémoire vit dans le même schéma
que les données métier, pas dans une base à part."*

Dans le **Panneau B**, lancer :

```bash
make chat
```

**Vérifier à l'œil qu'aucun warning SQLite n'apparaît avant de continuer.**

### Démo 1 — Capture + consolidation épisodique (~2 min)

Dire : *"J'envoie un message, on va voir qu'il est capturé immédiatement, puis
consolidé automatiquement au bout de quelques secondes : le modèle mémoire
écrit toujours un épisode, et détecte en plus, dans le même appel LLM, si un
fait généralisable en ressort."*

Taper dans le CLI (Panneau B) :

```text
J'ai acheté le maillot de l'OM édition 1993.
```

Dans le **Panneau A** (`velmo=#`), **pendant que le CLI reste ouvert** :

```sql
SELECT contenu FROM message_brut;
```

→ montrer que le message est déjà là (capture synchrone, avant tout traitement).

Attendre ~40 secondes (laisser le tick du scheduler passer) en gardant le CLI
ouvert dans le Panneau B. Pendant l'attente, pointer le **Panneau C** : dire
*"Le scheduler tourne en tâche de fond, on va voir le tick apparaître ici"* et
montrer la ligne `httpx: ... 200 OK` (l'appel au LLM de consolidation) quand
elle arrive. Puis, dans le Panneau A :

```sql
SELECT contenu FROM message_brut;
SELECT contenu, consolidated, consolidated_key FROM memory_episodes;
```

→ montrer : `message_brut` est vide (traité), `memory_episodes` contient
l'épisode avec `consolidated = false` (ici, pas de fait sémantique
généralisable détecté — juste un événement).

### Démo 2 — Fait à clé connue, consolidé depuis un épisode (~2 min)

Dire : *"Cette fois, le message révèle un fait durable — on va voir qu'il
génère À LA FOIS un épisode (trace de l'échange) ET une entrée sémantique
(source de vérité pour la lecture)."*

Dans le CLI (Panneau B, toujours ouvert) :

```text
Ma pointure de chaussure c'est du 43.
```

Attendre ~40 secondes (jeter un œil au Panneau C pour montrer le tick).
Puis, dans le Panneau A :

```sql
SELECT id, pointure FROM memory_users;
SELECT contenu, consolidated, consolidated_key FROM memory_episodes WHERE consolidated_key = 'pointure';
```

→ `pointure = 43` **et** un épisode marqué `consolidated = true`,
`consolidated_key = 'pointure'`. Dire : *"L'épisode reste en base comme trace
d'audit — on sait d'où vient ce fait et quand il a été dit — mais ce n'est
plus lui qui est utilisé pour répondre, c'est le fait sémantique."*

```sql
SELECT contenu FROM memory_episodes WHERE consolidated = false;
```

→ **Attendu** : l'épisode consolidé n'apparaît pas ici (exclu par défaut de la
lecture normale, cf. `include_consolidated=False`) — seul `inspect()`/l'audit
y accède.

### Démo 2bis — Question FAQ (~1 min)

Dire : *"Une question générique sur la boutique répond directement via la
base de connaissances — mais attention, le message est quand même capturé et
consolidé comme n'importe quel autre : `write()` et la consolidation tournent
indépendamment du routage de réponse. Depuis le nouveau modèle, TOUT message
devient systématiquement un épisode, pas seulement ceux qui matchent un
mot-clé particulier."*

Dans le CLI (Panneau B, toujours ouvert) :

```text
Quels sont vos frais de livraison ?
```

→ **Attendu** : réponse directe tirée de `kb/docs/frais-de-port.md` (6,90 € en
France métropolitaine, gratuit dès 150 €).

Attendre ~40 secondes (Panneau C pour suivre le tick). Puis, dans le Panneau A :

```sql
SELECT contenu FROM memory_episodes WHERE user_id = 'C-marc-dubois' ORDER BY date DESC LIMIT 1;
```

→ **Attendu** : le message finit tout de même dans `memory_episodes` — capture
systématique, quel que soit le contenu. Ce n'est **pas** un bug : la mémoire
ne sait pas qu'une réponse FAQ a été donnée, elle capture et consolide chaque
message indépendamment. Bon point pédagogique à souligner : capture/
consolidation et routage de réponse sont deux mécanismes complètement
découplés dans l'agent.

Deuxième exemple du même phénomène — le suivi de commande, où la réponse vient
d'un routage déterministe (`Agent._handle()`, ni FAQ ni LLM), pas de la mémoire :

```text
Où en est ma commande O-2024-0103 ?
```

→ **Attendu** : réponse directe sur le statut de la commande (routage
déterministe via `tools.get_order`). Attendre ~40 secondes, puis dans le
Panneau A :

```sql
SELECT contenu FROM memory_episodes WHERE user_id = 'C-marc-dubois' ORDER BY date DESC LIMIT 1;
```

→ **Attendu** : ce message aussi finit dans `memory_episodes`. Même mécanisme :
capture et consolidation indépendantes du routage de réponse.

### Démo 2ter — Fait à clé imprévisible (`memory_facts` / vecteur) (~2 min)

Dire : *"Un fait qui n'a pas de colonne dédiée (un numéro de contrat, un
secret) part vers le store à clé libre — Chroma si disponible, sinon un repli
relationnel local `memory_facts`."*

Dans le CLI (Panneau B, toujours ouvert) :

```text
Mon numéro de contrat est CT-4521.
```

Attendre ~40 secondes (Panneau C pour suivre le tick). Puis, dans le Panneau A :

```sql
SELECT key, value FROM memory_facts WHERE user_id = 'C-marc-dubois';
```

→ **Attendu** : une ligne avec la `value` contenant `CT-4521`. Si le fait
n'apparaît pas ici, vérifier si Chroma est utilisé à la place (`docker compose
ps chroma`) — dans ce cas l'inspection passe par `MemoryManager.inspect()`
plutôt que par une requête SQL directe sur `memory_facts`.

### Démo 3 — Isolation entre utilisateurs (~2 min)

Dans le Panneau B, fermer le CLI courant (Ctrl+C, attendre `À bientôt !`).

Ouvrir avec un autre utilisateur :

```bash
uv run python -m velmo.cli --user C-demo-isolation
```

Taper :

```text
Ma pointure de chaussure c'est du 38.
```

Attendre ~40 secondes (Panneau C pour suivre le tick), fermer (Ctrl+C).
Puis, dans le Panneau A :

```sql
SELECT id, pointure FROM memory_users;
```

→ deux lignes distinctes, chacune avec sa pointure — aucun mélange entre
`C-marc-dubois` et `C-demo-isolation`.

### Démo 4 — Oubli contrôlé (~2 min, optionnel si le temps le permet)

Dans un shell normal (pas Panneau A, pas Panneau B — ou réutiliser B une fois
le CLI fermé) :

**Important** : `load_dotenv()` n'est appelé qu'à l'intérieur du CLI
(`cli.py:31`) — une commande `uv run python -c "..."` isolée ne charge PAS le
`.env` automatiquement. Sans ça, `DB_URL` vaut `None` et la commande bascule
silencieusement sur SQLite (un autre fichier que la démo, la purge semblera
fonctionner mais sur la mauvaise base). Toujours charger le `.env` explicitement :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
from velmo.memory import MemoryManager
mm = MemoryManager()
removed = mm.forget('C-marc-dubois', 'OM')
print('supprimés :', removed)
mm.close()
"
```

Dans le Panneau A :

```sql
SELECT contenu FROM memory_episodes WHERE user_id = 'C-marc-dubois';
```

→ l'épisode "OM" a disparu.

---

## Partie 2 — Schéma (2-3 min)

Support : [`conception/memoire/flux_reel.png`](../conception/memoire/flux_reel.png)
à l'écran.

Dire : *"Ce qu'on vient de voir en direct correspond à ce flux."* Dérouler le
schéma en pointant, dans l'ordre, ce que la démo a montré :

1. **4 briques mémoire** : court terme (RAM, fenêtre 30 tours), tampon de capture
   (`message_brut`), sémantique clé connue (`memory_users`), sémantique clé libre +
   épisodique (`memory_facts`/Chroma, `memory_episodes`).
2. **Découplage capture/traitement** : `write()` capture immédiatement (rapide,
   pas de LLM) ; un scheduler périodique (toutes les 20s ici, configurable)
   déclenche la classification et le routage vers le long terme — c'est le
   Panneau C qu'on vient de regarder pendant les 40 secondes d'attente.
3. **Isolation stricte par `user_id`** : la Démo 3 vient de le montrer, deux
   lignes distinctes dans `memory_users`.
4. **Oubli contrôlé (R5)** : `forget()` purge dans toutes les briques d'un coup
   (Démo 4).

Ne pas dérouler tout le détail fichier/ligne ici — rester au niveau du schéma,
le détail vient dans la partie suivante.

---

## Partie 3 — Code de base (2-3 min)

Support : les deux tableaux ci-dessous, en référence rapide (pas besoin
d'ouvrir les fichiers dans l'éditeur).

### Vue d'ensemble

| Brique | Fichier | Rôle |
|---|---|---|
| Court terme | `short_term.py` | Fil de session en RAM |
| Tampon de capture | `buffer.py` | Insertion synchrone (`MessageBrut`), sans LLM |
| Consolidation | `consolidation.py` | Un seul appel LLM : nettoie en épisode **et** détecte un fait sémantique optionnel |
| Sémantique (clé connue) | `semantic.py` | Colonnes directes sur `MemoryUser` |
| Sémantique (clé libre) | `vector_store.py` | Recherche par similarité (Chroma ou repli local) |
| Épisodique (relationnel) | `episodic.py` | Événements datés, recherche/tri par mots-clés |
| Épisodique (vectoriel) | `episode_vector_store.py` | Regroupement des épisodes par unité de sens |
| Orchestration | `__init__.py` (`MemoryManager`) | Point d'entrée unique |
| Traitement périodique | `processor.py` + `scheduler.py` | Le scheduler déclenche, à intervalle fixe, le traitement du tampon (`processor`) par utilisateur |

*Modèle retenu : chaque message est toujours capturé en épisodique (trace
d'audit) ; un fait sémantique généralisable en est éventuellement dérivé en
plus — pas à la place. Détail : `conception/memoire/evolution_consolidation.md`.*

### Tables (`src/velmo/db.py`)

| Table | Modèle | Utilité |
|---|---|---|
| `memory_users` | `MemoryUser` | Faits durables à clé connue d'avance (pointure, segment, tutoiement, langue, canal_contact) — une ligne par `user_id`, colonnes mises à jour en place |
| `message_brut` | `MessageBrut` | Tampon de capture synchrone : messages en attente de consolidation, purgés une fois traités |
| `memory_episodes` | `MemoryEpisode` | Événements datés, recherchables par mots-clés. `consolidated`/`consolidated_key` marquent la trace source d'un fait sémantique dérivé |
| `memory_facts` | `MemoryFact` | Faits à clé imprévisible, repli relationnel hors-ligne du vectoriel (utilisé si Chroma indisponible) |

Toutes indexées/filtrées par `user_id` (isolation R3).

Détail fichier/ligne complet si besoin de creuser :
[`docs/presentation_memoire.md`](presentation_memoire.md).

---

## Nettoyage après la démo

Dans le Panneau A (`velmo=#`) :

```sql
DELETE FROM message_brut;
DELETE FROM memory_users;
DELETE FROM memory_episodes;
DELETE FROM memory_facts;
```

---

## Si quelque chose se passe mal pendant la démo

- **Le warning SQLite apparaît** : Postgres n'était pas prêt. Fermer le CLI,
  `docker compose ps` pour vérifier `postgres` = `healthy`, relancer `make chat`.
- **`message_brut` reste non vide après 40s d'attente** : regarder le
  Panneau C (`tail -f logs/memory.log`, déjà ouvert) — si aucune ligne
  `httpx: ... 200 OK` n'est apparue, le scheduler n'a pas encore tické, attendre
  encore un peu.
- **Les messages s'empilent dans `message_brut` sans jamais être traités,
  même après plusieurs minutes** (déjà vu en répétition) : un tick est resté
  bloqué (probablement un appel réseau Azure qui ne répond jamais). Dans le
  Panneau C, les ticks suivants affichent `WARNING ... skipped: maximum number
  of running instances reached (1)` en boucle — c'est le signe. **Solution
  rapide** : fermer le CLI (Ctrl+C, Panneau B) et relancer `make chat` — ça tue
  le tick bloqué et repart avec un scheduler neuf ; le message en attente sera
  traité au tick suivant. Pas un signe de panique, juste relancer et continuer.
- **Rien ne s'affiche dans les tables alors que le CLI répond bien** : vérifier
  que le Panneau A est bien connecté à la base du `docker compose`
  (`velmo=#`), jamais à un fichier `.velmo_memory.db` (SQLite local, à ignorer
  s'il existe).
- **La commande `forget()` de la démo 4 semble fonctionner (`supprimés : N`)
  mais rien ne change dans le Panneau A** : la commande `uv run python -c "..."`
  n'a pas chargé le `.env` (pas de `load_dotenv()`), donc elle a agi sur le
  fichier SQLite local, pas sur Postgres. Vérifier que le bloc de code contient
  bien `from dotenv import load_dotenv; load_dotenv()` avant l'import de
  `velmo.memory`.
