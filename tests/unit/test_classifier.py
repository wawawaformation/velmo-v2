"""Tests unitaires du classifier mémoire (règles + LLM), cf. spec
docs/superpowers/specs/2026-07-07-classifier-llm-design.md.
"""

from __future__ import annotations

from velmo.memory.classifier import ClassificationResult, classify_and_distill


class FakeLLM:
    """LLM factice renvoyant une réponse fixe (contrôlée par le test)."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str, str]] = []

    def invoke(self, system: str, context: str, message: str) -> str:
        self.calls.append((system, context, message))
        return self.response


def test_classify_extracts_multiple_facts_from_llm_response():
    # Cas réel découvert : un message avec pointure + canal de contact + langue
    # ne doit pas ne retenir qu'un seul fait (bug des règles regex).
    llm = FakeLLM(
        '[{"destination": "semantic_column", "key": "pointure", "value": "42"},'
        '{"destination": "semantic_column", "key": "canal_contact", "value": "email"},'
        '{"destination": "semantic_column", "key": "langue", "value": "français"}]'
    )
    message = (
        "Pour infos, je fais du 42 en pointure, je préfère être contacté "
        "par mail et je parle français"
    )

    results = classify_and_distill(message, llm=llm)

    assert results == [
        ClassificationResult("semantic_column", "pointure", "42"),
        ClassificationResult("semantic_column", "canal_contact", "email"),
        ClassificationResult("semantic_column", "langue", "français"),
    ]


def test_classify_falls_back_to_rules_on_invalid_json():
    llm = FakeLLM("ceci n'est pas du JSON")
    message = "Je parle français"

    results = classify_and_distill(message, llm=llm)

    assert results == classify_and_distill(message, llm=None)
    assert results == [ClassificationResult("semantic_column", "langue", "français")]


def test_classify_parses_json_surrounded_by_extra_text():
    # Message qui ne matche aucune règle (fallback donnerait "none" / []),
    # pour isoler le comportement du parsing JSON tolérant du LLM.
    llm = FakeLLM(
        'Voici le résultat :\n'
        '[{"destination": "semantic_column", "key": "segment", "value": "pro"}]\n'
        'J\'espère que cela vous aide.'
    )

    results = classify_and_distill("Rien de spécial à signaler ici", llm=llm)

    assert results == [ClassificationResult("semantic_column", "segment", "pro")]


def test_classify_without_llm_returns_list_of_single_rule_result():
    results = classify_and_distill("Je parle français", llm=None)

    assert results == [ClassificationResult("semantic_column", "langue", "français")]


def test_classify_without_llm_returns_empty_list_when_no_rule_matches():
    results = classify_and_distill("Bonjour, comment ça va ?", llm=None)

    assert results == []


def test_classify_sends_system_prompt_describing_json_schema_and_known_keys():
    llm = FakeLLM('[]')

    classify_and_distill("Je fais du 43 en pointure", llm=llm)

    assert len(llm.calls) == 1
    system, _context, _message = llm.calls[0]
    assert "JSON" in system
    assert "destination" in system
    assert "semantic_column" in system
    assert "semantic_vector" in system
    assert "episodic" in system
    for key in ("pointure", "segment", "tutoiement", "langue", "canal_contact"):
        assert key in system


def test_classify_ignores_single_invalid_item_but_keeps_valid_ones():
    llm = FakeLLM(
        '[{"destination": "semantic_column", "key": "segment", "value": "pro"},'
        '{"destination": "semantic_column", "key": "cle_inconnue", "value": "x"},'
        '{"destination": "bidon", "value": "y"}]'
    )

    results = classify_and_distill("Rien de spécial à signaler ici", llm=llm)

    assert results == [ClassificationResult("semantic_column", "segment", "pro")]


def test_classify_rejects_implausible_pointure_value():
    # Cas réel observé : le LLM a classé une année de naissance (1975) comme
    # pointure, faute de validation de plausibilité sur la valeur.
    llm = FakeLLM(
        '[{"destination": "semantic_column", "key": "pointure", "value": "1975"}]'
    )

    results = classify_and_distill("Salut, je suis né le 07 septembre 1975", llm=llm)

    assert results == []


def test_classify_accepts_plausible_pointure_values():
    for value in ("42", "M", "XXL"):
        llm = FakeLLM(
            f'[{{"destination": "semantic_column", "key": "pointure", "value": "{value}"}}]'
        )
        results = classify_and_distill("peu importe", llm=llm)
        assert results == [ClassificationResult("semantic_column", "pointure", value)]


def test_classify_rejects_implausible_segment_value():
    llm = FakeLLM(
        '[{"destination": "semantic_column", "key": "segment", "value": "1975"}]'
    )
    results = classify_and_distill("peu importe", llm=llm)
    assert results == []


def test_classify_accepts_plausible_segment_values():
    for value in ("particulier", "pro", "revendeur"):
        llm = FakeLLM(
            f'[{{"destination": "semantic_column", "key": "segment", "value": "{value}"}}]'
        )
        results = classify_and_distill("peu importe", llm=llm)
        assert results == [ClassificationResult("semantic_column", "segment", value)]


def test_classify_rejects_implausible_tutoiement_value():
    llm = FakeLLM(
        '[{"destination": "semantic_column", "key": "tutoiement", "value": "Marc"}]'
    )
    results = classify_and_distill("peu importe", llm=llm)
    assert results == []


def test_classify_accepts_plausible_tutoiement_values():
    for value in ("tutoiement", "vouvoiement"):
        llm = FakeLLM(
            f'[{{"destination": "semantic_column", "key": "tutoiement", "value": "{value}"}}]'
        )
        results = classify_and_distill("peu importe", llm=llm)
        assert results == [ClassificationResult("semantic_column", "tutoiement", value)]


def test_classify_rejects_implausible_canal_contact_value():
    llm = FakeLLM(
        '[{"destination": "semantic_column", "key": "canal_contact", "value": "1975"}]'
    )
    results = classify_and_distill("peu importe", llm=llm)
    assert results == []


def test_classify_accepts_plausible_canal_contact_values():
    for value in ("email", "téléphone"):
        llm = FakeLLM(
            f'[{{"destination": "semantic_column", "key": "canal_contact", "value": "{value}"}}]'
        )
        results = classify_and_distill("peu importe", llm=llm)
        assert results == [ClassificationResult("semantic_column", "canal_contact", value)]


def test_classify_rejects_implausible_langue_value():
    llm = FakeLLM(
        '[{"destination": "semantic_column", "key": "langue", "value": "1975"}]'
    )
    results = classify_and_distill("peu importe", llm=llm)
    assert results == []


def test_classify_accepts_plausible_langue_values():
    for value in ("français", "anglais"):
        llm = FakeLLM(
            f'[{{"destination": "semantic_column", "key": "langue", "value": "{value}"}}]'
        )
        results = classify_and_distill("peu importe", llm=llm)
        assert results == [ClassificationResult("semantic_column", "langue", value)]
