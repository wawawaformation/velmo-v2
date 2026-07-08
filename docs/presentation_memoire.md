# Architecture mémoire — Velmo 2.0

Quatre briques, isolées par `user_id`, orchestrées par `MemoryManager`.
Référence de conception : `conception/memoire/choix.md`.

---

## 1. Vue d'ensemble

| Brique | Fichier | Rôle |
|---|---|---|
| Court terme | `short_term.py` | Fil de session en RAM |
| Tampon de capture | `buffer.py` | Insertion synchrone (`MessageBrut`), sans LLM |
| Sémantique (clé connue) | `semantic.py` | Colonnes directes sur `MemoryUser` |
| Sémantique (clé libre) | `vector_store.py` | Recherche par similarité (Chroma ou repli local) |
| Épisodique | `episodic.py` | Événements datés, recherche par mots-clés |
| Classification | `classifier.py` | Route chaque message vers sa destination |
| Orchestration | `__init__.py` (`MemoryManager`) | Point d'entrée unique |
| Traitement périodique | `processor.py` + `scheduler.py` | Le scheduler déclenche, à intervalle fixe, le traitement du tampon (`processor`) par utilisateur |

### Tables (`src/velmo/db.py`)

| Table | Modèle | Utilité |
|---|---|---|
| `memory_users` | `MemoryUser` | Faits durables à clé connue d'avance (pointure, segment, tutoiement, langue, canal_contact) — une ligne par `user_id`, colonnes mises à jour en place |
| `message_brut` | `MessageBrut` | Tampon de capture synchrone : messages en attente de classification/routage, purgés une fois traités |
| `memory_episodes` | `MemoryEpisode` | Événements datés (commande, livraison, achat...), recherchables par mots-clés |
| `memory_facts` | `MemoryFact` | Faits à clé imprévisible, repli relationnel hors-ligne du vectoriel (utilisé si Chroma indisponible) |

Toutes indexées/filtrées par `user_id` (isolation R3, cf. § 8).

### `MemoryManager` (`__init__.py`) — méthodes publiques

Point d'entrée unique du module : toutes les briques passent par cette classe, jamais appelées directement depuis l'extérieur du package `memory`.

| Méthode | Ligne | Rôle |
|---|---|---|
| `read(user_id, message)` | [`__init__.py:57`](../src/velmo/memory/__init__.py#L57) | Reconstitue le `MemoryContext` (historique + faits + épisodes) pertinent pour un message |
| `write(user_id, user_message, assistant_message)` | [`__init__.py:69`](../src/velmo/memory/__init__.py#L69) | Capture synchrone uniquement (court terme + tampon), aucun appel LLM |
| `run_pending_job(user_id)` | [`__init__.py:79`](../src/velmo/memory/__init__.py#L79) | Déclenche le traitement du tampon pour un utilisateur donné |
| `run_pending_job_all_users()` | [`__init__.py:87`](../src/velmo/memory/__init__.py#L87) | Traite le tampon pour tous les utilisateurs en attente, un par un (appelé par `scheduler.py`) |
| `remember_fact(user_id, key, value)` | [`__init__.py:98`](../src/velmo/memory/__init__.py#L98) | Écriture directe d'un fait durable, sans passer par le tampon |
| `forget(user_id, target)` | [`__init__.py:106`](../src/velmo/memory/__init__.py#L106) | Oubli contrôlé (R5) : purge dans toutes les briques |
| `inspect(user_id)` | [`__init__.py:121`](../src/velmo/memory/__init__.py#L121) | Traçabilité (R6) : état mémoire complet d'un utilisateur |
| `close()` | [`__init__.py:117`](../src/velmo/memory/__init__.py#L117) | Ferme la session DB sous-jacente |

Détail de chaque méthode et de son rôle dans les exigences R1-R6 : voir les sections dédiées ci-dessous.

---

## 2. Capture synchrone vs traitement asynchrone

- [`__init__.py:70` — `MemoryManager.write()`](../src/velmo/memory/__init__.py#L70)
  Capture pure : ajoute le tour en RAM (`short_term.append`) et dans le tampon DB (`buffer.capture`). **Aucun appel LLM**, latence quasi nulle.
- [`__init__.py:80` — `MemoryManager.run_pending_job(user_id)`](../src/velmo/memory/__init__.py#L80)
  Déclenche le traitement différé pour un utilisateur.
- [`__init__.py:88` — `MemoryManager.run_pending_job_all_users()`](../src/velmo/memory/__init__.py#L88)
  Boucle sur tous les `user_id` en attente (`buffer.pending_user_ids`), traite chacun séparément — isolation garantie même en traitement de masse.
- [`processor.py:16` — `process_pending(session, user_id)`](../src/velmo/memory/processor.py#L16)
  Cœur du traitement : lit le tampon (`buffer.pending_for`), appelle `classify_and_distill`, route le résultat, purge le tampon (`buffer.delete`).
- [`scheduler.py:25` — `start(interval_seconds=INTERVAL_SECONDS_DEFAULT)`](../src/velmo/memory/scheduler.py#L25)
  `BackgroundScheduler` (APScheduler) qui appelle `run_pending_job_all_users` en tâche de fond, toutes les [`INTERVAL_SECONDS_DEFAULT`](../src/velmo/memory/scheduler.py#L20) secondes. Démarrage explicite (pas d'activation à l'import).
- [`cli.py:52` — `job.shutdown(wait=True)`](../src/velmo/cli.py#L52)
  Fix critique : à la fermeture du CLI, on attend qu'un tick en cours se termine avant de couper le process. Avec l'ancien `shutdown(wait=False)` + `os._exit(0)`, un tick interrompu en plein traitement laissait le LLM appelé mais le tampon jamais purgé (message bloqué indéfiniment dans `message_brut`).

---

## 3. Classification et distillation d'un message

- [`classifier.py:142` — `classify_and_distill(message, llm=None)`](../src/velmo/memory/classifier.py#L142)
  Point d'entrée public. LLM si fourni, sinon repli par règles.
- [`classifier.py:81` — `_extract_known_column(message)`](../src/velmo/memory/classifier.py#L81)
  Extraction par regex d'une clé connue (pointure, segment, tutoiement, langue, canal_contact).
- [`classifier.py:97` — `_classify_with_rules(message)`](../src/velmo/memory/classifier.py#L97)
  Classement déterministe hors-ligne : colonne connue → épisodique → vectoriel → aucun.
- [`classifier.py:115` — `_classify_with_llm(message, llm)`](../src/velmo/memory/classifier.py#L115)
  Extraction via LLM (JSON structuré), `None` en cas d'échec de parsing (repli règles).
- [`classifier.py:43` — `ClassificationResult`](../src/velmo/memory/classifier.py#L43)
  `destination` / `key` / `value` — structure commune aux deux chemins.

---

## 4. Court terme (fenêtre de contexte)

- [`short_term.py:12` — `MAX_TURNS = 30`](../src/velmo/memory/short_term.py#L12) — taille de la fenêtre glissante
- [`short_term.py:17` — `append(user_id, role, content)`](../src/velmo/memory/short_term.py#L17) — ajoute un tour puis tronque à `MAX_TURNS` (`del turns[:-MAX_TURNS]`)
- [`short_term.py:23` — `get_turns(user_id)`](../src/velmo/memory/short_term.py#L23)
- [`short_term.py:27` — `purge_matching(user_id, target)`](../src/velmo/memory/short_term.py#L27) — oubli ciblé (R5)
- Stockage : `_HISTORY: dict[str, list[Turn]]` ([`short_term.py:14`](../src/velmo/memory/short_term.py#L14)) — dict en RAM, clé `user_id`, non persistant.

**R4 tenu par troncature simple, pas par résumé.** `conception/memoire/choix.md:94` documentait à l'origine un résumé glissant par budget de tokens ; implémenté à la place : une fenêtre glissante fixe de 30 tours (troncature pure, pas d'appel LLM de résumé). Les tours au-delà de la fenêtre ne sont pas perdus pour autant : le fait a déjà été distillé vers le long terme par `process_pending` **avant** qu'il ne sorte de la fenêtre (à condition qu'un tick ait eu lieu) — cf. § 7 pour la sélection des épisodes en complément.

---

## 5. Long terme sémantique — clé connue

- [`semantic.py:11` — `KNOWN_KEYS`](../src/velmo/memory/semantic.py#L11) : `pointure`, `segment`, `tutoiement`, `langue`, `canal_contact`
- [`semantic.py:14` — `set_known_fact(session, user_id, key, value)`](../src/velmo/memory/semantic.py#L14)
- [`semantic.py:25` — `get_known_facts(session, user_id)`](../src/velmo/memory/semantic.py#L25)
- [`semantic.py:32` — `clear_matching(session, user_id, target)`](../src/velmo/memory/semantic.py#L32) — oubli (R5)

## 6. Long terme sémantique — clé libre (vectoriel)

- [`vector_store.py:115` — `get_fact_store(session)`](../src/velmo/memory/vector_store.py#L115) : factory, Chroma si `CHROMA_URL` joignable, sinon repli local
- [`vector_store.py:28` — `LocalFactStore`](../src/velmo/memory/vector_store.py#L28) : recouvrement de tokens, hors-ligne (CI sans réseau)
- [`vector_store.py:73` — `ChromaFactStore`](../src/velmo/memory/vector_store.py#L73) : embeddings + métadonnées `user_id`/`key`
- Méthodes communes aux deux backends : `add`, `search`, `all_facts`, `delete_matching`

## 7. Long terme épisodique

- [`episodic.py:13` — `add_episode(session, user_id, contenu)`](../src/velmo/memory/episodic.py#L13)
- [`episodic.py:32` — `search_episodes(session, user_id, query)`](../src/velmo/memory/episodic.py#L32) — recherche par mots-clés (`LIKE`-like)
- [`episodic.py:41` — `delete_matching(session, user_id, target)`](../src/velmo/memory/episodic.py#L41) — oubli (R5)

---

## 8. Isolation par `user_id` (R3)

Chaque fonction de lecture/écriture/suppression prend `user_id` en paramètre et filtre dessus (`WHERE user_id == ...` en SQL, `where={"user_id": ...}` pour Chroma). Aucune fonction ne parcourt les données tous utilisateurs confondus.

- [`__init__.py:9` — commentaire d'en-tête](../src/velmo/memory/__init__.py#L9) : « Isolation stricte par `user_id` sur toutes les opérations (R3) »
- [`__init__.py:96` — boucle `for user_id in buffer.pending_user_ids(...)`](../src/velmo/memory/__init__.py#L96) : traitement de masse cloisonné, jamais de mélange entre clients dans un même appel

---

## 9. Oubli contrôlé (R5)

- [`__init__.py:107` — `MemoryManager.forget(user_id, target)`](../src/velmo/memory/__init__.py#L107)
  Orchestrateur unique, appelle en séquence :
  1. `short_term.purge_matching` (court terme)
  2. `semantic.clear_matching` (colonnes connues)
  3. `store.delete_matching` (vectoriel)
  4. `episodic.delete_matching` (épisodique)
  5. `buffer.delete_matching` (tampon non encore traité — ferme la fenêtre de risque)

---

## 10. Traçabilité (R6)

- [`cli.py:15` — `LOG_FILE = .../logs/memory.log`](../src/velmo/cli.py#L15) et [`cli.py:18` — `_configure_logging()`](../src/velmo/cli.py#L18) : tous les logs applicatifs (dont mémoire) écrits dans `logs/memory.log`.
- [`scheduler.py:37` — `logger.exception(...)`](../src/velmo/memory/scheduler.py#L37) : échec de traitement périodique tracé sans interrompre le scheduler.
- [`__init__.py:121` — `MemoryManager.inspect(user_id)`](../src/velmo/memory/__init__.py#L121) : inspection fonctionnelle — agrège faits connus, faits vectoriels et épisodes pour un utilisateur (audit/debug).

---

## 11. Chaîne complète (à montrer en slide)

```
scheduler.start()
  → MemoryManager.run_pending_job_all_users()
    → processor.process_pending(session, user_id)
      → classifier.classify_and_distill(message, llm)
        → routage : semantic.set_known_fact | vector_store.add | episodic.add_episode
      → buffer.delete(rows)
```

Découplage clé : `write()` (capture, synchrone, rapide) ≠ `process_pending()` (classification, asynchrone, coûteux en LLM).
