# Velmo 2.0 — Cadrage projet

Agent de support pour une boutique de maillots de football collector.

L'objectif du projet est d'assurer un haut niveau de fiabilité sur trois axes :

- Mémoire
- Garde-fous
- Qualité mesurée en continu

---

## Stack technique imposée

### Langage et environnement

- Python
- Gestion des dépendances avec `uv`
- Toujours utiliser :
  - `uv sync`
  - `uv add`
- Ne jamais utiliser `pip install` directement

### LLM

- Azure AI Inference
- Modèle : **Kimi-K2.6**

### Persistance

#### État conversationnel et préférences utilisateur

- PostgreSQL
- Source de vérité durable par utilisateur

#### Mémoire long terme épisodique

- Chroma
- Recherche par similarité vectorielle

### Intégration continue

- GitHub Actions
- Seuil qualité bloquant

---

## Exigences non négociables

### 1. Mémoire exemplaire

Respect strict des exigences :

- R1
- R2
- R3
- R4
- R5
- R6

Notamment :

- gestion des longues conversations ;
- persistance multi-session ;
- isolation des utilisateurs ;
- gestion de la fenêtre de contexte ;
- oubli contrôlé ;
- traçabilité.

---

### 2. Garde-fous robustes

Contrôle :

- à l'entrée ;
- à la sortie.

Aucune catégorie interdite ne doit transiter :

- dans les requêtes utilisateur ;
- dans les réponses générées.

Les décisions de blocage doivent être traçables.

---

### 3. Qualité mesurée en continu

Chaque évolution doit démontrer l'absence de régression.

La CI doit être bloquante sous les seuils qualité définis.

---

## Principes d'architecture

### Isolation mémoire

Toutes les opérations mémoire doivent être strictement isolées par :

```text
user_id
```

Aucune fuite d'information entre utilisateurs n'est acceptable.

### Traçabilité

Les éléments suivants doivent être inspectables :

- écritures mémoire ;
- rappels mémoire ;
- décisions de garde-fous ;
- événements de blocage.

### Réduction du bruit

Le pipeline CI doit :

- bloquer les régressions critiques ;
- éviter les faux positifs ;
- produire des diagnostics exploitables.

---

## Conventions d'implémentation

### Code

- Code en anglais
- Commentaires en français

### Qualité

Maintenir des tests `pytest` pour :

- les parcours métier ;
- la mémoire ;
- les garde-fous ;
- les composants MLOps.

### Vérifications minimales

Avant tout commit :

```bash
ruff check .
```

Si applicable :

```bash
pytest
```

### Philosophie de développement

Favoriser :

- les changements minimaux ;
- les changements vérifiables ;
- les changements reproductibles.

Éviter :

- les refactorings non demandés ;
- la sur-ingénierie ;
- les modifications hors périmètre.

---

## Processus avant modification

Lire systématiquement :

- `docs/reco_expert.md`
- `conception/garde-fous/synthese.md`
- `conception/LMOPS/chantier3-reponses.md`
- `conception/memoire/choix.md`

avant toute modification significative du code.

---

## Mise à jour de l'historique

Toute modification notable du projet doit être documentée dans :

```text
docs/CHANGELOG.md
```

L'entrée doit décrire :

- ce qui a changé ;
- pourquoi ;
- les impacts éventuels ;
- les tests associés lorsque pertinent.
