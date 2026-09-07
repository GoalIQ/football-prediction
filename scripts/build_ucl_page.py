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
    BASE, CSS, MOBILE_COLS_JS, POSTHOG_SNIPPET, TABLE_TOOLS_JS,
    _og_image, _social_meta, _strip_css_comments,
)
from src.models import ucl_phase as vaiheet  # noqa: E402
from src.viz import svg_charts as sc  # noqa: E402

DATA = ROOT / "data" / "ucl_fantasy.json"
OUT_DIR = ROOT / "ucl"

# ---------------------------------------------------------------------------
# 🔴 RAJAUS ON YHDESSA PAIKASSA JA SE MENEE JOKAISELLE SIVULLE ITSESTAAN
# (COPY-SYNC-AUDIT 7.9.2026, blokkaavat loydokset 1 ja 2, saanto 6a mek. 1).
#
# Mitattu 7.9: sivustolla on KAKSI eri "UCL"-tuotetta.
#   (a) ottelumalli, joka kattaa Champions Leaguen aidosti
#       (api.goaliq.app/api/fixtures?league=INT-Champions League -> 200,
#        MD1 8.9.2026), ja
#   (b) tama osio, joka on UEFAn UCL Fantasy -syotetta ILMAN mallia.
# Ero oli kirjattu TASMALLEEN yhdelle pinnalle, `llms.txt`:aan, joka on
# koneluettava. Yksikaan ihminen ei nahnyt sita. Samaan aikaan naiden
# sivujen footer ajoi jaettua `DISCLAIMER`ia, joka VAITTAA sivun luvut
# malliennusteiksi ("GoalIQ model predictions are statistical estimates").
#
# Rajaus ei siksi ole sivukohtaista copya vaan `_page()`n tuottama pakko:
# uusi UCL-sivu ei voi syntya ilman sita, koska se ei kulje sivun kirjoittajan
# muistin kautta. Sanamuoto on EHDOTON eika kausisidottu ("in any phase of the
# season") - kausisidottu perustelu vanhenee itsestaan, ja tasan niin kavi
# llms.txt:n alkuperaiselle lauseelle MD1:ssa (muisti: ehto-ei-vanhene-teksti-
# vanhenee).
# ---------------------------------------------------------------------------
# Kanoninen kielto. Tama merkkijono esiintyy sanatarkasti myos llms.txt:ssa,
# faq.html:ssa, index.html:ssa, predictions.html:ssa ja SPA:n Paywallissa.
EI_MALLIA = (
    "There is no expected points model for UCL Fantasy, in any phase of the "
    "season, and we do not publish one."
)

UCL_SCOPE = (
    "This section is prices, ownership and squad availability read from "
    "UEFA's own public UCL Fantasy feed. "
    # 🔴 SANATARKKA JA SAMA JOKA PINNALLA. Sama kielto viitena eri
    # sanamuotona on viisi eri vaitetta lukijalle ja viisi eri
    # korjauskohdetta meille (muisti: sama-vaite-monessa-sanamuodossa).
    # `tests/test_ucl_no_projection.py` pitaa tata literaalia sallittujen
    # listalla; uusi parafraasi ei paase listalle vahingossa.
    + EI_MALLIA
)

# 🔴 EI JAETTUA `DISCLAIMER`IA. Sen sanamuoto on "GoalIQ model predictions
# are statistical estimates", ja talla sivulla ei ole yhtaan mallin tuottamaa
# lukua. Vaara varauma on huonompi kuin ei varaumaa: se kertoo lukijalle etta
# nama luvut ovat meidan arvioitamme, kun ne ovat UEFAn syotetta.
UCL_DISCLAIMER = (
    "Every number on this page is read from UEFA's official UCL Fantasy "
    "feed. GoalIQ does not model or project UCL Fantasy points."
)

# Osion oma navigointi. Sivusopimus vaatii sisaantulevan linkin joka
# sivulle; nama ristiinlinkit ovat se paikka josta se tulee.
UCL_LINKS = [
    ("/ucl/", "UCL Fantasy"),
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
    # 🔴 VERTAILU ILMAN rstrip("/"): hakemistoindeksin canonical on
    # `/ucl/` ja alasivujen `/ucl/prices`. `rstrip` teki `/ucl/`:sta
    # `/ucl`:n eika osunut listaan, jolloin sivu olisi linkittanyt
    # itseensa.
    tama = canonical.replace(BASE, "")
    linkit = "".join(
        f'<a href="{h}">{escape(t)}</a>'
        for h, t in UCL_LINKS if h != tama)
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
        f'<div class="wrap hero">\n{hero}\n'
        f'<p class="note">{UCL_SCOPE}</p>\n</div>\n</header>\n'
        f'<main class="wrap content">\n{body}\n'
        f'<nav class="toolnav"><h2>UCL Fantasy</h2><div>{linkit}</div></nav>\n'
        '<footer>© 2026 GoalIQ · '
        '<a href="/predictions">Football predictions</a> · '
        '<a href="/fpl">Free FPL tools</a> · '
        f'<a href="/privacy">Privacy</a><br>'
        # 🔴 EROTTAUTUMINEN ON OLTAVA SIELLA MISSA LUKIJA ON. `spl.html`
        # kantaa vastaavan rivin sivulla itsellaan; /ucl-sivuilla se oli
        # vain etusivun kaistalla ja llms.txt:ssa, eli ei silla sivulla
        # joka nimeaa UEFAn ja UCL Fantasyn.
        "GoalIQ is an independent data tool and is not affiliated with, "
        "endorsed by, or paid by UEFA, the UCL Fantasy game, or any club."
        f"<br>{UCL_DISCLAIMER}</footer>\n"
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


def _feed_dt(doc: dict) -> dt.datetime | None:
    """Syotteen aikaleima datetimena. YKSI LUKIJA neljalle pinnalle.

    Nakyva leima, JSON-LD:n `dateModified`, sitemapin `lastmod` ja llms.txt
    kertovat kaikki saman asian: milloin luvut ovat UEFAlta. Jos jokainen
    laskisi sen itse, jokin niista lukisi ajohetkea (CLAUDE.md 6a,
    mekanismi 1; muisti: rakennusaika-artefaktissa).
    """
    iso = (doc.get("meta") or {}).get("feed_updated_utc")
    if not iso:
        return None
    try:
        return dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def _feed_iso(doc: dict) -> str | None:
    d = _feed_dt(doc)
    return d.isoformat() if d else None


def _feed_pvm(doc: dict) -> str | None:
    d = _feed_dt(doc)
    return d.date().isoformat() if d else None


def _feed_leima(doc: dict) -> str:
    """Milloin luvut ovat UEFAlta. Ei rakennusaika (ks. ingest_ucl).

    🔴 VARAUS KULKEE LEIMAN MUKANA, EI SIVUN MUKANA (7.9.2026).
    UEFA julkaisee kierroskohtaisen pelaajatiedoston vasta kun kierros
    aktivoituu, joten kierroksen lukkiutumisen ja seuraavan tiedoston
    julkaisun valissa `ingest_ucl` tarjoilee AIEMMAN kierroksen tiedoston
    (`players_matchday_is_fallback`). Silloin leima on tosi mutta
    harhaanjohtava yksin: se nayttaa tuoreelta luvulta kierrokselle jonka
    lukuja siina ei ole.

    Varaus on tassa funktiossa eika sivujen copyssa, koska sivuja on kolme
    ja neljas tulee myohemmin. Jokainen pinta joutuisi muistamaan saman
    lisayksen, ja joku unohtaisi (CLAUDE.md 6a, mekanismi 1). Nyt leimaa ei
    voi nayttaa ilman varausta.
    """
    meta = doc.get("meta") or {}
    d = _feed_dt(doc)
    if not d:
        return "an unknown time"
    leima = d.strftime("%d %b %Y, %H:%M UTC")
    if meta.get("players_matchday_is_fallback"):
        md = meta.get("players_matchday")
        return (f"{leima}, for matchday {md}, which is the most recent "
                "player file UEFA has published")
    return leima


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


def _otsikot(sarake: str) -> list[str]:
    """Taulukon sarakeotsikot. YKSI LUKIJA kolmelle sivulle JA Datasetille.

    🔴 OTSIKKO "Price" ON SOPIMUS JS:N KANSSA, EI VAPAA TEKSTI.
    `scripts/table_tools.py:116` etsii hintasarakkeen otsikon TASMALLEEN
    (`n===names[j]`, listalla 'price'/'cost'/'£'). Otsikon muuttaminen
    muotoon "Price (m)" olisi vienyt Max price -suodattimen aanettomasti,
    eli sama vikaluokka kuin keksitty CSS-luokka: validia HTML:aa, nolla
    toiminnallisuutta. Yksikko kuuluu siksi SOLUUN, ei otsikkoon.
    """
    return ["Player", "Club", "Pos", "Price", "Owned", sarake, "Status"]


def _pelaajarivit(pelaajat: list[dict], kentta: str) -> list[list[str]]:
    ulos = []
    for p in pelaajat:
        tila = STATUS_SANA.get(p["status"], p["status"])
        ulos.append([
            escape(p["name"] or ""), escape(p["team_code"] or ""), p["pos"],
            # 🔴 YKSIKKO SOLUUN (7.9.2026, GEO-auditointi). Solu oli paljas
            # "11" ja otsikko "Price", kun kaavion aria-label samalla
            # sivulla sanoi "11m". Sama luku kahdessa muodossa, ja poimija
            # lukee taulukon: kysymys "what does X cost in UCL Fantasy" sai
            # vastauksen "11". `table_tools.num()` riisuu ei-numeeriset
            # merkit ennen lajittelua ja suodatusta, joten "11m" lajittuu ja
            # suodattuu edelleen numerona.
            f'{p["price"]:g}m', f'{p["owned_pct"]:g}%',
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

#: Sivuston entiteettigraafin solmu. Se on MAARITELTY `index.html`:ssa
#: (Organization, @id .../#organization) ja kaikki muut osiot viittaavat
#: siihen. UCL-sivut kantoivat inline-objektin ilman @id:ta, eli ne olivat
#: graafin ulkopuolella: sama julkaisija esiintyi crawlerille eri
#: entiteettina kuin muualla sivustolla.
ORG_ID = f"{BASE}/#organization"

#: Sarakkeen yksikko `Dataset.variableMeasured`iin. Otsikko itse ei voi
#: kantaa yksikkoa (ks. `_otsikot`), joten koneluettava puoli kantaa sen.
SARAKE_YKSIKKO = {"Price": "million", "Owned": "percent"}


def _kausi(doc: dict) -> str:
    """`Dataset.temporalCoverage` artefaktin kierroksista, ei kovakoodattuna.

    Kausiluku joka kirjoitetaan kasin ("2026-27") on tosi tasan yhden
    kauden ajan eika mikaan huuda kun se lakkaa olemasta. Vali johdetaan
    niista deadlineista jotka artefaktissa OIKEASTI ovat, joten se kattaa
    tasan sen mita data kattaa.
    """
    pvm = sorted(
        d for d in (
            _iso_dt(k.get("deadline_utc"))
            for k in (doc.get("matchdays") or []))
        if d)
    return f"{pvm[0]:%Y-%m}/{pvm[-1]:%Y-%m}" if pvm else ""


def _iso_dt(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _muru(url: str, nimi: str | None) -> dict:
    """BreadcrumbList canonicalista. Hierarkia on olemassa, ei keksitty."""
    kohteet = [
        {"@type": "ListItem", "position": 1, "name": "GoalIQ", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "UCL Fantasy",
         "item": f"{BASE}/ucl/"},
    ]
    if nimi and url.rstrip("/") != f"{BASE}/ucl":
        kohteet.append({"@type": "ListItem", "position": 3, "name": nimi,
                        "item": url})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": kohteet}


def _dataset(doc: dict, nimi: str, kuvaus: str, url: str,
             sarake: str) -> dict:
    """Taulukon koneluettava puoli.

    🔴 SARAKKEET TULEVAT `_otsikot`ista, EIVAT OMASTA LISTASTA. Kaksi
    listaa samasta asiasta ajautuu erilleen: sarake vaihtuu kauden
    alkaessa (`ucl_phase.pistekentta`), ja kasin kirjoitettu
    `variableMeasured` jaisi lupaamaan viime kauden otsikkoa.
    """
    ld = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": nimi, "description": kuvaus, "url": url,
        "isAccessibleForFree": True,
        "creator": {"@id": ORG_ID},
        "publisher": {"@id": ORG_ID},
        "variableMeasured": [
            dict({"@type": "PropertyValue", "name": o},
                 **({"unitText": SARAKE_YKSIKKO[o]}
                    if o in SARAKE_YKSIKKO else {}))
            for o in _otsikot(sarake)
        ],
        "keywords": ["UCL Fantasy", "Champions League fantasy",
                     "UCL Fantasy prices", "UCL Fantasy ownership",
                     "UCL Fantasy team news"],
    }
    # Tyhjaa kenttaa ei kirjoiteta: puuttuva arvo on rehellisempi kuin
    # tyhja merkkijono, jonka lukija lukee mittaustuloksena.
    if _kausi(doc):
        ld["temporalCoverage"] = _kausi(doc)
    if _feed_iso(doc):
        ld["dateModified"] = _feed_iso(doc)
    return ld


def _faq_ld(parit: list[tuple[str, str]]) -> dict:
    """FAQPage SAMASTA listasta josta nakyva FAQ renderoidaan.

    🔴 EI ERILLISTA VASTAUSTEKSTIA. JSON-LD on julkisempi pinta kuin runko
    (crawlerit lainaavat sen sanatarkasti), ja tassa osiossa on jo kerran
    kaynyt niin etta korjattu vaite jai elamaan JSON-LD:hen. Kun molemmat
    pinnat lukevat saman listan, ne eivat voi olla eri mielta.
    """
    return {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": v}}
            for q, v in parit
        ],
    }


def _faq_html(parit: list[tuple[str, str]]) -> str:
    """Nakyva FAQ.

    🔴 `quote=False` EI OLE KOSMETIIKKAA. Oletusarvoinen `escape()` muuttaa
    heittomerkin muotoon `&#x27;`, ja `UCL_DISCLAIMER` sisaltaa sellaisen
    ("UEFA's official ... feed"). Escapattuna kanoninen literaali ei enaa
    tasmaa itseensa, joten `tests/test_ucl_no_projection.py` luki sen
    projektiovaitteeksi: sivu kantoi kiellon, mutta portti ei nahnyt sita
    kieltona. Teksti menee elementin sisalle eika attribuuttiin, joten
    lainausmerkkeja ei tarvitse escapata.
    """
    return ("<h2>Common questions</h2>" + "".join(
        f"<h3>{escape(q, quote=False)}</h3>"
        f"<p>{escape(v, quote=False)}</p>" for q, v in parit))


def _jsonld(nimi: str, kuvaus: str, url: str, doc: dict,
            murunimi: str | None = None, dataset: dict | None = None,
            faq: list[tuple[str, str]] | None = None) -> list[dict]:
    lohkot: list[dict] = [{
        "@context": "https://schema.org", "@type": "WebPage",
        "name": nimi, "description": kuvaus, "url": url,
        "isPartOf": {"@type": "WebSite", "name": "GoalIQ", "url": BASE,
                     "publisher": {"@id": ORG_ID}},
        "publisher": {"@id": ORG_ID},
    }]
    if _feed_iso(doc):
        # Datan iasta, ei ajohetkesta: cron-katkossa ajohetki vaittaisi
        # tuoreutta jota luvuilla ei ole (muisti: rakennusaika-artefaktissa).
        lohkot[0]["dateModified"] = _feed_iso(doc)
    lohkot.append(_muru(url, murunimi))
    if dataset:
        lohkot.append(dataset)
    if faq:
        lohkot.append(_faq_ld(faq))
    return lohkot


def _karki_lause(kartoitus: list[dict]) -> str:
    """Lainattava kärkilause omistustaulukon ylle.

    🔴 TAULUKON RIVI EI OLE LAUSE. Kysymykseen "most owned UCL Fantasy
    players" sivulla oli vastaus vain soluina: otsikko `Most owned` ja
    taulukko. Poimija joutuu paattelemaan sen taulukon rakenteesta, ja
    kielimalli lainaa lauseen. Luvut tulevat SAMASTA lajitellusta
    listasta kuin taulukko, joten ne eivat voi olla eri mielta.
    """
    if len(kartoitus) < 2:
        return ""
    a, b = kartoitus[0], kartoitus[1]
    # Tasapeli on mahdollinen: omistusluvut ovat kokonaislukuja, joten
    # "ahead of" olisi vaara vaite yhtasuurilla luvuilla.
    suhde = "level with" if a["owned_pct"] == b["owned_pct"] else "ahead of"
    return (f'<p>The most owned player in UCL Fantasy is '
            f'{escape(a["name"] or "")} ({escape(a["team"] or "")}, '
            f'{a["price"]:g}m) at {a["owned_pct"]:g}% ownership, {suhde} '
            f'{escape(b["name"] or "")} ({escape(b["team"] or "")}) at '
            f'{b["owned_pct"]:g}%.</p>')


def _faq(doc: dict, nyt: dt.datetime) -> list[tuple[str, str]]:
    """Hubin kysymysvastaavuus. Jokainen luku johdetaan artefaktista.

    🔴 VAIHESIDOTTU VASTAUS ON KIRJOITETTAVA VAIHEEN FUNKTIONA. Vastaus
    pistesarakkeesta on tosi vain esikaudella; kovakoodattuna se olisi
    vihrea siihen asti kun se lakkaa olemasta tosi (CLAUDE.md 6a,
    mekanismi 3). Sama lukija (`ucl_phase.vaihe`) paattaa sen kuin
    sarakeotsikon.
    """
    P = doc["players"]
    klubit = len(doc.get("teams") or [])
    kartoitus = sorted(P, key=lambda p: (-p["owned_pct"], -p["price"],
                                         p["name"] or ""))
    toimittava_n = sum(1 for p in P if p["status"] in TOIMITTAVA)
    nis = sum(1 for p in P if p["status"] == "not_in_squad")
    a, b = kartoitus[0], kartoitus[1]
    suhde = "level with" if a["owned_pct"] == b["owned_pct"] else "ahead of"
    pistelause = (
        "The points column shows last season's UCL total, which is what "
        "the feed carries before a matchday of this season is played, and "
        "the column heading says so."
        if vaiheet.vaihe(doc, nyt) == vaiheet.ESIKAUSI else
        "The points column shows this season's UCL total from the feed.")
    return [
        ("How many players are in UCL Fantasy?",
         f"The official UCL Fantasy game has {len(P)} players from "
         f"{klubit} clubs. GoalIQ lists every one of them with price, "
         "ownership, position and squad status at "
         "https://goaliq.app/ucl/prices. Free, no login."),
        ("Who is the most owned UCL Fantasy player?",
         f'{a["name"]} ({a["team"]}, {a["price"]:g}m) is owned by '
         f'{a["owned_pct"]:g}% of managers, {suhde} {b["name"]} '
         f'({b["team"]}) at {b["owned_pct"]:g}%. The figures come from '
         f"UEFA's own public feed, last update {_feed_leima(doc)}."),
        ("Which UCL Fantasy players are injured or suspended?",
         f"{toimittava_n} players carry an injury, suspension or doubt "
         f"flag in the official feed. A further {nis} are left out of "
         "their club's registered squad, which is a club decision and not "
         f"a fitness one, for {toimittava_n + nis} rows in total at "
         "https://goaliq.app/ucl/team-news."),
        # 🔴 KANONISET LITERAALIT, EI OMAA SANAMUOTOA. Ensimmainen versio
        # kysyi "Does GoalIQ project points for UCL Fantasy?" ja vastasi
        # omin sanoin. `tests/test_ucl_no_projection.py` kaatoi sen: kysymys
        # itse on projektiovaite kunnes se on luettu loppuun, ja kuudes
        # parafraasi samasta kiellosta on kuudes eri vaite lukijalle.
        # `UCL_DISCLAIMER` ja `EI_MALLIA` ovat ne merkkijonot jotka koko
        # sivusto kayttaa, ja vain vaihesidottu osa on oma.
        ("Are the UCL Fantasy numbers on this page GoalIQ estimates?",
         f"No. {UCL_DISCLAIMER} {EI_MALLIA} {pistelause}"),
        ("Is GoalIQ affiliated with UEFA?",
         "No. GoalIQ is an independent data tool and is not affiliated "
         "with, endorsed by, or paid by UEFA, the UCL Fantasy game, or "
         "any club. These pages read UEFA's own public UCL Fantasy feed "
         "and normalise it."),
    ]


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
        perusta = (
            "<p>No matchday of this season has been played, so nothing on "
            "this page is a figure from it. The points column is last "
            "season's UCL total, which is what the feed carries at this "
            "point. Everything else on this page is current.</p>")
    else:
        perusta = (
            "<p>Points and minutes on this page are from the current UCL "
            "season.</p>")

    # 🔴 YKSI LAJITTELU KAHDELLE PINNALLE. Taulukon karki ja sen ylla
    # oleva lainattava lause vastaavat samaan kysymykseen; kaksi erillista
    # `sorted`-kutsua olisivat voineet nimeta eri pelaajan tasapelissa.
    # Tasapeli katkaistaan deterministisesti, ei syotteen jarjestyksella.
    kartoitus = sorted(P, key=lambda p: (-p["owned_pct"], -p["price"],
                                         p["name"] or ""))

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
    faq = _faq(doc, nyt)

    body = (
        f"{perusta}"
        # 🔴 KAKSI ERI "UCL"-TUOTETTA, SANOTTUNA AANEEN (audit-rivi 2).
        # Ottelumalli kattaa Champions Leaguen aidosti: mitattu 7.9,
        # api.goaliq.app/api/fixtures?league=INT-Champions League -> 200, MD1
        # 8.9.2026, ja kilpailu on valittavissa seka SPA:ssa
        # (web/pro-spa/src/lib/leagues.ts:43) etta mobiilissa
        # (goaliq-app/lib/leagues.ts:158). Fantasypisteita se EI ennusta.
        # Linkki menee SPA:han eika /predictions-hubiin, koska hubilla ei ole
        # yhtaan CL-ottelusivua (mitattu: prediction-lokissa 0 CL-rivia), ja
        # linkki joka lupaa reitin jota ei ole on sama vika toisin pain.
        '<p class="note">GoalIQ also has a match model, and it does cover '
        "Champions League fixtures: win probability, expected goals and the "
        "most likely scorelines for one match, at "
        '<a href="https://pro.goaliq.app/">pro.goaliq.app</a>. That is a '
        "different product from this section. It reads a football match, not "
        "a fantasy squad, and it produces no UCL Fantasy points.</p>"
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
        + _karki_lause(kartoitus)
        + _tyhja_selite(doc, kentta)
        + _taulukko(_otsikot(sarake),
                    _pelaajarivit(kartoitus[:20], kentta))
        + '<p><a href="/ucl/prices">Full list of all '
        f'{len(P)} players</a> · '
        '<a href="/ucl/team-news">Squad availability by club</a></p>'
        + _faq_html(faq))

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

    # 🔴 HUBIN OTSIKKO OLI LASTENSA OTSIKOT YHTEEN LIIMATTUNA (audit 7.9):
    # "prices, ownership and squad availability" = "prices and ownership" +
    # "squad availability". Kolme sivua kilpaili samoista hauista. Hubin
    # otsikko nimeaa nyt TEHTAVAN (mita taalta saa) kuten `/fpl`:n
    # "Free FPL Tools", ja alasivut pitavat sisaltohakunsa.
    otsikko = "Free UCL Fantasy Tools: Player Prices, Ownership, Team News"
    kuvaus = (
        f"Free UCL Fantasy data on all {len(P)} players from "
        f"{len(doc.get('teams') or [])} clubs: price, ownership percentage "
        f"and squad status, with {toimittava_n + nis} players flagged or "
        "left out of a registered squad. No login.")
    return _page(
        f"{otsikko} | GoalIQ", kuvaus, f"{BASE}/ucl/", hero, body,
        _jsonld(
            "UCL Fantasy tools", kuvaus, f"{BASE}/ucl/", doc,
            dataset=_dataset(
                doc,
                "GoalIQ UCL Fantasy player prices, ownership and squad "
                "availability",
                f"Every player in the official UEFA Champions League "
                f"Fantasy game, {len(P)} of them across "
                f"{len(doc.get('teams') or [])} clubs, with price in "
                "millions, the share of managers who own them, position, "
                f"and the squad status the official feed reports. "
                f"{sarake} is the points column. Read from UEFA's own "
                "public feed and normalised. No projection is included.",
                f"{BASE}/ucl/", sarake),
            faq=faq))


def sivu_hinnat(doc: dict, nyt: dt.datetime) -> str:
    P = sorted(doc["players"], key=lambda p: (-p["owned_pct"], -p["price"]))
    kentta, sarake = vaiheet.pistekentta(doc, nyt)
    mukana = sum(1 for p in doc["players"] if p["owned_pct"] > 1.0)
    klubit = len(doc.get("teams") or [])
    kallein = max(doc["players"], key=lambda p: (p["price"], p["owned_pct"]))
    # 🔴 SISALTO-H2:T PUUTTUIVAT KOKONAAN (audit 7.9). Sivun ainoa H2 oli
    # alatunnisteen navigointi, eli kahden eri asian (kaavio, koko lista)
    # valilla ei ollut rakennetta jonka poimija tai ruudunlukija nakisi.
    body = (
        "<h2>Ownership against price</h2>"
        # 🔴 RAJAUS ON SANOTTAVA NAKYVASSA TEKSTISSA. `svg_charts.otsikko`
        # menee vain `aria-label`iin, joten kaavion oma otsikko EI ole
        # nakevalle lukijalle olemassa. Ilman tata sivun nakyva copy lupasi
        # 1 162 ja kaavio piirsi 172 (muisti: honest-data-labels).
        f"<p>The chart shows the {mukana} players owned by 2% or more. "
        "The feed reports ownership in whole percent, so everyone else "
        "sits at 1% or 0%. The table below has all of them.</p>"
        f"{kaavio_omistus(doc['players'])}"
        f"<h2>All {len(P)} players</h2>"
        f'<p>The most expensive player in UCL Fantasy is '
        f'{escape(kallein["name"] or "")} ({escape(kallein["team"] or "")}) '
        f'at {kallein["price"]:g}m. Every price on this page is in the '
        "millions the game budgets in. Sorted by ownership. Click a column "
        "heading to sort by anything else.</p>"
        + _tyhja_selite(doc, kentta)
        + _taulukko(_otsikot(sarake), _pelaajarivit(P, kentta)))
    hero = ("<h1>UCL Fantasy prices and ownership</h1>"
            f'<p class="lede">All {len(P)} players in the game, with what '
            "the feed says they cost and how many managers own them. "
            f"Last update {_feed_leima(doc)}.</p>")
    kuvaus = (
        f"All {len(P)} UCL Fantasy players from {klubit} clubs with price "
        "in millions, ownership percentage, position and squad status. "
        "Sortable, free, no login.")
    return _page(
        "UCL Fantasy prices and ownership, all players | GoalIQ",
        kuvaus, f"{BASE}/ucl/prices", hero, body,
        _jsonld(
            "UCL Fantasy prices and ownership", kuvaus,
            f"{BASE}/ucl/prices", doc, murunimi="Prices and ownership",
            dataset=_dataset(
                doc, "GoalIQ UCL Fantasy price and ownership table",
                f"Price in millions and ownership percentage for all "
                f"{len(P)} players in the official UEFA Champions League "
                f"Fantasy game, across {klubit} clubs, with position, "
                f"squad status and {sarake}. One row per player, sortable "
                "and filterable by position and maximum price. Read from "
                "UEFA's own public feed and normalised.",
                f"{BASE}/ucl/prices", sarake)))


def sivu_team_news(doc: dict, nyt: dt.datetime) -> str:
    P = doc["players"]
    kentta, sarake = vaiheet.pistekentta(doc, nyt)
    poissa = [p for p in P if p["status"] in POISSA]
    poissa.sort(key=lambda p: (POISSA.index(p["status"]), -p["owned_pct"]))
    toimittava_n = sum(1 for p in P if p["status"] in TOIMITTAVA)
    # Erittely lauseeksi, ei pelkiksi taulukkoriveiksi: kysymys "who is
    # injured in UCL Fantasy" sai vastaukseksi vain kokonaisluvun, ja
    # jokainen tilaluku oli olemassa vain soluina. Luvut lasketaan
    # `POISSA`-listasta, joten uusi tila ei voi jaada lauseesta pois.
    per_tila = Counter(p["status"] for p in poissa)
    erittely = ", ".join(
        f"{per_tila[s]} {STATUS_SANA[s].lower()}" for s in POISSA
        if per_tila[s])
    body = (
        "<h2>Flagged by club</h2>"
        # 🔴 "CANNOT BE PICKED" ON YLIVAITE. Syotteessa on vain `pStatus`
        # -lippu (I/D/S/NIS), ei kenttaa valittavuudesta. Vain NIS
        # tarkoittaa varmasti ettei pelaajaa voi valita; loukkaantunut ja
        # epavarma ovat fantasypeleissa normaalisti valittavissa, ne ovat
        # lippuja. Emme voineet verifioida UEFAn omaa saantoa, joten
        # sanotaan se mita syote KANTAA.
        f"<p>The chart counts the {toimittava_n} flagged "
        "injured, suspended or doubtful. The table adds everyone left out "
        "of a registered squad, which is a club decision and not a "
        f"fitness one, for {len(poissa)} rows in total.</p>"
        f"{kaavio_saatavuus(P, doc['teams'])}"
        f"<h2>Every flagged player</h2>"
        f"<p>The official feed flags {erittely}. The table lists all "
        f"{len(poissa)} in that order, most owned first inside each group. "
        "Click a column heading to sort by anything else.</p>"
        + _tyhja_selite(doc, kentta)
        + _taulukko(_otsikot(sarake), _pelaajarivit(poissa, kentta)))
    hero = ("<h1>UCL Fantasy squad availability</h1>"
            f'<p class="lede">{len(poissa)} players are flagged in the '
            "official feed. Here is who, and at which club. Last update "
            f"{_feed_leima(doc)}.</p>")
    kuvaus = (
        f"UCL Fantasy team news: {erittely}. Which players carry a flag in "
        "the official feed or are left out of a registered squad, by club. "
        "Free, no login.")
    return _page(
        "UCL Fantasy squad availability and team news | GoalIQ",
        kuvaus, f"{BASE}/ucl/team-news", hero, body,
        # 🔴 JSON-LD ON JULKISEMPI KUIN RUNKO. Korjasin "cannot be picked"
        # -yliväitteen nakyvasta tekstista mutta jatin sen tahan: Google ja
        # LLM-crawlerit lainaavat strukturoitua dataa sanatarkasti (muisti:
        # hedge-vain-nakyvassa-copyssa).
        _jsonld(
            "UCL Fantasy squad availability",
            "UCL Fantasy players carrying an injury, suspension or "
            "doubt flag in the official feed, or left out of a "
            "registered squad, by club.",
            f"{BASE}/ucl/team-news", doc, murunimi="Squad availability",
            dataset=_dataset(
                doc, "GoalIQ UCL Fantasy squad availability table",
                f"The {len(poissa)} players in the official UEFA Champions "
                f"League Fantasy game who carry a status flag in the feed "
                f"or are left out of a registered squad: {erittely}. Each "
                "row carries the club, position, price in millions, "
                f"ownership percentage, {sarake} and the status the feed "
                "reports. Read from UEFA's own public feed and normalised.",
                f"{BASE}/ucl/team-news", sarake)))


# --- sivun ulkopuoliset pinnat ---------------------------------------------
#
# 🔴 SIVU EI OLE OSION AINOA PINTA. Kolme UCL-riviä sitemapissa ja neljä
# llms.txt:ssä lisättiin 7.9 KASIN, eikä mikään päivittänyt niitä. Sivut
# vaihtuvat joka ajolla, joten `changefreq: daily` + jäätynyt `lastmod` on
# ristiriita joka opettaa crawlerin olemaan palaamatta, ja llms.txt:n
# UCL-osiossa ei ollut yhtään lukua jonka kielimalli voisi lainata.
#
# Molemmat kirjoitetaan nyt samasta artefaktista kuin sivut. Kirjoitus
# levylle ei kuitenkaan riita: `ucl-refresh.yml`:n `git add` -listalla on
# oltava molemmat tiedostot, muuten upsert ajaa joka kerta eika paady
# committiin (muisti: refresh-kirjoittaa-levylle-commit-lista-ratkaisee).

LLMS = ROOT / "llms.txt"

#: Sivukohtaiset sitemap-painot. Loc on sama kuin canonical, muuten
#: upsert lisaisi rinnakkaisen rivin eika paivittaisi olemassaolevaa.
SITEMAP_RIVIT = [
    (f"{BASE}/ucl/", "daily", "0.8"),
    (f"{BASE}/ucl/prices", "daily", "0.7"),
    (f"{BASE}/ucl/team-news", "daily", "0.7"),
]


def paivita_sitemap(doc: dict) -> bool:
    """UCL-rivien `lastmod` DATAN iasta, ei ajohetkesta.

    Ajohetki vaittaisi tuoreutta myos silloin kun ingest ei saanut UEFAlta
    uutta tiedostoa. `_upsert_sitemap_entry` on jo olemassa ja idempotentti
    (`build_fpl_page`), joten tassa ei kirjoiteta toista toteutusta samasta
    asiasta. Import on funktion sisalla: `build_ucl_page` on osion oma
    moduuli eika sen tuonti saa vetaa mukanaan koko FPL-builderia.
    """
    from scripts.build_fpl_page import (  # noqa: PLC0415
        SITEMAP_PATH, _upsert_sitemap_entry)

    pvm = _feed_pvm(doc)
    if not pvm or not SITEMAP_PATH.exists():
        return False
    xml = SITEMAP_PATH.read_text(encoding="utf-8")
    uusi = xml
    for loc, cf, pri in SITEMAP_RIVIT:
        uusi = _upsert_sitemap_entry(uusi, loc, pvm, cf, pri)
    if uusi != xml:
        SITEMAP_PATH.write_text(uusi, encoding="utf-8")
        return True
    return False


def llms_lohko(doc: dict) -> str:
    """llms.txt:n UCL-rivit artefaktin luvuista.

    Kasin kirjoitettu rivi lupasi "the full sortable list of all players"
    ilman yhtaan lukua: kysymykseen "how many players are in UCL Fantasy"
    lahdeluettelo ei vastannut, vaikka lahde oli kadessa. Sama ratkaisu
    kuin kasvumoottorilla (`build_prediction_pages.update_llms_txt`):
    generoidaan VAIN markkeriparin sisus, arvostelukyky jaa kasin.
    """
    P = doc["players"]
    klubit = len(doc.get("teams") or [])
    kierroksia = len([k for k in (doc.get("matchdays") or [])
                      if k.get("deadline_utc")])
    poissa = [p for p in P if p["status"] in POISSA]
    per_tila = Counter(p["status"] for p in poissa)
    erittely = ", ".join(f"{per_tila[s]} {STATUS_SANA[s].lower()}"
                         for s in POISSA if per_tila[s])
    return "\n".join([
        "",
        f"- [UCL Fantasy prices, ownership and squad news]({BASE}/ucl/): "
        f"all {len(P)} players in the official UCL Fantasy game across "
        f"{klubit} clubs, with price in millions, ownership percentage, "
        "position and squad status, plus the next of the "
        f"{kierroksia} league phase matchday deadlines in the feed. Charts "
        "show ownership against price, "
        "the price range per position, and injuries, suspensions and "
        "doubts by club. Completely free, no login.",
        f"- [UCL Fantasy prices and ownership]({BASE}/ucl/prices): the full "
        f"sortable list of all {len(P)} players with price in millions and "
        "ownership percentage, filterable by position and maximum price.",
        f"- [UCL Fantasy squad availability]({BASE}/ucl/team-news): the "
        f"{len(poissa)} players who are injured, suspended, doubtful or "
        f"left out of the registered squad, listed by club: {erittely}.",
        f"- Read from UEFA's own public feed, last update "
        f"{_feed_leima(doc)}.",
        "",
    ])


def paivita_llms_txt(doc: dict) -> bool:
    """Kirjoita markkeriparin sisus. Puuttuva markkeri -> False, ei kaato.

    Sama sopimus kuin kasvumoottorilla: datan refresh ei saa kuolla siihen
    etta joku on siirtanyt markkerit. Fail-closed puoli on testissa
    (`test_ucl_page.test_llms_txt_ucl_lohko_on_generoitu`), joka kaatuu jos
    markkeria ei ole tai jos lohko on jaanyt jalkeen artefaktista.
    """
    if not LLMS.exists():
        return False
    s = LLMS.read_text(encoding="utf-8")
    if "GEN:UCL-START" not in s:
        print("  VAROITUS: llms.txt:sta puuttuu GEN:UCL-markkeri")
        return False
    import re  # noqa: PLC0415
    uusi = re.sub(r"(<!-- GEN:UCL-START -->).*?(<!-- GEN:UCL-END -->)",
                  lambda m: m.group(1) + llms_lohko(doc) + m.group(2),
                  s, flags=re.S)
    if uusi != s:
        LLMS.write_text(uusi, encoding="utf-8")
        return True
    return False


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
    print(f"  sitemap-core.xml  {'paivitetty' if paivita_sitemap(doc) else 'ennallaan'}")
    print(f"  llms.txt          {'paivitetty' if paivita_llms_txt(doc) else 'ennallaan'}")
    print(f"ucl: {len(sivut)} sivua, vaihe={vaiheet.vaihe(doc, nyt)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
