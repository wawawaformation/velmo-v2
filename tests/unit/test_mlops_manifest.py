"""Tests unitaires du manifeste d'évaluation — source de vérité unique du gate.

Avant : le seuil `0.8` vivait dans 5 endroits (deux tests, `score.py`, deux
fois `ci.yml`) et les pondérations en dur dans `run_eval`. Monter le seuil
imposait d'éditer cinq fichiers — et oublier les tests les laissait valider
silencieusement contre l'ancienne valeur.

La validation au chargement est délibérée : sans elle, des poids saisis à
`0.3/0.4/0.4` produiraient une note globale > 1 **en silence**, et le seuil ne
voudrait plus rien dire.
"""

from __future__ import annotations

import pytest

from velmo.mlops.manifest import load_manifest

_VALID = """
version: "2.1.0"
threshold: 0.75
weights:
  memory: 0.2
  guardrails: 0.5
  quality: 0.3
prompts:
  agent: "1.1.0"
  guardrails_moderation: "1.0.0"
  memory_consolidation: "1.0.0"
  memory_classifier: "1.0.0"
"""


def _write(tmp_path, content: str):
    path = tmp_path / "eval_manifest.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_manifest_reads_version_threshold_and_weights(tmp_path):
    manifest = load_manifest(_write(tmp_path, _VALID))

    assert manifest.version == "2.1.0"
    assert manifest.threshold == 0.75
    assert manifest.weights == {"memory": 0.2, "guardrails": 0.5, "quality": 0.3}


def test_load_manifest_reads_prompt_versions(tmp_path):
    manifest = load_manifest(_write(tmp_path, _VALID))

    assert manifest.prompts["agent"] == "1.1.0"
    assert set(manifest.prompts) == {
        "agent",
        "guardrails_moderation",
        "memory_consolidation",
        "memory_classifier",
    }


def test_load_manifest_rejects_missing_prompt_version(tmp_path):
    # Un prompt sans version déclarée casse la traçabilité silencieusement.
    bad = _VALID.replace('  memory_classifier: "1.0.0"\n', "")

    with pytest.raises(ValueError, match="memory_classifier"):
        load_manifest(_write(tmp_path, bad))


def test_load_manifest_rejects_weights_not_summing_to_one(tmp_path):
    # Faute de frappe classique : la note globale dépasserait 1 sans un mot.
    bad = _VALID.replace("quality: 0.3", "quality: 0.4")

    with pytest.raises(ValueError, match="somme"):
        load_manifest(_write(tmp_path, bad))


def test_load_manifest_rejects_threshold_out_of_range(tmp_path):
    bad = _VALID.replace("threshold: 0.75", "threshold: 1.5")

    with pytest.raises(ValueError, match="seuil"):
        load_manifest(_write(tmp_path, bad))


def test_load_manifest_rejects_missing_suite_weight(tmp_path):
    bad = _VALID.replace("  quality: 0.3\n", "")

    with pytest.raises(ValueError, match="quality"):
        load_manifest(_write(tmp_path, bad))


def test_shipped_manifest_is_valid():
    # Le manifeste réellement livré doit charger et être cohérent.
    manifest = load_manifest()

    assert manifest.version
    assert 0.0 <= manifest.threshold <= 1.0
    assert sum(manifest.weights.values()) == pytest.approx(1.0)
