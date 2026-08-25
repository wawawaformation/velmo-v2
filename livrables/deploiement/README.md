# Livrables — Déploiement Velmo 2.0

## Documentation opérationnelle

| Document | Contenu |
|---|---|
| **runbook_deploiement_azure.md** | Guide complet de déploiement et exploitation sur Azure |

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

**Dernière mise à jour** : 2026-08-25
