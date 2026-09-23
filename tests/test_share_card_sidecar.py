# -*- coding: utf-8 -*-
"""POSTATTU-KORTTI-EI-OLE-TALLESSA (22.9.2026): jokainen tallennettu kortti
kantaa sidecar-todisteen (rivit, generated_at, sha256).

TAUSTA. `outputs/` on football-predictionin .gitignoressa (rivi 260) ja
jokainen `gen_share_card.py`-ajo kirjoittaa SAMAN tiedostonimen yli.
Mitattu 12.9: 9.9 postattua GW4-korttia (M82) ei ollut enaa olemassa
missaan - MARKETING_QUEUE viittasi committiin `9ff5df035`, mutta
`git log -- outputs/cards/` oli tyhja. Emme siis voineet todistaa mita
postasimme.

Tama tiedosto vahtii MOOTTORIN (`_save_with_sidecar`) invariantteja: sha256
on tiedoston OMA, ei canvasin itseraportoima, ja jokainen kortin
tallennuspaikka kutsuu tasan tata yhta funktiota. `outputs/cards/` on
gitignoressa eika sen jarjestely (POSTATTU-rivin linkitys sidecariin) ole
tassa - tama on moottorin osa, ei markkinointityonkulun.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PIL_Image = pytest.importorskip("PIL.Image")

import scripts.gen_share_card as gsc  # noqa: E402

SRC = ROOT / "scripts" / "gen_share_card.py"


def _canvas():
    return PIL_Image.new("RGB", (10, 10), color=(1, 2, 3))


def test_sidecar_sisaltaa_oikean_sha256in_levylla_olevasta_tiedostosta(tmp_path):
    """Sidecarin sha256 on laskettava UUDELLEEN levylta, ei luotettava
    itseraportointiin - muuten testi mittaisi vain etta kentta on olemassa."""
    out = tmp_path / "card.png"
    gsc._save_with_sidecar(_canvas(), out, {"title": "T", "rows": [1, 2, 3]})

    assert out.exists()
    sidecar_path = tmp_path / "card.png.json"
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    todellinen_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    assert sidecar["sha256"] == todellinen_sha
    assert sidecar["file"] == "card.png"
    assert sidecar["card"] == "T"
    assert sidecar["rows"] == 3


def test_negatiivinen_kontrolli_eri_sisalto_tuottaa_eri_shan(tmp_path):
    """Jos sha256 olisi vakio tai laskettu vaarasta lahteesta, tama lapaisisi
    myos silloin kun kaksi eri kuvaa saisivat saman sha:n - eli emme
    mittaisi mitaan (muisti: kontrolli-lapaisi-tyhjana)."""
    out1 = tmp_path / "a.png"
    out2 = tmp_path / "b.png"
    gsc._save_with_sidecar(_canvas(), out1, {"title": "A"})
    canvas2 = PIL_Image.new("RGB", (10, 10), color=(9, 9, 9))
    gsc._save_with_sidecar(canvas2, out2, {"title": "B"})

    sha1 = json.loads((tmp_path / "a.png.json").read_text())["sha256"]
    sha2 = json.loads((tmp_path / "b.png.json").read_text())["sha256"]
    assert sha1 != sha2


def test_mutaatiokontrolli_tiedoston_muuttaminen_jalkikateen_paljastuu(tmp_path):
    """Todistaa etta testi tosiaan lukee LEVYA eika muistissa olevaa canvasia:
    jos tiedostoa peukaloidaan tallennuksen jalkeen, uudelleenlaskettu sha
    EI enaa tasmaa sidecarin kanssa - eli portti jonka tama testi mallintaa
    (verifioi sidecar vs. levylla oleva tiedosto) oikeasti puree."""
    out = tmp_path / "card.png"
    gsc._save_with_sidecar(_canvas(), out, {"title": "T"})
    sidecar = json.loads((tmp_path / "card.png.json").read_text())

    out.write_bytes(out.read_bytes() + b"\x00")  # peukaloitu tallennuksen jalkeen

    uusi_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    assert uusi_sha != sidecar["sha256"], (
        "peukaloitu tiedosto sai saman shan - sha256 ei todista mitaan")


def test_generated_at_on_jasentyva_utc_aikaleima(tmp_path):
    out = tmp_path / "card.png"
    # sidecar pyoristaa sekunnin tarkkuuteen (timespec="seconds"), joten
    # vertailuraja PYORISTETAAN ALASPAIN samoin - muuten testi voisi
    # satunnaisesti punastua mikrosekuntien takia (flaky, ei aito vika).
    ennen = datetime.now(timezone.utc).replace(microsecond=0)
    gsc._save_with_sidecar(_canvas(), out, {"title": "T"})
    jalkeen = datetime.now(timezone.utc)
    sidecar = json.loads((tmp_path / "card.png.json").read_text())

    leima = datetime.fromisoformat(sidecar["generated_at"])
    assert leima.tzinfo is not None
    assert ennen <= leima <= jalkeen


@pytest.mark.parametrize("spec,odotus", [
    ({"rows": [1, 2, 3, 4]}, 4),
    ({"fixtures": [1, 2]}, 2),
    ({"cols": [1, 2, 3]}, 3),
    ({"left": [1, 2], "right": [1, 2, 3]}, 5),
    ({"left": [1, 2]}, 2),
    ({}, None),
])
def test_card_row_count_tunnetut_muodot(spec, odotus):
    assert gsc._card_row_count(spec) == odotus


# ---------------------------------------------------------------------------
# Kutsupaikkaportti: JOKAINEN render*-funktio kutsuu YHTA sidecar-kirjoittajaa
# ---------------------------------------------------------------------------

def test_jokainen_render_funktio_kutsuu_save_with_sidecaria():
    """18.9-oppi (gate-substring-osuma-on-sokea): ei riita etta
    `_save_with_sidecar` on olemassa - jokaisen kortin tallennuspaikan on
    OIKEASTI kutsuttava sita eika omaa `.save(out_path, ...)`-riviaan.
    Ilman tata uusi kortti (tai vanha regressoituna) voisi ohittaa
    sidecarin hiljaa."""
    src = SRC.read_text(encoding="utf-8")

    # Ainoa sallittu suora `.save(out_path` on itse apufunktion sisalla.
    render_defs = [ln for ln in src.splitlines() if ln.strip().startswith("def render")]
    assert len(render_defs) >= 6, (
        f"odotettiin vahintaan 6 render*-funktiota, loytyi {len(render_defs)} - "
        "onko tiedosto muuttunut rakenteeltaan?")

    suorat_tallennukset = src.count('.save(out_path,')
    assert suorat_tallennukset == 1, (
        f"'.save(out_path,' esiintyy {suorat_tallennukset} kertaa lahteessa, "
        "odotettiin tasan 1 (vain _save_with_sidecarin sisalla). Uusi "
        "kutsupaikka ohittaisi sidecarin.")

    kutsurivit = [ln for ln in src.splitlines()
                  if "_save_with_sidecar(canvas, out_path" in ln
                  and not ln.strip().startswith("def ")]
    kutsut = len(kutsurivit)
    assert kutsut == 6, (
        f"_save_with_sidecar(canvas, out_path...) -kutsuja loytyi {kutsut}, "
        "odotettiin 6 (render, render_gw_outlook, render_gw_outlook_hero, "
        "render_reply_list, render_captain_compare, render_model_vs_template). "
        "Jos lisasit uuden korttityypin, sen ON kutsuttava samaa funktiota.")
