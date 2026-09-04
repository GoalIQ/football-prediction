"""Portti: premium-tyokalun endpoint ei saa palauttaa premium-sisaltoa
kirjautumattomalle.

🔴 SAMA VIKALUOKKA KOLMESTI:
  15.8  `/api/fantasy/captain` palautti top3:n JA differentiaalin anonyymille
  2.9   `/api/fantasy/replacements` palautti koko listan anonyymille
  4.9   `/api/fantasy/differentials` palautti 20 riviä + template_missing ja
        `/api/fantasy/value` 20 riviä + koko GK-lohkon anonyymille

Joka kerta portti oli VAIN SELAIMESSA: SPA renderoi tyokalun `{#if premium}`
tai leikkasi listan klientissa, ja suora API-kutsu sai koko sisallon. UI:n
piilotus ei ole portti — linkki ja endpoint ovat julkisia.

MITATTU 4.9 tuotannosta (`PREMIUM_ENFORCE` on paalla): edge, chip-ev,
plan-chains, wildcard-plan, model-race, xp, plan, captain ja replacements
palauttivat maskatun vastauksen anonyymille; differentials ja value eivat.
Julkaisuportti epaili ensin kolmea vaaraa endpointia — mittaus osoitti kaksi
oikeaa. Siksi tama testi lukee **koodia**, ei arvausta: jokaisella
premium-listalla olevalla endpointilla on oltava sek. `is_premium_request`
etta maski.

Poikkeuslista on perusteltu (saanto 6a kohta 2): uusi endpoint ei paase
listalle vahingossa, ja vapaaksi merkitylle on kirjoitettava syy.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1] / "api"

# endpoint -> (miksi premium, MILLA MEKANISMILLA se on portitettu)
#
# Mekanismi on osa poikkeuslistaa tarkoituksella: "jotenkin se on portitettu"
# ei ole tarkistettava vaite. Kolme sallittua muotoa:
#   "mask"     handleri kutsuu mask_<x>_payloadia
#   "truncate" handleri leikkaa vastauksen itse (`if not premium:`)
#   "builder"  premium-lippu menee rakentajalle (`premium=is_premium_request`)
MECHANISMS = {
    "mask": r"mask_\w+_payload",
    "truncate": r"if not premium|if not is_premium_request",
    "builder": r"premium=is_premium_request",
}

PREMIUM_ENDPOINTS = {
    "/api/fantasy/xp": ("per-gameweek xP on premium-listan ensimmainen rivi", "mask"),
    "/api/fantasy/plan": ("six-gameweek planner", "mask"),
    "/api/fantasy/plan-chains": ("transfer plans, hits counted", "truncate"),
    "/api/fantasy/chip-ev": ("chip timing windows", "truncate"),
    "/api/fantasy/edge": ("edge mode, rank-aware picks", "truncate"),
    "/api/fantasy/captain": ("captain ranker: differential + bonus", "mask"),
    "/api/fantasy/replacements": ("who replaces a player", "mask"),
    "/api/fantasy/value": ("player value + goalkeeper rotation pairs", "mask"),
    "/api/fantasy/wildcard-plan": ("wildcard draft is part of the planner", "truncate"),
    "/api/fantasy/xp.csv": ("CSV export on premium-listan rivi", "truncate"),
    "/api/fantasy/model-race": ("mallin rivi vs oma kausi, premium-erittelyt", "builder"),
}

# endpoint -> miksi se on tarkoituksella ilmainen
FREE_ENDPOINTS = {
    "/api/fantasy/rate-team": "rate my team on myyntilistan FREE-puolella",
    "/api/fantasy/fit": "fit checker on free",
    "/api/fantasy/price-watch": "price watch on free",
    "/api/fantasy/defcon-live": "FPL:n omaa julkista otteludataa",
    "/api/fantasy/defcon-gw": "sama julkinen data",
    "/api/fantasy/defcon-leaders": "sama julkinen data",
    "/api/fantasy/xg-leaders": "xG-leaders on free (landing lupaa sen)",
    "/api/fantasy/league": "mini-league standings on free",
    "/api/fantasy/career": "career card on free",
    "/api/fantasy/model-squad": "mallin oma joukkue on julkinen",
    "/api/fantasy/compare": "compare on free-pinnalla",
    "/api/fantasy/rival": "\"Catch your rival\" on myyntilistan FREE-puolella",
    "/api/fantasy/h2h": "mini-league head-to-head win probability on free",
    "/api/fantasy/defcon": "FPL:n omaa julkista otteludataa (koodin oma "
                           "perustelu: ei mallin tuotoksia -> ei maskia)",
    # 🔴 RISTIRIITA, EI RATKAISU (4.9): nama kaksi renderoityvat omassa
    # UI:ssamme ILMAN premium-vahtia (RateTeam weekMode), mutta landingin
    # premium-lista lupaa ne premiumina ("Where the gap came from:
    # captaincy, bench points and autosubs round by round"). Maskaaminen
    # POISTAISI ne omalta ilmaispinnalta, joten oikea korjaus on paattaa
    # kumpi puoli on totta — se on Villen paatos, ei portin. Jonorivi
    # GW-REVIEW-MYYNTIRAJA. Merkitaan freeksi koska niin ne KAYTTAYTYVAT.
    "/api/fantasy/gw-review": "renderoityy vapaasti omassa UI:ssa; "
                              "myyntilista on eri mielta -> GW-REVIEW-MYYNTIRAJA",
    "/api/fantasy/my-team-ledger": "sama ristiriita kuin gw-review",
    # 🔴 MITATTU SYY, EI UNOHDUS (4.9): julkisen /fpl/differentials-sivun
    # generaattori hakee taman CI:sta ANONYYMINA ja nielee virheen
    # varoituksella. Maski olisi pudottanut sivun 20 rivista kahteen HILJAA.
    # Sivun oma copy myy loput premiumina ("+19 more in Premium").
    "/api/fantasy/differentials": "julkisen sivun datalahde, anonyymi "
                                  "CI-haku -> DIFFERENTIALS-MYYNTIRAJA",
}


def _sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in API.glob("*.py")}


def _handler_body(src: str, route: str) -> str | None:
    """Reitin dekoraattorista seuraavaan dekoraattoriin."""
    m = re.search(rf'@(?:app|router)\.get\(\s*"{re.escape(route)}"', src)
    if not m:
        return None
    rest = src[m.start():]
    nxt = re.search(r"\n@(?:app|router)\.(?:get|post)\(", rest[10:])
    return rest[: nxt.start() + 10] if nxt else rest


def _find_handler(route: str) -> str | None:
    for src in _sources().values():
        body = _handler_body(src, route)
        if body:
            return body
    return None


def _mask_problem(route: str, mechanism: str) -> str | None:
    body = _find_handler(route)
    if body is None:
        return f"{route}: reittia ei loydy api/-lahteesta"
    if "is_premium_request" not in body:
        return f"{route}: ei kysy is_premium_requestia"
    pattern = MECHANISMS.get(mechanism)
    if pattern is None:
        return f"{route}: tuntematon mekanismi {mechanism!r}"
    if not re.search(pattern, body):
        return (f"{route}: taulukko lupaa mekanismin {mechanism!r} mutta "
                "handlerissa ei ole sita")
    return None


# --------------------------------------------------------------------------


def test_lahteet_loytyvat() -> None:
    """Ilman tata koko portti menisi lapi tyhjana jos api/-polku muuttuu."""
    srcs = _sources()
    assert "main.py" in srcs and len(srcs) >= 2
    assert _find_handler("/api/fantasy/xp"), "tunnettu reitti ei loydy"


@pytest.mark.parametrize("route", sorted(PREMIUM_ENDPOINTS))
def test_premium_endpoint_maskaa(route: str) -> None:
    syy, mekanismi = PREMIUM_ENDPOINTS[route]
    ongelma = _mask_problem(route, mekanismi)
    assert ongelma is None, (
        f"{ongelma}. {route} on myyty premiumina ({syy}), "
        "eika UI:n piilotus ole portti: linkki ja endpoint ovat julkisia. "
        "Sama vikaluokka on loytynyt 15.8, 2.9 ja 4.9."
    )


@pytest.mark.parametrize("route", sorted(FREE_ENDPOINTS))
def test_ilmaiselle_endpointille_on_perustelu(route: str) -> None:
    assert FREE_ENDPOINTS[route].strip(), f"{route}: syyta ei ole kirjattu"


def test_jokainen_fantasy_reitti_on_luokiteltu() -> None:
    """Uusi endpoint ei saa jaada luokittelematta: silloin kukaan ei ole
    paattanyt kumpaa puolta se on."""
    routes = set()
    for src in _sources().values():
        routes |= set(re.findall(r'@(?:app|router)\.get\(\s*"(/api/fantasy[^"]*)"', src))
    luokiteltu = set(PREMIUM_ENDPOINTS) | set(FREE_ENDPOINTS)
    # Polkuparametrilliset reitit normalisoidaan (esim. /league/{id}).
    tuntemattomat = sorted(
        r for r in routes
        if r.split("/{")[0] not in luokiteltu and r not in luokiteltu
        and r != "/api/fantasy"
    )
    assert not tuntemattomat, (
        f"nama fantasy-reitit eivat ole PREMIUM_ENDPOINTS- eivatka "
        f"FREE_ENDPOINTS-listalla: {tuntemattomat}. Lisaa listalle "
        "PERUSTELUN kanssa — kumpaa puolta myyntilupausta tama on?"
    )


# --------------------------------------------------------------------------
# Negatiiviset kontrollit
# --------------------------------------------------------------------------


def test_negatiivinen_kontrolli_maski_katoaa() -> None:
    body = _find_handler("/api/fantasy/value")
    assert body
    rikottu = body.replace("mask_value_payload", "identity")
    assert re.search(MECHANISMS["mask"], rikottu) is None, (
        "tarkistin ei huomaisi maskin katoamista"
    )


def test_negatiivinen_kontrolli_vaara_mekanismi() -> None:
    """Taulukon mekanismi on vaite, ei koriste: jos se on vaarin, portin on
    kaaduttava. Muuten "jotenkin portitettu" menisi lapi."""
    assert _mask_problem("/api/fantasy/value", "builder") is not None


def test_negatiivinen_kontrolli_premium_check_katoaa() -> None:
    body = _find_handler("/api/fantasy/value")
    assert body
    rikottu = body.replace("is_premium_request", "True")
    assert "is_premium_request" not in rikottu
