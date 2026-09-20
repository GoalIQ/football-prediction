# -*- coding: utf-8 -*-
"""ILMAISIKKUNAN PORTTI KATSOO JOKAISTA JULKAISTUA SIVUA (18.9.2026).

MITATTU. Adversariaalinen tarkistaja kirjoitti tiedoston
`predictions/ZZ-tarkistaja-temp.html` sisallolla

    <p>Premium is free on the web until the GW4 deadline on 12 September,
       so GW1 to GW3.</p>

ja ajoi `python scripts/check_free_window.py`:

    exit 0   "OK: ilmaisikkuna on kiinni (12 September mennyt) eika yksikaan
              pinta lupaa ilmaista Premiumia"

Sama tiedosto repojuuressa:

    exit 1   "FAIL: ZZ-tarkistaja-temp.html:1 lupaa yha ilmaista Premiumia"

Ero oli `SURFACE_GLOBS`, joka luetteli kasin `("*.html", "fpl/**/*.html",
"llms.txt", ...)` ja kantoi kommenttia "Glob, ei kasin nimetty lista".
Glob oli kuitenkin kasin nimetty HAKEMISTOLISTA, ja sen ulkopuolelle oli
kasvanut 2769 deployattua sivua: `predictions/**` (279 sitemapissa) ja
`ucl/**`. Mekanismi 2 (`STATIC_ALLOWED = {}`) vaitti takaavansa, ettei
yksikaan julkinen pinta kanna staattista lupausta - ja se takuu oli
mitattu 177:sta noin 2950:sta sivusta. Vihrea portti todisteena vaarasta
asiasta on pahempi kuin ei porttia.

KORJAUS (saanto 6a mekanismi 1). Pintajoukko JOHDETAAN siita mika oikeasti
deployataan: `hub-deploy.yml`:n push-`paths`. Uusi hakemisto tulee portin
piiriin samalla rivilla jolla se tulee deployn piiriin.

Tama tiedosto on sen vartija, kolmella kysymyksella:
  1. jokainen sitemapissa oleva sivu on `surfaces()`-joukossa
  2. jokainen deployattu tekstipinta on `surfaces()`-joukossa
  3. lupaus `predictions/`-kansiossa kaataa portin JOKAISESSA kauden
     vaiheessa (ennen deadlinea / tasan / jalkeen)
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.check_free_window as C  # noqa: E402
from src import free_window as FW  # noqa: E402

UNTIL = FW.until()
VAIHEET = [("ennen", UNTIL - dt.timedelta(hours=1)),
           ("tasan", UNTIL),
           ("jalkeen", UNTIL + dt.timedelta(hours=1))]

LUPAUS = ("<p>Premium is free on the web until the GW4 deadline on "
          "12 September, so GW1 to GW3.</p>")

#: Sama muoto kuin oikea hub-deploy.yml. Testin oma kopio, jotta parseria
#: voi ajaa hakemistolla jota repossa ei ole.
WORKFLOW = """name: hub-deploy
on:
  push:
    branches: [main]
    paths:
      - '*.html'
      - '*.js'
      - 'fpl/**'
      - 'ucl/**'
      - 'predictions/**'
      - 'assets/**'
      - '*.xml'
      - 'llms.txt'
      - 'robots.txt'
      - 'favicon.ico'
  workflow_dispatch: {}
jobs:
  deploy:
    runs-on: ubuntu-latest
"""


def _sitemap_urlit() -> list[str]:
    ulos = []
    for sm in sorted(ROOT.glob("sitemap*.xml")):
        for m in re.finditer(r"<loc>([^<]+)</loc>",
                             sm.read_text(encoding="utf-8")):
            u = m.group(1)
            if not u.endswith(".xml"):
                ulos.append(u)
    return ulos


def _url_polku(url: str) -> Path | None:
    """URL -> repossa oleva tiedosto, samalla kuvauksella kuin CF Pages."""
    polku = url.split("goaliq.app", 1)[1].lstrip("/")
    kand = ([polku + "index.html"] if polku == "" or polku.endswith("/")
            else [polku + ".html", polku + "/index.html"])
    for k in kand:
        if (ROOT / k).is_file():
            return ROOT / k
    return None


# ---------------------------------------------------------------------------
# 1. Sitemapissa oleva sivu on julkinen pinta
# ---------------------------------------------------------------------------

def test_jokainen_sitemapin_sivu_on_pinta():
    """Sivu jonka kerromme Googlelle on julkinen. Jos portti ei katso sita,
    lupaus voi elaa siella nakymattomana."""
    urlit = _sitemap_urlit()
    # 🔴 20.9.2026: tassa oli absoluuttinen raja `> 300`, ja se ajautui itse
    # aiheuttamatta yhtaan oikeaa vikaa. Ennustesivut VANHENEVAT kun ottelut
    # pelataan: yhtena paivana viisi poistui (la-liga/deportivo-real-betis,
    # serie-a/juventus-atalanta, ...) ja kaksi CL-ottelua tuli tilalle, netto
    # -3 -> 298. Mikaan ei ollut rikki; raja mittasi kalenteria, ei
    # katkaisua. Testi joka kaatuu ajan kulumisesta opettaa ohittamaan sen.
    #
    # Rajat ovat nyt TIEDOSTOKOHTAISIA ja rakenteellisia: ne kaatuvat jos
    # sitemap katkeaa tai regex lakkaa osumasta, mutta eivat siita etta
    # otteluita pelataan. Levylla olevaan maaraan niita EI voi sitoa:
    # `predictions/`issa on 2 688 html-tiedostoa mutta sitemapissa 237,
    # koska sitemap on tarkoituksella tuoreiden otteluiden osajoukko.
    per_tiedosto = {}
    for sm in sorted(ROOT.glob("sitemap*.xml")):
        n = len([m for m in re.finditer(r"<loc>([^<]+)</loc>",
                                        sm.read_text(encoding="utf-8"))
                 if not m.group(1).endswith(".xml")])
        per_tiedosto[sm.name] = n
    ALARAJAT = {"sitemap-core.xml": 5, "sitemap-fpl.xml": 20,
                "sitemap-predictions.xml": 50}
    for nimi, raja in ALARAJAT.items():
        assert nimi in per_tiedosto, f"{nimi} puuttuu kokonaan"
        assert per_tiedosto[nimi] >= raja, (
            f"{nimi}: {per_tiedosto[nimi]} sivua, alaraja {raja}. "
            "Tama on katkaisu, ei otteluiden vanhenemista.")
    assert len(urlit) >= 100, f"sitemap luki vain {len(urlit)} sivua"
    pinnat = set(C.surfaces())
    puuttuu = []
    for u in urlit:
        p = _url_polku(u)
        assert p is not None, f"sitemap osoittaa sivuun jota ei ole: {u}"
        if p not in pinnat:
            puuttuu.append(str(p.relative_to(ROOT)))
    assert not puuttuu, (
        f"{len(puuttuu)} sitemapissa olevaa sivua EI ole portin pinta-"
        f"joukossa, esim. {puuttuu[:5]}")


# ---------------------------------------------------------------------------
# 2. Deployattu tekstipinta on julkinen pinta
# ---------------------------------------------------------------------------

def test_jokainen_deployattu_tekstipinta_on_pinta():
    """`hub-deploy.yml` kertoo mika paatyy goaliq.app:iin. Portin joukon on
    katettava se, muuten julkaistua sivua ei tarkisteta."""
    wf = (ROOT / C.DEPLOY_WORKFLOW).read_text(encoding="utf-8")
    globit = C.deploy_globs(wf)
    assert "predictions/**/*.html" in globit, globit
    assert "ucl/**/*.html" in globit, globit
    pinnat = set(C.surfaces())
    puuttuu = []
    for g in globit:
        for p in ROOT.glob(g):
            if p.is_file() and p not in pinnat:
                puuttuu.append(str(p.relative_to(ROOT)))
    assert not puuttuu, f"deployattuja pintoja portin ulkopuolella: {puuttuu[:5]}"


def test_deploy_globs_lukee_workflowta_eika_muista_hakemistoja():
    """Parseri, ei muisti: workflow'hun lisatty uusi hakemisto tulee portin
    piiriin ilman etta tassa tiedostossa muutetaan mitaan."""
    uusi = WORKFLOW.replace("      - 'assets/**'",
                            "      - 'assets/**'\n      - 'uutiset/**'")
    globit = C.deploy_globs(uusi)
    assert "uutiset/**/*.html" in globit, globit
    # `*.js`, `*.xml`, `favicon.ico`: deployn piirissa, eivat kanna
    # luettavaa lupauslausetta -> tarkoituksella ulkona.
    assert not [g for g in globit if g.endswith((".js", ".xml", ".ico"))], globit
    # Ei workflow'ta (tmp_path-juuri) -> tyhja, pohjaglobit vastaavat yksin.
    assert C.deploy_globs("name: x\non:\n  push:\n") == ()


# ---------------------------------------------------------------------------
# 3. DoD: lupaus predictions-kansiossa kaataa portin joka vaiheessa
# ---------------------------------------------------------------------------

def _tee_juuri(tmp_path: Path) -> Path:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "hub-deploy.yml").write_text(
        WORKFLOW, encoding="utf-8")
    (tmp_path / "index.html").write_text("<p>GoalIQ</p>", encoding="utf-8")
    return tmp_path


def test_lupaus_predictions_kansiossa_kaataa_portin(tmp_path, monkeypatch):
    """TARKISTAJAN MITTAUS TOISTETTUNA. Sama tiedosto joka repojuuressa on
    exit 1 oli `predictions/`-kansiossa exit 0."""
    juuri = _tee_juuri(tmp_path)
    syva = juuri / "predictions" / "premier-league" / "arsenal-vs-chelsea"
    syva.mkdir(parents=True)
    f = syva / "index.html"
    f.write_text(LUPAUS, encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", juuri)

    # PORTIN VERDIKTI ENSIN. Se on se mita 18.9 mitattiin: vaara haara ei
    # kaadu vaan ONNISTUU (exit 0, "OK: ... eika yksikaan pinta lupaa
    # ilmaista Premiumia"). Jos tama testi tarkistaisi ensin pintajoukon
    # jasenyyden, se kaatuisi ennen kuin se on nahnyt vihrean portin - ja
    # exit-koodi ei olisi todiste mekanismista.
    assert C.main() == 1, "portti oli vihrea vaikka lupaus elaa"
    assert C.hits(), "lupausta ei havaittu predictions-kansiossa"
    assert f in C.surfaces(), "predictions-sivu ei ole pintajoukossa"


def test_lupaus_predictions_kansiossa_kaataa_portin_joka_vaiheessa(
        tmp_path, monkeypatch):
    """INVARIANTTI MITATAAN JOKA VAIHEESSA. Ikkunan ollessa AUKI lupaus on
    tosi mutta STAATTINEN (ei sulkeudu itse) -> kaatuu mekanismi 2:sta.
    Ikkunan sulkeuduttua se on epatosi -> kaatuu selviytymistarkistuksesta.
    Kumpikaan vaihe ei saa olla vihrea."""
    juuri = _tee_juuri(tmp_path)
    (juuri / "predictions" / "la-liga").mkdir(parents=True)
    f = juuri / "predictions" / "la-liga" / "sivu.html"
    f.write_text(LUPAUS, encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", juuri)
    for nimi, hetki in VAIHEET:
        t = C.tarkista(now=hetki)
        assert t.static_hits, f"{nimi}: staattista lupausta ei havaittu"
        if hetki >= UNTIL:
            assert t.hits, f"{nimi}: vanhentunutta lupausta ei havaittu"


def test_ucl_kansio_on_pinta(tmp_path, monkeypatch):
    """`ucl/**` oli sama sokea piste, pienempana: 3 deployattua sivua."""
    juuri = _tee_juuri(tmp_path)
    (juuri / "ucl").mkdir()
    f = juuri / "ucl" / "prices.html"
    f.write_text(LUPAUS, encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", juuri)
    assert f in C.surfaces()
    assert C.main() == 1


def test_negatiivinen_kontrolli_puhdas_predictions_sivu_lapaisee(
        tmp_path, monkeypatch):
    """EROTTELEVUUS: portti ei kaadu pelkasta hakemistosta, vaan lupauksesta."""
    juuri = _tee_juuri(tmp_path)
    (juuri / "predictions" / "serie-a").mkdir(parents=True)
    f = juuri / "predictions" / "serie-a" / "sivu.html"
    f.write_text("<p>Premium is 3.99 EUR/month or 25 EUR/year.</p>",
                 encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", juuri)
    assert f in C.surfaces()
    assert C.main() == 0


# ---------------------------------------------------------------------------
# 4. Nakymamuisti ei saa muuttaa vastausta (nopeus ei saa maksaa oikeutta)
# ---------------------------------------------------------------------------

def test_nakymamuisti_ei_muuta_tulosta():
    """`_nakymat` rakentaa saman nakyman kerran kun sivulla ei ole templatea.

    Perustelu: `_ilman_templatea` on identiteetti jokaisella `now`- ja
    `ilman_js`-arvolla kun `TEMPLATE_RE` ei osu. Tassa se MITATAAN, ei
    uskota: sama tiedosto ilman templatea antaa saman nakyman kolmella eri
    kellolla, ja templaten kanssa nakymat EROAVAT (muuten muisti olisi
    sokea juuri siella missa kello ratkaisee)."""
    ilman = "<p>Premium is 3.99 a month.</p>"
    hae = C._nakymat(ilman)
    perus = hae(None)
    for _nimi, hetki in VAIHEET:
        assert hae(hetki) == perus
    assert hae(None, ilman_js=True) == perus

    kanssa = FW.hero_cta_html(VAIHEET[0][1])
    assert "data-free-window-open" in kanssa
    hae2 = C._nakymat(kanssa)
    assert hae2(VAIHEET[0][1]) != hae2(VAIHEET[2][1]), (
        "templaten nakyman PITAA riippua kellosta")
    assert hae2(VAIHEET[0][1], ilman_js=True) != hae2(VAIHEET[0][1]), (
        "JS:ton lukijan nakyman PITAA erota")


def test_tarkista_vastaa_erillisia_funktioita(tmp_path, monkeypatch):
    """YKSI LUKIJA: `main()` kayttaa `tarkista()`:a, testit ja skriptit
    `hits()`/`static_hits()`/... . Jos ne voisivat olla eri mielta, portti
    olisi vihrea siella missa testi on punainen."""
    juuri = _tee_juuri(tmp_path)
    (juuri / "predictions").mkdir()
    (juuri / "predictions" / "a.html").write_text(LUPAUS, encoding="utf-8")
    (juuri / "b.html").write_text(
        FW.hero_price_note_html(VAIHEET[0][1]), encoding="utf-8")
    (juuri / "c.html").write_text(
        '<template data-free-window-open="X" data-until="2099-01-01T00:00:00Z">'
        "<p>Premium is free on the web until the GW4 deadline.</p></template>"
        '<p>Get Premium</p><template data-free-window-end="X"></template>',
        encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", juuri)
    for _nimi, hetki in VAIHEET:
        t = C.tarkista(now=hetki)
        assert t.hits == C.hits(now=hetki)
        assert t.scope_misses == C.scope_misses(now=hetki)
        assert t.until_mismatches == C.until_mismatches()
        assert t.static_hits == C.static_hits()
