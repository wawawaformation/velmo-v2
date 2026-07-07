# Changelog

Toutes les modifications notables de Velmo 2.0 sont documentées ici.

Le format s'inspire de [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Ajouté

- **Garde-fous (Chantier 2)** : Implémentation complète des règles déterministes (v1) pour bloquer le contenu nuisible en entrée (haine/violence/sexuel, injection de prompt, hors périmètre) et en sortie (mêmes catégories + PII/secrets). Journalisation structurée via `GuardrailEvent` avec extraits tronqués (jamais la donnée brute). Note : la détection `secret_leak` (PII/secrets) s'applique à la fois à l'entrée et à la sortie, décision de conception documentée dans `conception/garde-fous/synthese.md`.

### Corrections

- **Fuite possible de donnée sensible dans les logs de garde-fous** : `_redact` tronquait l'extrait journalisé à 40 caractères sans masquer spécifiquement la donnée sensible ; un secret court (mot de passe, mention de clé API, etc.) situé en début de message aurait été journalisé tel quel dans `GuardrailEvent.excerpt_redacted`. Pour les catégories `pii` et `secret_leak` uniquement, `_log` journalise désormais un placeholder générique fixe (`[donnée sensible masquée]`) au lieu d'un extrait du texte réel — plus aucune donnée brute ne peut transiter par troncature, quelle que soit sa position dans le message. Comportement inchangé pour les autres catégories (hate/violence/sexual/prompt_injection/out_of_scope). Tests : `tests/unit/test_guardrail_engine.py::test_check_output_short_password_near_start_never_logged_verbatim` et `::test_check_input_short_secret_leak_near_start_never_logged_verbatim`.
- **Statut de commande en français** : `_format_order` (agent.py) traduit désormais le statut technique (`shipped`, `delivered`, etc.) en français (« expédiée », « livrée », etc.) via un mapping `_ORDER_STATUS_FR`, au lieu d'afficher la valeur brute de l'enum `OrderStatus`
- **Incompatibilité client/serveur Chroma** : `docker-compose.yml` utilisait `chromadb/chroma:latest` (serveur en v1.4.4), incompatible avec le client Python figé sur `chromadb>=0.5,<0.6` (`pyproject.toml`), causant un `KeyError: '_type'` lors de la création de la collection `velmo_faq` ; image serveur épinglée sur `chromadb/chroma:0.5.23`
- **`make seed-kb` depuis l'hôte** : le script `scripts/seed_kb.py` se connectait par défaut à `chroma:8000` (nom de service Docker, résoluble uniquement depuis le réseau Compose) ; `make seed-kb` fixe désormais `CHROMA_HOST=localhost CHROMA_PORT=8001` pour fonctionner depuis la machine hôte, cohérent avec `CHROMA_URL` dans `.env.example`

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
