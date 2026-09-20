"""Lukija saa puhua vain niista tyokaluista joiden tier PALVELIN vahvistaa.

MIKSI TAMA ON OLEMASSA. 18.9 rakennettiin yksi lukija (`src/tool_tiers.py`)
joka johtaa jokaisen julkisen tier-lauseen `web/pro-spa/src/lib/tools.ts`:sta.
Se poistaa yhden vikaluokan ja luo toisen: **jos rekisteri on vaarassa, yksi
lukija levittaa vaaran vaitteen kaikille pinnoille kerralla.** Ennen lukijaa
vaara vaite oli yhdella sivulla; lukijan jalkeen se olisi kaikilla.

Siksi rekisteria ei tarkisteta KERRAN vaan joka ajolla, ja vertailukohta on
palvelimen TODELLINEN kaytos: `api/premium.py`:n maskiparametrit ja
`tests/test_premium_enforcement.py`:n luokittelu (GATED / FREE / PARTIAL),
joka puolestaan on mitattu ajamalla eika luettu koodista.

TARKISTUS 18.9 (kierros 2) loysi kaksi rekisterin ja palvelimen erimielisyytta:

  `value`    rekisteri `free`, mutta `/api/fantasy/value` on GATED ja free
             saa `FREE_VALUE_ROWS = 3` rivia. Pelkka "free" olisi puolikas
             totuus, tasan kuten watchlistilla. Siksi saanto: ilmainen
             tyokalu gatetun endpointin paalla saa puhua vain jos lauseessa
             on KATTO (`caveat()` ei ole None).

  `compare`  rekisteri `premium`, mutta `/api/fantasy/compare` on
             FREE_EXPECTEDissa. Toinen niista on vaarassa, ja kumpikin
             korjaus on tuotepaatos (gate endpointtiin vs. tier auki).
             🔒 GO Villelle. Talla valin lukija EI SAA nimeta sita: slugilla
             ei ole `_COPY`-merkintaa, joten `phrase()` kaatuu `MissingCopy`in
             ja mikaan pinta ei voi julkaista vaitetta kumpaankaan suuntaan.

Tama testi lukitsee molemmat: erimielisyys on sallittu vain kun lukija on
mykka sen tyokalun suhteen tai kun lause kertoa katon.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from test_premium_enforcement import (  # noqa: E402
    FREE_EXPECTED,
    GATED_EXPECTED,
    PARTIAL_EXPECTED,
)

from src.tool_tiers import _COPY, load  # noqa: E402

GATED, FREE, PARTIAL, NONE = "GATED", "FREE", "PARTIAL", "-"


class Pinta:
    """Tyokalun palvelinpinta: endpoint, tai kirjattu syy sille ettei ole."""

    def __init__(self, endpoint: str | None, reason: str = "") -> None:
        if endpoint is None and len(reason.strip()) < 30:
            raise AssertionError("endpointiton tyokalu tarvitsee perustelun")
        self.endpoint = endpoint
        self.reason = reason


# Slug -> palvelinpinta. Tama kartta on KASIN yllapidettava, ja se on
# tahallaan: jos uusi tyokalu ei ole taalla, `test_kartta_kattaa_rekisterin`
# kaatuu ja kirjoittaja joutuu kertomaan mista sen data tulee.
PINNAT: dict[str, Pinta] = {
    "rate-my-team": Pinta("/api/fantasy/rate-team"),
    "fit-checker": Pinta("/api/fantasy/fit"),
    "transfer-planner": Pinta("/api/fantasy/plan"),
    "watchlist": Pinta(
        None,
        "Watchlist on selaimen oma lista (web/pro-spa/src/lib/prefs.ts). "
        "Palvelimella ei ole watchlist-endpointtia; katto on prefs.ts:n "
        "WATCHLIST_FREE_LIMIT, ja se luetaan lauseeseen.",
    ),
    "player-card": Pinta(
        None,
        "Pelaajakortti kokoaa muiden endpointtien dataa yhdeksi nakymaksi "
        "SPA:ssa; silla ei ole omaa endpointtia jota voisi gatettaa.",
    ),
    "captain-ranker": Pinta("/api/fantasy/captain"),
    "fixture-swing": Pinta(
        None,
        "Fixture swing lasketaan SPA:ssa fixture-datasta jota /api/fantasy/xp "
        "ja julkiset fixture-syotteet tarjoavat; ei omaa endpointtia.",
    ),
    "player-xp": Pinta("/api/fantasy/xp"),
    "clean-sheets": Pinta(
        None,
        "Clean sheet -todennakoisyydet tulevat ottelumallista julkisilta "
        "predictions-syotteilta, ei omalta fantasy-endpointilta.",
    ),
    "value": Pinta("/api/fantasy/value"),
    "leaders": Pinta("/api/fantasy/xg-leaders"),
    "stats": Pinta("/api/fantasy/player-stats"),
    "differentials": Pinta("/api/fantasy/differentials"),
    "replacements": Pinta("/api/fantasy/replacements"),
    "compare": Pinta("/api/fantasy/compare"),
    "chip-timing": Pinta("/api/fantasy/chip-ev"),
    "transfer-chains": Pinta("/api/fantasy/plan-chains"),
    "edge-mode": Pinta("/api/fantasy/edge"),
    "league": Pinta("/api/fantasy/league/{league_id}"),
    "price-watch": Pinta("/api/fantasy/price-watch"),
    "predict": Pinta(
        None,
        "Ottelun ennuste luetaan julkisista predictions-artefakteista; "
        "ei fantasy-endpointtia jolla olisi tier.",
    ),
    "fixtures": Pinta(
        None,
        "Otteluohjelma on julkista dataa samoista artefakteista kuin sivut; "
        "ei omaa gatetavaa endpointtia.",
    ),
    "table": Pinta(
        None,
        "Sarjataulukko on julkista dataa samoista artefakteista kuin sivut; "
        "ei omaa gatetavaa endpointtia.",
    ),
}


def _luokka(endpoint: str | None) -> str:
    if endpoint is None:
        return NONE
    if endpoint in GATED_EXPECTED:
        return GATED
    if endpoint in FREE_EXPECTED:
        return FREE
    if endpoint in PARTIAL_EXPECTED:
        return PARTIAL
    return "TUNTEMATON"


def _erimieliset() -> dict[str, str]:
    """Slugit joiden rekisterin tier ei saa vahvistusta palvelimelta."""
    reader = load()
    out = {}
    for slug in reader.slugs():
        luokka = _luokka(PINNAT[slug].endpoint)
        tier = reader.tier(slug)
        if luokka in (NONE, PARTIAL):
            # PARTIAL = ilmainen ydin + premium-erittely. Se ei kumoa
            # kumpaakaan luokkaa: lause lupaa luokan, ei kenttia.
            continue
        if tier == "premium" and luokka == FREE:
            out[slug] = f"rekisteri premium, {PINNAT[slug].endpoint} on FREE"
        if tier == "free" and luokka == GATED:
            out[slug] = f"rekisteri free, {PINNAT[slug].endpoint} on GATED"
    return out


# --------------------------------------------------------------------------
# Portit
# --------------------------------------------------------------------------


def test_kartta_kattaa_rekisterin() -> None:
    """Uusi tyokalu ei paase lapi ilman etta joku kertoo mista sen data
    tulee — ja endpointiton tyokalu vaatii kirjatun perustelun."""
    reader = load()
    puuttuvat = [s for s in reader.slugs() if s not in PINNAT]
    assert not puuttuvat, (
        "nailla rekisterin tyokaluilla ei ole palvelinpintaa kirjattuna: "
        + ", ".join(puuttuvat)
    )
    ylimaaraiset = [s for s in PINNAT if s not in reader.slugs()]
    assert not ylimaaraiset, (
        "kartassa on tyokaluja joita rekisterissa ei ole: "
        + ", ".join(ylimaaraiset)
    )


def test_jokainen_endpoint_on_luokiteltu() -> None:
    """Kontrolli tyhjaa vastaan: jos endpointin polku kirjoitetaan vaarin,
    `_luokka` palauttaisi TUNTEMATON ja koko vertailu menisi hiljaa lapi."""
    tuntemattomat = [
        s for s, p in PINNAT.items() if _luokka(p.endpoint) == "TUNTEMATON"
    ]
    assert not tuntemattomat, (
        "nama endpointit eivat ole test_premium_enforcement.py:n luokittelussa "
        "(kirjoitusvirhe polussa tai endpoint poistettu): "
        + ", ".join(tuntemattomat)
    )
    assert any(_luokka(p.endpoint) == GATED for p in PINNAT.values())
    assert any(_luokka(p.endpoint) == FREE for p in PINNAT.values())


def test_lukija_ei_puhu_tyokalusta_jonka_tier_on_riidanalainen() -> None:
    """🔴 TAMA ON SE PORTTI JOKA ESTAA YHDEN LUKIJAN PAHIMMAN VIAN.

    Jos rekisteri ja palvelin ovat eri mielta, lukija ei saa nimeta
    tyokalua: ilman `_COPY`-merkintaa `phrase()` kaataa ajon (`MissingCopy`),
    eika yksikaan pinta voi julkaista vaitetta kumpaankaan suuntaan.
    """
    reader = load()
    riidanalaiset = _erimieliset()
    puhuu = []
    for slug, syy in riidanalaiset.items():
        if slug not in _COPY:
            continue
        # Poikkeus: ilmainen tyokalu gatetun endpointin paalla SAA puhua,
        # jos lause kertoo katon (kuten `value`: kolme rivia ilmaiseksi).
        if reader.tier(slug) == "free" and reader.caveat(slug):
            continue
        puhuu.append(f"{slug}: {syy}, mutta lukijalla on sille lause")
    assert not puhuu, (
        "lukija levittaisi vahvistamattoman tier-vaitteen kaikille pinnoille:\n  "
        + "\n  ".join(puhuu)
    )


def test_ilmainen_gatetun_endpointin_paalla_kertoo_katon() -> None:
    """`value` on rekisterissa free mutta /api/fantasy/value on GATED ja
    palauttaa freelle `FREE_VALUE_ROWS` rivia. Pelkka "free" olisi sama
    puolikas totuus jonka watchlist opetti: luokka oikein, maara kertomatta.
    """
    reader = load()
    ilman_kattoa = []
    for slug in _COPY:
        if reader.tier(slug) != "free":
            continue
        if _luokka(PINNAT[slug].endpoint) != GATED:
            continue
        if not reader.caveat(slug):
            ilman_kattoa.append(slug)
    assert not ilman_kattoa, (
        "nama ovat rekisterissa ilmaisia mutta endpoint on gatettu, eika "
        "lause kerro kattoa: " + ", ".join(ilman_kattoa)
    )
    # Ja positiivinen kontrolli: `value`n katto tulee LAHTEESTA.
    assert "three rows free" in (reader.caveat("value") or ""), reader.caveat("value")


def test_neljan_lauseessa_nimetyn_tyokalun_tier_on_vahvistettu() -> None:
    """Se lause joka 18.9 korjattiin nimeaa nelja tyokalua. Jokaisen luokan
    on oltava palvelimen vahvistama, muuten korjaus vain vaihtoi valheen
    suuntaa."""
    reader = load()
    odotus = {
        "rate-my-team": ("free", (FREE, PARTIAL)),
        "watchlist": ("free", (NONE,)),
        # 20.9: GATED -> (GATED, PARTIAL). `/api/fantasy/plan` luokiteltiin
        # GATEDiksi, mutta anonyymi kutsu palauttaa **200** ja
        # `meta.mask: "first 1 of 5 gameweeks (free preview)"` (mitattu
        # livena 20.9). Se on sama kuvio kuin `captain-ranker`illa ja
        # `defcon-leaders`illa: premium-tyokalu jolla on ilmainen esikatselu.
        # PARTIAL EI heikenna lupausta "Premium unlocks the transfer
        # planner" - se antaa vahemman kuin lause lupaa, ei enempaa, ja
        # esikatselun KOKO on nyt pinnattu (`ILMAINEN_ESIKATSELU`).
        "transfer-planner": ("premium", (GATED, PARTIAL)),
        "captain-ranker": ("premium", (GATED, PARTIAL)),
    }
    for slug, (tier, sallitut) in odotus.items():
        assert reader.tier(slug) == tier, slug
        assert _luokka(PINNAT[slug].endpoint) in sallitut, (
            f"{slug}: palvelinluokka {_luokka(PINNAT[slug].endpoint)} ei tue "
            f"rekisterin arvoa {tier}"
        )


def test_erimielisyys_on_kirjattu_eika_kadonnut() -> None:
    """Jos `compare` (tai mika tahansa muu) ei enaa ole riidanalainen, joku
    on korjannut sen — ja silloin tama testi kertoo etta muistiinpano ylla
    kuuluu paivittaa. Tyhja lista ei saa liukua ohi hiljaa."""
    riidanalaiset = _erimieliset()
    assert "compare" in riidanalaiset, (
        "compare ei ole enaa riidanalainen (rekisteri premium vs "
        "/api/fantasy/compare FREE). Jos se on korjattu, poista tama rivi ja "
        "paivita moduulin docstring; ala jata porttia vartioimaan tilaa jota "
        "ei ole."
    )
    assert "compare" not in _COPY, (
        "compare sai lauseen vaikka sen tier on riidanalainen"
    )


@pytest.mark.parametrize("slug", sorted(_COPY))
def test_jokaisella_lauseella_on_pinta_ja_luokka(slug: str) -> None:
    """Jokainen `_COPY`-rivi on julkaistavaa myyntitekstia. Sille on oltava
    palvelinpinta kartassa ja rekisterissa luokka."""
    reader = load()
    assert slug in PINNAT, slug
    assert reader.tier(slug) in ("free", "premium"), slug
    assert reader.phrase(slug), slug
