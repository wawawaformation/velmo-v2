"""Tests de la lecture d'entrée utilisateur tolérante aux octets UTF-8 invalides.

Bug corrigé : `input()` plante avec `UnicodeDecodeError` sur un octet UTF-8
invalide (ex. touche morte mal interceptée par le terminal), tuant tout le
process CLI et perdant le contexte de conversation en cours.
"""

from __future__ import annotations

import io

from velmo.cli import _read_line


def test_read_line_decodes_valid_utf8():
    stream = io.BytesIO("Voici mon numéro : XT-30445\n".encode("utf-8"))
    assert _read_line(stream) == "Voici mon numéro : XT-30445"


def test_read_line_replaces_invalid_utf8_bytes_instead_of_raising():
    # 0xc2 sans octet de continuation valide (cas réel observé).
    stream = io.BytesIO(b"Voici mon numero de contrat : \xc2XT-30445\n")
    result = _read_line(stream)
    assert result is not None
    assert "XT-30445" in result


def test_read_line_returns_none_on_eof():
    stream = io.BytesIO(b"")
    assert _read_line(stream) is None
