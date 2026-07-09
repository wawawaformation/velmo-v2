# Script de test manuel — Latence LLM, préchargement login, robustesse UTF-8

But : vérifier à la main les trois évolutions récentes (hors périmètre du
script de démo mémoire officiel `script_presentation_demo_memoire.md`) :

1. Log dédié de latence des appels LLM (`logs/llm_latency.log`)
2. Préchargement des faits mémoire en tâche de fond au login
3. Robustesse du CLI face à un octet UTF-8 invalide en entrée

Plus une **section d'inspection générale** (tables Postgres + collections
Chroma), utile pour vérifier l'état du système avant/après n'importe lequel
de ces tests, ou en cas de doute pendant une manip.

Durée estimée : 15-20 min. Pas une démo publique — un test de validation
technique, à faire seul avant de considérer ces points acquis.

**Prérequis** : `docker compose up -d`, `postgres` **et** `chroma` en statut
`healthy`/`Up` (`docker compose ps`).

Deux panneaux suffisent :

- **Panneau A** : `psql` connecté (`docker compose exec postgres psql -U app -d velmo`)
- **Panneau B** : shell normal, pour `make chat`, l'inspection des logs et de Chroma

---

## Inspection générale — tables Postgres et collections Chroma

À faire à tout moment pour un état des lieux (pas seulement en début de
script). Sert aussi de méthode de dépannage si un des tests plus bas donne
un résultat inattendu.

### Tables Postgres

Dans le Panneau A (`velmo=#`), lister toutes les tables :

```sql
\dt
```

→ **Attendu** : tables métier (`customers`, `orders`, `products`, `returns`,
`refunds`, `shipment_tracking`) + tables mémoire (`memory_users`,
`message_brut`, `memory_episodes`, `memory_facts`) + `alembic_version`.

Voir la structure d'une table mémoire (utile pour vérifier qu'une migration
a bien été appliquée, ex. les colonnes `consolidated`/`consolidated_key`) :

```sql
\d memory_episodes
```

Compter les lignes par table mémoire, pour une vue d'ensemble rapide :

```sql
SELECT 'memory_users' AS table, count(*) FROM memory_users
UNION ALL SELECT 'message_brut', count(*) FROM message_brut
UNION ALL SELECT 'memory_episodes', count(*) FROM memory_episodes
UNION ALL SELECT 'memory_facts', count(*) FROM memory_facts;
```

Voir le contenu complet d'une table (à répéter selon la table qui
intéresse) :

```sql
SELECT * FROM memory_users;
SELECT * FROM memory_episodes ORDER BY date DESC LIMIT 10;
SELECT * FROM memory_facts;
SELECT * FROM message_brut;
```

Vérifier la version de migration appliquée (doit correspondre au dernier
fichier dans `alembic/versions/`) :

```sql
SELECT * FROM alembic_version;
```

### Collections Chroma

Chroma n'a pas de shell interactif comme `psql` — l'inspection se fait via
l'API HTTP ou un script Python court. Le projet utilise potentiellement
jusqu'à 3 collections, selon ce qui a été alimenté :

| Collection | Alimentée par | Contenu |
| --- | --- | --- |
| `velmo_faq` | `make seed-kb` / `scripts/seed_kb.py` | Documents FAQ (`kb/docs/*.md`) |
| `velmo_episodes` | `episode_vector_store.py` (`ChromaEpisodeStore`) | Épisodes mémoire (si Chroma joignable, sinon repli `memory_episodes`) |
| `velmo_memory` | `vector_store.py` (`ChromaFactStore`) | Faits à clé libre (si Chroma joignable, sinon repli `memory_facts`) |

Vérifier que le service répond (healthcheck HTTP direct) :

```bash
curl -s http://localhost:8001/api/v2/heartbeat
```

→ **Attendu** : une réponse JSON (pas de `Connection refused`). Si ça échoue,
`docker compose ps chroma` pour vérifier que le conteneur tourne.

Lister les collections existantes et leur nombre d'éléments :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
import chromadb
client = chromadb.HttpClient(host='localhost', port=8001)
for c in client.list_collections():
    print(c.name, '->', c.count(), 'éléments')
"
```

→ **Attendu** : `velmo_faq` avec plusieurs documents (si `make seed-kb` a été
lancé) ; `velmo_episodes` et `velmo_memory` présentes seulement si Chroma a
déjà servi de backend au lieu du repli relationnel (sinon absentes — ce
n'est pas une erreur, c'est le repli `memory_episodes`/`memory_facts` qui a
pris le relais silencieusement).

Voir le contenu d'une collection précise (ex. `velmo_episodes`) :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
import chromadb
client = chromadb.HttpClient(host='localhost', port=8001)
c = client.get_collection('velmo_episodes')
result = c.get(include=['documents', 'metadatas'])
for doc, meta in zip(result['documents'], result['metadatas']):
    print(meta, '->', doc)
"
```

→ Remplacer `'velmo_episodes'` par `'velmo_memory'` ou `'velmo_faq'` selon
la collection à inspecter. Si `get_collection` lève une erreur
`does not exist`, la collection n'a simplement jamais été créée (Chroma
inutilisé pour cette brique jusqu'ici).

---

---

## 0. Nettoyage préalable

Dans le Panneau A (`velmo=#`) :

```sql
DELETE FROM message_brut;
DELETE FROM memory_users;
DELETE FROM memory_episodes;
DELETE FROM memory_facts;
```

Dans le Panneau B, vider les logs pour repartir propre (optionnel mais plus
lisible) :

```bash
: > logs/llm_latency.log
: > logs/memory.log
```

---

## 1. Log de latence LLM (`logs/llm_latency.log`)

Dire (à soi-même) : *"Chaque appel LLM — chat principal et consolidation
mémoire — doit apparaître ici avec sa durée, dans un fichier séparé de
`memory.log`."*

Dans le Panneau B :

```bash
make chat
```

Taper un message qui déclenche un appel LLM direct (pas de routage
déterministe, pas de FAQ) :

```text
Que peux-tu me dire sur les maillots collector en général ?
```

→ **Attendu** : réponse du LLM affichée normalement dans le CLI.

Sans fermer le CLI, dans un shell séparé (ou le Panneau A basculé
temporairement en shell) :

```bash
cat logs/llm_latency.log
```

→ **Attendu** : au moins une ligne de la forme
`2026-07-09 ... model=Kimi-K2.6 latency_ms=NNN.N` — le modèle du chat
principal, une latence numérique positive.

Attendre ~20-40 s (le temps d'un tick de scheduler consolidation), puis
relire le fichier :

```bash
cat logs/llm_latency.log
```

→ **Attendu** : une **deuxième** ligne apparaît, avec le modèle de
classification/consolidation (`Phi-4-mini-instruct` ou équivalent configuré
dans `AZURE_AI_CLASSIFIER_MODEL`) — preuve que le même mécanisme de logging
couvre aussi les appels internes, pas seulement le chat.

Vérifier que `logs/memory.log` ne contient **aucune** ligne `velmo.llm.latency`
(le fichier dédié ne doit rien faire fuiter vers l'autre) :

```bash
grep "latency" logs/memory.log
```

→ **Attendu** : aucune sortie (le `grep` ne trouve rien).

Fermer le CLI (Ctrl+C dans le Panneau B).

---

## 2. Préchargement mémoire au login

Dire : *"Au lancement du CLI, un thread en tâche de fond doit charger les
faits déjà connus pour l'utilisateur, avant même le premier message."*

D'abord, créer un fait pour avoir quelque chose à précharger. Dans le
Panneau B :

```bash
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
from velmo.memory import MemoryManager
mm = MemoryManager()
mm.remember_fact('C-marc-dubois', 'pointure', '43')
mm.close()
"
```

Vérifier en base (Panneau A) :

```sql
SELECT id, pointure FROM memory_users WHERE id = 'C-marc-dubois';
```

→ **Attendu** : une ligne avec `pointure = 43`.

Relancer le CLI :

```bash
make chat
```

→ **Attendu** : le message `Velmo 2.0 prêt (client C-marc-dubois)...`
s'affiche **sans délai perceptible** (le préchargement tourne en tâche de
fond, il ne bloque jamais l'affichage du prompt — c'est tout le but).

Il n'y a pas de sortie visible directe du préchargement (pas de print
dédié) : la preuve se fait par le comportement, pas par un log. Taper :

```text
Tu te souviens de moi ?
```

→ **Attendu** : le LLM restitue `pointure=43` dans sa réponse (le contexte
mémoire injecté contient bien le fait). Ce test valide indirectement que
`preload_facts` **et** `read()` retournent la même chose — le préchargement
n'a d'effet que sur la latence perçue du premier `read()`, pas sur le
contenu retourné.

Fermer le CLI (Ctrl+C).

---

## 3. Robustesse UTF-8 (octet invalide en entrée)

Dire : *"Un octet UTF-8 mal formé ne doit plus faire planter tout le
process — juste être remplacé, la conversation continue."*

Ce test nécessite d'envoyer un octet invalide, ce qui est difficile à taper
au clavier volontairement. Utiliser un pipe préparé à l'avance plutôt que
taper à la main :

```bash
printf 'salut\nVoici mon numero de contrat : \xc2XT-30445\nOK merci\n' | uv run python -m velmo.cli
```

→ **Attendu** :
- Le CLI démarre normalement.
- Le message `salut` reçoit une réponse.
- Le message contenant l'octet invalide (`\xc2`) **ne fait pas planter** le
  process — une réponse est produite (le `\xc2` se transforme en `�`, sans
  bloquer le reste de la phrase, `XT-30445` reste lisible dans la réponse
  du LLM si celui-ci le reprend).
- Le message `OK merci` reçoit aussi une réponse (preuve que le process a
  continué après l'octet invalide, pas juste survécu à un seul message).
- Le process se termine proprement en fin de flux (`À bientôt !`), sans
  traceback.

Si un `Traceback` ou `UnicodeDecodeError` apparaît, la régression n'est pas
corrigée — vérifier que `_read_line` (dans `src/velmo/cli.py`) est bien
utilisée dans la boucle de `main()` à la place de `input()`.

---

## Nettoyage final

Dans le Panneau A (`velmo=#`) :

```sql
DELETE FROM message_brut;
DELETE FROM memory_users;
DELETE FROM memory_episodes;
DELETE FROM memory_facts;
```

Dans le Panneau B :

```bash
: > logs/llm_latency.log
: > logs/memory.log
```
