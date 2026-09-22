"""Reply-moduulin reitit: luku kelpaa vain jos SAMA TEKSTI nakyy ilmaissivulla.

Generaattori (scripts/build_reply_module.py) hakee julkiset sivut ja ajaa
`resolve_routes`in. Tama testi ajaa saman funktion tallennetuilla
sivupaloilla: sama teksti -> reitti, eri teksti -> ristiriita (moduuli ei
synny), rivia ei ole -> ei reittia (public_url null), sivu nayttaa eri
kierrosta -> ei reittia. Lisaksi kommitoidun moduulin rakenne.
"""
from __future__ import annotations

import json

import pytest

import config
from src.marketing import public_surface as ps
from src.marketing import reply_module as rm
from src.marketing import reply_sections as rs

GW_XP_HTML = """
<h2 id="gw-xp">Gameweek 6 expected points, top 20</h2>
<table class="lb"><thead><tr><th class="n">#</th><th>Player</th><th>Team</th><th>Pos</th>
<th class="n">Price</th><th class="n">GW6 xP</th><th class="m-hide">Opponent</th><th class="n">Start%</th>
</tr></thead><tbody>
<tr><td class="n">1</td><td>B.Fernandes<span class="m-sub drv">on penalties</span><span class="m-only m-sub opp">TOT (H)</span></td>
<td class="tm"><svg class="kit"><use href="#kMUN"/></svg><span>MUN</span></td><td>MID</td><td class="n">11.9</td>
<td class="n hi">6.8</td><td class="m-hide">TOT (H)</td><td class="n">97</td></tr>
<tr><td class="n">2</td><td>Isak <span class="flag" title="Only 694 minutes">!</span></td>
<td class="tm"><span>LIV</span><span class="tflag">turnover</span></td><td>FWD</td><td class="n">10.5</td>
<td class="n hi">5.1</td><td class="m-hide">MCI (H)</td><td class="n">88</td></tr>
</tbody></table>
"""

CS_HTML = """
<h2 id="clean-sheets">Gameweek 6 clean sheet probabilities</h2>
<table><caption>Model clean sheet probability for every Premier League team, Gameweek 6, 2026/27 season.</caption>
<thead><tr><th scope="col">Team</th><th scope="col" class="num">Clean sheet %</th><th scope="col">Next opponent</th></tr></thead>
<tbody><tr><td class="team">Hull<span class="m-sub is-caveat">rating from 5 matches</span></td>
<td class="num">38.6%</td><td>Everton (H)<span class="m-sub goals">projected goals<br>HUL 1.14</span></td></tr></tbody></table>
"""


def test_parsers_read_the_visible_cell_not_the_sub_lines():
    gw, rows = ps.gw_xp_table(GW_XP_HTML)
    assert gw == 6
    assert rows[("B.Fernandes", "MUN")]["gw_xp"] == "6.8"
    assert rows[("Isak", "LIV")]["start_pct"] == "88"  # lippu "!" ei tartu nimeen
    gw2, cs = ps.clean_sheet_table(CS_HTML)
    assert gw2 == 6 and cs["Hull"]["cs_pct"] == "38.6%"
    assert cs["Hull"]["opponent"] == "Everton (H)"


def _pages(gw_page=6):
    gw, rows = ps.gw_xp_table(GW_XP_HTML)
    g2, cs = ps.clean_sheet_table(CS_HTML)
    return {"gw_xp": {"url": rs.URL["gw_xp"], "gw": gw_page, "rows": rows},
            "clean_sheets": {"url": rs.URL["clean_sheets"], "gw": g2, "rows": cs}}


def _section(text):
    return {"s": {"rows": [{"key": "b-fernandes-mun", "values": {
        "gw_xp": rs.val(float(text), text, "xP", "xp", [("gw_xp", ("B.Fernandes", "MUN"))])}},
        {"key": "hul", "values": {
            "cs_pct": rs.val(38.6, "38.6%", "%", "phase0", [("clean_sheets", ("Hull",))])}},
        {"key": "nobody-xxx", "values": {
            "gw_xp": rs.val(1.0, "1.0", "xP", "xp", [("gw_xp", ("Nobody", "XXX"))])}}]}}


SOURCES = {"xp": {"file": "data/fpl_xp_projections.json", "commit": "abc", "generated_at": "g"},
           "phase0": {"file": "data/fpl_projections_phase0.json", "commit": "def", "generated_at": "h"}}


def test_same_text_gets_a_route_missing_row_gets_none():
    secs = _section("6.8")
    ok, none, bad = rm.resolve_routes(secs, _pages(), 6, "T", SOURCES)
    assert (ok, none, bad) == (2, 1, [])
    idx = rm.value_index(secs)
    v = idx["s.b-fernandes-mun.gw_xp"]
    assert v["public_url"] == rs.URL["gw_xp"] and v["verified_at"] == "T"
    assert v["source"] == "data/fpl_xp_projections.json@abc" and v["generated_at"] == "g"
    assert v["check"] == ["gw_xp", ["B.Fernandes", "MUN"]] and "routes" not in v
    assert idx["s.nobody-xxx.gw_xp"]["public_url"] is None
    assert idx["s.nobody-xxx.gw_xp"]["verified_at"] is None


def test_different_text_on_the_same_row_is_a_conflict():
    ok, none, bad = rm.resolve_routes(_section("6.9"), _pages(), 6, "T", SOURCES)
    assert len(bad) == 1 and "6.8" in bad[0] and "6.9" in bad[0]


def test_page_showing_another_gameweek_is_not_a_route():
    """Kesken kierroksen sivu voi nayttaa kuluvaa kierrosta: se ei todista GW6:n lukua."""
    secs = _section("6.8")
    ok, none, bad = rm.resolve_routes(secs, _pages(gw_page=5), 6, "T", SOURCES)
    assert bad == []
    assert rm.value_index(secs)["s.b-fernandes-mun.gw_xp"]["public_url"] is None
    # Sama luku, oikea kierros sivulla: reitti loytyy (fikstuuri on erotteleva).
    secs2 = _section("6.8")
    rm.resolve_routes(secs2, _pages(gw_page=6), 6, "T", SOURCES)
    assert rm.value_index(secs2)["s.b-fernandes-mun.gw_xp"]["public_url"] == rs.URL["gw_xp"]


# ---------------------------------------------------------------------------
# Kommitoitu moduuli
# ---------------------------------------------------------------------------
def _committed():
    ps_ = sorted((config.DATA_DIR / "reply_modules").glob("gw*.json"))
    if not ps_:
        pytest.skip("ei kommitoitua reply-moduulia")
    return [json.loads(p.read_text(encoding="utf-8")) for p in ps_]


def test_committed_module_every_number_has_provenance():
    for m in _committed():
        assert m["schema"] == rm.SCHEMA and m["deadline_utc"]
        n_pub = 0
        for key, v, _r, _s in rm.iter_values(m["sections"]):
            for f in ("value", "text", "source", "generated_at", "public_url", "verified_at"):
                assert f in v, (key, f)
            assert "@" in v["source"], key
            if v["public_url"]:
                n_pub += 1
                assert v["verified_at"] and v.get("check"), key
                assert v["public_url"].startswith(("https://goaliq.app/",
                                                   "https://fantasy.premierleague.com/entry/"))
            else:
                assert v["verified_at"] is None, key
        assert n_pub == m["counts"]["verified"]


def test_committed_module_named_players_cover_every_player_row():
    for m in _committed():
        named = m["named_players"]
        for sname in rm.PLAYER_SECTIONS:
            for row in (m["sections"].get(sname) or {}).get("rows") or []:
                assert str(row["player_id"]) in named, (sname, row["key"])


def test_committed_module_has_no_blocklisted_player():
    from scripts.publish_gate import load_blocklist
    from src.models.fpl_gw_xp import excluded
    bl = load_blocklist()
    for m in _committed():
        for sname in ("captain_top5", "xp_top5", "player_lookup", "differentials"):
            for row in (m["sections"].get(sname) or {}).get("rows") or []:
                assert not excluded(row["name"], bl), row["name"]
