"""Ilmaiset indeksoitavat FPL-long-tail-sivut (#120).

Kolme evergreen-URLia, per-GW päivittyvä sisältö:

  fpl/best-captain.html    "Best FPL captain GW{n}" — top-pick NIMENÄ, sijat
                           2-3 niminä, EI xP-lukuja (3.8. korjaus: alkuperäinen
                           "captain suggestion on ilmainen appissa" oli VÄÄRÄ
                           premissi, CaptainRanker on kokonaan premium).
  fpl/differentials.html   "Best FPL differentials GW{n}" — top-1 nimi + EO
                           (FPL:n omaa julkista dataa), EI xP:tä → Premium.
  fpl/price-changes.html   "FPL price changes" — koko risers/fallers-lista
                           (price watch on ilmainen appissa). Esikausi →
                           rehellinen tyhjätila meta.notesta.

EI Premium-vuotoa: teaser-syvyys peilaa appin free/premium-rajaa.
Datalähteet: data/fpl_xp_projections.json + data/fpl_price_watch.json
(committattuja) + /api/fantasy/differentials (EO vaatii bootstrap-joinin —
yksi kevyt kutsu; virhe → sivu ohitetaan, ei kaatoa).
Gambling-safe: predictions/xP/model — EI betting/odds/tips.
Ajo: python -m scripts.build_fpl_longtail  (accuracy-log.yml, 3 h)
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 15.8: analytiikka MYOS longtail-sivuille. Mitattu 15.8: fpl.html sisalsi
# PostHogin (202 latausta / 14 vrk) mutta /fpl/expected-points ja
# /fpl/predicted-lineups eivat sisaltaneet sita LAINKAAN -> koko generoitu
# sisaltopinta oli mittaamaton. Sama vakio kuin paasivuilla eika kopio:
# kaksi rinnakkaista snippettia eriytyisivat hiljaa.
from scripts.build_fpl_page import (  # noqa: E402
    POSTHOG_SNIPPET,
    ROOT as _FP_ROOT,
    write_urlset,
)
from scripts.mobile_css import MOBILE_COLS_JS, MOBILE_CSS
from scripts.share_card_js import SHARE_CARD_JS
from scripts.table_tools import TABLE_TOOLS_JS  # noqa: E402

# #119b: long-tail-sivut omaan lapsi-sitemapiin (sitemap.xml-index listaa).
# Wholesale OUT_DIR-globista → entry jokaiselle olemassa olevalle sivulle,
# myös silloin kun jokin data-lähde puuttui tältä ajolta (sivu jää voimaan).
SITEMAP_FPL_PATH = _FP_ROOT / "sitemap-fpl.xml"
from scripts.build_prediction_pages import DISCLAIMER
from src.models.fpl_club_best import POSITIONS, club_best_rows, gap_text

BASE = "https://goaliq.app"
OUT_DIR = ROOT / "fpl"
XP_PATH = ROOT / "data" / "fpl_xp_projections.json"
PW_PATH = ROOT / "data" / "fpl_price_watch.json"
# #128/#120: xG- + DefCon-leaders-sivut samasta nightly-cachesta kuin API
LEADERS_PATH = ROOT / "data" / "fpl_player_leaders.json"
# 8.8 STATS-ZONE: ilmainen suodatettava raakataulukko (scripts/build_fpl_stats.py)
STATS_PATH = ROOT / "data" / "fpl_player_stats.json"
# FPL-PLAYER-POINTS-TABLE (23.8.2026, Villen tilaus): toteutuneet pisteet
# kierroksittain + kierroksen alla JAADYTETTY xP samalla rivilla.
PLAYER_GW_PATH = ROOT / "fpl" / "player-gw.json"
XP_FROZEN_DIR = ROOT / "data" / "fpl_xp_frozen"
# 8.8: joukkuetason puolustusprofiili (scripts/build_understat_team_defence.py)
DEFENCE_PATH = ROOT / "data" / "understat_team_defence_2526.json"
API = "https://api.goaliq.app"  # 27.7: pois estetysta onrender.com-vyohykkeesta

UPSELL = (
    '<div class="rec">Powered by the GoalIQ match model with a published, '
    'pre-match-logged track record. The full toolkit (captain ranker, all '
    'differentials, transfer planner) is <a '
    'href="https://pro.goaliq.app/?tab=premium">GoalIQ Premium</a>: '
    '3.99 €/month or 25 €/season. '
    'One subscription on web, iOS and Android.</div>'
)

# 24.7 brand redesign: sama ilme kuin fpl.html (Space Grotesk, magenta-bar,
# tumma ink-hero, cream-body, paper-kortit, pillerinapit). Longtail-sivuilla
# OMA template — build_prediction_pages.CSS/NAV/_page jää prediction-sivujen
# vanhaan asuun, ei sivuvaikutuksia sinne.
def _window_label(meta: dict, gws, fallback_n: int) -> str:
    """Ohut kaare jaettuun `fpl_gameweek.window_label`:iin (25.8)."""
    from src.models.fpl_gameweek import window_label
    return window_label(meta, gws, fallback_n)


def _strip_css_comments(css: str) -> str:
    """Poista /* ... */ -kommentit ENNEN kuin CSS kirjoitetaan sivulle.

    11.8.2026: CSS-lohkon perustelukommentit ovat suomeksi ja sisaltavat em
    dasheja, ja ne servattiin sellaisenaan julkisella englanninkielisella
    sivulla (nakyvat view-sourcesta). Kommentit kuuluvat lahdekoodiin, eivat
    tuotokseen. Ei kaanneta niita: pidetaan perustelut taalla ja jatetaan ne
    pois HTML:sta.

    Huom: ei koske MOBILE_CSS/SHARE_CARD_JS -moduuleja, ne injektoidaan
    erikseen; jos niissa on kommentteja, aja sama funktio niillekin.
    """
    out = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    # Kommenttien tilalle jaaneet tyhjat rivit pois, muuten sivulle jaa
    # kymmenia perakkaisia rivinvaihtoja.
    return re.sub(r"\n{2,}", "\n", out).strip()


CSS = """
.brand-icon{width:22px;height:22px;display:inline-block;vertical-align:-4px;margin-right:8px;flex:none;}
:root{--teal:#2ED6C2;
--teal-ink:#2ED6C2;--amber:#F5C542;--amber-deep:#F5C542;
--gold:#F5C542;--gold-deep:#F5C542;--coral:#FF8A5C;
--ink:#0B0A09;--ink2:#141311;--cream:#F3F2F2;
--paper:#1F1D1A;--muted:#A8A29A;--hero-muted:#A8A29A;--faint:#8A847A;
--line:rgba(243,242,242,0.24);--line-strong:rgba(243,242,242,0.40);--radius:0;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--ink);color:var(--cream);font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;line-height:1.6;}
h1,h2,h3,.brand{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;text-transform:uppercase;letter-spacing:-0.01em;}
.wrap{max-width:820px;margin:0 auto;padding:0 20px;}
.bar{height:1px;background:var(--line);}
/* Bug 26 Jul: color was var(--cream) = cream on a cream background -> every
   color:inherit child would be invisible. Leftover from the dark-to-light
   switch. */
.dark{background:var(--ink);
color:var(--cream);}
nav{display:flex;align-items:center;justify-content:space-between;
padding:18px 0;font-size:14px;}
nav a{text-decoration:none;color:var(--cream);font-weight:600;}
.brand{font-size:20px;font-weight:700;letter-spacing:.5px;}
.brand span{color:var(--amber);}
.nav-cta{background:transparent;color:var(--amber);border:1px solid var(--amber);padding:8px 16px;
border-radius:var(--radius);font-weight:700;}
.nav-cta:hover{background:var(--amber);color:var(--ink);}
/* 9 Aug (spotted on a large screen): this was 'padding:26px 0 44px', and
   the shorthand zeroed .wrap's horizontal padding -> the hero heading and
   lede started 20px left of everything else. The page had two different
   left edges (303 and 323). Vertical padding only. */
.hero{padding-top:26px;padding-bottom:44px;}
.hero h1{color:var(--cream);font-size:31px;line-height:1.15;margin:0 0 12px;
letter-spacing:-0.01em;}
.hero .lede{color:var(--hero-muted);max-width:640px;}
h2{font-size:22px;margin:30px 0 10px;}
.content{padding-top:26px;}
.card{background:var(--paper);border:1px solid var(--line);
border-radius:var(--radius);padding:18px 20px;margin-bottom:14px;}
.lede{color:var(--muted);margin-bottom:22px;}
.stat-row{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0;}
.stat{background:var(--paper);border:1px solid var(--line);
border-radius:var(--radius);padding:14px 18px;flex:1 1 140px;}
.stat b{display:block;font-size:22px;color:var(--amber);
font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
.stat span{color:var(--muted);font-size:12px;}
.rec{border:1px solid var(--line);background:var(--paper);
border-radius:var(--radius);padding:16px 20px;font-size:14px;color:var(--muted);
margin:24px 0 16px;}
.rec a{color:var(--teal);font-weight:700;}
.cta-row{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0;}
.btn{background:transparent;color:var(--amber);border:1px solid var(--amber);font-weight:700;padding:12px 22px;
border-radius:var(--radius);text-decoration:none;font-size:14px;}
.btn:hover{background:var(--amber);color:var(--ink);}
.btn.ghost{background:transparent;color:var(--cream);
border:1px solid var(--line);}
.btn.ghost:hover{background:transparent;color:var(--amber);}
.mrow{display:flex;align-items:center;justify-content:space-between;gap:10px;
padding:12px 0;border-bottom:1px solid var(--line);}
.mrow:last-child{border-bottom:none;}
.mrow a{color:var(--teal);font-weight:700;text-decoration:none;}
.mrow .meta{color:var(--muted);font-size:12px;}
.pick{color:var(--teal-ink);font-weight:700;font-size:13px;white-space:nowrap;}
footer{border-top:1px solid var(--line);margin-top:36px;padding:22px 0 34px;
color:var(--muted);font-size:13px;}
footer a{color:var(--teal);}
.note{color:var(--muted);font-size:12px;margin:18px 0;}
/* 26 Jul: the xG leaderboard opened up, full table free */
/* 8 Aug (user report): the page column is 820px, so even a wide screen did
   not show every table column and you had to scroll sideways with the arrow.
   Now EVERY table may escape the column and grow with the window up to
   1560px; header, body text and footer stay at 820 (line length is
   readability). 96vw rather than 100vw so the vertical scrollbar cannot push
   the page sideways. The table itself does NOT stretch as filler: width:auto
   + min-width keeps narrow tables at their previous width, centered, and
   only wide ones use the extra room. On a narrow screen min() returns 100%
   -> behavior is exactly what it was. */
/* Article typography. Long-form notes need paragraph spacing; without it the
   blocks run together into one wall of text. */
.note-body p{margin:0 0 15px;}
.note-body h3{margin:26px 0 10px;font-size:1.05rem;letter-spacing:.01em;}
.note-body h3:first-child{margin-top:0;}
/* Article data table. Deliberately NOT .lb-wrap: that stretches a table to
   the full viewport and centres it, which is wrong for a narrow four-column
   table inside a text column. It still gets its own scroll container so a
   narrow screen scrolls the table rather than the page. */
.tblwrap{overflow-x:auto;margin:14px 0;}
.note-tbl{border-collapse:collapse;font-size:.95rem;min-width:22rem;}
.note-tbl th,.note-tbl td{padding:5px 14px 5px 0;text-align:left;
white-space:nowrap;}
.note-tbl th{border-bottom:1px solid var(--line-strong);font-weight:600;}
.note-tbl td:nth-child(n+2){text-align:right;font-variant-numeric:tabular-nums;}
.note-tbl tbody tr+tr td{border-top:1px solid var(--line);}
.lb-wrap{overflow-x:auto;margin:14px 0;
width:min(96vw,1560px);margin-left:50%;transform:translateX(-50%);}
/* 820px was .wrap's max-width INCLUDING PADDING, but the text column is
   780px. A table centered at 820 in the full-width wrapper thus started
   20px left of the text. Same number as the text column -> edges align;
   wide tables still grow. */
.lb-wrap>.lb{width:auto;min-width:min(100%,780px);margin:0 auto;}
/* 96vw + translateX must not create page-level horizontal scrolling */
html,body{overflow-x:clip;}
.lb{width:100%;border-collapse:collapse;font-size:14px;}
.lb th,.lb td{padding:8px 10px;text-align:left;
border-bottom:1px solid var(--line);white-space:nowrap;}
.lb th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;
color:var(--muted);font-weight:700;}
.lb td.n,.lb th.n{text-align:right;font-variant-numeric:tabular-nums;}
.lb td.hi{color:var(--amber);font-weight:700;}
.lb tbody tr:last-child td{border-bottom:none;}
.lb thead th:hover{color:var(--amber);}
.lbctl{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:16px 0 6px;}
.lbctl .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;
color:var(--muted);font-weight:700;margin-left:6px;}
.lbctl .lbl:first-child{margin-left:0;}
.chips{display:inline-flex;gap:6px;}
.chip{min-width:34px;border:1px solid var(--line-strong);background:var(--paper);
color:var(--cream);border-radius:var(--radius);padding:6px 12px;font-size:13px;
font-weight:600;cursor:pointer;}
.chip.on{background:var(--amber);border-color:var(--amber);color:var(--ink);}
.lbctl select{border:1px solid var(--line-strong);background:var(--paper);
color:var(--cream);border-radius:var(--radius);padding:6px 12px;font-size:13px;
font-weight:600;}
/* Neutral team shirt (no crest or player likeness, see the IP note in code) */
.lb td.tm{display:flex;align-items:center;gap:7px;}
/* Confidence flag (10 Aug): the team's rating rests on weaker information.
   DESCRIPTIVE - it does not say which way the projection moves. Muted on
   purpose: it is a margin note on the row, not the row's main point. */
.tflag{flex:0 0 auto;font-size:10px;font-weight:600;letter-spacing:.04em;
text-transform:uppercase;padding:1px 5px;border:1px solid var(--line-strong);
border-radius:var(--radius);opacity:.72;white-space:nowrap;}
.kit{flex:0 0 auto;display:block;}
/* Model XI pitch. 26 Jul: same look as the SPA's TeamPitchManager and the
   mobile #106 pitch (teal tint, #108 palette) - NOT grass green. Decision:
   the brand palette beats literal grass, and all three surfaces must look
   the same. */
.pitch{background:rgba(46,214,194,0.22);border:1px solid var(--line);
border-radius:var(--radius);padding:10px 6px;margin:18px 0;}
.xirow{display:flex;justify-content:space-evenly;flex-wrap:wrap;gap:8px;
margin:10px 0;}
.xip{width:76px;text-align:center;color:var(--cream);}
.xip b{display:block;font-size:11px;font-weight:600;margin-top:2px;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.xip span{display:block;font-size:10px;color:var(--muted);
font-variant-numeric:tabular-nums;}
@media (max-width:520px){.xip{width:64px;}.xirow{gap:6px;}}
@media (max-width:520px){.cta-row{flex-direction:column;align-items:stretch;}
.btn{text-align:center;}}
.toolnav{margin:34px 0 6px;padding-top:18px;border-top:1px solid var(--line);
display:flex;flex-direction:column;gap:10px;justify-content:flex-start;
align-items:stretch;}
.navgrp{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;}
/* justify-content MUST be set here. The bare `nav` rule further up sets
   space-between for the page header, and .clubnav inherits it, which spread
   the last row of club links evenly across the full width. An element
   selector that reaches a component added later is a silent trap. */
.clubnav{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 10px;
justify-content:flex-start;
margin:0 0 26px;padding-bottom:14px;border-bottom:1px solid var(--line);}
.clubnav b{font-size:13px;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);font-weight:600;margin-right:4px;}
.clubnav a{font-size:14px;color:var(--cream);text-decoration:none;
border:1px solid var(--line);padding:3px 7px;}
.clubnav a:hover{border-color:var(--amber);}
.share{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px;
justify-content:flex-start;margin:26px 0 6px;}
.share span{font-size:13px;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);}
.share a{font-size:14px;color:var(--cream);text-decoration:none;
border:1px solid var(--line);padding:3px 10px;}
.share a:hover{border-color:var(--amber);}
.clubnav b.here{color:var(--amber);border:1px solid var(--amber);
padding:3px 7px;font-size:14px;letter-spacing:0;text-transform:none;}
.navgrp b{min-width:88px;}
.toolnav b{font-size:13px;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);font-weight:600;margin-right:2px;}
.toolnav a{font-size:15px;color:var(--cream);text-decoration:none;
border-bottom:1px solid var(--line);padding-bottom:1px;}
.toolnav a:hover{border-bottom-color:currentColor;}
""" + MOBILE_CSS


# 28.7: SISAINEN LINKITYS. GSC:n URL-tarkastus paljasti etta naista sivuista
# 5/6 oli Googlelle taysin tuntemattomia: "Viittaavia sivustokarttoja ei
# havaittu" JA "Viittaava sivu: Ei havaittuja". Sitemap yksin on heikko
# signaali - sivu jolle ei osoita yksikaan linkki on orpo, eika Google
# priorisoi sen indeksointia. Mitattu ennen korjausta: fpl.html -> 0 kpl
# /fpl/*-linkkeja, etusivu -> 1 (model-xi), /predictions -> 0.
# Naiden sivujen koko olemassaolon syy on FPL-hakuliikenne ennen GW1:ta.
#
# 15.8: TAMA LISTA OLI ITSE VANHENTUNUT. Yllaoleva kommentti kuvaa vian, mutta
# sen jalkeen lisatyt sivut jaivat listalta pois — mitattu 15.8: `expected-
# points` ja `team-news` eivat olleet siina, joten yksikaan sisarsivu eika
# etusivu osoittanut niihin. `expected-points` on se sivu johon X-postaukset
# linkittavat, eli orvoksi oli jaanyt tarkein ilmaispinta.
#
# Lista on nyt PORTITETTU (tests/test_fpl_team_news_page.py): jokaisen
# generoidun /fpl/-sivun on oltava taalla. Kuratoitu lista ilman porttia
# vanhenee joka kerta kun sivuja lisataan, ja se on tapahtunut nyt kahdesti.
_TOOL_LINKS = [
    ("/fpl/best-captain", "Captain picks"),
    ("/fpl/expected-points", "Expected points"),
    ("/fpl/club-best", "Best per club"),
    ("/fpl/team-news", "Team news"),
    ("/fpl/notes", "Notes"),
    ("/fpl/model-xi", "Model XI"),
    ("/fpl/differentials", "Differentials"),
    ("/fpl/price-changes", "Price changes"),
    ("/fpl/xg-leaders", "xG leaders"),
    ("/fpl/defcon", "DefCon leaders"),
    ("/fpl/points", "Points vs projection"),
    ("/fpl/stats", "Player stats"),
    ("/fpl/defence", "Defence profiles"),
    ("/fpl/predicted-lineups", "Predicted XI"),
    ("/fpl/minutes-accuracy", "Minutes accuracy"),
]


# Valikon ryhmittely (15.8.2026, Villen vaatimus: "jos sivuja alkaa olla
# paljon niin sitten menut pystyyn").
#
# Sivuja on nyt 32 ja tasainen linkkirivi on lukukelvoton siina koossa: se on
# 30 sanaa perakkain ilman hierarkiaa, eika lukija loyda siita mitaan. Ryhmat
# vastaavat kysymykseen jota lukija kysyy, eivat sita miten sivut syntyivat.
#
# Ryhma per rivi, otsikko lihavoituna. Nykyinen sivu jaa pois omasta
# ryhmastaan mutta ryhma sailyy — muuten valikko hyppii sivulta toiselle.
_NAV_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Picks", ("/fpl/best-captain", "/fpl/model-xi", "/fpl/differentials",
               "/fpl/expected-points")),
    ("Teams", ("/fpl/club-best", "/fpl/defence", "/fpl/team-news",
               "/fpl/predicted-lineups")),
    ("Numbers", ("/fpl/points", "/fpl/stats", "/fpl/xg-leaders",
                 "/fpl/defcon", "/fpl/price-changes")),
    ("Reading", ("/fpl/notes", "/fpl/minutes-accuracy")),
]


def _tool_nav(canonical: str) -> str:
    """Ristiinlinkitys ryhmiteltyna, nykyinen sivu pois.

    Renderoidaan <nav>-elementtina eika pelkkana linkkilistana, jotta
    sivun oma navigointirakenne on koneluettava.

    Jokainen `_TOOL_LINKS`-polku kuuluu johonkin ryhmaan; ryhmittelemattomat
    paatyvat "More"-ryhmaan, jottei uusi sivu voi kadota valikosta hiljaa.
    Sivusopimus (tests/test_page_contract.py) vaatii sisaantulevan linkin, ja
    tama on se paikka josta se yleensa tulee.
    """
    here = canonical.rstrip("/").replace(BASE, "")
    labels = dict(_TOOL_LINKS)
    ryhmitellyt = {h for _, hs in _NAV_GROUPS for h in hs}
    ryhmat = list(_NAV_GROUPS)
    loput = tuple(h for h, _ in _TOOL_LINKS if h not in ryhmitellyt)
    if loput:
        ryhmat.append(("More", loput))

    osat = []
    for otsikko, polut in ryhmat:
        linkit = "".join(
            f'<a href="{h}">{escape(labels.get(h, h))}</a>'
            for h in polut if h != here and h in labels
        )
        if linkit:
            osat.append(f'<span class="navgrp"><b>{otsikko}</b>{linkit}</span>')
    return (
        '<nav class="toolnav" aria-label="More free FPL tools">'
        + "".join(osat)
        + "</nav>\n"
    )


SOCIAL_IMAGE = f"{BASE}/assets/brand/goaliq-social-1200x630.png"


def _social_meta(title: str, desc: str, canonical: str,
                 image: str | None = None) -> str:
    """OG + Twitter Card, sama muoto ja sama kuva-asset kuin fpl.html:ssä
    (build_fpl_page.py). Ilman näitä sivu renderöityy jaettaessa paljaana
    linkkinä ilman otsikkoa, kuvausta tai kuvaa."""
    t, d = escape(title), escape(desc)
    img = image or SOCIAL_IMAGE
    return (
        '<meta property="og:type" content="article">\n'
        f'<meta property="og:title" content="{t}">\n'
        f'<meta property="og:description" content="{d}">\n'
        f'<meta property="og:url" content="{canonical}">\n'
        f'<meta property="og:image" content="{img}">\n'
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">\n'
        '<meta property="og:site_name" content="GoalIQ">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        '<meta name="twitter:site" content="@goaliqapp">\n'
        f'<meta name="twitter:title" content="{t}">\n'
        f'<meta name="twitter:description" content="{d}">\n'
        f'<meta name="twitter:image" content="{img}">\n'
    )



def _og_image(canonical: str) -> str:
    """Sivukohtainen og:image jos sellainen on generoitu, muuten yhteinen.

    Kortit: assets/brand/gen_og_cards.py (goaliq-app). Polku johdetaan
    canonicalin slugista, joten uusi sivu saa oman korttinsa automaattisesti
    heti kun tiedosto on olemassa — eika yksikaan render-funktio tarvitse
    muutosta. Puuttuva tiedosto putoaa yhteiseen korttiin, ei rikkinaiseen
    URLiin (jaettu linkki ilman kuvaa on parempi kuin 404-kuva).
    """
    slug = canonical.rstrip("/").rsplit("/", 1)[-1]
    rel = f"assets/brand/og/{slug}-1200x630.png"
    polku = _FP_ROOT / rel
    if not polku.exists():
        return SOCIAL_IMAGE
    # 🔴 SISALTOTIIVISTE URLIIN (15.8). Villen havainto: "Linkkikuva edelleen
    # toi sama?" Palvelimen tiedosto oli jo uusi (live ja lokaali tavulleen
    # identtiset), mutta X ja Bluesky valimuistittavat esikatselukortin
    # URL-kohtaisesti. Sama tiedostonimi eri sisallolla = alusta tarjoilee
    # vanhaa kuvaa, eika ankkuri (#slug) murra sita koska fragmenttia ei
    # laheteta palvelimelle lainkaan.
    #
    # Tiiviste muuttuu vain kun kuva muuttuu, joten tama ei riko
    # valimuistitusta silloin kun mitaan ei ole muuttunut.
    tiiviste = hashlib.sha256(polku.read_bytes()).hexdigest()[:8]
    return f"{BASE}/{rel}?v={tiiviste}"

def _page(title: str, desc: str, canonical: str, hero: str, body: str,
          jsonld: list[dict]) -> str:
    """Longtail-sivun runko uudessa ilmeessä: magenta-bar + tumma header/hero
    (h1 + lede) + cream-content. Sama head-järjestys kuin fpl.html:ssä."""
    ld = "".join(
        '<script type="application/ld+json">\n'
        + json.dumps(b, ensure_ascii=False, indent=1)
        + "\n</script>\n"
        for b in jsonld
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="UTF-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        f"<title>{escape(title)}</title>\n"
        f'<meta name="description" content="{escape(desc)}" />\n'
        f'<link rel="canonical" href="{canonical}" />\n'
        # 29.7 (#225-SEO): OG/Twitter myös longtail-sivuille — kuusi
        # fpl-alasivua jaettiin paljaana linkkinä vaikka fpl.html emittoi
        # nämä. Sama kuva-asset, arvot _page()-parametreista.
        f"{_social_meta(title, desc, canonical, _og_image(canonical))}"
        # 27.7: koko ikonisetti myös alasivuille. Pelkkä .ico jätti selaimet
        # käyttämään matalaresoluutioista varianttia ja iOS:n kotinäytön ilman
        # ikonia — 187 alasivua näytti eri merkkiä kuin neljä pääsivua.
        '<link rel="icon" href="/favicon.ico" sizes="any">\n'
        '<link rel="icon" type="image/png" sizes="32x32" href="/assets/brand/goaliq-favicon-32.png">\n'
        '<link rel="icon" type="image/png" sizes="48x48" href="/assets/brand/goaliq-favicon-48.png">\n'
        '<link rel="apple-touch-icon" sizes="180x180" href="/assets/brand/goaliq-apple-touch-180.png">\n'
        + POSTHOG_SNIPPET + "\n" +
        TABLE_TOOLS_JS + "\n" +
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        # 26.7 PERF: preload+onload, ei render-blocking stylesheetiä — FCP ei
        # odota kolmannen osapuolen CSS:ää. noscript = varmistus.
        '<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family='
        'IBM+Plex+Mono:wght@400;500;600;700&display=swap" onload="this.rel=\'stylesheet\'">\n'
        '<noscript><link href="https://fonts.googleapis.com/css2?family='
        'IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet"></noscript>\n'
        '<meta name="theme-color" content="#0B0A09">\n'
        f"{ld}"
        f"<style>{_strip_css_comments(CSS)}</style>\n"
        "</head>\n<body>\n"
        '<header class="dark">\n'
        '<div class="bar"></div>\n'
        '<div class="wrap"><nav>'
        '<a class="brand" href="/"><svg class="brand-icon" width="22" height="22" viewBox="0 0 44 44" role="img" aria-label="GoalIQ" focusable="false"><rect x="0" y="0" width="44" height="44" fill="#F5C542"/><text x="22" y="30" text-anchor="middle" font-family="IBM Plex Mono,ui-monospace,Consolas,monospace" font-size="20" font-weight="700" letter-spacing="-0.5" fill="#0B0A09">IQ</text></svg>Goal<span>IQ</span></a>'
        '<span><a href="/predictions">All predictions</a> · '
        '<a class="nav-cta" href="https://pro.goaliq.app/">Try it live</a></span>'
        "</nav></div>\n"
        f'<div class="wrap hero">\n{hero}\n</div>\n'
        "</header>\n"
        f'<main class="wrap content">\n{body}\n'
        f"{_tool_nav(canonical)}"
        f'<footer>© 2026 GoalIQ · '
        f'<a href="/predictions">Football predictions</a> · '
        f'<a href="/fpl">Free FPL tools</a> · '
        f'<a href="/privacy.html">Privacy</a><br>{DISCLAIMER}</footer>\n'
        "</main>\n" + MOBILE_COLS_JS + "</body>\n</html>\n"
    )


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fetch_differentials() -> dict | None:
    # 27.7: EKSPLISIITTINEN User-Agent on PAKOLLINEN. Kun API siirtyi
    # api.goaliq.app-domainiin Cloudflaren taakse, CF alkoi torjua urllib:n
    # oletus-UA:n ("Python-urllib/3.x") 403:lla -> differentials-sivu olisi
    # lakannut paivittymasta HILJAA (builderi nappaa poikkeuksen ja jatkaa
    # varoituksella). onrender.com-osoite vastasi ilman tata.
    #
    # Sama koskee KAIKKIA skripteja jotka hakevat api.goaliq.app:sta
    # urllibilla — jos lisaat uuden, muista UA.
    req = urllib.request.Request(
        f"{API}/api/fantasy/differentials?max_ownership=10",
        headers={"User-Agent": "GoalIQ-PageBuilder/1.0 (+https://goaliq.app)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except Exception as e:
        print(f"VAROITUS: differentials-haku epäonnistui: {type(e).__name__}: {e}")
        return None


def _cta() -> str:
    return (
        '<div class="cta-row">'
        '<a class="btn" href="https://pro.goaliq.app/?tab=premium">Open GoalIQ Premium</a>'
        '<a class="btn ghost" href="/fpl">Free clean-sheet probability &amp; FDR</a>'
        "</div>"
    )


def render_captain(xp: dict, now: datetime) -> str | None:
    meta = xp.get("meta") or {}
    players = xp.get("players") or []
    if not meta.get("available") or not players:
        return None
    # 25.8: actionable eika next_gameweek. Otsikko lupaa "Best FPL Captain
    # GW{n}", ja kesken kierroksen next_gameweek osoittaa jo lukittuun
    # kierrokseen -> sivu suosittelisi kapteenia kierrokselle joka on pelattu.
    from src.models.fpl_gameweek import actionable_gameweek as _act_gw
    gw = _act_gw(meta) or "?"

    # 8.8.2026 (Villen havainto): sivu lupaa otsikossa "Best FPL Captain GW{n}"
    # mutta sorttasi xp_per_gw:lla (koko horisontin keskiarvo) -> sivu ja appin
    # CaptainRanker antoivat ERI ykkosen (B.Fernandes vs Gabriel) samasta
    # datasta. Kapteeni valitaan YHDEKSI kierrokseksi, joten avain on seuraavan
    # GW:n xp. Fallback xp_per_gw:hen jos gameweeks puuttuu (vanha payload).
    def _next_gw_xp(p: dict) -> float:
        gws = p.get("gameweeks") or []
        if gws and gws[0].get("xp") is not None:
            return float(gws[0]["xp"])
        return float(p.get("xp_per_gw") or 0.0)

    ranked = sorted(players, key=_next_gw_xp, reverse=True)
    top = ranked[0]
    alts = ranked[1:3]
    url = f"{BASE}/fpl/best-captain"
    # 3.8.2026 PREMIUM-VUOTO KIINNI: xP-luku pois julkiselta sivulta.
    # Taman sivun alkuperainen perustelu oli "free-pariteetti: captain
    # suggestion on ilmainen appissa". Se EI pida paikkaansa: CaptainRanker
    # on kokonaan premium (CAPTAIN_PAYWALL_SOURCE = 'fantasy_captain',
    # FantasyEdge.tsx:71) ja captain_viewed emittoituu vain premium-listalta,
    # eli free-kayttaja ei nae appissa yhtaan kapteenisuositusta. Julkinen
    # sivu antoi siis nimen JA xP:n ilmaiseksi. NIMI jaa (se on sivun
    # SEO-arvo ja teaser), LUKU menee lukon taakse — sama linja kuin
    # 2.8. ottelusivujen xG-korjauksessa: paywall kertoo mita puuttuu.
    title = f"Best FPL Captain GW{gw}: Model Pick | GoalIQ"
    desc = (
        f"The GoalIQ model's best FPL captain for Gameweek {gw}: "
        f"{top['web_name']} ({top['team_short']}). Horizon expected points "
        f"for the top 100 players are free on our expected-points page; "
        f"the gameweek-specific number and the full captain ranking are "
        f"GoalIQ Premium. Updated every round."
    )
    hero = (
        f"<h1>Best FPL captain, Gameweek {gw}</h1>"
        f'<p class="lede">The GoalIQ match model\'s top captain pick for GW{gw} is '
        f"<strong>{escape(top['web_name'])} ({escape(top['team_short'])})</strong>.</p>"
    )
    # 9.8: Start% nakyviin. Sivu nimesi kapteenin ja piilotti KAIKKI luvut
    # ("xP in Premium"), joten lukija ei nahnyt onko valinta varma vai
    # kolikonheitto. 32 % pelaajista on vyohykkeella p_start 0,35-0,70, jossa
    # xMins on kahden lopputuloksen keskiarvo eika kumpikaan tapahdu.
    # Aloitustodennakoisyys EI ole se mita premium myy (se on xP ja
    # personointi), joten sen nayttaminen ei syo tuotetta - se tekee
    # suosituksesta luettavan.
    def _start_txt(p: dict) -> str:
        v = p.get("p_start")
        return f"starts {round(float(v) * 100)}%" if isinstance(v, (int, float)) \
            else "start probability in Premium"

    body = (
        f'<div class="stat-row">'
        f'<div class="stat"><b>{escape(top["web_name"])}</b>'
        f'<span>#1 pick · {escape(top["team_short"])} · {_start_txt(top)} '
        "· GW xP in Premium</span></div>"
        + "".join(
            f'<div class="stat"><b>{escape(p["web_name"])}</b>'
            f'<span>contender · {escape(p["team_short"])} · {_start_txt(p)} '
            "· GW xP in Premium</span></div>"
            for p in alts
        )
        + "</div>"
        '<p class="note"><strong>Start%</strong> is how likely the model thinks '
        "he is to be in the XI. Near 50 it is a coin flip, and a captaincy on a "
        "coin flip is a bet on team news. Check the press conference before you "
        "commit the armband.</p>"
        # 21.8: FPL-XP-COPY-RISTIRIITA. Tama sivu vaitti "Expected points
        # are in GoalIQ Premium" samalla kun /fpl/expected-points servaa
        # horisontti-xP:n top-100:lle ilmaiseksi. Raja on oikeasti:
        # top-100-horisontti-xP on sisaltoa (ilmainen), per-GW-luku ja
        # tyokalut ovat tuote. Portti 21.8 kaatoi "every player" -muodon:
        # ilmaissivu nayttaa tasan 100 rivia, ei jokaista pelaajaa.
        '<p class="note">Horizon expected points for the top 100 players '
        'are free on <a href="/fpl/expected-points">the expected points '
        "table</a>. This ranking sorts by the gameweek-specific number "
        "instead, and that number and the full ranked list are part of "
        "GoalIQ Premium.</p>"
        f"{UPSELL}{_cta()}"
        f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def render_differentials(diff: dict, now: datetime) -> str | None:
    players = (diff or {}).get("players") or []
    if not players:
        return None
    meta = diff.get("meta") or {}
    gw_txt = f"GW{meta['gw']}" if meta.get("gw") else "this gameweek"
    top = players[0]
    url = f"{BASE}/fpl/differentials"
    title = f"Best FPL Differentials {gw_txt}: Low-Owned Model Picks | GoalIQ"
    # 3.8.2026 PREMIUM-VUOTO KIINNI (sama silmays kuin best-captain):
    # DifferentialsSection on appissa premium (FantasyTools.tsx:3424) eika
    # siina ole free-teaseria, joten xP-luku ei saa nakya julkisella sivulla.
    # Omistus-% JAA: se on FPL:n omaa julkista dataa, ei mallin tuotos.
    desc = (
        f"GoalIQ's model differential for {gw_txt}: {top['web_name']} "
        f"({top['team_short']}), owned by just {top['owned_pct']}% of managers. "
        f"GW expected points and {len(players)} more low-owned picks in GoalIQ Premium."
    )
    hero = (
        f"<h1>Best FPL differentials, {escape(gw_txt)}</h1>"
        f'<p class="lede">A differential is a low-owned player (under 10% '
        f"ownership) the model rates far higher than the crowd does. Today's "
        f"top model differential:</p>"
    )
    body = (
        f'<div class="stat-row">'
        f'<div class="stat"><b>{escape(top["web_name"])}</b>'
        f'<span>{escape(top["team_short"])} · owned {top["owned_pct"]}% · '
        f"GW xP in Premium</span></div>"
        f'<div class="stat"><b>+{len(players) - 1} more</b>'
        f"<span>full differential list in Premium</span></div>"
        f"</div>"
        f"{UPSELL}{_cta()}"
        f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def _eta_label(p: dict) -> str:
    """Paiva kynnykseen ihmisluettavana. 22.8: FPL julkaisee taman itse, ja
    se on sivun ainoa toimintaan johtava luku. Puuttuva kentta (vanha
    velocity-arvio) -> "on watch", EI "not soon" — arvio ei tiennyt paivaa."""
    # "due" vaittaisi varmuutta jota lahde itse ei vaita: FPL antaa jokaiselle
    # projektiolle likelihood-kentan. "projected" on se mita luku on.
    # "no date yet" eika "on watch": jalkimmainen on SPA:ssa jo statuslabel
    # eri merkityksessa, ja sama sanapari kahdessa merkityksessa luetaan vaarin.
    eta = p.get("eta_days")
    if eta == 0:
        return "projected tonight"
    if eta == 1:
        return "projected tomorrow"
    if isinstance(eta, int):
        return f"projected in {eta} days"
    return "no date yet"


def render_price_changes(pw: dict, now: datetime) -> str:
    meta = (pw or {}).get("meta") or {}
    risers = (pw or {}).get("risers") or []
    fallers = (pw or {}).get("fallers") or []
    url = f"{BASE}/fpl/price-changes"
    title = "FPL Price Changes Tonight: Risers & Fallers | GoalIQ"
    desc = (
        "FPL's own price projection for tonight's risers and fallers, with "
        "the day FPL projects each change. Free, no sign-in."
    )

    def rows(items, label):
        if not items:
            return ""
        lines = "".join(
            f'<div class="mrow"><div><strong>{escape(p["web_name"])}</strong>'
            f'<div class="meta">£{p["now_cost"]:.1f}m · '
            f'{round(float(p.get("confidence") or 0) * 100)}% of the way · '
            f'{_eta_label(p)}</div></div>'
            f'<span class="pick">{label}</span></div>'
            for p in items[:10]
        )
        return f'<div class="card">{lines}</div>'

    if not risers and not fallers:
        content = (
            f'<div class="card"><p class="lede" style="margin:0">'
            f'{escape(meta.get("note") or "Price watch goes live when the FPL game opens for the new season.")}'
            f"</p></div>"
        )
    else:
        content = (
            ("<h2>Risers</h2>" + rows(risers, "rising")) if risers else ""
        ) + (
            ("<h2>Fallers</h2>" + rows(fallers, "falling")) if fallers else ""
        )
    official = bool(meta.get("official_projection"))
    hero = (
        "<h1>FPL price changes: risers and fallers</h1>"
        '<p class="lede">' + (
            "FPL's own price projection, ordered so the closest change is at "
            "the top. Free on the web and in the app."
            if official else
            "GoalIQ tracks net transfer velocity to estimate which players are "
            "about to rise or fall in price. Free on the web and in the app, "
            "rebuilt every few hours.") + "</p>"
    )
    body = (
        f"{content}"
        f"{UPSELL}{_cta()}"
        f'<p class="note">Updated {now.strftime("%d %b %Y")} · '
        f'{escape(meta.get("disclaimer") or "")} {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


# Joukkuevarit lyhytkoodilla. LAHDE: web/pro-spa/src/lib/teamColors.ts
# (joka on generoitu mobiilin lib/teamMeta.ts:sta) -> sama vari kaikilla
# kolmella pinnalla. Klubien primary-varit ovat julkista tietoa.
#
# IP-TURVA: emme kayta pelaajakuvia emmeka klubien krestejä. Ne ovat Premier
# Leaguen/klubien tekijanoikeus- ja tavaramerkkiaineistoa, ja appi on
# molemmissa kaupoissa IP-puhtaana. Tassa renderoidaan NEUTRAALI paitasiluetti
# joukkueen varilla + lyhenne, sama SVG-polku kuin TeamKit.svelte/TeamKit.tsx.
# 17.8: varit ja niiden apurit siirretty src/models/team_colors.py:hyn,
# jotta jakokortti kayttaa TASMALLEEN samoja varaja kuin sivut.
from src.models.team_colors import (  # noqa: E402
    _TEAM_COLORS, _hash_color, _team_color, _darken,
    _KIT_BY_SHORT, _kit_layers,
)


_JERSEY = ("M 33 15 L 43 9 C 46 15 54 15 57 9 L 67 15 L 84 27 L 76 42 L 67 36 "
           "L 67 86 Q 67 90 63 90 L 37 90 Q 33 90 33 86 L 33 36 L 24 42 L 16 27 Z")
_SLEEVE_L = "M 33 15 L 16 27 L 24 42 L 33 36 Z"
_SLEEVE_R = "M 67 15 L 84 27 L 76 42 L 67 36 Z"
# KIT-KUVIOT 21.8: kaulus + kuviotaulu tulevat src/models/team_colors.py:sta
# (peili jaetusta teamKits.ts:sta) — sama geometria ja piirtojarjestys kuin
# TeamKit.svelte / shareCard.ts (runko -> kuvio -> hihat -> kaulus ->
# aariviiva). Kuvio leikataan runkoon clipPathilla.
_COLLAR = "M 43 9 C 46 15 54 15 57 9"


def _hash_color(name: str) -> str:
    """Deterministinen fallback, peili teamColors.ts:n hashColorista."""
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFF
    return f"hsl({h % 360}, 45%, 32%)"


def _team_color(short: str) -> tuple[str, str]:
    hit = _TEAM_COLORS.get((short or "").upper())
    return hit if hit else (_hash_color(short or "?"), "#FFFFFF")


def _darken(hex_color: str, factor: float = 0.7) -> str:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (hex_color or "").strip())
    if not m:
        return hex_color
    n = int(m.group(1), 16)
    parts = [max(0, round(((n >> s) & 0xFF) * factor)) for s in (16, 8, 0)]
    return "#{:02x}{:02x}{:02x}".format(*parts)


def _kit_defs(shorts) -> str:
    """Yksi <symbol> per joukkue kerran sivun alussa.

    MIKSI: rivikohtainen inline-SVG toisti saman polun 373 kertaa ja kasvatti
    sivun 175 kB -> 468 kB. Joukkueita on ~20, joten symboli per joukkue +
    pieni <use> per rivi pitaa sivun kevyena.
    """
    out = [f'<clipPath id="k-body"><path d="{_JERSEY}"/></clipPath>']
    for s in sorted({(x or "").upper() for x in shorts if x}):
        color, _ = _team_color(s)
        pattern, secondary = _KIT_BY_SHORT.get(s, ("solid", None))
        # 'sleeves' = kontrastihihat: hiha kakkosvarilla darken-johdon sijaan.
        sleeve = secondary if (pattern == "sleeves" and secondary) else _darken(color)
        # EI lyhennetta paidan sisalle: 26 px:ssa se on lukukelvoton ja sotkee
        # siluetin, ja sama lyhenne on jo paidan vieressa omana solunaan.
        # (TeamKit.svelte/tsx pitaa tekstin, koska ne renderoivat 44 px:ssa.)
        pattern_svg = ""
        layers = _kit_layers(pattern) if secondary else []
        if layers:
            shapes = "".join(
                f'<rect x="{l[1]}" y="{l[2]}" width="{l[3]}" height="{l[4]}" fill="{secondary}"/>'
                if l[0] == "rect" else f'<path d="{l[1]}" fill="{secondary}"/>'
                for l in layers
            )
            pattern_svg = f'<g clip-path="url(#k-body)">{shapes}</g>'
        collar = secondary or sleeve
        out.append(
            f'<symbol id="k{escape(s)}" viewBox="0 0 100 100">'
            f'<path d="{_JERSEY}" fill="{color}"/>'
            f"{pattern_svg}"
            f'<path d="{_SLEEVE_L}" fill="{sleeve}"/>'
            f'<path d="{_SLEEVE_R}" fill="{sleeve}"/>'
            f'<path d="{_COLLAR}" fill="none" stroke="{collar}" '
            f'stroke-width="3.5" stroke-linecap="round"/>'
            f'<path d="{_JERSEY}" fill="none" stroke="rgba(10,8,32,0.28)" '
            f'stroke-width="3" stroke-linejoin="round"/>'
            f"</symbol>"
        )
    return ('<svg width="0" height="0" style="position:absolute" '
            'aria-hidden="true"><defs>' + "".join(out) + "</defs></svg>")


def _kit_svg(short: str, size: int = 26) -> str:
    """Viittaus valmiiseen symboliin. Ei krestia, ei sponsoria, ei pelaajakuvaa."""
    s = escape((short or "").upper())
    return (f'<svg class="kit" width="{size}" height="{size}" aria-hidden="true">'
            f'<use href="#k{s}"/></svg>')


XI_NAILED_FLOOR = 0.75


def _xi_start_risk(xi) -> str:
    """Nosta esiin ne XI:n pelaajat jotka EIVAT ole varmoja avaajia (9.8).

    Sivu suosittelee yhdentoista pelaajan joukkuetta ja nayttaa jokaisen xP:n,
    mutta ei kertonut kuinka varma kukin paikka on. 32 % kaikista pelaajista on
    vyohykkeella p_start 0,35-0,70, jossa xP on kahden lopputuloksen keskiarvo
    eika kumpikaan tapahdu — eli XI:n kokonaisluku voi levata pelaajilla jotka
    eivat pelaa lainkaan.

    Numero jokaiseen paitaan sotkisi kentan, joten nostetaan vain poikkeamat.
    Kynnys 0,75: sen ylapuolella pelaaja on kaytannossa naulattu.
    """
    risky = [p for p in xi
             if isinstance(p.get("p_start"), (int, float))
             and p["p_start"] < XI_NAILED_FLOOR]
    if not risky:
        # Prosentti johdetaan vakiosta: kovakoodattuna se valehtelisi heti kun
        # XI_NAILED_FLOOR muuttuu (havaittu negatiivisessa kontrollissa 9.8).
        return ('<p class="note"><strong>Every player in this XI projects as a '
                "nailed starter</strong> (start probability "
                f"{round(XI_NAILED_FLOOR * 100)}% or higher). "
                "The total does not rest on anyone who might be benched.</p>")
    risky.sort(key=lambda p: p["p_start"])
    names = ", ".join(
        f"{escape(p['web_name'])} {round(p['p_start'] * 100)}%" for p in risky)
    return ('<p class="note"><strong>Not everyone here is nailed.</strong> '
            f"{names}. Those totals are an average of two outcomes, playing "
            "and not playing, so the XI total is less certain than it looks. "
            "Check team news before you copy it.</p>")


def render_model_xi(xp: dict, now: datetime) -> str | None:
    """Model XI kenttagrafiikkana (26.7).

    MIKSI: sivustolla ei ollut yhtaan grafiikkaa, ja "beat the model" -liigalla
    ei ollut kotisivua. Mallin oma XI on jo olemassa oleva kasite (se postataan
    someen gen_card.py:lla) mutta se ei nakynyt webissa missaan.

    XI tulee fpl_rate_team.optimal_budget_xi():sta = SAMA heuristiikka kuin
    rate-my-teamin benchmark, joten sivu ja tuote eivat voi eriytya.
    """
    from src.models.fpl_rate_team import (BUDGET_TENTHS, POS_NAME,
                                          optimal_budget_xi)
    players = xp.get("players") or []
    if not xp.get("meta", {}).get("available") or not players:
        return None
    et = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    pool = []
    for p in players:
        t = et.get(p.get("pos"))
        if t is None or p.get("price") in (None, ""):
            continue
        pool.append({
            # 28.7: id ja xmins pakollisia - penkkivalinta tarvitsee molemmat
            # (duplikaattisuoja + pelattavuusvaatimus).
            "id": p.get("id"),
            "xmins": p.get("xmins"),
            "element_type": t,
            "price": int(round(float(p["price"]) * 10)),   # tenths
            "club": p.get("team_short") or p.get("team"),
            "xp_horizon_total": float(p.get("xp_horizon_total") or 0.0),
            "xp_per_gw": float(p.get("xp_per_gw") or 0.0),
            "web_name": p.get("web_name") or "",
            "team_short": p.get("team_short") or "",
        })
    xi = optimal_budget_xi(pool)
    if not xi:
        return None

    rows = {t: [p for p in xi if p["element_type"] == t] for t in (1, 2, 3, 4)}
    for t in rows:
        rows[t].sort(key=lambda p: p["xp_horizon_total"], reverse=True)
    shape = "-".join(str(len(rows[t])) for t in (2, 3, 4))
    total_xp = sum(p["xp_horizon_total"] for p in xi)
    cost = sum(p["price"] for p in xi) / 10.0

    def line(ps: list[dict]) -> str:
        cells = "".join(
            '<div class="xip">'
            f'{_kit_svg(p["team_short"], size=44)}'
            f'<b>{escape(p["web_name"])}</b>'
            f'<span>{p["xp_horizon_total"]:.1f} xP</span>'
            "</div>"
            for p in ps
        )
        return f'<div class="xirow">{cells}</div>'

    # 28.7 (Villen havainto): penkki nakyviin. Vertailukohta on KOKO 15, ja
    # penkin pelattavuus on osa sen uskottavuutta - "halvimmat mahdolliset"
    # -penkki ei ole joukkue jonka kukaan voisi oikeasti pelata kauden lapi.
    from src.models.fpl_rate_team import bench_of_last_optimum
    bench = bench_of_last_optimum()
    bench_cost = sum(p["price"] for p in bench) / 10.0
    bench_block = ""
    if bench:
        bench_block = (
            '<h2 class="bench-h">Bench</h2>'
            f'<p class="muted">The other four in the 15, {bench_cost:.1f}m. '
            "Outfield bench players must project at least 45 expected minutes "
            "a game, so the squad can cover a blank without a transfer. The "
            "backup keeper is the cheapest available: he only plays if the "
            "first choice does not.</p>"
            + line(sorted(bench, key=lambda p: (p["element_type"],
                                                -p["xp_horizon_total"]))))

    pitch = ('<div class="pitch">'
             + "".join(line(rows[t]) for t in (1, 2, 3, 4))
             + "</div>" + bench_block)

    url = f"{BASE}/fpl/model-xi"
    title = "The GoalIQ Model XI: best 100.0m FPL squad on xP | GoalIQ"
    desc = (f"The highest-scoring XI inside the 100.0m budget: {shape}, "
            f"{total_xp:.1f} projected points over the horizon, with a bench "
            f"that actually plays. Free, no sign-in, rebuilt daily.")
    # 28.7: vaite optimaalisuudesta VAIN kun ratkaisija on sen todistanut.
    # Ennen tata paivaa sivu vaitti "strongest" ahneesta heuristiikasta joka
    # jai tuotantodatalla 15.2 xP optimista.
    from src.models.fpl_rate_team import optimal_xi_proven
    claim = ("The highest-scoring XI that fits inside the standard 100.0m "
             "budget, proven optimal by exhaustive search"
             if optimal_xi_proven() else
             "The strongest XI the GoalIQ model found inside the standard "
             "100.0m budget")
    # 28.7 (Villen havainto): budjetti kattaa 15 pelaajaa, ei 11. Aiempi
    # vertailukohta varasi penkkiin halvimmat mahdolliset, mika on
    # epärealistista: siirtoja on rajallisesti, joten penkkiläinen on joskus
    # pakko pelauttaa. Sivun tekstin on kerrottava se, muuten luku nayttaa
    # paremmalta kuin mika on pelattavissa.
    hero = ("<h1>The Model XI</h1>"
            f'<p class="lede">{claim}, ranked on projected points. '
            "The budget has to cover a full 15, so the four on the bench are "
            "the cheapest players who still project real minutes: the squad "
            "can cover a blank without spending a transfer. "
            "This is the same squad logic the rate-my-team benchmark uses, so "
            "the page and the product cannot drift apart.</p>")
    body = (
        f'<div class="stat-row">'
        f'<div class="stat"><b>{shape}</b><span>Shape</span></div>'
        f'<div class="stat"><b>{total_xp:.1f}</b><span>Projected points, XI</span></div>'
        f'<div class="stat"><b>{cost:.1f}m</b><span>XI cost, {bench_cost:.1f}m on the bench</span></div>'
        f"</div>"
        f"{_kit_defs(p['team_short'] for p in list(xi) + list(bench))}"
        f"{pitch}"
        f"{_xi_start_risk(xi)}"
        '<p class="note">Shirts show club colours only. GoalIQ is not '
        "affiliated with the Premier League and uses no club badges or player "
        "images. Projected points are model estimates, not betting advice.</p>"
        '<div class="rec">The model plays this season in a public mini-league. '
        '<a href="https://fantasy.premierleague.com/leagues/auto-join/jgi6j9">'
        "Join with code jgi6j9</a> and try to beat it. Season winner gets a "
        "year of Premium, free.</div>"
        f"{UPSELL}{_cta()}"
        f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def _xg_payload(leaders: dict) -> str:
    """Kompakti JSON selainlaskentaa varten: [nimi, joukkue, pos, hinta,
    [[min, xg, xa, xgi], ...enintaan 10 viimeisinta]].

    Selain laskee tasta 3/5/10 pelin ikkunat seka per-game- ja per-90-luvut,
    joten yksi payload kattaa lajittelun, suodattimet ja ikkunavalinnan ilman
    yhtaan API-kutsua. Ikkunasemantiikka on sama kuin palvelimella
    (fpl_leaders._window_rows = recent_games[-window:]) -> JS kayttaa
    slice(-w), jolloin luvut tasmaavat bitilleen server-renderoidyn
    oletustaulukon kanssa.
    """
    out = []
    for p in leaders.get("players") or []:
        games = p.get("recent_games") or []
        if not games:
            continue
        rows = [[
            int(g.get("minutes") or 0),
            round(float(g.get("xg") or 0.0), 2),
            round(float(g.get("xa") or 0.0), 2),
            round(float(g.get("xgi") or 0.0), 2),
        ] for g in games[-10:]]
        s = p.get("season") or {}
        out.append([
            p.get("web_name", ""), p.get("team_short", ""), p.get("pos", ""),
            round(float(p.get("price") or 0.0), 1), rows,
            # kausitotaalit: [minuutit, avaukset, xG, xA, xGI]
            [int(s.get("mins") or 0), int(s.get("starts") or 0),
             float(s.get("xg") or 0.0), float(s.get("xa") or 0.0),
             float(s.get("xgi") or 0.0)],
            # paidan varit [pohja, hiha, teksti] -> JS piirtaa saman kitin
            list(_team_color(p.get("team_short", ""))[:1])
            + [_darken(_team_color(p.get("team_short", ""))[0])]
            + [_team_color(p.get("team_short", ""))[1]],
        ])
    return json.dumps(out, separators=(",", ":"), ensure_ascii=False)


# Selainlogiikka: ikkuna (3/5/10), per game vs per 90, lajittelu, suodattimet.
# Ei em dashia missaan nakyvassa tekstissa (viestintatyyli SS1b).
# 🔴 KAKSI ERI KAUTTA SAMASSA TAULUKOSSA (24.8). Rullaavat ikkunat (3/5/10)
# lukevat `recent_games`ia joka on BASIS-kauden otteluita; Season-ikkuna
# lukee `season`-lohkoa jonka `refresh_current_attrs` tayttaa ELAVASTA
# bootstrapista eli KULUVASTA kaudesta. Ennen 24.8 Season-ikkuna sanoi "full
# season" ilman kautta, ja sen ylapuolella oleva basis-rivi sanoi "2025/26" -
# luvut olivat 26/27:n GW1:sta. Nyt kumpikin ikkuna nimeaa kautensa
# (BASIS_K / TARGET_K, injektoidaan render_xg_leadersissa).
#
# HUOM: tahan merkkijonoon EI kirjoiteta suomea, se shippaa julkiselle
# englanninkieliselle sivulle. Portti: tests/test_no_finnish_in_public_js.py
XG_JS = """
<script>
(function(){
 var D=window.__XG__||[],w=5,per90=false,pos='',team='',key=5,desc=true;
 // Show 100 rows by default. WHY: 373 rows = ~5000 DOM nodes, and every
 // control click rebuilt them all through innerHTML -> the page lagged
 // badly. 100 covers practically everything, and "show all" is one click
 // away. The payload still holds everything, so filtering and sorting work
 // on the full data - only the DISPLAY is capped.
 var LIMIT=100,showAll=false;
 // Same neutral shirt silhouette as in server rendering and in
 // TeamKit.svelte/TeamKit.tsx. No crest, no player likeness (IP).
 var JP='M 33 15 L 43 9 C 46 15 54 15 57 9 L 67 15 L 84 27 L 76 42 L 67 36 '
  +'L 67 86 Q 67 90 63 90 L 37 90 Q 33 90 33 86 L 33 36 L 24 42 L 16 27 Z';
 function kit(c,lbl){
  // Points at the same <symbol> library the server renders once.
  return '<svg class="kit" width="26" height="26" aria-hidden="true">'
   +'<use href="#k'+(lbl||'').toUpperCase()+'"/></svg>';
 }
 // Minutes threshold. Per 90 is broken without it: a player with 2 minutes
 // tops the list as pure noise. The threshold is VISIBLE and adjustable,
 // not a silent hide: the user sees which filter is on and can remove it.
 var minm=0;
 var tb=document.getElementById('xgb'),cnt=document.getElementById('xgc');
 if(!tb)return;
 var BASIS_K='__BASIS_K__',TARGET_K='__TARGET_K__';
 function agg(p){
  if(w==='S'){
   // Full season: bootstrap totals. "Per game" mode shows TOTALS (per
   // match is not meaningful for the season: we have starts, not
   // appearances), "Per 90" divides by minutes.
   var s=p[5]||[0,0,0,0,0],d=per90?(s[0]/90):1;
   if(!d)d=1;
   return {n:p[0],t:p[1],p:p[2],c:p[3],g:s[1],m:s[0],k:p[6],
           xg:s[2]/d,xa:s[3]/d,xgi:s[4]/d};
  }
  var g=p[4].slice(-w),m=0,xg=0,xa=0,xgi=0;
  for(var i=0;i<g.length;i++){m+=g[i][0];xg+=g[i][1];xa+=g[i][2];xgi+=g[i][3];}
  var d=per90?(m/90):g.length;
  if(!d)d=1;
  return {n:p[0],t:p[1],p:p[2],c:p[3],g:g.length,m:m,k:p[6],
          xg:xg/d,xa:xa/d,xgi:xgi/d};
 }
 function rows(){
  var r=[];
  for(var i=0;i<D.length;i++){
   // Same rule as on the server (fpl_leaders.rank_xg_leaders): goalkeepers
   // out by default, because this is an xG list, not a saves list. The GKP
   // filter shows them separately. Without this the page would give two
   // different numbers.
   if(D[i][2]==='GKP'&&pos!=='GKP')continue;
   if(pos&&D[i][2]!==pos)continue;
   if(team&&D[i][1]!==team)continue;
   var a=agg(D[i]);
   if(per90&&a.m<1)continue;
   if(a.m<minm)continue;
   r.push(a);
  }
  // Indices match the column headings: 0 #, 1 Player, 2 Team, 3 Pos,
  // 4 Price, 5 xG, 6 xA, 7 xGI, 8 Mins, 9 Games.
  var ks=['n','n','t','p','c','xg','xa','xgi','m','g'];
  var k=ks[key];
  r.sort(function(x,y){
   var A=x[k],B=y[k];
   if(typeof A==='string')return desc?B.localeCompare(A):A.localeCompare(B);
   return desc?B-A:A-B;
  });
  return r;
 }
 function draw(){
  var r=rows(),h='';
  var n=showAll?r.length:Math.min(LIMIT,r.length);
  for(var i=0;i<n;i++){
   var a=r[i];
   h+='<tr><td class="n">'+(i+1)+'</td><td>'+a.n+'</td><td class="tm">'
    +kit(a.k,a.t)+'<span>'+a.t+'</span></td><td class="m-hide">'
    +a.p+'</td><td class="n m-hide">'+a.c.toFixed(1)+'</td><td class="n hi">'
    +a.xg.toFixed(2)+'</td><td class="n">'+a.xa.toFixed(2)+'</td><td class="n">'
    +a.xgi.toFixed(2)+'</td><td class="n m-hide">'+a.m
    +'</td><td class="n m-hide">'+a.g
    +'</td></tr>';
  }
  tb.innerHTML=h;
  var more=document.getElementById('xgmore');
  if(more){
   if(showAll||r.length<=LIMIT){more.style.display='none';}
   else{more.style.display='';
        more.textContent='Show all '+r.length+' players';}
  }
  // In season mode the last column holds STARTS, not appearances (the
  // bootstrap provides starts). The header says which one, no guessing.
  var hh=document.querySelectorAll('#xgt2 thead th');
  if(hh&&hh[9])hh[9].textContent=(w==='S')?'Starts':'Games';
  // Each window names its own season: they come from different sources.
  var span=(w==='S')?', '+TARGET_K+' season so far'
                    :(', last '+w+' games each'+(BASIS_K?', '+BASIS_K:''));
  var rate=per90?', per 90 minutes':((w==='S')?', season totals':', per game');
  // The count must match what is on screen. Saying "400 players" while the
  // table renders 100 is the same failure as a claim the reader cannot check:
  // they count the rows and get a different answer from the page.
  var nn=showAll?r.length:Math.min(LIMIT,r.length);
  if(cnt)cnt.textContent=r.length+' players'+rate+span
   +(minm?', at least '+minm+' minutes played':', no minutes filter')
   +((nn<r.length)?'. Showing '+nn:'');
 }
 function chips(id,vals,cur,set){
  var e=document.getElementById(id);if(!e)return;
  e.innerHTML='';
  vals.forEach(function(v){
   var b=document.createElement('button');
   b.type='button';b.className='chip'+(cur()===v[0]?' on':'');b.textContent=v[1];
   b.onclick=function(){set(v[0]);sync();};
   e.appendChild(b);
  });
 }
 function sync(){
  chips('xgw',[[3,'3'],[5,'5'],[10,'10'],['S','Season']],
        function(){return w;},function(v){w=v;});
  // In season mode the left option is NOT per match but a sum (we have
  // starts, not appearances -> there is no true per-match divisor). The
  // chip text says so, otherwise 25.50 would read like a "per game" figure.
  chips('xgr',[[0,(w==='S')?'Total':'Per game'],[1,'Per 90']],
        function(){return per90?1:0;},
        function(v){
         var was=per90;per90=!!v;
         // Switching to per 90 turns the default minutes threshold on, and
         // leaving it turns it back off. The user's own choice stays in force
         // if they have already touched it on this screen.
         if(!was&&per90&&minm===0)minm=180;
         if(was&&!per90&&minm===180)minm=0;
        });
  chips('xgm',[[0,'Any'],[90,'90+'],[180,'180+'],[270,'270+']],
        function(){return minm;},function(v){minm=v;});
  chips('xgp',[['','All'],['GKP','GKP'],['DEF','DEF'],['MID','MID'],
        ['FWD','FWD']],function(){return pos;},function(v){pos=v;});
  draw();
 }
 var ts=[];for(var i=0;i<D.length;i++){if(ts.indexOf(D[i][1])<0)ts.push(D[i][1]);}
 ts.sort();
 var sel=document.getElementById('xgt');
 if(sel){
  sel.innerHTML='<option value="">All teams</option>';
  ts.forEach(function(t){
   var o=document.createElement('option');o.value=t;o.textContent=t;
   sel.appendChild(o);
  });
  sel.onchange=function(){team=sel.value;draw();};
 }
 var hs=document.querySelectorAll('#xgt2 thead th');
 for(var i=0;i<hs.length;i++){
  (function(i){
   hs[i].style.cursor='pointer';
   hs[i].onclick=function(){
    if(key===i)desc=!desc;else{key=i;desc=(i>=4);}
    draw();
   };
  })(i);
 }
 var moreBtn=document.getElementById('xgmore');
 if(moreBtn)moreBtn.onclick=function(){showAll=true;draw();};
 sync();
})();
</script>
"""


def render_xg_leaders(leaders: dict, now: datetime) -> str | None:
    """#128/#120: 'Top xG performers'.

    26.7: VAPAUTETTU. Aiemmin top-3 luvuilla + sijat 4-10 pelkkinä niminä
    ("Per-game numbers, xGI and position filters are on GoalIQ Premium").
    Maksumuuri hyödykedatan päällä ei puolustanut mitään — xG/xA/xGI on FPL:n
    itsensä julkaisemaa taaksepäin katsovaa dataa, jonka kilpailijat antavat
    ilmaiseksi. Nyt koko top-100 kaikilla sarakkeilla, ei porttia. Upsell
    siirtyi eteenpäin katsoviin mallin tuotoksiin (xP, captain ranker).
    Basis-label AINA näkyvissä (esikaudella 25/26-data, ei arvauksia)."""
    from src.models.fpl_leaders import rank_xg_leaders
    if not leaders.get("meta", {}).get("available"):
        return None
    # Ei keinotekoista kattoa: sivu listaa JOKAISEN pelaajan jolla on dataa
    # ikkunassa (~497). API:n top_n on rajattu 100:aan (le=100), mutta tämä
    # generaattori kutsuu mallia suoraan → ei kattoa. SPA/mobiili jäävät
    # 100:aan kunnes API:n raja nostetaan (vaatii backend-deployn).
    out = rank_xg_leaders(leaders, window=5, top_n=100000)
    rows = out["players"]
    if not rows:
        return None
    # rank_xg_leaders karsii metan, joten target_season luetaan raakadatan
    # metasta. Molemmat tarkistetaan: tyhja kausi pudottaa vaitteen pois
    # eika tuota "from  matches" -tyyppista rikkinaista lausetta.
    _lm = (leaders.get("meta") or {})
    _om = (out.get("meta") or {})
    _basis_k = str(_om.get("basis_season") or _lm.get("basis_season") or "")
    _target_k = str(_om.get("target_season") or _lm.get("target_season") or "")
    # 🔴 META EI RIITA KAUSIVAIHDOSSA. Kun FPL kaantaa GW1:n finished-lipun,
    # `basis_season` muuttuu target-kaudeksi mutta MIN_CURRENT_GAMES=3
    # tarkoittaa etta lahes jokainen rivi kantaa yha edellisen kauden
    # otteluita (per-rivi `basis`). Pelkkaan metaan nojaava lause vaittaisi
    # silloin kautta jota rivien data ei ole - ja pudottaisi samalla
    # artefaktin oman rehellisen "Mixed basis" -varauksen. Rivit ovat
    # totuus, meta on tarjoilijan nakemys.
    _rivikaudet = sorted({str(x.get("basis") or "")
                          for x in (leaders.get("players") or [])} - {""})
    _sekakausi = len(_rivikaudet) > 1
    # Ikkunan kausimerkinta JS:lle: sekatilassa tyhja, koska yhta kautta ei
    # ole. Vaara kausi olisi pahempi kuin puuttuva.
    _ikkuna_k = "" if _sekakausi else (_rivikaudet[0] if _rivikaudet else _basis_k)

    # 🔴 EI TALLENNETTUA LABELIA. `basis_label` on rakennushetkella kirjoitettu
    # proosa, ja se lupasi kadenssin ("updates as the new season plays") joka
    # oli epatosi: artefakti ei ollut liikkunut 23.7. jalkeen. Sama saanto
    # kuin kortin kausiviitteessa - johda rakenteisista kentista, ala parsi
    # tai toista viereista proosaa. Nain korjaus patee heti eika vasta
    # seuraavan artefaktiajon jalkeen.
    if _sekakausi:
        basis = (f"Rolling-window numbers mix seasons: a player with fewer "
                 f"than 3 games in {_target_k} still shows his "
                 f"{_rivikaudet[0]} matches. The season column is "
                 f"{_target_k} so far")
    elif _ikkuna_k and _target_k and _ikkuna_k != _target_k:
        basis = (f"Rolling-window numbers are from the {_ikkuna_k} season; "
                 f"the season column is {_target_k} so far")
    elif _ikkuna_k and _target_k:
        basis = (f"Rolling-window numbers and the season column are both "
                 f"{_target_k}")
    else:
        basis = out["meta"].get("basis_label") or ""
    # 🔴 KAKSI ERI KAUTTA SAMALLA SIVULLA, JA "rebuilt every few hours" OLI
    # EPATOSI MOLEMMILLE. Rullaavat ikkunat (3/5/10) lukevat `recent_games`ia
    # joka on BASIS-kauden otteluita (viimeinen pelattu toukokuussa, artefakti
    # rakennettu 23.7); Season-ikkuna lukee `season`-lohkoa jonka
    # refresh_current_attrs tayttaa ELAVASTA bootstrapista. Yksi tuoreusluku
    # on siis aina vaara jommallekummalle, ja kadenssilupaus oli vaara
    # molemmille. Sanotaan mika data on, ei milloin se paivittyy.
    if _sekakausi:
        xg_tuoreus = (
            f"rolling windows mix seasons until a player has 3 games in "
            f"{_target_k}, the season column uses {_target_k} totals so far")
    elif _ikkuna_k and _target_k and _ikkuna_k != _target_k:
        xg_tuoreus = (f"rolling windows use {_ikkuna_k} matches, the season "
                      f"column uses {_target_k} totals so far")
    elif _ikkuna_k:
        xg_tuoreus = (f"rolling windows and the season column are both "
                      f"{_ikkuna_k}")
    else:
        xg_tuoreus = "see the basis line below"

    url = f"{BASE}/fpl/xg-leaders"
    title = "Top xG Performers: FPL Expected Goals Leaders | GoalIQ"
    desc = (
        f"The top FPL expected-goals (xG) performers over each player's last "
        f"5 games: {rows[0]['web_name']} leads at {rows[0]['xg_per_game']:.2f} "
        f"xG per game. From official FPL match data: {xg_tuoreus}."
    )
    top3 = "".join(
        '<div class="stat">'
        f'<b>{escape(r["web_name"])}</b>'
        f'<span>#{i + 1} · {escape(r["team_short"])} · {r["xg_per_game"]:.2f} '
        f'xG/game · {r["games"]} games</span></div>'
        for i, r in enumerate(rows[:3])
    )
    # Koko lista taulukkona. Kaksi desimaalia on tarkoituksellista: 0.46 ja
    # 0.54 eivät saa näyttää samalta (FPL-yhteisön palaute 26.7).
    # Minuutit oletusikkunalle (w=5) server-renderoityyn tauluun. rank_xg_
    # leaders ei palauta minuutteja, joten haetaan ne samasta lahteesta id:lla.
    mins5 = {
        p["id"]: sum(int(g.get("minutes") or 0)
                     for g in (p.get("recent_games") or [])[-5:])
        for p in (leaders.get("players") or [])
    }
    trows = "".join(
        "<tr>"
        f'<td class="n">{i + 1}</td>'
        f'<td>{escape(r["web_name"])}</td>'
        f'<td class="tm">{_kit_svg(r["team_short"])}'
        f'<span>{escape(r["team_short"])}</span></td>'
        f'<td>{escape(r["pos"])}</td>'
        f'<td class="n">{r["price"]:.1f}</td>'
        f'<td class="n hi">{r["xg_per_game"]:.2f}</td>'
        f'<td class="n">{r["xa_per_game"]:.2f}</td>'
        f'<td class="n">{r["xgi_per_game"]:.2f}</td>'
        f'<td class="n">{mins5.get(r["id"], 0)}</td>'
        f'<td class="n">{r["games"]}</td>'
        "</tr>"
        # Palvelin renderoi 100 riviä, sama raja kuin JS:n oletus. Koko
        # aineisto on payloadissa (suodatus/lajittelu koskee kaikkia), joten
        # tama on puhtaasti DOM-painon rajaus: 373 riviä teki sivusta laggaavan.
        for i, r in enumerate(rows[:100])
    )
    kitdefs = _kit_defs(p.get("team_short") for p in (leaders.get("players") or []))
    controls = (
        '<div class="lbctl">'
        '<span class="lbl">Games</span><span id="xgw" class="chips"></span>'
        '<span class="lbl">Rate</span><span id="xgr" class="chips"></span>'
        '<span class="lbl">Min mins</span><span id="xgm" class="chips"></span>'
        '<span class="lbl">Position</span><span id="xgp" class="chips"></span>'
        '<select id="xgt" aria-label="Filter by team"></select>'
        "</div>"
        f'<p class="note" id="xgc">{len(rows)} players, per game, '
        "last 5 games each. Click a column to sort.</p>"
    )
    # 🔴 JAKOKORTTI PALVELIMEN RIVEILTA (SHARE-CARD-SERVER-ROWS).
    # Sivulla on suodattimet (Games / Rate / Min mins / Position / Team) JA
    # klikkilajittelu, joten DOM-lukija olisi kantanut sen nakyman johon jakaja
    # oli sattunut suodattaa — ei sita jonka linkista tuleva lukija nakee.
    #
    # 🔴 OTTELUIDEN MAARA ON KORTILLA, JA SE ON PAKKO OLLA. Lista on
    # jarjestetty xG:lla PER OTTELU, ja mitattu 25.8: oletusnakyman karjessa on
    # kolme YHDEN ottelun pelaajaa (Emersonn 65 min, Gonzalo 90 min, Maeda
    # 79 min). Per-game-luku yhden ottelun otoksesta ei ole vaara, mutta ilman
    # otoskokoa se luetaan kauden tasoksi. Sivulla lukija nakee Games-sarakkeen
    # ja Min mins -suodattimen; kortin on kannettava sama tieto.
    # 🔴 KAUSI ON KORTILLA, PAIVAMAARA EI. Julkaisuportti mittasi 25.8 etta
    # kortin kymmenesta rivista KUUSI on viime kaudelta (`basis=2025/26`):
    # rullaava ikkuna sekoittaa kausia kunnes pelaajalla on 3 ottelua talla
    # kaudella. "As of 25 Aug" ei ollut kopioitu maneeri vaan AKTIIVINEN
    # TUOREUSVAITE, ja se oli epatosi kuudella rivilla kymmenesta.
    #
    # 🔴 JA `GAMES`-SARAKE, JONKA LISASIN VARAUKSEKSI, KAANTYI VAARAAN
    # SUUNTAAN. Mitattu: jokainen 5 ottelun rivi on 2025/26 ja jokainen yhden
    # ottelun rivi on 2026/27. Otoskokoa katsova lukija paatyy siis
    # jarjestelmallisesti VANHIMPAAN dataan. Sarake jaa — se on oikea varaus —
    # mutta vasta kausimerkinnan kanssa se lukee oikein pain.
    #
    # Kausi johdetaan rakenteisista kentista (`_sekakausi`, `_rivikaudet`,
    # `_target_k`), ei kovakoodata eika toisteta viereista proosaa.
    # 🔴 KAUSI ALAOTSIKKOON, EI ALAVIITTEESEEN. Renderoija kutistaa alaviitteen
    # 17px -> 11px ja alaotsikon 22px -> 13px. Kausiversio alaviitteessa oli
    # 104 merkkia (hyvaksyttyjen korttien haarukka on 55-60), joten se olisi
    # renderoitynyt lahes minimikoossa. Varaus pienimmassa mahdollisessa
    # fontissa on sama vikaluokka kuin varaus vaarassa paikassa: se on
    # muodollisesti lasna ja kaytannossa poissa.
    _korttikaudet = kortin_kaudet(rows)
    kortti = _card_spec_attr(
        title="TOP xG PER GAME",
        # 🔴 KAUSI JOHDETAAN KORTIN OMISTA RIVEISTA, EI KOKO AINEISTOSTA.
        # `_rivikaudet` lasketaan kaikista 442 pelaajasta; kortti nayttaa 10.
        # Tanaan joukot osuvat yhteen, mutta kauden edetessa karkikymmenikko
        # tayttyy 2026/27-riveilla (basis kaantyy kolmen ottelun jalkeen) kun
        # hanta — loukkaantuneet ja reunapelaajat, satoja — kantaa 2025/26:n
        # pitkalle kevaaseen. Silloin `_sekakausi` on yha tosi ja kortti
        # sanoisi "mixing 2025/26 and 2026/27" kymmenesta rivista jotka ovat
        # KAIKKI tata kautta. Vaite kaantyisi epatodeksi ilman etta kukaan
        # koskee koodiin. Sivun oma basis-lause saa jaada koko aineiston
        # mukaiseksi, koska se kuvaa taulukkoa.
        subtitle=("Each player's last 5 games"
                  + (f", mixing {' and '.join(_korttikaudet)}"
                     if len(_korttikaudet) > 1
                     else (f", {_korttikaudet[0]}" if _korttikaudet else ""))),
        mid_label="GAMES",
        value_label="xG/GAME",
        foot="every player with data is free on goaliq.app/fpl/xg-leaders",
        foot2="FPL shot data, not betting advice",
        rows=[{"rank": i + 1, "name": r["web_name"],
               "team": r.get("team_short") or "", "tag": r.get("pos") or "",
               "mid": str(r.get("games") or 0),
               "value": ("%.2f" % (r.get("xg_per_game") or 0.0))}
              for i, r in enumerate(rows[:10])],
        file_name="goaliq-xg-leaders.png")
    table = (
        f'<div class="lb-wrap"><table class="lb" id="xgt2"{kortti}>'
        "<thead><tr>"
        # Mobiili (a) 9.8: Pos/Price/Mins/Games ovat suodatinkontekstia, xG/xA/
        # xGI on se mita sivulta tullaan katsomaan. Taulukko oli 589px = 1,5 x
        # puhelimen leveys; kuudella sarakkeella se mahtuu ilman vieritysta.
        # Sarakkeita EI poisteta DOMista -> JS:n indeksiviittaukset (hh[9])
        # ja lajittelu toimivat entiseen tapaan kaikilla leveyksilla.
        '<th class="n">#</th><th>Player</th><th>Team</th><th class="m-hide">Pos</th>'
        '<th class="n m-hide">Price</th><th class="n">xG</th>'
        '<th class="n">xA</th><th class="n">xGI</th>'
        '<th class="n m-hide">Mins</th><th class="n m-hide">Games</th>'
        "</tr></thead>"
        f'<tbody id="xgb">{trows}</tbody></table></div>'
        '<button type="button" class="chip" id="xgmore" '
        'style="margin:4px 0 8px;">Show all players</button>'
    )
    payload = (
        '<script id="xgdata">window.__XG__='
        f"{_xg_payload(leaders)};</script>"
    )
    hero = (
        "<h1>Top xG performers in FPL</h1>"
        '<p class="lede">Which players generate the most expected goals (xG) '
        "per game? Ranked over each player's last five played matches from "
        f"official FPL match data. Free, no sign-in: {xg_tuoreus}.</p>"
    )
    body = (
        f'<p class="note"><strong>{escape(basis)}</strong></p>'
        f'<div class="stat-row">{top3}</div>'
        f"<h2>Full leaderboard: every player with data ({len(rows)})</h2>"
        '<p class="note">Two decimals, because 0.46 and 0.54 are not the same '
        "player. Switch between per game and per 90 minutes, pick a 3, 5 or 10 "
        "game window, filter by position or team, and sort any column. No "
        "cut-off and no sign-in: this is public FPL match data, so it is not "
        "behind a subscription.</p>"
        + _share_button()
        + f"{kitdefs}{controls}{table}{payload}"
        # Kortti lukee palvelimen `data-card-spec`-attribuutin; DOM-lukija on
        # tarkoituksella `null`.
        + SHARE_CARD_JS.replace("__CARD_ROWS_FN__", "function(){return null;}")
        + XG_JS.replace("__BASIS_K__", _ikkuna_k).replace("__TARGET_K__", _target_k)
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def render_defcon(leaders: dict, now: datetime) -> str | None:
    """#128/#120: 'Best DefCon players' — FPL:n defensive contribution
    -pistemekaniikan luotettavimmat lähteet. Top-3 luvuilla, loput niminä.

    #226-DC (1.8.2026): basis vaihdettu viimeisistä 5 pelistä KOKO KAUTEEN ja
    nimittäjä starteiksi. Kaksi syytä: (1) esikaudella "viimeiset 5" on
    mielivaltainen häntä edelliskaudesta, (2) tämä on julkinen sivu jonka luvut
    verrataan Premier Leaguen omaan DC-taulukkoon — eri nimittäjä tuotti eri
    prosentin samasta datasta. Season-basis ei ole saatavilla ennen kuin
    per-GW-matriisi on rakennettu → fallback vanhaan, ei tyhjää sivua."""
    from src.models.fpl_leaders import (load_defcon_gw, rank_defcon_leaders,
                                        rank_defcon_season)
    if not leaders.get("meta", {}).get("available"):
        return None
    try:
        out = rank_defcon_season(load_defcon_gw(), top_n=10)
    except Exception:
        out = rank_defcon_leaders(leaders, window=5, top_n=10)
    rows = out["players"]
    if not rows:
        return None
    per = "starts" if out["meta"].get("hit_rate_denominator") == "starts" else "games"
    # 24.8: luki tallennettua `basis_label`ia, jossa oli kadenssilupaus
    # ("updates as the new season plays"). Artefakti on committoitu, joten
    # lahteen korjaus ei nakyisi ennen seuraavaa ajoa - ja kadenssilupaus oli
    # livena juuri regeneroidulla sivulla. Pudotetaan lupausosa taalla.
    basis = (out["meta"].get("basis_label") or "").split(" · ")[0]
    if basis.startswith("Based on "):
        basis = "Numbers are from the " + basis[len("Based on "):] + " season"
    url = f"{BASE}/fpl/defcon"
    title = "Best DefCon Players: FPL Defensive Contribution Leaders | GoalIQ"
    desc = (
        f"The most reliable FPL defensive contribution (DefCon) point scorers: "
        f"{rows[0]['web_name']} hits the threshold in "
        f"{rows[0]['hit_rate_pct']:.0f}% of his {per}. Defenders need 10 CBIT, "
        f"midfielders and forwards 12 CBIRT, for 2 points."
    )
    top3 = "".join(
        '<div class="stat">'
        f'<b>{escape(r["web_name"])}</b>'
        f'<span>#{i + 1} · {escape(r["team_short"])} · '
        f'{r["hit_rate_pct"]:.0f}% of {per} · {r["dc_per_game"]:.1f} DC/game</span></div>'
        for i, r in enumerate(rows[:3])
    )
    rest = ", ".join(escape(r["web_name"]) for r in rows[3:10])
    hero = (
        "<h1>Best DefCon players in FPL</h1>"
        '<p class="lede">Defensive contribution (DefCon) is worth 2 FPL points '
        "a match: defenders need 10 combined clearances, blocks, interceptions "
        "and tackles (CBIT); midfielders and forwards need 12 including ball "
        "recoveries (CBIRT). These players hit the threshold most often.</p>"
    )
    pool = out["meta"].get("pool_min_starts")
    basis_note = (
        f"Hit rate is the share of a player's {per} that reached the "
        "threshold, the same basis the official FPL figures use."
        + (f" Ranking needs at least {pool} starts." if per == "starts" and pool
           else "")
    )
    body = (
        f'<p class="note"><strong>{escape(basis)}</strong></p>'
        f'<div class="stat-row">{top3}</div>'
        f'<p class="note">{escape(basis_note)}</p>'
        + (
            f'<p class="note">Also in the top 10: {rest}. Hit rates, DC per '
            f"game and position filters are on GoalIQ Premium.</p>"
            if rest
            else ""
        )
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


# ---------------------------------------------------------------------------
# STATS ZONE (8.8) — ilmainen suodatettava raakataulukko
#
# Kysyntasignaali: FFH:n Opta-osio katosi maksavalta kayttajalta ja han kysyi
# julkisesti mista muualta saa "filter tables". Iso osa noista luvuista on
# FPL:n omassa APIssa, joka on Opta-lahtoinen -> jaettavissa ilmaiseksi.
#
# RAJA (Villen paatos 8.8): raakaluvut ilmaiseksi, johdettu DefCon-tracker
# (hit rate, kynnysosumat, projisoidut pisteet) pysyy premiumina. Tama sivu
# nayttaa dc-kertyman lukuna, EI trackeria.
# ---------------------------------------------------------------------------
STATS_GROUPS = [
    # pts on mukana Key-ryhmassa tarkoituksella: taulukko on oletuksena
    # jarjestetty pisteilla, ja lajitteluperusteen pitaa olla nakyvissa.
    # Ilman sita "#"-sarakkeen jarjestys naytti selittamattomalta.
    ("key", "Key", ["pts", "g", "a", "xg", "xa", "xgi"]),
    # HUOM: xG (FPL/Opta) EI ole tassa ryhmassa vaikka se sinne kuuluisi
    # aiheen puolesta. Syy: npxG tulee laukausdatan omasta mallista, ja
    # vierekkain ne nayttavat rikkinaisilta — Haaland xG 25.50 (Opta) ja
    # npxG 25.75 (laukausmalli) = rangaistuspotkuton luku on suurempi kuin
    # kokonaisluku, mika on mahdotonta jos oletat yhden mallin. FPL:n xG
    # asuu Key-ryhmassa, laukausmallin luvut taalla. Ei sekoiteta rivilla.
    ("threat", "Goal threat", ["sh", "sot", "box", "head", "hvc", "npxg",
                               "g"]),
    ("create", "Creativity", ["kp", "a", "xa", "xgi", "xgchain", "xgbuildup",
                              "creativity"]),
    ("defend", "Defending", ["tkl", "cbi", "rec", "dc", "cs", "gc", "xgc",
                             "saves"]),
    ("setp", "Set pieces", ["pen", "cor", "fk", "spxg"]),
    ("fpl", "FPL", ["pts", "ppg", "bps", "bonus", "ict", "yc", "rc"]),
]
STATS_LABELS = {
    "g": "G", "a": "A", "xg": "xG", "xa": "xA", "xgi": "xGI",
    "threat": "Threat", "creativity": "Creativity",
    "tkl": "Tackles", "cbi": "CBI", "rec": "Recov", "dc": "DefCon",
    "cs": "CS", "gc": "GC", "xgc": "xGC", "saves": "Saves",
    "pen": "Pens", "cor": "Corners", "fk": "FK",
    "pts": "Pts", "ppg": "PPG", "bps": "BPS", "bonus": "Bonus",
    "ict": "ICT", "yc": "YC", "rc": "RC",
    # Vaihe 2, Understat. "hvc" ei ole Optan big chance vaan oma xG-kynnys,
    # ja otsikko kertoo kynnyksen itse — vaara termi vuoti aiemmin neljalle
    # pinnalle, joten talla kertaa nimi on laskusaanto.
    "sh": "Shots", "sot": "On target", "box": "In box", "head": "Headers",
    "hvc": "xG 0.3+", "npxg": "npxG", "spxg": "Set-piece xG",
    "kp": "Key passes", "xgchain": "xGChain", "xgbuildup": "xGBuildup",
}
# Sarakekohtainen lahdemerkinta (title-tooltip). Ilman tata kayttaja ei nae
# rivilta kumpi luku on FPL:n virallinen ja kumpi laukausdatan oma malli.
STATS_SOURCE = {
    k: ("Shot-level data, own expected-goals model (not Opta)"
        if k in {"sh", "sot", "box", "head", "hvc", "npxg", "spxg", "kp",
                 "xgchain", "xgbuildup"}
        else "Official FPL API (Opta-sourced)")
    for k in STATS_LABELS
}
# Sarakkeet joita per 90 / per start skaalaa. ppg on jo suhdeluku ja
# erikoistilannejarjestykset ovat sijalukuja -> ei skaalata kumpaakaan.
STATS_RATEABLE = {
    "g", "a", "xg", "xa", "xgi", "threat", "creativity", "tkl", "cbi", "rec",
    "dc", "cs", "gc", "xgc", "saves", "pts", "bps", "bonus", "ict", "yc", "rc",
    "sh", "sot", "box", "head", "hvc", "npxg", "spxg", "kp", "xgchain",
    "xgbuildup",
}
STATS_INT = {"g", "a", "tkl", "cbi", "rec", "dc", "cs", "gc", "saves", "pts",
             "bps", "bonus", "yc", "rc", "sh", "sot", "box", "head", "hvc",
             "kp"}

STATS_JS = """
<script>
(function(){
 var D=window.__ST__||{c:[],r:[]},C={},i;
 for(i=0;i<D.c.length;i++){C[D.c[i]]=i;}
 var GROUPS=__GROUPS__,LAB=__LAB__,RATE=__RATE__,INT=__INT__,SRC=__SRC__,
     ORDCOLS=['pen','cor','fk'];
 var grp='key',mode='total',pos='',team='',minm=0,maxp=99,q='',
     sortKey='pts',desc=true,all=false;
 // --- Gameweek-ikkuna (Villen pyynto 9.8) --------------------------------
 // "GW1-6" cannot be derived from season totals after the fact, so the
 // per-gameweek rows come from a SEPARATE file and only WHEN the user
 // reaches for the filter: it is 551 KB (122 KB gzip), and the readers who
 // never use it should not pay for it.
 var GW=null,gwFrom=0,gwTo=0,gwLoading=false,gwCache={},GWI=null;
 // Only columns from the official FPL API can be windowed. Shot-level
 // numbers come from Understat with no per-gameweek breakdown, so
 // windowing them would be a lie: the page blocks it rather than show
 // zeros.
 var WINCOLS=['pts','g','a','tkl','cbi','rec','dc','cs','gc','saves','bps',
              'bonus','yc','rc','starts','mins','xg','xa','xgi','xgc','ict',
              'ppg'];
 var WINGROUPS=['key','defend','fpl'];
 function gwOn(){return !!(GW&&gwFrom);}
 function winRow(row){
  if(!gwOn())return null;
  var id=row[C.id],key=id+':'+gwFrom+':'+gwTo;
  if(gwCache[key]!==undefined)return gwCache[key];
  var rs=GW.players[id];
  if(!rs){gwCache[key]=null;return null;}
  var acc={n:0},i,m;
  for(m=1;m<GW.meta.cols.length;m++)acc[GW.meta.cols[m]]=0;
  for(i=0;i<rs.length;i++){
   var g=rs[i][0];
   if(g<gwFrom||g>gwTo)continue;
   acc.n++;
   for(m=1;m<GW.meta.cols.length;m++)acc[GW.meta.cols[m]]+=rs[i][m];
  }
  gwCache[key]=acc.n?acc:null;
  return gwCache[key];
 }
 var tb=document.getElementById('stb'),cnt=document.getElementById('stc'),
     head=document.getElementById('sth'),more=document.getElementById('stmore');
 function cols(){return GROUPS[grp];}
 function raw(row,k){
  var w=winRow(row);
  if(w&&WINCOLS.indexOf(k)>=0){
   if(k==='ppg')return w.n?w.pts/w.n:0;
   return w[k];
  }
  return row[C[k]];
 }
 function val(row,k){
  var v=raw(row,k);
  if(typeof v!=='number')return v;
  if(mode==='total'||RATE.indexOf(k)<0)return v;
  var d=mode==='p90'?raw(row,'mins')/90:raw(row,'starts');
  return d>0?v/d:0;
 }
 function fmt(row,k){
  var v=val(row,k);
  // null = the player was not matched to shot data. An empty dash is the
  // truth; a zero would be a claim that he never had a shot.
  if(v===null||v===undefined)return '\\u2013';
  if(k==='pen'||k==='cor'||k==='fk')return v?String(v):'\\u2013';
  if(typeof v!=='number')return v;
  if(mode==='total'&&INT.indexOf(k)>=0)return String(v);
  return v.toFixed(2);
 }
 function rows(){
  var out=[],j;
  for(j=0;j<D.r.length;j++){
   var r=D.r[j];
   if(pos&&r[C.pos]!==pos)continue;
   if(team&&r[C.team]!==team)continue;
   if(gwOn()&&!winRow(r))continue;   // no minutes in the window
   if(raw(r,'mins')<minm)continue;
   if(r[C.price]>maxp)continue;
   if(q&&(r[C.name]+' '+r[C.team]).toLowerCase().indexOf(q)<0)continue;
   if(mode==='pstart'&&raw(r,'starts')<1)continue;
   out.push(r);
  }
  // Set-piece orders are ordinal ranks: 1 = first taker. Largest-first
  // would be backwards (5th in the penalty queue at the top), and
  // 0 = "not listed" must always sink to the end in both directions.
  var ORD=ORDCOLS.indexOf(sortKey)>=0;
  out.sort(function(a,b){
   var x=val(a,sortKey),y=val(b,sortKey);
   // An unknown value competes in neither sort direction.
   var xn=(x===null||x===undefined),yn=(y===null||y===undefined);
   if(xn||yn)return xn&&yn?0:(xn?1:-1);
   if(ORD){
    x=x?x:9999;y=y?y:9999;
    return desc?x-y:y-x;
   }
   if(typeof x==='string')return desc?(y>x?1:-1):(x>y?1:-1);
   return desc?y-x:x-y;
  });
  return out;
 }
 function draw(){
  // Mobile (a) 9 Aug: Pos/Price/Mins/Starts are filter context (they are
  // set with the buttons above), so a narrow screen shows Player + Team +
  // the chosen group's stats. The table was 657px = 1.7x a phone's width.
  // The columns are still in the DOM -> sorting and CSV are unchanged.
  var ks=cols(),h='<tr><th class="n">#</th><th data-k="name">Player</th>'
   +'<th data-k="team">Team</th><th class="m-hide" data-k="pos">Pos</th>'
   +'<th class="n m-hide" data-k="price">Price</th>'
   +'<th class="n m-hide" data-k="mins">Mins</th>',j;
  if(mode==='pstart')h+='<th class="n m-hide" data-k="starts">Starts</th>';
  for(j=0;j<ks.length;j++){
   h+='<th class="n" data-k="'+ks[j]+'" title="'+(SRC[ks[j]]||'')+'">'
     +LAB[ks[j]]
     +(sortKey===ks[j]?(desc?' \\u25be':' \\u25b4'):'')+'</th>';
  }
  head.innerHTML=h+'</tr>';
  var rs=rows(),n=all?rs.length:Math.min(100,rs.length),s='';
  for(j=0;j<n;j++){
   var r=rs[j];
   s+='<tr><td class="n">'+(j+1)+'</td><td>'+r[C.name]+'</td>'
    +'<td>'+r[C.team]+'</td><td class="m-hide">'+r[C.pos]+'</td>'
    +'<td class="n m-hide">'+r[C.price].toFixed(1)+'</td>'
    // Mins and Starts are windowable: without raw() they showed season
    // numbers under a GW heading (Haaland 2953 min for "GW1-6"). Found by
    // looking at the live page, not from the code.
    +'<td class="n m-hide">'+raw(r,'mins')+'</td>';
   if(mode==='pstart')s+='<td class="n m-hide">'+raw(r,'starts')+'</td>';
   for(var m=0;m<ks.length;m++){
    s+='<td class="n'+(ks[m]===sortKey?' hi':'')+'">'+fmt(r,ks[m])+'</td>';
   }
   s+='</tr>';
  }
  tb.innerHTML=s;
  var span=gwOn()?('GW'+gwFrom+(gwTo>gwFrom?'-'+gwTo:'')):'';
  var lbl=mode==='total'?(span?span+' totals':'season totals')
    :(mode==='p90'?'per 90 minutes':'per start');
  cnt.textContent=rs.length+' players, '+lbl
   +(minm?', '+minm+'+ minutes':'')+'. Showing '+n
   +'. Click a column to sort.';
  more.style.display=(!all&&rs.length>100)?'':'none';
  window.__STROWS__=rs;
 }
 function chips(id,items,cur,cb){
  var e=document.getElementById(id),s='',j;
  for(j=0;j<items.length;j++){
   s+='<button type="button" class="chip'+(items[j][0]===cur?' on':'')
    +'" data-v="'+items[j][0]+'">'+items[j][1]+'</button>';
  }
  e.innerHTML=s;
  e.onclick=function(ev){
   var b=ev.target.closest('button');if(!b)return;cb(b.getAttribute('data-v'));
  };
 }
 function paint(){
  chips('stg',GROUPKEYS,grp,function(v){grp=v;
   if(cols().indexOf(sortKey)<0){sortKey=cols()[0];desc=true;}paint();});
  chips('stm',[['total','Total'],['p90','Per 90'],['pstart','Per start']],
   mode,function(v){
    // Sample-size guard: 7 minutes played yields 12.86 tackles/90 and
    // takes over the top of the list. A rate without sample size is
    // misleading, so switching to rate mode raises the minimum to 450
    // minutes. The user can drop it back to zero in one click - it is not
    // blocked, it just stops being the default.
    if(v!=='total'&&mode==='total'&&minm===0){minm=450;}
    mode=v;paint();});
  chips('stp',[['','All'],['GKP','GKP'],['DEF','DEF'],['MID','MID'],
   ['FWD','FWD']],pos,function(v){pos=v;paint();});
  chips('stmin',[[0,'0'],[450,'450'],[900,'900'],[1500,'1500']],minm,
   function(v){minm=+v;paint();});
  draw();
 }
 var GROUPKEYS=[];
 for(var gk in GROUPS){if(GROUPS.hasOwnProperty(gk)){
  GROUPKEYS.push([gk,GROUPNAMES[gk]]);}}
 head.onclick=function(ev){
  var th=ev.target.closest('th');if(!th)return;
  var k=th.getAttribute('data-k');if(!k)return;
  if(k===sortKey){desc=!desc;}else{sortKey=k;desc=true;}
  draw();
 };
 more.onclick=function(){all=true;draw();};
 var ts={},j2;
 for(j2=0;j2<D.r.length;j2++){ts[D.r[j2][C.team]]=1;}
 var tsel=document.getElementById('stteam'),o='<option value="">All teams</option>',
     tk=Object.keys(ts).sort();
 for(j2=0;j2<tk.length;j2++){o+='<option value="'+tk[j2]+'">'+tk[j2]+'</option>';}
 tsel.innerHTML=o;
 tsel.onchange=function(){team=this.value;draw();};
 var psel=document.getElementById('stprice'),po='<option value="99">Any price</option>';
 for(var p=40;p<=155;p+=5){po+='<option value="'+(p/10)+'">Max '+(p/10).toFixed(1)+'</option>';}
 psel.innerHTML=po;
 psel.onchange=function(){maxp=+this.value;draw();};
 var qi=document.getElementById('stq');
 qi.oninput=function(){q=this.value.toLowerCase();all=false;draw();};

 // --- Gameweek-ikkuna ----------------------------------------------------
 var gwf=document.getElementById('stgwf'),gwt=document.getElementById('stgwt');
 function syncGroups(){
  // Shot-level groups cannot be windowed (Understat, no per-gameweek
  // breakdown). They lock visibly instead of showing zeros or season totals
  // under a gameweek heading, because either one would lie.
  var on=gwOn(),e=document.getElementById('stg');
  if(!e)return;
  var bs=e.querySelectorAll('.chip'),i;
  for(i=0;i<bs.length;i++){
   var k=bs[i].getAttribute('data-v'),lock=on&&WINGROUPS.indexOf(k)<0;
   bs[i].disabled=lock;
   bs[i].style.opacity=lock?'0.4':'';
   bs[i].title=lock?'No per-gameweek data for these columns':'';
  }
 }
 function applyGw(){
  var f=gwf&&gwf.value?+gwf.value:0,t=gwt&&gwt.value?+gwt.value:0;
  if(f&&t&&t<f){t=f;if(gwt)gwt.value=String(t);}
  gwFrom=f;gwTo=t;gwCache={};
  if(gwOn()&&WINGROUPS.indexOf(grp)<0){grp='key';sync();}
  syncGroups();draw();
 }
 function loadGw(cb){
  if(GW||gwLoading)return cb&&cb();
  gwLoading=true;
  if(cnt)cnt.textContent='Loading gameweek data…';
  fetch('/fpl/player-gw.json').then(function(r){
   if(!r.ok)throw new Error(r.status);return r.json();
  }).then(function(j){
   GW=j;gwLoading=false;cb&&cb();
  })['catch'](function(){
   gwLoading=false;
   // A failed load returns the picker to season mode AND says so. Falling
   // back silently would look exactly like a window that works.
   if(gwf)gwf.value='';
   gwFrom=0;gwTo=0;syncGroups();draw();
   if(cnt)cnt.textContent='Could not load gameweek data. Showing season totals.';
  });
 }
 if(gwf){
  gwf.onchange=function(){
   if(!this.value){applyGw();return;}
   loadGw(applyGw);
  };
 }
 if(gwt)gwt.onchange=function(){if(gwf&&gwf.value)loadGw(applyGw);};
 document.getElementById('stcsv').onclick=function(){
  var ks=cols(),hdr=['Player','Team','Pos','Price','Mins'];
  if(mode==='pstart')hdr.push('Starts');
  for(var j=0;j<ks.length;j++){hdr.push(LAB[ks[j]]);}
  var lines=[hdr.join(',')],rs=window.__STROWS__||[];
  for(var m=0;m<rs.length;m++){
   var r=rs[m],line=['"'+String(r[C.name]).replace(/"/g,'""')+'"',r[C.team],
    r[C.pos],r[C.price].toFixed(1),raw(r,'mins')];
   if(mode==='pstart')line.push(raw(r,'starts'));
   for(var n2=0;n2<ks.length;n2++){
    var v=val(r,ks[n2]);
    line.push(typeof v==='number'?v.toFixed(2):v);
   }
   lines.push(line.join(','));
  }
  var b=new Blob([lines.join('\\n')],{type:'text/csv'}),
      a=document.createElement('a');
  a.href=URL.createObjectURL(b);
  a.download='goaliq-fpl-stats-'+grp+'-'+mode+'.csv';
  document.body.appendChild(a);a.click();document.body.removeChild(a);
  setTimeout(function(){URL.revokeObjectURL(a.href);},1000);
 };
 paint();
})();
</script>
"""


def _stats_js() -> str:
    groups = {k: c for k, _, c in STATS_GROUPS}
    names = {k: n for k, n, _ in STATS_GROUPS}
    js = STATS_JS.replace("__GROUPS__", json.dumps(groups))
    js = js.replace("__LAB__", json.dumps(STATS_LABELS))
    js = js.replace("__RATE__", json.dumps(sorted(STATS_RATEABLE)))
    js = js.replace("__INT__", json.dumps(sorted(STATS_INT)))
    js = js.replace("__SRC__", json.dumps(STATS_SOURCE))
    # GROUPNAMES on erillinen, jotta ryhmien jarjestys sailyy chipeissa
    return js.replace(
        "(function(){",
        "(function(){\n var GROUPNAMES=" + json.dumps(names) + ";", 1)



def _stats_gw_controls() -> str:
    """Gameweek-ikkunan valikot.

    Renderoidaan VAIN jos fpl/player-gw.json on olemassa. Jos data puuttuu,
    koko kontrolli jaa pois eika sivulle jaa nappia joka ei tee mitaan --
    rikkinainen suodatin on huonompi kuin puuttuva.
    """
    meta = _player_gw_meta()
    if not meta:
        return ""
    n = int(meta.get("max_gw") or 0)
    if n < 2:
        return ""
    opts_from = '<option value="">All gameweeks</option>' + "".join(
        f'<option value="{i}">From GW{i}</option>' for i in range(1, n + 1))
    opts_to = "".join(
        f'<option value="{i}"{" selected" if i == n else ""}>To GW{i}</option>'
        for i in range(1, n + 1))
    return (
        '<span class="lbl">Gameweeks</span>'
        f'<select id="stgwf" aria-label="From gameweek">{opts_from}</select>'
        f'<select id="stgwt" aria-label="To gameweek">{opts_to}</select>'
    )


def _player_gw_meta() -> dict | None:
    p = _FP_ROOT / "fpl" / "player-gw.json"
    if not p.exists():
        return None
    try:
        # Vain meta tarvitaan; tiedosto on 551 KB, joten se luetaan kerran.
        return json.loads(p.read_text(encoding="utf-8")).get("meta") or None
    except Exception:
        return None


# PAATOS 24.8: EI NIMIESTOLISTAA KORTTIIN.
#
# Julkaisutarkistaja nosti asian: kortti on nyt automaattisesti generoitua
# brandattya materiaalia, ja kirjattu markkinointisaanto sanoo ettei tiettyja
# nimia kayteta (heikoin puolustettava nimi). Han on tanaan sijalla 24 eika
# siis kortilla, mutta mikaan ei esta hanta nousemasta.
#
# Estolistaa EI lisata, ja syy on rakenteellinen: kortin koko peruste on
# ETTA SE ON SAMA KUIN SIVU. Rivin vaientaminen kortilta palauttaisi tasan
# sen "kortti nayttaa muuta kuin taulukko" -luokan jonka poistamiseen tama
# rakennemuutos tehtiin, ja `test_share_card_server_rows` kaatuisi oikein.
#
# Saanto koskee VALITTUJA markkinointikulmia - sita kenesta me paatamme
# puhua - ei faktuaalista jarjestysta jonka lukija nakee samalta sivulta.
# Jos nimi nousee korttiin, se on datan tulos eika meidan vaitteemme.
#
# 🔴 Tama on kirjaus, ei ohitus: jos joku haluaa eston, se on tehtava
# TAULUKKOON eika korttiin, jolloin sivu ja kuva pysyvat samana.
def kortin_kaudet(rivit: list[dict], n: int = 10) -> list[str]:
    """Kausiperustat KORTIN omilta riveilta, ei koko aineistosta.

    🔴 TAMA ON OMA FUNKTIONSA JOTTA SE VOIDAAN TESTATA. Sisakkaisena
    lausekkeena vika oli nakymaton: koko aineistosta ja karkikymmenikosta
    johdettu joukko ovat 25.8 IDENTTISET, joten mikaan tuotantodataan nojaava
    testi ei erota niita. Kauden edetessa ne eroavat, ja silloin kortti
    vaittaisi kahta kautta kymmenesta rivista jotka ovat yhta.
    """
    return sorted({str(r.get("basis") or "") for r in rivit[:n]} - {""})


def ottelumaara_lause(maarat: set[int]) -> str:
    """Ottelumaaralause. `each` VAIN kun kaikilla on sama maara.

    🔴 `max()` ei todista sanaa "each". Kesken kautta ajettu artefakti antaa
    eri lukuja joukkueittain, ja `max` vaittaisi silti "each".
    """
    puhtaat = {m for m in maarat if m}
    if not puhtaat:
        return ""
    if len(puhtaat) == 1:
        return f"{next(iter(puhtaat))} matches each. "
    return f"at least {min(puhtaat)} matches per team. "


def _card_spec_attr(*, title: str, subtitle: str, rows: list[dict],
                    file_name: str, name_label: str = "PLAYER",
                    mid_label: str = "", value_label: str = "",
                    foot: str = "",
                    foot2: str = "model projections, not betting advice") -> str:
    """Palvelimen kirjoittama korttispec HTML-attribuutiksi.

    🔴 KORTTI EI LUE ELAVAA DOMIA. Rivit tulevat SAMASTA listasta josta
    taulukkokin renderoidaan, joten kortti on aina se nakyma jonka linkista
    tuleva lukija nakee - ei se johon jakaja oli sattunut suodattaa.

    Taustaa: jokainen `table.lb` saa GEN:TABLE-TOOLSilta klikkilajittelun ja
    suodatinpalkin. DOM-lukija tuotti siksi kuvia jotka sanoivat vastakkaista
    kuin data ("TOP 10 BY EXPECTED POINTS" = kymmenen kalleinta kahdella
    klikkauksella), ja suodattimet piilottavat rivit `display:none`-tyylilla
    jota `querySelectorAll` ei nae. Julkaisutarkistaja blokkasi kortit nelja
    kierrosta, ja kaksi lukijan korjausyritysta tuotti kumpikin uusia
    valheita. Tama poistaa koko luokan.

    `rows`: [{rank,name,team?,tag?,mid?,value}] valmiiksi muotoiltuina
    merkkijonoina - muotoilu kuuluu sinne missa luvutkin ovat.
    """
    spec = {"title": title, "subtitle": subtitle, "nameLabel": name_label,
            "valueLabel": value_label, "rows": rows[:10],
            "fileName": file_name, "footNote2": foot2}
    if mid_label:
        spec["midLabel"] = mid_label
    if foot:
        spec["footNote"] = foot
    return " data-card-spec='" + escape(
        json.dumps(spec, ensure_ascii=False), quote=True).replace("'", "&#39;") + "'"


def _share_button(margin: str = "10px 0 4px") -> str:
    return ('<button type="button" class="chip" id="sharecard" '
            f'style="margin:{margin};">Share as image</button>')







def render_stats(stats: dict, now: datetime) -> str | None:
    """Ilmainen Stats zone: koko pelaajajoukko, suodattimet, per 90 / per start.

    Palvelin renderoi 100 rivia default-ryhmalla (SEO + ei-JS), loput ja
    ryhmavaihdot klientissa. Sama 100-rivin DOM-katto kuin xg-leaders: 26.7
    todettiin etta 373 rivia x taysrender teki sivusta laggaavan."""
    meta = stats.get("meta") or {}
    rows = stats.get("players") or []
    if not meta.get("available") or not rows:
        return None
    cols = meta.get("cols") or []
    idx = {c: i for i, c in enumerate(cols)}
    basis = meta.get("basis_label") or ""
    url = f"{BASE}/fpl/stats"
    title = "Free FPL Player Stats: Shots, xG and Filterable Raw Numbers | GoalIQ"
    desc = (
        f"Every Premier League player's numbers in one filterable table: "
        f"shots, shots in the box, key passes, xG, xA, xGI, tackles, "
        f"recoveries and set-piece order. {len(rows)} players, per 90 or per "
        f"start, CSV export. Free, no sign-in."
    )
    keys = STATS_GROUPS[0][2]
    trows = "".join(
        "<tr>"
        f'<td class="n">{i + 1}</td>'
        f'<td>{escape(str(r[idx["name"]]))}</td>'
        f'<td>{escape(str(r[idx["team"]]))}</td>'
        f'<td class="m-hide">{escape(str(r[idx["pos"]]))}</td>'
        f'<td class="n m-hide">{r[idx["price"]]:.1f}</td>'
        f'<td class="n m-hide">{r[idx["mins"]]}</td>'
        + "".join(f'<td class="n">{r[idx[k]]}</td>' for k in keys)
        + "</tr>"
        for i, r in enumerate(rows[:100])
    )
    thead = (
        '<tr><th class="n">#</th><th data-k="name">Player</th>'
        '<th data-k="team">Team</th><th class="m-hide" data-k="pos">Pos</th>'
        '<th class="n m-hide" data-k="price">Price</th>'
        '<th class="n m-hide" data-k="mins">Mins</th>'
        + "".join(
            f'<th class="n" data-k="{k}" title="{STATS_SOURCE[k]}">'
            f'{STATS_LABELS[k]}</th>' for k in keys)
        + "</tr>"
    )
    controls = (
        '<div class="lbctl">'
        '<span class="lbl">Stats</span><span id="stg" class="chips"></span>'
        '<span class="lbl">Show</span><span id="stm" class="chips"></span>'
        "</div>"
        '<div class="lbctl">'
        '<span class="lbl">Position</span><span id="stp" class="chips"></span>'
        '<span class="lbl">Min mins</span><span id="stmin" class="chips"></span>'
        + _stats_gw_controls() +
        '<select id="stteam" aria-label="Filter by team"></select>'
        '<select id="stprice" aria-label="Maximum price"></select>'
        '<input id="stq" type="search" placeholder="Search player" '
        'aria-label="Search player" style="border:1px solid '
        'var(--line-strong);background:var(--paper);color:var(--cream);'
        'padding:7px 10px;font:inherit;font-size:13px;">'
        '<button type="button" class="chip" id="stcsv">Download CSV</button>'
        # Jakokortti (Villen pyynto 9.8): sama kortti kuin SPA:ssa ja
        # viikkopostauksessa. Vapaata dataa, joten ei premium-porttia.
        # 24.8: JAKONAPPI POIS KUNNES TAMA SIVU ON SIIRRETTY
        # PALVELINRIVEILLE. Taman sivun kortti lukee yha elavaa DOMia
        # (`_STATS_SPEC_FN`), ja se lukija on todettu nelja kertaa
        # valehtelevaksi: taulukko on klikkilajiteltava ja suodatettava,
        # joten otsikko ja rivit voivat eriytya kahdella klikkauksella.
        # Uusi portti EI mittaa tata sivua, joten "portti on nyt olemassa"
        # ei ole peruste jattaa nappia pystyyn. Ks. jonorivi
        # SHARE-CARD-SERVER-ROWS.
        ''
        "</div>"
        f'<p class="note" id="stc">{len(rows)} players, season totals. '
        "Showing 100. Click a column to sort, or press Show all players.</p>"
    )
    table = (
        '<div class="lb-wrap"><table class="lb">'
        f'<thead id="sth">{thead}</thead>'
        f'<tbody id="stb">{trows}</tbody></table></div>'
        '<button type="button" class="chip" id="stmore" '
        'style="margin:4px 0 8px;">Show all players</button>'
    )
    payload = ('<script id="stdata">window.__ST__='
               + json.dumps({"c": cols, "r": rows}, ensure_ascii=False)
               + ";</script>")
    hero = (
        "<h1>Free FPL player stats</h1>"
        '<p class="lede">The raw numbers, in one filterable table. Shots, '
        "shots in the box, key passes, expected goals and assists, tackles, "
        "recoveries, clean sheets, set-piece order and FPL scoring history "
        "for every player. Filter by position, team, price and minutes, "
        "switch to per 90 or per start, sort any column, export CSV. Free, "
        "no sign-in.</p>"
    )
    body = (
        f'<p class="note"><strong>{escape(basis)}</strong></p>'
        f"<h2>Every player with minutes ({len(rows)})</h2>"
        '<p class="note">Two sources, both stated plainly. Goals, assists, '
        "expected goals, expected assists, expected goals conceded, tackles, "
        "clearances, recoveries, clean sheets, saves and set-piece order come "
        "from the official FPL API, which is Opta-sourced, so there is no "
        "reason to put them behind a subscription and we do not. Shots, shots "
        "on target, shots in the box, headers, non-penalty xG, set-piece xG, "
        "key passes, xGChain and xGBuildup come from shot-level data with its "
        "own expected-goals model, so those numbers will not match Opta's and "
        "we do not call them Opta. In box means the shot was taken inside the "
        "penalty area. The xG 0.3+ column counts chances worth at least 0.3 "
        "expected goals, which is our own threshold and not anyone else's "
        # 15.8: portti blokkasi erikoistilanne-artikkelin koska teksti sanoi
        # "corner" ja sarake tarkoittaa laajempaa joukkoa. Sarakkeen sisalto
        # oli sivulla maarittelematta, joten lukija ei voinut ratkaista eroa
        # miltaan pinnalta. Maaritelma kuuluu sinne missa luku on.
        "definition of a big chance. Set-piece xG counts shots from corners, "
        "free kicks and other dead-ball situations, not corners alone, and the "
        "column does not split them. Our DefCon tracker (hit rate, thresholds, "
        "projected points) is a model output rather than a raw stat, so it "
        "lives in the app and the DefCon column here is the raw count. A dash "
        "means we have no data for that player, not zero.</p>"
        f"{controls}{table}{payload}{_stats_js()}"
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    # GEO/SEO: Dataset kertoo koneluettavasti MITA sarakkeita sivulla on ja
    # etta ne ovat ilmaisia. WebPage yksin ei kerro kumpaakaan, ja juuri nama
    # kaksi ovat ne joita hakukone tai kielimalli tarvitsee vastatakseen
    # kysymykseen "mista saa ilmaiseksi FPL:n laukausdataa".
    measured = [STATS_LABELS[k] for _, _, cols in STATS_GROUPS for k in cols]
    measured = list(dict.fromkeys(measured))
    jsonld = [
        {
            "@context": "https://schema.org", "@type": "WebPage",
            "name": title, "url": url, "description": desc,
            "isPartOf": {"@id": f"{BASE}/#organization"},
            "dateModified": now.strftime("%Y-%m-%d"),
        },
        {
            "@context": "https://schema.org", "@type": "Dataset",
            "name": "GoalIQ free FPL player stats",
            "url": url,
            "description": (
                "Season statistics for every Premier League player with "
                "minutes, covering shots, shots on target, shots in the box, "
                "headed attempts, non-penalty expected goals, set-piece "
                "expected goals, key passes, xGChain, xGBuildup, goals, "
                "assists, expected goals, expected assists, expected goal "
                "involvement, expected goals conceded, tackles, clearances "
                "blocks and interceptions, recoveries, defensive "
                "contribution, clean sheets, saves, penalty, corner and "
                "free-kick order, points, bonus, BPS and ICT."
            ),
            "isAccessibleForFree": True,
            "creator": {"@id": f"{BASE}/#organization"},
            "temporalCoverage": (meta.get("basis_season") or "").replace(
                "/", "-"),
            "variableMeasured": measured,
            "distribution": [{
                "@type": "DataDownload",
                "encodingFormat": "text/csv",
                "name": "CSV export of the current view",
            }],
        },
        {
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "GoalIQ",
                 "item": BASE},
                {"@type": "ListItem", "position": 2, "name": "Free FPL tools",
                 "item": f"{BASE}/fpl"},
                {"@type": "ListItem", "position": 3, "name": "Player stats",
                 "item": url},
            ],
        },
    ]
    return _page(title, desc, url, hero, body, jsonld)



def _join_names(names: list[str]) -> str:
    """["A", "B", "C"] -> "A, B and C" (luettelo copyyn, ei koodilistana)."""
    safe = [escape(n) for n in names]
    if len(safe) == 1:
        return safe[0]
    return ", ".join(safe[:-1]) + " and " + safe[-1]

def render_defence(defence: dict, now: datetime) -> str | None:
    """Joukkuetason puolustusprofiili: MILLAISIA paikkoja puolustus paastaa.

    Taydentaa CS-% ja FDR -sivua, joka kertoo KUINKA PALJON muttei mista.
    FPL-hyoty: paalaukausmaara kertoo erikoistilanneriskin, keskiboksin
    paikat avoimen pelin heikkoudesta."""
    meta = defence.get("meta") or {}
    rows = defence.get("teams") or []
    if not meta.get("available") or not rows:
        return None
    season = meta.get("season", "")
    url = f"{BASE}/fpl/defence"
    title = "Premier League Defence Profiles: What Each Defence Concedes | GoalIQ"
    desc = (
        f"Not how many chances each Premier League defence concedes but what "
        f"kind: shots in the six-yard box, central box, wide box, edge of box "
        f"and long range, plus headers and set-piece xG. {season} data, free."
    )
    best = rows[0]
    most_headers = max(rows, key=lambda r: r["head_pm"])
    most_central = max(rows, key=lambda r: r["central_pm"])
    stat_row = "".join([
        '<div class="stat"><b>' + escape(best["team"]) + "</b>"
        f'<span>Fewest expected goals conceded: {best["xg_pm"]:.2f} per match</span></div>',
        '<div class="stat"><b>' + escape(most_headers["team"]) + "</b>"
        f'<span>Most headers faced: {most_headers["head_pm"]:.2f} per match</span></div>',
        '<div class="stat"><b>' + escape(most_central["team"]) + "</b>"
        f'<span>Most central-box shots faced: {most_central["central_pm"]:.2f} per match</span></div>',
    ])
    trows = "".join(
        "<tr>"
        f'<td class="n">{i + 1}</td>'
        f'<td>{escape(r["team"])}</td>'
        f'<td class="n hi">{r["xg_pm"]:.2f}</td>'
        f'<td class="n">{r["shots_pm"]:.1f}</td>'
        f'<td class="n">{r["six_pm"]:.2f}</td>'
        f'<td class="n m-hide">{r["central_pm"]:.2f}</td>'
        f'<td class="n m-hide">{r["wide_pm"]:.2f}</td>'
        f'<td class="n m-hide">{r["edge_pm"]:.2f}</td>'
        f'<td class="n m-hide">{r["far_pm"]:.2f}</td>'
        f'<td class="n">{r["head_pm"]:.2f}</td>'
        f'<td class="n m-hide">{r["sp_xg_pm"]:.2f}</td>'
        f'<td class="n">{r["box_share"]:.0f}%</td>'
        "</tr>"
        for i, r in enumerate(rows)
    )
    # 🔴 JAKOKORTTI PALVELIMEN RIVEILTA (SHARE-CARD-SERVER-ROWS).
    # Aiempi versio luki elavaa DOMia (`_DEFENCE_SPEC_FN`), ja `table.lb` saa
    # GEN:TABLE-TOOLSilta klikkilajittelun: kaksi klikkausta kaansi listan ja
    # kortti olisi sanonut "FEWEST" kymmenesta ENITEN paastavasta. Rivit
    # tulevat nyt samasta `rows`-listasta josta taulukkokin.
    # 🔴 OTSIKKO ON SUUNTAVAITE. Ensimmainen ehdotus oli "MOST XG CONCEDED",
    # ja taulukko on NOUSEVASSA jarjestyksessa (Arsenal 0.91 = paras puolustus)
    # eli otsikko olisi vaittanyt tasan painvastaista kuin data.
    # 🔴 KAUSI ON KORTILLA, PAIVAMAARA EI. Lahde on KOKO PAATTYNYT KAUSI:
    # `understat_team_defence_2526.json` meta sanoo season 2025/26,
    # matches_read 380, generated_at 8.8 — ja Arsenalin 0,91 on 38 ottelun
    # keskiarvo. Artefakti ei liiku. Sivu mainitsee kauden viidesti; kortti ei
    # kertaakaan, ja "As of 25 Aug" luki tuoreutena joka lukijalle tarkoittaa
    # tata kautta. Kausi ja ottelumaara luetaan metasta, ei kovakoodata.
    _dmeta = (defence.get("meta") or {})
    _dkausi = str(_dmeta.get("season") or "")
    # 🔴 `max()` EI TODISTA "each". Tanaan kaikilla 17 joukkueella on 38
    # ottelua, mutta kesken kauden ajettu artefakti antaisi eri lukuja ja
    # `max` vaittaisi silti "each". Sana kaytetaan vain kun arvot ovat samat.
    _dlause = ottelumaara_lause({r.get("matches") or 0 for r in rows})
    kortti = _card_spec_attr(
        title="FEWEST xG CONCEDED",
        subtitle=("Expected goals conceded per match, "
                  + (f"{_dkausi}, " if _dkausi else "") + "lowest is best"),
        name_label="TEAM",
        mid_label="SHOTS",
        value_label="xGC",
        foot="the full table is free on goaliq.app/fpl/defence",
        # Kausi on alaotsikossa; alaviite kertoo vain otoskoon eika toista
        # sita. Sama varaus kahdesti samassa kuvassa on tunnusmerkki.
        foot2=(_dlause + "Shot-level data, own expected-goals model"),
        rows=[{"rank": i + 1, "name": r["team"], "team": "", "tag": "",
               "mid": ("%.1f" % r["shots_pm"]),
               "value": ("%.2f" % r["xg_pm"])}
              for i, r in enumerate(rows[:10])],
        file_name="goaliq-defence-xgc.png")
    table = (
        f'<div class="lb-wrap"><table class="lb"{kortti}>'
        "<thead><tr>"
        '<th class="n">#</th><th>Team</th>'
        '<th class="n" title="Expected goals conceded per match">xGC</th>'
        '<th class="n" title="Shots faced per match">Shots</th>'
        '<th class="n" title="Six-yard box, central">6yd</th>'
        '<th class="n m-hide" title="Penalty area, central band">Central</th>'
        '<th class="n m-hide" title="Penalty area, wide of the central band">Wide</th>'
        '<th class="n m-hide" title="Between 18 yards and the penalty area">Edge</th>'
        '<th class="n m-hide" title="Long range">Far</th>'
        '<th class="n" title="Headed attempts faced per match">Headers</th>'
        '<th class="n m-hide" title="Set-piece expected goals conceded per match">SP xG</th>'
        '<th class="n" title="Share of shots faced that came from inside the box">In box</th>'
        "</tr></thead>"
        f"<tbody>{trows}</tbody></table></div>"
        # Lede lupaa kaikki vyohykkeet, mutta kapea naytto nayttaa niista
        # viisi. Ilman tata rivia copy lupaisi enemman kuin ruutu antaa
        # (COPY-SYNC-GATE: pinta ja lupaus eivat saa eriytya).
        '<p class="note m-only">Central, wide, edge, long range and set-piece '
        "xG are in the same table on a wider screen.</p>"
        # Jakokortti (Villen pyynto 9.8)
        # 24.8: jakonappi pois, sama syy kuin stats-sivulla - kortti lukee
        # yha elavaa DOMia eika uusi portti mittaa tata sivua.
        ''
    )
    hero = (
        "<h1>What each Premier League defence concedes</h1>"
        '<p class="lede">Clean sheet probability tells you how likely a shutout is. '
        "This tells you what a defence actually gives up: shots from the "
        "six-yard box, the central penalty area, wide in the box, the edge and "
        "long range, plus headers faced and set-piece expected goals. Two "
        "defences can face the same number of shots and be nothing alike.</p>"
    )
    promoted = meta.get("promoted_no_data") or []
    relegated = meta.get("relegated_excluded") or []
    scope = (
        f"<strong>{escape(season)} season, per match.</strong> This covers the "
        f"{len(rows)} clubs that played in the Premier League last season and "
        "are still in it."
    )
    if promoted:
        scope += (
            " " + _join_names(promoted) + " came up from the Championship, so "
            "there is no Premier League shot data for them yet and they are "
            "not in the table."
        )
    if relegated:
        scope += (
            " " + _join_names(relegated) + " are in last season's data but "
            "went down, so they are left out."
        )
    body = (
        f'<p class="note">{scope}</p>'
        '<p class="note">Penalties are counted separately and left out of the '
        "zone columns, because they say nothing about defensive shape.</p>"
        f'<div class="stat-row">{stat_row}</div>'
        f"<h2>These {len(rows)} defences, sorted by expected goals conceded</h2>"
        '<p class="note">Why this matters for FPL: a defence that faces a lot '
        "of headers is a set-piece risk, so its clean sheet is fragile even "
        "against weak opponents. A defence that concedes mostly from long "
        "range is giving up volume without quality, and its goalkeeper is a "
        "save-points candidate. These come from shot-level data with its own "
        "expected-goals model, so the numbers are not Opta's and we do not "
        "call them that.</p>"
        + _share_button()
        + f"{table}"
        + SHARE_CARD_JS.replace("__CARD_ROWS_FN__", "function(){return null;}")
                + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [
        {
            "@context": "https://schema.org", "@type": "WebPage",
            "name": title, "url": url, "description": desc,
            "isPartOf": {"@id": f"{BASE}/#organization"},
            "dateModified": now.strftime("%Y-%m-%d"),
        },
        {
            "@context": "https://schema.org", "@type": "Dataset",
            "name": "GoalIQ Premier League defence profiles",
            "url": url,
            "description": (
                "Per match, for every Premier League team: shots faced split "
                "by pitch zone (six-yard box, central penalty area, wide in "
                "the box, edge of the box, long range), headed attempts "
                "faced, set-piece expected goals conceded, expected goals "
                "conceded and the share of shots faced from inside the box. "
                "Penalties are counted separately and excluded from the zone "
                "columns."
            ),
            "isAccessibleForFree": True,
            "creator": {"@id": f"{BASE}/#organization"},
            "temporalCoverage": season.replace("/", "-"),
            "variableMeasured": [
                "Expected goals conceded per match", "Shots faced per match",
                "Six-yard box shots faced", "Central penalty area shots faced",
                "Wide penalty area shots faced", "Edge of box shots faced",
                "Long range shots faced", "Headed attempts faced",
                "Set-piece expected goals conceded", "Share of shots in box",
            ],
        },
        {
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "GoalIQ",
                 "item": BASE},
                {"@type": "ListItem", "position": 2, "name": "Free FPL tools",
                 "item": f"{BASE}/fpl"},
                {"@type": "ListItem", "position": 3,
                 "name": "Defence profiles", "item": url},
            ],
        },
    ]
    return _page(title, desc, url, hero, body, jsonld)


# ---------------------------------------------------------------------------
# LUOTTAMUSLIPPU (10.8.2026) — lippu tulee ARTEFAKTISTA (build_fpl_xp.py), ei
# talta sivulta. Renderin tyo on vain nayttaa se. Nain SPA, mobiili, etusivu ja
# tama sivu lukevat saman lahteen eivatka voi eriytya.
#
# EI SUUNTAVAITETTA copyyn: kalibrointi kaatui 9.8. (hyokkays R^2 0,000,
# puolustus vaara merkki), joten lippu kertoo mika on muuttunut, ei mita siita
# seuraa. Tama on sitova rajaus kaikilla pinnoilla.
# ---------------------------------------------------------------------------
_TFLAG_LABEL = {"promoted": "promoted", "high_turnover": "turnover"}


def _tflag_html(row: dict) -> str:
    label = _TFLAG_LABEL.get(row.get("team_flag") or "")
    return f'<span class="tflag">{label}</span>' if label else ""


def _tflag_note(xp: dict, shown: list[dict], allrows: list[dict]) -> str:
    """Selite taulukon alle, vain jos jokin joukkue on liputettu.

    KORJAUS 10.8: ensimmainen versio selitti merkin jota sivulla ei nay.
    Liputetut ovat nousijoiden pelaajia, eika yksikaan yllä tallä hetkella
    top 100:aan (paras on #129), joten taulukossa on nolla merkkia. Selite
    kertoo sen nyt itse sen sijaan etta lukija etsisi merkkia turhaan.
    """
    tc = (xp.get("meta") or {}).get("team_confidence") or {}
    teams = tc.get("teams") or {}
    promoted = sorted(k for k, v in teams.items() if v.get("flag") == "promoted")
    churn = sorted(k for k, v in teams.items()
                   if v.get("flag") == "high_turnover")
    if not promoted and not churn:
        return ""
    bits = []
    if promoted:
        bits.append(
            f"<strong>{escape(', '.join(promoted))}</strong> "
            f"{'are' if len(promoted) > 1 else 'is'} newly promoted, so "
            "there are no Premier League results to fit a team rating on and "
            "the model starts them from a baseline.")
    if churn:
        bits.append(
            f"<strong>{escape(', '.join(churn))}</strong> lost an unusually "
            "large share of last season's minutes, and team ratings are "
            "fitted on results, so they still read as last season's squad.")
    n_shown = sum(1 for r in shown if r.get("team_flag"))
    if n_shown:
        where = (f" Their players carry a tag in the table, {n_shown} of them "
                 f"in this top 100.")
    else:
        best = next(((i + 1, r) for i, r in enumerate(allrows)
                     if r.get("team_flag")), None)
        where = (
            f" No flagged player makes this top 100. The highest is "
            f"{escape(best[1]['web_name'])} "
            f"({escape(best[1]['team_short'])}) at #{best[0]} of "
            f"{len(allrows)}." if best else "")
    return (
        '<p class="note"><strong>Flagged teams.</strong> ' + " ".join(bits) +
        " The flag means the projection is working with weaker information. "
        "It does not say which way that moves the number, because that is "
        "the part the data would not support." + where + "</p>")


def render_club_best(xp: dict, now: datetime) -> str | None:
    """Jokaisen seuran paras pelaaja per positio (14.8.2026).

    MIKSI TAMA SIVU ON OLEMASSA. Jakokortti (`gen_share_card.py club-best`)
    julkaisee samat 80 rivia kuvana, ja sen alatunniste ohjaa TANNE. Ilman
    tata sivua kortin luvut eivat olisi tarkistettavissa milläan ilmaisella
    pinnalla: `/api/fantasy/xp` on premium-portin takana maskattu top-10:een,
    ja `/fpl/expected-points` on `rows[:100]` — eli nousijaseurojen karjet
    (Belloumi, Tchaouna, Florentino, Smith Rowe) eivat mahdu koko liigan
    sadan parhaan joukkoon, ja ne ovat tasan ne rivit joita lukija
    todennakoisimmin haluaa tarkistaa.

    Laskenta on JAETTU MODUULI (`src/models/fpl_club_best.py`) kortin kanssa.
    Jos ne laskettaisiin erikseen, ne voisivat ajautua erilleen ja kortin
    vaite kaatuisi tasan silla reitilla jolla se piti todistaa.

    VAPAA/PREMIUM-RAJA: tama on seurakohtainen KARKI, ei koko lista — 80
    rivia 507:sta. Rate-my-team, siirtosuunnittelija ja kapteenirankkeri
    pysyvat premiumina. Sama peruste kuin /fpl/expected-points-rajassa:
    lista on sisaltoa, tyokalut ovat tuote.
    """
    meta = xp.get("meta") or {}
    players = xp.get("players") or []
    if not meta.get("available") or not players:
        return None

    _gws = ((players[0] if players else {}).get("gameweeks")) or []
    n_gw = len(_gws) or 6
    # 25.8: ikkuna johdetaan TODELLISISTA kierroksista eika kaavasta
    # `first + n - 1`, joka valehtelee heti kun lista ja aloituskierros ovat
    # eri mielta. Ks. src/models/fpl_gameweek.window_label.
    window = _window_label(meta, _gws, n_gw)
    url = f"{BASE}/fpl/club-best"

    sections, all_clubs, lead = [], [], None
    for pos in POSITIONS:
        rows = club_best_rows(players, pos)
        if not rows:
            continue
        if pos == "MID":
            lead = rows[0]
        all_clubs.extend(r["club"] for r in rows)
        n_prior = sum(1 for r in rows if r["prior"])
        trows = "".join(
            "<tr>"
            f'<td class="n">{i + 1}</td>'
            f'<td>{escape(str(r["name"]))}'
            + (' <span class="flag" title="No Premier League games yet, '
               'role guessed from price">?</span>' if r["prior"] else "")
            + "</td>"
            f'<td class="tm">{_kit_svg(r["club"])}'
            f'<span>{escape(r["club"])}</span></td>'
            f'<td class="n m-hide">{r["price"]:.1f}</td>'
            f'<td class="n hi">{r["xp"]:.1f}</td>'
            f'<td>{escape(gap_text(r))}</td>'
            f'<td class="n m-hide">{r["xmins"]:.0f}</td>'
            "</tr>"
            for i, r in enumerate(rows)
        )
        note = ""
        if n_prior:
            note = (f'<p class="note">? = no Premier League games yet, role '
                    f"guessed from price ({n_prior} of {len(rows)}).</p>")
        sections.append(
            f'<h2 id="{pos.lower()}">Best {pos} at every club</h2>'
            '<div class="lb-wrap"><table class="lb">'
            "<thead><tr>"
            '<th class="n">#</th><th>Player</th><th>Club</th>'
            '<th class="n m-hide">Price</th>'
            f'<th class="n">{n_gw}GW xP</th>'
            "<th>Gap to club's 2nd</th>"
            '<th class="n m-hide">xMins</th>'
            "</tr></thead>"
            f"<tbody>{trows}</tbody></table></div>{note}"
        )
    if not sections:
        return None

    title = (f"Best FPL Player at Every Club by Position "
             f"({window}) | GoalIQ")
    desc = (
        f"Every Premier League club's best goalkeeper, defender, midfielder "
        f"and forward by projected points for {window}, with the gap to that "
        f"club's second option. Free, no sign-in."
    )
    lead_txt = ""
    if lead:
        lead_txt = (
            f" {escape(str(lead['name']))} leads the midfielders on "
            f"{lead['xp']:.1f} xP.")
    hero = (
        "<h1>The best player at every club, by position</h1>"
        '<p class="lede">Our match model projects every player over '
        f"{escape(window)}. This page shows the leader at each club in each "
        "position, plus the gap to that club's second option, which tells you "
        "whether the club has one obvious pick or a real choice."
        f"{lead_txt} Free, no sign-in, rebuilt every few hours.</p>"
    )
    body = (
        f"{_kit_defs(all_clubs)}"
        + "".join(sections)
        # 🔴 15.8, Villen havainto: "aika huonosti erottee tuolta noi seurojen
        # omat sivut tosta club-best sivulta". Nama olivat pienessa harmaassa
        # alaviitteessa kahdenkymmenen nimen pilkkuluettelona, eli 20 sivua
        # piiloutui yhteen virkkeeseen. Nyt oma otsikko ja sama chip-tyyli
        # kuin seurasivujen valitsimessa: sama asia nayttaa samalta.
        + '<h2 id="club-pages">Every club has its own page</h2>'
        + '<p>Set-piece takers with the order FPL publishes, a predicted XI '
          "with start probabilities, and that club's best players in one "
          "place.</p>"
        + '<nav class="clubnav" aria-label="Club pages"><b>Clubs</b>'
        + "".join(
            f'<a href="/fpl/club/{s}">{escape(c)}</a>'
            for c, s in sorted(
                (c, CLUB_SLUGS[c]) for c in set(all_clubs) if c in CLUB_SLUGS))
        + "</nav>"
        + '<p class="note">The gap is measured against the same club and the '
          "same position, not against the row above. \"No 2nd projected\" "
          "means no other player at that club cleared the projection "
          "threshold, which is not the same as the club having only one.</p>"
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)



def render_team_news(xp: dict, now: datetime) -> str | None:
    """Team news, mutta KAANTEISENA: mita poissaolo maksaa pisteina (15.8.2026).

    MIKSI TAMA SIVU ON OLEMASSA. Villen kysymys 15.8: saisiko meille FFScoutin
    kaltaisen team news -pinnan, ja vaatiiko se toimittajan lehdistotilaisuuteen.

    Ei vaadi. Mittasin FPL:n bootstrapista samana paivana: 76 pelaajaa 587:sta
    kantaa VIRALLISTA news-tekstia aikaleimoineen (news, news_added,
    chance_of_playing_next_round). Se on sama pohja jolta FFScout lahtee, ja se
    on jo committoidussa artefaktissamme — tama sivu ei tee yhtaan uutta hakua.

    ERO KILPAILIJAAN ON KULMA, EI DATA. FFScout kertoo KUKA on ulkona. Me
    kerromme MITA SE MAKSAA: epavarmalla pelaajalla on xP-luku horisontille ja
    omistusprosentti, eli lukija nakee seka riskin etta sen laajuuden. Sita
    lukua ei voi kirjoittaa ilman mallia, joten sivua ei voi kopioida
    uutisvirrasta.

    EI TEKOALYARTIKKELEITA. Tama on generoitu taulukko mallin omista luvuista
    eika teeskentele journalismia. Peruste on mitattu: 9.-10.8 nelja
    Reddit-kayttajaa tunnisti tekstimme koneen kirjoittamaksi, ja ainoa
    puolustettava omaisuutemme on julkinen track record.

    JARJESTYS on omistusprosentti laskevasti eika xP: sivun kysymys on
    "koskeeko tama minua", ja omistus on FPL:n oma julkinen luku johon lukija
    voi verrata omaa joukkuettaan.
    """
    meta = xp.get("meta") or {}
    players = xp.get("players") or []
    excluded = xp.get("excluded") or []
    if not meta.get("available") or not players:
        return None

    _gws = ((players[0] if players else {}).get("gameweeks")) or []
    n_gw = len(_gws) or 6
    # 25.8: ikkuna johdetaan TODELLISISTA kierroksista eika kaavasta
    # `first + n - 1`, joka valehtelee heti kun lista ja aloituskierros ovat
    # eri mielta. Ks. src/models/fpl_gameweek.window_label.
    window = _window_label(meta, _gws, n_gw)
    url = f"{BASE}/fpl/team-news"

    def _owned(r):
        try:
            return float(r.get("owned_pct") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    # Ulkona = chance 0 kummastakin listasta. `excluded` sisaltaa myos
    # below_min_xp -rivit joilla ei ole uutista lainkaan -> ne EIVAT ole team
    # newsia ja ne rajautuvat pois uutistekstin olemassaololla.
    out_rows, doubt_rows = [], []
    for r in list(players) + list(excluded):
        news = (r.get("news") or "").strip()
        chance = r.get("chance_next")
        if not news or chance is None:
            continue
        (out_rows if chance == 0 else doubt_rows).append(r)
    out_rows.sort(key=_owned, reverse=True)
    doubt_rows.sort(key=_owned, reverse=True)
    if not out_rows and not doubt_rows:
        return None

    all_clubs = [r.get("team_short") for r in out_rows + doubt_rows
                 if r.get("team_short")]

    # 15.8, Villen saanto: "jos team news tms uutisissa on jotain pistedataa
    # tms niin sen tulee olla meidan omaa" — ja tarkennus: viime kauden
    # FPL-pisteet SAAVAT nakya, koska ne ovat muuttumaton fakta eivatka
    # johdettu luku. Ne jaavat siis omalle sarakkeelleen.
    #
    # Sen RINNALLE tulee oma lukumme, koska pelkka viime kausi ei vastaa siihen
    # mita lukija oikeasti kysyy ("pitaako minun tehda siirto"): kuka seurassa
    # korvaa ja mita meidan malli antaa hanelle. Laskenta on jaettu moduuli
    # club_best_rows, sama jota /fpl/club-best kayttaa, joten luvut eivat voi
    # ajautua erilleen.
    cover: dict[tuple[str, str], dict] = {}
    for _pos in POSITIONS:
        for _row in club_best_rows(players, _pos):
            cover[(_row["club"], _pos)] = _row

    def _cover_cell(r):
        """Seuran paras saatavilla oleva pelaaja samassa positiossa, meidan xP."""
        c = cover.get((r.get("team_short"), r.get("pos")))
        if not c or c.get("name") == r.get("web_name"):
            return "<td>-</td>"
        return (f'<td>{escape(str(c["name"]))} '
                f'<span class="hi">{c["xp"]:.1f}</span></td>')

    def _xp_cell(r):
        v = r.get("xp_horizon_total")
        if isinstance(v, (int, float)):
            return f'<td class="n hi">{v:.1f}</td>'
        # Poissaolevalla ei ole projektiota. Viime kauden pisteet kertovat mika
        # on poissa, ilman etta keksitaan xP:ta jota ei laskettu.
        ls = (r.get("last_season") or {}).get("points")
        if isinstance(ls, (int, float)):
            return f'<td class="n">{ls:.0f}<span class="m-hide"> last yr</span></td>'
        return '<td class="n">-</td>'

    sections = []
    if out_rows:
        trows = "".join(
            "<tr>"
            f'<td>{escape(str(r.get("web_name", "")))}</td>'
            f'<td class="tm">{_kit_svg(r.get("team_short", ""))}'
            f'<span>{escape(str(r.get("team_short", "")))}</span></td>'
            f'<td class="m-hide">{escape(str(r.get("pos", "")))}</td>'
            f'<td>{escape((r.get("news") or "").strip())}</td>'
            f'<td class="n">{_owned(r):.1f}%</td>'
            + _xp_cell(r)
            + _cover_cell(r)
            + "</tr>"
            for r in out_rows
        )
        sections.append(
            '<h2 id="out">Ruled out</h2>'
            '<div class="lb-wrap"><table class="lb">'
            "<thead><tr><th>Player</th><th>Club</th>"
            '<th class="m-hide">Pos</th><th>Status</th>'
            '<th class="n">Owned</th>'
            '<th class="n m-hide">Last season</th>'
            "<th>Who covers (our xP)</th>"
            "</tr></thead>"
            f"<tbody>{trows}</tbody></table></div>"
            '<p class="note">Last season is the player\'s final FPL total, '
            "a fixed historical number, not a projection. The model does not "
            "project a player it has ruled out, so the last column is our own "
            "number instead: the club's best available player in the same "
            "position and what we project them to score. A dash means no "
            "other player at that club cleared the projection threshold "
            "there.</p>"
        )

    if doubt_rows:
        trows = "".join(
            "<tr>"
            f'<td>{escape(str(r.get("web_name", "")))}</td>'
            f'<td class="tm">{_kit_svg(r.get("team_short", ""))}'
            f'<span>{escape(str(r.get("team_short", "")))}</span></td>'
            f'<td class="m-hide">{escape(str(r.get("pos", "")))}</td>'
            f'<td>{escape((r.get("news") or "").strip())}</td>'
            f'<td class="n">{int(r.get("chance_next") or 0)}%</td>'
            f'<td class="n">{_owned(r):.1f}%</td>'
            + _xp_cell(r)
            + "</tr>"
            for r in doubt_rows
        )
        sections.append(
            '<h2 id="doubtful">Doubtful</h2>'
            '<div class="lb-wrap"><table class="lb">'
            "<thead><tr><th>Player</th><th>Club</th>"
            '<th class="m-hide">Pos</th><th>Status</th>'
            '<th class="n">Chance</th><th class="n">Owned</th>'
            f'<th class="n">{n_gw}GW xP</th>'
            "</tr></thead>"
            f"<tbody>{trows}</tbody></table></div>"
            '<p class="note">The xP column already carries the flag: a '
            "reduced chance of playing lowers projected minutes, so the "
            "number you see is what the model expects including the doubt, "
            "not what the player would score if fully fit.</p>"
        )

    n_out, n_doubt = len(out_rows), len(doubt_rows)
    title = f"FPL Team News: Injuries and Suspensions ({window}) | GoalIQ"
    desc = (
        f"Every Premier League player currently ruled out or doubtful for "
        f"{window}, with ownership and what the model projects them to score. "
        f"{n_out} out, {n_doubt} doubtful. Free, no sign-in."
    )
    hero = (
        "<h1>Team news, with the points cost attached</h1>"
        '<p class="lede">Official FPL status for every ruled-out and doubtful '
        "player, sorted by how many managers own them. The difference from a "
        "team news list is the last column: our match model projects what each "
        f"doubtful player is still worth over {escape(window)}, with the "
        "reduced chance of playing already priced in. "
        f"{n_out} out, {n_doubt} doubtful. Updated daily, no sign-in.</p>"
    )
    body = (
        f"{_kit_defs(all_clubs)}"
        + "".join(sections)
        + '<p class="note">Status text comes from the official Fantasy '
          "Premier League feed, which is what clubs report. It is not a press "
          "conference summary: if a manager says a player trained today but "
          "the official status has not changed, this page will not know it "
          "yet.</p>"
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)



NOTES_PATH = ROOT / "data" / "fpl_notes.json"


def note_plain_text(n: dict) -> str:
    """Muistion KOKO teksti litteana, taulukon solut mukaan lukien.

    Tarvitaan koska `claims`-portti vertaa vaitteita muistion tekstiin, ja
    15.8 artikkelin luvut siirtyivat kappaleista datataulukkoon. Pelkka
    `" ".join(paragraphs)` kaatuu dict-lohkoon eika nakisi taulukon soluja
    vaikka ne ovat juuri ne luvut jotka lukija tarkistaa.
    """
    osat = []
    for p in n.get("paragraphs") or []:
        if isinstance(p, str):
            osat.append(p)
        elif isinstance(p, dict):
            if p.get("h2"):
                osat.append(str(p["h2"]))
            for solu in (p.get("head") or []):
                osat.append(str(solu))
            for rivi in (p.get("rows") or []):
                osat += [str(c) for c in rivi]
    return " ".join(osat)


def _note_block(p) -> str:
    """Yksi muistiolohko: merkkijono = kappale, dict = valiotsikko tai taulukko.

    MIKSI LAAJENNUS (15.8). Ensimmainen muistio oli neljan kappaleen mittainen
    ja litteä lista riitti. Villen pyytama LAAJA analyyttinen artikkeli (malli
    FFScoutin seuraennakot) ei mahdu siihen muotoon: siina on valiotsikot ja
    datataulukko, ja taulukon puristaminen kappaleeksi tekisi juuri sen mita
    artikkeli kritisoi — lukujen esittamisen muodossa jota ei voi lukea.

    Taaksepain yhteensopiva: merkkijono kayttaytyy tasan kuten ennen, joten
    olemassa oleva muistio renderoityy muuttumattomana.
    """
    if isinstance(p, str):
        return f"<p>{escape(p)}</p>"
    if isinstance(p, dict):
        if p.get("h2"):
            return f"<h3>{escape(str(p['h2']))}</h3>"
        rows = p.get("rows") or []
        if rows:
            head = p.get("head") or []
            th = (
                "<thead><tr>"
                + "".join(f"<th>{escape(str(c))}</th>" for c in head)
                + "</tr></thead>"
                if head
                else ""
            )
            body = "".join(
                "<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>"
                for r in rows
            )
            # Taulukko kaaritaan omaan vieritinsailioonsa: leveä sisalto ei saa
            # panna koko sivua vaakavieritykseen kapealla ruudulla.
            return f'<div class="tblwrap"><table class="note-tbl">{th}<tbody>{body}</tbody></table></div>'
    return ""


def render_notes(notes_doc: dict, now: datetime) -> str | None:
    """Kierrosmuistiot yhdella URLilla (15.8.2026, Villen GO).

    MIKSI YKSI SIVU EIKA SIVU PER MUISTIO. Erillinen sivu per muistio jaisi
    orvoksi sisaisessa linkityksessa — sama vika joka mitattiin samana paivana
    kahdesti (`team-news` ja `expected-points` puuttuivat `_TOOL_LINKS`:sta,
    ja `expected-points` on se sivu johon X-postaukset linkittavat). Yksi
    kertyva URL keskittaa linkit eika voi vanhentua kuratoidusta listasta.

    MIKSI TEKSTIA EI GENEROIDA. Villen kysymys 15.8 oli voiko naita
    automatisoida. Julkaisutarkistaja blokkasi ensimmaisen muistion kuudella
    loydoksella, joista NELJA koski tyylia: nolla lyhennetta 960 merkissa,
    pilkottu antiteesi, yhteenvetolause. Generaattori tuottaisi tasan ne.
    Teksti tulee siis `data/fpl_notes.json`:sta kasin kirjoitettuna kierrosta
    varten ja julkaisutarkistajan lapaisemana; tama funktio vain lataa sen.

    🔴 EI KUITENKAAN "ihmisen kirjoittama". Kirjoitin llms.txt:aan 15.8
    rivin "Written by a person, not generated" ja se oli VALHE: tekstin
    kirjoitti tama assistentti. Villen huomio samana paivana. Ero jota
    oikeasti ajoin takaa on generoitu vs kierrosta varten kirjoitettu, eika
    se ole sama asia kuin tekijyys. Kirjattu muisti: AI-kayttoa ei koskaan
    kiisteta.

    Automatisoitu on se osa joka petti MEKAANISESTI: `claims`-lista ajetaan
    `scripts/check_claim_route.py`:lla, joka tarkistaa etta jokainen luku on
    loydettavissa siita sivusta johon muistio linkittaa. Se on tarpeen koska
    15.8 kirjoitin vaitteen joka oli TOSI mutta jonka lukija ei olisi voinut
    tarkistaa.
    """
    notes = (notes_doc or {}).get("notes") or []
    if not notes:
        return None
    # Sama tasatilanne kuin etusivun nostossa: jarjestysnumero ratkaisee, jotta
    # saman paivan uudempi muistio on sivulla ylimpana.
    notes = [
        n for _, n in sorted(
            enumerate(notes),
            key=lambda p: (str(p[1].get("date") or ""), p[0]),
            reverse=True,
        )
    ]
    url = f"{BASE}/fpl/notes"

    blocks = []
    for n in notes:
        paras = "".join(_note_block(p) for p in n.get("paragraphs") or [])
        if not paras:
            continue
        check = str(n.get("check_url") or f"{BASE}/fpl/team-news")
        cta = escape(str(n.get("cta") or "Check the numbers"))
        # Otsikko linkittaa artikkelin omaan URLiin. Ilman tata kokoomasivu
        # olisi ainoa reitti, ja ulkoiset linkit osoittaisivat sivulle jonka
        # sisalto vaihtuu seuraavan muistion myota.
        slug_ = escape(str(n.get("slug") or ""))
        blocks.append(
            f'<h2 id="{slug_}">'
            f'<a href="/fpl/note/{slug_}">'
            f'{escape(str(n.get("title") or ""))}</a></h2>'
            f'<p class="note">{escape(str(n.get("date") or ""))}</p>'
            f'<div class="note-body">{paras}</div>'
            f'<p><a href="{escape(check)}">{cta}</a>.</p>'
            + _share_row(str(n.get("title") or ""),
                         f'{url}#{n.get("slug") or ""}')
        )
    if not blocks:
        return None

    latest = notes[0]
    title = "FPL notes from the model | GoalIQ"
    desc = (
        "Short gameweek notes where every number comes from our own match "
        "model and every one of them is on a free page you can open. Latest: "
        + str(latest.get("title") or "")
    )
    hero = (
        "<h1>Notes from the model</h1>"
        '<p class="lede">Short notes, one per gameweek, written when the '
        "numbers say something worth saying. Every figure here is our own "
        "model output and every one of them sits on a free page you can open "
        "and check. No sign-in.</p>"
    )
    body = (
        "".join(blocks)
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)



NOTE_DIR = OUT_DIR / "note"


MINUTES_VALIDATION_PATH = ROOT / "data" / "fpl_minutes_validation.json"

SLICE_LABELS = {
    "all": "Every player in the test",
    "played >=1 min in GW1-6": "Played at least one minute",
    "no minutes at all": "Never appeared",
    "prior >=60 min (expected starters)": "We expected 60+ minutes",
    "prior >=60 AND played": "We expected 60+ and they played",
}


def _preseason_basis(meta: dict) -> bool:
    """Onko minuuttimalli yha edellisen kauden arkistolla?

    22.8: esikausivaraukset renderoityivat EHDOITTA, ja ne ovat ristiriidassa
    saman sivun "kierros on kesken" -rivin kanssa heti kun liigaminuutteja
    alkaa kertya. Ehto on DATAN POHJA eika kierrosnumero — sama saanto kuin
    appin esikausivarauksessa 19.8 — joten varaus poistuu itsestaan kun malli
    vaihtaa kuluvan kauden dataan.
    """
    return (((meta or {}).get("data_coverage") or {})
            .get("baseline_mode") == "prev_season_archive")


def _minutes_caveat() -> str:
    """Ylipredikointivaraus SUORAAN mittausartefaktista.

    Ks. kutsupaikan kommentti: aiempi kovakoodattu "about 14 minutes" oli
    peraisin kalibrointiskriptin sarakkeesta joka kertoo eri asian kuin lause
    vaitti. Luku tulee nyt samasta artefaktista kuin /fpl/minutes-accuracy,
    joten kaksi pintaa ei voi kertoa samasta asiasta eri lukua.

    Artefakti puuttuu -> tyhja merkkijono. Varaus katoaa mieluummin kuin
    nayttaa vaaran luvun; sivun muut varaukset jaavat paikalleen.
    """
    doc = _load(MINUTES_VALIDATION_PATH)
    foldit = [f for f in ((doc or {}).get("folds") or [])
              if f.get("starter_bias_80_min") is not None]
    if not foldit:
        return ""
    ka = sum(f["starter_bias_80_min"] for f in foldit) / len(foldit)
    return (
        '<p class="note"><strong>Our pre-season minutes run high at the top.'
        "</strong> We tested our own prior across "
        f"{'three' if len(foldit) == 3 else str(len(foldit))} summer breaks. "
        f"Players we projected at 80+ minutes came in about {ka:.0f} minutes "
        "lower than we said, and players we projected at the bottom came in a "
        "little higher. The order of this list is unchanged by that, and the "
        "gap closes as 2026/27 results arrive. "
        '<a href="/fpl/minutes-accuracy">The full measurement &#9656;</a></p>'
    )


def _kausipari(fold: str) -> str:
    """'2223->2324' -> '22/23 to 23/24'. Raaka kausikoodi on sisainen muoto."""
    osat = [x.strip() for x in fold.split("->")]
    muoto = [f"{o[:2]}/{o[2:]}" if len(o) == 4 and o.isdigit() else o
             for o in osat]
    return " to ".join(muoto)


def render_minutes_accuracy(doc: dict | None, now: datetime) -> str | None:
    """/fpl/minutes-accuracy - mallin oman minuuttiarvion mitattu virhe.

    MIKSI TAMA SIVU ON OLEMASSA (19.8.2026, Villen paatos). Artikkeli
    "We measured our own worst column" lupasi lukijalle etta laskennan voi
    toistaa, ja ainoa reitti oli julkinen repo. Ville: repoa ei nayteta.
    Ilman korvaavaa reittia jaljelle olisi jaanyt "luota lukuihimme omasta
    virheestamme", ja se on tasan se muoto jonka julkaisuportti kaataa.

    Luvut tulevat artefaktista `data/fpl_minutes_validation.json`, jonka
    `scripts/validate_preseason_prior.py --emit` kirjoittaa SAMASTA ajosta
    jonka se tulostaa. Sivulla ei ole yhtaan kasin kirjoitettua lukua: jos
    mittaus muuttuu, sivu muuttuu, eivatka ne voi ajautua erilleen.
    """
    if not doc or not doc.get("slices_prior_only"):
        return None

    def rivi(r, label_map=None):
        nimi = (label_map or {}).get(r["slice"], r["slice"])
        return (f"<tr><td>{escape(nimi)}</td>"
                f'<td class="num">{r["n"]}</td>'
                f'<td class="num">{r["mae"]:.1f}</td>'
                f'<td class="num">{r["bias"]:+.1f}</td></tr>')

    leikkaukset = "".join(rivi(r, SLICE_LABELS) for r in doc["slices_prior_only"])
    jalkeen = "".join(rivi(r, SLICE_LABELS)
                      for r in doc.get("slices_after_squad_constraint") or [])
    foldit = "".join(
        f'<tr><td>{escape(_kausipari(str(f["fold"])))}</td>'
        f'<td class="num">{f["n"]}</td>'
        f'<td class="num">{f["live_mae"]:.2f}</td>'
        f'<td class="num">{f["best_mae"]:.2f}</td>'
        f'<td class="num">{f["starter_bias_min"]:+.1f}</td>'
        f'<td class="num">'
        f'{("%+.1f" % f["starter_bias_80_min"]) if f.get("starter_bias_80_min") is not None else "-"}'
        f'</td></tr>'
        for f in doc.get("folds") or [])
    puoliintumat = "".join(
        f'<tr><td>{"Flat" if r["halflife"] == "flat" else "Half-life " + str(int(r["halflife"]))}'
        f'{" (live)" if r["halflife"] == doc.get("live_halflife") else ""}</td>'
        f'<td class="num">{r["mae"]:.3f}</td>'
        f'<td class="num">{r["bias"]:+.2f}</td></tr>'
        for r in doc.get("halflives") or [])

    n = doc["population"]
    to_gw = doc.get("to_gw", 6)
    kaudet = f'{doc["season_from"][:2]}/{doc["season_from"][2:]}'
    kausi_to = f'{doc["season_to"][:2]}/{doc["season_to"][2:]}'
    url = f"{BASE}/fpl/minutes-accuracy"
    otsikko = "How wrong our expected minutes are"
    desc = (f"We tested the model's own minutes prior across three summer "
            f"breaks. Mean absolute error is about {doc['live']['mae']:.0f} "
            f"minutes per player per game, and almost all of the bias comes "
            f"from players who never appeared.")

    body = (
        f"<p>Every expected points total we publish rests on a guess about how "
        f"long someone will be on the pitch. This page is that guess measured "
        f"against what happened.</p>"

        f"<h2>The test</h2>"
        f"<p>Build the minutes prior from {kaudet}, use it to predict the first "
        f"{to_gw} gameweeks of {kausi_to}, then compare it to the minutes those "
        f"players actually played. Both ends are FPL's own published data: last "
        f"season's minutes in, this season's first {to_gw} gameweeks out. The "
        f"prior is a decay-weighted average of a player's own past rounds, "
        f"half-life {int(doc.get('live_halflife') or 10)} gameweeks, and nothing "
        f"in it sees team news. {n} players had at least five rounds behind them "
        f"and were still in the game the next season, so they qualified.</p>"

        f"<h2>Where the error is</h2>"
        f'<div class="tblwrap"><table class="note-tbl"><thead><tr>'
        f"<th>Group</th><th>Players</th><th>Average error, minutes</th>"
        f"<th>Bias, minutes</th></tr></thead><tbody>{leikkaukset}"
        f"</tbody></table></div>"
        f"<p>Bias is how far we were above what happened. The column is "
        f"close to unbiased for players who got on the pitch at all, and the "
        f"whole overshoot sits with the players who never appeared.</p>"

        + (f"<h2>After the squad constraint</h2>"
           f"<p>The builder normalises each club to one keeper and ten outfield "
           f"players before the numbers reach a page, so these are the same "
           f"groups measured after that pass.</p>"
           f'<div class="tblwrap"><table class="note-tbl"><thead><tr>'
           f"<th>Group</th><th>Players</th><th>Average error, minutes</th>"
           f"<th>Bias, minutes</th></tr></thead><tbody>{jalkeen}"
           f"</tbody></table></div>" if jalkeen else "")

        + (f"<h2>Three summers, not one</h2>"
           f"<p>One summer could be luck, so the same test runs on three.</p>"
           f'<div class="tblwrap"><table class="note-tbl"><thead><tr>'
           f"<th>Prior to season</th><th>Players</th><th>Error, live setting</th>"
           f"<th>Error, best setting</th><th>Overshoot, 60+ starters</th>"
           f"<th>Overshoot, 80+ starters</th>"
           f"</tr></thead><tbody>{foldit}</tbody></table></div>" if foldit else "")

        + (f"<h2>Tuning doesn't fix it</h2>"
           f"<p>The prior weights recent rounds more heavily than old ones. "
           f"Here is the whole range, from very sharp to no decay at all.</p>"
           f'<div class="tblwrap"><table class="note-tbl"><thead><tr>'
           f"<th>Setting</th><th>Average error, minutes</th><th>Bias</th>"
           f"</tr></thead><tbody>{puoliintumat}</tbody></table></div>"
           f"<p>The best setting scores "
           f'{doc["best"]["mae"]:.3f} and the one we run scores '
           f'{doc["live"]["mae"]:.3f}, which is '
           f'{doc["live"]["mae"] - doc["best"]["mae"]:.2f} of a minute apart. '
           f"Flat weighting, which is where most people start, scores "
           f'{doc["flat"]["mae"]:.3f}.</p>' if puoliintumat else "")

        + f"<h2>What to do with this</h2>"
        f"<p>Treat our expected minutes as a good estimate for players you're "
        f"already sure are starting, and as close to no information for "
        f"players you're not.</p>"
        f'<p><a href="/fpl/note/we-measured-our-own-worst-column">The write-up '
        f"of this measurement &#9656;</a> &middot; "
        f'<a href="/fpl/expected-points">The projections it feeds &#9656;</a></p>'

        + f"{UPSELL}{_cta()}"
        f'<p class="note">Measured {escape(str(doc.get("generated_at", ""))[:10])}. '
        f"These numbers are written to this page out of the run that produced "
        f"them, so the page cannot drift from the measurement. "
        f"{DISCLAIMER}</p>"
    )

    jsonld = [{
        "@context": "https://schema.org", "@type": "Dataset",
        "name": otsikko, "url": url, "description": desc,
        "dateModified": now.strftime("%Y-%m-%d"),
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "variableMeasured": [
            {"@type": "PropertyValue", "name": "Mean absolute error, minutes",
             "value": round(doc["live"]["mae"], 2)},
            {"@type": "PropertyValue", "name": "Players in test", "value": n},
        ],
    }]
    return _page(f"{otsikko} | GoalIQ", desc, url,
                 f"<h1>{escape(otsikko)}</h1>", body, jsonld)


def render_note_page(n: dict, now: datetime) -> str | None:
    """Yksi artikkeli omalla URLillaan: /fpl/note/<slug>.

    🔴 MIKSI TAMA LISATTIIN 15.8, vaikka `render_notes` valittiin nimenomaan
    YHDEKSI kertyvaksi URLiksi. Kaksi mitattua syyta, kumpikaan ei ollut
    tiedossa silloin:

    1. Alustan valimuisti. X tallentaa esikatselukortin sivukohtaisesti ja
       yhdistaa variantit `og:url`:n kautta, joten utm-parametri ei murra
       sita. Mitattu 15.8: `/fpl/stats` naytti X:ssa GENEERISTA korttia
       vaikka silla on ollut oma 8.8 lahtien, ja `/fpl/notes` naytti kortin
       ilman kuvaa lainkaan. Osoite jota alusta ei ole nahnyt haetaan
       tuoreena.
    2. Linkin hauraus. Kokoomasivulle osoittava linkki nayttaa sen artikkelin
       joka sattuu olemaan ylimpana. Uusi muistio tyontaa edellisen alemmas
       ilman etta mikaan huutaa, eli eilen jaettu linkki vie tanaan eri
       tekstiin.

    Kokoomasivu JAA paikalleen ja linkittaa naihin, joten alkuperainen
    orpoushuoli ei palaa: jokainen artikkeli on kahden sisaisen linkin paassa.

    og:image loytyy automaattisesti, koska kortti on nimetty artikkelin
    slugilla ja `_og_image()` johtaa nimen canonicalista.
    """
    slug = str(n.get("slug") or "").strip()
    otsikko = str(n.get("title") or "").strip()
    if not slug or not otsikko:
        return None
    paras = "".join(_note_block(x) for x in n.get("paragraphs") or [])
    if not paras:
        return None

    url = f"{BASE}/fpl/note/{slug}"
    tekstit = [x for x in (n.get("paragraphs") or []) if isinstance(x, str)]
    desc = (tekstit[0] if tekstit else otsikko)[:300]
    check = str(n.get("check_url") or f"{BASE}/fpl/stats")
    cta = escape(str(n.get("cta") or "Check the numbers"))

    body = (
        f'<p class="note">{escape(str(n.get("date") or ""))}</p>'
        f'<div class="note-body">{paras}</div>'
        f'<p><a href="{escape(check)}">{cta}</a>.</p>'
        + _share_row(otsikko, url)
        + '<p class="note-more"><a href="/fpl/notes">'
        "All notes from the model &#9656;</a></p>"
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "Article",
        "headline": otsikko, "url": url, "description": desc,
        "datePublished": str(n.get("date") or ""),
        "dateModified": now.strftime("%Y-%m-%d"),
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }]
    return _page(f"{otsikko} | GoalIQ", desc, url,
                 f"<h1>{escape(otsikko)}</h1>", body, jsonld)


CLUB_DIR = OUT_DIR / "club"

# FPL:n lyhenne -> URL-slug. Kirjoitettu auki eika johdettu nimesta, koska
# slug on PYSYVA sopimus: johdettu slug muuttuisi jos seuran nayttonimi
# muuttuu, ja jokainen ulkoinen linkki katkeaisi hiljaa.
CLUB_SLUGS = {
    "ARS": "arsenal", "AVL": "aston-villa", "BOU": "bournemouth",
    "BRE": "brentford", "BHA": "brighton", "BUR": "burnley",
    "CHE": "chelsea", "COV": "coventry", "CRY": "crystal-palace",
    "EVE": "everton", "FUL": "fulham", "HUL": "hull", "IPS": "ipswich",
    "LEE": "leeds", "LEI": "leicester", "LIV": "liverpool",
    "MCI": "manchester-city", "MUN": "manchester-united",
    "NEW": "newcastle", "NFO": "nottingham-forest", "SOU": "southampton",
    "SUN": "sunderland", "TOT": "tottenham", "WHU": "west-ham",
    "WOL": "wolves",
}

_SP_LABELS = (("pens", "Penalties"), ("corners", "Corners"), ("fk", "Free kicks"))





def _share_row(title: str, url: str) -> str:
    """Jakonapit artikkelille (15.8, Villen pyynto).

    ESITAYTETTY TEKSTI ON VAIN OTSIKKO JA LINKKI. Se on tietoinen rajaus:
    jaettu teksti on julkista tekstia, ja jos se sisaltaisi vaitteen, se
    pitaisi ajaa julkaisutarkistajan lapi joka kerta kun sivu regeneroituu.
    Otsikko on jo portitettu sivun mukana, joten se on ainoa turvallinen
    esitaytto joka ei vanhene lukujen mukana.

    Ei JS:aa: intent-linkit toimivat ilman skriptia, ja sivut ovat staattisia.
    """
    from urllib.parse import quote
    teksti = quote(f"{title}\n\n{url}")
    x = f"https://twitter.com/intent/tweet?text={teksti}"
    bsky = f"https://bsky.app/intent/compose?text={teksti}"
    return (
        '<div class="share"><span>Share</span>'
        f'<a href="{x}" rel="noopener nofollow" target="_blank">X</a>'
        f'<a href="{bsky}" rel="noopener nofollow" target="_blank">Bluesky</a>'
        f'<a href="{escape(url)}">Link</a>'
        "</div>"
    )


def _club_switcher(current: str, saatavilla: set[str]) -> str:
    """Kaikki 20 seuraa linkkeina, nykyinen korostettuna.

    🔴 MITATTU 15.8: seurasivulta linkitettiin NOLLAAN toiseen seurasivuun.
    Sisaantulo oli kunnossa (club-best linkitti kaikkiin 20), mutta lukija
    joka oli Bournemouthin sivulla ei paassyt Arsenaliin ilman paluuta.
    Kahdenkymmenen sisarsivun setti ilman keskinaista linkitysta on
    kaksikymmenta umpikujaa.

    Sivuvaikutus joka on itse asiassa paavaikutus: jokainen sivu saa 19 uutta
    sisaantulevaa linkkia, mika on tasan se signaali jota GSC kaipasi 28.7.
    """
    # VAIN sivut jotka oikeasti kirjoitetaan. CLUB_SLUGS kattaa 24 seuraa
    # (nousijat ja putoajat mukana), mutta sivuja syntyy vain niille joilla on
    # projektio: ensimmainen versio linkitti neljaan 404:aan (BUR, LEI, SOU,
    # WOL). Kuollut linkki on pahempi kuin puuttuva.
    rivit = []
    for short, slug in sorted(CLUB_SLUGS.items(), key=lambda x: x[1]):
        if slug not in saatavilla:
            continue
        if slug == current:
            rivit.append(f'<b class="here">{escape(short)}</b>')
        else:
            rivit.append(f'<a href="/fpl/club/{slug}">{escape(short)}</a>')
    return (
        '<nav class="clubnav" aria-label="Other clubs">'
        "<b>Clubs</b>" + "".join(rivit) + "</nav>"
    )


def _no_history_flag(p: dict) -> str:
    """Merkinta pelaajalle jolla ei ole Valioliiga-historiaa.

    🔴 MITATTU 15.8, Villen havainto: "araujon projected points 8.7 kuulostaa
    liian matalalta, han siirtyi juuri barcelonasta". Luku ei ollut vaite
    laadusta vaan minuuteista: `xmins` 33.5 ja `predicted_starts` 38 %, koska
    `data_basis` on `no_history` eika minuuttimallilla ole mihin ankkuroida.

    Malli KERTOO taman kahdella kentalla, ja niita on 158/505. Ne saavat myos
    saman kovakoodatun 38,0 %:n oletuksen, eli luku on sama arvaus kaikille.
    Ensimmainen versioni seurasivuista pudotti lipun, joten lukija nakisi
    "8.7" ilman merkkia siita etta se on arvaus. `club-best` naytti taman
    oikein jo ennestaan — en vain kayttanyt sen konventiota.

    🔴 TOINEN LIPPU 16.8, Villen havainto: "arsenalilla ei edes ole
    odegaardia laitettu alotuksee". Odegaard EI ole `no_history` vaan
    tavallinen `pl_history`-rivi, joten yllakuvattu lippu ei koskenut hanta
    lainkaan. Mitattu: korrelaatio(viime kauden avaukset / 38, `p_start`) =
    0,785 (n=285), eli katkennut kausi painaa priorin alas ilman etta
    mikaan kertoo sita lukijalle. 1363 minuuttia ja 16 avausta luetaan
    rotaatiopelaajaksi.

    Lippu ei korjaa lukua eika kerro suuntaa. Se kertoo etta arvio nojaa
    lyhyeen otokseen.
    """
    if p.get("data_basis") == "no_history":
        return (' <span class="flag" title="No Premier League games yet, role '
                'and minutes estimated">?</span>')
    if p.get("minutes_basis_flag") == "short_season":
        mins = (p.get("last_season") or {}).get("minutes")
        return (' <span class="flag" title="Only '
                f'{mins} minutes last season, so this player&#x27;s minutes '
                'estimate rests on a short spell rather than a full one. It '
                'does not say which way the number is off">!</span>')
    return ""


def _set_piece_rows(players: list[dict]) -> str:
    """Erikoistilannevuorot jarjestysnumeron mukaan.

    FPL julkaisee jarjestyksen (1 = ensimmainen vuorossa). Naytetaan vain
    numerot jotka FPL on antanut — tyhja tarkoittaa ettei jarjestysta ole
    julkaistu, EI etta pelaaja ei ota niita. Se ero on kerrottava, koska
    esikaudella tyhjia on paljon.
    """
    out = []
    for avain, otsikko in _SP_LABELS:
        rivit = [(p, (p.get("set_pieces") or {}).get(avain)) for p in players]
        rivit = sorted(((p, n) for p, n in rivit if isinstance(n, int)),
                       key=lambda x: x[1])
        if not rivit:
            continue
        nimet = ", ".join(
            f'{escape(str(p["web_name"]))} <span class="hi">{n}</span>'
            for p, n in rivit[:4])
        out.append(f"<tr><td>{otsikko}</td><td>{nimet}</td></tr>")
    return "".join(out)


def _xi_rows(players: list[dict]) -> tuple[str, int, list[dict]]:
    """Ennustettu avauskokoonpano: paras 11 aloitustodennakoisyyden mukaan,
    positiorajoilla 1-4-4-2 -tyyliin taipuen. Palauttaa (rivit, n)."""
    # 🔴 Kayta JAETTUA POSITIONS-vakiota, ala kovakoodaa. Kirjoitin tahan
    # ensin {"GK": 1, ...} ja jokaisen 20 seuran "Predicted XI" renderoitui
    # KYMMENELLA pelaajalla ilman maalivahtia: FPL:n koodi on "GKP" eika "GK",
    # ja `src.models.fpl_club_best.POSITIONS` tiesi sen jo. Rivi nakyi vaarana
    # vasta valmiilla sivulla, ei koodia lukemalla.
    kiintio = dict(zip(POSITIONS, (1, 4, 4, 2)))
    valitut = []
    for pos, n in kiintio.items():
        ryhma = sorted(
            (p for p in players if p.get("pos") == pos
             and isinstance(p.get("predicted_starts"), (int, float))),
            key=lambda p: -p["predicted_starts"])
        valitut.extend(ryhma[:n])
    # 🔴 TAYDENNYS 11:een. Kiintio 1-4-4-2 ei tayty jos seuralla ei ole
    # tarpeeksi pelaajia jossakin positiossa: mitattu Liverpool, jolla on
    # projektiossa YKSI nimellinen hyokkaaja, jolloin XI jai kymmeneen.
    # Vajaa "Predicted XI" on nakyva virhe. Taytetaan parhailla jaljella
    # olevilla aloitustodennakoisyyden mukaan, mika on myos lahempana sita
    # miten seura oikeasti pelaa kuin tyhja paikka.
    if len(valitut) < 11:
        otetut = {id(p) for p in valitut}
        loput = sorted(
            (p for p in players
             if id(p) not in otetut
             and isinstance(p.get("predicted_starts"), (int, float))),
            key=lambda p: -p["predicted_starts"])
        valitut.extend(loput[:11 - len(valitut)])
    if len(valitut) < 11:
        return "", 0, []
    # Sama kovakoodaus oli myos tassa: "GK" ei osunut, joten maalivahti
    # sortautui listan HANNILLE. Kentalla se on absurdi jarjestys.
    jarj = {pos: i for i, pos in enumerate(POSITIONS)}
    valitut.sort(key=lambda p: (jarj.get(p.get("pos"), 9), -p["predicted_starts"]))
    rivit = "".join(
        "<tr>"
        f'<td>{escape(str(p["web_name"]))}{_no_history_flag(p)}</td>'
        f'<td class="m-hide">{escape(str(p.get("pos", "")))}</td>'
        f'<td class="n">{float(p.get("price") or 0):.1f}</td>'
        f'<td class="n hi">{p["predicted_starts"]:.0f}%</td>'
        "</tr>"
        for p in valitut)
    return rivit, len(valitut), valitut


def _xi_omissions(players: list[dict], valitut: list[dict]) -> str:
    """Liputetut pelaajat jotka JAIVAT ulos ennustetusta XI:sta.

    🔴 MIKSI TAMA ON ERI ASIA KUIN RIVIN LIPPU. Ville huomasi 16.8 ettei
    Arsenalin XI:ssa ole Odegaardia. Rivikohtainen "!" ei auta hanta
    lainkaan, koska Odegaard ei ole sivulla: hanta ei renderoida XI:hin
    eika kahdeksan parhaan listaan. Lippu nakyy vain niille jotka ovat jo
    nakyvissa, ja valitus koski nimenomaan puuttuvaa nimea.

    Tama rivi vastaa siihen kysymykseen suoraan: kuka jai ulos ja mihin
    lukuun se nojaa. Ei suuntavaitetta.
    """
    otetut = {id(p) for p in valitut}
    ulkona = [p for p in players
              if id(p) not in otetut
              and p.get("minutes_basis_flag") == "short_season"
              and isinstance(p.get("predicted_starts"), (int, float))]
    if not ulkona:
        return ""
    ulkona.sort(key=lambda p: -(p.get("price") or 0))
    osat = []
    for p in ulkona[:4]:
        mins = (p.get("last_season") or {}).get("minutes")
        osat.append(f'{escape(str(p["web_name"]))} '
                    f'({p["predicted_starts"]:.0f}%, {mins} min)')
    return ('<p class="note">Missing from that eleven, and the reason is the '
            "same in each case: they played a short season, so the estimate "
            "reads them as rotation. "
            + ", ".join(osat) + ".</p>")


def render_club_page(short: str, players: list[dict], meta: dict,
                     now: datetime, saatavilla: set[str] | None = None) -> str | None:
    """Yhden seuran esittelysivu (15.8.2026, Villen tilaus).

    MIKSI TAMA FORMAATTI. Ville antoi esimerkiksi FFScoutin seurakohtaisen
    ennakon (parhaat pelaajat, erikoistilannevuorot, ennustettu XI). Se on
    heilla proosaa; meilla se on DATAA, ja siksi se on ainoa artikkelityyppi
    jonka runko voidaan generoida ilman etta teksti alkaa kuulostaa koneelta.
    Generoitu taulukko ei teeskentele mielipidetta.

    Kolme osaa vastaavat esimerkin kolmea lupausta:
      1. Best players    xP-jarjestys, hinta ja omistus rinnalla
      2. Set-piece takers FPL:n julkaisema jarjestysnumero
      3. Predicted XI     aloitustodennakoisyys, ei arvaus

    REHELLISYYSRAJAUS joka on koodissa eika vain copyssa: tyhja
    erikoistilannevuoro tarkoittaa ettei FPL ole julkaissut jarjestysta, EI
    etta pelaaja ei ota niita. Esikaudella tyhjia on paljon, ja tuon eron
    piilottaminen tekisi sivusta itsevarmemman kuin data on.
    """
    if len(players) < 8:
        return None
    slug = CLUB_SLUGS.get(short)
    if not slug:
        return None
    nimi = str(players[0].get("team") or short)
    url = f"{BASE}/fpl/club/{slug}"
    n_gw = len(((players[0]).get("gameweeks")) or []) or 6
    _gws3 = ((players[0] if players else {}).get("gameweeks")) or []
    window = _window_label(meta or {}, _gws3, n_gw)

    karki = sorted(players, key=lambda p: -(p.get("xp_horizon_total") or 0))[:8]
    best_rows = "".join(
        "<tr>"
        f'<td class="n">{i + 1}</td>'
        f'<td>{escape(str(p["web_name"]))}{_no_history_flag(p)}</td>'
        f'<td class="m-hide">{escape(str(p.get("pos", "")))}</td>'
        f'<td class="n">{float(p.get("price") or 0):.1f}</td>'
        f'<td class="n m-hide">{float(p.get("owned_pct") or 0):.1f}%</td>'
        f'<td class="n hi">{float(p.get("xp_horizon_total") or 0):.1f}</td>'
        "</tr>"
        for i, p in enumerate(karki))

    osat = [
        f'<h2 id="best">{escape(nimi)} best players for {escape(window)}</h2>'
        '<div class="lb-wrap"><table class="lb">'
        '<thead><tr><th class="n">#</th><th>Player</th>'
        '<th class="m-hide">Pos</th><th class="n">Price</th>'
        '<th class="n m-hide">Owned</th>'
        f'<th class="n">{n_gw}GW xP</th></tr></thead>'
        f"<tbody>{best_rows}</tbody></table></div>"
    ]

    sp = _set_piece_rows(players)
    if sp:
        osat.append(
            '<h2 id="set-pieces">Set-piece takers</h2>'
            '<div class="lb-wrap"><table class="lb">'
            "<thead><tr><th>Situation</th><th>Order</th></tr></thead>"
            f"<tbody>{sp}</tbody></table></div>"
            # 🔴 16.8: edellinen versio sanoi etta nama pelaajat "all start
            # from the same default". Se on epatosi: PROMOTED_PRIOR_TIERS
            # antaa kolme eri arvoa (0.38 / 0.16 / 0.096) sen mukaan monesko
            # kallein pelaaja on klubinsa positioryhmassa. Lause selitti
            # samat luvut vaaralla syylla ja piilotti sen etta luku ON
            # roolin luenta, karkea mutta mitattu (Brier +13,8 %).
            '<p class="note">? = no Premier League games yet, so the start '
            "probability comes from where the player sits in his club's price "
            "order rather than from anything he has done here. Players on the "
            "same rung get the same number.</p>"
            '<p class="note">The number is the order FPL publishes, so 1 is '
            "first in line. An empty situation means FPL has not published an "
            "order for it, which is not the same as nobody taking them. "
            "Pre-season there are a lot of blanks.</p>")

    xi, n_xi, xi_valitut = _xi_rows(players)
    if xi:
        osat.append(
            '<h2 id="xi">Predicted XI</h2>'
            '<div class="lb-wrap"><table class="lb">'
            '<thead><tr><th>Player</th><th class="m-hide">Pos</th>'
            '<th class="n">Price</th><th class="n">Start</th></tr></thead>'
            f"<tbody>{xi}</tbody></table></div>"
            '<p class="note">This table answers one question: who starts. '
            "Projected points for the same players are in GoalIQ Premium, "
            "along with the tools that use them. "
            "Start is our projected chance of starting, not a "
            "lineup leak. We do not watch press conferences. The shape is the "
            "highest-probability starter at each position, so it will not "
            "always match the manager's formation.</p>"
            # 🔴 16.8: kaksi rajoitetta jotka lukija nakee ITSE sivulta, joten
            # ne on parempi sanoa kuin antaa hanen loytaa. Kumpikaan ei
            # kerro suuntaa: emme tieda kumpaan suuntaan luku on vaarassa.
            '<p class="note">Two things this table gets wrong in a way worth '
            "knowing. A player who missed most of last season is read as a "
            "rotation player, because the estimate leans on the minutes he "
            "actually played and it cannot tell an injury from a benching. "
            "Those names carry a ! here. And the shape is fixed, so a club "
            "that plays five in midfield will always have one real starter "
            "pushed out of this eleven.</p>"
            + _xi_omissions(players, xi_valitut))

    conf = ((meta or {}).get("team_confidence") or {}).get("teams", {}).get(nimi)
    if conf and conf.get("note"):
        osat.append(f'<h2 id="squad">Squad turnover</h2>'
                    f'<p>{escape(str(conf["note"]))}</p>')

    title = f"{nimi} FPL {escape(window)}: best players, set-piece takers, predicted XI | GoalIQ"
    lead = karki[0]
    desc = (
        f"{nimi}'s best FPL picks for {window} by projected points, who takes "
        f"their penalties and corners, and our predicted XI with start "
        f"probabilities. {lead['web_name']} leads on "
        f"{float(lead.get('xp_horizon_total') or 0):.1f} xP. Free, no sign-in."
    )
    hero = (
        f"<h1>{escape(nimi)}: best players, set pieces and a predicted XI</h1>"
        f'<p class="lede">Everything on this page comes from our own match '
        f"model over {escape(window)}. "
        f"{escape(str(lead['web_name']))} leads the squad on "
        f"{float(lead.get('xp_horizon_total') or 0):.1f} projected points. "
        "Free, no sign-in, rebuilt every few hours.</p>"
    )
    body = (
        f"{_kit_defs([short])}"
        + _club_switcher(slug, saatavilla or {slug})
        + _share_row(f"{nimi} FPL {window}: best players, set pieces, XI", url)
        + "".join(osat)
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def render_predicted_lineups(xp: dict, now: datetime) -> str | None:
    """Kaikkien seurojen Model Predicted XI yhdella sivulla.

    MIKSI (15.8.2026, Villen tilaus). Kilpailijalla on yksi "Predicted
    Lineups" -tyokalu; meilla sama data oli olemassa mutta hajallaan 20
    seurasivulla, eli sita ei voinut selata eika loytaa yhdesta paikasta.

    🔴 NIMI ON "MODEL PREDICTED XI" EIKA "PREDICTED LINEUPS". Ero ei ole
    kosmeettinen. FFScoutin ja Roguen kokoonpanot nojaavat IHMISIIN:
    lehdistotilaisuudet, toimittajat, viime hetken tiedot. Meidan XI on
    mallin arvio aloitustodennakoisyyksista. Jos kutsuisimme sita samalla
    nimella, lupaisimme scout-tason tietoa jota meilla ei ole — ja se on
    tasan se virhe joka on tanaan jo kahdesti maksanut julkaisun.

    Vastineeksi annamme sen luvun jota HEILLA ei ole rivilla: kunkin
    pelaajan aloitustodennakoisyys prosenttina. Arvaus ilman lukua on
    mielipide; luku on tarkistettavissa jalkikateen.
    """
    meta = xp.get("meta") or {}
    players = xp.get("players") or []
    if not meta.get("available") or not players:
        return None
    per_club: dict[str, list[dict]] = {}
    for pl in players:
        s = pl.get("team_short")
        if s:
            per_club.setdefault(s, []).append(pl)

    lohkot = []
    n_klubia = 0
    for short, ryhma in sorted(per_club.items()):
        if short not in CLUB_SLUGS or len(ryhma) < 8:
            continue
        rivit, n, _ = _xi_rows(ryhma)
        if not rivit:
            continue
        n_klubia += 1
        slug = CLUB_SLUGS[short]
        lohkot.append(
            f'<h2 id="{slug}">{escape(str(ryhma[0].get("team") or short))}</h2>'
            '<div class="lb-wrap"><table class="lb">'
            '<thead><tr><th>Player</th><th class="m-hide">Pos</th>'
            '<th class="n">Price</th><th class="n">Start</th></tr></thead>'
            f"<tbody>{rivit}</tbody></table></div>"
            f'<p class="note"><a href="/fpl/club/{slug}">'
            # Sisempi lainausmerkki on HIPSU, ei kaksoislainaus. Sama merkki
            # f-stringin sisalla on laillinen vasta 3.12:sta (PEP 701), ja
            # CI ajaa 3.11:ta -> tama oli SyntaxError joka kaatoi KOKO
            # tests.yml-ajon 15.8 asti. Paikallisesti se ei nakynyt, koska
            # tama kone ajaa 3.14:aa.
            f"{escape(str(ryhma[0].get('team') or short))} club page &#9656;</a></p>"
        )
    if not lohkot:
        return None

    url = f"{BASE}/fpl/predicted-lineups"
    title = "Model Predicted XI for every Premier League club | GoalIQ"
    desc = (
        "The eleven our model expects to start for all 20 Premier League "
        "clubs, with each player's chance of starting. Not a lineup leak: "
        "these are projections from minutes history, not press conferences. "
        "Free, no sign-in."
    )
    hero = (
        "<h1>Model Predicted XI</h1>"
        '<p class="lede">The eleven our model expects to start at every club, '
        "with each player's projected chance of starting next to his name. "
        "This is a projection from minutes history, not a lineup leak. We do "
        "not watch press conferences, and when a manager surprises everyone "
        "this table will be wrong with him.</p>"
    )
    body = (
        f'<p class="note"><strong>{n_klubia} clubs</strong>. Start is the '
        "model's projected chance that the player is in the starting eleven, "
        "shown as a percentage so you can weigh it yourself. The shape is the "
        "highest-probability starter at each position, so it will not always "
        "match the manager's formation.</p>"
        + "".join(lohkot)
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def render_club_pages(xp: dict, now: datetime) -> list[str]:
    """Kirjoita jokaisen seuran sivu. Palauttaa kirjoitetut slugit."""
    meta = xp.get("meta") or {}
    players = xp.get("players") or []
    if not meta.get("available") or not players:
        return []
    per_club: dict[str, list[dict]] = {}
    for p in players:
        s = p.get("team_short")
        if s:
            per_club.setdefault(s, []).append(p)
    CLUB_DIR.mkdir(parents=True, exist_ok=True)
    # Laske ensin MITKA sivut syntyvat, jotta valitsin voi linkittaa vain
    # niihin. Sama kynnys kuin renderoijassa (alle 8 pelaajaa -> ei sivua).
    saatavilla = {
        CLUB_SLUGS[s] for s, g in per_club.items()
        if s in CLUB_SLUGS and len(g) >= 8
    }
    tehdyt = []
    for short, ryhma in sorted(per_club.items()):
        page = render_club_page(short, ryhma, meta, now, saatavilla)
        if not page:
            continue
        (CLUB_DIR / f"{CLUB_SLUGS[short]}.html").write_text(page, encoding="utf-8")
        tehdyt.append(CLUB_SLUGS[short])
    return tehdyt


def render_expected_points(xp: dict, now: datetime) -> str | None:
    """Koko xP-lista ilmaiseksi, ilman kirjautumista (9.8.2026).

    MIKSI TAMA SIVU ON OLEMASSA: postasimme X:aan ja Blueskyyn xP-lukuja
    ("Bruno 34.1 xP, No.1 midfielder") ja linkitimme /fpl/stats-sivulle, jossa
    on RAAKADATAA (laukaukset, xG) eika xP:ta lainkaan. Villen huomio 9.8:
    lupasimme numeron ja toimitimme jotain muuta. Ilmaista xP-listaa ei ollut
    millaan pinnalla — model-xi nayttaa 11 pelaajaa ja best-captain karjen,
    mutta rankattua listaa ei.

    Sivu on myos ainoa Reddit-kelpoinen kohde xP-sisallolle: r/FantasyPL:n
    saanto 9 poistaa linkit sivustoihin jotka vaativat rekisteroitymisen
    tiedon nakemiseen.

    VAPAA/PREMIUM-RAJA: lista on sisaltoa, tyokalut ovat tuote. Ranking nakyy
    kokonaan ilmaiseksi; rate-my-team, siirtosuunnittelija, kapteenirankkeri
    ja watchlist pysyvat premiumina. Sama peruste kuin /fpl/stats-rajassa:
    puolustettavuus, ei kustannus.

    Sarakevalinta on tahallinen: xP/90 (vauhti) ja xMins (peliaika) ERIKSEEN,
    koska niiden sekoittaminen on juuri se virhe joka korjattiin 9.8. Lukija
    nakee itse kumpi ajaa lukua.
    """
    meta = xp.get("meta") or {}
    players = xp.get("players") or []
    if not meta.get("available") or not players:
        return None

    rows = sorted(players, key=lambda p: -(p.get("xp_horizon_total") or 0))
    n_gw = len(rows[0].get("gameweeks") or []) or 6
    # 🔴 KIERROSNUMEROT, EI "next N". Ks. yllä: `next_gameweek` on kesken
    # oleva kierros, joten "next 6" luetaan seuraavaksi kuudeksi ja se on
    # kokonaisen kierroksen verran vaarin heti kun kierros on pelattu.
    dl_gw = meta.get("deadline_gameweek")
    next_gw = meta.get("next_gameweek")
    in_progress = (isinstance(dl_gw, int) and isinstance(next_gw, int)
                   and dl_gw > next_gw)
    esikausi = str(meta.get("caveat_code") or "").endswith(".preseason")
    _gws2 = ((players[0] if players else {}).get("gameweeks")) or []
    window = _window_label(meta, _gws2, n_gw)
    url = f"{BASE}/fpl/expected-points"
    # 21.8 (portti): "every player ranked" saa esiintya vain top-100-
    # rajauksen kanssa samassa lauseessa — ilmaissivu nayttaa tasan 100
    # rivia koko projektiosta, ei jokaista pelaajaa.
    title = (f"FPL Expected Points: Top 100 Players by xP "
             f"({window}) | GoalIQ")
    lead = rows[0]
    desc = (
        f"Every FPL player ranked by expected points over {window}; "
        f"the top 100 of the full projection shown free, no "
        f"sign-in. {lead['web_name']} leads on "
        f"{lead['xp_horizon_total']:.1f} xP. Scoring rate and minutes shown "
        f"separately."
    )

    top3 = "".join(
        '<div class="stat">'
        f'<b>{escape(r["web_name"])}</b>'
        f'<span>#{i + 1} · {escape(r["team_short"])} · '
        f'{r["xp_horizon_total"]:.1f} xP · {r["price"]:.1f}m</span></div>'
        for i, r in enumerate(rows[:3])
    )

    trows = "".join(
        "<tr>"
        f'<td class="n">{i + 1}</td>'
        f'<td>{escape(r["web_name"])}</td>'
        f'<td class="tm">{_kit_svg(r["team_short"])}'
        f'<span>{escape(r["team_short"])}</span>{_tflag_html(r)}</td>'
        # 15.8: pos ja price ilman m-hidea, kuten otsikotkin. Suodatin lukee
        # naita soluja, joten piilotettuina se suodattaisi nakymattomalla
        # perusteella.
        f'<td>{escape(r["pos"])}</td>'
        f'<td class="n">{r["price"]:.1f}</td>'
        f'<td class="n hi">{r["xp_horizon_total"]:.1f}</td>'
        f'<td class="n m-hide">{(r.get("xp_per_gw") or 0):.2f}</td>'
        f'<td class="n">{(r.get("xp_per_90") or 0):.2f}</td>'
        f'<td class="n">{(r.get("p_start") or 0) * 100:.0f}</td>'
        f'<td class="n m-hide">{(r.get("xmins") or 0):.0f}</td>'
        f'<td class="n m-hide">{(r.get("owned_pct") or 0):.1f}</td>'
        "</tr>"
        # Sama 100 rivin DOM-rajaus kuin xg-leadersissa; koko lista on
        # nakyvissa positiosuodattimen kautta appissa/premiumissa.
        for i, r in enumerate(rows[:100])
    )
    kitdefs = _kit_defs(p.get("team_short") for p in rows[:100])
    # Jakokortti PALVELIMEN riveilta, samasta `rows`-listasta kuin taulukko.
    # Teksti on julkaisutarkistajan hyvaksyma (ajo 2): kierrosnumerot eivat
    # "next 6" (koska next_gameweek on KESKEN oleva kierros, joten "next 6"
    # luetaan seuraavaksi kuudeksi), esikausivaraus kun mallin metassa on
    # `caveat_code`, ja tarkistusreitti footNotessa.
    kortti = _card_spec_attr(
        title="TOP 10 BY EXPECTED POINTS",
        subtitle=(f"{window}, pre-season baselines from last season, "
                  f"GoalIQ match model" if esikausi
                  else f"{window}, GoalIQ match model"),
        mid_label="PRICE", value_label=f"{n_gw}GW xP",
        foot="the full top 100 is free on goaliq.app/fpl/expected-points",
        # 🔴 PAIVAMAARA. Portti (24.8): sivu sanoo omin sanoin "These pages
        # rebuild every few hours, so a row can differ from the one you saw
        # this morning", ja builderin oma kirjaus 22.8 mittasi liikkeen
        # kesken ottelun (B.Fernandes GW-xP 5,76 -> 5,95 yhden ajon aikana).
        # Paivaamaton kuva luvusta jonka sivu itse sanoo liikkuvan
        # tunneittain on sama vika kuin pistekortilla, vain vahvempana -
        # ja "pre-season" on kortilla ehdoton vaikka sivu kvalifioi sen.
        # Eri runko kuin kortti 1:lla: sama runko perakkain on tunnusmerkki.
        # 🔴 EI TILAVAITETTA IKKUNAN ALKUPAASTA. Ensimmainen versio sanoi
        # "GW{n} still running", ja portti mittasi miksi se harhauttaa:
        # rankkausluku on GW1-6, ja GW1:sta oli 9/10 ottelua pelattu eli
        # 16,7 % luvusta on ottelu jonka tulos on jo kirjoissa. "Still
        # running" on kirjaimellisesti tosi mutta kytkee lukijan ikkunan
        # alkuun ja lupaa etta se on edessa. Se olisi lisaksi vanhentunut
        # tunneissa. Paivamaara ja "rows move" kantavat saman varauksen
        # ilman tilavaitetta, ja ne pysyvat tosina kaikissa tiloissa.
        foot2=(f"As of {now.strftime('%d %b').lstrip('0')}. "
               "Rows move on every rebuild, not betting advice"),
        rows=[{"rank": i + 1, "name": r["web_name"], "team": r["team_short"],
               "tag": r.get("pos") or "", "mid": ("%.1f" % (r.get("price") or 0)),
               "value": ("%.1f" % (r.get("xp_horizon_total") or 0))}
              for i, r in enumerate(rows[:10])],
        file_name="goaliq-expected-points.png")
    table = (
        f'<div class="lb-wrap"><table class="lb"{kortti}>'
        "<thead><tr>"
        '<th class="n">#</th><th>Player</th><th>Team</th>'
        # 15.8: Pos ja Price EIVAT ole enaa m-hide. Ne ovat suodattimen
        # kaksi ulottuvuutta, ja piilotettuina suodatin olisi sokea juuri
        # silla laitteella jolla suurin osa lukijoista tulee. Sama puute
        # esti julkaisutarkistajaa verifioimasta hintavaitetta puhelimella.
        '<th>Pos</th><th class="n">Price</th>'
        f'<th class="n">{n_gw}GW xP</th>'
        '<th class="n m-hide">xP/GW</th><th class="n">xP/90</th>'
        '<th class="n">Start%</th>'
        '<th class="n m-hide">xMins</th><th class="n m-hide">Own%</th>'
        "</tr></thead>"
        f"<tbody>{trows}</tbody></table></div>"
    )
    hero = (
        "<h1>FPL expected points, top 100 players ranked</h1>"
        '<p class="lede">What our match model projects each player to score '
        f"over {window}, shown here for the top 100 of the "
        f"full {len(rows)}-player projection. Scoring rate and expected "
        "minutes are shown separately, so you can see which one is driving "
        "the number. Free, no sign-in, rebuilt every few hours.</p>"
    )
    # 22.8 (Villen havainto): xP liikkuu kesken kierroksen, koska malli lukee
    # FPL:n live-syotetta. Mitattu samana paivana: B.Fernandes xmins 85,6 ->
    # 88,4 ja GW-xP 5,76 -> 5,95 yhden ajon aikana, kesken hanen ottelunsa.
    # Sivu ei sanonut sita, joten luku muuttui lukijan silmissa ilman syyta.
    # Rivi renderoityy VAIN kesken kierroksen (deadline mennyt mutta otteluita
    # jaljella) — ehto on datassa, ei kellonajassa, eika rivi siis jaa
    # roikkumaan kierrosten valiin.

    # Eri runko kuin SPA:n vastaavalla rivilla (portti 22.8): sama lause
    # sanatarkasti kahdella pinnalla on templaattitunnusmerkki. Tassa:
    # tila -> mekanismi (because) -> tahti. "not finished" eika "is being
    # played", koska GW:n ottelupaivien valissa on monen tunnin taukoja.
    live_note = (
        f'<p class="note"><strong>Gameweek {next_gw} is not finished.</strong> '
        "Expected minutes climb once a player has kicked off, because the "
        "model reads FPL's own match data. These pages rebuild every few "
        "hours, so a row can differ from the one you saw this morning.</p>"
    ) if in_progress else ""
    body = (
        f'<div class="stat-row">{top3}</div>'
        f"{live_note}"
        f"<h2>Top 100 by expected points (of {len(rows)} players)</h2>"
        # Selitys taulukon ALLE, ei ylle (9.8): ensimmainen versio tyonsi 237
        # sanaa datan eteen, eli X:sta tulija joutui vierittamaan kaksi
        # ruudullista mobiilissa paastakseen siihen lukuun joka hanelle
        # luvattiin. Sivun tyo on antaa luku ensin ja selittaa sitten.
        # 21.8 (portti B3): xP/GW-sarake on selitettava — ilman tata mikaan
        # ei kerro lukijalle ettei se ole se per-GW-luku jota Premium myy.
        '<p class="note">'
        f"Ranked by total xP over {window}. <em>xP/GW</em> "
        f"is that total divided by {n_gw}, not a single-gameweek projection. "
        "<em>xP/90</em> is the scoring rate, <em>Start%</em> is how likely "
        "he is to start, <em>xMins</em> combines the two.</p>"
        + _share_button()
        + f"{kitdefs}{table}"
        + SHARE_CARD_JS.replace("__CARD_ROWS_FN__", "function(){return null;}")
        + _tflag_note(xp, rows[:100], rows) +
        '<p class="note"><strong>Start% near 50 means the model is split.'
        "</strong> Those totals are a bet on team news, not a settled "
        "projection. A keeper on 51% is not a 45-minute keeper.</p>"
        # 10.8: mitattu harha julki (Villen valinta C). Nelja korjausyritysta
        # havisi, viimeisin ristiinvalidoitu kalibrointi kaikilla varianteilla,
        # joten lukua EI sadeta. Sama vaste kuin siirtosokeudessa: kerro se.
        #
        # 19.8: luku EI ole enaa kovakoodattu, ks. _minutes_caveat(). Rivilla
        # luki "about 14 minutes lower", ja se oli peraisin
        # calibrate_preseason_minutes.py:n sarakkeesta "karki >=75 min siirtyy"
        # (affine -13.9) — se kertoo kuinka paljon KALIBROINTI siirtaisi
        # karkea, ei kuinka paljon priori ylipredikoi. Suoraan mitattuna
        # 80+ ylipredikointi on kolmen kesan keskiarvona noin 10 minuuttia.
        + (_minutes_caveat() if _preseason_basis(meta) else "")
        # 16.8: sokea piste sanottu ääneen. Villen päätös oli ettei vahti
        # kysy esikaudesta, joten rajoite kirjataan näkyviin siellä missä
        # luku esitetään. Laukaiseva tapaus 15.8: João Pedro teki kaksi
        # esikauden maalia eikä lukumme liikkunut lainkaan, ja olin
        # kirjoittamassa siitä X-vastausta.
        + (('<p class="note"><strong>Start% does not read pre-season.</strong> '
            "It comes from last season's minutes and FPL's own availability "
            "flags, and for players with no Premier League history yet, from "
            "how they are priced in the squad. A player who has looked like a "
            "new first choice in friendlies barely moves this number until "
            "league minutes start to build up.</p>")
           if _preseason_basis(meta) else "")
        + '<p class="note">This ranking is free and needs no account. The tools '
        "built on top of it, rate my team, the transfer planner, the captain "
        "ranker and your watchlist, are part of GoalIQ Premium.</p>"
        + f"{UPSELL}{_cta()}"
        + f'<p class="note">Updated {now.strftime("%d %b %Y")} · '
        + f'{escape(str(meta.get("caveat") or ""))[:300]} · {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def _data_now(xp: dict | None) -> datetime:
    """Sivujen "Updated"-leima + JSON-LD:n dateModified DATAN iästä, ei
    ajohetkestä (STALE-UPDATED-LABEL). 22.8-cron-katkossa jokainen alasivu
    sanoi "Updated 22 Aug 2026" vaikka data oli 21.8 15:24 -ajosta — sivu ei
    saa väittää tuoreutta jota datalla ei ole, ja cron-korjaus ei poista
    mekanismia (leima valehtelisi taas seuraavassa katkossa). Kaikki sivut
    rakentuvat samasta refresh-nipusta, joten xP-metan aikaleima edustaa
    nippua. Fallback ajohetkeen jos metaa ei ole (fail-open: parempi tuore
    leima kuin kaatunut build)."""
    ts = ((xp or {}).get("meta") or {}).get("generated_at")
    if ts:
        try:
            d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except ValueError:
            pass
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# /fpl/points - toteutuneet pisteet vs kierroksen alla jaadytetty ennuste
# ---------------------------------------------------------------------------
# MIKSI (Villen tilaus 23.8): *"erillinen lista kaikkien pelaajien fpl
# pisteist eroteltuna defconit ja kaikki mahollinen"*.
#
# EROTTAJA EI OLE TAULUKKO VAAN VIEREINEN SARAKE. Raakaluvut ovat ilmaisia
# kaikkialla (kirjattu: raakaluvut ilmaiseksi, malli maksaa), ja pelkka
# pistetaulukko olisi kymmenes kopio samasta datasta. Mutta **mita malli
# ennusti ENNEN kierrosta vs mita tapahtui, pelaajakohtaisesti ja julkisesti
# logattuna** on sama puolustettava asset kuin ottelu-track-record - eika
# sita ole kenellakaan muulla.
#
# xP-SARAKE ON JAADYTETTY, EI ELAVA. `data/fpl_xp_frozen/gw{n}.json`
# kirjoitetaan deadlinella ja on immutable. Elava xP liikkuu kesken ja
# jalkeen kierroksen kohti toteumaa (mitattu 22.8: Gabriel 5.78 -> 5.14,
# B.Fernandes 5.70 -> 4.74), joten sen vertaaminen toteumaan nayttaisi mallin
# tarkempana kuin se oli. Sama korjaus kuin mobiilin Model vs actual -listassa.
#
# PUUTTUVA RIVI ON TOTUUS. `player-gw.json` kantaa rivin vain pelaajalle jolla
# on pelattu ottelu. Nolla olisi vaite ("pelasi eika saanut pisteita"),
# puuttuminen on tosiasia ("ei ole viela pelannut").
#
# EI RIIPPUVUUTTA data/raw/fpl:aan: tama builderi ajetaan MYOS
# accuracy-log.yml:ssa, jossa FPL-cachea ei ole. Molemmat lahteet ovat
# committoituja artefakteja.
POINTS_COLS = [
    ("g", "G", "Goals scored"),
    ("a", "A", "Assists"),
    ("dc", "DC", "Defensive contribution actions (the DefCon stat)"),
    ("cs", "CS", "Clean sheet"),
    ("bps", "BPS", "Bonus points system score"),
    ("bonus", "B", "Bonus points awarded"),
    ("xg", "xG", "Expected goals in the match"),
    ("xa", "xA", "Expected assists in the match"),
]


def _gw_still_running(gw: int) -> bool:
    """Onko kierros gw yha kesken? Luetaan komittoidusta xp-artefaktista.

    🔴 EI BOOTSTRAPISTA. Tama builderi ajetaan MYOS accuracy-log.yml:ssa jossa
    `data/raw/fpl` ei ole olemassa, joten FPL:n oma `event.finished` ei ole
    kaytettavissa. `fpl_xp_projections.json`:n `next_gameweek` kertoo saman:
    se on kesken olevan kierroksen numero ja kasvaa vasta kun kierros on ohi.
    Mitattu 24.8: `next_gameweek 1`, `deadline_gameweek 2` = GW1 kesken.

    🔴 MITTAA OTTELUT, EI BONUSVAHVISTUSTA. `next_gameweek` on
    `min(gw | not fixture.finished)` (build_fpl_xp.py:634), joten se kaantyy
    VIIMEISEN OTTELUN VIHELLYKSEEN - tunteja ennen kuin FPL vahvistaa
    bonukset (`data_checked`). Talle varaukselle on siis ikkuna jossa se on
    jo pudonnut vaikka pisteet voivat yha liikkua.

    Siksi kortin footNote2 kantaa AINA paivamaaran ("as of 24 Aug") eika vain
    "not final" -lippua: paivamaara on tosi molemmissa tiloissa ja rajaa
    lukijan odotuksen ilman etta se nojaa tahan mittariin. Alkuperainen
    perustelu nojasi `data_checked`iin jota tama funktio ei lue, ja portti
    kiinnitti sen 24.8 - sama luokka kuin "selitys nimeaa vaaran mekanismin".

    Tuntematon tila palautetaan keskeneraisena: liikaa varausta on halvempaa
    kuin liian vahan.
    """
    xp = _load(XP_PATH) or {}
    nxt = ((xp.get("meta") or {}).get("next_gameweek"))
    if nxt is None:
        return True
    try:
        return int(nxt) <= int(gw)
    except (TypeError, ValueError):
        return True


def _ennen(a: str, b: str) -> bool:
    """Onko aikaleima a aidosti ennen b:ta? False jos kumpaakaan ei jasennы.

    Olemassa jotta kortti ei vaita aikajarjestysta jota se ei ole mitannut.
    Portti blokkasi 24.8 kahdesti perakkain tasan taman takia: ensin
    "frozen at the deadline" (epatosi), sitten "before the GW1 deadline"
    (tosi mutta mittaamaton). Molemmat aikaleimat ovat gw{n}.json:n metassa.
    """
    def parse(x: str):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        except ValueError:
            return None
    pa, pb = parse(a), parse(b)
    if not (pa and pb):
        return False
    try:
        return pa < pb
    except TypeError:
        # Naivi vs aware -vertailu heittaa. Tanaan molemmissa on Z, mutta
        # jos toinen menettaa vyohykkeen, builderi ei saa kaatua - kortti
        # jattaa relaation sanomatta, mika on koko funktion tarkoitus.
        return False


def _pvm_lyhyt(iso: str) -> str:
    """'2026-08-20T12:33:43Z' -> '20 Aug'. Tyhja jos ei jasenny."""
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d %b").lstrip("0")
    except ValueError:
        return ""


def _latest_frozen_gw(gw: int) -> dict | None:
    """Kierroksen deadlinella jaadytetty xP-lumikuva, tai None."""
    return _load(XP_FROZEN_DIR / f"gw{gw}.json")


def render_points(player_gw: dict, now: datetime) -> str | None:
    meta = (player_gw or {}).get("meta") or {}
    players = (player_gw or {}).get("players") or {}
    gw = meta.get("max_gw")
    cols = meta.get("cols") or []
    if not players or not gw or "pts" not in cols:
        return None
    ci = {c: i for i, c in enumerate(cols)}

    frozen = _latest_frozen_gw(int(gw)) or {}
    fmeta = frozen.get("meta") or {}
    fro = {int(r["id"]): r for r in (frozen.get("players") or []) if r.get("id")}

    rivit = []
    ilman_ennustetta = 0
    for pid, gws in players.items():
        try:
            key = int(pid)
        except (TypeError, ValueError):
            continue
        rivi = next((r for r in gws if r and r[ci["gw"]] == gw), None)
        if rivi is None:
            continue
        f = fro.get(key)
        if not f:
            # Pelasi, mutta deadline-lumikuvassa ei ole hanta (esim. siirto
            # kierroksen aikana). Rivi jaa pois - ilman jaadytettya ennustetta
            # sarakeparilla ei ole kulmaa - mutta MAARA sanotaan aaneen alla.
            # Hiljainen pudotus tekisi taulusta vajaan ilman etta kukaan nakee.
            ilman_ennustetta += 1
            continue
        pts = rivi[ci["pts"]]
        xp = float(f.get("xp") or 0.0)
        rivit.append({
            "id": key,
            "name": str(f.get("web_name") or ""),
            "team": str(f.get("team_short") or ""),
            "pos": str(f.get("pos") or ""),
            "price": float(f.get("price") or 0.0),
            "xp": round(xp, 2),
            "pts": pts,
            "diff": round(pts - xp, 2),
            "mins": rivi[ci["mins"]] if "mins" in ci else 0,
            **{k: rivi[ci[k]] for k, _, _ in POINTS_COLS if k in ci},
        })
    if not rivit:
        return None
    rivit.sort(key=lambda r: (-r["pts"], -r["xp"]))

    # Mallin oma tarkkuus tassa kierroksessa. Lasketaan riveista, EI
    # kovakoodata: luku vanhenisi hiljaa seuraavassa kierroksessa.
    n = len(rivit)
    mae = round(sum(abs(r["diff"]) for r in rivit) / n, 2)
    yli = sum(1 for r in rivit if r["diff"] > 0)

    def solu(r: dict) -> str:
        merkki = "pos" if r["diff"] > 0 else ("neg" if r["diff"] < 0 else "")
        return (
            "<tr>"
            f'<td>{escape(r["name"])}</td>'
            f'<td>{escape(r["team"])}</td>'
            f'<td class="m-hide">{escape(r["pos"])}</td>'
            f'<td class="n m-hide">{r["price"]:.1f}</td>'
            f'<td class="n">{r["xp"]:.2f}</td>'
            f'<td class="n"><strong>{r["pts"]}</strong></td>'
            f'<td class="n {merkki}">{r["diff"]:+.2f}</td>'
            f'<td class="n m-hide">{r["mins"]}</td>'
            + "".join(f'<td class="n m-hide">{r.get(k, "")}</td>'
                      for k, _, _ in POINTS_COLS)
            + "</tr>"
        )

    thead = (
        '<tr><th data-k="name">Player</th><th data-k="team">Team</th>'
        '<th class="m-hide" data-k="pos">Pos</th>'
        '<th class="n m-hide" data-k="price">Price</th>'
        # 24.8: luki "frozen at the GW deadline". Jaadytys tapahtuu ENNEN
        # deadlinea, ei sen hetkella: gw1.json sanoo frozen_at
        # 2026-08-20T12:33 ja deadline 2026-08-21T17:30, eli 29 h ennen.
        # Vaite oli ilmaispinnalla ja se on sivun oma ydinlupaus, joten se
        # korjataan vaikka jakokortti otettiin pois.
        '<th class="n" data-k="xp" title="The projection frozen before the '
        'GW deadline, before a ball was kicked">xP</th>'
        '<th class="n" data-k="pts" title="Actual FPL points scored">Pts</th>'
        '<th class="n" data-k="diff" title="Actual minus projected">Diff</th>'
        '<th class="n m-hide" data-k="mins">Mins</th>'
        + "".join(f'<th class="n m-hide" data-k="{k}" title="{escape(t)}">{lbl}</th>'
                  for k, lbl, t in POINTS_COLS)
        + "</tr>"
    )
    # Jakokortin varaukset samasta datasta kuin sivun omat luvut.
    kesken = _gw_still_running(int(gw))
    jaadytetty = _pvm_lyhyt(str(fmeta.get("frozen_at") or ""))
    ennen_dl = _ennen(str(fmeta.get("frozen_at") or ""),
                      str(fmeta.get("deadline") or ""))
    kortti = _card_spec_attr(
        # 🔴 KAIKKI PORTIN LOYDOKSET SISALLA (4 kierrosta):
        # "SO FAR" koska kierros voi olla kesken · relaatio "before the
        # deadline" MITATAAN (`_ennen`) eika kirjoiteta, koska "frozen at the
        # deadline" oli epatosi 29 tunnilla · MAE-ankkuri, koska kortin
        # kymmenen rivia ovat rakenteellisesti mallin suurimmat alilyonnit ja
        # sivu ankkuroi ne heti taulukon ylla · EI "all", koska n on
        # VERRATTUJEN maara eika pelanneiden · paivamaara AINA, koska
        # kesken-mittari putoaa viimeiseen vihellykseen mutta bonukset
        # vahvistuvat myohemmin.
        title=(f"GW{gw} SO FAR: PROJECTED VS ACTUAL" if kesken
               else f"GW{gw}: PROJECTED VS ACTUAL"),
        subtitle=(f"xP frozen {jaadytetty}, before the deadline. "
                  f"Points from the FPL API."
                  if jaadytetty and ennen_dl else
                  f"xP frozen {jaadytetty}. Points from the FPL API."
                  if jaadytetty else
                  "xP frozen before kickoff. Points from the FPL API."),
        mid_label="xP", value_label="PTS",
        foot=f"model MAE {mae} pts across {n} compared players",
        foot2=((f"GW{gw} not final. " if kesken else "")
               + f"As of {now.strftime('%d %b').lstrip('0')}. "
               + "goaliq.app/fpl/points, not betting advice"),
        # Muotoilu tehdaan tassa, ei JS:ssa: luvut ja niiden esitys kuuluvat
        # samaan paikkaan. (Sisakkaiset samat lainausmerkit f-stringissa ovat
        # syntaksivirhe alle 3.12:ssa, siksi erillinen muuttuja.)
        rows=[{"rank": i + 1, "name": r["name"], "team": r["team"],
               "tag": r["pos"], "mid": ("%.2f" % r["xp"]),
               "value": str(r["pts"])}
              for i, r in enumerate(rivit[:10])],
        file_name=f"goaliq-points-gw{gw}.png")
    table = (f'<div class="lb-wrap"><table class="lb"{kortti}>'
             f"<thead>{thead}</thead><tbody>"
             + "".join(solu(r) for r in rivit) + "</tbody></table></div>")

    url = f"{BASE}/fpl/points"
    title = f"FPL Points GW{gw}: Projected vs Actual, Every Player | GoalIQ"
    desc = (
        f"Every player's actual Gameweek {gw} FPL points next to the expected "
        f"points GoalIQ's model published before the deadline, with goals, "
        f"assists, defensive contribution (DefCon), bonus, BPS, xG and xA "
        f"broken out. {n} players. Free, no sign-in."
    )
    frozen_at = fmeta.get("frozen_at") or ""
    deadline = fmeta.get("deadline") or ""
    hero = (
        f"<h1>FPL points GW{gw}: projected vs actual</h1>"
        '<p class="lede">The xP column is the projection this model published '
        "<strong>before the deadline</strong>, not a number recalculated "
        "afterwards. Actual points come from the official FPL API. Both are "
        "on the same row so you can check the model instead of taking its "
        "word for it.</p>"
    )
    body = (
        f'<div class="card"><p class="lede" style="margin:0">'
        # 24.8: luki "the {n} players who have played". n on VERRATTUJEN maara,
        # ei pelanneiden - ja sama sivu kumoaa sen kolme kappaletta alempana
        # ("N players who did play are also left out"). Sama kvanttori
        # korjattiin ensin korttiin ja sivu jai; nyt molemmat.
        f"Across the {n} players in both the projection and the results, "
        f"the model's mean absolute "
        f"error is <strong>{mae} points</strong>. It was too low on "
        f"{yli} of them and too high on {n - yli}."
        f"</p></div>"
        + _share_button()
        + f"{table}"
        + SHARE_CARD_JS.replace("__CARD_ROWS_FN__", "function(){return null;}")
        + '<p class="note">A player with no row has not played yet, so the '
        + "table grows as each match finishes. A missing row is not a zero."
        + (f" {ilman_ennustetta} player"
           + ("s" if ilman_ennustetta != 1 else "")
           + " who did play "
           + ("are" if ilman_ennustetta != 1 else "is")
           + " also left out, because "
           + ("they were" if ilman_ennustetta != 1 else "he was")
           + " not in the projection frozen before the deadline and there is "
             "nothing to compare the points against."
           if ilman_ennustetta else "")
        + "</p>"
        f"{UPSELL}{_cta()}"
        f'<p class="note">Projection frozen {escape(str(frozen_at)[:16])} UTC '
        f"for the GW{gw} deadline {escape(str(deadline)[:16])} UTC. "
        f'Updated {now.strftime("%d %b %Y")}. {DISCLAIMER}</p>'
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "url": url, "description": desc,
        "isPartOf": {"@id": f"{BASE}/#organization"},
        "dateModified": now.strftime("%Y-%m-%d"),
    }]
    return _page(title, desc, url, hero, body, jsonld)


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    built = []

    xp = _load(XP_PATH)
    now = _data_now(xp)
    if xp:
        page = render_captain(xp, now)
        if page:
            (OUT_DIR / "best-captain.html").write_text(page, encoding="utf-8")
            built.append("best-captain")
        # 26.7: Model XI kenttagrafiikkana (sama XI-heuristiikka kuin
        # rate-my-teamin benchmark) — antaa myos beat-the-model-liigalle kodin.
        page = render_model_xi(xp, now)
        if page:
            (OUT_DIR / "model-xi.html").write_text(page, encoding="utf-8")
            built.append("model-xi")
        # 9.8: koko xP-lista ilmaiseksi — ks. render_expected_points-docstring.
        page = render_expected_points(xp, now)
        if page:
            (OUT_DIR / "expected-points.html").write_text(page, encoding="utf-8")
            built.append("expected-points")
        # 14.8: jakokortin tarkistuskohde — ks. render_club_best-docstring.
        page = render_club_best(xp, now)
        if page:
            (OUT_DIR / "club-best.html").write_text(page, encoding="utf-8")
            built.append("club-best")
        # 15.8: team news kaanteisena - ks. render_team_news-docstring.
        page = render_team_news(xp, now)
        if page:
            (OUT_DIR / "team-news.html").write_text(page, encoding="utf-8")
            built.append("team-news")

    if xp:
        clubs = render_club_pages(xp, now)
        if clubs:
            built.append(f"club x{len(clubs)}")
        sivu = render_predicted_lineups(xp, now)
        if sivu:
            (OUT_DIR / "predicted-lineups.html").write_text(sivu, encoding="utf-8")
            built.append("predicted-lineups")

    # FPL-PLAYER-POINTS-TABLE: molemmat lahteet ovat committoituja
    # artefakteja, joten tama rakentuu myos accuracy-logissa (ei FPL-cachea).
    pgw = _load(PLAYER_GW_PATH)
    if pgw:
        page = render_points(pgw, now)
        if page:
            (OUT_DIR / "points.html").write_text(page, encoding="utf-8")
            built.append("points")

    mv = _load(MINUTES_VALIDATION_PATH)
    if mv:
        sivu = render_minutes_accuracy(mv, now)
        if sivu:
            (OUT_DIR / "minutes-accuracy.html").write_text(
                sivu, encoding="utf-8")
            built.append("minutes-accuracy")

    notes_doc = _load(NOTES_PATH)
    if notes_doc:
        page = render_notes(notes_doc, now)
        if page:
            (OUT_DIR / "notes.html").write_text(page, encoding="utf-8")
            built.append("notes")
        NOTE_DIR.mkdir(parents=True, exist_ok=True)
        n_art = 0
        for muistio in notes_doc.get("notes") or []:
            sivu = render_note_page(muistio, now)
            if sivu:
                (NOTE_DIR / f"{muistio['slug']}.html").write_text(
                    sivu, encoding="utf-8")
                n_art += 1
        if n_art:
            built.append(f"note x{n_art}")

    diff = _fetch_differentials()
    if diff:
        page = render_differentials(diff, now)
        if page:
            (OUT_DIR / "differentials.html").write_text(page, encoding="utf-8")
            built.append("differentials")

    pw = _load(PW_PATH)
    if pw is not None:
        (OUT_DIR / "price-changes.html").write_text(
            render_price_changes(pw, now), encoding="utf-8")
        built.append("price-changes")

    # #128/#120: xG- + DefCon-leaders-sivut (nightly-cache; puuttuva data →
    # sivut ohitetaan, vanhat jäävät voimaan)
    leaders = _load(LEADERS_PATH)
    if leaders:
        page = render_xg_leaders(leaders, now)
        if page:
            (OUT_DIR / "xg-leaders.html").write_text(page, encoding="utf-8")
            built.append("xg-leaders")
        page = render_defcon(leaders, now)
        if page:
            (OUT_DIR / "defcon.html").write_text(page, encoding="utf-8")
            built.append("defcon")

    # 8.8 STATS-ZONE: oma nightly-JSON (build_fpl_stats.py). Puuttuva data →
    # sivu ohitetaan ja vanha jää voimaan, sama konventio kuin muut.
    stats = _load(STATS_PATH)
    if stats:
        page = render_stats(stats, now)
        if page:
            (OUT_DIR / "stats.html").write_text(page, encoding="utf-8")
            built.append("stats")

    defence = _load(DEFENCE_PATH)
    if defence:
        page = render_defence(defence, now)
        if page:
            (OUT_DIR / "defence.html").write_text(page, encoding="utf-8")
            built.append("defence")

    today = now.strftime("%Y-%m-%d")
    # Seurasivut ovat alihakemistossa, joten `glob("*.html")` EI nae niita.
    # Ilman tata 20 sivua olisi olemassa mutta poissa sitemapista — sama
    # orpous joka mitattiin 15.8 `expected-points`- ja `team-news`-sivuilla.
    urlit = [(f"{BASE}/fpl/{f.stem}", today, "daily", "0.7")
             for f in sorted(OUT_DIR.glob("*.html"))]
    urlit += [(f"{BASE}/fpl/club/{f.stem}", today, "daily", "0.6")
              for f in sorted(CLUB_DIR.glob("*.html"))]
    # Artikkelisivut ovat myos alihakemistossa: sama orpousansa kuin
    # seurasivuilla, ja juuri niihin ulkoiset linkit osoittavat.
    urlit += [(f"{BASE}/fpl/note/{f.stem}", today, "weekly", "0.7")
              for f in sorted(NOTE_DIR.glob("*.html"))]
    write_urlset(SITEMAP_FPL_PATH, urlit)
    print(f"LONGTAIL: {', '.join(built) or 'ei sivuja (data puuttuu)'} "
          f"(sitemap-fpl.xml: {len(urlit)} URL:ia)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
