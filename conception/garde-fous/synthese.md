# Fiche synthétique — Chantier 2 : Garde-fous Velmo 2.0

*Réécriture intégrant les réponses aux questions de réflexion du brief + les candidats Azure AI Foundry pour chaque sous-contrôle.*

---

## Avant-propos — réponses aux questions de réflexion (garde-fous)

**1. Où placez-vous chaque contrôle : entrée, sortie, ou les deux ?**

| Catégorie | Emplacement | Pourquoi |
|---|---|---|
| Haine / violence / sexuel | **Les deux** | le client peut insulter (entrée) *et* le LLM peut halluciner un contenu problématique (sortie) |
| Injection de prompt | **Entrée seule** | doit être arrêtée avant que le LLM ne lise la requête |
| PII / secrets internes | **Entrée (secret_leak) + Sortie** | une demande explicite de secrets internes (clé API, mot de passe serveur) est aussi un risque en entrée, distinct du risque de fuite en génération — les deux sont couverts par `detect_pii` (catégories `secret_leak` en entrée et sortie, `pii` structurel type carte/IBAN en sortie) |
| Données d'un autre client | **Outils** (ni entrée ni sortie au sens strict) | question d'autorisation sur l'action, pas de filtrage de texte |
| Hors périmètre (médical/juridique) | **Les deux** | détectable dans la demande, mais le LLM peut aussi y dériver spontanément en sortie |

**2. Quelle méthode par catégorie, avantages et angles morts ?**
Voir le tableau détaillé plus bas. En résumé : **regex** pour les motifs structurés (rapide, gratuit ; angle mort = ne détecte que ce qui est prévu) ; **classifieur de modération** pour le contenu naturel (fiable sur les catégories connues ; angle mort = coûte un appel, peut rater l'ironie/le contexte) ; **vérification de périmètre** pour l'intention (nécessite de comprendre le sens, donc plus lent) ; **contrôle applicatif** pour l'autorisation (`user_id` — déterministe, aucun angle mort si bien implémenté).

**3. Comment gérez-vous les faux positifs ?**
Trois comportements, pas deux : **autoriser** (sûr) / **clarifier** (ambigu — comportement par défaut plutôt que bloquer sec) / **bloquer** (clairement interdit). Le seuil de déclenchement des classifieurs est ajustable ; le taux de faux positifs sera mesuré au Chantier 3 (`guardrail_cases.jsonl`) pour recalibrer.

**4. Que fait l'agent quand il bloque ?**
Message poli expliquant le périmètre + proposition d'aide alternative, journalisation systématique (`GuardrailEvent`, sans recopier la donnée sensible), et **escalade humaine** réservée aux cas graves (remboursement > 50 €, commande expédiée, litige d'authenticité, contenu manifestement illégal).

**5. Comment résistez-vous à une injection qui tente de désactiver vos garde-fous ?**
Défense en profondeur : les contrôles sont **externes au LLM**, avant/pendant/après. Même si l'injection réussit à influencer le LLM en interne, le contrôleur d'outils et le garde-fou de sortie interceptent quand même — le LLM n'a jamais le dernier mot sur ce qui s'exécute ou sort.

---

## Objectif

Velmo 2.0 doit traiter automatiquement les demandes simples de support, tout en empêchant les contenus interdits, les fuites de données, les actions métier dangereuses, les tentatives de contournement et les sorties hors périmètre.

> L'agent peut lire largement pour comprendre la situation, mais il n'agit qu'après confirmation explicite et dans les limites autorisées.

---

## Tableau des garde-fous — catégorie × emplacement × méthode × action

| Catégorie | Emplacement | Méthode | Action si déclenché |
|---|---|---|---|
| ① Haine / discrimination / harcèlement | Entrée + Sortie | Classifieur de modération | Bloquer, refus poli, journaliser |
| Violence / menaces | Entrée + Sortie | Classifieur de modération | Bloquer, refus poli, journaliser |
| Contenu sexuel / NSFW | Entrée + Sortie | Classifieur de modération | Bloquer, refus poli, journaliser |
| ② Injection de prompt | Entrée | Règles (motifs) + classifieur | Neutraliser, ne jamais obéir, journaliser |
| ③ Hors périmètre (médical, juridique) | Sortie (et entrée si détectable) | Vérification de périmètre (LLM léger) | Refuser poliment, rediriger, journaliser |
| ④ PII / secrets internes | Entrée + Sortie | Azure Language — Conversational PII redaction | Rédiger automatiquement, journaliser (extrait non recopié) |
| Données d'un autre client | Outils + Sortie | Contrôle applicatif (`user_id`) | Bloquer l'accès, journaliser |

---

## Petits modèles / services candidats — Azure AI Foundry

*Correspondance directe avec les numéros ①②③④ du schéma drawio. Confirmé sur le catalogue Foundry du projet (161 modèles disponibles).*

### Azure AI Content Safety — le candidat naturel pour ①②

- **Détection de contenu nuisible** (haine, violence, sexuel, automutilation) sur texte, seuils réglables par catégorie — couvre **①**.
- **Prompt Shields** : détecte les tentatives de jailbreak/injection, directes ou indirectes (documents tiers) — couvre **②**.
- **Groundedness detection** (bonus) : vérifie qu'une réponse s'appuie sur des données réelles — utile pour repérer une promesse non tenue.

### Azure Language — Conversational PII redaction — le candidat pour ④

Meilleur choix que le regex initialement prévu : ce service est **entraîné spécifiquement sur des données conversationnelles**, pas sur un motif figé. Il attrape des formulations qu'un regex raterait (ex. un numéro de carte dicté avec des espaces ou des mots entre les chiffres).

*Disponible aussi en variante `Document-PII-redaction` (fichiers) et `Text-PII-redaction` (générique) — on retient la version conversationnelle, la plus adaptée à un agent de support qui dialogue.*

### Petits LLM (Foundry Model Catalog) — pour ③ et pour la mémoire

| Modèle | Éditeur | Usage recommandé |
|---|---|---|
| **Phi-4-mini-instruct** (3,8 Md param.) | Microsoft | Déployé dans ton projet — vérification de périmètre (③), classification/distillation mémoire |
| **Ministral-3B** | Mistral AI | Alternative encore plus légère, disponible dans ton catalogue |
| **Phi-4-reasoning** | Microsoft | Si ③ nécessite un raisonnement plus poussé |

*Note : Llama Guard 3 (LLM spécialisé modération) n'est pas disponible sur ce projet Azure — non bloquant, Content Safety couvre déjà ①②.*

> **Architecture recommandée pour Velmo** : Content Safety pour ①②, Conversational PII redaction pour ④, Phi-4-mini-instruct pour ③ et pour la mémoire (Chantier 1). Un seul écosystème (Foundry), cohérent, avec un contrôle de coût dès la conception.

---

## Garde-fou d'outils

**Lecture** (libre, filtrée `user_id`) : `get_order`, `track_shipment`, `check_stock`, `search_kb`
**Action** (renforcé — confirmation + seuils + journalisation + escalade) : `update_order_item`, `cancel_order`, `create_return`, `trigger_refund`, `escalate_to_human`

Le filtrage `user_id` s'applique **aux deux familles**, pas seulement à la lecture.

## Règles d'action

| Situation | Décision |
|---|---|
| Remboursement ≤ 50 € | Possible après confirmation |
| Remboursement > 50 € | Escalade humaine obligatoire |
| Commande déjà expédiée | Pas d'annulation auto ; retour ou escalade |
| Litige d'authenticité | Escalade humaine obligatoire |
| Demande sur un autre client | Blocage |

## Journalisation

```text
GuardrailEvent
- id, user_id, session_id, date
- stage: input | tool | output
- category, severity
- action: allow | block | redact | confirm_required | escalate
- reason, excerpt_redacted (jamais la donnée brute)
```

---

## Position retenue

Velmo ne fait confiance ni à l'utilisateur, ni au modèle seul. Les contrôles sont **externes** au LLM (avant/pendant/après) — une injection de prompt ne peut donc pas désactiver les garde-fous, même si elle réussit à influencer la génération.
