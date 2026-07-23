# Livrables — Velmo 2.0

Instantané figé des 4 livrables exigés par le brief, au commit `6665153`
(`dev`) / `f35d640` (merge vers `main`). Ce dossier n'est **pas synchronisé
en continu** avec le code vivant — c'est une remise à un instant T, à
actualiser manuellement lors d'une prochaine étape significative.

## 1. Dossier de conception → [`conception/`](conception/)

Chaque schéma est fourni en `.jpg` (aperçu direct, sans installation de
draw.io). Sources `.drawio` éditables dans le dépôt vivant, sous
[`conception/`](../conception/) (non dupliquées ici — cf. `code/README.md`
sur le même principe pour le code).

| Pièce exigée | Aperçu | Source éditable |
|---|---|---|
| Schéma d'architecture global | [`velmo2-pipeline-global_reel.jpg`](conception/velmo2-pipeline-global_reel.jpg) | [`conception/velmo2-pipeline-global_reel.drawio`](../conception/velmo2-pipeline-global_reel.drawio) |
| Modèle de données de la mémoire | [`velmo2-modele-memoire.jpg`](conception/velmo2-modele-memoire.jpg) (cible) + [`velmo2-modele-memoire_reel.jpg`](conception/velmo2-modele-memoire_reel.jpg) (réel) | [`conception/memoire/flux.drawio`](../conception/memoire/flux.drawio) + [`flux_reel.drawio`](../conception/memoire/flux_reel.drawio) |
| Tableau des garde-fous | [`velmo2-garde-fous-schema.jpg`](conception/velmo2-garde-fous-schema.jpg) (cible) + [`velmo2-garde-fous-flux-reel.jpg`](conception/velmo2-garde-fous-flux-reel.jpg) (réel) | [`conception/garde-fous/velmo2-garde-fous-schema.drawio`](../conception/garde-fous/velmo2-garde-fous-schema.drawio) + [`velmo2-garde-fous-flux-reel.drawio`](../conception/garde-fous/velmo2-garde-fous-flux-reel.drawio) |
| Schéma de la boucle qualité | [`velmo2-boucle-qualite_reel.jpg`](conception/velmo2-boucle-qualite_reel.jpg) | [`conception/LMOPS/velmo2-boucle-qualite_reel.drawio`](../conception/LMOPS/velmo2-boucle-qualite_reel.drawio) |

Convention `X.drawio` / `X_reel.drawio` : la version cible est la conception
initiale (avant code), la version `_reel` documente ce qui a été
effectivement constaté après implémentation — l'écart entre les deux est
volontairement conservé, pas masqué (ex. le garde-fou PII visait Azure
Language PII redaction en cible, remplacé par un regex applicatif en réel
après un faux positif documenté dans `conception/garde-fous/synthese.md`).

**Note sur la validation formateur** : je ne peux pas attester ici que ce
dossier a été formellement validé avant le début du code — c'est un fait
externe au dépôt.

## 2. Code de Velmo 2.0 → [`code/README.md`](code/README.md)

Référence au dépôt (commit exact), pas de copie de fichiers sources —
dupliquer du code vivant part en décalage dès le commit suivant.

## 3. Rapport de suivi → [`report.md`](report.md)

Instantané réel : mémoire 100 %, garde-fous 100 %, qualité 100 %, note globale
100 % — issu du run CI qui a validé le merge vers `main`
([run 29906194048](https://github.com/wawawaformation/velmo-v2/actions/runs/29906194048)).

Le fichier vivant (régénéré à chaque exécution) est
[`mlops/report.md`](../mlops/report.md), désormais versionné en Git — voir
`docs/CHANGELOG.md` pour la politique de mise à jour (commit manuel à chaque
merge significatif vers `main`, pas par la CI elle-même).

## 4. Preuve d'exécution des tests d'acceptance → [`preuve_tests_acceptance.md`](preuve_tests_acceptance.md)

Sortie complète de la suite hors-ligne (195 tests, capturée en local) +
référence au run CI de la suite contre le vrai agent Azure (3 critères
Gherkin du chantier 3, tous verts).

## Limites connues, non résolues à ce stade

- **Coût par conversation** dans `mlops/report.md` : placeholder `0.0`,
  en attente de l'intégration Langfuse (elle-même en attente de la décision
  de cible de déploiement — cloud ou auto-hébergé, question RGPD).
- **Contamination entre suites d'évaluation** : un même client de test
  (`C-marc-dubois`) est utilisé par la suite mémoire et la suite qualité,
  ce qui peut légèrement sous-estimer la note qualité isolée.
- **`main` non développée séparément** de `dev` — voir
  [`code/README.md`](code/README.md#pourquoi-main-na-pas-été-développée-séparément)
  pour le détail et la justification.
- **Bug de concurrence découvert, non corrigé** : `sqlalchemy.exc.InvalidRequestError`
  observé en local lors d'appels d'outils parallèles (session SQLAlchemy
  partagée) — voir `docs/CHANGELOG.md`.
