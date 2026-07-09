"""Test de non-régression : NoOpProductTelemetry doit s'instancier sans lever.

Bug corrigé : la méthode `capture` surchargeait `ProductTelemetryClient.capture`
sans le décorateur `@override` requis par la lib `overrides` (dépendance de
chromadb) — `TypeError` à l'import, avalé silencieusement par le
`except Exception` de `get_episode_store`/`get_fact_store`, qui retombaient
alors sur le repli relationnel Postgres même quand Chroma était disponible
et configuré (observé en usage réel : CHROMA_URL valide, connexion directe
fonctionnelle, mais `get_episode_store()` renvoyait quand même
`LocalEpisodeStore`).
"""

from __future__ import annotations

def test_no_op_product_telemetry_module_imports_without_raising():
    # La levée se produisait à la définition de la classe (import du module),
    # avant même toute tentative d'instanciation — Chroma instancie la classe
    # via son propre système interne (`Component.__init__` exige `system`),
    # ce qui est hors du périmètre de ce test.
    from velmo.chroma_telemetry import NoOpProductTelemetry

    assert callable(NoOpProductTelemetry.capture)
