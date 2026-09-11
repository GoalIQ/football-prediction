# -*- coding: utf-8 -*-
"""UCL FANTASYSSA EI OLE MALLIA, JA SE MITATAAN JOKA VAIHEESSA JA JOKA PINNALTA.

🔴 MITA TAMA KORJAA (COPY-SYNC-AUDIT 7.9.2026, blokkaava loydos 4)

`tests/test_ucl_page.py` kielsi xP-sarakkeen, mutta kielto asui HAARASSA:

    if kentta == "prev_season_points":
        assert "xP" not in h

`pistekentta()` palauttaa `prev_season_points`in vain esikaudella. MD1 on
8.9.2026, eli **9.9. alkaen se haara ei enaa laukea** ja mikaan ei olisi
estanyt xP-saraketta tai xP-vaitetta /ucl-sivuilla. Toinen portti
(`test_hub_ei_lupaa_taman_kauden_lukuja_esikaudella`) skippaa samasta
hetkesta eteenpain. Invariantti oli siis mitattu hetkella jolloin se sattui
pitamaan - tasan se vikaluokka jonka CLAUDE.md:n saanto 6a kohta 3 kieltaa.

KOLME MEKANISMIA, SAANNON OMASSA JARJESTYKSESSA

1. **Yksi lahde jota pinta ei voi ohittaa.** Kielto on yksi merkkijono
   (`build_ucl_page.EI_MALLIA`) ja `_page()` kirjoittaa sen jokaisen
   UCL-sivun heroon. Uusi UCL-sivu ei voi syntya ilman sita, koska se ei
   kulje kirjoittajan muistin kautta.

2. **Poikkeuslista jossa on perustelu.** Pinta joka NIMEAA UCL Fantasyn
   mutta ei kanna rajausta paatyy `PERUSTELLUT_POIKKEUKSET`iin, ja rivin
   lisaaminen vaatii kirjoitetun syyn. Unohduksesta syntyva vika muuttuu
   mahdottomaksi, tietoinen valinta jaa nakyviin diffiin.

3. **Invariantti mitataan JOKA VAIHEESSA, ei nykyhetkessa.** Sivut
   renderoidaan synteettisella datalla esikaudella, kesken kauden ja
   kauden jalkeen, ja kielto vaaditaan kaikissa kolmessa. Testi joka ajetaan
   vain talla kauden hetkella on vihrea siihen asti kun se lakkaa olemasta
   tosi.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_ucl_page as bp  # noqa: E402
from src.models import ucl_phase as up  # noqa: E402

# ---------------------------------------------------------------------------
# SALLITUT LITERAALIT
#
# Nama ovat KIELLON omat sanamuodot. Ilman poistoa jokainen rajauslause
# nayttaisi projektiovaitteelta ("expected points", "projection"), eika
# negaatiotunnistusta lisata: se on haurasta ja huijattavissa
# ("not just an expected points model"), ja talon portti on jo kerran
# valittu sokeaksi kieltolauseelle tietoisesti (scripts/check_copy_style.py).
#
# Lista on TAHALLAAN lyhyt. Sama vaite viidessa sanamuodossa on viisi eri
# vaitetta lukijalle (muisti: sama-vaite-monessa-sanamuodossa), joten uuden
# parafraasin lisaaminen tanne on paatos, ei rutiini.
# ---------------------------------------------------------------------------
SALLITUT: dict[str, str] = {
    bp.EI_MALLIA:
        "kanoninen kielto; /ucl-hero, llms.txt, faq.html, index.html, "
        "predictions.html ja SPA:n Paywall kayttavat TATA merkkijonoa",
    bp.UCL_DISCLAIMER:
        "/ucl-sivujen footer-varauma, joka korvasi jaetun DISCLAIMERin "
        "('GoalIQ model predictions are statistical estimates') - se vaitti "
        "UEFAn syotelukuja meidan malliennusteiksi",
    "no points projection":
        "tiivis muoto pinnoille joilla ei ole tilaa koko lauseelle "
        "(fpl.html-rivi, index.html-paneelilistaus, AppShellin footer)",
}

# 🔴 KIELLETYT: projektiovaitteen sanaperhe, ei yksi sana. Greppi yhdelle
# sanalle on sokea seuraavalle - se maksoi 16.8 nelja perakkaista
# korjauskierrosta samasta vaitteesta (muisti: vaiteperhe-ei-tyhjene-
# greppaamalla). `xP` on tapauskohtainen ja sanarajattu: 'experience'
# sisaltaa merkit 'xp'.
PROJEKTIO: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bxP\b"), "xP"),
    (re.compile(r"expected points", re.I), "expected points"),
    (re.compile(r"points model", re.I), "points model"),
    (re.compile(r"\bproject(s|ed|ion|ions|ing)?\b", re.I), "project*"),
    (re.compile(r"\bpredict(s|ed|ion|ions|ive)?\b", re.I), "predict*"),
    (re.compile(r"\bforecast(s|ed|ing)?\b", re.I), "forecast*"),
]

# Pinnalla puhutaan UCL FANTASYSTA, ei Champions Leaguesta. Ero on koko
# korjauksen ydin: ottelumalli KATTAA Champions Leaguen aidosti (mitattu
# 7.9: api.goaliq.app/api/fixtures?league=INT-Champions League -> 200, MD1
# 8.9.2026), joten "Champions League" + "prediction" samassa lauseessa on
# TOSI eika saa kaataa mitaan.
UCL_MARKERIT = [re.compile(r"ucl fantasy", re.I), re.compile(r"/ucl\b")]

# ---------------------------------------------------------------------------
# POIKKEUKSET (mekanismi 2). Jokaisella rivilla on syy, ja rivi joutuu
# diffiin. Tyhja lista on oikea lahtotila: poikkeus lisataan silloin kun
# joku sita oikeasti tarvitsee, ei varmuuden vuoksi.
# ---------------------------------------------------------------------------
PERUSTELLUT_POIKKEUKSET: dict[str, str] = {}


def _yksikot(teksti: str) -> list[str]:
    """Pilko luettava teksti yksikoihin.

    🔴 RIVI EI OLE SKANNAUSYKSIKKO (muisti), mutta EIKA KOKO LOHKOKAAN:
    fpl.html:n footerissa on linkkirivi jossa ovat vierekkain 'UCL Fantasy
    prices' ja 'Points vs projection'. Lohkotason skannaus lukisi ne samaksi
    vaitteeksi ja kaatuisi vaarasta syysta. Erottimiksi otetaan siksi myos
    luettelomerkki ja pystyviiva, jotka ovat talla sivustolla linkkirivin
    erottimet.
    """
    return [y for y in re.split(r"(?<=[.!?])\s+|[\n·|]|&middot;", teksti) if y.strip()]


def _luettava(polku: Path) -> str:
    """Tiedoston teksti ilman merkkausta.

    <script> EI leikata pois: JSON-LD asuu siella, ja se on JULKISEMPI pinta
    kuin runko - Google ja LLM-crawlerit lainaavat sen sanatarkasti (muisti:
    hedge-vain-nakyvassa-copyssa). Juuri se paasti 'cannot be picked'
    -yliväitteen lapi 7.9.
    """
    raw = polku.read_text(encoding="utf-8", errors="replace")
    if polku.suffix.lower() in (".html", ".svelte"):
        raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
        raw = re.sub(r"<style\b.*?</style>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
    return raw


def _riisu_sallitut(teksti: str) -> str:
    for lause in SALLITUT:
        teksti = teksti.replace(lause, " ")
    return teksti


def _osumat(teksti: str) -> list[tuple[str, str]]:
    """[(kielletty_kuvio, yksikko)] jokaiselle UCL-yksikolle joka vaittaa
    projektiota."""
    ulos = []
    for y in _yksikot(_riisu_sallitut(teksti)):
        if not any(m.search(y) for m in UCL_MARKERIT):
            continue
        for kuvio, nimi in PROJEKTIO:
            if kuvio.search(y):
                ulos.append((nimi, " ".join(y.split())[:200]))
    return ulos


# ---------------------------------------------------------------------------
# 1. VAIHEESTA RIIPPUMATON: kolme synteettista kauden vaihetta
# ---------------------------------------------------------------------------
_NYT = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)
_RENDEROIJAT = (bp.sivu_hub, bp.sivu_hinnat, bp.sivu_team_news)


def _pelaajat(pelattu: int, pisteet: bool) -> list[dict]:
    """Jokainen positio ja jokainen tila edustettuna.

    `sivu_hub` laskee kalleimman per positio `max()`illa (kaatuu tyhjaan
    positioon), `nis_max`in `not_in_squad`-ryhmasta ja kaavion
    loukkaantuneista - synteettisen datan on katettava ne kaikki tai testi
    olisi vihrea siksi etta se kaatuu vaaraan asiaan.
    """
    pohja = [
        ("A", "AAA", "MID", 7.5, 12.0, "available", 40, 900),
        ("B", "BBB", "DEF", 5.0, 3.0, "injured", 0, 0),
        ("C", "AAA", "FWD", 9.0, 30.0, "not_in_squad", 12, 300),
        ("D", "BBB", "GK", 4.5, 8.0, "available", 20, 720),
        ("E", "AAA", "MID", 6.0, 2.0, "suspended", 15, 450),
        ("F", "BBB", "FWD", 8.0, 5.0, "doubtful", 30, 800),
    ]
    ulos = []
    for i, (nimi, koodi, pos, hinta, om, tila, pp, pm) in enumerate(pohja, 1):
        p = {"id": i, "name": nimi, "team": f"Club {koodi}", "team_id": i,
             "team_code": koodi, "pos": pos, "price": hinta, "owned_pct": om,
             "status": tila, "matchdays_played": pelattu,
             "prev_season_points": pp, "prev_season_minutes": pm}
        if pisteet:
            p["points"] = pp // 2
        ulos.append(p)
    return ulos


def _doc(vaihe: str) -> dict:
    """Artefakti jonka `ucl_phase.vaihe()` luokittelee halutuksi vaiheeksi."""
    if vaihe == up.ESIKAUSI:
        dls = ["2026-11-24T18:45:00+00:00", "2026-12-09T18:45:00+00:00"]
        pelattu, pisteet = 0, False
    elif vaihe == up.KESKEN:
        dls = ["2026-09-08T18:45:00+00:00", "2026-12-09T18:45:00+00:00"]
        pelattu, pisteet = 3, True
    else:
        dls = ["2026-09-08T18:45:00+00:00", "2026-10-13T18:45:00+00:00"]
        pelattu, pisteet = 8, True
    doc = {
        "meta": {"season_id": 90, "matchday": 2, "players_matchday": 2,
                 "players_matchday_is_fallback": False,
                 "feed_updated_utc": "2026-10-30T18:40:00+00:00",
                 "players": 6, "teams": 2},
        # Esikaudella yhtaan kierrosta ei ole lukittu: lukittu kierros on
        # 11.9 lahtien kauden alun signaali (`ucl_phase.kausi_alkanut`), ja
        # UEFA:n syotteessa `gdIsLocked` on False ennen deadlinea.
        "matchdays": [{"md": i + 1, "deadline_utc": d,
                       "is_locked": vaihe != up.ESIKAUSI,
                       "gamedays": 1} for i, d in enumerate(dls)],
        "teams": [{"id": 1, "name": "Club AAA", "code": "AAA"},
                  {"id": 2, "name": "Club BBB", "code": "BBB"}],
        "players": _pelaajat(pelattu, pisteet),
    }
    return doc


@pytest.mark.parametrize("vaihe", [up.ESIKAUSI, up.KESKEN, up.OHI])
def test_synteettinen_vaihe_on_se_jota_luullaan(vaihe):
    """KONTROLLI: ilman tata kolme 'eri' vaihetta voisivat olla sama vaihe,
    ja testi alla olisi vihrea siksi etta se mittaa yhden asian kolmesti."""
    assert up.vaihe(_doc(vaihe), _NYT) == vaihe


@pytest.mark.parametrize("vaihe", [up.ESIKAUSI, up.KESKEN, up.OHI])
@pytest.mark.parametrize("render", _RENDEROIJAT,
                         ids=[f.__name__ for f in _RENDEROIJAT])
def test_ei_xp_vaitetta_missaan_kauden_vaiheessa(render, vaihe):
    h = render(_doc(vaihe), _NYT)
    assert "xP" not in h, (
        f"{render.__name__} / {vaihe}: sivulla on xP, mutta UCL Fantasylle "
        "ei ole mallia missaan kauden vaiheessa")
    osumat = _osumat(h)
    assert not osumat, (
        f"{render.__name__} / {vaihe}: projektiovaite UCL Fantasysta:\n  "
        + "\n  ".join(f"[{n}] {t}" for n, t in osumat))


@pytest.mark.parametrize("vaihe", [up.ESIKAUSI, up.KESKEN, up.OHI])
@pytest.mark.parametrize("render", _RENDEROIJAT,
                         ids=[f.__name__ for f in _RENDEROIJAT])
def test_rajaus_on_sivulla_jokaisessa_vaiheessa(render, vaihe):
    """Rajaus ei saa olla esikauden copya joka katoaa MD1:ssa."""
    h = render(_doc(vaihe), _NYT)
    assert bp.EI_MALLIA in h, (
        f"{render.__name__} / {vaihe}: kanoninen rajaus puuttuu")
    assert bp.UCL_DISCLAIMER in h, (
        f"{render.__name__} / {vaihe}: footer-varauma puuttuu")
    assert "statistical estimates" not in h, (
        f"{render.__name__} / {vaihe}: sivu ajaa jaettua DISCLAIMERia, joka "
        "vaittaa UEFAn syotelukuja GoalIQ:n malliennusteiksi")


# ---------------------------------------------------------------------------
# 2. KAIKKI PINNAT, EI VAIN /ucl
#
# Sivulista johdetaan globista eika vakiosta: uusi pinta on juuri se paikka
# jossa vaite palaa (muisti: vieras-tiedosto-glob-kansiossa). `predictions/`
# -alipuusta luetaan vain hubit: 2 760 ottelusivua on generoitu samasta
# templatesta eika yksikaan nimea UCL Fantasya.
# ---------------------------------------------------------------------------
def _pinnat() -> list[Path]:
    ulos: list[Path] = []
    ulos += sorted(ROOT.glob("*.html"))
    ulos += sorted(ROOT.glob("fpl/**/*.html"))
    ulos += sorted(ROOT.glob("ucl/*.html"))
    ulos += sorted(ROOT.glob("predictions/*/index.html"))
    if (ROOT / "llms.txt").exists():
        ulos.append(ROOT / "llms.txt")
    spa = ROOT / "web" / "pro-spa" / "src"
    if spa.exists():
        ulos += sorted(spa.rglob("*.svelte")) + sorted(spa.rglob("*.ts"))
    return ulos


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


@pytest.mark.parametrize("polku", _pinnat(), ids=_rel)
def test_mikaan_pinta_ei_lupaa_ucl_fantasy_projektiota(polku):
    osumat = _osumat(_luettava(polku))
    assert not osumat, (
        f"{_rel(polku)}: pinta vaittaa projektiota UCL Fantasysta. "
        "UCL Fantasy on UEFAn syotetta (hinta, omistus, kokoonpanotila) "
        "eika sille ole mallia.\n  "
        + "\n  ".join(f"[{n}] {t}" for n, t in osumat))


def _kuvaileva(polku: Path) -> str:
    """Teksti ilman LINKKITEKSTEJA.

    🔴 EROTUS ON KOKO PORTIN TARKKUUS. Ensimmainen versio vaati rajauksen
    jokaiselta pinnalta jolla lukee "UCL Fantasy", ja se kaatui 55 sivulla:
    jokaisen /fpl-sivun footerissa on linkkirivi jossa lukee "UCL Fantasy
    prices". Linkki ei KUVAA osiota, se osoittaa siihen, ja rajaus on
    yhden klikin paassa sivulla johon linkki vie.

    Vaatimus koskee siis pintaa joka KERTOO mika osio on. Vaite joka on
    kirjoitettu linkkitekstiin ei silti paase pakoon: negatiivinen skannaus
    (`_osumat`) lukee koko tekstin, linkkitekstit mukaan lukien.
    """
    raw = polku.read_text(encoding="utf-8", errors="replace")
    if polku.suffix.lower() in (".html", ".svelte"):
        raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
        raw = re.sub(r"<style\b.*?</style>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<a\b[^>]*>.*?</a>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
    else:
        # llms.txt on markdownia: [label](url) on sama asia kuin <a>.
        raw = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", raw)
    return raw


def _nimeaa_uclin(polku: Path) -> bool:
    return bool(re.search(r"ucl fantasy", _kuvaileva(polku), re.I))


@pytest.mark.parametrize("polku", _pinnat(), ids=_rel)
def test_ucl_fantasyn_nimeava_pinta_kantaa_rajauksen(polku):
    """🔴 AUDIT-RIVI 2: rajaus oli olemassa TASMALLEEN yhdella pinnalla,
    `llms.txt`:ssa, joka on koneluettava. Yksikaan ihminen ei nahnyt sita,
    ja samaan aikaan sivusto myy ennustemallia samassa navissa.

    Portti on positiivinen tarkoituksella: negatiivinen skannaus lapaisee
    pinnan joka ei sano MITAAN, ja tasan sellaisia pintoja oli 7.9 kuusi."""
    if not _nimeaa_uclin(polku):
        pytest.skip("ei nimea UCL Fantasya")
    rel = _rel(polku)
    if rel in PERUSTELLUT_POIKKEUKSET:
        pytest.skip(f"poikkeus: {PERUSTELLUT_POIKKEUKSET[rel]}")
    teksti = _luettava(polku)
    assert any(l in teksti for l in SALLITUT), (
        f"{rel}: pinta nimeaa UCL Fantasyn muttei kerro etta sille ei ole "
        "mallia. Lisaa `build_ucl_page.EI_MALLIA` sanatarkasti, tai lisaa "
        "tiedosto PERUSTELLUT_POIKKEUKSET-listalle syyn kanssa.")


def test_poikkeuslistalla_ei_ole_kuolleita_rivaja():
    """Poikkeus jonka kohdetta ei ole on muistiinpano, ei paatos: se jaa
    listalle vuosiksi ja peittaa seuraavan lisayksen."""
    puuttuu = [r for r in PERUSTELLUT_POIKKEUKSET if not (ROOT / r).exists()]
    assert not puuttuu, f"poikkeuslistalla tiedostoja joita ei ole: {puuttuu}"


# ---------------------------------------------------------------------------
# 3. NEGATIIVISET KONTROLLIT
#
# Portti joka ei voi kaatua ei mittaa mitaan (muisti: kontrolli-lapaisi-
# tyhjana). Nama ajavat SAMAT funktiot kuin portti itse.
# ---------------------------------------------------------------------------
def test_kontrolli_havaitsin_loytaa_projektiovaitteen():
    assert _osumat("<p>UCL Fantasy expected points for every player.</p>")
    assert _osumat("Our xP for UCL Fantasy is live.")
    assert _osumat('{"description": "Projected UCL Fantasy points by club."}')
    assert _osumat("Predicted points at goaliq.app/ucl/prices.")


def test_kontrolli_havaitsin_ei_kaadu_oikeaan_copyyn():
    """Ottelumalli KATTAA Champions Leaguen (API 200, MD1 8.9.2026), joten
    'Champions League' + 'prediction' on tosi eika saa kaatua."""
    assert not _osumat(
        "Champions League predictions: win probability for any fixture.")
    assert not _osumat(f"<p>{bp.EI_MALLIA}</p>")
    assert not _osumat(f"<p>{bp.UCL_DISCLAIMER}</p>")
    assert not _osumat("Free UCL Fantasy prices and ownership, no login.")


def test_kontrolli_linkkirivi_ei_ole_yksi_vaite():
    """fpl.html:n footerissa 'UCL Fantasy prices' ja 'Points vs projection'
    ovat vierekkain. Ne ovat kaksi linkkia, eivat yksi vaite."""
    rivi = ("Points vs projection &middot; Player stats &middot; "
            "UCL Fantasy prices &middot; World Cup 2026 predictions")
    assert not _osumat(rivi)
    # ...mutta saman linkin sisalla oleva vaite EI saa livahtaa lapi.
    assert _osumat("Team news &middot; UCL Fantasy projected points "
                   "&middot; Player stats")


def test_kontrolli_linkkiteksti_ei_laukaise_vaatimusta_mutta_vaite_kaatuu(
        tmp_path):
    """KONTROLLI `_kuvaileva`lle: se voisi riisua liikaa (kaikki pinnat
    skippaisivat) tai liian vahan (55 turhaa kaatoa, kuten ensimmaisella
    ajolla)."""
    linkki = tmp_path / "linkki.html"
    linkki.write_text('<p>Team news &middot; <a href="/ucl/">UCL Fantasy '
                      "prices</a> &middot; Notes</p>", encoding="utf-8")
    assert not _nimeaa_uclin(linkki), "pelkka linkkiteksti vaatii rajauksen"

    kuvaus = tmp_path / "kuvaus.html"
    kuvaus.write_text("<h2>UCL Fantasy prices and squad news</h2>"
                      "<p>Every player's price and ownership.</p>",
                      encoding="utf-8")
    assert _nimeaa_uclin(kuvaus), "kuvaileva pinta ei vaadi rajausta"

    # Ja linkkitekstiin kirjoitettu VAITE ei paase pakoon.
    vaite = tmp_path / "vaite.html"
    vaite.write_text('<p><a href="/ucl/">UCL Fantasy expected points</a></p>',
                     encoding="utf-8")
    assert _osumat(_luettava(vaite)), "linkkitekstin vaite livahti lapi"


def test_kontrolli_pintalista_ei_ole_tyhja():
    pinnat = _pinnat()
    assert len(pinnat) > 60, f"vain {len(pinnat)} pintaa - onko glob rikki?"
    nimet = {_rel(p) for p in pinnat}
    for pakollinen in ("index.html", "faq.html", "fpl.html", "llms.txt",
                       "predictions.html",
                       "web/pro-spa/src/lib/components/Paywall.svelte"):
        assert pakollinen in nimet, f"pintalistasta puuttuu {pakollinen}"
