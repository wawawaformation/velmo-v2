# Changelog

All notable changes to Velmo 2.0 are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned (Chantiers)
- **Chantier 1** : Mémoire épisodique (R1–R6 conformance, Chroma + PostgreSQL integration)
- **Chantier 2** : Middleware guardrails (LangFuse tracing, guardrails-ai integration)
- **Chantier 3** : MLOps (quality gates, regression detection, CI scoring)

---

## [0.2.0] — 2026-07-06

### Changed
- **LLM Architecture** : Replaced `AzureLLM` + `AzureAIOpenAIApiChatModel` with `LangChainAdapter` wrapping `AzureAIOpenAIApiChatModel` in a LangChain Runnable chain
- **PromptTemplate** : Introduced `langchain_core.prompts.PromptTemplate` for structured prompt composition (`{system}`, `{context}`, `{message}`)
- **Backward Compatibility** : Maintained Protocol `LLM` interface; `agent.py` and guardrails/memory layers unchanged

### Technical Details
- LangChain Runnable chain ready for future middleware integration (LangFuse, guardrails-ai)
- EchoLLM fallback verified; business acceptance tests passing
- Import strategy: lazy import of `langchain_azure_ai` to avoid SDK dependency in offline mode

---

## [0.1.0] — 2026-07-06

### Added
- **Project Scaffolding** : Velmo 2.0 boutique support agent (football shirts collector)
- **Database Layer** : SQLAlchemy models (Order, Customer, Product, Return, Refund, ShipmentTracking)
- **Tools** : Deterministic routing for order queries, modifications (size, address, cancellation), returns, refunds, stock checks, shipment tracking, KB search
- **Guardrails Engine** : Input/output gates (stub; blocking rules to be implemented in Chantier 2)
- **Memory Manager** : Conversation history and episodic memory (stub; Chroma + PostgreSQL to be integrated in Chantier 1)
- **LLM Integration** : Azure AI Inference (`AzureLLM` with `AzureAIOpenAIApiChatModel`), Kimi-K2.6 model
- **Test Suite** : Acceptance tests for business logic (7/7 passing), guardrails/memory/MLOps stubs
- **CI/CD** : GitHub Actions quality gate (placeholder; scoring to be implemented in Chantier 3)
- **Documentation** : `reco_expert.md` (expert recommendations), CLAUDE.md (project charter)

### Stack
- **Language** : Python 3.11+ with `uv` package manager
- **Database** : PostgreSQL (SQLAlchemy ORM)
- **LLM** : Azure AI Inference + Kimi-K2.6
- **Memory** : Chroma (vector search) + PostgreSQL (state)
- **Testing** : pytest with langsmith integration
- **Linting** : ruff

