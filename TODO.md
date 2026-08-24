# Velmo 2.0 — Tâches restantes

**Priorité** : Suivre le brief `conception/deploiement/brief2.md`, points 5-9
(conception + provisioning déjà validés, points 1-4)

---

## 🔴 Brief points 5-9 (Priorité 1 — critères de performance/livrables)

### Point 5 — Vérifier une conversation en ligne
- [ ] `POST /messages` réel contre `velmo-basic` (pas juste `/users`/`/openapi.json`)
  - Vérifier tool-calling (ex. statut de commande, stock)
  - Vérifier qu'aucun secret/config n'apparaît dans la réponse

### Point 6 — R2 (persistance) / R3 (isolation) en ligne
- [ ] Envoyer un fait en session 1 (`user_id` A), vérifier qu'il est retrouvé en session 2
- [ ] Vérifier qu'un `user_id` B n'a **aucun accès** aux faits de A

### Point 7 — Garde-fous et secrets en prod
- [ ] Rejouer un message à bloquer (haine/violence), une injection de prompt, un cas PII en sortie
- [ ] Vérifier le blocage + la journalisation (`logs/guardrails.log` — accessible comment en prod ? via Log stream)
- [ ] Confirmer qu'aucun secret n'est exposé dans une réponse ou une page

### Point 8 — Signaux de suivi
- [ ] Relevé : latence par conversation, coût indicatif, taux de blocage garde-fous
- [ ] Consulter/exporter le Log stream Azure (déjà utilisé pour le debug déploiement)

### Point 9 — Documentation et présentation
- [ ] Runbook « Déployer et exploiter Velmo 2.0 sur Azure » (`docs/` ou `conception/deploiement/`)
- [ ] Capture du portail Azure montrant le groupe de ressources `dlegrandRG`
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
