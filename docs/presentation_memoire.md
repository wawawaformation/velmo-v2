# Architecture mémoire — Velmo 2.0

Quatre briques, isolées par `user_id`, orchestrées par `MemoryManager`.
Référence de conception initiale : `conception/memoire/choix.md`.

**Évolution de doctrine (skill de cours `semantic-episodic-memory`)** :
`choix.md` décrit une classification directe (un message → une seule
destination). Le code actuel adopte un modèle à **consolidation** : chaque
message est toujours capturé en épisodique, et un fait sémantique
généralisable en est éventuellement dérivé **en plus** (pas à la place). Détail
complet et justification : `conception/memoire/evolution_consolidation.md`
(`choix.md` reste inchangé comme trace historique).

---

## 1. Vue d'ensemble

| Brique | Fichier | Rôle |
|---|---|---|
| Court terme | `short_term.py` | Fil de session en RAM |
| Tampon de capture | `buffer.py` | Insertion synchrone (`MessageBrut`), sans LLM |
| Sémantique (clé connue) | `semantic.py` | Colonnes directes sur `MemoryUser` |
| Sémantique (clé libre) | `vector_store.py` | Recherche par similarité (Chroma ou repli local) |
| Épisodique (relationnel) | `episodic.py` | Événements datés, recherche/tri par mots-clés |
| Épisodique (vectoriel) | `episode_vector_store.py` | Regroupement des épisodes par unité de sens (Chroma ou repli local par tokens) |
| Consolidation | `consolidation.py` | Un seul appel LLM : nettoie en épisode **et** détecte un fait sémantique généralisable optionnel |
| Orchestration | `__init__.py` (`MemoryManager`) | Point d'entrée unique |
| Traitement périodique | `processor.py` + `scheduler.py` | Le scheduler déclenche, à intervalle fixe, le traitement du tampon (`processor`) par utilisateur |

### Tables (`src/velmo/db.py`)

| Table | Modèle | Utilité |
|---|---|---|
| `memory_users` | `MemoryUser` | Faits durables à clé connue d'avance (pointure, segment, tutoiement, langue, canal_contact) — une ligne par `user_id`, colonnes mises à jour en place |
| `message_brut` | `MessageBrut` | Tampon de capture synchrone : messages en attente de classification/routage, purgés une fois traités |
| `memory_episodes` | `MemoryEpisode` | Événements datés (commande, livraison, achat...), recherchables par mots-clés. Colonnes `consolidated`/`consolidated_key` (migration `0002_episode_consolidation`) : marquent un épisode source d'un fait sémantique dérivé — trace d'audit (R6), exclu de la lecture par défaut |
| `memory_facts` | `MemoryFact` | Faits à clé imprévisible, repli relationnel hors-ligne du vectoriel (utilisé si Chroma indisponible) |

Toutes indexées/filtrées par `user_id` (isolation R3, cf. § 8).

### `MemoryManager` (`__init__.py`) — méthodes publiques

Point d'entrée unique du module : toutes les briques passent par cette classe, jamais appelées directement depuis l'extérieur du package `memory`.

| Méthode | Ligne | Rôle |
|---|---|---|
| `read(user_id, message)` | [`__init__.py:58`](../src/velmo/memory/__init__.py#L58) | Reconstitue le `MemoryContext` (historique + faits + épisodes) pertinent pour un message |
| `write(user_id, user_message, assistant_message)` | [`__init__.py:73`](../src/velmo/memory/__init__.py#L73) | Capture synchrone uniquement (court terme + tampon), aucun appel LLM |
| `run_pending_job(user_id)` | [`__init__.py:83`](../src/velmo/memory/__init__.py#L83) | Déclenche le traitement du tampon pour un utilisateur donné |
| `run_pending_job_all_users()` | [`__init__.py:91`](../src/velmo/memory/__init__.py#L91) | Traite le tampon pour tous les utilisateurs en attente, un par un (appelé par `scheduler.py`) |
| `remember_fact(user_id, key, value)` | [`__init__.py:102`](../src/velmo/memory/__init__.py#L102) | Écriture directe d'un fait durable, sans passer par le tampon (donc sans épisode source associé) |
| `forget(user_id, target)` | [`__init__.py:110`](../src/velmo/memory/__init__.py#L110) | Oubli contrôlé (R5) : purge dans toutes les briques, y compris l'épisode source d'un fait consolidé |
| `inspect(user_id)` | [`__init__.py:126`](../src/velmo/memory/__init__.py#L126) | Traçabilité (R6) : état mémoire complet d'un utilisateur |
| `close()` | [`__init__.py:122`](../src/velmo/memory/__init__.py#L122) | Ferme la session DB sous-jacente |

Détail de chaque méthode et de son rôle dans les exigences R1-R6 : voir les sections dédiées ci-dessous.

---

## 2. Capture synchrone vs traitement asynchrone

**Schéma à l'écran pour cette partie** : [`conception/memoire/flux_reel.drawio`](../conception/memoire/flux_reel.drawio) (export [`flux_reel.png`](../conception/memoire/flux_reel.png)) — montre le flux complet `write()` → tampon → scheduler/tick → `process_pending` → classification → routage, avec la légende des écarts vs `choix.md` à jour (intervalle 20s, fenêtre glissante 30 tours, fix `shutdown(wait=True)`).

- [`__init__.py:73` — `MemoryManager.write()`](../src/velmo/memory/__init__.py#L73)
  Capture pure : ajoute le tour en RAM (`short_term.append`) et dans le tampon DB (`buffer.capture`). **Aucun appel LLM**, latence quasi nulle.
- [`__init__.py:83` — `MemoryManager.run_pending_job(user_id)`](../src/velmo/memory/__init__.py#L83)
  Déclenche le traitement différé pour un utilisateur.
- [`__init__.py:91` — `MemoryManager.run_pending_job_all_users()`](../src/velmo/memory/__init__.py#L91)
  Boucle sur tous les `user_id` en attente (`buffer.pending_user_ids`), traite chacun séparément — isolation garantie même en traitement de masse.
- [`processor.py:23` — `process_pending(session, user_id, llm=None, episode_store=None)`](../src/velmo/memory/processor.py#L23)
  Cœur du traitement : lit le tampon (`buffer.pending_for`), appelle `consolidate` (un seul appel LLM), écrit **toujours** l'épisode (`episodic.add_episode`), route en plus le fait sémantique s'il y en a un, indexe l'épisode dans le vector store épisodique, purge le tampon (`buffer.delete`).
- [`scheduler.py:25` — `start(interval_seconds=INTERVAL_SECONDS_DEFAULT)`](../src/velmo/memory/scheduler.py#L25)
  `BackgroundScheduler` (APScheduler) qui appelle `run_pending_job_all_users` en tâche de fond, toutes les [`INTERVAL_SECONDS_DEFAULT`](../src/velmo/memory/scheduler.py#L20) secondes. Démarrage explicite (pas d'activation à l'import).
- [`cli.py:52` — `job.shutdown(wait=True)`](../src/velmo/cli.py#L52)
  Fix critique : à la fermeture du CLI, on attend qu'un tick en cours se termine avant de couper le process. Avec l'ancien `shutdown(wait=False)` + `os._exit(0)`, un tick interrompu en plein traitement laissait le LLM appelé mais le tampon jamais purgé (message bloqué indéfiniment dans `message_brut`).

**Historique du découplage — un angle mort resté longtemps invisible.** `write()`
n'a pas toujours été purement synchrone : dans l'implémentation initiale
(commit `7862816`, *"Implement memory (R1-R6) per conception/memoire/choix.md"*),
elle appelait directement `process_pending(...)` en son sein — classification
inline, à chaque écriture. Le commit `6416565`
(*"Decouple memory capture from processing"*) a ensuite introduit le
découplage actuel (`write()` = capture pure, `run_pending_job()` = traitement
à déclencher explicitement) et a corrigé `test_right_to_be_forgotten` en
conséquence (ajout d'un appel à `run_pending_job()` entre `write()` et le
premier `read()`).

`test_recall_over_30_turns` n'a en revanche **pas** reçu cette même mise à
jour à l'époque — il continuait d'enchaîner `write()` puis `read()` sans
jamais déclencher le traitement. Le test passait quand même, car le fil court
terme ne tronquait jamais (aucune limite de taille) : le fait restait
accessible via la RAM, sans besoin du long terme. L'angle mort n'est devenu
visible qu'avec l'introduction de `MAX_TURNS = 30` (§ 4) — une fois la
troncature réelle, le test échouait, révélant que le fait n'avait jamais été
distillé vers le long terme. Corrigé en ajoutant `mm.run_pending_job(user)`
juste après le premier `write()`, alignant ce test sur le même pattern que
`test_right_to_be_forgotten` depuis `6416565`.

---

## 3. Consolidation — un seul appel LLM, deux résultats

Remplace l'ancienne classification directe (`classify_and_distill`, toujours
présente dans `classifier.py` comme brique interne réutilisée, mais plus
appelée directement par `processor.py`). Voir
`conception/memoire/evolution_consolidation.md` pour la justification du
changement.

- [`consolidation.py:59` — `consolidate(message, llm=None)`](../src/velmo/memory/consolidation.py#L59)
  Point d'entrée public. Renvoie un `ConsolidationResult` : épisode nettoyé
  **toujours** présent, fait sémantique optionnel en plus. LLM si fourni,
  sinon repli par règles.
- [`consolidation.py:24` — `ConsolidationResult`](../src/velmo/memory/consolidation.py#L24)
  `episode: str` / `semantic: ClassificationResult | None`.
- [`consolidation.py:48` — `_consolidate_with_rules(message)`](../src/velmo/memory/consolidation.py#L48)
  Repli déterministe hors-ligne : épisode = message brut, réutilise
  `classifier._extract_known_column` pour détecter un éventuel fait connu.
- Validation de plausibilité (`classifier._VALUE_VALIDATORS`) réutilisée telle
  quelle : un fait implausible (ex. année classée pointure) n'est jamais
  consolidé, que ce soit via LLM ou via règles.
- Prompt système demande un objet JSON `{"episode": "...", "semantic": {...} | null}`
  — un seul appel réseau par message, pas de latence supplémentaire par
  rapport à l'ancienne classification directe.

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
- [`semantic.py:34` — `clear_matching(session, user_id, target)`](../src/velmo/memory/semantic.py#L34) — oubli (R5)

## 6. Long terme sémantique — clé libre (vectoriel)

- [`vector_store.py:115` — `get_fact_store(session)`](../src/velmo/memory/vector_store.py#L115) : factory, Chroma si `CHROMA_URL` joignable, sinon repli local
- [`vector_store.py:28` — `LocalFactStore`](../src/velmo/memory/vector_store.py#L28) : recouvrement de tokens, hors-ligne (CI sans réseau)
- [`vector_store.py:73` — `ChromaFactStore`](../src/velmo/memory/vector_store.py#L73) : embeddings + métadonnées `user_id`/`key`
- Méthodes communes aux deux backends : `add`, `search`, `all_facts`, `delete_matching`

## 7. Long terme épisodique — relationnel + vectoriel

**Relationnel** (`episodic.py`), source de vérité pour la persistance :

- [`episodic.py:13` — `add_episode(session, user_id, contenu, consolidated_key=None)`](../src/velmo/memory/episodic.py#L13)
  Écrit toujours l'épisode. `consolidated_key` (ex. `"pointure"`) marque un
  épisode comme source d'un fait sémantique dérivé.
- [`episodic.py:35` — `list_episodes(session, user_id, include_consolidated=False)`](../src/velmo/memory/episodic.py#L35)
  Exclut par défaut les épisodes consolidés (le fait sémantique associé est la
  source de vérité pour la lecture, pas l'épisode).
- [`episodic.py:46` — `search_episodes(session, user_id, query, include_consolidated=False)`](../src/velmo/memory/episodic.py#L46)
  — recherche par mots-clés (`LIKE`-like).
- [`episodic.py:57` — `delete_by_consolidated_key(session, user_id, key)`](../src/velmo/memory/episodic.py#L57)
  Purge l'épisode source d'un fait consolidé, par sa clé — nécessaire car le
  texte nettoyé par le LLM ne contient pas forcément le mot cible littéral.
- [`episodic.py:71` — `delete_matching(session, user_id, target)`](../src/velmo/memory/episodic.py#L71) — oubli par correspondance textuelle (R5)

**Vectoriel** (`episode_vector_store.py`), regroupement par unité de sens —
évolution notée en v2 dans `choix.md:151`, maintenant implémentée :

- [`episode_vector_store.py:82` — `get_episode_store(session)`](../src/velmo/memory/episode_vector_store.py#L82) : factory, Chroma (collection `velmo_episodes`) si `CHROMA_URL` joignable, sinon repli local
- [`episode_vector_store.py:20` — `LocalEpisodeStore`](../src/velmo/memory/episode_vector_store.py#L20) : ne duplique pas les données — réutilise `episodic.list_episodes`, ajoute un tri par recouvrement de tokens (`add`/`delete_matching` sont des no-op, la persistance est déjà assurée côté relationnel)
- [`episode_vector_store.py:46` — `ChromaEpisodeStore`](../src/velmo/memory/episode_vector_store.py#L46) : embeddings réels + métadonnées `user_id`/`consolidated`

---

## 8. Isolation par `user_id` (R3)

Chaque fonction de lecture/écriture/suppression prend `user_id` en paramètre et filtre dessus (`WHERE user_id == ...` en SQL, `where={"user_id": ...}` pour Chroma). Aucune fonction ne parcourt les données tous utilisateurs confondus.

- [`__init__.py:9` — commentaire d'en-tête](../src/velmo/memory/__init__.py#L9) : « Isolation stricte par `user_id` sur toutes les opérations (R3) »
- [`__init__.py:99` — boucle `for user_id in buffer.pending_user_ids(...)`](../src/velmo/memory/__init__.py#L99) : traitement de masse cloisonné, jamais de mélange entre clients dans un même appel

---

## 9. Oubli contrôlé (R5)

- [`__init__.py:110` — `MemoryManager.forget(user_id, target)`](../src/velmo/memory/__init__.py#L110)
  Orchestrateur unique, appelle en séquence :
  1. `short_term.purge_matching` (court terme)
  2. `semantic.clear_matching` (colonnes connues)
  3. `store.delete_matching` (vectoriel sémantique)
  4. `episodic.delete_matching` (épisodique, correspondance textuelle)
  5. `episodic.delete_by_consolidated_key` (épisode source d'un fait consolidé, par clé — nécessaire car le texte nettoyé par le LLM peut ne pas contenir le mot cible littéral)
  6. `buffer.delete_matching` (tampon non encore traité — ferme la fenêtre de risque)

**Double stockage d'un fait consolidé.** Depuis l'adoption du modèle à
consolidation, un fait comme la pointure vit à deux endroits : la colonne
`memory_users.pointure` (source de vérité pour la lecture) **et** l'épisode
source marqué `consolidated_key="pointure"` (trace d'audit R6). `forget()`
doit purger les deux, sinon l'oubli serait incomplet — testé par
`tests/acceptance/test_memory.py::test_forget_removes_consolidated_episode_even_without_text_match`.

---

## 10. Traçabilité (R6)

- [`cli.py:15` — `LOG_FILE = .../logs/memory.log`](../src/velmo/cli.py#L15) et [`cli.py:18` — `_configure_logging()`](../src/velmo/cli.py#L18) : tous les logs applicatifs (dont mémoire) écrits dans `logs/memory.log`.
- [`scheduler.py:37` — `logger.exception(...)`](../src/velmo/memory/scheduler.py#L37) : échec de traitement périodique tracé sans interrompre le scheduler.
- [`__init__.py:126` — `MemoryManager.inspect(user_id)`](../src/velmo/memory/__init__.py#L126) : inspection fonctionnelle — agrège faits connus, faits vectoriels et épisodes pour un utilisateur (audit/debug). Épisodes consolidés inclus via `include_consolidated=True` : permet de retracer quel échange a produit quel fait.

---

## 11. Chaîne complète (à montrer en slide)

```
scheduler.start()
  → MemoryManager.run_pending_job_all_users()
    → processor.process_pending(session, user_id)
      → consolidation.consolidate(message, llm)   [un seul appel LLM]
        → episodic.add_episode(...)                [toujours]
        → routage optionnel en plus :
            semantic.set_known_fact | vector_store.add
        → episode_vector_store.add(...)            [indexation Chroma]
      → buffer.delete(rows)
```

Découplage clé : `write()` (capture, synchrone, rapide) ≠ `process_pending()` (consolidation, asynchrone, coûteux en LLM — mais toujours un seul appel par message, comme avant).

---

## 12. De la lecture mémoire à l'injection dans le prompt LLM

**Où `read()` est appelé** : [`agent.py:86` — `Agent.respond()`](../src/velmo/agent.py#L86) — `context = self.memory.read(user_id, message).render()`, calculé **avant** le routage déterministe (commande, stock, FAQ...), donc systématiquement à chaque tour, même si le contexte ne sera pas toujours utilisé.

**Où `context` sert réellement** : [`agent.py:147` — `self.llm.invoke(SYSTEM_PROMPT, context, message)`](../src/velmo/agent.py#L147), dans [`Agent._handle()`](../src/velmo/agent.py#L98) — uniquement en dernier recours, quand aucun routage déterministe n'a matché (pas de numéro de commande, pas de question stock/FAQ). Les branches déterministes (`_format_order`, `_format_tracking`, `_format_kb`...) répondent sans jamais consulter `context` : le calcul fait à la ligne 86 est donc parfois perdu (calculé pour rien) si la question est finalement traitée par une règle plutôt que par le LLM.

**Comment `context` devient du texte** : [`__init__.py:41` — `MemoryContext.render()`](../src/velmo/memory/__init__.py#L41) concatène, ligne par ligne : l'historique court terme (`role: contenu`), les faits sémantiques connus (`fact:key=value`), puis les épisodes/faits vectoriels retrouvés (sémantiques imprévisibles **et** épisodiques, tous deux via vector store depuis l'Étape 2) — un simple `"\n".join(...)`, pas de mise en forme élaborée ni de résumé.

**Comment le texte s'insère dans le prompt final** : [`llm.py:44` — `LangChainAdapter.invoke(system, context, message)`](../src/velmo/llm.py#L44) — le template est `"{system}\n{context}{message}"` ; `context` est préfixé par `"Mémoire:\n"` seulement s'il est non vide (`llm.py:47`). Le repli hors-ligne `EchoLLM` (`llm.py:19`) ignore totalement `context` et `system` — utile pour les tests, mais ne permet pas de vérifier visuellement l'injection mémoire (`CapturingLLM`, dans `tests/acceptance/test_memory.py:10`, sert justement à ça : il renvoie `context` tel quel pour que le test puisse l'inspecter).

**Point d'attention pédagogique** : la mémoire ne "force" jamais la réponse du LLM — elle n'est qu'un bloc de texte ajouté au prompt système. Rien n'empêche le LLM de l'ignorer ; c'est `test_agent_injects_memory_context_into_llm_fallback` (`tests/acceptance/test_memory.py:92`) qui garantit que le contexte est bien *transmis*, pas qu'il est *utilisé* par un vrai LLM (le test utilise `CapturingLLM`, qui renvoie le contexte reçu, précisément pour découpler cette vérification d'un appel LLM réel).
