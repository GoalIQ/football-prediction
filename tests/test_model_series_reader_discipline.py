# -*- coding: utf-8 -*-
"""Portti: pinta ei voi lukea mallin kierrospisteita ohi julkisen lukijan.

TAUSTA (21.9.2026, Villen paatos "mallin rivi"). Mallin pisteita luki
KOLME pintaa suoraan tiedostosta `data/model_squad_gw_scores.json`:
`/api/fantasy/model-race` (Season race), `scripts/build_gw_recap.py`
(track record, gw_recap.json) ja `fpl_rate_team.model_squad_gw`
(tuloskortti + SPA:n "Model · entry" -solu). Jokainen paatti itse mika
sarja on mallin luku. Kun paatos vaihtui entrysta jaadytettyyn riviin,
kolme paikkaa olisi pitanyt muistaa muuttaa - ja neljas pinta olisi
lukenut vanhaa sarjaa hiljaa.

SAANTO 6a kohta 1 + 2: yksi lukija (`load_public_model_series`) ja
poikkeuslista perusteluineen. Tama testi kavelee api/, src/ ja scripts/
-hakemistojen AST:n ja kaatuu jos sarjatiedoston nimi (merkkijonona, ei
docstringissa) tai sarjan matalan tason lukijan nimi esiintyy muualla kuin
poikkeuslistan tiedostoissa.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKANNATTAVAT = ("api", "src", "scripts")

#: Merkkijonot jotka ovat sarjatiedostojen nimia.
TIEDOSTONIMET = ("model_squad_gw_scores.json", "model_squad_frozen_gw_scores.json")
#: Matalan tason nimet joilla sarjan voi lukea ohi julkisen lukijan.
MATALAT_NIMET = ("ENTRY_SCORES_PATH", "FROZEN_SCORES_PATH", "SERIES_PATHS",
                 "load_gw_scores")

#: Tiedosto -> miksi sen on lupa kasitella sarjoja suoraan.
POIKKEUKSET: dict[str, str] = {
    "src/models/model_squad_scores.py":
        "lukija itse: maarittelee polut ja julkisen sarjan",
    "scripts/grade_model_squad.py":
        "entry-sarjan ainoa kirjoittaja (lukee oman sarjansa ennen kirjoitusta)",
    "scripts/grade_model_squad_gw.py":
        "jaadytetyn sarjan ainoa kirjoittaja (lukee oman sarjansa ennen "
        "kirjoitusta)",
}

#: Pinnat joiden ON luettava julkinen sarja (kutsupaikkaportti).
JULKISET_PINNAT = ("api/main.py", "scripts/build_gw_recap.py",
                   "src/models/fpl_rate_team.py")


def _docstring_solmut(puu: ast.AST) -> set[int]:
    ids = set()
    for n in ast.walk(puu):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)) and n.body:
            eka = n.body[0]
            if (isinstance(eka, ast.Expr) and isinstance(eka.value, ast.Constant)
                    and isinstance(eka.value.value, str)):
                ids.add(id(eka.value))
    return ids


def _osumat(polku: Path) -> list[str]:
    puu = ast.parse(polku.read_text(encoding="utf-8"))
    docit = _docstring_solmut(puu)
    ulos = []
    for n in ast.walk(puu):
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docit):
            for nimi in TIEDOSTONIMET:
                if nimi in n.value:
                    ulos.append(f"r{n.lineno}: merkkijono {nimi!r}")
        elif isinstance(n, ast.Name) and n.id in MATALAT_NIMET:
            ulos.append(f"r{n.lineno}: nimi {n.id}")
        elif isinstance(n, ast.Attribute) and n.attr in MATALAT_NIMET:
            ulos.append(f"r{n.lineno}: attribuutti .{n.attr}")
        elif isinstance(n, ast.alias) and n.name in MATALAT_NIMET:
            ulos.append(f"import {n.name}")
    return ulos


def _kaikki_osumat() -> dict[str, list[str]]:
    out = {}
    for hak in SKANNATTAVAT:
        for p in sorted((ROOT / hak).rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            o = _osumat(p)
            if o:
                out[rel] = o
    return out


def test_sarjoja_lukee_vain_poikkeuslistan_tiedosto():
    osumat = _kaikki_osumat()
    luvattomat = {k: v for k, v in osumat.items() if k not in POIKKEUKSET}
    assert not luvattomat, (
        "Mallin kierrossarja luetaan ohi julkisen lukijan: "
        f"{luvattomat}. Kayta model_squad_scores.load_public_model_series():a "
        "(tai provisional_hint_gws():a lopullisuusvihjeeseen). Jos tiedoston "
        "on oikeasti kasiteltava sarjaa suoraan, lisaa se POIKKEUKSET-listaan "
        "PERUSTELUN kanssa.")


def test_poikkeuslista_ei_vanhene():
    """Poikkeus jota ei enaa tarvita on vartija joka vartioi tyhjaa."""
    osumat = _kaikki_osumat()
    turhat = [k for k in POIKKEUKSET if k not in osumat]
    assert not turhat, f"poikkeuslistalla tiedostoja joita ei tarvita: {turhat}"
    for k, syy in POIKKEUKSET.items():
        assert len(syy) > 20, f"{k}: perustelu puuttuu"


@pytest.mark.parametrize("pinta", JULKISET_PINNAT)
def test_julkinen_pinta_kutsuu_julkista_lukijaa(pinta):
    """Kutsupaikka: pinta joka ei lue mitaan ei riko ylempaa porttia, joten
    lukijan kaytto mitataan erikseen."""
    puu = ast.parse((ROOT / pinta).read_text(encoding="utf-8"))
    nimet = {n.id for n in ast.walk(puu) if isinstance(n, ast.Name)}
    nimet |= {a.name for n in ast.walk(puu) if isinstance(n, ast.ImportFrom)
              for a in n.names}
    assert "load_public_model_series" in nimet, (
        f"{pinta} ei lue julkista mallisarjaa")


def test_skanneri_nakee_raa_an_luvun():
    """Erotteleva kontrolli: synteettinen pinta joka lukee entry-sarjan
    suoraan loytyy. Ilman tata portti voisi olla vihrea tyhjaa vasten."""
    import tempfile
    lahde = ('"""docstring model_squad_gw_scores.json on sallittu"""\n'
             'from pathlib import Path\n'
             'P = Path("data") / "model_squad_gw_scores.json"\n'
             'from src.models.model_squad_scores import ENTRY_SCORES_PATH\n')
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pinta.py"
        p.write_text(lahde, encoding="utf-8")
        o = _osumat(p)
    assert any("merkkijono" in x for x in o), o
    assert any("ENTRY_SCORES_PATH" in x for x in o), o
    assert not any("r1:" in x for x in o), "docstring ei saa laueta"
