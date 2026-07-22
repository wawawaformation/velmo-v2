# Velmo 2.0 — Mémoire : nos choix de conception expliqués

*Document destiné au formateur et aux apprenants — Chantier 1 (Mémoire).*
*Objectif : pour chaque exigence imposée R1–R6, présenter le choix retenu et le justifier.*

---

## Avant-propos — réponses aux questions de réflexion (mémoire)

**1. Quels types de mémoire distinguez-vous ? Lequel répond à quelle exigence ?**
Nous distinguons une **mémoire court terme de conversation** (le fil de la session en cours), une **mémoire long terme persistante** elle-même scindée en **sémantique** (faits durables) et **épisodique** (événements datés). La « mémoire de travail » au sens classique n'est pas chez nous un magasin à part : c'est le **contexte effectivement assemblé à chaque tour** pour le LLM, composé du fil récent (+ son résumé glissant) et des souvenirs long terme sélectionnés — autrement dit le produit des autres mémoires, pas une quatrième base.
Correspondance avec les exigences : **R1** → court terme ; **R2** → long terme sémantique ; **R4** → court terme (résumé glissant) + mémoire de travail (sélection) ; **R3, R5, R6** → transverses, portées par le partitionnement `user_id` sur les deux mémoires long terme.
*Une mémoire procédurale (règles d'usage des outils, ton, seuils d'escalade) existe également, mais elle est identique pour tous les clients — elle ne relève pas de ce document (qui traite la mémoire par utilisateur) mais du Chantier 3, en tant que composante versionnée d'une « version » de l'agent (prompt + config mémoire + config garde-fous).*

**2. Comment structurez-vous la mémoire long terme (épisodique vs sémantique) ? Quel schéma de données ?**
La mémoire **sémantique** n'est pas dupliquée dans deux bases : c'est **un seul concept, routé vers un seul domicile selon la nature de sa clé**. Les faits à **clé connue d'avance** (`pointure`, `statut_compte`, `langue`…) deviennent des **colonnes directes sur la table `User`** (relationnel, typé, lecture immédiate). Les faits à **clé imprévisible** (formulés librement par le client, sans champ anticipé) sont stockés en **base vectorielle**, recherchés par similarité de sens. Avant écriture, un **petit modèle distille** le message brut en valeur propre — indispensable pour la route `User` (valeur typée dans une colonne), et utile aussi côté vectoriel (un embedding propre indexe mieux qu'une phrase bavarde).
La mémoire **épisodique** stocke des **événements en texte + date** en base **relationnelle**, avec un **nettoyage léger** : le bruit conversationnel est coupé et plusieurs messages bruts relatifs au même épisode sont fusionnés en un texte cohérent, mais le **vocabulaire du client est préservé** (noms de produits, termes exacts du litige, numéros…). Champs : `id_episode`, `user_id`, `contenu`, `date`. Ce n'est ni du copier-coller brut, ni une reformulation libre : la recherche se fait par mots-clés (`LIKE`), donc on ne change pas les mots, on coupe seulement le superflu.

*Règle générale retenue : le degré de retraitement suit le mode de recherche, pas le type de mémoire.* Recherche par **similarité de sens** (vectoriel, sémantique imprévisible) → **distillation forte**, valeur nette. Recherche par **mots exacts** (`LIKE`, épisodique) → **nettoyage léger**, vocabulaire intact.

**3. Comment décidez-vous ce qui est durable vs éphémère ? Qui écrit en long terme, et quand ?**
L'écriture se fait en **deux temps découplés**, pour ne jamais ralentir la conversation :
- **Capture (synchrone, immédiate) :** chaque message est écrit **un par un**, tel quel, dans une table tampon `MessageBrut`. C'est une simple insertion en base — quasi gratuite, aucun appel LLM, aucune latence perceptible pour le client.
- **Traitement (asynchrone, périodique) :** à intervalle régulier, **par utilisateur**, un petit modèle LLM lit les messages en attente dans `MessageBrut`, les **classe** (sémantique / épisodique / rien à retenir), les **retraite** selon la destination (distillation forte, nettoyage léger, ou aucun traitement), puis les **route**. Une fois un message traité, sa ligne est **supprimée** de `MessageBrut` — pas de duplication entre le brut et sa forme finale.

Ce qui n'est identifié dans aucun passage reste **éphémère** : rien n'est écrit, la ligne est simplement retirée du tampon.

*Pourquoi ce découplage plutôt qu'un traitement synchrone par lot :* un lot de taille fixe (« tous les 10 messages ») peut laisser un reliquat si la conversation s'arrête avant d'atteindre le seuil. Un **déclenchement périodique** (« toutes les X minutes, traiter tout ce qui est en attente ») vide le tampon quel que soit son contenu à chaque passage — plus aucun message ne peut rester bloqué indéfiniment. Le passage **par utilisateur** respecte l'isolation R3 : aucun risque de mélanger le texte de deux clients dans un même appel.

**4. Comment tenez-vous R4, et comment évitez-vous de perdre une info critique ?**
Par **résumé glissant** (condenser les messages anciens, garder les récents en intégral) plutôt que par troncature sèche, complété par la **sélection des souvenirs pertinents** via recherche plein texte/mots-clés sur les épisodes. On évite de perdre une info critique parce que les faits durables sont **extraits vers le long terme en tâche de fond**, indépendamment du fil court terme : ce qui compte est sauvegardé ailleurs, le résumé ne porte que sur le conversationnel.

**5. Comment implémentez-vous concrètement R5 (suppression) et R3 (isolation) dans le stockage ?**
**R3 (isolation) :** `user_id` est une colonne/métadonnée présente sur **chaque** entrée des mémoires long terme (y compris implicitement pour les colonnes fixes de `User`, isolées par construction puisque chaque ligne `User` est un client), sur la session, et sur `MessageBrut` ; toute lecture est filtrée par `user_id`, et le traitement asynchrone lui-même est cloisonné par utilisateur. La séparation est donc **structurelle**, pas applicative.
**R5 (suppression) :** on cible la donnée par `user_id` et on la **supprime dans tous les emplacements** où elle peut subsister — sémantique (colonne `User` remise à vide, ou ligne vectorielle supprimée selon le domicile du fait), épisodique (relationnel), fil court terme, **et `MessageBrut`** si le message contenant l'information n'a pas encore été traité par le passage asynchrone (fenêtre de risque courte, bornée par la fréquence du traitement périodique).

---

## En une phrase

Notre mémoire repose sur **quatre briques** distinctes, chacune stockée là où elle est le plus efficace :

| Brique | Contenu | Stockage |
|---|---|---|
| **Court terme (session)** | le fil de la conversation en cours | RAM, le temps de l'échange |
| **Tampon de capture** | messages bruts en attente de traitement | relationnel, temporaire (supprimé après traitement) |
| **Long terme sémantique** | faits durables, clé connue → colonne `User` / clé imprévisible → vectoriel | relationnel (colonnes User) ou vectoriel, selon la clé |
| **Long terme épisodique** | événements nettoyés (léger), recherchables par mots-clés | base relationnelle (plein texte) |

Toute la conception découle d'une règle de tri : *on ne met en mémoire que ce que l'agent doit retenir **d'un client**, **par client**, avec besoin de l'**isoler** et de l'**oublier**.* Les commandes, le stock et la FAQ ne sont **pas** de la mémoire : ce sont des données métier, interrogées par les outils (`get_order`, `check_stock`, `search_kb`).

### Cas de la base de connaissances (KB) — pourquoi elle n'est PAS de la mémoire

La base de connaissances (FAQ, politiques de retour, conditions de remboursement, guides de taille, explications d'authenticité) est interrogée par l'outil `search_kb`. **Elle n'a aucun lien avec un utilisateur**, et nous l'excluons volontairement du modèle de mémoire. Trois raisons, en appliquant notre règle de tri :

- **Elle est identique pour tous les clients.** Elle ne se décline pas « par utilisateur » → elle échoue au critère *« par client »*.
- **On ne l'« isole » pas et on ne l'« oublie » pas.** R3 (isolation) et R5 (droit à l'oubli) n'ont aucun sens sur la KB : un client ne peut pas demander d'oublier la politique de retour de la boutique.
- **L'agent ne la « retient » pas, il la consulte.** C'est une source documentaire externe, pas un souvenir construit au fil des échanges.

**Attention au faux ami technique :** la KB peut utiliser, comme la mémoire sémantique imprévisible, des **embeddings** et une recherche vectorielle. C'est une coïncidence d'outil, **pas** une parenté de nature. On classe une donnée par *ce qu'elle est et à qui elle appartient*, jamais par *la techno qui la stocke*.

En résumé : la KB vit **en dehors** du modèle de mémoire, comme une brique documentaire propre, branchée sur l'outil `search_kb`.

---

## R1 — Tenir le fil d'une conversation de 30+ tours sans perdre une info du début

**Notre choix.** La **mémoire court terme** conserve l'intégralité des messages de la session en cours (entité `Session` → `Message`), en RAM, accessibles à chaque tour. Pour qu'un fait donné au tour 1 reste disponible même quand la conversation s'allonge, on combine ça avec le résumé glissant (voir R4).

**Pourquoi.** Garder le fil complet en mémoire vive donne un accès direct et instantané à n'importe quel tour, y compris le premier — c'est la condition exacte du test (« interroger sur une info donnée au 1er tour »). Pas besoin de base pour ça : le court terme est éphémère et n'a pas vocation à survivre à la session.

---

## R2 — Se souvenir, d'une session à l'autre, des faits et préférences durables

**Notre choix.** Chaque message est d'abord écrit, un par un, dans `MessageBrut` (capture synchrone, immédiate). Un petit modèle LLM, en tâche de fond et à intervalle régulier, lit ce tampon par utilisateur, **distille** les faits durables en valeur propre, puis les route vers **un seul domicile** selon la prévisibilité de leur clé — pas de duplication. Clé **connue d'avance** (`statut_compte`, `tutoiement`, `pointure`…) → **colonne directe sur la table `User`**. Clé **imprévisible**, formulée librement par le client → **base vectorielle**. À l'ouverture d'une nouvelle session, on relit les colonnes `User` et on interroge le vectoriel pour le `user_id` concerné.

**Pourquoi.** Un fait à clé connue n'a besoin d'aucune recherche : une colonne `User` donne une lecture directe, immédiate, et rend l'oubli trivial (on vide la colonne). Un fait à clé imprévisible n'a, par définition, pas de colonne prête à l'accueillir — le vectoriel le capte sans qu'on ait eu à prévoir sa structure, et la recherche par similarité absorbe les reformulations de la question (« je suis pro non ? » plutôt que « quel est mon statut ? »). Ce routage à deux domiciles est plus propre qu'un stockage dupliqué : chaque fait n'a qu'une seule source de vérité, ce qui simplifie la lecture, l'oubli (R5) et l'inspection (R6). Le passage par `MessageBrut` (plutôt qu'une extraction directe à chaque message) garantit que le client n'attend jamais un appel LLM pour recevoir sa réponse — la latence de conversation reste minimale.

---

## R3 — Isolation stricte : la mémoire d'un utilisateur n'est jamais accessible à un autre

**Notre choix.** Le `user_id` est présent sur **toutes** les entités de mémoire, y compris `MessageBrut`. Chaque lecture est filtrée (`WHERE user_id = …`), et le traitement asynchrone périodique s'exécute **par utilisateur** (jamais un appel mélangeant plusieurs clients). Le court terme est en plus cloisonné par `session_id`, lui-même rattaché à un `user_id`.

**Pourquoi.** Partitionner par `user_id` empêche **structurellement** la fuite : un client ne peut pas requêter ce qui n'est pas à lui. Le test le vérifie avec deux secrets (`SEC-AAA-111` pour u-301, `SEC-BBB-222` pour u-302) qui ne doivent jamais se croiser.
*Piège que nous avons identifié et évité :* si l'agent tourne dans un process persistant (script/LangChain qui ne s'arrête pas), une variable d'historique globale partagée ferait fuiter la conversation d'un client vers le suivant. Le cloisonnement par `session_id`/`user_id` — étendu maintenant au traitement asynchrone par utilisateur — neutralise ce risque, quel que soit le lieu de stockage.

---

## R4 — Tenir la fenêtre de contexte : résumer/sélectionner sans perdre l'info critique

**Notre choix.** Deux mécanismes complémentaires :
- **Résumé glissant** sur le fil court terme : au-delà du budget de tokens, les messages anciens sont condensés en un résumé court, les récents gardés en intégral.
- **Sélection des épisodes pertinents** par recherche plein texte/mots-clés (relationnel) : on ne réinjecte que les souvenirs long terme pertinents pour la question courante.

**Pourquoi.** On ne peut pas tout réinjecter indéfiniment. La protection contre la « perte d'info critique » vient d'un mécanisme indépendant du fil : les faits durables sont capturés dans `MessageBrut` **dès leur émission**, puis extraits vers le long terme par le traitement asynchrone — sans dépendre du rythme du résumé glissant. Donc résumer le fil ne fait pas perdre l'essentiel : il est sauvegardé ailleurs, sur un circuit séparé.

---

## R5 — Droit à l'oubli (RGPD) : suppression effective et vérifiable

**Notre choix.** Sur « oublie mon numéro de commande », on efface l'information **dans tous les emplacements** où elle peut se trouver : mémoire **sémantique** (colonne `User` vidée si clé connue, ou ligne vectorielle supprimée si clé imprévisible), mémoire **épisodique** (relationnel), **fil court terme** de la session en cours, et **`MessageBrut`** si le message contenant l'information est encore en attente de traitement.

**Pourquoi.** Le test `forget` vérifie une **absence** : il échoue si la valeur (ex. `4490`) ressort encore, **où que ce soit**. Supprimer une seule copie ne suffirait pas. L'ajout de `MessageBrut` à cette liste est une conséquence directe du traitement asynchrone : entre l'écriture d'un message et son traitement périodique, il existe une **fenêtre courte** pendant laquelle l'information n'est encore nulle part ailleurs que dans ce tampon — l'oubli doit la couvrir, sans quoi le passage asynchrone risquerait de **réécrire un fait que le client vient d'explicitement demander d'oublier**. Cette fenêtre se referme d'elle-même dès que le tampon est traité (la ligne est alors supprimée, cf. Point 3).

---

## R6 — Traçabilité : inspecter ce que l'agent a retenu d'un utilisateur

**Notre choix (v1, au plus simple).** Une **fonction d'inspection** qui, pour un `user_id`, lit ses colonnes `User` renseignées (faits à clé connue) et interroge le vectoriel (faits à clé imprévisible), et liste ses épisodes. `MessageBrut` n'a pas vocation à être inspecté : c'est un tampon temporaire, pas une mémoire consultée par le client.

**Pourquoi.** C'est le strict nécessaire pour répondre à l'exigence (« inspecter ce que l'agent a retenu »), sans surcharge.
*Évolutions notées en v2 :* exposer l'inspection via un point d'accès dédié (endpoint/CLI), puis ajouter un **journal des écritures/suppressions** qui matérialiserait la *preuve* d'oubli — utile pour la traçabilité RGPD.

---

## Mécanisme transverse — Écriture différée en mémoire long terme (qui écrit, et quand)

**Notre choix.** L'écriture se déroule en **deux temps découplés** :

1. **Capture synchrone, message par message.** Chaque message entrant est écrit tel quel, immédiatement, dans une table tampon `MessageBrut` (`id`, `user_id`, `contenu`, `horodatage`). C'est une simple insertion en base — quasi gratuite (aucun token, aucun appel LLM), donc aucune raison de temporiser.
2. **Traitement asynchrone, périodique, par utilisateur.** À intervalle régulier, un **petit modèle LLM** balaie le tampon d'un utilisateur donné, **classe** chaque message (sémantique / épisodique / rien à retenir), applique le **degré de retraitement adapté à la destination** — distillation forte pour le sémantique, nettoyage léger (vocabulaire préservé) pour l'épisodique, aucun traitement si rien n'est retenu — puis **route** vers la colonne `User`, la base vectorielle, ou la table épisodique. Une fois un message traité, sa ligne est **supprimée** de `MessageBrut`.

**Pourquoi découpler capture et traitement.** Le client n'attend jamais un appel LLM pour recevoir sa réponse : la latence de conversation reste minimale, puisque seule une insertion en base se produit sur le chemin critique. Le traitement, coûteux en tokens, est repoussé en tâche de fond.

**Pourquoi périodique plutôt que par lot compté.** Un lot à taille fixe (« tous les 10 messages ») peut laisser un reliquat non traité si la conversation s'arrête avant d'atteindre le seuil. Un déclenchement **temporel** vide le tampon à chaque passage, quel que soit son contenu — le problème du reliquat disparaît structurellement, sans mécanisme de secours à ajouter.

**Pourquoi supprimer après traitement.** Éviter la duplication entre le message brut et sa forme finale (colonne, vecteur, épisode). Ça referme aussi, à chaque passage, la fenêtre de risque pour R5 (cf. section R5).

**Pourquoi le degré de retraitement varie selon la destination.** *Le retraitement suit le mode de recherche, pas le type de fait.* Colonne `User` et vectoriel se recherchent par clé ou par similarité de sens → une valeur nette indexe et se lit mieux qu'une phrase brute, d'où la **distillation forte**. L'épisodique se recherche par mots-clés (`LIKE`) → reformuler risquerait de faire disparaître le terme que le client réutilisera plus tard, d'où le **nettoyage léger** qui coupe le bruit conversationnel sans changer les mots.

---

## Tableau de synthèse — exigence → mémoire → stockage

| Exigence | Réponse principale | Type de mémoire | Stockage |
|---|---|---|---|
| **R1** fil 30+ tours | fil complet de la session | court terme | RAM |
| **R2** inter-session | faits capturés puis routés selon la clé | long terme sémantique | colonne User (clé connue) ou vectoriel (clé imprévisible) |
| **R3** isolation | `user_id` partout, y compris `MessageBrut` ; traitement asynchrone par utilisateur | toutes | (transverse) |
| **R4** budget tokens | résumé glissant + sélection plein texte | court terme + épisodique | RAM + relationnel |
| **R5** oubli | suppression dans tous les emplacements, y compris le tampon en attente | toutes | User (colonne vidée) + vectoriel + relationnel + RAM + MessageBrut |
| **R6** inspection | fonction de listing par `user_id` | long terme | colonnes User + vectoriel + relationnel (épisodes) |

---

## Notre fil directeur

**v1 = la solution la plus simple qui respecte l'exigence ; tout raffinement → v2.**
Chaque choix ci-dessus a été pris pour passer les tests d'acceptance et tenir les six exigences, sans sur-ingénierie. Les pistes plus ambitieuses (endpoint d'inspection dédié, journal RGPD, vectoriel sur l'épisodique) sont assumées comme évolutions, pas comme dette cachée.

*Remarque sur la couverture des tests :* le jeu `memory_cases.jsonl` (12 cas) couvre R1, R2, R3, R5. R4 et R6 n'ont pas de cas d'éval associé — nous les tenons quand même, car ce sont des exigences imposées. **Cette analyse des 12 cas a aussi guidé un choix d'architecture** : dans tous les cas, le mot-clé du fait réapparaît quasi tel quel dans la question de rappel (aucune reformulation profonde testée) ; combiné au faible volume d'épisodes par client, cela nous a conduits à ne pas recourir au vectoriel pour l'épisodique en v1 — la contrainte de stack imposée (« base vectorielle pour la mémoire long terme ») restant satisfaite par le routage des faits sémantiques imprévisibles vers le vectoriel.
