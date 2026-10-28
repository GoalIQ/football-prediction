"""Ottelusivu pysyy kickoffin jalkeen tulossivuna (ylläpitäjän päätös 2026-10-19).

Lukitsee: sama URL ja samat ennusteluvut ennen kickoffia, kickoffin jalkeen
ilman tulosta ja tuloksen jalkeen; sivua ei poisteta (kutsupaikka main());
saman parin myohempi ottelu saa paivasuffiksin; hub ja sitemap kasittelevat
pelatut.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from scripts import build_prediction_pages as bpp

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _entry(days: float, result=None, home="Arsenal FC", away="Chelsea FC",
           comp="PL", now=NOW) -> dict:
    ko = now + timedelta(days=days)
    return {
        "match_id": f"x-{home}-{days}", "competition": comp,
        "home_team": home, "away_team": away,
        "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": ko.strftime("%Y-%m-%d"),
        "p_home": 0.62, "p_draw": 0.21, "p_away": 0.17,
        "logged_at": "2026-10-20T10:00:00+00:00", "result": result,
    }


RESULT = {"home_score": 3, "away_score": 1, "actual_outcome": "home",
          "reconciled_at": "2026-10-27T21:00:00+00:00"}


def _probs(html: str) -> list[str]:
    return re.findall(r"\d+%", re.search(r'class="legend">(.*?)</div>', html).group(1))


def test_phases_keep_numbers_and_url():
    before = bpp.render_match_page("PL", _entry(1), NOW)
    pending = bpp.render_match_page("PL", _entry(-1), NOW)
    final = bpp.render_match_page("PL", _entry(-1, RESULT), NOW)
    assert _probs(before) == _probs(pending) == _probs(final) == ["62%", "21%", "17%"]
    canon = lambda h: re.search(r'rel="canonical" href="([^"]+)"', h).group(1)
    assert canon(before) == canon(pending) == canon(final)
    assert "Result pending" in pending and "Result pending" not in final
    assert "Full time: Arsenal FC 3-1 Chelsea FC (home win)" in final
    assert "/predictions#record" in pending and "/predictions#record" in final
    assert "Result pending" not in before and "Full time" not in before
    # Maskaus ennallaan: ei xG:ta eika tarkkaa tulosta sivulla
    assert "expected goals and scoreline probabilities on" in final


def test_numbers_come_from_log_row_only():
    e = _entry(-1, RESULT)
    e["p_home"], e["p_draw"], e["p_away"] = 0.30, 0.30, 0.40
    assert _probs(bpp.render_match_page("PL", e, NOW)) == ["30%", "30%", "40%"]


def test_rematch_gets_date_suffix_and_first_keeps_slug():
    old, new = _entry(-120, RESULT), _entry(5)
    assert bpp._assign_filenames([new, old]) == []
    assert old["_file"] == "arsenal-fc-vs-chelsea-fc.html"
    assert old["_file"] != new["_file"]
    assert new["_file"].startswith(old["_file"][:-5] + "-")


def test_hub_lists_recent_played():
    up, rec = _entry(2), _entry(-2, RESULT, home="Everton FC", away="Fulham FC")
    html = bpp.render_league_hub("PL", [up], NOW, [rec])
    assert "Played in the last 7 days" in html and "full time 3-1" in html
    assert "Played in the last" not in bpp.render_league_hub("PL", [up], NOW)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(bpp, "OUT_ROOT", tmp_path / "predictions")
    monkeypatch.setattr(bpp, "SITEMAP_PRED_PATH", tmp_path / "sitemap.xml")
    monkeypatch.setattr(bpp, "PREDICTIONS_HTML", tmp_path / "none.html")
    monkeypatch.setattr(bpp, "LLMS_TXT", tmp_path / "llms.txt")
    monkeypatch.setattr(bpp, "_deploy_file_count", lambda: 1)
    return tmp_path


def test_main_keeps_played_page_and_sitemap(sandbox, monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [_entry(3, now=now),
            _entry(-2, RESULT, home="Everton FC", away="Fulham FC", now=now),
            _entry(-1, None, home="Leeds United", away="Brentford FC", now=now)]
    monkeypatch.setattr(bpp, "_attach_confidence", lambda by_comp: 1)
    monkeypatch.setattr(bpp.acc, "load_log", lambda: {"predictions": rows})
    assert bpp.main() == 0
    out = sandbox / "predictions" / "premier-league"
    played = out / "everton-fc-vs-fulham-fc.html"
    assert played.exists() and "Full time" in played.read_text(encoding="utf-8")
    assert "Result pending" in (out / "leeds-united-vs-brentford-fc.html").read_text(encoding="utf-8")
    sm = (sandbox / "sitemap.xml").read_text(encoding="utf-8")
    assert "everton-fc-vs-fulham-fc" in sm and "<lastmod>2026-10-27</lastmod>" in sm
    # toinen ajo ei poista pelattua
    assert bpp.main() == 0 and played.exists()


def test_main_fails_over_file_limit(sandbox, monkeypatch):
    monkeypatch.setattr(bpp.acc, "load_log", lambda: {"predictions": [_entry(3)]})
    monkeypatch.setattr(bpp, "_attach_confidence", lambda by_comp: 1)
    monkeypatch.setattr(bpp, "_deploy_file_count", lambda: bpp.CF_FILE_LIMIT + 1)
    assert bpp.main() == 1


def test_deploy_file_count_uses_site_filter_not_repo_walk(tmp_path, monkeypatch):
    """Raja mitataan julkaistavista (site_output), ei repon hakemistoista:
    28.10 lokaali .venv (~41 000 tiedostoa) kaatoi builderin rajaan."""
    import subprocess
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(k, raising=False)

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True,
                       capture_output=True)

    git("init", "-q", "-b", "main")
    (tmp_path / ".gitignore").write_text(".venv/\n")
    (tmp_path / ".venv").mkdir()
    for i in range(30):
        (tmp_path / ".venv" / f"m{i}.py").write_text("")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "b.py").write_text("")
    (tmp_path / "index.html").write_text("<h1>x</h1>")
    git("add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    # Builder kirjoittaa uuden sivun ennen committia: se lasketaan mukaan.
    (tmp_path / "predictions" / "pl").mkdir(parents=True)
    (tmp_path / "predictions" / "pl" / "a-vs-b.html").write_text("<h1>A</h1>")
    monkeypatch.setattr(bpp, "ROOT", tmp_path)
    assert bpp._deploy_file_count() == 2
