# Livrables — Déploiement Velmo 2.0

## Pièces fournies pour le Brief 2

### 1. Conception (points 1-3)

| Fichier | Contenu | Correspond à |
|---|---|---|
| **reponses-deploiement.md** | Services Azure justifiés, liste secrets, plan mémoire | Brief 1-3 |
| **velmo2-deploiement-azure.drawio** | Schéma cible : utilisateur → App Service → LLM → mémoire | Brief point 3 |

### 2. Monitoring (point 8)

| Fichier | Contenu |
|---|---|
| **signaux-suivi.md** | Latence, coût, taux blocage garde-fous |

### 3. Exploitation (point 9 — runbook)

| Fichier | Contenu |
|---|---|
| **runbook_deploiement_azure.md** | Déployer, configurer secrets, domaine, vérifier, dépanner (étapes GUI) |

### 4. Preuves d'infrastructure (point 4 — capture portail)

| Fichier | Contenu |
|---|---|
| **azure_deploiement.png** | Capture portail Azure : groupe `dlegrandRG` avec toutes ressources |

## Ressources Azure (groupe `dlegrandRG`, France Central)

- **velmo-basic** (App Service) — Agent API (FastAPI + Uvicorn)
- **velmo-chroma** (App Service) — Mémoire vectorielle (Chroma)
- **velmo-pg** (PostgreSQL Flexible Server) — Mémoire relationnelle
- **velmo-kv** (Key Vault) — Secrets (`AZURE-AI-INFERENCE-API-KEY`, `DB-URL`)
- **velmostorageprod** (Storage Account) — Persistance Chroma
- **Static Web App** — Frontend Vue.js (`velmo-client.koabana.fr`)
- **Azure OpenAI** — Modèles `gpt-5.4` (chat) / `gpt-5.4-nano` (classifieur)

## Points clés

### Flux de déploiement

```
git push (dev/main)
  ↓
GitHub Actions (cd.yml, quality.yml)
  ↓
Image Docker construite + poussée sur ghcr.io
Frontend bundlé + déployé sur Static Web App
  ↓
Redémarrage manuel App Service velmo-basic nécessaire
  (Azure ne re-pull pas automatiquement le même tag)
```

### Vérification rapide

```bash
# API
curl https://velmo.koabana.fr/users

# Frontend
https://velmo-client.koabana.fr (bouton "Envoyer")

# Collection Bruno (test complet)
bruno/velmo-demo-cto/
```

### Incidents courants

Voir section 6 du runbook (`runbook_deploiement_azure.md`).

---

## URLs publiques

- **API Agent** : https://velmo.koabana.fr/users
- **Frontend** : https://velmo-client.koabana.fr (bouton "Envoyer" fonctionnel)
- **Dépôt GitHub** : https://github.com/wawawaformation/velmo-v2 (branche `dev`)

---

## Critères de performance validés

✅ Agent accessible publiquement via URL Azure  
✅ Mémoire long terme persistante d'une session à l'autre (**R2**)  
✅ Isolation stricte par utilisateur (**R3**)  
✅ Garde-fous validés en production (7 catégories, traçabilité)  
✅ Aucun secret dans le code source (tous externalisés Key Vault)  
✅ Ressources regroupées groupe `dlegrandRG` (facile à retrouver/supprimer)  

---

**Livrable complet** : 2026-08-25
