# -*- coding: utf-8 -*-
"""QUEUE POSTATTU-KORTTI-EI-OLE-TALLESSA (26.9.2026).

`outputs/` on .gitignoressa ja jokainen `gen_share_card.py`-ajo kirjoittaa
saman tiedostonimen yli (mitattu 12.9: 9.9 postattu GW4-kortti ei ollut enaa
olemassa missaan). `write_card_sidecar()` kirjoittaa PNG:n VIERELLE
`<tiedosto>.json`-sivutiedoston (generated_at, sha256, rivit) samalla
hetkella kun kortti piirretaan, jotta postattu kortti voidaan myohemmin
todistaa (ei vain vaittaa) samaksi kuin se mika levylla oli postaushetkella.

Testataan `write_card_sidecar()` suoraan synteettisella PNG:lla + spekilla,
EI koko `gen_share_card.py main()`-putkea: putki tarvitsee fontit
goaliq-appin node_modulesista (npm install, ei tehty tassa saastossa) eika
sen renderointi ole tamans rivin kysymys. Rakenteellinen testi varmistaa
etta main()n kolme paluuhaaraa yhä kutsuvat `write_card_sidecar`ia — jos
joku poistaa kutsun refaktoroidessaan, testi kaataa build+n ilman etta
fontteja tarvitaan.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gen_share_card as gsc  # noqa: E402


def _write_dummy_png(path: Path) -> None:
    Image.new("RGB", (4, 4), (10, 20, 30)).save(path, "PNG")


def test_sidecar_sha256_matches_written_file(tmp_path):
    png = tmp_path / "card.png"
    _write_dummy_png(png)
    expected_sha = hashlib.sha256(png.read_bytes()).hexdigest()

    side = gsc.write_card_sidecar(png, "stats", {"rows": [{"a": 1}, {"a": 2}]})

    assert side == png.with_name("card.png.json")
    doc = json.loads(side.read_text(encoding="utf-8"))
    assert doc["sha256"] == expected_sha
    assert doc["card"] == "stats"
    assert doc["n_rows"] == 2
    assert doc["rows"] == [{"a": 1}, {"a": 2}]
    # generated_at parsittavissa ja UTC:ssa (fromisoformat kaataa jos ei).
    ts = datetime.fromisoformat(doc["generated_at"])
    assert ts.tzinfo is not None


def test_sidecar_sha256_changes_if_png_content_changes(tmp_path):
    """Negatiivinen kontrolli: jos joku ylikirjoittaisi PNG:n sisallon
    muuttamatta sidecaria, seuraava sidecar-ajo EI saisi antaa samaa
    sha256:aa vanhalle sisallolle — eli sha lasketaan levylta, ei muistista."""
    png = tmp_path / "card.png"
    _write_dummy_png(png)
    side1 = gsc.write_card_sidecar(png, "stats", {"rows": []})
    sha1 = json.loads(side1.read_text(encoding="utf-8"))["sha256"]

    Image.new("RGB", (4, 4), (99, 99, 99)).save(png, "PNG")
    side2 = gsc.write_card_sidecar(png, "stats", {"rows": []})
    sha2 = json.loads(side2.read_text(encoding="utf-8"))["sha256"]

    assert sha1 != sha2
    assert sha2 == hashlib.sha256(png.read_bytes()).hexdigest()


def test_sidecar_falls_back_to_fixtures_when_no_rows(tmp_path):
    png = tmp_path / "gw.png"
    _write_dummy_png(png)
    side = gsc.write_card_sidecar(png, "gw-outlook",
                                  {"fixtures": [{"home": "ARS", "away": "SUN"}]})
    doc = json.loads(side.read_text(encoding="utf-8"))
    assert doc["n_rows"] == 1
    assert doc["rows"] == [{"home": "ARS", "away": "SUN"}]


def test_sidecar_n_rows_none_without_rows_or_fixtures(tmp_path):
    png = tmp_path / "x.png"
    _write_dummy_png(png)
    side = gsc.write_card_sidecar(png, "defence", {})
    doc = json.loads(side.read_text(encoding="utf-8"))
    assert doc["n_rows"] is None
    assert doc["rows"] is None


@pytest.mark.parametrize("kind", ["reply", "gw_outlook", "default"])
def test_main_calls_write_card_sidecar_on_every_exit_branch(kind):
    """Rakenteellinen mutaatiovahti: jos joku poistaa
    `write_card_sidecar(...)`-kutsun main()sta jatkorefaktoroinnissa,
    tama kaataa ilman etta koko renderointiputkea (fontit, data) tarvitsee
    ajaa. Kolme haaraa = reply-kortit, gw-outlook, oletusrenderi."""
    src = inspect.getsource(gsc.main)
    calls = src.count("write_card_sidecar(")
    assert calls == 3, (
        f"main() kutsuu write_card_sidecar:ia {calls} kertaa, odotettiin 3 "
        "(reply/gw_outlook/default) — kortti voisi taas kadota jaljetta.")
