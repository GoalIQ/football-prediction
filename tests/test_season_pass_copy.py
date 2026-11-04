# -*- coding: utf-8 -*-
"""Portti (WP6 copy-synkka, 4.11.2026): hub ei sano vuosipaketista tilauksen sanoja.

Villen paatos 1.11.2026: verkon vuosipaketti on kertamaksu (25 €, Premium
30.5.2027 asti, ei uusiudu). Ennen sita se oli tilaus, ja hubin pinnat sanoivat
sen kukin omin sanoin: "€25 a year" (etusivun nappi + hintanootti + ottelusivun
nappi), "25 €/year" (ottelusivujen ja FPL-alasivujen alatunniste), "25 EUR per
year" (fpl.html FAQ), "under €2.10 a month" (fpl.html, 25/12 - passille
epatosi: marraskuusta 30.5.2027:aan noin 3,6 €/kk), "Cancel anytime" ja "One
subscription covers ..." (etusivu, FAQ, predictions).

Vuosipaketin sanat tulevat nyt `src.price_copy`ista ja loppupaiva
`src.season_pass`ista. Tama testi mittaa RENDEROIDYN tekstin (ei lahdetta):
GEN-lohkot ja generaattorien vakiot renderoidaan ilmaisikkunan jalkeisella
hetkella, kasin kirjoitetut sivut luetaan sellaisenaan.

Hub on staattinen, joten se ei lue Renderin kytkinta. Tama muutos mergetaan
vasta kun /api/stripe-config price_lookup.season_pass.ok == true;
goaliq-appin ground_truth vertaa sen jalkeen elavaa hintavastausta etusivuun.
"""
from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import price_copy as PC  # noqa: E402
from src import free_window as FW  # noqa: E402
from src.season_pass import SEASON_PASS_END  # noqa: E402

#: Ilmaisikkunan jalkeen (12.9.2026): GEN-lohkot renderoivat "kiinni"-haaran.
JALKEEN = _dt.datetime(2026, 11, 5, 12, 0, tzinfo=_dt.timezone.utc)

#: Vuosipaketin tilaussanat. "cancel anytime" saa esiintya vain kun sama
#: lause rajaa sen kuukausipakettiin (tarkistetaan erikseen).
TILAUSSANAT = [
    re.compile(p, re.I) for p in (
        r"(?:€|&euro;)\s?25\s?a year",
        r"25\s?(?:€|&euro;)\s?/\s?year",
        r"(?:€|&euro;)\s?25\s?/\s?year",
        r"25 (?:euros?|EUR) (?:per|a) year",
        r"under (?:€|&euro;)?\s?2\.10",
        r"\bone subscription\b",
        r"premium subscription covers",
        r"season \(yearly\)",
        # creators.html (Villen paatos 4.11): passilla ei ole uusiutumista.
        r"(?:every|each) renewal",
        r"survives renewals",
    )
]

#: Kasin kirjoitetut julkiset sivut joilla vuosipaketista puhutaan
#: (julkaisutarkistaja 4.11 lisasi llms.txt:n, career.html:n ja privacy.html:n).
KASIN = ("index.html", "faq.html", "predictions.html", "llms.txt", "creators.html",
         "career.html", "privacy.html")
#: Naista sivuista passin loppupaiva on kirjoitettu kasin.
KASIN_PAIVA = ("index.html", "faq.html", "predictions.html", "llms.txt", "creators.html")


def _ilman_kommentteja(html: str) -> str:
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def _renderoidyt() -> dict[str, str]:
    """Generaattorien julkinen teksti sellaisena kuin se paatyy sivulle."""
    import build_fpl_longtail as LT  # noqa: E402
    import build_prediction_pages as BP  # noqa: E402
    import build_fpl_page as FP  # noqa: E402
    ulos = {f"free_window:{tiedosto}:{avain}": fn(JALKEEN)
            for (tiedosto, avain), fn in FW.SURFACE_BLOCKS.items()}
    ulos["build_fpl_page:free_window_block"] = FP.free_window_block(JALKEEN)
    ulos["build_fpl_longtail:UPSELL"] = LT.UPSELL
    ulos["build_prediction_pages:FOOTER"] = BP.FOOTER
    lukko = BP._scoreline_lock({"home": "A", "away": "B"}, played=False) \
        if _lukko_kutsuttavissa(BP) else ""
    ulos["build_prediction_pages:_scoreline_lock"] = lukko
    # fpl.html:n FAQ ja alatunniste ovat render_pagen sisalla; lahteen
    # f-stringin LITERAALIOSAT mitataan, koska PC-kutsut renderoituvat oikein.
    ulos["build_fpl_page:lahde"] = (ROOT / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    return ulos


def _lukko_kutsuttavissa(BP) -> bool:
    try:
        BP._scoreline_lock({"home": "A", "away": "B"}, played=False)
        return True
    except Exception:  # noqa: BLE001 - synteettinen syote voi puuttua kentista
        return False


def test_loppupaiva_tulee_season_passista():
    d = SEASON_PASS_END
    assert PC.pass_end() == f"{d.day} {PC._KUUKAUDET[d.month - 1]} {d.year}"
    assert PC.pass_end() == "30 May 2027"
    assert PC.season_cta() == "€25 for the season"
    assert PC.season_once(before=False) == "25 € once for the season (until 30 May 2027)"


@pytest.mark.parametrize("sivu", KASIN)
def test_kasin_kirjoitettu_sivu_ei_sano_tilausta(sivu):
    html = _ilman_kommentteja((ROOT / sivu).read_text(encoding="utf-8"))
    osumat = [m.group(0) for r in TILAUSSANAT for m in r.finditer(html)]
    assert osumat == [], f"{sivu}: {osumat}"


@pytest.mark.parametrize("sivu", KASIN_PAIVA)
def test_kasin_kirjoitettu_paiva_on_lahteen_paiva(sivu):
    """Kasin kirjoitettu '30 May 2027' kaatuu tahan jos loppuhetki muuttuu."""
    html = _ilman_kommentteja((ROOT / sivu).read_text(encoding="utf-8"))
    paivat = set(re.findall(r"until (\d{1,2} [A-Z][a-z]+ \d{4})", html))
    paivat |= set(re.findall(r"ends on (\d{1,2} [A-Z][a-z]+ \d{4})", html))
    assert paivat, f"{sivu}: passin loppupaiva puuttuu"
    assert paivat == {PC.pass_end()}, f"{sivu}: {paivat}"


def test_cancel_anytime_vain_kuukausipaketista():
    # Lauseet ensin, haku sitten: `[^.]*X[^.]*` koko sivua vasten on
    # neliollinen pitkissa lohkoissa (JSON-LD, tyylit) ja jumitti ajon 4.11.
    for sivu in KASIN:
        html = _ilman_kommentteja((ROOT / sivu).read_text(encoding="utf-8"))
        teksti = re.sub(r"<[^>]+>", " ", html)
        for lause in re.split(r"(?<=[.!?])\s+", teksti):
            if re.search(r"\bcancel(?:led)? (?:anytime|at any time)\b", lause, re.I):
                assert re.search(r"monthly", lause, re.I), f"{sivu}: '{lause.strip()[:200]}'"


def test_renderoity_generaattoriteksti_ei_sano_tilausta():
    loydot = []
    for nimi, teksti in _renderoidyt().items():
        if nimi == "build_fpl_page:lahde":
            # POIKKEUS (6a kohta 2): free_window_block:n auki-haara
            # (ilmaisikkuna paattyi 12.9.2026, ei renderoidy enaa koskaan)
            # sanoo yha "a year"; funktio mitataan RENDEROITUNA ylla. Muu
            # lahde (JSON-LD Offer, FAQ, alatunniste) mitataan kokonaan.
            alku = teksti.index("def free_window_block")
            loppu = teksti.index("\ndef ", alku + 1)
            teksti = teksti[:alku] + teksti[loppu:]
        loydot += [f"{nimi}: {m.group(0)}" for r in TILAUSSANAT for m in r.finditer(teksti)]
        loydot += [f"{nimi}: EUR a year" for _ in re.finditer(r"EUR (?:a|per) year", teksti)]
    assert loydot == []


def test_renderoity_teksti_nimeaa_passin():
    r = _renderoidyt()
    assert PC.season_cta("&euro;") in r["free_window:index.html:FREE-CTA"]
    assert PC.pass_end() in r["free_window:index.html:FREE-HERO-PRICE"]
    assert "/ season" in r["free_window:index.html:FREE-PRICE"]
    assert PC.pass_end() in r["free_window:predictions.html:FREE-PRICE"]
    assert PC.pass_end() in r["build_fpl_page:free_window_block"]
    assert PC.season_once(before=False) in r["build_fpl_longtail:UPSELL"]
    assert PC.season_once(before=False) in r["build_prediction_pages:FOOTER"]


def test_gen_lohkot_ovat_renderoity_versio():
    """index.html ja predictions.html sisaltavat tasan renderoijan tuloksen
    (check_free_window.py --fix ajettu), eli kasin muokattu lohko ei jaa."""
    for (tiedosto, avain), fn in FW.SURFACE_BLOCKS.items():
        html = (ROOT / tiedosto).read_text(encoding="utf-8")
        m = re.search(rf"<!-- GEN:{avain}-START[^>]*-->\n?(.*?)\n?<!-- GEN:{avain}-END -->", html, re.S)
        if not m:
            continue
        assert m.group(1).strip() == fn(JALKEEN).strip(), f"{tiedosto} {avain}"
