# -*- coding: utf-8 -*-
"""XG-KAUSI-SARAKE (27.8): builderin rivit kantavat kuluvan kauden totaalit.

Tausta: `season`-lohkon kirjoitti vain refresh_current_attrs (esikausihaara).
GW1:n jalkeen build() ajoi ilman sita -> Season-ikkuna nollia 477/477
rivilla, SPA/mobiili piilottivat nakyman, ja basis-lause lupasi silti
"the season column is 2026/27 so far". Nama testit vartioivat etta
_player_rows emittoi lohkon AINA ja etta kausivaihto-merge sailyttaa sen
(rullaava data voi olla viime kautta, totaalit ovat aina kuluvaa).
"""
from __future__ import annotations

from scripts.build_fpl_player_leaders import _player_rows, _season_block


def _boot():
    return {
        "teams": [{"id": 1, "short_name": "LIV"}, {"id": 2, "short_name": "IPS"}],
        "elements": [
            {"id": 379, "code": 219168, "web_name": "Isak", "team": 1,
             "element_type": 4, "now_cost": 90, "selected_by_percent": "16.6",
             "minutes": 62, "starts": 1, "expected_goals": "1.09",
             "expected_assists": "0.04", "expected_goal_involvements": "1.13"},
            {"id": 316, "code": 543968, "web_name": "Emersonn", "team": 2,
             "element_type": 4, "now_cost": 55, "selected_by_percent": "1.4",
             "minutes": 65, "starts": 1, "expected_goals": "0.82",
             "expected_assists": "0.06", "expected_goal_involvements": "0.88"},
        ],
    }


def _summaries():
    g = {"round": 1, "opponent_team": 2, "was_home": True, "minutes": 62,
         "expected_goals": "1.09", "expected_assists": "0.04",
         "expected_goal_involvements": "1.13", "defensive_contribution": 2,
         "clearances_blocks_interceptions": 1, "tackles": 1, "recoveries": 0}
    return {379: [g], 316: [dict(g, opponent_team=1, minutes=65)]}


def test_player_rows_carry_current_season_totals():
    rows = _player_rows(_boot(), _summaries(), "2026/27", keep_empty=True)
    by = {r["web_name"]: r for r in rows}
    assert by["Isak"]["season"] == {
        "mins": 62, "starts": 1, "xg": 1.09, "xa": 0.04, "xgi": 1.13}
    assert by["Emersonn"]["season"]["xg"] == 0.82


def test_season_block_is_zero_not_missing_for_unplayed():
    """Pelaamaton pelaaja saa nollalohkon, ei puuttuvaa avainta: klientit
    piilottavat Season-nakyman kun avain puuttuu, ja nolla on eri vaite."""
    e = {"minutes": None, "starts": None, "expected_goals": None,
         "expected_assists": None, "expected_goal_involvements": None}
    assert _season_block(e) == {"mins": 0, "starts": 0, "xg": 0.0,
                                "xa": 0.0, "xgi": 0.0}


def test_merge_keeps_fresh_season_totals_with_last_season_rolling(monkeypatch, tmp_path):
    """Kausivaihto-merge: alle 3 kuluvan kauden ottelua -> rullaava data on
    viime kautta (basis 2025/26) MUTTA season-lohko on kuluvaa kautta."""
    import json
    import scripts.build_fpl_player_leaders as b

    prev = {"meta": {"available": True}, "players": [{
        "id": 1, "code": 219168, "web_name": "Isak", "team_short": "LIV",
        "pos": "FWD", "price": 8.5, "owned_pct": 1.0, "games_total": 14,
        "basis": "2025/26",
        "recent_games": [{"round": 36, "opp": "X", "venue": "H", "minutes": 70,
                          "xg": 0.0, "xa": 0.0, "xgi": 0.0, "dc": 0,
                          "cbi": 0, "tkl": 0, "rec": 0}],
    }]}
    path = tmp_path / "leaders.json"
    path.write_text(json.dumps(prev), encoding="utf-8")
    monkeypatch.setattr(b, "LEADERS_PATH", path)
    monkeypatch.setattr(b, "fetch_bootstrap", _boot)
    monkeypatch.setattr(b, "fetch_all_summaries", lambda boot: _summaries())
    monkeypatch.setattr(b, "season_key_from_bootstrap", lambda boot: "2627")

    out = b.build()
    isak = next(p for p in out["players"] if p["web_name"] == "Isak")
    assert isak["basis"] == "2025/26"          # rullaava = viime kausi
    assert isak["recent_games"][0]["round"] == 36
    assert isak["season"]["xg"] == 1.09        # totaalit = kuluva kausi
    assert isak["price"] == 9.0                # attribuutit = kuluva kausi


def test_committed_artefact_obeys_the_published_basis_rule():
    """Sivun basis-lause on kaksisuuntainen vaite (27.8, julkaisuportti):
    (a) 2025/26-rivi = pelaajalla alle MIN_CURRENT_GAMES kuluvan kauden
        ottelua; artefaktissa on vain `starts`, ja starts <= pelatut, joten
        `starts < 3` on valttamaton ehto (ei riittava);
    (b) kohdekauden rivi = kaikki sen ottelut ovat kuluvaa kautta, eli
        games_total == len(recent_games) <= RECENT_KEEP eika rivi voi
        kantaa 10 viime kauden ottelua. Haara (b) mittaa vaitteen SEURAUSTA
        ("ei 25/26-dataa lainkaan" ei nay artefaktista); jos kohdekauden rivi
        saa joskus edelliskauden dataa oikean pituisena, tama ei nae sita.
    Jos merge-logiikka muuttuu, tama kaatuu ennen kuin lause vanhenee."""
    import json
    from src.models.fpl_leaders import LEADERS_PATH, MIN_CURRENT_GAMES
    if not LEADERS_PATH.exists():
        import pytest
        pytest.skip("artefaktia ei ole")
    d = json.loads(LEADERS_PATH.read_text(encoding="utf-8"))
    target = d["meta"]["target_season"]
    if d["meta"]["basis_season"] != target:
        return  # esikausi: saanto ei ole voimassa
    for p in d["players"]:
        s = p.get("season") or {}
        assert "mins" in s, f"{p['web_name']}: season-lohko puuttuu"
        if p["basis"] != target:
            assert int(s.get("starts") or 0) < MIN_CURRENT_GAMES, (
                f"{p['web_name']}: {p['basis']}-rivi mutta {s['starts']} "
                f"startia kaudella {target}")
        else:
            assert p["games_total"] == len(p["recent_games"]), (
                f"{p['web_name']}: kohdekauden rivi kantaa vierasta dataa")
