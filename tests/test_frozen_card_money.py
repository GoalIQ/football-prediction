"""FROZEN-KORTTI-RAHALUKU-VAARIN: mallin jakokortissa EI ole rahalukua (28.9.2026).

Historia:
- 4.9 portti tuomitsi "<nykyhintojen summa>m spent" (ostohinnat eivat ole julkisia).
- 22.9 kortti luki `selling_value_tenths` + `bank_tenths` freezen metasta:
  "<b>99.1m</b> selling value · 1.2m in the bank".
- 28.9 Ville: "eihan 99.1m selling value ja 1.2m in the bank tasmaa?" Mitattu:
  FPL kirjasi GW5-deadlinella value 1004 ja bank 5 (entry/116920/event/5/picks),
  eli pankki 0.5m eika 1.2m. Myyntiarvo nakyy FPL:ssa vain tilin omistajalle,
  joten lukija ei voi tarkistaa sita ilmaispinnalta. Villen GO CC:n
  suositukselle: rahaluku pois kortista.

Kortti on pysyva kuva (julkinen teksti). Portti kaatuu jos kortti alkaa taas
lukea rahakenttia tai tulostaa rahasanan alatunnisteeseen.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import render_frozen_squad_card as card  # noqa: E402

SRC = (ROOT / "scripts" / "render_frozen_squad_card.py").read_text(encoding="utf-8")
RAHASANAT = re.compile(r"selling value|in the bank|\bspent\b|\bbank\b|team value|squad value", re.I)


def _code(src: str) -> str:
    """Kommentit ja docstringit pois, jotta perustelu ei kay koodista."""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    return "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())


def _runko(meta: dict) -> dict:
    """Tuotannon muotoinen runko: 15 pelaajaa, freezen meta rahakenttineen."""
    pos = [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4]

    def p(i, ps):
        return {"id": 200 + i, "web_name": f"P{i}", "team_short": "ARS", "pos": ps,
                "price": 55, "status": "a", "chance": None}
    xi = [p(i, ps) for i, ps in enumerate(pos)]
    bench = [p(11 + i, ps) for i, ps in enumerate([1, 2, 3, 4])]
    return {"xi": xi, "bench": bench, "captain": xi[-1]["id"], "vice_captain": xi[-2]["id"],
            "meta": meta}


def _alatunniste(html: str) -> str:
    m = re.search(r'<div class="ftr">(.*?)</div>', html, re.S)
    assert m, "alatunniste puuttuu"
    return m.group(1)


def test_kortissa_ei_ole_rahalukua_vaikka_meta_kantaa_kentat():
    """Erotteleva fikstuuri: metassa ON molemmat kentat (22.9-version syote)."""
    meta = {"gw": 6, "frozen_at": "2026-10-09T05:00:00Z", "chip": None,
            "selling_value_tenths": 991, "bank_tenths": 12}
    html = card.build_html(_runko(meta), 6)
    ftr = _alatunniste(html)
    assert not RAHASANAT.search(ftr), ftr
    assert "99.1" not in html and "1.2m" not in html
    assert "data/model_squad_frozen/gw6.json" in ftr


def test_kortti_renderoityy_ilman_rahakenttia():
    """22.9-versio kaatoi ajon kun myyntiarvo puuttui (gw5.json). Nyt kentat
    eivat ole kortin syote lainkaan."""
    html = card.build_html(_runko({"gw": 5, "frozen_at": "2026-09-17T12:18:34Z"}), 5)
    assert not RAHASANAT.search(_alatunniste(html))


def test_kortin_koodi_ei_lue_rahakenttia():
    code = _code(SRC)
    assert "money_line" not in code
    assert "selling_value_tenths" not in code and "bank_tenths" not in code
    assert "squad_value_m" not in code
    assert "spent" not in code
    assert not re.search(r'sum\(\s*p\["price"\]', code), "rahaluku lasketaan taas nykyhinnoista"
