# Livrables — Velmo 2.0

**Dépôt** : [github.com/wawawaformation/velmo-v2](https://github.com/wawawaformation/velmo-v2)
**Commit de référence** : `6665153`

Le code n'est pas dupliqué ici (source de vérité = le dépôt Git).

| Livrable | Où |
|---|---|
| Code — mémoire | [`src/velmo/memory/`](../src/velmo/memory/) |
| Code — garde-fous | [`src/velmo/guardrails/`](../src/velmo/guardrails/) |
| Code — MLOps | [`src/velmo/mlops/`](../src/velmo/mlops/) |
| Dossier de conception | [`conception/`](conception/) |
| Rapport de suivi | [`report.md`](report.md) |
| Preuve des tests d'acceptance | [`preuve_tests_acceptance.md`](preuve_tests_acceptance.md) |
| Historique détaillé | [`docs/CHANGELOG.md`](../docs/CHANGELOG.md) |

`main` n'a pas été développée séparément de `dev` (contrainte de temps) —
détail dans le CHANGELOG.

Build Docker, déploiement staging/prod et Langfuse ne sont pas implémentés :
bloqués par une même décision externe non tranchée (cible de déploiement) —
détail dans le CHANGELOG.
