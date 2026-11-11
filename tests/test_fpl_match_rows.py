"""PL-fitin ottelurivit FPL:n datasta (11.11.2026, Understat-katko 1.11-).

Invariantit (saanto 6a):
1. Kotipuoli luetaan rivin `was_home`-kentasta. Pelaajan NYKYINEN joukkue ei vaikuta: kesken kauden siirtynyt
   pelaaja kirjautuu sen seuran otteluun, jossa han pelasi (team_xg_by_fixture summaa nykyisen joukkueen mukaan).
2. Vajaa puoli (hakematon summary), ristiriitainen tulos tai tuntematon joukkue = ottelu pois, ei vaaraa xG:ta.
3. Kattavuusportti: jos pelatuista otteluista puuttuu enemman kuin sallittu, kausi palautuu tyhjana syyn kanssa,
   ja lukija (lataa_pl_fit_data) kieltaytyy.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from src.data import fpl_api, fpl_match_xg
from src.data.fpl_match_xg import aggregate_matches, season_match_frame

NAMES = {1: "Arsenal", 2: "Everton", 3: "Manchester City"}


def _row(fixture, was_home, opp, xg, minutes=90, hs=2, as_=1, ko="2026-10-18T14:00:00Z"):
    return {"fixture": fixture, "was_home": was_home, "opponent_team": opp, "expected_goals": f"{xg:.2f}",
            "minutes": minutes, "team_h_score": hs, "team_a_score": as_, "kickoff_time": ko}


def _side(fixture, was_home, opp, xg_each, n=11, **kw):
    return [{"history": [_row(fixture, was_home, opp, xg_each, **kw)]} for _ in range(n)]


def test_kotipuoli_rivin_kentasta_eika_nykyisesta_joukkueesta():
    docs = _side(10, True, 2, 0.2) + _side(10, False, 1, 0.1)
    # Siirtynyt pelaaja: pelasi Arsenalissa (koti, vastustaja Everton), nyt toisessa seurassa.
    docs.append({"history": [_row(10, True, 2, 0.5, minutes=20)]})
    rows, dropped = aggregate_matches(docs, NAMES)
    assert dropped == []
    (r,) = rows
    assert (r["home_team"], r["away_team"]) == ("Arsenal", "Everton")
    assert (r["home_score"], r["away_score"]) == (2, 1)
    assert r["home_xg"] == pytest.approx(11 * 0.2 + 0.5) and r["away_xg"] == pytest.approx(1.1)
    assert r["date"] == "2026-10-18"


def test_pelaamaton_ottelu_ei_ole_rivi():
    docs = [{"history": [_row(11, True, 2, 0.3, hs=None, as_=None)]}]
    assert aggregate_matches(docs, NAMES) == ([], [])


def test_vajaa_puoli_ristiriita_ja_tuntematon_joukkue_pudotetaan():
    vajaa = _side(1, True, 2, 0.1, n=9) + _side(1, False, 1, 0.1)          # 810 min kotipuolella
    ristiriita = _side(2, True, 2, 0.1) + _side(2, False, 1, 0.1, hs=0, as_=0)
    tuntematon = _side(3, True, 9, 0.1) + _side(3, False, 1, 0.1)           # id 9 ei kauden bootstrapissa
    rows, dropped = aggregate_matches(vajaa + ristiriita + tuntematon, NAMES)
    assert rows == []
    syyt = {d["fixture"]: d["syy"] for d in dropped}
    assert "pelaajaminuutteja" in syyt[1] and "ristiriitainen" in syyt[2] and "bootstrapissa" in syyt[3]


def _kirjoita(tmp_path, kausi, docs):
    d = tmp_path / f"summary_{kausi}"
    d.mkdir(parents=True)
    for i, doc in enumerate(docs):
        (d / f"element_{i + 1}.json").write_text(json.dumps(doc), encoding="utf-8")


def _live(monkeypatch, tmp_path, docs, finished):
    _kirjoita(tmp_path, "2627", docs)
    boot = {"events": [{"deadline_time": "2026-08-21T17:30:00Z"}],
            "teams": [{"id": k, "name": {3: "Man City"}.get(k, v)} for k, v in NAMES.items()],
            "elements": []}
    monkeypatch.setattr(fpl_match_xg, "SUMMARY_DIR", tmp_path)
    monkeypatch.setattr(fpl_api, "fetch_bootstrap", lambda *a, **k: boot)
    haut = []
    monkeypatch.setattr(fpl_api, "fetch_all_summaries", lambda b, force=False, **k: haut.append(force) or {})
    monkeypatch.setattr(fpl_api, "fetch_fixtures",
                        lambda *a, **k: [{"id": i, "finished": i <= finished} for i in range(1, 39)])
    return haut


def test_kuluva_kausi_mallinimin_ja_tuore_haku(monkeypatch, tmp_path):
    docs = _side(1, True, 3, 0.2) + _side(1, False, 1, 0.1)
    haut = _live(monkeypatch, tmp_path, docs, finished=1)
    df = season_match_frame("2627")
    assert haut == [True]  # ei viela haettu tuoreena tassa prosessissa
    assert list(df["home_team"]) == ["Arsenal"] and list(df["away_team"]) == ["Manchester City"]
    assert set(df["lahde"]) == {"FPL-Opta"} and set(df["season"]) == {"2627"}
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_kattavuusportti_palauttaa_tyhjan_syyn_kanssa(monkeypatch, tmp_path):
    docs = _side(1, True, 2, 0.2) + _side(1, False, 1, 0.1)
    _live(monkeypatch, tmp_path, docs, finished=10)   # 1/10 pelatusta ottelusta
    df = season_match_frame("2627")
    assert df.empty and "1/10" in df.attrs["virhe"]


def test_kerran_tuoreena_haettu_ei_hae_uudelleen(monkeypatch, tmp_path):
    docs = _side(1, True, 2, 0.2) + _side(1, False, 1, 0.1)
    haut = _live(monkeypatch, tmp_path, docs, finished=1)
    monkeypatch.setattr(fpl_api, "haettu_tuoreena", lambda k: k == "2627")
    season_match_frame("2627")
    assert haut == [False]


def test_paattynyt_kausi_arkistosta_ja_puuttuva_arkisto_on_syy(monkeypatch, tmp_path):
    boot_live = {"events": [{"deadline_time": "2026-08-21T17:30:00Z"}], "teams": [], "elements": []}
    monkeypatch.setattr(fpl_match_xg, "SUMMARY_DIR", tmp_path)
    monkeypatch.setattr(fpl_api, "fetch_bootstrap", lambda *a, **k: boot_live)
    monkeypatch.setattr(fpl_api, "fetch_all_summaries", lambda *a, **k: pytest.fail("arkistoa ei haeta"))
    df = season_match_frame("2526")
    assert df.empty and "arkistoa" in df.attrs["virhe"]
    # Kahden joukkueen arkisto: odotettu 2 ottelua, molemmat levylla.
    arkisto = {"events": [{"deadline_time": "2025-08-15T17:30:00Z"}],
               "teams": [{"id": 1, "name": "Arsenal"}, {"id": 2, "name": "Everton"}]}
    (tmp_path / "bootstrap_static_2526.archive.json").write_text(json.dumps(arkisto), encoding="utf-8")
    docs = (_side(1, True, 2, 0.2) + _side(1, False, 1, 0.1)
            + _side(2, True, 1, 0.3, ko="2026-02-01T15:00:00Z") + _side(2, False, 2, 0.1, ko="2026-02-01T15:00:00Z"))
    _kirjoita(tmp_path, "2526", docs)
    df = season_match_frame("2526")
    assert len(df) == 2 and set(df["season"]) == {"2526"}
    assert list(df["home_team"]) == ["Everton", "Arsenal"]  # pvm-jarjestys: helmikuu ensin
