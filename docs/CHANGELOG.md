# Changelog

Toutes les modifications notables de Velmo 2.0 sont documentées ici.

Le format s'inspire de [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Ajouté

- **Garde-fous (Chantier 2)** : Implémentation complète des règles déterministes (v1) pour bloquer le contenu nuisible en entrée (haine/violence/sexuel, injection de prompt, hors périmètre) et en sortie (mêmes catégories + PII/secrets). Journalisation structurée via `GuardrailEvent` avec extraits tronqués (jamais la donnée brute). Note : la détection `secret_leak` (PII/secrets) s'applique à la fois à l'entrée et à la sortie, décision de conception documentée dans `conception/garde-fous/synthese.md`.
- **Consolidation épisodique → sémantique (mémoire)** : évolution de doctrine par rapport à la classification directe de `conception/memoire/choix.md` (laissé intact comme trace historique), au profit du modèle du skill de cours `semantic-episodic-memory` : chaque message est désormais **toujours** capturé en épisodique (nettoyage léger), et le même appel LLM détecte en plus un éventuel fait sémantique généralisable à consolider — l'épisode source (marqué `consolidated`/`consolidated_key`) reste en base comme trace d'audit (R6) plutôt que d'être perdu. `MemoryManager.forget()` purge désormais aussi l'épisode source lié à un fait consolidé (R5), pas seulement par correspondance textuelle. Nouveau module `src/velmo/memory/consolidation.py`, migration Alembic `0002_episode_consolidation`. Détail complet : `conception/memoire/evolution_consolidation.md`. Tests : `tests/unit/test_consolidation.py`, `tests/unit/test_episodic.py`, `tests/unit/test_processor.py`.
- **Log de latence LLM** : `LangChainAdapter.invoke()` (src/velmo/llm.py) mesure et journalise désormais la latence de chaque appel LLM (logger dédié `velmo.llm.latency`, nom du modèle + durée en ms), couvrant à la fois le chat principal (Kimi-K2.6) et la classification/consolidation mémoire (Phi-4-mini-instruct) puisque les deux passent par ce même adaptateur. Le CLI (`src/velmo/cli.py::_configure_logging`) câble ce logger vers un fichier dédié `logs/llm_latency.log` (`propagate = False`, ne pollue pas `logs/memory.log`), avec rotation (`RotatingFileHandler`, 1 Mo, 3 sauvegardes conservées) pour éviter une croissance illimitée — un appel toutes les ~20s (tick scheduler) rend ce fichier bavard en usage prolongé. Tests : `tests/unit/test_llm_latency.py`.
- **Préchargement mémoire au login** : nouvelle méthode `MemoryManager.preload_facts(user_id)` (faits connus + faits vectoriels, sans recherche sémantique/épisodique qui nécessite un message). `cli.py::main` la déclenche dans un thread en arrière-plan dès le lancement (avant le premier message de l'utilisateur), avec sa propre session DB (non partageable entre threads) — réduit la latence perçue du premier `read()` en cours de conversation. Tests : `tests/unit/test_memory_manager.py::test_preload_facts_returns_known_and_vector_facts`.

### Corrections

- **Fuite possible de donnée sensible dans les logs de garde-fous** : `_redact` tronquait l'extrait journalisé à 40 caractères sans masquer spécifiquement la donnée sensible ; un secret court (mot de passe, mention de clé API, etc.) situé en début de message aurait été journalisé tel quel dans `GuardrailEvent.excerpt_redacted`. Pour les catégories `pii` et `secret_leak` uniquement, `_log` journalise désormais un placeholder générique fixe (`[donnée sensible masquée]`) au lieu d'un extrait du texte réel — plus aucune donnée brute ne peut transiter par troncature, quelle que soit sa position dans le message. Comportement inchangé pour les autres catégories (hate/violence/sexual/prompt_injection/out_of_scope). Tests : `tests/unit/test_guardrail_engine.py::test_check_output_short_password_near_start_never_logged_verbatim` et `::test_check_input_short_secret_leak_near_start_never_logged_verbatim`.
- **Statut de commande en français** : `_format_order` (agent.py) traduit désormais le statut technique (`shipped`, `delivered`, etc.) en français (« expédiée », « livrée », etc.) via un mapping `_ORDER_STATUS_FR`, au lieu d'afficher la valeur brute de l'enum `OrderStatus`
- **Incompatibilité client/serveur Chroma** : `docker-compose.yml` utilisait `chromadb/chroma:latest` (serveur en v1.4.4), incompatible avec le client Python figé sur `chromadb>=0.5,<0.6` (`pyproject.toml`), causant un `KeyError: '_type'` lors de la création de la collection `velmo_faq` ; image serveur épinglée sur `chromadb/chroma:0.5.23`
- **`make seed-kb` depuis l'hôte** : le script `scripts/seed_kb.py` se connectait par défaut à `chroma:8000` (nom de service Docker, résoluble uniquement depuis le réseau Compose) ; `make seed-kb` fixe désormais `CHROMA_HOST=localhost CHROMA_PORT=8001` pour fonctionner depuis la machine hôte, cohérent avec `CHROMA_URL` dans `.env.example`
- **Crash CLI sur octet UTF-8 invalide en entrée** : `input()` levait `UnicodeDecodeError` sur un octet non décodable (ex. touche morte mal interceptée par le terminal), tuant tout le process et perdant le fil de conversation en cours (observé en usage réel). Nouvelle fonction `_read_line` (src/velmo/cli.py) lit `sys.stdin.buffer` en octets et décode avec `errors="replace"` au lieu de planter. Tests : `tests/unit/test_cli_read_line.py`.
- **Crash CLI sur timeout LLM** : un incident réseau (`openai.APITimeoutError` déclenché par `LLM_TIMEOUT_SECONDS`, cf. `src/velmo/llm.py`) remontait tel quel depuis `agent.respond()`, tuant tout le process et perdant le fil de conversation en cours (observé en usage réel). Nouvelle fonction `_safe_respond` (src/velmo/cli.py) encadre l'appel dans un `try/except Exception` (n'intercepte pas `KeyboardInterrupt`, qui hérite de `BaseException`), journalise l'incident et renvoie un message d'erreur à l'utilisateur au lieu de planter. Le message utilisateur est capturé en mémoire malgré l'échec (`agent.memory.write(...)`, traçabilité R6), symétrique au chemin garde-fou existant (`Agent.respond()` capture déjà le message sur un refus). Tests : `tests/unit/test_cli_safe_respond.py`.
- **Chroma jamais réellement utilisé pour la mémoire (bascule silencieuse vers le repli relationnel)** : `NoOpProductTelemetry.capture` (`src/velmo/chroma_telemetry.py`) surchargeait `ProductTelemetryClient.capture` sans le décorateur `@override` requis par la lib `overrides` (dépendance de `chromadb`), levant un `TypeError` à l'import — avalé silencieusement par le `except Exception` de `get_episode_store`/`get_fact_store`, qui retombaient donc **toujours** sur `LocalEpisodeStore`/`LocalFactStore` (relationnel), même avec `CHROMA_URL` configuré et Chroma disponible, depuis le début du projet. Corrigé par l'ajout de `@override`. Un `logger.warning(..., exc_info=True)` est désormais émis à chaque bascule vers le repli (symétrique au warning SQLite existant), pour ne plus jamais perdre cette information silencieusement. Ce bug masquait à son tour une vraie lacune RGPD : `MemoryManager.forget()` n'effaçait jamais l'episode store vectoriel (Chroma ou local), seulement la base relationnelle — un épisode « oublié » restait retrouvable via une recherche par similarité de sens. `forget()` appelle désormais aussi `episode_store.delete_matching(...)`. Tests : `tests/unit/test_chroma_telemetry.py`, `tests/unit/test_episode_vector_store.py::test_get_episode_store_logs_warning_when_falling_back_to_local`, `tests/unit/test_vector_store.py::test_get_fact_store_logs_warning_when_falling_back_to_local`, `tests/acceptance/test_memory.py::test_right_to_be_forgotten` (révèle la régression une fois Chroma réellement actif).

### Prévu (Chantiers)

- **Chantier 1** : Mémoire épisodique (conformité R1–R6, intégration Chroma + PostgreSQL)
- **Chantier 2** : Middleware garde-fous (traçage LangFuse, intégration guardrails-ai)
- **Chantier 3** : MLOps (seuils qualité, détection de régression, scoring CI)

---

## [0.2.0] — 2026-07-06

### Modifié

- **Architecture LLM** : Remplacement de `AzureLLM` + `AzureAIOpenAIApiChatModel` par `LangChainAdapter` encapsulant `AzureAIOpenAIApiChatModel` dans une chaîne LangChain Runnable
- **PromptTemplate** : Introduction de `langchain_core.prompts.PromptTemplate` pour la composition structurée des prompts (`{system}`, `{context}`, `{message}`)
- **Compatibilité ascendante** : Interface `LLM` (Protocol) conservée ; `agent.py` et les couches garde-fous/mémoire inchangés

### Détails techniques

- Chaîne LangChain Runnable prête pour une future intégration de middleware (LangFuse, guardrails-ai)
- Fallback EchoLLM vérifié ; tests d'acceptation métier passants
- Stratégie d'import : import différé (lazy) de `langchain_azure_ai` pour éviter la dépendance au SDK en mode hors ligne

---

## [0.1.1] — 2026-07-06

### Corrigé

- **Docker Compose** : Suppression de la ligne `image: velmo-v2` en conflit, qui provoquait des erreurs `pull access denied` lorsque `build: .` et un tag d'image explicite étaient tous deux déclarés ; Compose utilise désormais uniquement l'image construite localement
- **Script de seed** (`make seed`) : Correction d'une `ForeignKeyViolation` sur `escalations.order_id` causée par un flush SQLAlchemy non ordonné ; `sampledata.py` initialise désormais les données en deux phases — tables de base (`customers`, `products`, `variants`, `orders`) avec un `flush()` intermédiaire, puis tables dépendantes (`order_items`, `shipments`, `returns`, `refunds`, `escalations`) avec `commit()` final
- **Connexion Chroma** (`make chat`) : Correction de l'erreur `Could not connect to a Chroma server` ; `kb_store.py` parse désormais `CHROMA_URL` via `urlparse` et configure le client dynamiquement (`host`, `port`, `ssl`) au lieu d'un `host="chroma", port=8000` codé en dur ; ajout d'un repli robuste vers `LocalKB` en cas d'échec de connexion/import
- **Avertissement de télémétrie Chroma** : Suppression d'un avertissement bruyant non bloquant (`Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given`) causé par une incompatibilité de signature `posthog` ; ajout d'une implémentation no-op de télémétrie (`chroma_telemetry.py`) et désactivation de la télémétrie anonymisée dans la configuration du client Chroma

### Fichiers modifiés

- `docker-compose.yml`
- `src/velmo/sampledata.py`
- `src/velmo/kb_store.py`
- `src/velmo/chroma_telemetry.py` (nouveau)

---

## [0.1.0] — 2026-07-06

### Ajouté

- **Scaffolding du projet** : Agent de support boutique Velmo 2.0 (maillots de football collector)
- **Couche base de données** : Modèles SQLAlchemy (Order, Customer, Product, Return, Refund, ShipmentTracking)
- **Outils** : Routage déterministe pour les requêtes de commande, modifications (taille, adresse, annulation), retours, remboursements, vérification de stock, suivi d'expédition, recherche KB
- **Moteur de garde-fous** : Portes d'entrée/sortie (stub ; règles de blocage à implémenter au Chantier 2)
- **Gestionnaire de mémoire** : Historique de conversation et mémoire épisodique (stub ; intégration Chroma + PostgreSQL au Chantier 1)
- **Intégration LLM** : Azure AI Inference (`AzureLLM` avec `AzureAIOpenAIApiChatModel`), modèle Kimi-K2.6
- **Suite de tests** : Tests d'acceptation pour la logique métier (7/7 passants), stubs garde-fous/mémoire/MLOps
- **CI/CD** : Quality gate GitHub Actions (placeholder ; scoring à implémenter au Chantier 3)
- **Documentation** : `reco_expert.md` (recommandations expertes), CLAUDE.md (charte du projet)

### Stack

- **Langage** : Python 3.11+ avec le gestionnaire de paquets `uv`
- **Base de données** : PostgreSQL (ORM SQLAlchemy)
- **LLM** : Azure AI Inference + Kimi-K2.6
- **Mémoire** : Chroma (recherche vectorielle) + PostgreSQL (état)
- **Tests** : pytest avec intégration langsmith
- **Linting** : ruff
</content>
</invoke>
