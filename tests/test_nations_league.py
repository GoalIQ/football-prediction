"""UEFA Nations League 2026/27 (Villen GO 23.9.2026).

Portit:
  * nimiresoluutio: jokainen 54 osallistujasta ja UEFAn omat kirjoitusasut
    (Türki̇ye U+0307:lla, "Bosnia and Herzegovina") osuvat mallin avaimeen,
    ei-UNL-maa ei.
  * kotietu: UNL SAILYTTAA kotiedun, WC neutraloi sen. Erotteleva pari: sama
    ottelu kaannettyna antaa UNL:lle eri luvut ja WC:lle peilatut. Jos UNL-haara
    neutraloisi vahingossa, testi kaatuu (ja painvastoin).
  * UEFAn rivit -> API-muoto synteettisilla kierrosvaiheilla (ennen kautta,
    kesken, pelattu ottelu, tuntematon joukkue), ei elavasta rajapinnasta.
  * kausi johdetaan config.current_season():sta, ei kovakoodata.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.data import nations_league as nl

TOL = 1e-9


# --- nimet --------------------------------------------------------------------
@pytest.mark.parametrize("team", nl.UNL_TEAMS)
def test_jokainen_osallistuja_resolvoituu_itseensa(team):
    assert nl.resolve_unl_name(team) == team


@pytest.mark.parametrize("raw,canon", [
    ("Türki̇ye", "Turkey"),
    ("Türkiye", "Turkey"),
    ("Bosnia and Herzegovina", "Bosnia-Herzegovina"),
    ("Ireland", "Republic of Ireland"),
    ("  czech republic ", "Czechia"),
    ("Faroes", "Faroe Islands"),
])
def test_uefan_kirjoitusasut(raw, canon):
    assert nl.resolve_unl_name(raw) == canon


@pytest.mark.parametrize("raw", ["Brazil", "Russia", "Arsenal", "", None])
def test_ei_unl_maa(raw):
    assert nl.resolve_unl_name(raw) is None


def test_54_osallistujaa_ja_kaikki_mallissa():
    assert len(nl.UNL_TEAMS) == 54 == len(nl.UNL_TEAMS_SET)
    dc = nl.load_unl_model()
    assert [t for t in nl.UNL_TEAMS if t not in dc.attack] == []


def test_kausi_johdetaan_configista(monkeypatch):
    monkeypatch.setattr(nl.config, "current_season", lambda: "2627")
    assert nl.unl_season_year() == 2027
    monkeypatch.setattr(nl.config, "current_season", lambda: "2728")
    assert nl.unl_season_year() == 2028


# --- API --------------------------------------------------------------------------
def _unl(client, home, away):
    return client.post("/api/predict-wc", json={
        "home_team": home, "away_team": away, "leagues": [nl.UNL_LEAGUE]})


def _wc(client, home, away):
    return client.post("/api/predict-wc", json={
        "home_team": home, "away_team": away,
        "leagues": ["INT-World Cup"], "seasons": ["2018", "2022"]})


def test_unl_ennuste_summautuu(client):
    r = _unl(client, "Portugal", "Wales")
    assert r.status_code == 200, r.text[:200]
    b = r.json()
    assert b["p_home_win"] + b["p_draw"] + b["p_away_win"] == pytest.approx(1.0, abs=2e-4)


def test_unl_kotietu_sailyy_wc_neutraloi(client):
    """Erotteleva pari: England-Spain molemmat ovat seka WC- etta UNL-maita."""
    a, b = _unl(client, "England", "Spain").json(), _unl(client, "Spain", "England").json()
    assert a["p_home_win"] > b["p_away_win"] + 0.02, "UNL neutraloi kotiedun"
    assert a["expected_goals_home"] > b["expected_goals_away"]
    c, d = _wc(client, "England", "Spain").json(), _wc(client, "Spain", "England").json()
    assert c["p_home_win"] == pytest.approx(d["p_away_win"], abs=TOL)


def test_unl_portti(client):
    r = _unl(client, "Brazil", "Wales")
    assert r.status_code == 404
    assert "Nations League" in r.json()["detail"]
    assert _unl(client, "Andorra", "San Marino").status_code == 200  # pienet maat mukana


def test_tuntematon_liiga_400_ja_wc_ennallaan(client):
    r = client.post("/api/predict-wc", json={
        "home_team": "Portugal", "away_team": "Wales", "leagues": ["INT-Euro"]})
    assert r.status_code == 400
    r = _wc(client, "Portugal", "Andorra")
    assert r.status_code == 404
    assert r.json()["detail"] == "Away team 'Andorra' is not a World Cup 2026 team."


def test_teams_unl(client):
    r = client.get("/api/teams", params={"leagues": nl.UNL_LEAGUE})
    assert r.status_code == 200
    assert r.json()["teams"] == sorted(nl.UNL_TEAMS)


def test_fixtures_ja_standings_unl_tyhjat_ilman_lahdetta(client):
    """3.10.2026: UNL:n ottelut ja lohkot haettiin UEFAlta; haku lopetettu.
    Reitit vastaavat 200 + tyhja (klientin tyhjatila), eivat 503:a."""
    f = client.get("/api/fixtures", params={"league": nl.UNL_LEAGUE, "days": 7})
    assert f.status_code == 200 and f.json()["fixtures"] == []
    s = client.get("/api/standings", params={"league": nl.UNL_LEAGUE})
    assert s.status_code == 200 and s.json()["groups"] == []


def test_unl_h2h_ja_joukkuekortti_kayttavat_kaikkia_otteluita(client):
    """Mallin treenidata ('any') ei sisalla pienten maiden keskinaisia
    otteluita; naytto (H2H, vire, joukkuekortti) kayttaa kaikkia."""
    import pandas as pd
    start = nl.unl_model_meta()["window_start"]
    kaikki = nl.display_data(start)
    pari = kaikki[((kaikki.home_team == "Andorra") & (kaikki.away_team == "Malta"))
                  | ((kaikki.home_team == "Malta") & (kaikki.away_team == "Andorra"))]
    treeni = nl.training_data(start)
    assert len(pari) > 0, "testidata: Andorra-Malta puuttuu ikkunasta"
    assert len(treeni[(treeni.home_team == "Andorra") & (treeni.away_team == "Malta")]) == 0
    r = _unl(client, "Andorra", "Malta").json()
    assert r["h2h_summary"] and sum(v for k, v in r["h2h_summary"].items()
                                    if isinstance(v, int)) > 0
    t = client.get("/api/team/Türki̇ye", params={"leagues": nl.UNL_LEAGUE})
    assert t.status_code == 200, t.text[:200]
    assert len(t.json()["last_5_matches"]) == 5


def test_by_date_ei_sisalla_unl_ryhmaa(client):
    """3.10.2026: UNL poistettu by-date-nakymasta (UEFA-haku lopetettu)."""
    r = client.get("/api/fixtures/by-date", params={"date": "2026-09-24"}).json()
    assert not [g for g in r["leagues"] if g["league"] == nl.UNL_LEAGUE]
