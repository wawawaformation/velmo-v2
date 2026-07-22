# Script de présentation — Mémoire Velmo 2.0 (15-20 min)

But de ce document : dérouler la présentation sans improviser, avec une checklist
qui élimine la cause du dernier échec (repli SQLite silencieux quand Postgres
n'était pas encore prêt).

Ordre retenu : **démo live d'abord** (concret, accroche), **puis le schéma**
(explique ce qu'on vient de voir), **puis le code** (pour qui veut creuser).

Durée cible : **12-15 min** de démo live (mémoire + latence LLM + préchargement
login + robustesse UTF-8) + **3-4 min** de schéma/code. Les démos 5 à 7
(dernières évolutions techniques) sont optionnelles si le temps manque —
signalées comme telles ci-dessous.

**Prérequis de terminal** : Terminator avec 4 panneaux (splits combinés
`Ctrl+Shift+O`/`Ctrl+Shift+E`), tous visibles à l'écran pendant toute la démo :

- **Panneau A** : shell `psql` déjà connecté à la base (`velmo=#`), utilisé pour
  toutes les requêtes SQL du script — pas de `docker compose exec` à répéter.
- **Panneau B** : shell normal, utilisé pour `make chat` /
  `uv run python -m velmo.cli`.
- **Panneau C** : `tail -f logs/memory.log`, pour montrer en direct le tick du
  scheduler (appel LLM, traitement) pendant les temps d'attente des démos —
  rend visible ce qui se passe pendant les 40 secondes d'attente.
- **Panneau D** : `tail -f logs/llm_latency.log`, pour montrer en direct
  chaque appel LLM (chat et consolidation) avec sa durée, sans avoir à
  interrompre la démo pour aller lire le fichier (utile pour la Démo 3).

Astuce Terminator : grossir la police avant de commencer (`Ctrl+` plusieurs
fois dans chaque panneau) pour que le public lise les quatre panneaux sans
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

Ouvrir les 4 panneaux Terminator (`Ctrl+Shift+O`/`Ctrl+Shift+E`), puis dans le
**Panneau A**, se connecter à Postgres en interactif :

```bash
docker compose exec postgres psql -U app -d velmo
```

→ le prompt devient `velmo=#` : c'est ce panneau qui sert pour toutes les
requêtes SQL du reste du script.

Dans le **Panneau C**, suivre les logs de l'ordonnanceur (scheduler mémoire)
en direct :

```bash
tail -f logs/memory.log
```

→ ce panneau restera ouvert pendant toute la démo ; il affichera les ticks du
scheduler (`Scheduler started`, l'appel LLM `httpx: ... 200 OK`) au fur et à
mesure qu'ils se produisent, sans action de votre part.

Dans le **Panneau D**, suivre les latences LLM en direct :

```bash
tail -f logs/llm_latency.log
```

→ ce panneau affichera une ligne (`model=... latency_ms=...`) à chaque appel
LLM, chat comme consolidation — pratique pendant les 40 secondes d'attente
pour montrer concrètement ce qui se passe, sans commande à taper.

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

**Important** : Chroma étant réellement utilisé pour la mémoire (dès que
`CHROMA_URL` est joignable), ce nettoyage SQL ne suffit plus seul — les
anciens épisodes/faits restent indexés dans `velmo_episodes`/`velmo_memory`
et remontent quand même via la recherche par similarité, même après un
`DELETE FROM memory_episodes` complet (observé en usage réel : une réponse
mentionnant un contexte d'une session précédente pourtant purgée en SQL).
Vider aussi les collections Chroma (dans un shell libre, **pas** `velmo_faq`
— c'est la FAQ, pas la mémoire conversationnelle) :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
import chromadb
from chromadb.config import Settings
client = chromadb.HttpClient(
    host='localhost', port=8001,
    settings=Settings(anonymized_telemetry=False),
)
for name in ['velmo_episodes', 'velmo_memory']:
    try:
        client.delete_collection(name)
    except Exception:
        pass
"
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

Montrer aussi les collections vectorielles Chroma (aucun shell interactif
type `psql`, on passe par un script Python court, dans un shell libre) :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
import chromadb
from chromadb.config import Settings
client = chromadb.HttpClient(
    host='localhost', port=8001,
    settings=Settings(anonymized_telemetry=False),
)
for c in client.list_collections():
    print(c.name, '->', c.count(), 'éléments')
"
```

→ 3 collections attendues : `velmo_faq` (FAQ, alimentée par `make seed-kb`),
`velmo_episodes` et `velmo_memory` (mémoire épisodique/sémantique clé libre).
Dire : *"Chroma est le backend réel de la mémoire dès que `CHROMA_URL` est
joignable — le repli relationnel (`memory_episodes`/`memory_facts`) ne
prend le relais qu'en cas d'indisponibilité, avec un warning explicite dans
`logs/memory.log` (`Chroma ... injoignable ou en échec — repli sur
Local...Store`)."* Si `velmo_episodes`/`velmo_memory` sont absentes ici,
c'est le signe que ce repli est actif — vérifier `docker compose ps chroma`
et ce warning.

*(`anonymized_telemetry=False` évite le `Failed to send telemetry event`
inoffensif mais bruyant que Chroma affiche sinon à chaque connexion.)*

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

### Démo 2ter — Fait à clé imprévisible (Chroma / vecteur) (~2 min)

Dire : *"Un fait qui n'a pas de colonne dédiée (un numéro de contrat, un
secret) part vers le store à clé libre — Chroma en usage normal, avec un
repli relationnel local `memory_facts` si Chroma est indisponible."*

Dans le CLI (Panneau B, toujours ouvert) :

```text
Mon numéro de contrat est CT-4521.
```

Attendre ~40 secondes (Panneau C pour suivre le tick). Puis, l'inspection
passe par `MemoryManager.inspect()` (pas de SQL direct, le fait est indexé
dans Chroma, pas dans `memory_facts`) :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
from velmo.memory import MemoryManager
mm = MemoryManager()
print(mm.inspect('C-marc-dubois'))
mm.close()
"
```

→ **Attendu** : `CT-4521` apparaît dans les faits retournés. Si absent ici,
vérifier `memory_facts` en SQL comme repli (`SELECT key, value FROM
memory_facts WHERE user_id = 'C-marc-dubois';`) — signe que Chroma est
indisponible pour cette session (voir le warning dans `logs/memory.log`).

### Démo 3 — Log de latence LLM (~1 min, optionnel)

Dire : *"Chaque appel LLM — chat principal et consolidation mémoire — est
mesuré et journalisé en direct dans un fichier séparé, pour objectiver les
temps de réponse réels."* Pointer le **Panneau D**, déjà ouvert sur
`tail -f logs/llm_latency.log`.

Dans le CLI (Panneau B, toujours ouvert), un message qui déclenche un appel
LLM direct (pas de routage déterministe, pas de FAQ) :

```text
Que peux-tu me dire sur les maillots collector en général ?
```

→ **Attendu** : une ligne `model=Kimi-K2.6 latency_ms=NNN.N` apparaît
**aussitôt** dans le Panneau D. Attendre ~20-40 s (tick du scheduler,
visible en parallèle dans le Panneau C) : une **deuxième** ligne apparaît
dans le Panneau D, avec le modèle de classification/consolidation
(`Phi-4-mini-instruct` ou équivalent) — même mécanisme pour les appels
internes, pas seulement le chat. Dire : *"Le fichier tourne en rotation
(1 Mo, 3 sauvegardes) pour ne jamais grossir indéfiniment."*

### Démo 4 — Préchargement mémoire au login (~1-2 min, optionnel)

Dire : *"Au lancement du CLI, un thread en tâche de fond charge déjà les
faits connus de l'utilisateur, avant même son premier message — pour que la
première réponse mémoire soit plus rapide."*

Fermer le CLI courant (Ctrl+C). Relancer :

```bash
make chat
```

→ **Attendu** : `Velmo 2.0 prêt (client C-marc-dubois)...` s'affiche sans
délai perceptible (le préchargement tourne en arrière-plan, il ne bloque
jamais le prompt). Taper :

```text
Tu te souviens de moi ?
```

→ **Attendu** : le LLM restitue les faits déjà connus (ex. `pointure=43` si
la Démo 2 a été faite juste avant) — preuve indirecte que le préchargement
et `read()` pointent vers les mêmes données, seule la latence perçue change.

### Démo 5 — Robustesse face à un octet UTF-8 invalide (~1 min, optionnel)

Dire : *"Un bug réel observé en usage : une touche morte mal interceptée par
le terminal envoyait un octet invalide, qui faisait planter tout le CLI et
perdait la conversation. Ce n'est plus le cas."*

Fermer le CLI courant si besoin (Ctrl+C). Dans un shell libre (l'octet
invalide est difficile à taper au clavier, on le prépare via un pipe) :

```bash
printf 'salut\nVoici mon numero de contrat : \xc2XT-30445\nOK merci\n' | uv run python -m velmo.cli
```

→ **Attendu** : les trois messages reçoivent chacun une réponse, y compris
celui contenant l'octet invalide (transformé en `�`, le reste du message
reste lisible) ; le process se termine proprement (`À bientôt !`), sans
`Traceback`.

### Démo 6 — Isolation entre utilisateurs (~2 min)

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

### Démo 7 — Oubli contrôlé (~2 min, optionnel si le temps le permet)

Dire : *"`forget()` purge à la fois la base relationnelle et l'episode store
vectoriel Chroma — un oubli qui ne toucherait que Postgres laisserait
l'épisode retrouvable via une recherche par similarité, une vraie fuite RGPD.
C'est un bug qu'on a corrigé récemment (l'un existait sans qu'on le sache,
masqué par un autre bug qui empêchait Chroma d'être utilisé du tout)."*

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

Support : [`conception/memoire/flux_reel.drawio`](../conception/memoire/flux_reel.drawio)
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
3. **Isolation stricte par `user_id`** : la Démo 6 vient de le montrer, deux
   lignes distinctes dans `memory_users`.
4. **Oubli contrôlé (R5)** : `forget()` purge dans toutes les briques d'un coup
   (Démo 7).

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

Vider aussi les collections Chroma mémoire (voir l'avertissement de la
Checklist pré-démo — sans ça, les épisodes/faits de cette session restent
consultables la prochaine fois) :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
import chromadb
from chromadb.config import Settings
client = chromadb.HttpClient(
    host='localhost', port=8001,
    settings=Settings(anonymized_telemetry=False),
)
for name in ['velmo_episodes', 'velmo_memory']:
    try:
        client.delete_collection(name)
    except Exception:
        pass
"
```

Fermer les Panneaux C et D (Ctrl+C sur chaque `tail -f`), puis dans un shell
libre :

```bash
: > logs/llm_latency.log
: > logs/memory.log
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
- **La commande `forget()` de la démo 7 semble fonctionner (`supprimés : N`)
  mais rien ne change dans le Panneau A** : la commande `uv run python -c "..."`
  n'a pas chargé le `.env` (pas de `load_dotenv()`), donc elle a agi sur le
  fichier SQLite local, pas sur Postgres. Vérifier que le bloc de code contient
  bien `from dotenv import load_dotenv; load_dotenv()` avant l'import de
  `velmo.memory`.
- **`logs/llm_latency.log` reste vide après un message (Démo 3)** : vérifier
  que le CLI a bien été lancé via `make chat` (pas un `uv run python -c "..."`
  isolé) — c'est `cli.py::_configure_logging` qui câble le `RotatingFileHandler`
  dédié, rien n'est journalisé sans ce câblage.
- **Le pipe de la Démo 5 (`printf ... | uv run python -m velmo.cli`) affiche
  un `Traceback UnicodeDecodeError`** : la régression n'est pas corrigée —
  vérifier que `_read_line` (dans `src/velmo/cli.py`) est bien utilisée dans
  la boucle de `main()` à la place de `input()`.
- **`velmo_episodes`/`velmo_memory` absentes dans l'inspection Chroma de
  l'ouverture, alors que `docker compose ps chroma` montre le conteneur
  `Up`** : chercher une ligne `WARNING ... Chroma (CHROMA_URL=...)
  injoignable ou en échec — repli sur Local...Store` dans `logs/memory.log`
  (Panneau C) — la trace complète de l'exception y est jointe
  (`exc_info=True`), utile pour diagnostiquer sans deviner. Un bug de ce
  type (décorateur `@override` manquant dans `chroma_telemetry.py`) a déjà
  fait planter silencieusement toute bascule vers Chroma par le passé,
  corrigé depuis — si le warning apparaît malgré tout, c'est un nouvel
  incident à investiguer, pas un comportement attendu.
