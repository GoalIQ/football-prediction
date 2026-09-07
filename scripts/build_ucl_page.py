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
# 🔴 KAKSI ERI KYSYMYSTA, EIKA NIITA SAA PINOTA SAMAAN PYLVAASEEN.
# `not_in_squad` on seuran rekisterointipaatos, ei kuntoasia: klubi voi
# jattaa yhdeksan pelaajaa listalta ja olla taysin terve. Kun molemmat
# olivat samassa kaaviossa, pylvaan pituus ja rivin sija mittasivat eri
# asiaa.
TOIMITTAVA = ["injured", "suspended", "doubtful"]
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
        f'<a href="/privacy.html">Privacy</a><br>'
        # 🔴 EROTTAUTUMINEN ON OLTAVA SIELLA MISSA LUKIJA ON. `spl.html`
        # kantaa vastaavan rivin sivulla itsellaan; /ucl-sivuilla se oli
        # vain etusivun kaistalla ja llms.txt:ssa, eli ei silla sivulla
        # joka nimeaa UEFAn ja UCL Fantasyn.
        "GoalIQ is an independent data tool and is not affiliated with, "
        "endorsed by, or paid by UEFA, the UCL Fantasy game, or any club."
        f"<br>{DISCLAIMER}</footer>\n"
        "</main>\n" + MOBILE_COLS_JS + "</body>\n</html>\n")


# --- kaaviot ---------------------------------------------------------------

def kaavio_omistus(pelaajat: list[dict]) -> str:
    """Omistus x hinta, vari = positio.

    Rajaus on tahallinen ja sanotaan sivulla aaneen. Mitattu: kaikki
    `owned_pct`-arvot ovat kokonaislukuja, joten "yli 1 %" on kaytannossa
    "2 % tai enemman" - copy sanoo sen niin, koska muuten lukija odottaa
    naissa myos 1,5 %:n omistuksia. Rajauksen ulkopuolelle jaa 990
    pelaajaa jotka olisivat yksi musta palkki alalaidassa.
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
        otsikko="Ownership by price, players owned by 2% or more")


def kaavio_saatavuus(pelaajat: list[dict], teams: list[dict]) -> str:
    """Loukkaantumiset, pelikiellot ja epavarmat klubeittain.

    🔴 KAHDESTI KORJATTU, JA ENSIMMAINEN KORJAUS TEKI TOISEN VIAN.

    v1 lajitteli poissaolojen SUMMALLA. Mitattu renderoidysta kuvasta:
    karjessa oli Real Madrid siksi etta se jattaa eniten pelaajia
    rekisteroimatta, ei siksi etta silla olisi eniten loukkaantumisia.

    v2 lajitteli loukkaantumisilla mutta piirsi silti `not_in_squad`in
    pylvaaseen. Julkaisuportti mittasi lopputuloksen: MCI ja AVL olivat
    10 pelaajan pylvailla sijoilla 11-12 ja BAR 4 pelaajan pylvaalla
    sijalla 13. Jarjestys oli oikein, mutta PITUUS mittasi eri asiaa, ja
    lukija lukee pituuden. Kaavio nayttaa jarjestamattomalta.

    v3 (tama): kaavio vastaa yhteen kysymykseen. Pituus, jarjestys ja
    otsikko ovat kaikki I+S+D. Rekisteroimatta jattaminen on eri kysymys
    ja se saa oman lauseensa runkotekstissa.

    Suodatinta EI ole: kaikki 18 klubia joilla on yksikin tapaus
    mahtuvat, joten otsikko kattaa 49/49 pelaajaa. Edellinen versio
    sanoi "Players unavailable by club" ja naytti 111 pelaajaa 171:sta
    ja 16 klubia 32:sta (muisti: honest-data-labels).
    """
    per_klubi: dict[str, Counter] = defaultdict(Counter)
    for p in pelaajat:
        if p["status"] in TOIMITTAVA:
            per_klubi[p["team_code"]][p["status"]] += 1
    rivit = sorted(per_klubi.items(), key=lambda kv: -sum(kv[1].values()))
    return sc.stacked_bars(
        rivit=[(k, dict(v)) for k, v in rivit],
        sarjat=[(s, POISSA_VARI[s], STATUS_SANA[s]) for s in TOIMITTAVA],
        otsikko="Injuries, suspensions and doubts by club",
        x_label="Players injured, suspended or doubtful")


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


def _feed_leima(doc: dict) -> str:
    """Milloin luvut ovat UEFAlta. Ei rakennusaika (ks. ingest_ucl)."""
    iso = (doc.get("meta") or {}).get("feed_updated_utc")
    if not iso:
        return "an unknown time"
    return dt.datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M UTC")


def _tyhja_selite(doc: dict, kentta: str) -> str:
    """🔴 SELITE KULKEE TAULUKON MUKANA, EI SIVUN MUKANA.

    Julkaisuportti mittasi: `/ucl/prices`-sivulla oli 762 tyhjaa solua ja
    `/ucl/team-news`illa 104, molemmat ilman selitysta - selittava kappale
    oli vain hubilla. Tyhja on oikein nollan sijaan, mutta selittamaton
    tyhja sarakkeessa "Pts (last season)" on arvoitus juuri silla sivulla
    jolle haku tuo lukijan.
    """
    if kentta != "prev_season_points":
        return ""
    n = sum(1 for p in doc["players"] if not p.get("prev_season_minutes"))
    return (f"<p>The points column is blank for the {n} "
            "players who logged no UCL minutes last season, most of them "
            "at clubs that were not in the competition.</p>")


def _pelaajarivit(pelaajat: list[dict], kentta: str) -> list[list[str]]:
    ulos = []
    for p in pelaajat:
        tila = STATUS_SANA.get(p["status"], p["status"])
        ulos.append([
            escape(p["name"] or ""), escape(p["team_code"] or ""), p["pos"],
            f'{p["price"]:g}', f'{p["owned_pct"]:g}%',
            # 🔴 TYHJA, EI NOLLA, kun pelaaja ei ollut kilpailussa viime
            # kaudella. Mitattu: 762 pelaajaa 1 162:sta, ja kymmenella
            # klubilla se koskee jokaista pelaajaa. "0" luetaan huonoksi
            # kaudeksi (muisti: nolla-ei-ole-sama-kuin-ei-tietoa).
            (str(vaiheet.arvo(p, kentta))
             if kentta == "points" or p.get("prev_season_minutes") else ""),
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
        # 🔴 NOLLA EI OLE SAMA KUIN EI TIETOA. Mitattu: 762 pelaajalla
        # 1 162:sta `prev_season_points` on 0, ja KAIKILLA niista myos
        # `prev_season_minutes` on 0 - he eivat pelanneet kilpailussa.
        # Nolla solussa luetaan huonoksi kaudeksi, ei puuttumiseksi, joten
        # solu jatetaan tyhjaksi ja syy kerrotaan tassa.
        tyhjia = sum(1 for p in P if not p.get("prev_season_minutes"))
        perusta = (
            "<p>No matchday of this season has been played, so nothing on "
            "this page is a figure from it. The points column is last "
            "season's UCL total, which is what the feed carries at this "
            f"point. It's blank for the {tyhjia} players who logged no UCL "
            "minutes last season, most of them at clubs that were not in "
            "the competition. Everything else on this page is current.</p>")
    else:
        perusta = (
            "<p>Points and minutes on this page are from the current UCL "
            "season.</p>")

    kartoitus = sorted(P, key=lambda p: -p["owned_pct"])[:20]

    # Jokainen luku johdetaan datasta. Kasin kirjoitettu luku vanhenee
    # hiljaa, ja "a dozen" oli jo vaarin: suurin todellinen oli 9.
    kalleimmat = {pos: max(p["price"] for p in P if p["pos"] == pos)
                  for pos in ("GK", "DEF", "MID", "FWD")}
    nis = sum(1 for p in P if p["status"] == "not_in_squad")
    nis_max = max(Counter(p["team_code"] for p in P
                          if p["status"] == "not_in_squad").values())
    toimittava_n = sum(1 for p in P if p["status"] in TOIMITTAVA)
    # Mitattu: kaikki `owned_pct`-arvot ovat kokonaislukuja, joten
    # "yli 1 %" tarkoittaa kaytannossa 2 % tai enemman. Sanotaan se niin.
    mukana = sum(1 for p in P if p["owned_pct"] > 1.0)

    body = (
        f"{perusta}"
        "<h2>Where the money is</h2>"
        f"<p>The {mukana} players owned by 2% or more, plotted by price "
        f"against ownership. The other {len(P) - mukana} sit at 1% or "
        "below and would be one dark block along the bottom.</p>"
        f"{kaavio_omistus(P)}"
        "<h2>What each position costs</h2>"
        f"<p>Goalkeepers and defenders stop at {kalleimmat['DEF']:g}m. "
        f"Midfielders run to {kalleimmat['MID']:g}m and forwards to "
        f"{kalleimmat['FWD']:g}m, so every expensive slot in a squad is a "
        "midfielder or a forward.</p>"
        f"{kaavio_hinnat(P)}"
        "<h2>Who is flagged</h2>"
        f"<p>{toimittava_n} players are flagged injured, suspended or "
        "doubtful in the official feed, and "
        f"the chart counts those three. A further {nis} are not in their "
        "club's registered squad, which is a squad decision rather than a "
        f"fitness one: the largest group at any one club is {nis_max}, and "
        'those clubs can still be fully fit. The <a href="/ucl/team-news">'
        f"full list</a> has all {toimittava_n + nis}.</p>"
        f"{kaavio_saatavuus(P, doc['teams'])}"
        "<h2>Most owned</h2>"
        + _taulukko(["Player", "Club", "Pos", "Price", "Owned", sarake,
                     "Status"], _pelaajarivit(kartoitus, kentta))
        + '<p><a href="/ucl/prices">Full list of all '
        f'{len(P)} players</a> · '
        '<a href="/ucl/team-news">Squad availability by club</a></p>')

    # 🔴 EI KADENSSILUPAUSTA, VAAN AIKALEIMA. "Updated every six hours" on
    # vaite jota lukija ei voi tarkistaa mistaan, ja oma mittauksemme
    # (27.8 alkaen) sanoo GitHubin ajastimen olleen 5-12 h myohassa.
    # Aikaleima on tarkistettava, kadenssi ei.
    leima = _feed_leima(doc)

    # 🔴 DEADLINE ON AINOA LUKU JOKA VANHENEE ILMAN ETTA DATA MUUTTUU.
    # Hinta, omistus ja lippu ovat tosia niin kauan kuin artefakti on
    # tuore; deadline lakkaa olemasta seuraava KELLOSTA, ei syotteesta.
    # Se laskettiin buildhetkella ja luetaan lukuhetkella, eli sivu
    # vaittaa mennytta deadlinea seuraavaksi kunnes seuraava ajo korjaa
    # sen. Kaikki kahdeksan deadlinea ovat jo artefaktissa, joten oikea
    # kierros voidaan valita lukijan kellosta.
    #
    # Ilman JS:aa jaa buildin arvo, eli tama ei voi olla huonompi kuin
    # aiempi tila. Sama lukija (`vaiheet.seuraava_kierros`) maarittelee
    # staattisen arvon, joten kaksi polkua eivat voi olla eri mielta
    # samasta hetkesta.
    dls = [{"md": k["md"], "iso": k["deadline_utc"],
            "txt": _fmt_deadline(k["deadline_utc"])}
           for k in sorted(doc.get("matchdays") or [],
                           key=lambda x: x.get("md") or 0)
           if k.get("deadline_utc")]
    dl_js = (
        "<script>(function(){var D=" + json.dumps(dls, ensure_ascii=False)
        + ',e=document.getElementById("ucl-dl"),n=Date.now(),i;'
        "if(!e){return;}"
        "for(i=0;i<D.length;i++){if(Date.parse(D[i].iso)>n){"
        'e.textContent="Matchday "+D[i].md+" deadline is "+D[i].txt+".";'
        "return;}}"
        'e.textContent="No deadline ahead: the league phase is over.";'
        "})();</script>")

    hero = ("<h1>UCL Fantasy: prices, ownership and squad news</h1>"
            f'<p class="lede"><span id="ucl-dl">{escape(dl)}</span> Free, '
            "no login. Read from the official UEFA feed, last update "
            f"{leima}.</p>")
    body += dl_js

    return _page(
        "UCL Fantasy prices, ownership and squad availability | GoalIQ",
        "Free UCL Fantasy data: what every player costs, how many managers "
        "own them, and which players carry a flag. No login.",
        f"{BASE}/ucl", hero, body,
        _jsonld("UCL Fantasy tools",
                "Free UCL Fantasy prices, ownership and squad availability.",
                f"{BASE}/ucl"))


def sivu_hinnat(doc: dict, nyt: dt.datetime) -> str:
    P = sorted(doc["players"], key=lambda p: (-p["owned_pct"], -p["price"]))
    kentta, sarake = vaiheet.pistekentta(doc, nyt)
    mukana = sum(1 for p in doc["players"] if p["owned_pct"] > 1.0)
    body = (
        f"<p>All {len(P)} players in the UCL Fantasy game, sorted by "
        "ownership. Click a column heading to sort.</p>"
        # 🔴 RAJAUS ON SANOTTAVA NAKYVASSA TEKSTISSA. `svg_charts.otsikko`
        # menee vain `aria-label`iin, joten kaavion oma otsikko EI ole
        # nakevalle lukijalle olemassa. Ilman tata sivun nakyva copy lupasi
        # 1 162 ja kaavio piirsi 172 (muisti: honest-data-labels).
        f"<p>The chart shows the {mukana} players owned by 2% or more. "
        "The feed reports ownership in whole percent, so everyone else "
        "sits at 1% or 0%. The table below has all of them.</p>"
        f"{kaavio_omistus(doc['players'])}"
        + _tyhja_selite(doc, kentta)
        + _taulukko(["Player", "Club", "Pos", "Price", "Owned", sarake,
                     "Status"], _pelaajarivit(P, kentta)))
    hero = ("<h1>UCL Fantasy prices and ownership</h1>"
            f'<p class="lede">All {len(P)} players in the game, with what '
            "the feed says they cost and how many managers own them. "
            f"Last update {_feed_leima(doc)}.</p>")
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
    toimittava_n = sum(1 for p in P if p["status"] in TOIMITTAVA)
    body = (
        # 🔴 "CANNOT BE PICKED" ON YLIVAITE. Syotteessa on vain `pStatus`
        # -lippu (I/D/S/NIS), ei kenttaa valittavuudesta. Vain NIS
        # tarkoittaa varmasti ettei pelaajaa voi valita; loukkaantunut ja
        # epavarma ovat fantasypeleissa normaalisti valittavissa, ne ovat
        # lippuja. Emme voineet verifioida UEFAn omaa saantoa, joten
        # sanotaan se mita syote KANTAA.
        f"<p>{len(poissa)} of {len(P)} players carry a flag in the "
        f"official feed. The chart counts the {toimittava_n} flagged "
        "injured, suspended or doubtful. The table adds everyone left out "
        "of a registered squad, which is a club decision and not a "
        "fitness one.</p>"
        f"{kaavio_saatavuus(P, doc['teams'])}"
        + _tyhja_selite(doc, kentta)
        + _taulukko(["Player", "Club", "Pos", "Price", "Owned", sarake,
                     "Status"], _pelaajarivit(poissa, kentta)))
    hero = ("<h1>UCL Fantasy squad availability</h1>"
            f'<p class="lede">{len(poissa)} players are flagged in the '
            "official feed. Here is who, and at which club. Last update "
            f"{_feed_leima(doc)}.</p>")
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
