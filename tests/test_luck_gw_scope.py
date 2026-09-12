# -*- coding: utf-8 -*-
"""Paattyneen kierroksen luvut eivat saa vuotaa toisen kierroksen sarakkeeseen.

Vika (3.9.2026, Villen havainto): "My team" nayttti GW2:n toteutuneet pisteet
siina missa pitaisi lukea GW3:n xP. Ehto `picksGw === lastFinished.gw` luettiin
merkiksi siita etta kierros juuri paattyi, mutta FPL pitaa entryn picksit
edellisessa kierroksessa deadlineen asti — eli ehto on tosi koko sen ikkunan
jonka kayttaja kayttaa SEURAAVAN kierroksen suunnitteluun.

Mekanismi (CLAUDE.md saanto 6a):
  (1) yksi lukija: `settledGwReadable` molemmilla pinnoilla. Kartta jaa
      tyhjaksi kun katsottava kierros ei ole se jolta toteumat ovat.
  (2) tama testi: jos joku rakentaa kartan uudelleen suoraan
      `lastFinished.players`-lohkosta ilman lukijaa, testi kaatuu.
  (3) vaiheparametroitu totuustaulu ajetaan mobiilissa
      (`goaliq-app/lib/fantasyDisplay.test.ts`), jossa TS on ajettavissa.

Mobiilin lahde on toisessa reposssa eika luettavissa taalta (sama rajoite kuin
test_luck_parity.py:ssa) — tama testi pinnaa TAMAN repon pinnan.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LUCK_TS = ROOT / "web" / "pro-spa" / "src" / "lib" / "luck.ts"
PITCH = ROOT / "web" / "pro-spa" / "src" / "lib" / "components" / "TeamPitchManager.svelte"

# Lohko joka rakentaa toteumakartan. Haetaan nimella, ei rivinumerolla.
LUCK_MAP_RE = re.compile(
    r"const luckById = \$derived\.by\(\(\) => \{(.*?)\n\t\}\);", re.S)


def _luck_map_body() -> str:
    m = LUCK_MAP_RE.search(PITCH.read_text(encoding="utf-8"))
    assert m, "TeamPitchManager: luckById-lohkoa ei loytynyt (nimi vaihtui?)"
    return m.group(1)


def test_helper_exists_and_is_not_a_constant():
    """Lukija on olemassa ja sen ehto on aito (ei `return true`)."""
    src = LUCK_TS.read_text(encoding="utf-8")
    assert "export function settledGwReadable(" in src
    body = src.split("export function settledGwReadable(", 1)[1]
    # Negatiivinen kontrolli: kaikki kolme haaraa on kirjoitettu ulos.
    assert "if (!sameSquad || luckGw == null) return false;" in body
    assert "if (selGw == null) return true;" in body
    assert "return selGw === luckGw;" in body


def test_pitch_builds_the_map_only_through_the_reader():
    """Kartta rakennetaan lukijan takana, ei suoraan lohkosta."""
    body = _luck_map_body()
    assert "settledGwReadable(premium ? selGw : null, luckGw, luckSameSquad)" in body, (
        "luckById lukee last_finished-lohkon ilman settledGwReadablea — "
        "silloin paattyneen kierroksen pisteet voivat nakya tulevan "
        "kierroksen sarakkeessa (vika 3.9.2026).")
    # Portti ei saa lapaista pelkasta maininnasta: ehdon on oltava
    # AIKAISEMMIN kuin silmukka joka tayttaa kartan.
    gate = body.index("settledGwReadable(")
    fill = body.index("for (const r of lastFinished.players)")
    assert gate < fill, "ehto on silmukan JALKEEN — kartta ehtii tayttya"


def test_forecast_column_is_the_default():
    """Oletusvalinta on ennustekierros, ei paattynyt."""
    src = PITCH.read_text(encoding="utf-8")
    assert "defaultGw != null && gwsAvailable.includes(defaultGw)" in src, (
        "oletus-GW luetaan chip-listalta (johon paattynyt kuuluu) eika "
        "ennustelistalta — silloin naytto voi avautua tulokseen")
    # Paattynyt kierros on oma chippinsa, eli kayttaja EI menetä nakymaa.
    assert "gwChips" in src and "result" in src


# ---------------------------------------------------------------------------
# JAKOKORTTI: sama vika yhta pintaa myohemmin (12.9.2026, Villen havainto)
#
# "my teamista kun haluaa copy image gw4 joukkueen nii antaa ton gw3 resultin"
#
# `luckCardSpec()` tarkisti vain ETTA paattynyt kierros on olemassa, ei sita
# MITA KIERROSTA naytto katsoo, ja `shareImage()` otti sen aina ensisijaisena
# (`luckSpec ?? {...}`). Kentalla luki GW4, kortissa GW3 RESULT — ja kortti on
# pysyva kuva, eli vaara kierros jaa kiertoon.
#
# Sama vikaluokka kuin `luckById` 3.9: ehto kirjoitettiin uudelleen sen sijaan
# etta luettaisiin `settledGwReadable`. Kaksi ehtoa samasta kysymyksesta
# ajautuu erilleen.
# ---------------------------------------------------------------------------

CARD_SPEC_RE = re.compile(
    r"function luckCardSpec\(\) \{(.*?)\n\t\}\n", re.S)
SHARE_RE = re.compile(r"async function shareImage\(\) \{(.*?)\n\t\}\n", re.S)


def _card_spec_body() -> str:
    m = CARD_SPEC_RE.search(PITCH.read_text(encoding="utf-8"))
    assert m, "TeamPitchManager: luckCardSpec-lohkoa ei loytynyt (nimi vaihtui?)"
    return m.group(1)


def test_jakokortti_lukee_saman_lukijan():
    """Kortin ehto tulee `settledGwReadable`ista, ei omasta vertailusta."""
    body = _card_spec_body()
    assert "settledGwReadable(" in body, (
        "luckCardSpec ei lue jaettua lukijaa - kortti voi nayttaa eri "
        "kierrosta kuin kentta")


def test_jakokortti_ottaa_valitun_kierroksen_huomioon():
    """MUTAATIO: pelkka `luckSameSquad`-ehto ei riita.

    Jos joku palauttaa vanhan muodon (`if (!luckSameSquad || !lastFinished`
    ... `) return null;` ilman lukijaa), tama kaatuu."""
    body = _card_spec_body()
    i_lukija = body.find("settledGwReadable(")
    i_lf = body.find("const lf = lastFinished")
    assert i_lukija != -1 and i_lf != -1
    assert i_lukija < i_lf, (
        "lukijan on portitettava ENNEN kuin spekki rakennetaan")
    assert "selGw" in body[i_lukija:i_lukija + 120], (
        "lukijalle ei anneta valittua kierrosta - ehto on sokea silla, mita "
        "naytto katsoo")


def test_jakokortti_ja_toteumakartta_antavat_lukijalle_saman_argumentin():
    """Molemmat pinnat kysyvat SAMAA kysymysta samoilla argumenteilla.

    Jos toinen antaa `selGw` ja toinen `premium ? selGw : null`, ne voivat
    erota tasan ilmaispinnalla - ja silloin kortti ja kentta ovat eri mielta
    siella missa kukaan meista ei katso."""
    kutsu = re.compile(r"settledGwReadable\(([^)]*)\)")
    kartta = kutsu.search(_luck_map_body())
    kortti = kutsu.search(_card_spec_body())
    assert kartta and kortti, (kartta, kortti)
    siivoa = lambda s: " ".join(s.split())
    assert siivoa(kartta.group(1)) == siivoa(kortti.group(1)), (
        f"kartta: {kartta.group(1)!r}\nkortti: {kortti.group(1)!r}")


def test_share_ottaa_tuloskortin_vain_kun_spekki_on_olemassa():
    """`shareImage` saa suosia tuloskorttia, mutta vain kun spekki on ei-null.

    Tama on kontrolli: jos joku poistaa `??`-varahaaran, GW4:n jakaminen
    kaatuisi kokonaan sen sijaan etta antaisi XI-kortin."""
    body = SHARE_RE.search(PITCH.read_text(encoding="utf-8"))
    assert body, "shareImage-lohkoa ei loytynyt"
    s = body.group(1)
    assert "luckSpec ??" in s, "XI-varahaara puuttuu"
    assert "GAMEWEEK ${selGw} XI" in s, (
        "varahaara ei nimea valittua kierrosta")
