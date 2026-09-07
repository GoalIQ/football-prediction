"""KORTIN LUPAAMA TARKISTUSREITTI VASTAA - SILLE KIERROKSELLE JOKA KORTISSA ON.

MIKSI TAMA ON OLEMASSA (7.9.2026). Tuloskortin alatunniste lupasi
`goaliq.app/fpl/points`. Se sivu naytti VAIN kuluvan kierroksen, joten GW2:n
kortti lahetti lukijan sivulle jolla oli GW3:n luvut - eika mikaan huutanut.
Kortti on pysyva kuva: vaara reitti ei vanhene vaan jaa kiertoon niin kauan
kuin kuva on olemassa.

Vika oli mahdollinen koska REITTI JA SIVU OLIVAT ERI LUKIJOITA: sovellus
kirjoitti URLin merkkijonona, builderi paatti erikseen mita sivuja syntyy.
Tama testi sitoo ne yhteen:

  reitti  <- `luckCardSpec`in `footNote` MOLEMMILTA pinnalta (mobiili + SPA)
  sivut   <- `build_fpl_longtail._arkistoitavat_kierrokset()`, sama funktio
             jota kirjoitussilmukka, sitemap ja kierrosnauha kayttavat

Jos jompikumpi muuttuu ilman toista, testi kaatuu.

🔴 NEGATIIVINEN KONTROLLI ON OSA PORTTIA. Portti joka lapaisee tyhjalla
joukolla ei mittaa mitaan (`kontrolli-lapaisi-tyhjana`): alla vaaditaan etta
kierroksia on vahintaan yksi, etta URL-malli LOYTYI molemmista lahteista, ja
etta kierros JOLLE sivua ei luvata ei myoskaan ole olemassa.

Live-osa (curl tuotantoa vasten) on `hub-deploy.yml`:n portti "kortin reitti
vastaa tuotannossa": statuskoodi yksin ei todista olemassaoloa, koska
goaliq.app ei palauta 404:aa kaikilla poluilla (`goaliq-app-ei-palauta-404`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import scripts.build_fpl_longtail as bl

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
FPL = ROOT / "fpl"
POINTS_DIR = FPL / "points"
SPA = (ROOT / "web" / "pro-spa" / "src" / "lib" / "components"
       / "TeamPitchManager.svelte")
MOBILE = HERE.parents[2] / "goaliq-app" / "components" / "FantasyTools.tsx"

# Kortin alatunnisteen URL-malli. `${...}` on kierrospaikka.
_REITTI = re.compile(
    r"goaliq\.app(/fpl/points(?:/gw\$\{[^}]+\})?)")


def _unescape(s: str) -> str:
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def _footnote_reitit(polku: Path) -> list[str]:
    """`luckCardSpec`in footNote-haarojen URL-polut, esim.
    ['/fpl/points/gw${lf.gw}', '/fpl/points']."""
    src = _unescape(polku.read_text(encoding="utf-8"))
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    m = re.search(r"footNote:(.{0,400}?)(?:\n\s*\}|,\n)", src, re.S)
    assert m, f"{polku.name}: luckCardSpecin footNote ei loytynyt"
    return [g.group(1) for g in _REITTI.finditer(m.group(1))]


@pytest.fixture(scope="module")
def kierrokset() -> list[int]:
    if not (ROOT / "fpl" / "player-gw.json").exists():  # pragma: no cover
        pytest.skip("player-gw.json puuttuu talta koneelta")
    return bl._arkistoitavat_kierrokset()


def test_kontrolli_ei_ole_tyhja(kierrokset):
    """Portti joka ajaa nollan kierroksen yli lapaisee aina."""
    assert len(kierrokset) >= 1, (
        "arkistoitavia kierroksia ei ole yhtaan -> kaikki alla olevat "
        "tarkistukset menisivat lapi mittaamatta mitaan")


@pytest.mark.skipif(not MOBILE.exists(), reason="goaliq-app ei ole sisarkansiona")
def test_molemmat_pinnat_lupaavat_saman_reitin():
    """Reitti kirjoitetaan kahteen tiedostoon, joten se voi eriytya. Sama
    luokka kuin tests/test_result_card_copy_parity.py vartioi lauseille."""
    mob = _footnote_reitit(MOBILE)
    spa = _footnote_reitit(SPA)
    assert mob, "mobiilin footNotesta ei loytynyt yhtaan goaliq.app-reittia"
    assert spa, "SPA:n footNotesta ei loytynyt yhtaan goaliq.app-reittia"
    # Muuttujan nimi eroaa pinnoittain (lastFinished.gw vs lf.gw), rakenne ei.
    kuori = lambda xs: sorted(re.sub(r"\$\{[^}]+\}", "${gw}", x) for x in xs)
    assert kuori(mob) == kuori(spa), f"mobiili {mob} vs SPA {spa}"


@pytest.mark.skipif(not MOBILE.exists(), reason="goaliq-app ei ole sisarkansiona")
def test_reitti_on_kierroskohtainen():
    """🔴 TAMA ON SE VIKA. Paljas /fpl/points nayttaa vain kuluvan kierroksen,
    joten se ei ole tarkistusreitti pysyvalle kuvalle."""
    for polku in (MOBILE, SPA):
        reitit = _footnote_reitit(polku)
        assert any("/gw${" in r for r in reitit), (
            f"{polku.name}: kortti lupaa reitin ilman kierrosta ({reitit}) - "
            f"jaettu kuva osoittaisi sivulle jolla on eri kierroksen luvut")


def test_luvattu_sivu_on_olemassa_jokaiselle_kierrokselle(kierrokset):
    """Sama lukija kuin kirjoitussilmukalla: jos nama eroavat, lukija saa
    404:n siita URLista jonka kortti hanelle lupasi."""
    puuttuu = [g for g in kierrokset
               if not (POINTS_DIR / f"gw{g}.html").exists()]
    assert not puuttuu, (
        f"kierroksille {puuttuu} luvataan reitti /fpl/points/gw{{n}} mutta "
        f"sivua ei ole. Aja: python -m scripts.build_fpl_longtail")


def test_sivua_ei_ole_kierrokselle_jolle_sita_ei_luvata(kierrokset):
    """Negatiivinen kontrolli: portti ei saa lapaista siksi etta sivuja on
    kaikille mahdollisille numeroille."""
    if not POINTS_DIR.exists():  # pragma: no cover
        pytest.skip("arkistohakemistoa ei ole")
    olemassa = {int(f.stem[2:]) for f in POINTS_DIR.glob("gw*.html")
                if f.stem[2:].isdigit()}
    assert olemassa == set(kierrokset), (
        f"levylla {sorted(olemassa)}, luvataan {kierrokset}")
    assert not (POINTS_DIR / "gw99.html").exists(), (
        "gw99 ei ole pelattu kierros, sille ei saa olla sivua")


def test_jokainen_nauhan_linkki_osoittaa_olemassa_olevaan_sivuun():
    """Nauha on lukijan reitti. Kuollut linkki on pahempi kuin puuttuva."""
    if not FPL.exists():  # pragma: no cover
        pytest.skip("fpl/-hakemistoa ei ole")
    linkit: set[str] = set()
    for f in list(FPL.glob("*.html")) + list(POINTS_DIR.glob("*.html")):
        linkit |= set(re.findall(r'href="/fpl/points/(gw\d+)"',
                                 f.read_text(encoding="utf-8")))
    assert linkit, "yksikaan sivu ei linkita arkistoon -> nauha katosi"
    kuolleet = sorted(s for s in linkit if not (POINTS_DIR / f"{s}.html").exists())
    assert not kuolleet, f"kuolleet arkistolinkit: {kuolleet}"


def test_sivun_oman_kortin_reitti_on_saman_sivun_kierros():
    """Sivulla renderoity jakokortti lupaa reitin `data-card-spec`in
    `footNote2`:ssa. Se on sama vaite kuin sovelluksen kortissa, ja se voi
    osoittaa vaaraan kierrokseen tasan samalla tavalla."""
    if not POINTS_DIR.exists():  # pragma: no cover
        pytest.skip("arkistohakemistoa ei ole")
    for f in sorted(POINTS_DIR.glob("gw*.html")):
        h = f.read_text(encoding="utf-8")
        spec = re.search(r"data-card-spec='(.*?)'", h, re.S)
        assert spec, f"{f.name}: kortin speciä ei ole"
        assert f"goaliq.app/fpl/points/{f.stem}," in spec.group(1), (
            f"{f.name}: kortti lupaa eri kierroksen reitin kuin sivu on")
        assert re.search(
            rf'<link rel="canonical" href="https://goaliq\.app/fpl/points/{f.stem}"',
            h), f"{f.name}: canonical ei osoita itseensa"
