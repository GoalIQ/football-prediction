# -*- coding: utf-8 -*-
"""Seurasivu linkkaa pron joukkuepaneeliin OMAN seuransa koodilla.

PRO-JOUKKUENAKYMA (Villen paatos 27.9.2026): 20 staattista seurasivua
(goaliq.app/fpl/club/<slug>) ovat liikenne, pro on tyokalu. Sivu linkkaa
`https://pro.goaliq.app/?team=<FPL-lyhenne>`, ja SPA:n `teamParam` avaa
paneelin sen perusteella (web/pro-spa/src/lib/teamPanel.gate.test.ts).

Mita tama estaa: vaara lyhenne (sivu avaisi toisen seuran), linkki joka
katoaa generaattorista hiljaa, ja lyhenne jota SPA ei hyvaksy (kolme
kirjainta A-Z). Tarkistus ajetaan SEKA renderoijalle etta julkaistuille
sivuille: julkaistu sivu on se jonka lukija nakee.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLUB_DIR = ROOT / "fpl" / "club"
LINK_RE = re.compile(r'href="https://pro\.goaliq\.app/\?team=([^"&]+)"')


def _player(i: int, short: str, team: str) -> dict:
    return {
        "id": i, "web_name": f"P{i}", "team": team, "team_short": short,
        "pos": ("GKP", "DEF", "MID", "FWD")[i % 4], "price": 5.0 + i / 10,
        "owned_pct": 10.0, "xp_horizon_total": 30.0 - i, "p_start": 0.9,
        "gameweeks": [{"gw": 6, "xp": 5.0, "opponents": []}],
    }


def test_renderer_links_own_club_code():
    from scripts import build_fpl_longtail as L

    now = datetime(2026, 9, 27, tzinfo=timezone.utc)
    meta = {"available": True, "horizon_gw": 6, "horizon_total_from": 6,
            "horizon_total_gw": 6, "next_gameweek": 6, "deadline_gameweek": 6}
    for short, team in (("ARS", "Arsenal"), ("NFO", "Nottingham Forest")):
        page = L.render_club_page(short, [_player(i, short, team) for i in range(10)],
                                  meta, now)
        assert page, short
        assert LINK_RE.findall(page) == [short], short
        assert f">{team} in the FPL tools</a>" in page


def test_every_club_code_is_one_the_spa_accepts():
    from scripts import build_fpl_longtail as L

    for short in L.CLUB_SLUGS:
        assert re.fullmatch(r"[A-Z]{3}", short), short


@pytest.mark.skipif(not CLUB_DIR.exists(), reason="julkaistut sivut puuttuvat")
def test_published_club_pages_link_their_own_club():
    from scripts import build_fpl_longtail as L

    slug_to_short = {v: k for k, v in L.CLUB_SLUGS.items()}
    pages = sorted(CLUB_DIR.glob("*.html"))
    assert len(pages) >= 20
    for p in pages:
        found = LINK_RE.findall(p.read_text(encoding="utf-8"))
        assert found == [slug_to_short[p.stem]], (p.name, found)
