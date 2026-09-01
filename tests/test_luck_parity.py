# -*- coding: utf-8 -*-
"""LUCK-PITCH: kynnysten pariteetti SPA:n ja mobiilin valilla (1.9.2026).

Sama saanto ajetaan kolmella pinnalla: mobiilin pitch
(`goaliq-app/lib/fantasyDisplay.ts`), taman repon SPA (`$lib/luck`) ja
jakokortit. Mobiili on toisessa reposssa eika ole luettavissa taalta, joten
tama testi pinnaa TAMAN pinnan kanoniseen lukuun: jos joku viilaa kynnysta
vain toisella pinnalla, testi kaatuu ja pakottaa kirjaamaan muutoksen molempiin.

Kanoniset luvut ovat MITATTUJA (GW1-GW2, 607 pelaaja-kierrosta joilla on
seka deadline-freeze etta toteuma), eivat valittuja:

    yli   poikkeama >= +6.0     43 osumaa
    alle  poikkeama <= -2.5     48 osumaa
    yhteensa 1,6 merkkia XI:ta kohti

Epasymmetria on tarkoitus: alisuoritus on rajattu (pisteita ei voi olla alle
nollan) mutta ylisuoritus ei, joten sama luku molempiin suuntiin antaisi lahes
pelkkia yli-merkkeja (K=4 symmetrisena: 75 yli, 2 alle).

Edellinen versio vertasi absoluuttisiin rajoihin (10 / 2 / xP 5.0). Se oli
skaalavirhe: xP >= 5.0 tayttyi 4 kertaa 607:sta ja suurin freeze oli 5.78,
joten tuomio "malli osui" ei laukennut kertaakaan ja merkin sai 61 %
pelaajista. Se korjattiin 1.9 mittaamalla, ei arvaamalla uudelleen.
"""
import re
from pathlib import Path

import pytest

LUCK_TS = Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src" / "lib" / "luck.ts"

CANON = {"LUCK_OVER_DIFF": 6, "LUCK_UNDER_DIFF": 2.5}


def _constants(src: str) -> dict[str, int]:
    out = {}
    for name in CANON:
        m = re.search(rf"export const {name} = (-?\d+(?:\.\d+)?);", src)
        if m:
            out[name] = float(m.group(1))
    return out


def test_luck_module_exists():
    assert LUCK_TS.is_file(), f"puuttuu: {LUCK_TS}"


def test_kynnykset_ovat_kanonisia():
    got = _constants(LUCK_TS.read_text(encoding="utf-8"))
    assert got == pytest.approx(CANON), (
        "SPA:n luck-kynnykset eroavat kanonisista. Jos muutos on tarkoitettu, "
        "muuta MOLEMMAT pinnat (mobiili lib/fantasyDisplay.ts) ja tama testi."
    )


def test_negatiivinen_kontrolli_havaitsee_muutetun_kynnyksen():
    """Portti joka lapaisee kaiken ei ole portti."""
    mutated = LUCK_TS.read_text(encoding="utf-8").replace(
        "export const LUCK_OVER_DIFF = 6;", "export const LUCK_OVER_DIFF = 7;"
    )
    assert _constants(mutated)["LUCK_OVER_DIFF"] == 7
    assert _constants(mutated) != pytest.approx(CANON)


def test_vertailusuunnat_ovat_inklusiivisia():
    """Rajalla tasan oleva pelaaja saa tuomion. `>` ja `<` pudottaisivat sen
    hiljaa: merkki vain puuttuisi eika mikaan huutaisi."""
    src = LUCK_TS.read_text(encoding="utf-8")
    assert "diff >= LUCK_OVER_DIFF" in src
    assert "diff <= -LUCK_UNDER_DIFF" in src


def test_kynnykset_ovat_epasymmetriset():
    """NEGATIIVINEN KONTROLLI mittaukselle. Symmetrinen kynnys tuottaisi
    jakauman 75 yli / 2 alle eli kaytannossa vain yhden tuomion."""
    got = _constants(LUCK_TS.read_text(encoding="utf-8"))
    assert got["LUCK_OVER_DIFF"] != got["LUCK_UNDER_DIFF"]


def test_tuomio_lasketaan_poikkeamasta_ei_absoluuttisesta_pistemaarasta():
    """Skaalavirhe joka mitattiin 1.9: xP:n mediaani ~2, huippu 5.78, kun
    FPL:n "haul" on 10+. Absoluuttinen pisteraja ei voi toimia tuomiona."""
    src = LUCK_TS.read_text(encoding="utf-8")
    assert "const diff = actual - xp;" in src
    assert "LUCK_HAUL_PTS" not in src, "vanha absoluuttinen kynnys palasi"
    assert "LUCK_HIGH_XP" not in src, "vanha xP-seina palasi"


def test_kaksi_tuomiota_eika_nelja():
    """"Malli osui" ja "ansaittu nolla" poistettiin mittauksen perusteella:
    ensimmainen ei laukennut kertaakaan 607 havainnossa, toinen osui 125
    kertaa 151:sta eli oli perustaso. Jos ne palaavat ilman uutta mittausta,
    tama kaatuu."""
    src = LUCK_TS.read_text(encoding="utf-8")
    for verdict in ("lucky", "robbed"):
        assert f"'{verdict}'" in src, f"tuomio {verdict} puuttuu"
        assert f"{verdict}:" in src, f"merkki tuomiolle {verdict} puuttuu"
    for gone in ("called", "cold"):
        assert f"'{gone}'" not in src, f"poistettu tuomio {gone} palasi"


def test_tyhja_rivi_ei_tuota_nollasummaa():
    """`squadLuck([]) -> null`, koska 0 pistetta / 0 xP olisi vaite
    kierroksesta jota ei ole pelattu."""
    src = LUCK_TS.read_text(encoding="utf-8")
    assert "if (rows.length === 0) return null;" in src
