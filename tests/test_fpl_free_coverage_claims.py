"""Portti: pysyva kuva tai video ei saa vaittaa ilmaissivusta enempaa kuin siella on.

MITATTU VIKA (20.9.2026):

    scripts/gen_share_card.py  render_gw_outlook       17.9 korjattu
    scripts/gen_share_card.py  render_gw_outlook_hero  "All 20 teams, every gameweek"  <- livena
    scripts/gen_reel.py        card_clean_sheets       "Every team, every gameweek"    <- livena

17.9 julkaisuportti hylkasi sanamuodon joka vaitti /fpl:n ilmaispinnasta
enemman kuin sivulla on, ja hylkays kirjattiin `data/rejected_phrases.json`:iin
MERKKIJONONA ("both columns, on goaliq.app/fpl"). Saman tiedoston sisarfunktio
ja reel-generaattori sanoivat saman vaitteen eri sanoin, joten merkkijonoportti
ei nahnyt niita. Kortti ja video ovat pysyvia: ne leviavat ilman linkkia ja
ilman tasmennysta, joten niissa vaite on tarkistettava sellaisenaan.

Tama portti tekee kolme asiaa:
  1. mittaa SIVUSTA etta kate on yha se jonka `src/fpl_free_coverage.py`
     vaittaa (jos sivu kasvaa, testi kaataa ja luvut paivitetaan lukijaan),
  2. skannaa korttipinnat: horisonttisanoja ei kirjoiteta kasin,
  3. varmistaa etta kortit oikeasti KUTSUVAT lukijaa - muuten korjaus voi
     palata kovakoodatuksi merkkijonoksi ilman etta portti huomaa.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from src.fpl_free_coverage import (
    CARD_SURFACES,
    CLEAN_SHEET_GAMEWEEKS,
    HORIZON_OVERCLAIMS,
    POIKKEUKSET,
    PROJECTED_GOALS_MENTIONS,
    fpl_free_claim,
)

ROOT = Path(__file__).resolve().parents[1]
SIVU = ROOT / "fpl.html"
GW_OTSIKKO = re.compile(r"<th[^>]*>GW(\d+)</th>")


def _docstring_idt(tree: ast.AST) -> set[int]:
    out = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            out.add(id(body[0].value))
    return out


def _literaalit(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_idt(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


# --- 1. kate mitataan sivusta, ei muistista (saanto 6a kohta 3) -------------

def test_ilmaissivu_ei_kata_kaikkia_kierroksia() -> None:
    """Jos /fpl alkaa kattaa enemman, TAMA kaatuu eika kortti jaa vanhaksi."""
    teksti = SIVU.read_text(encoding="utf-8", errors="replace")
    gws = GW_OTSIKKO.findall(teksti)
    assert gws, ("fpl.html:ssa ei ole yhtaan kierroskohtaista GW-otsikkoa - "
                 "joko sivun rakenne muuttui tai portti mittaa vaaraa asiaa")
    assert len(gws) <= CLEAN_SHEET_GAMEWEEKS, (
        f"fpl.html nayttaa nollapeli-%:n {len(gws)} kierrokselle, mutta "
        f"src/fpl_free_coverage.py vaittaa enintaan {CLEAN_SHEET_GAMEWEEKS}. "
        "Paivita lukija, ala korttia.")


def test_maaliluku_on_vain_seuraavasta_ottelusta() -> None:
    teksti = SIVU.read_text(encoding="utf-8", errors="replace")
    osumat = teksti.count("projected goals")
    assert osumat <= PROJECTED_GOALS_MENTIONS, (
        f"'projected goals' esiintyy {osumat} kertaa (yli "
        f"{PROJECTED_GOALS_MENTIONS} = kerran per joukkue). Sivu on ehka "
        "saanut kierroskohtaisen maaligridin -> `fpl_free_claim` voi "
        "vihdoin luvata horisontin myos maaleista. Paivita lukija.")


# --- 2. vaite seuraa kortin sisaltoa ---------------------------------------

def test_vaite_seuraa_kortin_sisaltoa() -> None:
    vain_cs = fpl_free_claim(projected_goals=False)
    molemmat = fpl_free_claim(projected_goals=True)
    assert vain_cs != molemmat, (
        "sama vaite molemmille sisalloille -> toinen niista on epatosi")
    assert "six gameweeks" in vain_cs, vain_cs
    for sana in HORIZON_OVERCLAIMS:
        assert sana not in molemmat.lower(), (
            f"{molemmat!r} vaittaa horisonttia, mutta kortissa on kaksi lukua "
            "joilla on ERI horisontti (nollapeli kuusi kierrosta, maalit "
            "seuraava ottelu)")


# --- 3. horisonttisanaa ei kirjoiteta kasin korttipinnalle ------------------

@pytest.mark.parametrize("rel", CARD_SURFACES)
def test_korttipinta_ei_kirjoita_horisonttia_kasin(rel: str) -> None:
    path = ROOT / rel
    assert path.exists(), f"{rel}: portti osoittaa tiedostoon jota ei ole"
    litt = _literaalit(path)
    for sana in HORIZON_OVERCLAIMS:
        osumat = [s for s in litt if sana in s.lower()]
        if not osumat:
            continue
        syy = POIKKEUKSET.get(f"{rel}::{sana}")
        assert syy, (
            f"{rel}: kovakoodattu {sana!r} ({osumat[:2]}). Ilmaissivu kattaa "
            f"nollapeli-%:n enintaan {CLEAN_SHEET_GAMEWEEKS} kierrokselle ja "
            "maaliluvun vain seuraavasta ottelusta, eika pysyva kuva voi "
            "kantaa tasmennysta joka tekisi laajemmasta vaitteesta toden. "
            "Kayta src.fpl_free_coverage.fpl_free_claim(). Jos vaite on tosi "
            "juuri tassa, lisaa POIKKEUKSET-listalle PERUSTELUN kanssa.")


def test_poikkeuksella_on_perustelu_ja_kohde() -> None:
    for avain, syy in POIKKEUKSET.items():
        assert str(syy).strip(), f"{avain}: poikkeukselle ei ole syyta"
        rel = avain.split("::", 1)[0]
        assert (ROOT / rel).exists(), f"{avain}: osoittaa tiedostoon jota ei ole"


# --- 4. korjaus ei saa palata kovakoodatuksi (kutsupaikka, ei vain funktio) -

@pytest.mark.parametrize("rel", ["scripts/gen_share_card.py", "scripts/gen_reel.py"])
def test_kortti_kutsuu_lukijaa(rel: str) -> None:
    """Muisti `testi-kutsuu-funktiota-ei-kutsupaikkaa`: ilman tata kortin voi
    kirjoittaa takaisin kasin ja portti olisi vihrea, koska tuloksena oleva
    merkkijono ei satu sisaltamaan kiellettya sanaa."""
    lahde = (ROOT / rel).read_text(encoding="utf-8")
    assert "fpl_free_claim(" in lahde, (
        f"{rel} ei kutsu fpl_free_claim():a - ilmaissivun kate on taas kasin "
        "kirjoitettu proosaa")


# --- 5. negatiivinen kontrolli: skanneri nakee istutetun osuman -------------

def test_negatiivinen_kontrolli_skanneri_nakee_literaalin(tmp_path) -> None:
    f = tmp_path / "x.py"
    f.write_text('"""every gameweek"""\nX = "All 20 teams, every gameweek"\n',
                 encoding="utf-8")
    litt = _literaalit(f)
    assert any("every gameweek" in s for s in litt), litt
    assert not any(s.strip() == "every gameweek" for s in litt), (
        "docstringin pitaa jaada pois, muuten hylkayksen selittaminen "
        "laukaisee portin")
