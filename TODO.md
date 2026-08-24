# Velmo 2.0 — Tâches restantes

**BLOCAGE CRITIQUE (2026-08-24)** : Agent down en production suite déploiement Langfuse. Voir `docs/CHANGELOG.md` section "Incident — Langfuse integration...".

---

## 🔴 URGENT — Rétablir le service (demain matin)

- [ ] Reverter commit `a52230c` (Langfuse) — identifier bug timeout/crash dans `_build_callbacks()` ou `Agent.respond()`
  - Audit code : LangfuseCallbackHandler initialization + network call blocking ?
  - Ou roll back + redeploy image `dev` sans Langfuse
  - Vérifier quand service est de nouveau stable

- [ ] Diagnostiquer pourquoi Azure ne peut pas pull `ghcr.io/wawawaformation/velmo-v2:dev`
  - Image existe (confirmé via `docker pull` local)
  - Logs Azure détaillés ? Network/firewall ? Credentials ?
  - Options de secours : Azure Container Registry, ou autre registry

- [ ] Une fois service stable : intégrer Langfuse **avec** error handling
  - Callback ne doit pas bloquer l'API
  - Doit time out/fail silencieusement si Langfuse down
  - Test timeout artificiel avant redeploy

---

## 🔴 Brief points 5-9 (Priorité 1 — critères de performance/livrables)

### Point 5 — Vérifier une conversation en ligne ✅
- [x] `POST /messages` réel contre `velmo-basic` — tool-calling + garde-fous actifs
- [x] Comportement correct sur un numéro de commande inventé (`owned_order()`)

### Point 6 — R2 (persistance) / R3 (isolation) en ligne ✅
- [x] Fait donné à `C-marc-dubois` (pointure 42), retrouvé dans une requête indépendante suivante
- [x] `C-emma-roux` interrogée sur la même info : aucun accès (isolation confirmée)

### Point 7 — Garde-fous et secrets en prod ✅
- [x] Injection de prompt (2 cas) et violence bloqués, bonne catégorie retournée
- [x] Cas légitime non bloqué (pas de faux positif), réponse fidèle à la FAQ
- [x] Aucun secret observé dans les réponses testées
- [ ] Vérifier la journalisation (`logs/guardrails.log` en prod — accessible comment ? via Log stream, pas encore fait)

### Point 8 — Signaux de suivi ✅ (voir `conception/deploiement/signaux-suivi.md`)
- [x] Relevé latence (9 messages, moyenne ≈ 5,6s hors démarrage à froid) + taux de blocage (3/9)
- [x] Log stream Azure consulté (pendant le debug déploiement)
- [ ] Coût : non mesurable via CLI sur cet abonnement de formation — capture "Analyse des coûts" du portail à faire manuellement (point 9)

### Point 9 — Documentation et présentation
- [x] Runbook « Déployer et exploiter Velmo 2.0 sur Azure » → `docs/runbook_deploiement_azure.md`
- [x] Capture du portail Azure montrant le groupe de ressources `dlegrandRG` → `docs/img/azure_deploiement.png`, intégrée au runbook
- [ ] Préparer présentation 5-10 min (agent en ligne, mémoire, garde-fous, signaux)

## 🟠 Nettoyage avant de considérer le déploiement "fini"

- [ ] Committer `scripts/seed_kb.py` (fix support HTTPS, déjà appliqué en local + Cloud Shell)
- [ ] Committer `conception/deploiement/reponses-deploiement.md` (statuts mis à jour)
- [ ] Job `promote-prod` dans `.github/workflows/cd.yml` (retag dev→main, jamais rebuild — Réponse 5)
- [ ] Automatiser l'étape de déploiement dans `cd.yml` (aujourd'hui fait manuellement en CLI)

---

## 🟡 MLOps Phase 2 (Priorité 2 — Post-déploiement)

### Monitoring en production
- [ ] Intégration LangFuse complète (POC effectué, branche `poc-langfuse`)
  - API key Cloud + réseau accessible depuis Azure
  - Décision : cloud vs self-hosted (RGPD ?)
  - Métriques : latence/coûts réels en prod

- [ ] Dashboard temps réel
  - Latence par appel
  - Coût par utilisateur (tokens consommés)
  - Taux d'erreur par catégorie garde-fou
  - Utilisation mémoire

- [ ] Alertes
  - Régression score < 80 %
  - Latence > seuil (ex. 5s)
  - Taux erreur > 5 %

### Amélioration suite d'évaluation
- [ ] Isoler suites (reset mémoire `C-marc-dubois` entre elles)
  - Actuellement : qualité polluée par mémoire antérieure (8/8 → 7/8)
  - Créer user distinct par suite OU purger mémoire entre runs

- [ ] Rejouer/vérifier non-déterminisme Azure + Chroma
  - Score parfois 96,25 %, parfois 100 % (Chroma ANN ?)
  - Décider si c'est acceptable ou à investiguer

---

## 🟠 Bug known fixes (Priorité 3 — Amélioration qualité)

### Concurrence SQLAlchemy
- [ ] Investiguer & corriger crash `InvalidRequestError` en parrallel tool-calling
  - Actuellement : non reproduit en CI, découvert localement
  - Options : session par outil / verrou / session par requête
  - **Impact** : rare, mais bloque `make eval` en local certains jours

### Contamination mémoire entre suites (test d'évaluation)
- [ ] Non-trivial : jeux de cas fournis (ne pas modifier)
  - Créer user distinct par suite OU
  - Reset Chroma/Postgres entre suites OU
  - Comparer sur même baseline (pollution mesurée avant/après)

---

## 🟢 Améliorations (Priorité 4 — Nice to have)

### Tests & couverture
- [ ] Acceptance tests API
  - Validation 422 sur payload incomplet
  - Tool-calling réel (mock tools ?)
  - Latence rapportée correctement
  - Catégorie garde-fou rapportée

- [ ] E2E tests déploiement
  - Staging : test tous les parcours métier
  - Prod : test par tenant (canary deploy ?)

### Frontend
- [ ] Historique de messages (actuellement : dernière réponse uniquement)
- [ ] Sélecteur utilisateur UI (actuellement : dropdown hors écran)
- [ ] Indicateur de confiance IA/fiabilité (mention source = FAQ vs général)

### Documentation
- [ ] Script déploiement Azure automatisé (`az cli`)
- [ ] Runbook incident (latence, 429, Chroma down, Postgres down)
- [ ] SLA/SLO pour production

---

## 📊 Checklist avant Go Live

- [ ] Postgres Flexible Server créé et testé (`make test` + `make eval` contre vrai Postgres)
- [ ] Chroma décidé & déployé
- [ ] Secrets GitHub créés
- [ ] Variables d'env Web App configurées (pas de hardcode)
- [ ] Job `promote-prod` implémenté
- [ ] Staging déployé & validé (tous parcours métier)
- [ ] LangFuse / monitoring décidé (cloud vs self-hosted)
- [ ] Logs collectés & alertes en place
- [ ] Plan rollback documenté
- [ ] On-call assigné pour les premières 48h
