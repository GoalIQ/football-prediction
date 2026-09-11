"""DRAFT-COMPARE-OTSIKKORIVI (11.9.2026): `meta.chips` rate-teamin
vastauksessa.

Otsikkorivi (SquadHeaderRow) nayttaa pelatut ja jaljella olevat chipit
samalla rivilla kuin ratingin, ITB:n ja FT:n. Testit lukitsevat SOPIMUKSEN,
koska mobiili lukee samat kentat:

  (a) entry jolla on pelattuja chippeja -> {"played": [{"name","gw"}, ...],
      "remaining": [{name, from_gw, available_now}, ...]} FPL:n omilla
      nimilla, pelattu chip EI ole remainingissa samalla kauden puolikkaalla,
  (b) draft (manual-moodi, ei entrya) -> `chips` on None, EI tyhja objekti:
      tyhja lista olisi vaite "ei chippeja pelattu", eika sita tiedeta,
  (c) historian puuttuminen (FPL 404) ei kaada ratea eika keksi chippeja,
  (d) free-maski paastaa chipit lapi: ne ovat kayttajan omaa julkista dataa,
  (e) sama lukija kuin chip timingilla -> toisen kauden puolikkaan ikkuna
      pysyy remainingissa vaikka ensimmainen on kaytetty.

Hermeettinen: jaettu _mock_fpl-fixture (entry 424242), jonka paalle
kirjoitetaan oma _fetch_fpl joka osaa myos /history/-polun.
"""
from __future__ import annotations

import src.models.fpl_rate_team as rt
from api.premium import mask_rate_team_payload
from src.models import fpl_chips
from tests.test_fpl_rate_team import (  # noqa: F401 — _mock_fpl-fixture kayttoon
    FAKE_BOOTSTRAP, FAKE_PICKS, SQUAD_IDS, _mock_fpl,
)

# Kauden 2026/27 kahden puolikkaan ikkunat (sama muoto kuin bootstrap-static
# `chips`; mitattu 3.9 FPL:n API:sta). Pooli/eventit tulevat jaetusta
# fixturesta, joten vain `chips` lisataan.
BOOT_WITH_CHIPS = dict(
    FAKE_BOOTSTRAP,
    chips=[
        {"name": "wildcard", "start_event": 2, "stop_event": 19},
        {"name": "wildcard", "start_event": 20, "stop_event": 38},
        {"name": "freehit", "start_event": 2, "stop_event": 19},
        {"name": "freehit", "start_event": 20, "stop_event": 38},
        {"name": "bboost", "start_event": 1, "stop_event": 19},
        {"name": "bboost", "start_event": 20, "stop_event": 38},
        {"name": "3xc", "start_event": 1, "stop_event": 19},
        {"name": "3xc", "start_event": 20, "stop_event": 38},
    ],
)


def _history(chips, transfers=0):
    return {
        "current": [{"event": 1, "event_transfers": transfers}],
        "chips": chips,
    }


def _patch(monkeypatch, history, bootstrap=BOOT_WITH_CHIPS):
    """Jaetun fixturen _fetch_fpl + /history/. history=None -> 404."""
    def fake_fetch(path):
        if path == "/bootstrap-static/":
            return bootstrap
        if path == "/entry/424242/":
            return {"id": 424242}
        if path == "/entry/424242/event/1/picks/":
            return FAKE_PICKS
        if path == "/entry/424242/history/":
            if history is None:
                raise rt.RateTeamError(404, "Not found on the FPL API.")
            return history
        raise rt.RateTeamError(404, "Not found on the FPL API.")

    monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
    rt._FPL_CACHE.clear()


def test_entry_with_played_chips(monkeypatch):
    """(a) Pelattu chip nakyy kierroksineen eika ole enaa tarjolla."""
    _patch(monkeypatch, _history([{"name": "wildcard", "event": 2},
                                  {"name": "3xc", "event": 3}]))
    chips = rt.rate_team(entry=424242)["meta"]["chips"]
    assert chips["played"] == [{"name": "wildcard", "gw": 2},
                               {"name": "3xc", "gw": 3}]
    # bboost/freehit koskematta -> tarjolla. wildcard/3xc: ensimmainen
    # puolikas kaytetty mutta TOINEN (GW20-38) on yha pelattavissa, joten
    # ne ovat remainingissa kerran. Sama saanto kuin chip timingilla.
    assert _nimet(chips) == ["wildcard", "bboost", "3xc", "freehit"]


def test_no_chips_played_is_empty_list_not_null(monkeypatch):
    """Entry jolla on historia muttei chippeja: `played` on tyhja lista.
    None on varattu "ei tietoa" -tilalle, ja ero on pinnalla nakyva."""
    _patch(monkeypatch, _history([]))
    chips = rt.rate_team(entry=424242)["meta"]["chips"]
    assert chips["played"] == []
    assert _nimet(chips) == ["wildcard", "bboost", "3xc", "freehit"]


def _nimet(chips: dict) -> list[str]:
    return [r["name"] for r in chips["remaining"]]


def test_pelattu_chip_ei_lue_kaytettavissa_olevana_ilman_kierrosta():
    """🔴 JULKAISUPORTIN LOYDOS 11.9.2026. Ensimmainen versio palautti
    `remaining`issa pelkan nimen, ja koska kaudella 2026/27 jokaisella
    chipilla on kaksi ikkunaa, GW4:ssa jo pelattu wildcard palasi listalle.
    Rivi renderoitui kahdesti: kerran yliviivattuna ("WC GW2") ja kerran
    amberilla tekstilla "Still available", vaikka toinen ikkuna aukeaa
    GW20. Jokainen `remaining`-rivi kantaa nyt kierroksen ja lipun, joten
    pinta ei voi vaittaa kaytettavyytta jota ei ole."""
    hist = _history([{"name": "wildcard", "event": 2}, {"name": "3xc", "event": 3}])
    chips = fpl_chips.chips_payload(BOOT_WITH_CHIPS, hist, 4)
    rivit = {r["name"]: r for r in chips["remaining"]}
    assert {"wildcard", "3xc"} <= set(rivit)
    for nimi in ("wildcard", "3xc"):
        assert rivit[nimi]["available_now"] is False, nimi
        assert rivit[nimi]["from_gw"] == 20, nimi
    # Kontrolli: toisen puolikkaan sisalla sama chip ON kaytettavissa nyt.
    myohemmin = {r["name"]: r
                 for r in fpl_chips.chips_payload(BOOT_WITH_CHIPS, hist, 21)["remaining"]}
    assert myohemmin["wildcard"]["available_now"] is True


def test_past_window_unplayed_chip_is_not_remaining():
    """(e) Kokonaan menneisyydessa oleva ikkuna ei ole tarjolla vaikka
    chippia ei pelattu. Ilman `current_gw`-ehtoa rivi lupaisi chipin jota ei
    enaa voi pelata. Mitataan suoraan lukijalta ja usealla kauden vaiheella
    (CLAUDE.md 6a, mekanismi 3): pelkka "nyt on GW1" -ajo olisi vihrea
    siihen asti kun se lakkaa olemasta tosi."""
    boot = dict(FAKE_BOOTSTRAP,
                chips=[{"name": "bboost", "start_event": 1, "stop_event": 3},
                       {"name": "bboost", "start_event": 20,
                        "stop_event": 38}])
    hist = _history([])
    # Muut kolme chippia perivat fallback-ikkunan (1, 38), joten vaite
    # kohdistetaan siihen jonka ikkunat testi maarittelee.
    assert "bboost" in _nimet(fpl_chips.chips_payload(boot, hist, 1))
    assert "bboost" in _nimet(fpl_chips.chips_payload(boot, hist, 3))
    # GW5: ensimmainen ikkuna on ohi, toinen ei ole viela auki mutta on
    # tulossa -> chip on yha pelattavissa kaudella.
    assert "bboost" in _nimet(fpl_chips.chips_payload(boot, hist, 5))
    # GW39: kumpikaan ikkuna ei ole enaa pelattavissa, eika yhdenkaan muun
    # chipin fallback-ikkuna (1, 38) ulotu sinne.
    assert _nimet(fpl_chips.chips_payload(boot, hist, 39)) == []


def test_draft_has_null_chips():
    """(b) Manual-moodissa (rate my draft) ei ole entrya -> ei chip-tietoa."""
    out = rt.rate_team(players=SQUAD_IDS)
    assert out["meta"]["mode"] == "manual"
    assert out["meta"]["chips"] is None
    assert out["meta"]["free_transfers"] is None


def test_history_404_is_fail_safe(monkeypatch):
    """(c) FPL:n 404 historiassa ei kaada ratea eika keksi chippeja."""
    _patch(monkeypatch, None)
    out = rt.rate_team(entry=424242)
    assert out["meta"]["chips"] is None
    assert out["meta"]["free_transfers"] is None
    assert len(out["team"]["players"]) == 15


def test_free_mask_keeps_chips(monkeypatch):
    """(d) Chipit ovat kayttajan omaa julkista FPL-dataa, eivat mallin
    tuotos -> free-maski ei saa pudottaa niita. Maski on `meta`-dictin
    kopio, joten tama testi kaatuu jos maskista tulee sallittujen
    avainten lista."""
    _patch(monkeypatch, _history([{"name": "wildcard", "event": 2}]))
    payload = rt.rate_team(entry=424242)
    masked = mask_rate_team_payload(payload)
    assert masked["meta"]["chips"] == payload["meta"]["chips"]
    assert masked["meta"]["free_transfers"] == payload["meta"]["free_transfers"]
    assert masked["transfers"]["suggestions"] == []
