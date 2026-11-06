"""Portti: generaattori ei voi tuottaa viivaa, jonka tyyliportti hylkaa (6.11.2026).

fp #99 lisasi `_band_txt`:iin `&ndash;`-merkinnan. PR:n CI oli vihrea, koska
tyyliportti lukee valmiit sivut, ja sivu rakentui vasta bottiajossa, joka ei aja
CI:ta. Seuraava PR kaatui vikaan, jota se ei ollut tehnyt.

Siksi tarkistus on tassa generaattorin lahdekoodille ja tulosteelle, ei vain sivulle.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import build_fpl_page as b
from scripts import check_copy_style as ccs

ROOT = Path(__file__).resolve().parent.parent

# Polku ja perustelu: uusi tiedosto ei paase listalle vahingossa.
SAA_SISALTAA = {
    "scripts/check_copy_style.py": "portti itse: kielletyt merkinnat ovat sen saantolistalla",
}


def test_lahdekoodissa_ei_ole_portin_kieltamaa_merkintaa():
    osumat = []
    for kansio in ("scripts", "src", "api"):
        for polku in sorted((ROOT / kansio).rglob("*.py")):
            suhteellinen = polku.relative_to(ROOT).as_posix()
            if suhteellinen in SAA_SISALTAA:
                continue
            teksti = polku.read_text(encoding="utf-8", errors="replace")
            osumat += [f"{suhteellinen}: {e}" for e in ccs.ENTITIES if e in teksti]
    assert not osumat, f"portti kaataa taman tuottaman sivun: {osumat}"


@pytest.mark.parametrize("html", [
    f'<span class="trk-band">{b._band_txt(0.3, 0.4, False)}</span>',
    f'<span class="trk-band">{b._band_txt(0.7, 1.0, True)}</span>',
    f'<td class="num">{b._run_cell({"run_cs_pct": None})}</td>',
])
def test_generaattorin_tuloste_lapaisee_tyyliportin(tmp_path, html):
    sivu = tmp_path / "sivu.html"
    sivu.write_text(f"<table><tr>{html}</tr></table>", encoding="utf-8")
    assert ccs.scan(sivu) == []


def test_kalibrointivali_on_tavuviivalla():
    assert b._band_txt(0.3, 0.4, False) == "30-40%"
