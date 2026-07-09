# Évolution — Consolidation épisodique → sémantique

*Ce document ne remplace pas `choix.md` (fiche de conception initiale du
cours, laissée intacte comme trace historique). Il documente une évolution de
doctrine ultérieure, adoptée après coup.*

---

## Ce qui change

**Avant** (`choix.md`, § R2 et « Mécanisme transverse ») : classification
**directe**. Un LLM lit un message en attente et le route immédiatement vers
une seule destination mutuellement exclusive — `semantic_column`,
`semantic_vector`, `episodic`, ou `none`.

**Après** (ce document) : modèle à **consolidation**, aligné sur le skill
`semantic-episodic-memory` (cours). Tout message est **toujours** capturé en
épisodique (nettoyage léger, vocabulaire préservé). Le même appel LLM détecte
en plus, si présent, un fait sémantique généralisable — celui-ci est alors
**consolidé** en plus de l'épisode, pas à sa place.

## Pourquoi ce changement

Le skill du cours distingue explicitement les deux mémoires par leur nature :
- **épisodique** = « que s'est-il passé ? » (événement, daté, contextuel)
- **sémantique** = « qu'est-ce qui est vrai ? » (connaissance généralisable,
  indépendante du contexte)

et prescrit qu'une connaissance sémantique **résulte d'une consolidation**
d'épisodes, jamais d'un classement immédiat en parallèle. La classification
directe de `choix.md` contredisait ce principe : un fait comme « ma pointure
c'est du 43 » partait en `semantic_column` sans jamais transiter par
l'épisodique — aucune trace de l'échange d'origine n'était conservée.

## Ce qui reste vrai de `choix.md`

- Capture synchrone / traitement asynchrone (`MessageBrut`, scheduler
  périodique) : inchangé.
- Isolation stricte par `user_id` : inchangée.
- Un seul appel LLM par message (pas de latence supplémentaire) : préservé —
  la consolidation se fait dans le même appel que le nettoyage épisodique.
- Repli déterministe sans LLM : préservé (`_consolidate_with_rules`).

## Ce qui change concrètement

| Aspect | `choix.md` (avant) | Ce document (après) |
|---|---|---|
| Destination d'un message | Une seule, mutuellement exclusive | Épisode toujours + fait sémantique optionnel en plus |
| Trace de l'échange d'origine | Perdue si routé en sémantique | Conservée (épisode source, marqué `consolidated`) |
| Source de vérité pour la lecture (`read()`) | Directement la destination unique | Le fait sémantique consolidé (l'épisode source est exclu de la lecture par défaut, filtré `consolidated=False`) |
| Oubli (R5) | Un seul emplacement à purger | Fait sémantique **et** épisode source lié (`consolidated_key`), tous deux purgés par `forget()` |
| Traçabilité (R6) | `inspect()` liste faits + épisodes séparément | `inspect()` peut en plus retracer quel épisode a produit quel fait (`consolidated_key`) |

## Implémentation

- `src/velmo/memory/consolidation.py` — `consolidate(message, llm) -> ConsolidationResult`
  (épisode nettoyé + fait sémantique optionnel, un seul appel LLM).
- `src/velmo/db.py` — `MemoryEpisode.consolidated` / `.consolidated_key`
  (migration Alembic `0002_episode_consolidation`).
- `src/velmo/memory/episodic.py` — `list_episodes`/`search_episodes` excluent
  les épisodes consolidés par défaut (`include_consolidated=False`) ;
  `delete_by_consolidated_key` pour l'oubli ciblé.
- `src/velmo/memory/processor.py` — `process_pending` appelle `consolidate()`
  au lieu de l'ancien `classify_and_distill` ; écrit toujours l'épisode, route
  en plus le fait sémantique si présent.
- `src/velmo/memory/__init__.py` — `MemoryManager.forget()` purge aussi
  l'épisode source d'un fait consolidé via `consolidated_key`.

Tests : `tests/unit/test_consolidation.py`, `tests/unit/test_episodic.py`,
`tests/unit/test_processor.py`, et `tests/acceptance/test_memory.py`
(`test_forget_removes_consolidated_episode_even_without_text_match`).

## Référence

Skill `semantic-episodic-memory` (cours) — voir aussi
[`docs/presentation_memoire.md`](../../docs/presentation_memoire.md) pour la
présentation orale mise à jour de ce flux.
