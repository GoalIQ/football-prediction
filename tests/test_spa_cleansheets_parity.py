# -*- coding: utf-8 -*-
"""SPA-CLEANSHEETS-PARITEETTI (30.8.2026): kolme vikaa `CleanSheets.svelte`:ssa.

Julkaisutarkistajan k2 loysi ne, ja kaikki kolme ovat samaa luokkaa kuin ne
jotka `/fpl`-sivulta oli juuri korjattu - SPA jai jalkeen:

1. **Vaara vaite ilmaispinnalla.** Copy lupasi *"the cell colour follows the
   same probability on a continuous scale"*, mutta `csCellClass` on kolme
   bucketia (>=44 gold, <=20 coral, muuten tyhja). Ei gradienttia.
2. **Pyoristysristiriita.** Luokka luettiin pyoristamattomasta arvosta, solu
   renderoi `Math.round`, joten 20,1 luki "20%" ilman coralia samalla kun
   caption lupaa "20% or less". Sivulla korjattu `838ed2a1d`, SPA ei.
3. **Double gameweekin pudotus.** `t.fixtures.find((x) => x.gw === gw)`
   palautti vain ensimmaisen ottelun, samalla kun Games-sarakkeen tooltip
   lupaa "2+ = double gameweek". SPA lupasi tasan sen mista sivun copy
   luopui.

Portti lukee Svelte-lahdetta tekstina, koska SPA:lla ei ole omaa
testiajuria. Se on karkea mutta EI sokea: jokaiselle vahdille on
negatiivinen kontrolli joka osoittaa etta se kaatuu vaarasta muodosta.

Ajo: .venv/Scripts/python -m pytest tests/test_spa_cleansheets_parity.py -q
"""
import re
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src" / "lib"
       / "components" / "CleanSheets.svelte")


@pytest.fixture(scope="module")
def s() -> str:
    assert SRC.exists(), f"{SRC} puuttuu - porttia ei voi todentaa (fail-closed)"
    return SRC.read_text(encoding="utf-8")


def _tiivis(t: str) -> str:
    return re.sub(r"\s+", " ", t)


# --- 1. varilupaus ----------------------------------------------------------

def test_copy_ei_lupaa_jatkuvaa_variskaalaa(s):
    assert "continuous scale" not in s, "gradienttilupaus on takaisin"


def test_copy_nimeaa_molemmat_kynnykset(s):
    t = _tiivis(s)
    assert "44% or more reads gold" in t
    assert "20% or less reads coral" in t


def test_copyn_kynnykset_vastaavat_koodin_kynnyksia(s):
    """🔴 Copy ja koodi samasta luvusta. Ilman tata kynnysta voi muuttaa
    koodissa ja copy jaa lupaamaan vanhaa (muisti: ehto-ei-vanhene)."""
    easy = re.search(r"if \(v >= (\d+)\) return 'is-easy'", s)
    hard = re.search(r"if \(v <= (\d+)\) return 'is-hard'", s)
    assert easy and hard, "csCellClassin kynnyksia ei loydy"
    t = _tiivis(s)
    assert f"{easy.group(1)}% or more reads gold" in t
    assert f"{hard.group(1)}% or less reads coral" in t


# --- 2. pyoristys -----------------------------------------------------------

def test_luokka_luetaan_pyoristetysta_arvosta(s):
    assert "const v = csRounded(csPct);" in s
    assert "if (v >= 44)" in s and "if (v <= 20)" in s


def test_solu_ja_luokka_kayttavat_samaa_pyoristysta(s):
    assert "{csRounded(f.cs_pct)}%" in s, "solu ei kayta jaettua pyoristysta"


def test_pyoristamaton_vertailu_on_poissa(s):
    """Negatiivinen kontrolli: juuri se muoto joka oli rikki."""
    assert "if (csPct >= 44)" not in s
    assert "Math.round(f.cs_pct)" not in s


# --- 3. double gameweek -----------------------------------------------------

def test_solu_ottaa_kaikki_kierroksen_ottelut(s):
    assert "t.fixtures.filter((x) => x.gw === gw)" in s


def test_find_ei_ole_enaa_kaytossa_soluvalinnassa(s):
    """Negatiivinen kontrolli: `find` on TASAN se joka pudotti doublen."""
    assert "t.fixtures.find((x) => x.gw === gw)" not in s


def test_molemmat_ottelut_renderoidaan(s):
    assert "{#each fs as f, i (" in s, "solu ei silmukoi otteluita"
    assert "dgw-sep" in s, "doublen erotinta ei ole"


def test_double_jatetaan_varittamatta_ja_se_sanotaan(s):
    """Kaksi ottelua voi vetaa eri suuntiin, joten yksi vari valehtelisi -
    ja varauksen on oltava SAMASSA paikassa kuin solu, ei muualla sivulla."""
    t = _tiivis(s)
    assert "fs.length === 1 && typeof fs[0].cs_pct === 'number'" in t
    assert "double gameweek, so the cell is left uncoloured" in t


def test_games_tooltipin_lupaus_on_yha_katettu(s):
    """Sarake lupaa "2+ = double gameweek"; solun on pystyttava nayttamaan se."""
    assert "2+ = double gameweek" in s
    assert "t.fixtures.filter" in s, "lupaus ilman katetta"
