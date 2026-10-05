"""Puolustusprofiilin kuluva kausi (5.10.2026): sanity-raja, tuoreus ja
inkrementaalinen haku. Verkko korvataan valekutsuilla."""
from __future__ import annotations

import datetime as dt
import gzip
import json

import pytest

import scripts.build_understat_team_defence as B
from src.models.fpl_leaders import MIN_CURRENT_GAMES


def _data(matches: int, complete: bool) -> dict:
    row = {"team": "Arsenal", "matches": matches, "shots_pm": 8.0, "pens": 0,
           "six_pm": 1.0, "central_pm": 2.0, "wide_pm": 2.0, "edge_pm": 2.0,
           "far_pm": 1.0, "box_share": 62.5, "head_pm": 1.0}
    rows = [dict(row, team=f"T{i}") for i in range(20)]
    return {"meta": {"complete": complete, "matches_missing": 0,
                     "promoted_no_data": [], "relegated_excluded": [],
                     "n_current_teams": 20},
            "teams": rows}


def test_sanity_kesken_kauden_hyvaksyy_min_current_games():
    assert B.sanity(_data(MIN_CURRENT_GAMES, complete=False)) == []
    assert B.sanity(_data(MIN_CURRENT_GAMES - 1, complete=False))


def test_sanity_paattynyt_kausi_vaatii_koko_otoksen():
    assert B.sanity(_data(B.SANITY_MIN_MATCHES, complete=True)) == []
    assert B.sanity(_data(5, complete=True)), "5 ottelua ei kelpaa paattyneelle kaudelle"


def test_is_fresh(tmp_path):
    p = tmp_path / "d.json"
    now = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.timezone.utc)
    p.write_text(json.dumps({"meta": {"generated_at": "2026-10-05T00:00:00+00:00"}}))
    assert B.is_fresh(p, 20, now)
    assert not B.is_fresh(p, 10, now)
    # Vanha naiivi aikaleima tulkitaan UTC:ksi eika kaada.
    p.write_text(json.dumps({"meta": {"generated_at": "2026-08-08T21:21:32"}}))
    assert not B.is_fresh(p, 20, now)
    assert not B.is_fresh(tmp_path / "puuttuu.json", 20, now)


class _Resp:
    def __init__(self, body: dict, gz: bool = False):
        raw = json.dumps(body).encode()
        self.content = gzip.compress(raw) if gz else raw

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, league, matches):
        self.headers = {}
        self.calls = []
        self._league, self._matches = league, matches

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if "/getLeagueData/" in url:
            return _Resp(self._league, gz=True)
        if "/getMatchData/" in url:
            return _Resp(self._matches[int(url.rsplit("/", 1)[1])], gz=True)
        return _Resp({})


def test_fetch_hakee_vain_puuttuvat_ottelut(tmp_path, monkeypatch):
    league = {"dates": [{"id": "1", "isResult": True}, {"id": "2", "isResult": True},
                        {"id": "3", "isResult": False}],
              "teams": {}, "players": []}
    shots = {"shots": {"h": [{"xG": "0.1"}], "a": []}, "rosters": {}, "tmpl": {}}
    sess = _Session(league, {1: shots, 2: shots})
    import requests
    monkeypatch.setattr(requests, "Session", lambda: sess)
    (tmp_path / "match_1.json").write_text("{}")  # jo valimuistissa
    new, played = B.fetch_season("2627", tmp_path, sleep=0)
    assert (new, played) == (1, 2)
    assert not any(c.endswith("/getMatchData/1") for c in sess.calls)
    assert any(c.endswith("/getMatchData/2") for c in sess.calls)
    assert not any(c.endswith("/getMatchData/3") for c in sess.calls), "pelaamaton ottelu"
    saved = json.loads((tmp_path / "league_1_season_2026.json").read_text(encoding="utf-8"))
    assert len(saved["dates"]) == 3
    assert B.season_complete("2627", tmp_path) is False


def test_fetch_ottelu_ilman_laukauksia_kaatuu(tmp_path, monkeypatch):
    league = {"dates": [{"id": "9", "isResult": True}], "teams": {}, "players": []}
    sess = _Session(league, {9: {"shots": {"h": [], "a": []}}})
    import requests
    monkeypatch.setattr(requests, "Session", lambda: sess)
    with pytest.raises(RuntimeError):
        B.fetch_season("2627", tmp_path, sleep=0)
    assert not (tmp_path / "match_9.json").exists()


def test_kukaan_ei_lue_kauden_tiedostoa_lukijan_ohi():
    """Saanto 6a(2): sivu ja kortti lukivat kumpikin kovakoodattua
    `understat_team_defence_2526.json`:ia, ja siksi /fpl/defence jai 2025/26:een
    viela GW5:n jalkeen. Kauden tiedostonimi saa esiintya koodissa vain
    lukijassa ja rakentajassa; muut kutsuvat `load_defence()`ia."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sallitut = {"fpl_defence.py", "build_understat_team_defence.py"}
    bad = []
    for d in ("scripts", "api", "src"):
        for f in (root / d).rglob("*.py"):
            if f.name in sallitut:
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                koodi = line.split("#", 1)[0]
                if re.search(r"understat_team_defence_\d{4}", koodi):
                    bad.append(f"{f.relative_to(root)}:{i}")
    assert not bad, f"lue load_defence()illa: {bad}"
    src = (root / "scripts" / "build_fpl_longtail.py").read_text(encoding="utf-8")
    assert "defence = load_defence()" in src
