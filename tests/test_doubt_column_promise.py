"""Portti: epavarmuus-sarakkeesta luvataan sama asia joka pinnalla.

TAUSTA (12.9.2026, DOUBT-COST-LUPAUS). Kaksi ILMAISTA pintaa sanoi samasta
sarakkeesta eri asian:

  /fpl            "...so you can see what the doubt actually costs"
  /fpl/team-news  "...not what the player would score if fully fit"

Hinnan nakeminen vaatii kaksi lukua (terve ja epavarma). Sivulla on vain
toinen, joten hintalupaus oli epatosi. Se ei jaanyt sisaiseksi: 12.9
julkaisutarkistaja blokkasi postausdraftin joka kaytti /fpl:n omaa
sanamuotoa lahteena. Oma copymme oli lahde vaaralle vaitteelle.

MIKSI TAMA TESTI EIKA SANALISTA. Sanalista "costs" vanhenisi ensimmaisesta
uudelleenmuotoilusta (muisti: portin-sanalista-vanhenee). Siksi kaksi ehtoa:

  (1) Molemmat pinnat renderoivat SAMAN jaetun lauseen
      (src/doubt_copy.XP_SISALTAA_EPAVARMUUDEN). Kopiota ei voi kirjoittaa
      eriytymaan, koska kopiota ei ole.
  (2) Kummallakaan pinnalla ei saa olla hintavaiteperheen osumaa. Perhe on
      regex eika merkkijono, ja sille on mutaatiokontrolli alla: jos regex
      lakkaa loytamasta poistettua lausetta, testi kaatuu.

Mitataan RENDEROIDUSTA HTML:sta, ei lahdekoodista: vaite syntyy vasta
tarjoilussa (muisti: invariantti-syntyy-vasta-tarjoilussa).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_fpl_longtail import render_team_news  # noqa: E402
from scripts.build_fpl_page import team_news_block  # noqa: E402
from src.doubt_copy import (  # noqa: E402
    XP_SISALTAA_EPAVARMUUDEN,
    HINTAVAITE_SALLITTU,
    hintavaitteet,
    lauseena,
)

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)

# Sanamuoto joka oli livena 12.9 asti. Kontrolli sille etta regex mittaa
# oikeaa asiaa (muisti: portin-fikstuuri-kirjoitetaan-korjatusta-tapauksesta).
POISTETTU_LAUSE = (
    "<p>The full list is free and sorted by ownership, and every doubtful "
    "player carries the model's projected points with the reduced chance of "
    "playing already priced in, so you can see what the doubt actually "
    'costs: <a href="/fpl/team-news">FPL team news</a>.</p>'
)


def _p(name="Gakpo", **kw):
    base = {
        "web_name": name, "team_short": "LIV", "pos": "MID",
        "owned_pct": 12.9, "news": "Knock - 75% chance of playing",
        "chance_next": 75, "status": "d", "xp_horizon_total": 18.0,
        "gameweeks": [4, 5, 6, 7, 8, 9],
    }
    base.update(kw)
    return base


def _xp(players=None, excluded=None):
    return {
        "meta": {"available": True, "next_gameweek": 4},
        "players": list(players if players is not None else [_p()]),
        "excluded": list(excluded or []),
    }


def _pinnat() -> dict[str, str]:
    """Molemmat renderoidut pinnat. Tyhja/None = testi kaatuu, ei ohita."""
    etusivu = team_news_block(_xp())
    longtail = render_team_news(_xp(), NOW)
    assert etusivu, "team_news_block palautti tyhjan: fikstuuri ei kelpaa"
    assert longtail, "render_team_news palautti Nonen: fikstuuri ei kelpaa"
    return {"/fpl (team_news_block)": etusivu, "/fpl/team-news": longtail}


def test_molemmat_pinnat_kertovat_saman_sarakkeesta():
    for nimi, html in _pinnat().items():
        auki = " ".join(html.split())
        assert XP_SISALTAA_EPAVARMUUDEN in auki or lauseena() in auki, (
            f"{nimi} ei kanna jaettua lausetta epavarmuus-sarakkeesta. "
            "Jos sanamuoto muuttuu, muuta src/doubt_copy.py eika pintaa."
        )


def test_kumpikaan_pinta_ei_lupaa_epavarmuuden_hintaa():
    assert not HINTAVAITE_SALLITTU, (
        "HINTAVAITE_SALLITTU on True: fully-fit-luku on siis julkaistu. "
        "Paivita talloin tama testi ja molempien pintojen copy."
    )
    for nimi, html in _pinnat().items():
        osumat = hintavaitteet(html)
        assert not osumat, (
            f"{nimi} lupaa epavarmuuden hinnan: {osumat}. Sivu nayttaa vain "
            "epavarmuuden sisaltavan luvun, ei tervetta lukua, joten hintaa "
            "ei voi lukea sivulta."
        )


def test_kontrolli_hintavaite_loytyy_poistetusta_lauseesta():
    """Ilman tata kaksi edellista voisivat olla vihreita tyhjina."""
    assert hintavaitteet(POISTETTU_LAUSE) == ["what the doubt actually costs"]


def test_kontrolli_perhe_kattaa_uudelleenmuotoilut():
    """Sanalista vanhenee, perheen pitaa kestaa sanamuodon vaihto."""
    for muunnos in (
        "see how much the injury is costing you",
        "the cost of the doubt in points",
        "the flag costs him two points",
        "what the knock actually costs",
    ):
        assert hintavaitteet(f"<p>{muunnos}</p>"), muunnos


def test_kontrolli_ei_osu_naapurivaitteisiin():
    """Perhe ei saa blokata lauseita jotka eivat lupaa epavarmuuden hintaa."""
    for viaton in (
        "<p>the hold-or-transfer verdict with the hit priced in</p>",
        "<p>what a four-point hit costs you over six gameweeks</p>",
        "<p>the price of every player in your squad</p>",
    ):
        assert not hintavaitteet(viaton), viaton


def test_vaite_loytyy_myos_kun_tagi_katkaisee_lauseen():
    """Rivi ei ole skannausyksikko: <strong> tai linkki keskella lausetta
    ei saa piilottaa vaitetta portilta."""
    katkaistu = "<p>so you can see what the <strong>doubt</strong> actually costs</p>"
    assert hintavaitteet(katkaistu)


# --- Rakenteellinen ehto -------------------------------------------------
# Portti mittasi 12.9 etta SEITSEMAN vaihtoehtoista sanamuotoa lapaisi
# hintavaiteperheen, vahvimpana sivun OMA H1 joka oli silloin tuotannossa.
# Juurisyy: perhe mittaa SANAMUOTOA, mutta epatosi asia on VAITE RUUDUN
# SISALLOSTA, ja sanamuotoja on aareton maara. Alla oleva ehto ei ole
# kierrettavissa sanoilla: hinta vaatii kaksi lukua, ja taulukossa on yksi.

def _thead_otsikot(html: str, section: str) -> list[str]:
    import re as _re
    blk = _re.search(rf'<h2 id="{section}">.*?</thead>', html, _re.S)
    assert blk, f"sektiota {section} ei loytynyt renderoidysta sivusta"
    return [
        _re.sub(r"<[^>]+>", "", c).strip()
        for c in _re.findall(r"<th[^>]*>(.*?)</th>", blk.group(0), _re.S)
    ]


def test_doubtful_taulukossa_on_yksi_projektioluku_eika_vastafaktuaalia():
    """TAMA on portin ydin, ei sanalista.

    Hintaa ei voi nayttaa ilman kahta lukua: mita malli odottaa nyt, ja mita
    se odottaisi terveena. Taulukossa on tasan yksi projektiosarake eika
    yhtaan vastafaktuaalista. Jos tama joskus muuttuu, hintavaite muuttuu
    LUETTAVAKSI ja copy on arvioitava uudelleen -- silloin tama testi kaatuu
    ja pakottaa sen paatoksen nakyviin.
    """
    from src.doubt_copy import projektiosarakkeet, vastafaktuaalisarakkeet

    otsikot = _thead_otsikot(render_team_news(_xp(), NOW), "doubtful")
    proj = projektiosarakkeet(otsikot)
    assert len(proj) == 1, (
        f"Doubtful-taulukossa on {len(proj)} projektiosaraketta ({proj}). "
        "Kahdella luvulla lukija voi lukea EROTUKSEN, eli hintavaite muuttuu "
        "todeksi. Paivita src/doubt_copy.py ja molempien pintojen copy."
    )
    vasta = vastafaktuaalisarakkeet(otsikot)
    assert not vasta, (
        f"Doubtful-taulukossa on vastafaktuaalinen sarake ({vasta}). "
        "Sama seuraus kuin yllä."
    )


def test_otsikko_tulee_jaetusta_lukijasta():
    """12.9: hintavaite oli poistettu /fpl:lta mutta jai kohdesivun H1:een,
    eli lukija klikkasi linkkia ja laskeutui juuri siihen vaitteeseen."""
    from src.doubt_copy import TEAM_NEWS_H1

    html = render_team_news(_xp(), NOW)
    assert f"<h1>{TEAM_NEWS_H1}</h1>" in html
    assert not hintavaitteet(TEAM_NEWS_H1)


def test_kontrolli_perhe_loytaa_vanhan_otsikon():
    assert hintavaitteet("<h1>Team news, with the points cost attached</h1>")
