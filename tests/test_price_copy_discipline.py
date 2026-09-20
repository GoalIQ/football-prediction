# -*- coding: utf-8 -*-
"""Portti: listahinta kirjoitetaan yhteen paikkaan, ei viiteen.

MITATTU 20.9.2026: sama hintalause oli kovakoodattuna viidessa paikassa
neljassa tiedostossa, jokainen omalla kirjoitusasullaan ("3.99 EUR a month",
"3.99 EUR/month", "EUR3.99 a month"). Hinnanmuutos olisi pitanyt muistaa
viidesta paikasta, ja unohtunut paikka olisi jaanyt vaittamaan vanhaa hintaa
maaramattomaksi ajaksi.

Tama testi lukee vain MERKKIJONOLITERAALEJA (ei kommentteja eika
docstringeja), joten hinnan selittaminen ei laukaise porttia mutta julkiseen
tekstiin paatyva luku laukaisee.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAHTEET = (ROOT / "scripts", ROOT / "src")

#: Hintaluku valuutan vieressa. Paljas "25" ei riita: se on liian yleinen
#: (kierrokset, prosentit, rivimaarat) ja portti joka kaatuu joka toisesta
#: rivista lakkaa merkitsemasta mitaan.
HINTA_RE = re.compile(
    r"(?:€|EUR)\s?(?:3[.,]99|25(?:[.,]00)?)\b"
    r"|(?:3[.,]99|25(?:[.,]00)?)\s?(?:€|EUR)\b")

#: Poikkeukset perusteluineen (CLAUDE.md 6a kohta 2).
POIKKEUKSET = {
    "src/price_copy.py": "taalla luku ASUU - se on koko pointti",
    "scripts/set_regional_prices.py":
        "varoitusteksti kertoo listahinnan suhteen aluehintaan; se on "
        "kehittajalle terminaaliin, ei julkista copya",
    "scripts/check_free_window.py":
        "ilmaisikkunan portti etsii sivuilta hintalupauksia, eli luku on "
        "sen HAKUKUVIO eika sen oma vaite",
}


def _literaalit(path: Path) -> list[str]:
    try:
        puu = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    docstringit = set()
    for n in ast.walk(puu):
        body = getattr(n, "body", None)
        if (isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            docstringit.add(id(body[0].value))
    return [n.value for n in ast.walk(puu)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstringit]


def _tiedostot() -> list[Path]:
    return sorted(p for juuri in LAHTEET for p in juuri.rglob("*.py"))


def test_hintaa_ei_kirjoiteta_kasin_julkiseen_tekstiin():
    loydot: dict[str, list[str]] = {}
    for p in _tiedostot():
        rel = p.relative_to(ROOT).as_posix()
        if rel in POIKKEUKSET:
            continue
        osumat = [s[:90] for s in _literaalit(p) if HINTA_RE.search(s)]
        if osumat:
            loydot[rel] = osumat[:3]
    assert not loydot, (
        "listahinta kovakoodattuna julkiseen tekstiin: "
        f"{loydot}. Kayta src/price_copy.py:ta (MONTHLY / SEASON / LOCAL_NOTE). "
        "Jos luku on tosi juuri tassa eika se ole julkista copya, lisaa "
        "tiedosto POIKKEUKSET-listalle PERUSTELUN kanssa.")


def test_poikkeuksella_on_perustelu_ja_kohde():
    for rel, syy in POIKKEUKSET.items():
        assert str(syy).strip(), f"{rel}: poikkeukselle ei ole syyta"
        assert (ROOT / rel).exists(), f"{rel}: osoittaa tiedostoon jota ei ole"


def test_skanneri_loytaa_istutetun_hinnan(tmp_path):
    """Ilman tata portti voisi olla koriste."""
    f = tmp_path / "x.py"
    f.write_text('"""25 EUR a year"""\nX = "Premium is 25 EUR a year"\n',
                 encoding="utf-8")
    litt = _literaalit(f)
    assert any(HINTA_RE.search(s) for s in litt), litt
    assert not any(s.strip() == "25 EUR a year" for s in litt), \
        "docstringin pitaa jaada pois"


@pytest.mark.parametrize("teksti,osuu", [
    ("3.99 EUR a month", True), ("EUR3.99 a month", True),
    ("25 EUR a year", True), ("€25 a year", True),
    ("25 gameweeks", False), ("top 25", False), ("3.99", False),
])
def test_kuvio_ei_ole_liian_ahne(teksti, osuu):
    assert bool(HINTA_RE.search(teksti)) is osuu, teksti


# --- julkaistut pinnat: sama luku joka paikassa ---------------------------

from src import price_copy as PC  # noqa: E402

#: Pinnat joilla hinta nakyy lukijalle tai koneelle.
PINNAT = ("fpl.html", "index.html", "predictions.html", "llms.txt")

#: JSON-LD:n `"price": "25"` ei osu HINTA_RE:hen (valuutta on omassa
#: kentassaan), ja juuri se paasi 20.9 lapi literaaliskannista. Siksi
#: julkaistu artefakti tarkistetaan erikseen.
JSONLD_PRICE_RE = re.compile(r'"price":\s*"([0-9]+(?:\.[0-9]+)?)"')
COPY_PRICE_RE = re.compile(
    r"(?:€|&euro;|EUR)\s?([0-9]+(?:[.,][0-9]{2})?)\b"
    r"|([0-9]+(?:[.,][0-9]{2})?)\s?(?:€|&euro;|EUR)\b")


def _sallitut() -> set[str]:
    return {PC.MONTHLY, PC.SEASON, PC.season_monthly_cap(), "0",
            PC.SEASON + ".00", PC.MONTHLY.replace(".", ",")}


@pytest.mark.parametrize("pinta", PINNAT)
def test_julkaistu_pinta_kayttaa_samaa_lukua(pinta):
    p = ROOT / pinta
    if not p.exists():
        pytest.skip(f"{pinta} ei ole generoitu")
    teksti = p.read_text(encoding="utf-8", errors="replace")
    loydot = set(JSONLD_PRICE_RE.findall(teksti))
    for a, b in COPY_PRICE_RE.findall(teksti):
        loydot.add((a or b).replace(",", "."))
    vieraat = {x for x in loydot if x not in _sallitut()}
    assert not vieraat, (
        f"{pinta}: hintaluku joka ei tule src/price_copy.py:sta: "
        f"{sorted(vieraat)}. Sallitut: {sorted(_sallitut())}. "
        "Kaksi pintaa samasta luvusta on kaksi tilaisuutta olla eri mielta.")


def test_aluehinnan_varaus_on_jokaisella_hintapinnalla():
    """Aluehinta on paalla 20.9 alkaen. Pinta joka mainitsee hinnan mutta ei
    varausta vaittaa yhta hintaa kaikille."""
    puuttuu = []
    for pinta in PINNAT:
        p = ROOT / pinta
        if not p.exists():
            continue
        teksti = p.read_text(encoding="utf-8", errors="replace")
        if not COPY_PRICE_RE.search(teksti):
            continue
        if PC.LOCAL_NOTE not in teksti:
            puuttuu.append(pinta)
    assert not puuttuu, (
        f"hinta mainitaan mutta aluehinnan varaus puuttuu: {puuttuu}")
