# Classification mémoire par LLM (Phi-4-mini-instruct)

## Contexte et problème

`classify_and_distill` (`src/velmo/memory/classifier.py`) route chaque message
brut (`message_brut`) vers sa destination mémoire (`semantic_column`,
`semantic_vector`, `episodic`, `none`) par des règles regex déterministes.

Bug découvert en usage réel : un message contenant plusieurs faits (ex.
« je fais du 42 en pointure, je préfère être contacté par mail et je parle
français ») ne fait extraire **qu'un seul fait** — `_extract_known_column`
s'arrête au premier motif qui matche (ordre fixe : tutoiement → segment →
langue → email → pointure), les autres faits du même message sont perdus
silencieusement.

Le traitement mémoire étant désormais asynchrone (scheduler APScheduler,
cf. `processor.py` et commit "Add real periodic scheduler"), la latence d'un
appel LLM n'impacte plus l'UX conversationnelle en direct. On peut donc
remplacer les règles par un LLM capable d'extraire tous les faits d'un
message en un seul appel, avec repli déterministe sur les règles existantes
en cas d'échec.

## Objectif

Remplacer `classify_and_distill` par une version pilotée par LLM qui :
- extrait **tous** les faits présents dans un message (0, 1 ou N),
- route chacun vers sa destination (`semantic_column` / `semantic_vector` /
  `episodic`),
- retombe sur les règles regex actuelles si le LLM échoue ou renvoie une
  sortie invalide (aucune exception ne doit remonter, aucun message perdu).

## Modèle utilisé

Un modèle dédié, distinct du LLM de conversation (Kimi-K2.6) : **Phi-4-mini-instruct**,
un petit modèle adapté à une tâche d'extraction structurée simple.

Variables d'environnement (`.env` / `.env.example`) :
```
AZURE_AI_INFERENCE_ENDPOINT=...     # réutilisé (même endpoint)
AZURE_AI_INFERENCE_API_KEY=...      # réutilisé (même clé)
AZURE_AI_CLASSIFIER_MODEL=Phi-4-mini-instruct
```

## Architecture

### `src/velmo/llm.py`

Nouvelle fonction `get_classifier_llm() -> LLM`, miroir de `get_llm()` :
- si `AZURE_AI_CLASSIFIER_MODEL` n'est pas défini ou pas d'endpoint Azure
  configuré → `EchoLLM()` (repli hors-ligne, comme `get_llm()`),
- sinon → `LangChainAdapter` configuré avec le modèle `AZURE_AI_CLASSIFIER_MODEL`,
  même endpoint/clé que `get_llm()`.

### `src/velmo/memory/classifier.py`

Signature actuelle : `classify_and_distill(message: str) -> ClassificationResult`

Nouvelle signature : `classify_and_distill(message: str, llm: LLM | None = None) -> list[ClassificationResult]`

- **`llm=None`** (défaut) : comportement 100% règles actuel (`_extract_known_column`
  + hints épisodiques/vectoriels), remballé dans une liste (0 ou 1 élément).
  Utilisé par les tests existants et comme filet de secours.
- **`llm` fourni** : tente `_classify_with_llm(message, llm)` :
  1. construit un prompt système décrivant le schéma de sortie JSON attendu
     et les clés connues (`KNOWN_KEYS` de `semantic.py`),
  2. appelle `llm.invoke(system, "", message)`,
  3. parse la réponse : extrait le premier bloc `[...]` (tolérant au texte
     parasite autour du JSON), `json.loads`,
  4. valide chaque élément (`destination` ∈ `{semantic_column, semantic_vector,
     episodic, none}` ; si `semantic_column`, `key` ∈ `KNOWN_KEYS`),
  5. toute erreur (réseau, JSON globalement non parsable) est capturée
     localement → retourne `None` (signal d'échec, fallback sur tout le message).
  - Si un élément individuel de la liste est invalide (destination inconnue,
    ou `semantic_column` avec `key` hors `KNOWN_KEYS`) alors que le reste du
    JSON est valide, cet élément est ignoré seul — les autres éléments valides
    du même message sont conservés (pas de fallback total pour une erreur
    partielle).
  - Si `_classify_with_llm` retourne `None` (échec global) → repli sur les
    règles (liste).
  - Sinon → la liste des éléments valides est retournée.

Aucune exception ne doit être levée hors de `classify_and_distill` pour une
cause liée au LLM (réseau, parsing) : le pire cas est un repli vers les règles.

### `src/velmo/memory/processor.py`

`process_pending` appelle désormais `classify_and_distill(row.contenu,
llm=get_classifier_llm())` et itère sur la liste de résultats :

```python
for row in rows:
    results = classify_and_distill(row.contenu, llm=get_classifier_llm())
    for result in results:
        if result.destination == "semantic_column" and result.key and result.value:
            semantic.set_known_fact(session, user_id, result.key, result.value)
        elif result.destination == "semantic_vector" and result.value:
            store.add(user_id, result.key or "fait", result.value)
        elif result.destination == "episodic" and result.value:
            episodic.add_episode(session, user_id, result.value)
```

## Tests

- Tests d'acceptance existants (`tests/acceptance/test_memory.py`) inchangés :
  ils passent par `remember_fact`/`run_pending_job`, qui n'injectent pas de
  LLM → restent sur le chemin règles déterministes, pas de dépendance réseau
  ni de flakiness ajoutée à la suite existante.
- Nouveaux tests unitaires pour `classify_and_distill` (fichier à créer,
  ex. `tests/unit/test_classifier.py`) avec un `FakeLLM` :
  - JSON multi-faits valide (le cas pointure + email + langue découvert en
    usage réel) → vérifie que les 3 faits sont extraits et routés
    correctement, pas seulement le premier.
  - JSON invalide / texte non parsable → vérifie le repli vers les règles
    (résultat identique à `classify_and_distill(message, llm=None)`).
  - Réponse LLM avec un mélange d'éléments valides et d'un élément à
    `destination`/`key` invalide → vérifie que l'élément invalide est ignoré
    seul et que les éléments valides du même message sont conservés (pas de
    fallback total), sans exception.

## Hors périmètre

- Pas de changement du protocole `LLM` (`invoke(system, context, message) -> str`)
  ni de structured output natif Azure/LangChain — le parsing JSON reste manuel
  et tolérant, dans `classifier.py` uniquement.
- Pas de traitement par batch (un appel LLM par message, comme aujourd'hui).
- Pas de logging/observabilité ajoutée sur les échecs de fallback (déjà identifié
  comme point de vigilance séparé, cf. le fallback silencieux de `kb_store.get_kb`).
