"""LUCK-PITCH-tuloskortin lauseet: mobiili ja SPA sanovat saman (2.9.2026).

Julkaisutarkistaja hylkasi kortin tekstin kolmella kierroksella, ja jokainen
korjaus piti tehda kahteen tiedostoon kasin:
  goaliq-app/lib/fantasyResultCopy.ts              (mobiili, testattu nodella)
  web/pro-spa/src/lib/components/TeamPitchManager.svelte  (SPA, ei testia)

Tama testi lukee molemmat ja vertaa funktioiden `projectionLine`,
`swingInfo` ja `swingLineEn` KAIKKIA merkkijonoliteraaleja: jos toiseen
pintaan korjataan lause ja toinen jaa, joukot eroavat ja testi kaatuu.
Rungon muotoilua (prettier, tyyppinimet) ei verrata - se vaihtelee eika
ole se mika lukijalle nakyy.

Sama kaava kuin tests/test_luck_parity.py (kynnysvakiot). Mobiilirepo on
sisarkansio; jos sita ei ole (CI), testi ohitetaan eika kaadu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
WEB = HERE.parents[1] / "web" / "pro-spa" / "src" / "lib" / "components" / "TeamPitchManager.svelte"
MOBILE = HERE.parents[2] / "goaliq-app" / "lib" / "fantasyResultCopy.ts"

MOBILE_SPEC = HERE.parents[2] / "goaliq-app" / "components" / "FantasyTools.tsx"

FUNCS = ("projectionLine", "swingInfo", "swingLineEn", "chipLabel")

# Kortin spec-funktio: reitti (mallin entry-id avaimessa, /fpl/points
# alatunnisteessa) ja muut kortin literaalit asuvat TAALLA, eivat
# lausefunktioissa. Kierros 4 osoitti mutaatiolla etta pelkat lausefunktiot
# eivat huomaa reitin katoamista.
SPEC_LITERALS = (
    "You",
    "Model · entry ${",
    "You win by",
    "Model wins by",
    "Projected",
    "Gameweek ${",
    "FPL average ${",
    "rank ${",
    "model on ${",
    "got lucky",
    "got robbed",
    "frozen before the deadline · goaliq.app/fpl/points",
    "n/a",
)


def _unescape(s: str) -> str:
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def _function_body(src: str, name: str) -> str:
    # `function name(` TAI `const name = (...) =>` (mobiilin luckCardSpec).
    m = re.search(r"function " + name + r"\(|const " + name + r" = \(", src)
    assert m, f"{name} puuttuu"
    i = src.index("{", m.end())
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise AssertionError(f"{name}: sulkeva aaltosulku puuttuu")


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", src)


def _literals(body: str) -> set[str]:
    out: set[str] = set()
    # Kommentit pois ensin: perustelukommentin lainaus ("matched") ei ole copya.
    body = _strip_comments(body)
    for m in re.finditer(r"`([^`]*)`|'([^']*)'|\"([^\"]*)\"", body):
        s = next(g for g in m.groups() if g is not None)
        if s:
            out.add(_unescape(s))
    return out


@pytest.mark.skipif(not MOBILE.exists(), reason="goaliq-app ei ole sisarkansiona")
@pytest.mark.parametrize("name", FUNCS)
def test_kortin_lauseet_ovat_samat_molemmilla_pinnoilla(name: str):
    web = _literals(_function_body(WEB.read_text(encoding="utf-8"), name))
    mob = _literals(_function_body(MOBILE.read_text(encoding="utf-8"), name))
    assert web == mob, (
        f"{name}: vain webissa {sorted(web - mob)} · vain mobiilissa {sorted(mob - web)}"
    )


@pytest.mark.skipif(not MOBILE_SPEC.exists(), reason="goaliq-app ei ole sisarkansiona")
@pytest.mark.parametrize("literal", SPEC_LITERALS)
def test_kortin_spec_literaalit_molemmilla_pinnoilla(literal: str):
    web = _unescape(_function_body(WEB.read_text(encoding="utf-8"), "luckCardSpec"))
    mob = _unescape(_function_body(MOBILE_SPEC.read_text(encoding="utf-8"), "luckCardSpec"))
    assert literal in web, f"webin luckCardSpec ei sisalla {literal!r}"
    assert literal in mob, f"mobiilin luckCardSpec ei sisalla {literal!r}"


@pytest.mark.skipif(not MOBILE_SPEC.exists(), reason="goaliq-app ei ole sisarkansiona")
def test_mallin_luku_vain_reitin_kanssa():
    """Reitti ei saa kadota hiljaa: mallisolu vaatii entry-id:n molemmilla."""
    web = _function_body(WEB.read_text(encoding="utf-8"), "luckCardSpec")
    mob = _function_body(MOBILE_SPEC.read_text(encoding="utf-8"), "luckCardSpec")
    assert "model_entry_id != null" in web and "model_entry_id != null" in mob


@pytest.mark.skipif(not MOBILE_SPEC.exists(), reason="goaliq-app ei ole sisarkansiona")
def test_ruudun_mallisolu_vaatii_reitin():
    """Kierros 4 B1: korjaus meni kortille muttei ruudulle. Ruutu on toinen
    renderointipolku samalle luvulle, joten sama ehto vartioidaan siella."""
    web = _strip_comments(WEB.read_text(encoding="utf-8"))
    mob = _strip_comments(MOBILE_SPEC.read_text(encoding="utf-8"))
    assert "lastFinished.model_points != null && lastFinished.model_entry_id != null" in web
    assert "lastFinished.vs_model != null && lastFinished.model_entry_id != null" in web
    assert "lf.model_points != null && lf.model_entry_id != null" in mob
    assert "lf.vs_model != null && lf.model_entry_id != null" in mob


def test_hylatyt_sanamuodot_eivat_palaa():
    """Portin hylkaamat muodot (k1-k3) eivat saa palata kummallekaan pinnalle.
    Kommentit riisutaan ensin: niissa hylatty muoto SAA olla perusteluna."""
    for path in (WEB, MOBILE):
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
        src = re.sub(r"//[^\n]*", "", src)
        src = re.sub(r"<!--.*?-->", "", src, flags=re.DOTALL)
        for bad in ("alone was", "of that", "of it.", "logged before kickoff, graded in public"):
            assert bad not in src, f"{path.name}: hylatty sanamuoto '{bad}' on yha koodissa"


@pytest.mark.skipif(not MOBILE_SPEC.exists(), reason="goaliq-app ei ole sisarkansiona")
def test_kortin_oma_pistemaara_on_netto_molemmilla():
    """🔴 Portin 13. kierros: RUUTU MIGRATOITIIN, KORTTI EI.

    12. kierroksella siirsin `vs_model`in laskettavaksi netosta ja korjasin
    Svelten ruudun (rivi 929) - mutta saman tiedoston JAKOKORTTI (rivi 539)
    jai bruttoon. Hittiviikolla (gross 70, cost 4, malli 62) kortti sanoi
    "You 70 ... Model 62 ... You win by 4": kortin oma laskutoimitus antaa
    8, eika lukija voi tarkistaa sita mistaan. Samaan aikaan ruutu saman
    komponentin sisalla naytti 66.

    **Miksi tama ei jaanyt kiinni:** viereiset testit vartioivat `vs_model`-
    ja `model_entry_id`-EHTOJA molemmilta pinnoilta, mutta eivat yhtaan
    NAYTETTYA LUKUA. Portti mittasi ehdot, ei arvoa.
    """
    web = _strip_comments(WEB.read_text(encoding="utf-8"))
    mob = _strip_comments(MOBILE_SPEC.read_text(encoding="utf-8"))
    assert "lf.points_net ?? lf.points" in web, "webin kortti nayttaa bruttoa"
    assert "lastFinished.points_net ?? lastFinished.points" in mob, (
        "mobiilin kortti nayttaa bruttoa")
    # NEGATIIVINEN KONTROLLI: paljas brutto ei saa jaada kummallekaan.
    assert "String(lf.points)" not in web
    assert "String(lastFinished.points)" not in mob


@pytest.mark.skipif(not MOBILE_SPEC.exists(), reason="goaliq-app ei ole sisarkansiona")
def test_ruutu_ja_kortti_lukevat_samaa_kenttaa():
    """Sama invariantti toiseen suuntaan: jos jompikumpi pinta lisaa uuden
    `points`-luvun, se on luettava samasta kentasta kuin toinen. Lasketaan
    esiintymat, ei etsita yhta merkkijonoa (muisti:
    yksi-renderointipolku-kahdesta)."""
    web = _strip_comments(WEB.read_text(encoding="utf-8"))
    netot = web.count("points_net ?? ")
    assert netot >= 3, (
        f"webissa on {netot} netto-lukua; ruutu, kortti ja otsikkoluku "
        "lukevat kaikki samaa kenttaa")


def test_points_kentta_tarkoittaa_samaa_kaikissa_moduuleissa():
    """🔴 N1 (portin 13. kierros): RAKENTEELLINEN SYY B1:lle.

    `fpl_model_race` kaytti `points`ia NETTONA samalla kun `fpl_rate_team` ja
    `fpl_gw_review` kayttavat sita BRUTTONA. Sama sana, kaanteinen merkitys,
    ja kirjoittajan piti muistaa kummassa moduulissa han on - juuri siksi
    jakokortti jai bruttoon kahden kierroksen ajaksi.

    Konventio: `points` / `fpl_points` = FPL:n oma kentta sellaisenaan
    (brutto). `points_net` / `fpl_points_net` = se luku jonka lukija nakee.
    Tama testi kaatuu jos joku moduuli palaa toiseen suuntaan.
    """
    SRC = HERE.parents[1] / "src" / "models"
    race = (SRC / "fpl_model_race.py").read_text(encoding="utf-8")
    # model_racessa `points` on raaka kentta, netto omalla nimellaan
    assert '"points": int(row.get("points") or 0),' in race
    assert '"points_net": int(row.get("points") or 0) - kustannus,' in race
    # ja vertailut lukevat NETTOA
    assert 'u["points_net"] - mp' in race
    assert 'u["points"] - mp' not in race, (
        "vertailu lukee bruttoa - malli ei ota hitteja, joten se antaisi "
        "kayttajalle hitin verran etumatkaa")

    rate = (SRC / "fpl_rate_team.py").read_text(encoding="utf-8")
    assert '"points_net":' in rate and '"points": points,' in rate

    review = (SRC / "fpl_gw_review.py").read_text(encoding="utf-8")
    assert '"fpl_points_net":' in review
