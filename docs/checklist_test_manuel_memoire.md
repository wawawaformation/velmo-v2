# Suite de tests manuels — pipeline mémoire (tampon → classification → routage)

Objectif : valider, étape par étape, chaque destination possible du pipeline mémoire
(`src/velmo/memory/classifier.py`) via le CLI + des requêtes psql directes sur la base
Postgres.

Pré-requis :

- `docker compose up -d` (Postgres + Chroma + app) démarré.
- Base `message_brut` vide avant de commencer (sinon nettoyer, cf. § 0).
- CLI lancé avec `uv run python -m velmo.cli` — l'utilisateur par défaut est
  `C-marc-dubois` (`--user` pour changer).
- Laisser le CLI ouvert au moins un intervalle de scheduler
  (`INTERVAL_SECONDS_DEFAULT`, `src/velmo/memory/scheduler.py:20`) avant de fermer
  avec Ctrl+C, pour laisser le tick de traitement s'exécuter.

Toutes les requêtes psql sont à exécuter via :

```bash
docker compose exec postgres psql -U app -d velmo -c "<requête>"
```

---

## 0. État initial — nettoyage

```sql
SELECT contenu FROM message_brut;
```

→ doit être vide. Sinon :

```sql
DELETE FROM message_brut;
DELETE FROM memory_users;
DELETE FROM memory_episodes;
DELETE FROM memory_facts;
```

---

## 0bis. Accès à la FAQ (base de connaissances)

**But** : vérifier que l'agent répond aux questions génériques via la base de
connaissances (`src/velmo/kb_store.py` — backend Chroma si `CHROMA_URL` joignable,
sinon repli local `LocalKB` sur `kb/docs/*.md`), **avant** d'entrer dans les tests
mémoire proprement dits. Une question FAQ ne doit rien écrire dans `message_brut`
côté faits mémorisables (elle peut quand même être capturée comme tour de
conversation en court terme, cf. § 1).

1. Vérifier que les documents FAQ sont présents :
   ```bash
   ls kb/docs/
   ```
   → doit lister des fichiers `.md` (ex. `delais-livraison.md`, `frais-de-port.md`,
   `politique-retour.md`...).
2. Lancer le CLI, envoyer une question dont la réponse est dans la FAQ :
   ```text
   Quels sont les délais de livraison ?
   ```
3. **Attendu** : la réponse de l'agent reprend les informations de
   `kb/docs/delais-livraison.md` (ex. "J+2" pour la France, "J+5" pour l'UE).
4. Fermer le CLI (Ctrl+C).

**Point d'attention** : si aucune réponse pertinente n'est retournée, vérifier que
`kb/docs/` n'est pas vide et que `get_kb()` (`kb_store.py:77`) retombe bien sur
`LocalKB` en l'absence de `CHROMA_URL` joignable (`docker compose ps chroma` pour
vérifier l'état du conteneur Chroma).

---

## 1. Capture synchrone dans `message_brut`

**But** : vérifier que le message est capturé immédiatement, avant tout traitement.

1. Lancer le CLI, envoyer :
   ```text
   J'ai acheté le maillot de l'OM édition 1993.
   ```
2. **Sans attendre**, dans un autre terminal :
   ```sql
   SELECT contenu FROM message_brut WHERE user_id = 'C-marc-dubois';
   ```
   → **Attendu** : 1 ligne, le message tel quel (capture synchrone, aucun appel LLM
   à ce stade — cf. `buffer.py:13`, `MemoryManager.write()` à `__init__.py:69`).

---

## 2. Classification épisodique

**But** : un message contenant un mot-clé épisodique (`_EPISODIC_HINTS`,
`classifier.py:59` : `adresse|command[ée]|rue des|achet[ée]|casque|maillot|colis|
livr[ée]|retour`) est routé vers `memory_episodes`.

1. Reprendre le message envoyé au § 1 : `"J'ai acheté le maillot de l'OM édition 1993."`
2. Attendre un tick du scheduler, puis fermer le CLI (Ctrl+C).
3. Vérifier que le tampon est vide :
   ```sql
   SELECT contenu FROM message_brut WHERE user_id = 'C-marc-dubois';
   ```
   → **Attendu** : 0 ligne.
4. Vérifier le routage épisodique :
   ```sql
   SELECT contenu FROM memory_episodes WHERE user_id = 'C-marc-dubois' AND contenu LIKE '%OM%';
   ```
   → **Attendu** : 1 ligne (le fait, éventuellement reformulé légèrement — nettoyage
   léger, mots-clés préservés).

---

## 3. Classification sémantique — clé connue (`semantic_column`)

**But** : un message évoquant une des clés connues (`KNOWN_KEYS`, `semantic.py:11` :
`pointure`, `segment`, `tutoiement`, `langue`, `canal_contact`) met à jour la colonne
correspondante dans `memory_users`.

1. Relancer le CLI, envoyer :
   ```text
   Ma pointure de chaussure c'est du 43.
   ```
2. Attendre un tick, fermer (Ctrl+C).
3. Vérifier :
   ```sql
   SELECT id, pointure FROM memory_users WHERE id = 'C-marc-dubois';
   ```
   → **Attendu** : `pointure = 43`.
4. Vérifier que le tampon est vide (comme § 2).

**Variante à tester également** (autre clé connue) :
```text
Tu peux me tutoyer.
```
→ **Attendu** : `tutoiement` renseigné dans `memory_users`.

> Équivalent automatisé : `tests/acceptance/test_memory.py::test_cross_session_persistence`.

---

## 4. Classification sémantique — clé imprévisible (`semantic_vector`)

**But** : un fait important sans clé prédéfinie (numéro de contrat, secret, code
postal) est routé vers le stockage vectoriel/relationnel (`memory_facts` en repli
local, ou Chroma si configuré — cf. `vector_store.py:115`, `_extract_known_column`
ne matche pas, mais le motif `secret|numéro|contrat|code postal`,
`classifier.py:109`, matche).

1. Relancer le CLI, envoyer :
   ```text
   Mon numéro de contrat est CT-7788.
   ```
2. Attendre un tick, fermer (Ctrl+C).
3. Vérifier (repli local — si `CHROMA_URL` n'est pas joignable) :
   ```sql
   SELECT key, value FROM memory_facts WHERE user_id = 'C-marc-dubois';
   ```
   → **Attendu** : 1 ligne contenant `CT-7788`.
4. Si Chroma est utilisé (voir `docker compose ps chroma`), l'inspection passe par
   `MemoryManager.inspect(user_id)` plutôt qu'une requête SQL directe — pas de table
   à interroger dans Postgres dans ce cas.

---

## 4bis. Fenêtre glissante — court terme (R1/R4)

**But** : vérifier que le fil court terme conserve au plus les 30 derniers tours
(`MAX_TURNS`, `short_term.py:12`), sans perdre l'information ancienne pour autant
(déjà distillée vers le long terme avant de sortir de la fenêtre).

1. Relancer le CLI, envoyer un premier message contenant un fait à retenir :
   ```text
   Ma commande prioritaire est O-2024-0101.
   ```
2. Attendre un tick (le fait est distillé vers le long terme avant que le fil ne
   tronque), puis envoyer plus de 30 messages de suivi quelconques (ex. copier-coller
   une trentaine de fois une question anodine).
3. Demander : `"Quelle était ma commande prioritaire ?"`
4. **Attendu** : l'agent retrouve `O-2024-0101` malgré le dépassement de la fenêtre
   de 30 tours — l'info vient du long terme (`memory_episodes`/`memory_facts`), pas
   du fil court terme qui l'a depuis tronquée.

> Équivalent automatisé : `tests/acceptance/test_memory.py::test_recall_over_30_turns`.

---

## 5. Aucun fait à retenir (`none`)

**But** : un message de pure conversation (salutation, remerciement) ne doit rien
persister en long terme.

1. Relancer le CLI, envoyer :
   ```text
   Merci beaucoup, bonne journée !
   ```
2. Attendre un tick, fermer (Ctrl+C).
3. Vérifier qu'aucune nouvelle ligne n'apparaît dans `memory_episodes`,
   `memory_users` (nouvelle colonne) ou `memory_facts` pour ce message.
4. Vérifier que le tampon est bien vidé (le message a été classé `none`, donc
   silencieusement écarté, mais purgé du tampon comme les autres) :
   ```sql
   SELECT contenu FROM message_brut WHERE user_id = 'C-marc-dubois';
   ```
   → **Attendu** : 0 ligne.

---

## 6. Oubli contrôlé — mémoire épisodique (R5)

**But** : vérifier que `MemoryManager.forget(user_id, target)` supprime bien un
épisode dont le contenu correspond à `target` (`episodic.delete_matching`,
`episodic.py:41` — comparaison sur le texte de l'épisode, pas sur une clé).

> Note : `forget()` n'est pas encore relié à une commande du CLI/agent (aucun
> message utilisateur du type "oublie X" ne le déclenche automatiquement) — ce test
> s'exécute donc directement en Python, pas via le CLI interactif.

1. Pré-requis : avoir un épisode existant, ex. celui du § 2
   (`"maillot de l'OM édition 1993"` pour `C-marc-dubois`). Sinon le recréer
   (§ 2) avant de continuer.
2. Vérifier l'état avant oubli :
   ```sql
   SELECT contenu FROM memory_episodes WHERE user_id = 'C-marc-dubois';
   ```
   → l'épisode doit être présent.
3. Déclencher l'oubli :
   ```bash
   uv run python -c "
   from velmo.memory import MemoryManager
   mm = MemoryManager()
   removed = mm.forget('C-marc-dubois', 'OM')
   print('supprimés :', removed)
   mm.close()
   "
   ```
4. Vérifier que l'épisode a disparu :
   ```sql
   SELECT contenu FROM memory_episodes WHERE user_id = 'C-marc-dubois';
   ```
   → **Attendu** : 0 ligne contenant "OM" (l'épisode est bien supprimé).

**Point d'attention** : `target` est comparé en sous-chaîne insensible à la casse
sur tout le contenu de l'épisode — un mot trop générique (ex. "commande") peut
supprimer plusieurs épisodes non liés. Vérifier `removed` (nombre retourné) pour
détecter une suppression plus large que prévu.

> Équivalent automatisé : `tests/acceptance/test_memory.py::test_right_to_be_forgotten`.

---

## 7. Isolation par utilisateur (R3)

**But** : vérifier qu'un fait mémorisé pour un utilisateur n'apparaît jamais pour un
autre.

1. Lancer le CLI avec un autre utilisateur :
   ```bash
   uv run python -m velmo.cli --user C-test-isolation
   ```
2. Envoyer : `"Ma pointure de chaussure c'est du 38."`
3. Attendre un tick, fermer.
4. Vérifier :
   ```sql
   SELECT id, pointure FROM memory_users WHERE id IN ('C-marc-dubois', 'C-test-isolation');
   ```
   → **Attendu** : deux lignes distinctes, chacune avec sa propre pointure (43 pour
   l'un, 38 pour l'autre) — aucun mélange.

> Équivalent automatisé : `tests/acceptance/test_memory.py::test_isolation_between_customers`.

---

## Récapitulatif

| # | Scénario | Destination attendue | Table vérifiée | Test d'acceptance équivalent |
|---|---|---|---|---|
| 0bis | Accès FAQ | — | `kb/docs/*.md` | — |
| 1 | Capture synchrone | — | `message_brut` (avant traitement) | — |
| 2 | Fait épisodique (achat, commande...) | `episodic` | `memory_episodes` | — |
| 3 | Fait à clé connue (pointure, tutoiement...) | `semantic_column` | `memory_users` | `test_cross_session_persistence` |
| 4 | Fait à clé imprévisible (n° contrat, secret...) | `semantic_vector` | `memory_facts` (ou Chroma) | — |
| 4bis | Fenêtre glissante 30 tours (R1/R4) | — | `memory_episodes`/`memory_facts` (long terme) | `test_recall_over_30_turns` |
| 5 | Message sans fait (salutation) | `none` | aucune (tampon quand même purgé) | — |
| 6 | Oubli contrôlé d'un épisode | — | `memory_episodes` | `test_right_to_be_forgotten` |
| 7 | Isolation entre deux `user_id` | — | `memory_users` | `test_isolation_between_customers` |

---

## Nettoyage après la suite

```sql
DELETE FROM message_brut;
DELETE FROM memory_users;
DELETE FROM memory_episodes;
DELETE FROM memory_facts;
```
