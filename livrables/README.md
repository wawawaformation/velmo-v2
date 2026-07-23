# Livrable — Code de Velmo 2.0

**Dépôt** : [github.com/wawawaformation/velmo-v2](https://github.com/wawawaformation/velmo-v2)

Le code n'est **pas dupliqué** dans ce dossier : une copie figée du code source
partirait en décalage dès le commit suivant, et le dépôt Git est déjà la
source de vérité versionnée (même principe que pour les schémas de
conception — un seul exemplaire fait foi).

**Commit de référence pour cette remise** : `6665153`
(`git checkout 6665153` pour revenir exactement à cet état).

## Emplacement des trois modules exigés

| Module | Chemin | Rôle |
|---|---|---|
| Mémoire | [`src/velmo/memory/`](../src/velmo/memory/) | Court terme (RAM), long terme sémantique (colonnes `User` + vectoriel Chroma), épisodique (relationnel + vectoriel), isolation par `user_id`, droit à l'oubli (`forget()` + outil conversationnel `forget_memory`) |
| Garde-fous | [`src/velmo/guardrails/`](../src/velmo/guardrails/) | Cascade entrée/sortie : règles regex → Azure AI Content Safety → classifieur LLM (`gpt-5.4-nano`) |
| MLOps | [`src/velmo/mlops/`](../src/velmo/mlops/) | 3 suites d'évaluation, note globale versionnée (`mlops/eval_manifest.yaml`), gate CI bloquant, rapport de suivi (`score.py`) |

## Tests associés

- `tests/unit/` — tests hors-ligne, déterministes
- `tests/acceptance/` — suite d'acceptance (mémoire, garde-fous, MLOps),
  y compris contre le vrai agent Azure (marqueur `pytest.mark.real_llm`)

Voir [`preuve_tests_acceptance.md`](preuve_tests_acceptance.md) pour la
preuve d'exécution.

## Rapport de suivi

Instantané réel (100 % sur les 3 suites) : [`report.md`](report.md).

## Dossier de conception

Schémas (aperçu JPG + sources éditables) : [`conception/`](conception/).

## Historique détaillé

Chaque décision, chaque bug trouvé et corrigé, chaque commit est documenté
dans [`docs/CHANGELOG.md`](../docs/CHANGELOG.md).

## Pourquoi `main` n'a pas été développée séparément

La stratégie de branches retenue en conception (`conception/LMOPS/chantier3-reponses.md`,
Réponse 5) prévoit `feature/* → dev → main`, avec un contrôle croissant à
chaque étape. En pratique, faute de temps disponible pour mener les deux
branches en parallèle, **tout le développement itératif (86 commits, TDD,
diagnostics, corrections de bugs) a été fait directement sur `dev`**, et
`main` n'a reçu qu'un unique merge de fond une fois ce travail validé.

Ce n'est pas un raccourci pris sans contrôle : avant ce merge, `dev` avait été
vérifiée intégralement — suite complète verte, éval réelle contre le vrai
agent Azure (mémoire/garde-fous/qualité à 100 %), gate CI qui bloque
effectivement une régression (constaté en conditions réelles, pas seulement
en test). Le merge lui-même s'est fait par pull request (revue explicite),
conformément à la doctrine « le merge est toujours manuel, jamais automatique »
posée dans la même Réponse 5.

La conséquence assumée : `main` ne bénéficie pas d'un historique de commits
granulaire qui lui soit propre (un seul commit de merge), et le développement
« par étages » (feature isolée → dev → main) décrit en conception n'a pas été
suivi à la lettre sur ce projet mené seul, dans le temps imparti.
