"""Portti: "N Premier League teams" -luku tulee taulukosta, ei kasin.

Loydos 29.8.2026 (julkaisuportti, llms.txt-kierros): `build_fpl_page.py` kirjoitti
"all 20 Premier League teams" kovakoodattuna. Blank-gameweekissa taulukossa on
vahemman rivaja kuin 20, ja sivu olisi vaittanyt 20 silti. Sama vaite oli
kopioitu llms.txt:hen, jossa se olisi elanyt viela pidempaan koska sita ei
regeneroida.

Negatiivinen kontrolli: testi laskee rivit ITSE eika lue samaa lukua
molemmista paikoista.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "fpl.html"
CLAIM_RE = re.compile(
    r"Model clean sheet probability for the (\d+) Premier League teams"
)


def _clean_sheet_rows(html: str) -> int:
    i = html.find('id="clean-sheets"')
    assert i > 0, "#clean-sheets-lohkoa ei loydy - kontrolli lapaisisi tyhjana"
    j = html.find("</table>", i)
    assert j > i
    body = html[html.find("<tbody>", i): j]
    return body.count("<tr")


def test_luku_vastaa_taulukon_riveja():
    html = PAGE.read_text(encoding="utf-8")
    m = CLAIM_RE.search(html)
    assert m, "clean sheet -vaitetta ei loydy odotetussa muodossa"
    claimed = int(m.group(1))
    actual = _clean_sheet_rows(html)
    assert claimed == actual, (
        f"sivu vaittaa {claimed} joukkuetta mutta taulukossa on {actual} rivia"
    )


def test_vaite_ei_ole_kovakoodattu_lahteessa():
    src = (ROOT / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    assert "all 20 Premier League teams" not in src, (
        "luku on taas kovakoodattu - johda se cs_rows:n pituudesta"
    )


def test_kontrolli_havaitsee_vaaran_luvun():
    # Ilman tata testi voisi olla vihrea vaikka _clean_sheet_rows palauttaisi
    # aina saman luvun kuin vaite (esim. jos molemmat luettaisiin samasta
    # kohdasta).
    fake = '<h2 id="clean-sheets">x</h2><p>Model clean sheet probability for the 20 Premier League teams</p><table><tbody><tr></tr><tr></tr></tbody></table>'
    m = CLAIM_RE.search(fake)
    assert m and int(m.group(1)) == 20
    assert _clean_sheet_rows(fake) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
