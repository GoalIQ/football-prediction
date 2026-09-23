"""KORTTI-PENKIN-SAATAVUUSMERKKI (23.9.2026): mallin jakokortti merkitsee
FPL:n saatavuuden, ja status kirjataan freezeen jaadytyshetkella.

Julkaisutarkistajan loydos 18.9: GW5-kortissa Oliver Dovin nakyi tavallisena
penkkilaisena hintaan 4.0m, vaikka FPL sanoi `status u` ("Has joined Leyton
Orient on loan for the rest of the season"). Kortin ainoa sallittu lahde on
freeze, ja freeze ei kantanut statusta. Kortti on pysyva kuva.

Mekanismit (CLAUDE.md 6a):
  (1) kirjoittaja: `slim(p, gw, *, element=...)` on pakollinen avainsana,
      joten freeze ei voi unohtaa saatavuutta.
  (2) lukija: `availability_mark` kaataa ajon kun status puuttuu (fail-closed),
      eli merkitsematon pelaaja ei paase kuvaan.
  (3) vaiheet: jokainen FPL-status (a, d 25/50/75, d ilman prosenttia,
      i/s/u/n), XI ja penkki.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import freeze_model_squad_gw as freeze  # noqa: E402
import render_frozen_squad_card as card  # noqa: E402

FREEZE_SRC = (ROOT / "scripts" / "freeze_model_squad_gw.py").read_text(encoding="utf-8")


def _pool_row(pid=171, name="Dovin"):
    return {"id": pid, "web_name": name, "team_short": "COV", "element_type": 1,
            "club": 7, "price": 40, "gameweeks": [{"gw": 6, "xp": 0.0}]}


DOVIN_EL = {"id": 171, "status": "u", "chance_of_playing_next_round": 0,
            "news": "Has joined Leyton Orient on loan for the rest of the season"}


# ---------------------------------------------------------------- kirjoittaja
def test_slim_kirjaa_fpln_saatavuuden_jaadytyshetkella():
    row = freeze.slim(_pool_row(), 6, element=DOVIN_EL)
    assert row["status"] == "u"
    assert row["chance"] == 0
    assert row["news"].startswith("Has joined Leyton Orient")


def test_slim_ilman_bootstrap_rivia_on_tuntematon_eika_terve():
    """Puuttuva bootstrap-rivi EI ole 'a' (nolla ei ole sama kuin ei tietoa)."""
    row = freeze.slim(_pool_row(), 6, element=None)
    assert row["status"] is None


def test_slim_element_on_pakollinen():
    with pytest.raises(TypeError):
        freeze.slim(_pool_row(), 6)  # type: ignore[call-arg]


def test_freeze_main_antaa_jokaiselle_riville_bootstrapin_rivin():
    """Kutsupaikka: xi ja bench kirjoitetaan slimilla, jolle annetaan saman
    pelaajan bootstrap-rivi (muisti testi-kutsuu-funktiota-ei-kutsupaikkaa)."""
    calls = [n for n in ast.walk(ast.parse(FREEZE_SRC))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "slim"]
    assert len(calls) == 2, "uusi slim-kutsupaikka: anna sille bootstrapin rivi"
    for c in calls:
        kw = {k.arg: ast.unparse(k.value) for k in c.keywords}
        assert kw.get("element") == "_el_by_id.get(p['id'])"
    assert re.search(r'_el_by_id = \{e\["id"\]: e for e in \(_bootstrap or \{\}\)'
                     r'\.get\("elements"\)', FREEZE_SRC)


# ---------------------------------------------------------------- lukija
@pytest.mark.parametrize("status,chance,expect", [
    ("d", 75, "75%"), ("d", 50, "50%"), ("d", 25, "25%"), ("d", None, "doubt"),
    ("i", 0, "out"), ("s", 0, "out"), ("u", 0, "out"), ("n", None, "out"),
])
def test_jokainen_ei_terve_status_merkitaan(status, chance, expect):
    mark = card.availability_mark({"web_name": "X", "id": 1,
                                   "status": status, "chance": chance})
    assert f">{expect}</em>" in mark


def test_terve_ei_saa_merkkia():
    assert card.availability_mark({"status": "a", "chance": None}) == ""


@pytest.mark.parametrize("row", [
    {"id": 171, "web_name": "Dovin", "price": 40},          # GW5-muoto: ei avainta
    {"id": 171, "web_name": "Dovin", "price": 40, "status": None},
])
def test_puuttuva_saatavuus_kaataa_ajon(row):
    with pytest.raises(SystemExit):
        card.availability_mark(row)


def test_gw5_freeze_ei_renderoidy_merkitsemattomana():
    """DoD-fikstuuri: oikea gw5.json (jaadytetty 17.9, Dovin status u)."""
    gw5 = ROOT / "data" / "model_squad_frozen" / "gw5.json"
    if not gw5.exists():
        pytest.skip("gw5.json puuttuu")
    frozen = json.loads(gw5.read_text(encoding="utf-8"))
    dovin = next(p for p in frozen["bench"] if p["id"] == 171)
    assert "status" not in dovin, "fikstuuri ei ole enaa erotteleva"
    with pytest.raises(SystemExit):
        card.cell(dovin, cap=-1, vice=-1, size=42)


def test_penkin_ja_xin_solu_kantaa_merkin():
    """Molemmat rivit kulkevat cell()in lapi: merkki on solussa itsessaan."""
    row = {"id": 171, "web_name": "Dovin", "team_short": "COV", "pos": 1,
           "price": 40, "status": "u", "chance": 0}
    html = card.cell(row, cap=-1, vice=-1, size=42)
    assert 'COV · 4.0m · <em class="flag out">out</em></span>' in html
    xi_row = dict(row, id=5, web_name="Gabriel", team_short="ARS", pos=2,
                  status="d", chance=75)
    assert 'ARS · 4.0m · <em class="flag d">75%</em></span>' in card.cell(xi_row, cap=5, vice=6)


def test_kirjoittaja_ja_lukija_samat_kentat():
    """Freeze kirjoittaa `status`/`chance`, kortti lukee samat avaimet."""
    src = (ROOT / "scripts" / "render_frozen_squad_card.py").read_text(encoding="utf-8")
    assert 'p.get("status")' in src and 'p.get("chance")' in src
    assert '"status": el.get("status")' in FREEZE_SRC
    assert '"chance": el.get("chance_of_playing_next_round")' in FREEZE_SRC


# ---------------------------------------------------------------- julkaisutarkistaja k1 (23.9)
@pytest.mark.parametrize("status,chance,expect", [
    ("a", 75, ">75%</em>"),     # prosentti voittaa statuksen
    ("i", 50, ">50%</em>"),
    ("d", 0, ">out</em>"),
    ("d", 100, ""),
])
def test_prosentti_ratkaistaan_ensin(status, chance, expect):
    mark = card.availability_mark({"id": 1, "web_name": "X", "status": status,
                                   "chance": chance})
    assert (expect in mark) if expect else mark == ""


def _p(status="a", chance=None):
    return {"id": 1, "web_name": "X", "status": status, "chance": chance}


def test_alaotsikko_kertoo_etta_liput_ovat_jaadytyshetkelta():
    """Lippu ilman hetkea on vaite (muisti lippu-ilman-kierrosta-on-vaite)."""
    sub = card.subtitle([_p(), _p("u", 0)], "17 Sep", None)
    assert sub == ("Picked by the optimiser and frozen 17 Sep, FPL flags too. "
                   "We score it exactly as frozen.")


def test_ilman_merkkeja_alaotsikko_ennallaan():
    sub = card.subtitle([_p(), _p("d", 100)], "17 Sep", None)
    assert sub == "Picked by the optimiser and frozen 17 Sep. We score it exactly as frozen."


def test_ohitus_ei_pudota_lippulausetta_hiljaa():
    with pytest.raises(SystemExit):
        card.subtitle([_p("d", 75)], "17 Sep", "Rebuilt on deadline day.")
    ok = card.subtitle([_p("d", 75)], "17 Sep", "Rebuilt on deadline day, FPL flags too.")
    assert "flags" in ok
    assert card.subtitle([_p()], "17 Sep", "Rebuilt on deadline day.") == "Rebuilt on deadline day."


def test_kutsupaikka_kayttaa_alaotsikkoa_nakyvista_pelaajista():
    src = (ROOT / "scripts" / "render_frozen_squad_card.py").read_text(encoding="utf-8")
    assert "subtitle(xi + ([] if args.hide_bench else bench), frozen_at, args.subtitle)" in src
    assert "Picked by the optimiser and frozen {frozen_at}. We score" not in src.split("def subtitle")[0]


def test_hintarivi_ei_rivity():
    """Penkin 96 px solu rivitti 'AVL · 4.5m ·' / 'doubt' (tarkistaja 23.9)."""
    assert "font-variant-numeric:tabular-nums;white-space:nowrap;}" in card.CSS
