# Rapport — Latence et fiabilité Azure AI Foundry

**Date** : 2026-07-10
**Contexte** : suspicion que l'accès Azure Foundry du projet (hors de notre maîtrise —
provisionnement au niveau du hub) présente une latence/fiabilité dégradée, y compris
sur le modèle de chat principal (Kimi-K2.6), pas seulement sur le classifieur de
modération (Phi-4-mini-instruct) déjà connu comme instable.

## Méthode

Script `scripts/bench_llm_latency.py` : appels HTTP directs sur l'endpoint
`/chat/completions` (Azure OpenAI API), **sans LangChain ni SDK OpenAI**, pour
éliminer toute hypothèse d'overhead applicatif (retries, chaînes, etc.) et isoler
la latence réseau/backend pure. Log dédié `logs/bench_llm_latency.log`, distinct de
`logs/llm_latency.log` (production, via LangChain).

Trois séries testées sur 3 runs à des horaires différents (09:58, 10:04, 10:17) :

1. Prompt trivial ("Réponds uniquement par le mot OK.", `max_tokens=5`) sur Kimi-K2.6.
2. Même prompt trivial sur Phi-4-mini-instruct.
3. Prompt hors périmètre ("Pourquoi le ciel est bleu ?", `max_tokens=300`) sur Kimi-K2.6.

## Résultats

| Série | Run 1 (09:58) | Run 2 (10:04) | Run 3 (10:17) |
|---|---|---|---|
| Kimi-K2.6, prompt simple | 5/5 OK, 566-1759ms (avg 1017ms) | 5/5 OK, 533-1146ms (avg 842ms) | 5/5 OK, 573-1490ms (avg 1075ms) |
| Phi-4-mini-instruct, prompt simple | **3/5 OK** (2 timeouts à 30s pile), 514-838ms sur les réussites | 5/5 OK, 496-2119ms (avg 977ms) | 5/5 OK, 684-776ms (avg 744ms) |
| Kimi-K2.6, prompt hors périmètre (300 tokens) | — | 5/5 OK, 2367-3941ms (avg 2968ms) | 5/5 OK, 2578-3462ms (avg 2815ms) |

## Constats

- **Kimi-K2.6 est fiable et rapide en HTTP brut** : 15/15 appels réussis sur les 3
  runs, latence stable (0.5-1.5s sur prompt trivial, 2.4-3.9s sur une vraie génération
  de ~300 tokens). Aucune corrélation entre la nature du prompt (métier vs hors-scope)
  et la latence — le temps de réponse suit uniquement le volume de tokens générés.
- **Phi-4-mini-instruct est intermittent** : 40% d'échec en timeout pur (30s, aucune
  réponse) sur le run 1, 0% sur les runs 2 et 3. Ces échecs se produisent **hors de
  tout code applicatif** (pas de LangChain, pas de SDK OpenAI, pas de retries) — la
  cause est donc bien côté déploiement/infra Azure Foundry, pas notre couche logicielle.
- **Aucune reproduction ici des latences de 16-32s observées en usage réel** (CLI,
  via LangChain) — les runs de ce rapport sont soit rapides (<4s), soit des échecs
  francs à 30s (timeout du script, pas une lenteur intermédiaire). Cohérent avec une
  panne intermittente côté Foundry (tantôt ça répond vite, tantôt ça ne répond pas du
  tout) plutôt qu'une dégradation progressive et uniforme.

## Conclusion

L'hypothèse initiale ("tout Foundry est mauvais, même Kimi") n'est **pas confirmée** :
Kimi-K2.6 est rapide et fiable dans tous les tests. Le problème réel et mesuré est
**spécifique au déploiement Phi-4-mini-instruct**, utilisé comme classifieur de la
cascade de modération des garde-fous — instabilité intermittente (échecs francs,
pas juste de la lenteur), non liée à LangChain ni à notre code.

## Actions déjà en place / possibles

- **Fait** : `max_retries=0` sur `get_classifier_llm()` (évite qu'un échec Phi-4-mini
  ne soit multiplié par les retries automatiques du SDK OpenAI).
- **Fait** : coupe-circuit `VELMO_GUARDRAILS_LLM_CASCADE=0` (désactive la cascade LLM
  des garde-fous à chaud, repli sur les règles déterministes seules).
- **À explorer** (piste déjà notée en mémoire, non urgente) : remplacer
  Phi-4-mini-instruct par une solution locale (Detoxify) ou une autre API de
  modération, pour ne plus dépendre de ce déploiement Foundry spécifique.
- **En cours côté utilisateur** : évaluation d'un changement de modèle/déploiement
  sur Azure Foundry pour le classifieur.
