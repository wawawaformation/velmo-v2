# Ressource — piloter GitHub en ligne de commande (`gh`)

Mémo pratique du CLI GitHub, orienté **ce projet** : suivre la CI sans quitter
le terminal, diagnostiquer un run rouge, gérer les secrets, ouvrir une PR.

Toutes les commandes ci-dessous ont été utilisées en conditions réelles sur
`velmo-v2` (version testée : `gh 2.45.0`).

> **Pourquoi c'est utile** : lire les logs d'un run dans le navigateur oblige à
> cliquer dans 4 écrans. En CLI, on filtre 3000 lignes de log avec un `grep` et
> on récupère la conclusion d'une étape précise en une commande.

---

## 0. Vérifier son authentification

```bash
gh --version
gh auth status          # doit afficher "Logged in to github.com as <toi>"
```

Si besoin : `gh auth login` (choisir HTTPS + authentification par navigateur).

`gh` détecte automatiquement le dépôt à partir du dossier courant (via le
remote git) — pas besoin de préciser `--repo` tant qu'on est dans `velmo-v2/`.

---

## 1. Suivre la CI

### Lister les runs

```bash
# Les 5 derniers runs de la branche dev
gh run list --branch dev --limit 5

# Tous les runs récents, toutes branches
gh run list --limit 15
```

Colonnes : statut, conclusion, titre du commit, workflow, branche, événement,
**identifiant du run**, durée, date.

### Suivre un run en direct

```bash
gh run watch <RUN_ID> --exit-status
echo "code retour = $?"
```

- Rafraîchit l'affichage jusqu'à la fin du run.
- `--exit-status` fait que la commande **échoue** (code ≠ 0) si le run échoue —
  indispensable pour enchaîner (`gh run watch ... && echo OK`).

### Voir le détail et les logs

```bash
gh run view <RUN_ID>              # étapes, conclusions, annotations
gh run view <RUN_ID> --log        # log complet (très volumineux)
gh run view <RUN_ID> --log-failed # uniquement les étapes en échec
```

En pratique on filtre presque toujours :

```bash
gh run view <RUN_ID> --log | grep -E "passed|failed|error"
```

### Relancer sans re-pousser

```bash
gh run rerun <RUN_ID>              # relance tout
gh run rerun <RUN_ID> --failed     # relance seulement les jobs en échec
```

Très utile après avoir **corrigé un secret** : les secrets sont lus à
l'exécution, donc un simple `rerun` suffit — inutile de créer un commit vide.

---

## 2. Sortie structurée (`--json` / `--jq`) — le vrai gain

C'est ce qui permet d'extraire une information précise au lieu de lire à l'œil.

```bash
# Récupérer l'ID du dernier run de dev, sans le lire à la main
gh run list --branch dev --limit 1 --json databaseId --jq '.[0].databaseId'

# Conclusion globale d'un run
gh run view <RUN_ID> --json conclusion --jq '.conclusion'

# Conclusion de chaque étape qui nous intéresse
gh run view <RUN_ID> --json jobs \
  --jq '.jobs[].steps[] | select(.name|test("MLOps|Test suite")) | .name + " → " + .conclusion'

# Liste compacte : date, branche, statut, titre
gh run list --limit 10 --json createdAt,headBranch,conclusion,displayTitle \
  --jq '.[] | "\(.createdAt) \(.headBranch) \(.conclusion) \(.displayTitle)"'
```

Pour découvrir les champs disponibles : `gh run view --json` (sans valeur)
affiche la liste complète.

### Le pattern complet, réutilisable

```bash
RID=$(gh run list --branch dev --limit 1 --json databaseId --jq '.[0].databaseId')
echo "run = $RID"
gh run watch "$RID" --exit-status; echo "EXIT=$?"
gh run view "$RID" --json jobs \
  --jq '.jobs[].steps[] | .name + " → " + .conclusion'
```

---

## 3. Artefacts

Le workflow publie `mlops/report.md` en artefact (`mlops-report`) :

```bash
gh run download <RUN_ID>                      # tous les artefacts, dans le dossier courant
gh run download <RUN_ID> -n mlops-report      # un seul, par son nom
```

Pratique pour récupérer le rapport d'évaluation d'un run passé sans passer par
le navigateur.

---

## 4. Secrets et variables

Les secrets Azure du projet ont été saisis via l'interface web ; en CLI :

```bash
gh secret list                                  # noms + date de MAJ (jamais les valeurs)
gh secret set AZURE_AI_INFERENCE_MODEL          # demande la valeur en interactif (pas d'historique shell)
gh secret set AZURE_AI_INFERENCE_API_KEY < cle.txt   # depuis un fichier
gh secret delete NOM_DU_SECRET
```

**Secret ou variable ?** Un *secret* est chiffré et masqué dans les logs (clé
d'API). Une *variable* est en clair et **lisible dans les logs** — adapté à ce
qui n'est pas sensible (nom de modèle, URL d'endpoint) :

```bash
gh variable list
gh variable set AZURE_AI_INFERENCE_MODEL --body "gpt-5.4"
```

> **Retour d'expérience** : mettre le nom du modèle en *secret* le masque dans
> les logs (`***`), ce qui complique le diagnostic quand on cherche justement à
> vérifier quelle valeur la CI utilise. Une *variable* aurait été plus adaptée.

---

## 5. Workflows

```bash
gh workflow list                       # workflows du dépôt
gh workflow view quality               # détail d'un workflow
gh workflow run quality --ref dev      # déclenchement MANUEL
```

⚠️ `gh workflow run` exige que le workflow déclare le déclencheur
`workflow_dispatch` :

```yaml
on:
  push:
    branches: [dev, main]
  workflow_dispatch:      # ← rend le déclenchement manuel possible
```

Intéressant ici : l'évaluation réelle est lente et coûteuse (appels Azure). La
passer en déclenchement manuel évite de la subir à chaque push.

---

## 6. Pull requests

Pour la future PR `dev → main` :

```bash
gh pr create --base main --head dev --title "..." --body "..."
gh pr create --base main --head dev --fill      # reprend titre/corps des commits

gh pr list
gh pr view <NUM>                # détail
gh pr view <NUM> --web          # ouvrir dans le navigateur
gh pr checks <NUM>              # état des vérifications CI de la PR
gh pr diff <NUM>
gh pr merge <NUM> --squash      # ou --merge / --rebase
```

`gh pr checks` est le complément naturel de la doctrine « merge manuel après
review » : on vérifie que le gate qualité est vert avant d'approuver.

---

## 7. `gh api` — tout le reste

Quand une commande dédiée n'existe pas, l'API REST est accessible directement
(authentification gérée automatiquement) :

```bash
# Protection de branche (non exposée en commande dédiée)
gh api repos/:owner/:repo/branches/main/protection

# Consommation Actions du dépôt
gh api repos/:owner/:repo/actions/workflows

# Environments
gh api repos/:owner/:repo/environments
```

`:owner` et `:repo` sont résolus automatiquement depuis le dépôt courant.

---

## Aller plus loin — pistes non exploitées sur ce projet

Trois fonctionnalités GitHub qui prolongent des décisions **déjà prises** dans
`conception/LMOPS/chantier3-reponses.md` (Réponse 5) :

| Fonctionnalité | Ce qu'elle apporte ici |
|---|---|
| **Branch protection + required status checks** | La Réponse 5 pose « merge toujours manuel, PR + review ». Aujourd'hui c'est une intention ; GitHub peut l'**imposer** : interdire le push direct sur `main`, exiger le job `quality` vert avant merge. Le gate devient contraignant, plus consultatif. |
| **Environments** (Settings → Environments) | Trois branches → trois environnements. Porte des **secrets par environnement** (staging ≠ prod) et un **required reviewer** qui suspend le déploiement en attendant une approbation humaine — exactement la doctrine « automatiser la vérification, garder la décision humaine ». |
| **`workflow_dispatch`** | Déclencher l'évaluation coûteuse quand on le décide, au lieu de la subir à chaque push. |

Voir aussi : `gh <commande> --help` est complet et à jour — par exemple
`gh run --help`, `gh pr merge --help`.
