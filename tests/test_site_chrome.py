# -*- coding: utf-8 -*-
"""Portti: yksi ylapalkki, yksi identiteetti, sama erottelu joka pinnalla.

MITATTU 22.9.2026 (web-audit T5 + T7 + brandisekaannus, Villen GO).

  * Hubin ylapalkista oli SEITSEMAN versiota. FPL-alasivujen palkki vei
    ottelu-ennusteisiin ("All predictions") eika takaisin /fpl:aan, /spl:lla
    ja /404:lla palkkia ei ollut, ja /career linkitti fpl.html:aan (308).
  * `WebSite`-schemaa ei ollut millaan sivulla. `Organization.description`
    oli 1 201 merkin ominaisuuslista kolmella eri tekstilla kolmessa
    tiedostossa, ja sameAs:sta puuttui Bluesky ja GitHub.
  * Erottelu GOAL IQ -YouTube-kanavasta, goaliq.livesta ja goaliq.uk:sta oli
    vain llms.txt:ssa. Hakukoneen AI-yhteenveto yhdisti brandit.

Kaikki lahtee nyt kahdesta moduulista (`src/site_nav.py`,
`src/site_identity.py`). Tama portti mittaa sivut, ei lahdetta: kahdeksas
palkkiversio, kasin kirjoitettu Organization tai vanhentunut sameAs kaatuu
tassa ennen kuin se paasee tuotantoon.

Poikkeukset (sivu ilman palkkia) ovat `build_site_chrome.NAV_EXEMPT`issa
perusteluineen (CLAUDE.md 6a, mekanismi 2).
"""
from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_site_chrome as B  # noqa: E402
from src import site_identity as SI  # noqa: E402
from src import site_nav as SN  # noqa: E402

NAV_RE = re.compile(r'<nav class="gqn".*?</nav>', re.S)
LD_RE = re.compile(r'<script type="application/ld\+json">\n(.*?)\n</script>', re.S)


# ---------------------------------------------------------------------------
# apurit
# ---------------------------------------------------------------------------

def _sitemap_pages() -> list[tuple[str, Path]]:
    """(url, tiedosto) jokaiselle sitemapin URLille. Johdettu sitemapeista,
    ei kasin listattu: uusi sivu on mukana heti kun se on sitemapissa."""
    out = []
    for sm in sorted(ROOT.glob("sitemap-*.xml")):
        for url in re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8")):
            path = url.replace("https://goaliq.app", "")
            if path.endswith("/"):
                f = ROOT / path.lstrip("/") / "index.html"
            else:
                f = ROOT / (path.lstrip("/") + ".html")
            out.append((path or "/", f))
    return out


def _generated_pages() -> list[Path]:
    """Kaikki generoidut sivut, myos ne joita sitemap ei listaa (ottelusivut
    30 pv horisontin takana, muistiot): ne ovat yhta lailla julkisia."""
    out: list[Path] = []
    for g in ("fpl/**/*.html", "ucl/*.html", "predictions/**/*.html"):
        out.extend(sorted(ROOT.glob(g)))
    return out


def _expected_active(rel: str) -> str | None:
    rel = rel.replace("\\", "/")
    if rel.startswith("fpl"):
        return "fpl"
    if rel.startswith("predictions"):
        return "predictions"
    return B.ACTIVE.get(rel)


def nav_problem(html: str, active: str | None) -> str | None:
    """None jos sivun palkki on lahteen tuloste, muuten syy."""
    body = html[html.find("<body"):]
    navs = NAV_RE.findall(body)
    if len(navs) != 1:
        return f"palkkeja {len(navs)}, odotettiin 1"
    first_nav = re.search(r"<nav\b", body)
    if not first_nav or not body[first_nav.start():].startswith('<nav class="gqn"'):
        return "ensimmainen <nav> ei ole jaettu palkki"
    if navs[0] != SN.site_nav_html(active):
        return f"palkki ei vastaa src/site_nav.py:n tulostetta (active={active!r})"
    return None


def _ld_blocks(html: str) -> list[dict]:
    out = []
    for m in LD_RE.finditer(html):
        try:
            out.append(json.loads(m.group(1)))
        except ValueError:
            pass
    return out


def _orgs(html: str) -> list[dict]:
    """Kaikki Organization-solmut, myos sisakkaiset (publisher/creator)."""
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("@type") == "Organization":
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    for b in _ld_blocks(html):
        walk(b)
    return found


def _read(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():  # pragma: no cover
        pytest.skip(f"{rel} puuttuu")
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Ylapalkki
# ---------------------------------------------------------------------------

def test_kasin_yllapidetyt_sivut_ovat_lahteen_tahdissa():
    """`build_site_chrome --check`: lahteen muutos ilman ajoa kaatuu tassa."""
    assert B.main(["--check"]) == 0, "aja: python -m scripts.build_site_chrome"


def test_jokaisella_sitemap_sivulla_on_sama_palkki():
    pages = _sitemap_pages()
    assert len(pages) > 250, f"vain {len(pages)} sitemap-URLia, onko luku rikki?"
    viat = []
    for url, f in pages:
        assert f.exists(), f"sitemapin URL {url} ilman tiedostoa {f}"
        rel = f.relative_to(ROOT).as_posix()
        syy = nav_problem(f.read_text(encoding="utf-8"), _expected_active(rel))
        if syy:
            viat.append(f"{url}: {syy}")
    assert not viat, "\n".join(viat[:20])


def test_jokaisella_generoidulla_sivulla_on_sama_palkki():
    pages = _generated_pages()
    assert len(pages) > 1000, f"vain {len(pages)} generoitua sivua"
    viat = []
    for f in pages:
        rel = f.relative_to(ROOT).as_posix()
        syy = nav_problem(f.read_text(encoding="utf-8"), _expected_active(rel))
        if syy:
            viat.append(f"{rel}: {syy}")
    assert not viat, "\n".join(viat[:20])


@pytest.mark.parametrize("name", B.nav_pages() + ["fpl.html"])
def test_juurisivun_palkki(name):
    syy = nav_problem(_read(name), _expected_active(name))
    assert syy is None, f"{name}: {syy}"


def test_404_sivulla_on_palkki():
    """404 ei ole sitemapissa, mutta vanhentunut ottelulinkki laskeutuu sinne."""
    assert nav_problem(_read("404.html"), None) is None


def test_poikkeuksilla_on_perustelu():
    for name, reason in B.NAV_EXEMPT.items():
        assert len(reason) >= 40, f"{name}: perustelu puuttuu tai on liian lyhyt"
        assert name not in {u.lstrip("/") + ".html" for u, _ in _sitemap_pages()}, (
            f"{name} on sitemapissa: julkinen sivu ei voi olla ilman palkkia")


def test_palkki_fpl_ensin_ja_linkit():
    html = SN.site_nav_html()
    hrefs = re.findall(r'href="([^"]+)"', html)
    assert hrefs == ["/", "/fpl", "/predictions", "https://pro.goaliq.app/",
                     "https://pro.goaliq.app/?tab=premium"], hrefs
    assert html.index(">FPL tools<") < html.index(">Predictions<")


def test_kontrolli_vanha_palkki_kaatuu():
    """NEGATIIVINEN KONTROLLI: portti ei saa hyvaksya vanhaa palkkia eika
    kahta palkkia. Ilman tata NAV_RE voisi olla rikki ja kaikki vihreaa."""
    vanha = ('<body><header class="dark"><div class="wrap"><nav><a href="/">x</a>'
             '<span><a href="/predictions">All predictions</a></span></nav></div>')
    assert nav_problem(vanha, "fpl") is not None
    kaksi = "<body>" + SN.site_nav_html("fpl") + SN.site_nav_html("fpl")
    assert nav_problem(kaksi, "fpl") is not None
    vaara_osio = "<body>" + SN.site_nav_html("predictions")
    assert nav_problem(vaara_osio, "fpl") is not None
    oikea = "<body>" + SN.site_nav_html("fpl") + "<nav class=\"toolnav\"></nav>"
    assert nav_problem(oikea, "fpl") is None


# ---------------------------------------------------------------------------
# 2. Identiteetti (schema.org)
# ---------------------------------------------------------------------------

def test_etusivulla_on_website_schema():
    blocks = [b for b in _ld_blocks(_read("index.html")) if b.get("@type") == "WebSite"]
    assert len(blocks) == 1, "etusivulta puuttuu WebSite (Googlen sivustonimen lahde)"
    w = blocks[0]
    assert w["@id"] == SI.WEBSITE_ID
    assert w["name"] == "GoalIQ"
    assert w["url"] == "https://goaliq.app/"
    assert w["publisher"] == {"@id": SI.ORG_ID}
    assert w.get("alternateName"), "alternateName puuttuu"


def test_organization_on_identiteetti_eika_ominaisuuslista():
    orgs = [o for o in _orgs(_read("index.html")) if "description" in o]
    assert len(orgs) == 1
    o = orgs[0]
    assert o["@id"] == SI.ORG_ID
    assert len(o["description"]) < 300, (
        f"Organization.description {len(o['description'])} merkkia; "
        "ominaisuudet kuuluvat SoftwareApplicationiin, ei identiteettiin")
    assert o["legalName"] == "Savikurki Digital Oy"
    assert o["disambiguatingDescription"] == SI.ORG_DISAMBIGUATION
    for nimi in ("GOAL IQ YouTube", "goaliq.live", "goaliq.uk"):
        assert nimi in o["disambiguatingDescription"], nimi
    assert "founder" not in o, "founder on henkilotieto: vain Villen paatoksella"
    assert "Finland" not in o["description"], "ei sijaintia copyyn"


def test_organization_on_sama_kaikilla_pinnoilla():
    """Kolme eri kuvausta kolmessa tiedostossa oli se vika. Nyt jokainen
    Organization-solmu (taysi tai julkaisijasolmu) kantaa saman sameAs:n,
    ja jokainen taysi solmu on sanasta sanaan lahteen tuloste."""
    full = SI.organization_ld()
    pinnat = ["index.html", "fpl.html", "predictions.html", "faq.html"]
    pinnat += [p.relative_to(ROOT).as_posix()
               for p in sorted(ROOT.glob("predictions/premier-league/*.html"))[:5]]
    for rel in pinnat:
        orgs = _orgs(_read(rel))
        assert orgs, f"{rel}: ei Organization-solmua"
        for o in orgs:
            assert o.get("@id") == SI.ORG_ID, f"{rel}: Organization ilman oikeaa @id:ta"
            if "sameAs" in o:
                assert o["sameAs"] == SI.SAME_AS, f"{rel}: sameAs eri kuin lahde"
            if "description" in o:
                assert o == full, f"{rel}: kasin kirjoitettu Organization"


def test_sameas_on_llms_txtn_kanavalistassa():
    """Copy-sync: koneiden kaksi kanavalistaa eivat saa ajautua erilleen."""
    llms = _read("llms.txt")
    kahvat = {
        SI.PLAY_URL: "com.veikkoville.goaliq",
        SI.APPSTORE_URL: "id6780047163",
        SI.X_URL: "@goaliqapp",
        SI.BLUESKY_URL: "goaliqapp.bsky.social",
        SI.IG_URL: "Instagram @goaliqfpl",
        SI.TIKTOK_URL: "TikTok @goaliqfpl",
        SI.GITHUB_URL: "github.com/GoalIQ",
    }
    assert set(kahvat) == set(SI.SAME_AS), "uusi sameAs-kanava ilman llms-kahvaa"
    for url, kahva in kahvat.items():
        assert kahva in llms, f"llms.txt ei mainitse kanavaa {url} ({kahva})"


# ---------------------------------------------------------------------------
# 3. Ihmisluettava erottelu (FAQ + footer)
# ---------------------------------------------------------------------------

def test_faq_kysymys_nakyy_ja_on_schemassa_samoin_sanoin():
    html = _read("faq.html")
    m = re.search(r'<details id="' + SI.DISAMBIG_ANCHOR + r'">\s*<summary>(.*?)</summary>'
                  r'\s*<div>\s*<p>(.*?)</p>', html, re.S)
    assert m, "FAQ-sivulta puuttuu nakyva erottelukysymys"
    assert unescape(m.group(1)) == SI.DISAMBIG_QUESTION
    assert unescape(m.group(2)) == SI.DISAMBIG_ANSWER
    faq = [b for b in _ld_blocks(html) if b.get("@type") == "FAQPage"]
    assert len(faq) == 1
    ents = [e for e in faq[0]["mainEntity"] if e["name"] == SI.DISAMBIG_QUESTION]
    assert len(ents) == 1, "FAQPage-schemasta puuttuu erottelukysymys"
    assert ents[0]["acceptedAnswer"]["text"] == SI.DISAMBIG_ANSWER


@pytest.mark.parametrize("rel", list(B.DISAMBIG_PAGES) + ["fpl.html"])
def test_footerissa_on_erottelurivi(rel):
    html = _read(rel)
    foot = html[html.rfind("<footer"):]
    assert SI.footer_disambig_html() in foot, f"{rel}: erottelurivi puuttuu footerista"


def test_erottelu_sanoo_saman_kaikissa_muodoissa():
    """FAQ, footer, schema ja llms.txt: ei YouTube-kanavaa, ei vinkkeja,
    ei goaliq.live / goaliq.uk."""
    llms = _read("llms.txt")
    for teksti in (SI.DISAMBIG_ANSWER, SI.ORG_DISAMBIGUATION, llms):
        low = teksti.lower()
        assert "youtube" in low and "betting tips" in low, teksti[:80]
    for teksti in (SI.DISAMBIG_ANSWER, SI.ORG_DISAMBIGUATION, llms):
        assert "goaliq.live" in teksti and "goaliq.uk" in teksti
    assert "YouTube" in SI.FOOTER_DISAMBIG_TEXT and "betting tips" in SI.FOOTER_DISAMBIG_TEXT


def test_identiteettiteksteissa_ei_em_dashia():
    for t in (SI.ORG_DESCRIPTION, SI.ORG_DISAMBIGUATION, SI.DISAMBIG_ANSWER,
              SI.FOOTER_DISAMBIG_TEXT, SI.DISAMBIG_QUESTION):
        assert "—" not in t and "–" not in t, t


# ---------------------------------------------------------------------------
# 4. Hakutuloksen mitat (web-audit C6 + brandi 5) ja og:url
# ---------------------------------------------------------------------------

def _title_desc(rel: str) -> tuple[str, str]:
    html = _read(rel)
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    d = re.search(r'<meta name="description" content="([^"]*)"', html)
    return (unescape(t.group(1)) if t else "", unescape(d.group(1)) if d else "")


_KORJATUT_TITLET = ["predictions.html", "spl.html", "fpl/model-xi.html"] + [
    p.relative_to(ROOT).as_posix() for p in sorted(ROOT.glob("fpl/club/*.html"))]
_KORJATUT_KUVAUKSET = ["spl.html", "predictions.html", "fpl/best-captain.html", "fpl/points.html",
                       "faq.html"] + [
    p.relative_to(ROOT).as_posix() for p in sorted(ROOT.glob("fpl/points/gw*.html"))]


@pytest.mark.parametrize("rel", _KORJATUT_TITLET)
def test_title_mahtuu_hakutulokseen(rel):
    t, _ = _title_desc(rel)
    assert t and len(t) <= 60, f"{rel}: title {len(t)} merkkia: {t}"


@pytest.mark.parametrize("rel", _KORJATUT_KUVAUKSET)
def test_description_mahtuu_hakutulokseen(rel):
    _, d = _title_desc(rel)
    assert d and len(d) <= 160, f"{rel}: description {len(d)} merkkia"


def test_predictions_otsikko_erottaa_mallin_vinkeista():
    t, _ = _title_desc("predictions.html")
    assert "Logged Before Kickoff" in t, t
    for sana in ("tips", "bet", "odds", "most likely"):
        assert sana not in t.lower(), t


@pytest.mark.parametrize("rel", sorted(p.name for p in ROOT.glob("*.html")))
def test_og_url_on_canonical(rel):
    html = _read(rel)
    c = re.search(r'rel="canonical" href="([^"]+)"', html)
    o = re.search(r'property="og:url" content="([^"]+)"', html)
    if not (c and o):
        pytest.skip("ei canonical+og:url -paria")
    assert o.group(1) == c.group(1), f"{rel}: og:url {o.group(1)} != canonical {c.group(1)}"


# ---------------------------------------------------------------------------
# 5. Palkin CSS-lohko ei saa kaapata MOBILE-CSS:aa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", B.nav_pages())
def test_mobile_css_ei_mene_palkin_gen_lohkoon(name, tmp_path):
    """🔴 MITATTU 22.9. `apply_mobile_css` liittaa MOBILE-CSS:n viimeiseen
    </style>:iin jonka rivilla ei ole "GEN:". Ensimmaisessa versiossa palkin
    <style> oli omalla rivillaan </head>:n edessa, eli juuri se oli
    "viimeinen": MOBILE-CSS olisi mennyt SITE-NAV-CSS-lohkon sisaan ja
    `build_site_chrome` olisi pyyhkinyt sen seuraavalla ajolla. Ajetaan
    oikea `apply_to` kopiolle ja mitataan mihin lohko osui."""
    from scripts.apply_mobile_css import apply_to
    from scripts.mobile_css import BEGIN_MARKER
    kopio = tmp_path / name
    kopio.write_text(_read(name), encoding="utf-8")
    tulos = apply_to(kopio)
    assert not tulos.startswith("skipped"), f"{name}: {tulos}"
    s = kopio.read_text(encoding="utf-8")
    a, b = s.index(SN.CSS_BEGIN), s.index(SN.CSS_END)
    m = s.index(BEGIN_MARKER)
    assert not (a < m < b), f"{name}: MOBILE-CSS osui palkin GEN-lohkoon"
    # palkin lohko on yhdella rivilla markkereiden kanssa
    rivi = s[s.rfind("\n", 0, a) + 1:s.find("\n", a)]
    assert SN.CSS_END in rivi, f"{name}: SITE-NAV-CSS ei ole yhdella rivilla"


# ---------------------------------------------------------------------------
# 6. Vedonlyontimarkkinoiden sanasto pois julkisilta pinnoilta (D3, 22.9)
# ---------------------------------------------------------------------------

#: Sanat jotka lukevat vedonlyontimarkkinoilta. Hakukoneen AI-yhteenveto
#: yhdisti GoalIQ:n GOAL IQ -vinkkikanavaan (web-audit 22.9); naiden
#: sanojen poisto on osa erottelua. Korvaavat muodot: "scoreline
#: probabilities", "the chance of three or more goals", "the chance both
#: teams score". "expected total goals" on listalla koska tuote nayttaa
#: vain todennakoisyyden kolmelle tai useammalle maalille, ei odotusarvoa
#: (julkaisutarkistaja blokkasi sen 22.9).
VEDONLYONTISANAT = re.compile(
    r"most[ -]likely scor|likely scorelines|\bBTTS\b|both teams to score|"
    r"expected total goals|fair value|top-10 scorelines", re.I)


def _julkiset_pinnat() -> list[Path]:
    out = [p for p in sorted(ROOT.glob("*.html")) if not p.name.startswith("_")]
    out += [ROOT / "llms.txt"]
    out += _generated_pages()
    return out


def test_julkisilla_pinnoilla_ei_vedonlyontisanastoa():
    pinnat = _julkiset_pinnat()
    assert len(pinnat) > 1000
    osumat = []
    for p in pinnat:
        t = p.read_text(encoding="utf-8")
        m = VEDONLYONTISANAT.search(t)
        if m:
            osumat.append(f"{p.relative_to(ROOT).as_posix()}: {t[max(0, m.start()-60):m.end()+20]!r}")
    assert not osumat, "\n".join(osumat[:15])


def test_kontrolli_vedonlyontisanat_osuvat():
    for lause in ("the most likely scorelines", "top-10 scorelines, total goals and BTTS",
                  "expected total goals", "both teams to score"):
        assert VEDONLYONTISANAT.search(lause), lause
    for lause in ("scoreline probabilities", "the chance both teams score",
                  "Which teams are most likely to keep a clean sheet"):
        assert not VEDONLYONTISANAT.search(lause), lause
