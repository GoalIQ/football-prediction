# -*- coding: utf-8 -*-
"""UCL Fantasy -osio: /ucl, /ucl/prices, /ucl/team-news.

Villen paatos 7.9.2026 ("laajin mahdollinen") + kysymys "Grafiikoita?".
Lahde on `data/ucl_fantasy.json` (scripts/ingest_ucl.py).

🔴 KOLME PAATOSTA JOTKA MITTAUS TEKI PUOLESTANI

**(1) SIVU ON OMASSA ALIHAKEMISTOSSAAN, EI JUURESSA.** `spl.html` on
juuressa ja kasin yllapidetty. Mitattu 7.9:
`tests/test_page_contract.py::_pages()` enumeroi VAIN `fpl/*.html` ja
`fpl/club/*.html`. Juuritason sivu ei siis kuulu sivusopimukseen lainkaan -
ei canonical-, ei sitemap-, ei sisaantuleva linkki -porttia. Juureen
kirjoitettu `ucl.html` olisi karannut jokaiselta portilta HILJAA, ja se on
tasan se vikaluokka josta on muisti (`uusi-sivu-ei-nay-hubissa`).

**(2) SIVU JA DATA SAMASSA WORKFLOW'SSA.** `ucl-refresh.yml` ajaa
ingestion, taman builderin ja committaa molemmat samassa ajossa. Erilliset
workflow't ajautuvat erilleen ja sivu jaatyy datan alle (muisti:
sivu-ja-data-eri-workflowssa).

**(3) MITAAN EI ENNUSTETA, KOSKA MITAAN EI OLE PELATTU.** Mitattu:
`matchdays_played == 0` kaikilla 1 162 pelaajalla. xP-lukua ei voi laskea
kauden datasta jota ei ole, joten sita ei ole talla sivulla. Naytamme sen
mika on TOTTA nyt: hinta, omistus, kokoonpanotila, otteluohjelma. Luvut
joita naytetaan viime kaudelta kantavat otsikossaan sen sanan, ja otsikon
antaa `ucl_phase.pistekentta()` samassa kutsussa kuin kentan - ne eivat voi
ajautua erilleen.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_fpl_longtail import (  # noqa: E402
    BASE, CSS, DISCLAIMER, MOBILE_COLS_JS, POSTHOG_SNIPPET, TABLE_TOOLS_JS,
    _og_image, _social_meta, _strip_css_comments,
)
from src.models import ucl_phase as vaiheet  # noqa: E402
from src.viz import svg_charts as sc  # noqa: E402

DATA = ROOT / "data" / "ucl_fantasy.json"
OUT_DIR = ROOT / "ucl"

# Osion oma navigointi. Sivusopimus vaatii sisaantulevan linkin joka
# sivulle; nama ristiinlinkit ovat se paikka josta se tulee.
UCL_LINKS = [
    ("/ucl", "UCL Fantasy"),
    ("/ucl/prices", "Prices & ownership"),
    ("/ucl/team-news", "Squad availability"),
]

STATUS_SANA = {
    "available": "Available",
    "doubtful": "Doubtful",
    "injured": "Injured",
    "suspended": "Suspended",
    "not_in_squad": "Not in squad",
    "unknown": "Unknown",
}
# Jarjestys on vakavuus, ei aakkoset: pinottu pylvas luetaan vasemmalta.
POISSA = ["injured", "suspended", "doubtful", "not_in_squad"]
# 🔴 VARIT MITATTIIN RENDEROIDYSTA KUVASTA, EI LUETTELOSTA. Ensimmainen
# versio antoi `doubtful`ille MUTEDin (#A8A29A) ja `not_in_squad`ille
# FAINTin (#8A847A). Legendassa ne ovat eri riveilla, mutta pinotussa
# pylvaassa ne ovat kaksi lahes samaa harmaata vierekkain eika lukija erota
# niita. Kaavion erottelu ei ole legendan asia vaan pylvaan.
POISSA_VARI = {"injured": sc.CORAL, "suspended": sc.AMBER,
               "doubtful": sc.CREAM, "not_in_squad": sc.FAINT}


def _fmt_deadline(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    return d.strftime("%a %-d %b %Y, %H:%M UTC") if sys.platform != "win32" \
        else d.strftime("%a %d %b %Y, %H:%M UTC")


def _page(title: str, desc: str, canonical: str, hero: str, body: str,
          jsonld: list[dict]) -> str:
    """UCL-osion runko.

    Head-jarjestys, CSS ja skriptit tuodaan `build_fpl_longtail`ista, joten
    osiot eivat voi ajautua eri nakoisiksi. Vain navigointi on oma.
    """
    ld = "".join(
        '<script type="application/ld+json">\n'
        + json.dumps(b, ensure_ascii=False, indent=1)
        + "\n</script>\n" for b in jsonld)
    linkit = "".join(
        f'<a href="{h}">{escape(t)}</a>'
        for h, t in UCL_LINKS if h != canonical.replace(BASE, "").rstrip("/"))
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        f"<title>{escape(title)}</title>\n"
        f'<meta name="description" content="{escape(desc)}" />\n'
        f'<link rel="canonical" href="{canonical}" />\n'
        f"{_social_meta(title, desc, canonical, _og_image(canonical))}"
        '<link rel="icon" href="/favicon.ico" sizes="any">\n'
        '<link rel="icon" type="image/png" sizes="32x32" href="/assets/brand/goaliq-favicon-32.png">\n'
        '<link rel="icon" type="image/png" sizes="48x48" href="/assets/brand/goaliq-favicon-48.png">\n'
        '<link rel="apple-touch-icon" sizes="180x180" href="/assets/brand/goaliq-apple-touch-180.png">\n'
        + POSTHOG_SNIPPET + "\n" + TABLE_TOOLS_JS + "\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family='
        'IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" onload="this.rel=\'stylesheet\'">\n'
        '<noscript><link href="https://fonts.googleapis.com/css2?family='
        'IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"></noscript>\n'
        '<meta name="theme-color" content="#0B0A09">\n'
        f"{ld}"
        f"<style>{_strip_css_comments(CSS)}{sc.CHART_CSS}</style>\n"
        "</head>\n<body>\n"
        '<header class="dark">\n<div class="bar"></div>\n'
        '<div class="wrap"><nav>'
        '<a class="brand" href="/"><svg class="brand-icon" width="22" height="22" viewBox="0 0 44 44" role="img" aria-label="GoalIQ" focusable="false"><rect x="0" y="0" width="44" height="44" fill="#F5C542"/><text x="22" y="30" text-anchor="middle" font-family="IBM Plex Mono,ui-monospace,Consolas,monospace" font-size="20" font-weight="700" letter-spacing="-0.5" fill="#0B0A09">IQ</text></svg>Goal<span>IQ</span></a>'
        '<span><a href="/fpl">FPL tools</a> · '
        '<a class="nav-cta" href="https://pro.goaliq.app/">Try it live</a></span>'
        "</nav></div>\n"
        f'<div class="wrap hero">\n{hero}\n</div>\n</header>\n'
        f'<main class="wrap content">\n{body}\n'
        f'<nav class="toolnav"><h2>UCL Fantasy</h2><div>{linkit}</div></nav>\n'
        '<footer>© 2026 GoalIQ · '
        '<a href="/predictions">Football predictions</a> · '
        '<a href="/fpl">Free FPL tools</a> · '
        f'<a href="/privacy.html">Privacy</a><br>{DISCLAIMER}</footer>\n'
        "</main>\n" + MOBILE_COLS_JS + "</body>\n</html>\n")


# --- kaaviot ---------------------------------------------------------------

def kaavio_omistus(pelaajat: list[dict]) -> str:
    """Omistus x hinta, vari = positio.

    Rajaus >1 % on tahallinen ja sanotaan sivulla aaneen: 990 pelaajaa
    nollan tuntumassa olisi musta massa jonka lapi ei nae mitaan. Rajattu
    joukko on 172 pelaajaa, ja se on juuri se joukko josta joukkueet
    kootaan.
    """
    valitut = [p for p in pelaajat if p["owned_pct"] > 1.0]
    sarjat = []
    for pos in ("GK", "DEF", "MID", "FWD"):
        pisteet = [(p["price"], p["owned_pct"],
                    f'{p["name"]} ({p["team_code"]}) {p["price"]:g}m, '
                    f'{p["owned_pct"]:g}% owned')
                   for p in valitut if p["pos"] == pos]
        if pisteet:
            sarjat.append({"nimi": pos, "vari": sc.POS_VARI[pos],
                           "pisteet": pisteet})
    return sc.scatter(
        sarjat=sarjat, x_label="Price (m)", y_label="Owned by",
        x_yksikko="m", y_yksikko="%",
        otsikko="Ownership by price, players owned by more than 1%")


def kaavio_saatavuus(pelaajat: list[dict], teams: list[dict]) -> str:
    """Poissaolot klubeittain. Vain klubit joilla on poissaoloja."""
    per_klubi: dict[str, Counter] = defaultdict(Counter)
    for p in pelaajat:
        if p["status"] in POISSA:
            per_klubi[p["team_code"]][p["status"]] += 1
    # 🔴 JARJESTYS JA NAYTETTY LUKU VASTAAVAT SAMAAN KYSYMYKSEEN.
    # Ensimmainen versio lajitteli POISSAOLOJEN SUMMALLA, ja mitattu
    # kuvasta: karjessa oli Real Madrid siksi etta sen rekisteroity
    # kokoonpano jattaa eniten pelaajia ulos - ei siksi etta silla olisi
    # eniten loukkaantumisia. Lukija tulee sivulle kysymyksella "kuka on
    # poissa pelista", ja sai vastauksen kysymykseen "kuka on jattanyt
    # eniten pelaajia rekisteroimatta" (muisti:
    # uusi-sorttiulottuvuus-muuttaa-sarakkeen).
    def toimittava(c: Counter) -> int:
        return c["injured"] + c["suspended"] + c["doubtful"]

    rivit = sorted(per_klubi.items(),
                   key=lambda kv: (-toimittava(kv[1]), -sum(kv[1].values())))
    rivit = [kv for kv in rivit if toimittava(kv[1]) > 0][:16]
    return sc.stacked_bars(
        rivit=[(k, dict(v)) for k, v in rivit],
        sarjat=[(s, POISSA_VARI[s], STATUS_SANA[s]) for s in POISSA],
        otsikko="Players unavailable by club",
        x_label="Players not available to pick")


def kaavio_hinnat(pelaajat: list[dict]) -> str:
    rivit = []
    for pos in ("GK", "DEF", "MID", "FWD"):
        hinnat = [p["price"] for p in pelaajat if p["pos"] == pos]
        if hinnat:
            rivit.append((pos, min(hinnat), max(hinnat), sc.POS_VARI[pos]))
    return sc.ranges(rivit=rivit, otsikko="Price range by position",
                     x_label="Price (m)", x_yksikko="m")


# --- taulukot --------------------------------------------------------------

def _taulukko(otsikot: list[str], rivit: list[list[str]]) -> str:
    """Sivuston oma taulukko.

    🔴 LUOKKANIMI EI OLE KOSMETIIKKAA. Ensimmainen versio kirjoitti
    `class="tablewrap"` ja `class="sortable"` - kumpaakaan ei ole
    olemassa. Mitattu renderoidysta kuvasta: taulukko oli tyylitön, ja
    `scripts/table_tools.py` kytkee lajittelun JA suodattimen valitsimella
    `table.lb`, joten nekin jaivat pois. Mikaan ei valittanut: keksitty
    luokka on validia HTML:aa.
    """
    th = "".join(f"<th>{escape(o)}</th>" for o in otsikot)
    tr = "".join("<tr>" + "".join(f"<td>{s}</td>" for s in r) + "</tr>"
                 for r in rivit)
    return (f'<div class="tblwrap"><table class="lb">'
            f"<thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>")


def _pelaajarivit(pelaajat: list[dict], kentta: str) -> list[list[str]]:
    ulos = []
    for p in pelaajat:
        tila = STATUS_SANA.get(p["status"], p["status"])
        ulos.append([
            escape(p["name"] or ""), escape(p["team_code"] or ""), p["pos"],
            f'{p["price"]:g}', f'{p["owned_pct"]:g}%',
            str(vaiheet.arvo(p, kentta)),
            # Tyhja solu, ei viivaa: em dash on kielletty julkisessa
            # tekstissa (muisti: em-dash-ja-pinta-pariteetti), ja
            # "Available" 20 rivilla on kohinaa.
            tila if p["status"] != "available" else "",
        ])
    return ulos


# --- sivut -----------------------------------------------------------------

def _jsonld(nimi: str, kuvaus: str, url: str) -> list[dict]:
    return [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": nimi, "description": kuvaus, "url": url,
        "isPartOf": {"@type": "WebSite", "name": "GoalIQ", "url": BASE},
        "publisher": {"@type": "Organization", "name": "GoalIQ"},
    }]


def sivu_hub(doc: dict, nyt: dt.datetime) -> str:
    P = doc["players"]
    kentta, sarake = vaiheet.pistekentta(doc, nyt)
    seuraava = vaiheet.seuraava_kierros(doc, nyt)
    vaihe = vaiheet.vaihe(doc, nyt)

    if seuraava and seuraava.get("deadline_utc"):
        dl = (f'Matchday {seuraava["md"]} deadline is '
              f'{_fmt_deadline(seuraava["deadline_utc"])}.')
    else:
        dl = "No deadline ahead: the league phase is over."

    saatavilla = sum(1 for p in P if p["status"] == "available")
    poissa = len(P) - saatavilla

    # 🔴 Copy sanoo mita luvut EIVAT ole. Esikaudella sivulla ei ole
    # yhtaan taman kauden suoritusnumeroa, ja lukijan on tiedettava se
    # ilman etta han paattelee sen puuttuvista sarakkeista.
    if vaihe == vaiheet.ESIKAUSI:
        perusta = (
            "<p>No matchday of this season has been played yet, so there are "
            "no points, minutes or form figures for it anywhere on this page. "
            "The points column shows last season's UCL total, carried in the "
            "official feed, and it is labelled that way. Prices, ownership "
            "and squad status are current.</p>")
    else:
        perusta = (
            "<p>Points and minutes on this page are from the current UCL "
            "season.</p>")

    kartoitus = sorted(P, key=lambda p: -p["owned_pct"])[:20]

    body = (
        f"{perusta}"
        "<h2>Where the money is</h2>"
        "<p>Every player owned by more than 1% of managers, plotted by price "
        "against ownership. Players below that line are left out on purpose: "
        f"{sum(1 for p in P if p['owned_pct'] <= 1.0)} of the "
        f"{len(P)} players sit near zero and would be one dark block.</p>"
        f"{kaavio_omistus(P)}"
        "<h2>What each position costs</h2>"
        "<p>Goalkeepers and defenders are capped well below midfielders and "
        "forwards, which is what makes the budget decision a forward "
        "decision.</p>"
        f"{kaavio_hinnat(P)}"
        "<h2>Who cannot be picked</h2>"
        f"<p>{poissa} of {len(P)} players are not available: injured, "
        "suspended, doubtful, or left out of the registered squad. Clubs "
        "are ordered by injuries, suspensions and doubts, not by the total: "
        "a club can leave a dozen players out of its registered squad and "
        "still have everyone fit.</p>"
        f"{kaavio_saatavuus(P, doc['teams'])}"
        "<h2>Most owned</h2>"
        + _taulukko(["Player", "Club", "Pos", "Price", "Owned", sarake,
                     "Status"], _pelaajarivit(kartoitus, kentta))
        + '<p><a href="/ucl/prices">Full list of all '
        f'{len(P)} players</a> · '
        '<a href="/ucl/team-news">Squad availability by club</a></p>')

    hero = ("<h1>UCL Fantasy: prices, ownership and squad news</h1>"
            f"<p class=\"lede\">{escape(dl)} Free, no login. Updated from "
            "the official UEFA feed every six hours.</p>")

    return _page(
        "UCL Fantasy prices, ownership and squad availability | GoalIQ",
        "Free UCL Fantasy data: every player's price and ownership, squad "
        "availability by club, and the next matchday deadline. No login.",
        f"{BASE}/ucl", hero, body,
        _jsonld("UCL Fantasy tools",
                "Free UCL Fantasy prices, ownership and squad availability.",
                f"{BASE}/ucl"))


def sivu_hinnat(doc: dict, nyt: dt.datetime) -> str:
    P = sorted(doc["players"], key=lambda p: (-p["owned_pct"], -p["price"]))
    kentta, sarake = vaiheet.pistekentta(doc, nyt)
    body = (
        f"<p>All {len(P)} players in the UCL Fantasy game, sorted by "
        "ownership. Click a column heading to sort.</p>"
        f"{kaavio_omistus(doc['players'])}"
        + _taulukko(["Player", "Club", "Pos", "Price", "Owned", sarake,
                     "Status"], _pelaajarivit(P, kentta)))
    hero = ("<h1>UCL Fantasy prices and ownership</h1>"
            f'<p class="lede">Every player, every price, every ownership '
            "percentage. Straight from the official feed.</p>")
    return _page(
        "UCL Fantasy prices and ownership, all players | GoalIQ",
        f"All {len(P)} UCL Fantasy players with price, ownership percentage, "
        "position and squad status. Free, no login.",
        f"{BASE}/ucl/prices", hero, body,
        _jsonld("UCL Fantasy prices and ownership",
                "Every UCL Fantasy player with price and ownership.",
                f"{BASE}/ucl/prices"))


def sivu_team_news(doc: dict, nyt: dt.datetime) -> str:
    P = doc["players"]
    kentta, sarake = vaiheet.pistekentta(doc, nyt)
    poissa = [p for p in P if p["status"] in POISSA]
    poissa.sort(key=lambda p: (POISSA.index(p["status"]), -p["owned_pct"]))
    body = (
        f"<p>{len(poissa)} of {len(P)} players cannot be picked right now. "
        "Injured, suspended and doubtful players are listed first, then "
        "players left out of the registered squad.</p>"
        f"{kaavio_saatavuus(P, doc['teams'])}"
        + _taulukko(["Player", "Club", "Pos", "Price", "Owned", sarake,
                     "Status"], _pelaajarivit(poissa, kentta)))
    hero = ("<h1>UCL Fantasy squad availability</h1>"
            '<p class="lede">Who is injured, suspended, doubtful or left '
            "out of the registered squad, by club.</p>")
    return _page(
        "UCL Fantasy squad availability and team news | GoalIQ",
        "Which UCL Fantasy players are injured, suspended, doubtful or out "
        "of the registered squad, by club. Free, no login.",
        f"{BASE}/ucl/team-news", hero, body,
        _jsonld("UCL Fantasy squad availability",
                "UCL Fantasy players unavailable to pick, by club.",
                f"{BASE}/ucl/team-news"))


def main() -> int:
    if not DATA.exists():
        print("data/ucl_fantasy.json puuttuu - aja scripts/ingest_ucl.py ensin")
        return 1
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    nyt = dt.datetime.now(dt.timezone.utc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sivut = {
        ROOT / "ucl" / "index.html": sivu_hub(doc, nyt),
        ROOT / "ucl" / "prices.html": sivu_hinnat(doc, nyt),
        ROOT / "ucl" / "team-news.html": sivu_team_news(doc, nyt),
    }
    for polku, html in sivut.items():
        polku.write_text(html, encoding="utf-8")
        print(f"  {polku.relative_to(ROOT).as_posix()}  {len(html):,} merkkia")
    print(f"ucl: {len(sivut)} sivua, vaihe={vaiheet.vaihe(doc, nyt)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
