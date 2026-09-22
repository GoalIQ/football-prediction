"""FROZEN-KORTTI-RAHALUKU-VAARIN (22.9.2026): mallin jakokortin raharivi FPL:n
omista luvuista, ei nykyhintojen summasta.

Mitattu 18.9: `render_frozen_squad_card.py` tulosti "<summa>m spent" aina kun
`meta.squad_value_m` puuttui, ja freeze ei ollut koskaan kirjoittanut sita:
GW5 "99.8m spent" kun myyntiarvo oli 99.1m. 4.9:n portti oli jo tuominnut
sanamuodon (ostohinnat eivat ole julkisia).

Kortti on pysyva kuva (julkinen teksti), joten puuttuva kentta kaataa ajon.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import render_frozen_squad_card as card  # noqa: E402

SRC = (ROOT / "scripts" / "render_frozen_squad_card.py").read_text(encoding="utf-8")


def _code(src: str) -> str:
    """Kommentit ja docstringit pois, jotta perustelu ei kay koodista."""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    return "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())


def test_fpln_omat_luvut_myyntiarvo_ja_pankki():
    assert card.money_line({"selling_value_tenths": 991, "bank_tenths": 12}) == (
        "<b>99.1m</b> selling value · 1.2m in the bank")


def test_pankki_puuttuu_rivi_ilman_pankkia():
    assert card.money_line({"selling_value_tenths": 1000}) == "<b>100.0m</b> selling value"


@pytest.mark.parametrize("meta", [{}, {"selling_value_tenths": None},
                                  {"squad_value_m": 99.8}, {"selling_value_tenths": "991"}])
def test_puuttuva_myyntiarvo_kaataa_ajon(meta):
    with pytest.raises(SystemExit):
        card.money_line(meta)


def test_gw5_freeze_ilman_kenttia_ei_renderoidy_spent_luvulla():
    """DoD-fikstuuri: oikea gw5.json (jaadytetty 17.9 ennen kenttia)."""
    gw5 = ROOT / "data" / "model_squad_frozen" / "gw5.json"
    if not gw5.exists():
        pytest.skip("gw5.json puuttuu")
    meta = json.loads(gw5.read_text(encoding="utf-8")).get("meta") or {}
    assert meta.get("selling_value_tenths") is None, "fikstuuri ei ole enaa erotteleva"
    with pytest.raises(SystemExit):
        card.money_line(meta)


def test_kutsupaikka_lukee_money_linea_eika_laske_nykyhinnoista():
    code = _code(SRC)
    assert "money = money_line(meta_val)" in code
    assert "{money}" in code
    assert "spent" not in code, "'spent'-sanamuoto palasi kortin koodiin"
    assert not re.search(r'sum\(\s*p\["price"\]', code), "rahaluku lasketaan taas nykyhinnoista"


def test_kirjoittaja_ja_lukija_samat_kentat():
    """Freeze on kenttien AINOA kirjoittaja (attach_entry_state)."""
    freeze = (ROOT / "scripts" / "freeze_model_squad_gw.py").read_text(encoding="utf-8")
    assert 'meta["selling_value_tenths"] = int(' in freeze
    assert 'meta["bank_tenths"] = int(' in freeze
