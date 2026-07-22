# AGENTS.md — Guide des Agents Velmo 2.0

Documentation de l'architecture d'agents et du framework LangGraph utilisé.

---

## Vue d'ensemble

Velmo 2.0 utilise **LangChain 1.3+ avec LangGraph** pour implémenter un agent IA conversationnel. L'agent est construit via `create_agent()` et amélioré par deux middlewares : `GuardrailMiddleware` et `MemoryMiddleware`.

### Contrat public

```python
from velmo.agent import build_default_agent

agent = build_default_agent()
reply = agent.respond(user_id="C-123", message="Quel est le statut de ma commande ?")
```

- **Entrée** : `user_id` (isolation) + `message` (requête utilisateur)
- **Sortie** : `str` (réponse textuelle, jamais None)
- **Contrat de latence** : aucune garantie temporelle, peut aller de 500ms à plusieurs secondes (dépend Azure)

---

## Architecture interne

### Graphe LangGraph (`create_agent()`)

```
┌─────────────────────────────────────────────┐
│ Agent = LangGraph compilé                   │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ Nœud: router                         │  │
│  │ - Lit le message utilisateur          │  │
│  │ - Décide : appeler outil ou répondre │  │
│  └──────────────────────────────────────┘  │
│                    │                        │
│          ┌─────────┴─────────┐             │
│          ▼                   ▼             │
│  ┌──────────────┐   ┌──────────────┐     │
│  │ Tool nodes   │   │ LLM response │     │
│  │ (get_order,  │   │              │     │
│  │  cancel, …)  │   │ gpt-5.4      │     │
│  └──────────────┘   └──────────────┘     │
│                                             │
└─────────────────────────────────────────────┘
```

**Points clés** :
- Le LLM (Kimi-K2.6 devenu gpt-5.4) décide si appeler un outil ou renvoyer une réponse directe
- Pas de boucle fixe : LLM peut itérer (appel outil → lecture résultat → nouvelle décision)
- Instruction de confirmation mono-message encodée dans le system prompt

### Middlewares

#### 1. GuardrailMiddleware

Contrôle entrée/sortie en 3 niveaux :

```python
GuardrailMiddleware.before_agent()
  ├─ Règles regex (moderation.py, prompt_injection.py, scope.py, pii.py)
  ├─ Azure Content Safety (content_safety.py)
  └─ LLM classifier (moderation_llm.py, gpt-5.4-nano)
```

- **before_agent** : bloque l'entrée → `jump_to="end"` (court-circuite le graphe)
- **after_agent** : bloque la sortie → remplace le dernier message par le refus

**Comportement spécial `self_harm`** : ne refuse pas, redirige vers le **3114** (prévention suicide)

#### 2. MemoryMiddleware

Gère la mémoire à long terme (épisodique + sémantique) :

```python
MemoryMiddleware.before_agent()
  └─ memory.read(user_id, message)
     → cache du contexte mémoire en `state["memory_context"]`
     → injecté dans system_prompt à chaque appel LLM

MemoryMiddleware.wrap_model_call()
  └─ Ajoute memory_context au system_prompt du LLM

MemoryMiddleware.after_agent()
  └─ memory.write(user_id, message, reply)
     → capture le message + réponse en épisodique
     → détecte et consolide les faits sémantiques
```

**Isolation** : chaque utilisateur a sa propre mémoire isolée (R3)

---

## Outils métier

Tous liés via `binding.py` (fermeture Python) — `user_id`/`session` jamais exposés comme arguments au LLM.

| Outil | Signature exposée | Fichier | Rôle |
|-------|-------------------|---------|------|
| `get_order` | `order_id: str` | `src/velmo/tools/get_order.py` | Récupérer le statut d'une commande |
| `cancel_order` | `order_id: str` | (pending) | Annuler une commande |
| `check_stock` | `product_ref: str, size: str` | `src/velmo/tools/check_stock.py` | Vérifier la disponibilité |
| `search_kb` | `query: str` | `src/velmo/tools/search_kb.py` | Chercher dans la FAQ (ChromaDB) |
| (autres) | … | (pending) | … |

**Sécurité** : `owned_order()` reste le filet final (isolation client)

---

## System Prompt

Défini dans `src/velmo/agent.py::SYSTEM_PROMPT`.

### Sections clés

1. **Rôle** : Assistant de support pour boutique de maillots
2. **Périmètre** : commandes, retours, remboursements, FAQ
3. **Instruction de confirmation** : avant toute action modifiant une commande, demander confirmation et attendre intention + confirmation dans le même message
4. **Limitations** : pas d'escalade humaine (pas d'outil `escalate_to_human`), pas de PII manipulée hors protocole
5. **Format** : réponses en français, toujours courtois

**Important** : les garde-fous de contenu ne sont **pas** mentionnés ici (le LLM ne sait pas qu'il en existe). Ils agissent en-dessous du LLM, transparemment.

---

## Flux complet (exemple)

### Entrée utilisateur

```
User ID : "C-marc-dubois"
Message : "Je veux annuler ma commande O-2024-1234. Je confirme."
```

### 1. GuardrailMiddleware.before_agent()

- ✅ Passe les 3 niveaux (pas de contenu interdit)
- → Continuer

### 2. MemoryMiddleware.before_agent()

- Charge mémoire : "Marc préfère le tutoiement"
- Cache dans `state["memory_context"]`

### 3. Graphe LLM (create_agent)

- **Router lit** : "Je veux annuler ma commande O-2024-1234. Je confirme."
- **LLM décide** : Hmm, intention claire + confirmation présente → appeler `cancel_order("O-2024-1234")`
- **Tool exécute** : retourne `{"success": true, "status": "cancelled"}`
- **LLM répond** : "✅ C'est fait, ta commande est annulée. Tu recevras un remboursement sous 5-7 jours."

### 4. GuardrailMiddleware.after_agent()

- ✅ Réponse passe Content Safety
- → Valide

### 5. MemoryMiddleware.after_agent()

- Écrit en mémoire : Message + réponse
- Détecte fait sémantique : "Marc a annulé une commande" (consolidé)

### 6. Retour utilisateur

```json
{
  "reply": "✅ C'est fait, ta commande est annulée. Tu recevras un remboursement sous 5-7 jours.",
  "latency_ms": 2345.6,
  "guardrail_category": null
}
```

---

## Implémentation technique

### Fichiers clés

| Fichier | Rôle | État |
|---------|------|------|
| `src/velmo/agent.py` | `Agent` class, `build_default_agent()`, `create_agent()` | ✅ |
| `src/velmo/tools/binding.py` | `bound_tools(session, user_id, kb)` | ✅ |
| `src/velmo/guardrails/middleware.py` | `GuardrailMiddleware` | ✅ |
| `src/velmo/memory/middleware.py` | `MemoryMiddleware` | ✅ |
| `src/velmo/llm.py` | `get_chat_model()`, `LatencyCallbackHandler` | ✅ |

### Tests associés

| Test | Fichier | Couverture |
|------|---------|-----------|
| Tool binding (schema, isolation) | `tests/unit/test_tool_binding.py` | ✅ |
| Guardrail middleware | `tests/unit/test_guardrail_middleware.py` | ✅ |
| Memory middleware | `tests/unit/test_memory_middleware.py` | ✅ |
| Graphe agent (bout-en-bout) | `tests/acceptance/test_agent_graph.py` | ✅ |
| Business (fabulation, confirmation) | `tests/acceptance/test_business.py` | ✅ |

---

## Exigences pour utiliser l'agent

### Environnement

```bash
# Requis
AZURE_AI_INFERENCE_ENDPOINT=https://...
AZURE_AI_INFERENCE_API_KEY=...
AZURE_AI_INFERENCE_MODEL=gpt-5.4

# Optionnel (garde-fous)
AZURE_AI_CLASSIFIER_MODEL=gpt-5.4-nano
AZURE_CONTENT_SAFETY_ENDPOINT=https://...
VELMO_GUARDRAILS_LLM_CASCADE=1

# Optionnel (mémoire)
CHROMA_URL=http://localhost:8001
```

### Infrastructure

- **PostgreSQL** : User, Session, MessageBrut, FaitSémantique, Épisode (migrations Alembic)
- **ChromaDB** : KB + stockage vectoriel mémoire (optionnel, fallback relationnel)
- **Azure** : LLM (gpt-5.4) + classifier (gpt-5.4-nano) + Content Safety

### Erreurs attendues

```python
# Sans identifiants Azure
RuntimeError: "Identifiants Azure requis pour démarrer l'agent"

# Timeout LLM
openai.APITimeoutError (géré dans CLI, renvoie message d'erreur)

# Base DB inaccessible
sqlalchemy.exc.OperationalError (crash intentionnel, pas de fallback)
```

---

## Différences avec une approche traditionnelle

### Avant (Agent._handle regex)

```python
if "commande" in message and "statut" in message:
    order_id = extract_order_id(message)  # regex
    reply = get_order(order_id)
    return f"Le statut de {order_id} est {reply}"
```

**Problèmes** : pas flexible, pas de contexte, messages rigides

### Après (create_agent + LLM)

```python
# LLM lit le message, décide d'appeler get_order si pertinent
# Réponse rédigée librement selon le résultat
# Mémoire capturée automatiquement
# Garde-fous appliqués transparemment
```

**Avantages** : flexible, contextuel, messages naturels, traçabilité

---

## Limitations connues

### Non testable hors-ligne

- **Flux de confirmation mono-message** : le respect de l'instruction "demander confirmation" dépend du LLM réel (Kimi-K2.6 avant, gpt-5.4 maintenant). Les tests hors-ligne utilisent un modèle scriptable → pas de vrai raisonnement. À vérifier manuellement contre Azure.

### Cascade LLM intermittente

- **gpt-5.4-nano** (classifieur) a un taux d'erreur de ~2.7% (benchmark multi-région sur 16 820 appels). Les garde-fous peuvent être lents (15s+ timeout). Variable `VELMO_GUARDRAILS_LLM_CASCADE=0` permet de désactiver ce niveau si trop instable.

### Pas de persistance session

- Chaque `Agent.respond()` crée une instance neuve (pas d'état partagé entre requêtes). Approprié pour une API REST (isolation, scalabilité), pas pour un client avec état long-term.

---

## Observabilité (MLOPS)

### Logs

```
logs/guardrails.log        # Décisions de garde-fous (REGEX|LLM, catégorie, extrait)
logs/llm_latency.log       # Latence de chaque appel LLM (modèle, ms)
logs/memory.log            # Lectures/écritures mémoire (faits consolidés, oublis)
```

### Tracing LangFuse (POC)

- Branch `poc-langfuse` : POC complet (traces, datasets, évaluation)
- Intégration Velmo pending (étape 2)

---

## À venir

- [ ] Tests pour les outils `cancel_order`, `refund_order`, etc. (pending)
- [ ] Monitoring prod : LLM-as-Judge, seuils qualité
- [ ] CI gate : éval mémoire/garde-fous/qualité avec seuils de blocage
- [ ] Self-healing : si garde-fou bloque, rejouer avec context différent (exploratory)

---

**Version** : Velmo 2.0 (Chantier 1-2 complétés, Chantier 3 phase 1 POC)
**Dernière mise à jour** : 2026-07-16
