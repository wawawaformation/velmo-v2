# Script de présentation — Velmo 2.0 en production (5-10 min, pair "CTO")

But : dérouler exactement les 4 éléments demandés par le brief
(`conception/deploiement/brief2.md`, point 9) — *"l'agent en ligne, la
persistance mémoire, les garde-fous et les signaux de suivi"* — devant un
pair qui joue le rôle de la CTO. Démo live via **Bruno**, contre l'agent
réellement déployé sur Azure (`https://velmo.koabana.fr`), pas en local.

Collection Bruno prête à l'emploi : `bruno/velmo-demo-cto/` (7 requêtes
numérotées dans l'ordre de la démo, environnement `azure` déjà configuré
avec `baseUrl = https://velmo.koabana.fr`).

**Durée cible : 8-9 min** (tient dans la fourchette 5-10 min du brief avec
de la marge pour les questions). Repères de coupe si besoin de raccourcir
à 5 min : sauter la requête 2 (redondante avec 4) et compresser la partie
signaux à l'oral sans montrer le fichier.

---

## Préparation (avant la présentation, pas devant la CTO)

1. Ouvrir Bruno → **Open Collection** → `bruno/velmo-demo-cto/`
2. Sélectionner l'environnement **azure** en haut à droite
3. Avoir un second onglet/fenêtre ouvert sur
   `conception/deploiement/signaux-suivi.md` (ou le portail Azure, onglet
   Log stream de `velmo-basic`, au choix)
4. Lancer une fois la requête 1 en avance pour vérifier que tout répond
   (évite un démarrage à froid de 40s pendant la vraie démo)

---

## 0. Intro (30s)

Dire : *"Velmo 2.0 est un agent de support pour une boutique de maillots
collector. Il devait tenir trois promesses non négociables : une mémoire
fiable, des garde-fous robustes, une qualité mesurée en continu. Ce qu'on
va vérifier maintenant, c'est que ces trois promesses tiennent une fois
l'agent réellement en ligne sur Azure — pas seulement en local."*

---

## 1. L'agent en ligne (1-2 min)

**Requête 1** (`GET /users`) : *"Voici le référentiel client, exposé
publiquement sur `velmo.koabana.fr` — un domaine personnalisé avec un vrai
certificat HTTPS, pas juste l'URL Azure par défaut."*

**Requête 2** (`POST /messages`, statut de commande) : *"Et voici une
vraie conversation, contre le vrai modèle Azure OpenAI (`gpt-5.4`), avec
un appel d'outil réel qui va lire la commande dans Postgres."*

→ Montrer la réponse : statut de la commande (le mot exact varie d'un
appel à l'autre — parfois traduit "préparée", parfois la valeur brute
"prepared" — le LLM rédige librement à partir du résultat de l'outil, ce
n'est pas un texte figé), total, adresse. Dire : *"Le contenu factuel vient
toujours de Postgres, seule la formulation change d'un appel à l'autre —
normal avec un LLM qui rédige la réponse, pas un template fixe."*

---

## 2. Persistance mémoire — R2 et R3 (2-3 min)

Dire : *"Deux exigences non négociables : un fait donné par un client doit
être retrouvé plus tard (persistance), et jamais visible par un autre
client (isolation). On les vérifie toutes les deux, en direct, avec de
vraies requêtes HTTP indépendantes — pas de session, pas de cookie."*

**Requête 3** : donner un fait à `C-marc-dubois` ("ma pointure est du
42"). *"J'envoie ça, et j'attends une trentaine de secondes — le temps que
la consolidation mémoire tourne en tâche de fond."*

*(pause ~20-30s — remplir avec l'explication du mécanisme : consolidation
épisodique → sémantique, Postgres pour les faits à clé connue, Chroma pour
le reste)*

**Requête 4** : reposer la question à `C-marc-dubois` dans une **nouvelle
requête**. → **"42"** revient. *"C'est une requête HTTP complètement
neuve, sans aucun état côté client — la seule façon que ça marche, c'est
que ce soit vraiment en base."*

**Requête 5** : même question, mais `user_id = C-emma-roux`. → L'agent
répond qu'il n'a pas cette information. *"Aucune fuite entre clients —
c'est le filtrage `WHERE user_id = ...` qui fait ça, vérifié ici en
conditions réelles, pas juste en test unitaire."*

---

## 3. Garde-fous en production (2 min)

Dire : *"Les garde-fous tournent en cascade — règles déterministes, Azure
Content Safety, puis un modèle de classification en dernier recours. On
vérifie qu'ils sont toujours actifs une fois déployés."*

**Requête 6** : tentative d'injection de prompt. → Bloqué,
`guardrail_category: "prompt_injection"`, réponse de refus. *"Toujours un
`200 OK` — un refus de l'agent n'est pas une erreur technique."*

**Requête 7** : question légitime sur un retour produit. → Répond
normalement, avec les vrais chiffres de la FAQ (14 jours, échange sous 7
jours). *"Important de montrer aussi ce cas : un garde-fou trop agressif
qui bloquerait les vraies questions clients serait un problème tout aussi
grave qu'un garde-fou absent."*

---

## 4. Signaux de suivi (1-2 min)

Basculer sur `conception/deploiement/signaux-suivi.md` (ou le Log stream
Azure en direct) :

- **Latence** : ~5,6s en moyenne hors démarrage à froid — montrer que
  celle du 1er message envoyé pendant la démo (si visible) confirme l'ordre
  de grandeur.
- **Taux de blocage garde-fous** : mesuré sur la session de test, avec le
  détail par catégorie.
- **Coût** : non mesurable via l'API Azure sur cet abonnement de
  formation partagé — limite assumée et documentée, pas cachée.

Dire : *"Ce ne sont pas des métriques théoriques — chaque chiffre vient
d'un appel réel qu'on vient de faire ou qu'on a fait plus tôt dans la même
session, contre ce même agent déployé."*

---

## Clôture (30s)

Dire : *"Pour résumer : agent joignable publiquement avec un vrai domaine
et un vrai certificat, mémoire persistante et isolée vérifiée en
conditions réelles, garde-fous actifs sans faux positif sur les cas
testés, et des signaux de suivi qui ne sont pas de la théorie. Le détail
complet — schémas, secrets, procédure de déploiement, incidents rencontrés
et corrigés — est dans `docs/runbook_deploiement_azure.md`."*

---

## Si quelque chose se passe mal pendant la démo

- **Une requête traîne (>15-20s)** : probable démarrage à froid si l'app
  vient de redémarrer — dire "le premier appel après une pause peut
  prendre jusqu'à 40s, c'est documenté" plutôt que paniquer.
- **La requête 4 ne retrouve pas le fait** : la consolidation n'a peut-être
  pas eu le temps de tourner — attendre encore 15-20s et relancer la
  requête 4 (pas la 3, sinon ça recrée le fait sans tester la persistance).
- **Un des `user_id` de démo n'existe plus** (base reseedée entre-temps) :
  relancer la requête 1 (`GET /users`) pour choisir deux ids valides à la
  volée, adapter les requêtes 3-5 en conséquence.
- **`Connection refused` / timeout total** : vérifier que `velmo-basic`
  n'est pas arrêté (`az webapp show --query state`) — cf.
  `docs/runbook_deploiement_azure.md`, section Incidents.
