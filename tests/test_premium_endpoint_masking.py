"""Portti: premium-tyokalun endpoint ei saa palauttaa premium-sisaltoa
kirjautumattomalle.

🔴 SAMA VIKALUOKKA NELJASTI:
  15.8  `/api/fantasy/captain` palautti top3:n JA differentiaalin anonyymille
  2.9   `/api/fantasy/replacements` palautti koko listan anonyymille
  4.9   `/api/fantasy/differentials` palautti 20 riviä + template_missing ja
        `/api/fantasy/value` 20 riviä + koko GK-lohkon anonyymille
  12.9  `/api/fantasy/defcon-leaders` palautti 182 (season) / 377 (window)
        riviä anonyymille vaikka "Full DefCon leaderboard" on myyty
        premiumina; SPA ja mobiili leikkasivat listan kolmeen itse

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
#   "lock"     17.10: ajastettu kytkin `personal_tools_mask_applies(request)`
#              JA maskifunktio samassa haarassa (pelkka kytkin ei typista)
MECHANISMS = {
    "mask": r"mask_\w+_payload",
    "truncate": r"if not premium|if not is_premium_request",
    "builder": r"premium=is_premium_request",
    # Ikkuna 1500 merkkia: differentials laskee lipun ennen listan
    # rakentamista ja maskaa sen jalkeen (joukkuetta ei haeta lukitulle).
    "lock": (r"personal_tools_mask_applies\(request\)[\s\S]{0,1500}?"
             r"return mask_\w+_payload\("),
}

#: Premium-tarkistuksen todiste rungossa. 17.10: henkilokohtaisen tyokalun
#: kytkin kutsuu is_premium_requestia api.premiumin sisalla.
PREMIUM_CHECKS = ("is_premium_request", "personal_tools_mask_applies(request)")

PREMIUM_ENDPOINTS = {
    "/api/fantasy/xp": ("per-gameweek xP on premium-listan ensimmainen rivi", "mask"),
    "/api/fantasy/plan": ("six-gameweek planner", "mask"),
    "/api/fantasy/plan-chains": ("transfer plans, hits counted", "truncate"),
    "/api/fantasy/chip-ev": ("chip timing windows", "truncate"),
    "/api/fantasy/edge": ("edge mode, rank-aware picks", "truncate"),
    # 17.10 ilta: "mask" -> "lock". Entryn kanssa (oma XI) kytkimen jalkeen
    # nolla rivia (mask_captain_entry_payload); ilman entrya 15.8-maski
    # (mask_captain_payload, yksi valinta) pysyy.
    "/api/fantasy/captain": ("captain ranker: differential + bonus; oman "
                             "XI:n kapteeni lukittu", "lock"),
    "/api/fantasy/replacements": ("who replaces a player", "mask"),
    "/api/fantasy/value": ("player value + goalkeeper rotation pairs", "mask"),
    "/api/fantasy/wildcard-plan": ("wildcard draft is part of the planner", "truncate"),
    "/api/fantasy/xp.csv": ("CSV export on premium-listan rivi", "truncate"),
    "/api/fantasy/model-race": ("mallin rivi vs oma kausi, premium-erittelyt", "builder"),
    # 6.9: player stats - FPL:n luvut ja freeze-vertailu ilmaisia, eteenpain
    # katsova xP (next_gw_xp, xp_horizon_total) premium; rakentaja maskaa.
    "/api/fantasy/player-stats": ("next-gameweek and horizon xP need premium", "builder"),
    # 17.9: "Full DefCon leaderboard" on myyty premiumina (fpl.html,
    # build_fpl_page.py, llms.txt, mobiilin paywall-bulletit, SPA-teaser);
    # free = top 3, sama luku jonka klientit jo nayttivat.
    "/api/fantasy/defcon-leaders": ("full DefCon leaderboard, top 3 free", "mask"),
    # 18.9 COMPARE-PALVELINRAJA: "player compare for up to four players" on
    # Premium-lause viidella julkisella pinnalla (faq.html:34/62/94,
    # fpl.html:47, index.html:48/66/117), rekisterin tier on premium ja
    # molemmat klientit piilottavat tyokalun ilmaiskayttajalta kokonaan --
    # mutta anonyymi `?players=411,426` palautti 2 taytta rivia + verdictin
    # (mitattu livena 18.9 13:40 UTC). Seitsemas kerta tata vikaluokkaa.
    "/api/fantasy/compare": ("player compare for up to four players", "mask"),
    # --- 17.10.2026 VILLEN PAATOS "tyokalut taakse": henkilokohtaiset
    # FPL-tyokalut Premiumiin (spec goaliq-app cos-reports/2026-10-17-
    # tyokalut-maksumuuriin-spec.md). Yhdeksan reittia siirtyi
    # FREE_ENDPOINTSista tanne. Mekanismi on ajastettu kytkin
    # (`personal_tools_mask_applies`, PERSONAL_TOOLS_ENFORCE_FROM 21.10.2026,
    # jotta mobiilin OTA ehtii levita) + maskifunktio. Ajonaikainen todennus
    # ennen/jalkeen kytkimen: tests/test_personal_tools_lock.py.
    "/api/fantasy/rate-team": ("rate my team: arvosana on esimaku, pitch, "
                               "kapteeni, siirrot ja hold-verdikti Premium",
                               "lock"),
    "/api/fantasy/model-squad": ("Team 2 -vertailu (mallin runko vertailuun) "
                                 "on Premium; sama runko jaa julkiseksi "
                                 "/fpl/model-xi-sivulle", "lock"),
    # 4.9-linja ("rehellisyyspinta ei maksumuurin taakse") korvattu 17.10:
    # mallin OMA julkinen tarkkuus jaa ilmaiseksi (track record, kutsuloki),
    # kayttajan oman rivin katsaus ja kirjanpito ovat Premium-tyokaluja.
    "/api/fantasy/gw-review": ("oman kierroksen katsaus on Premium", "lock"),
    "/api/fantasy/my-team-ledger": ("season ledger on Premium", "lock"),
    "/api/fantasy/fit": ("fit checker on Premium", "lock"),
    "/api/fantasy/defcon-live": ("oman rungon live-DefCon on Premium", "lock"),
    "/api/fantasy/h2h": ("mini-league head-to-head win probability on "
                         "Premium; sarjataulukko jaa ilmaiseksi", "lock"),
    # Julkinen lista jaa ilmaiseksi, vain `entry` (oma joukkue) on Premium.
    "/api/fantasy/price-watch": ("oman joukkueen omistusmerkinnat Premium, "
                                 "julkinen hintalista ilmainen", "lock"),
    # Julkinen lista jaa ilmaiseksi (Bluesky-vastausmoduuli hakee sen
    # anonyymina, scripts/build_reply_module.py), vain oman joukkueen
    # suodatus on Premium.
    "/api/fantasy/differentials": ("oman joukkueen suodatus Premium, "
                                   "julkinen lista ilmainen", "lock"),
}

# endpoint -> miksi se on tarkoituksella ilmainen
FREE_ENDPOINTS = {
    "/api/fantasy/defcon-gw": "sama julkinen data (per-GW-matriisi, ei ranking)",
    "/api/fantasy/xg-leaders": "xG-leaders on free (landing lupaa sen)",
    # 17.10: sarjataulukko jaa ilmaiseksi (spec rivi 11); payloadissa ei ole
    # voittotodennakoisyys- eika rival-kenttia. H2h on erillinen reitti.
    "/api/fantasy/league": "mini-league standings on free",
    "/api/fantasy/career": "career card on free",
    "/api/fantasy/model-captain": "mallin kapteeni on jo julkinen /fpl:n "
                                  "kutsulokissa (22.9); 17.10 spec rivi 3: "
                                  "mallin oma kapteeni jaa sisalloksi",
    "/api/fantasy/rival": "\"Catch your rival\" otsikko on ilmainen, "
                          "erittely jo Premium (builder-maski, 17.10 ennallaan)",
    "/api/fantasy/defcon": "FPL:n omaa julkista otteludataa (koodin oma "
                           "perustelu: ei mallin tuotoksia -> ei maskia)",
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
    if not any(c in body for c in PREMIUM_CHECKS):
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


def test_negatiivinen_kontrolli_lock_ilman_maskia() -> None:
    """17.10: "lock"-mekanismi vaatii kytkimen JA maskifunktion. Pelkka
    kytkinkutsu (tai maski ilman kytkinta) ei kelpaa."""
    body = _find_handler("/api/fantasy/fit")
    assert body and re.search(MECHANISMS["lock"], body), "fit ei kayta lockia"
    ilman_maskia = body.replace("return mask_fit_payload(payload)",
                                "return payload")
    assert re.search(MECHANISMS["lock"], ilman_maskia) is None
    ilman_kytkinta = body.replace("personal_tools_mask_applies(request)",
                                  "False")
    assert re.search(MECHANISMS["lock"], ilman_kytkinta) is None
    assert not any(c in ilman_kytkinta for c in PREMIUM_CHECKS), (
        "fitin ainoa premium-tarkistus on kytkin; sen poisto on loydyttava")
