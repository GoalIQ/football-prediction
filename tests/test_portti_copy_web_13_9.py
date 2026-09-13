"""Julkaisuportin 12.9 yon web-blokit WG4, WG5 ja WG7 (korjattu 13.9).

WG4: `SquadHeaderRow.svelte` naytti chips=null -tilassa "no entry", mutta null
tarkoittaa myos epaonnistunutta historiahakua. Entry on silloin olemassa.

WG5: "Weak spot" -tooltip sanoi "The line the model would strengthen first".
`fpl_rate_team._line_strength` ei laske mitaan vahvistusjarjestysta: se vertaa
XI:n rivin keski-xP/GW:ta saman pelipaikan poolikeskiarvoon ja palauttaa pienimman.

WG7: `FixtureSwing.svelte` otti Low/High-arvot myos kesken olevalta kierrokselta
(live 12.9: next_gameweek 4 kesken, deadline_gameweek 5, Haalandin Low GW4:sta)
ja alaotsikon kierrosmaara tuli `meta.horizon_gw`:sta, joka laskee alkaneen mukaan.
"""
from __future__ import annotations

import re
from pathlib import Path

FP = Path(__file__).resolve().parents[1]
COMP = FP / "web" / "pro-spa" / "src" / "lib" / "components"
RATE_TEAM = FP / "src" / "models" / "fpl_rate_team.py"


def _code(name: str) -> str:
    s = (COMP / name).read_text(encoding="utf-8")
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", s)


def test_wg4_chips_null_reads_unknown_not_no_entry():
    s = _code("SquadHeaderRow.svelte")
    assert '<span class="none">unknown</span>' in s
    assert "no entry" not in s


def test_wg5_weak_spot_tooltip_describes_line_strength():
    s = _code("SquadHeaderRow.svelte")
    assert "strengthen first" not in s
    m = re.search(r'title="([^"]*)"\s*>\s*<span class="k">Weak spot', s)
    assert m, "Weak spot -solun title-attribuuttia ei loydy"
    assert "lowest average xP per gameweek" in m.group(1)
    assert "average for that position" in m.group(1)
    # Tooltip kuvaa taman funktion; jos laskenta muuttuu, teksti on tarkistettava.
    src = RATE_TEAM.read_text(encoding="utf-8")
    body = src[src.index("def _line_strength"):]
    body = body[: body.index("\ndef ", 1)]
    assert 'p["element_type"] == t' in body and "min(ratios" in body


def test_wg7_fixture_swing_skips_started_gameweek():
    s = _code("FixtureSwing.svelte")
    assert "actionableGameweek(data?.meta)" in s
    assert re.search(r"g\.gw\s*>=\s*fromGw", s), "kierrosraja puuttuu"
    assert re.search(
        r"playable\(p\.gameweeks\)\.filter\(\(g\)\s*=>\s*g\.opponents\.length\s*>\s*0\)", s
    ), "rivit eivat kulje playable()-suodatuksen kautta"
    assert re.search(r"playable\(p\.gameweeks\)\.length", s), "alaotsikon luku ei tule samasta suodatuksesta"
    assert "horizon_gw" not in s, "alaotsikon luku lukee yha meta.horizon_gw:ta (sisaltaa alkaneen kierroksen)"
