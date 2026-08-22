"""KESKEN KIERROKSEN -VARAUS (22.8.2026).

Villen havainto: xP-luvut liikkuivat paivan aikana eika sivu sanonut miksi.
Mitattu samana paivana tuotannon artefakteista: B.Fernandes xmins 85,6 -> 88,4
ja GW-xP 5,76 -> 5,95 yhden ajon aikana, kesken Man Utdin ottelua. Syy on
oikea ja haluttu (malli lukee live-syotetta), mutta selittamatta se lukee
epavakaudelta.

Nama testit vartioivat kahta asiaa:
  1. varaus nakyy VAIN kesken kierroksen — ei kierrosten valissa, jolloin se
     olisi kohinaa joka viikko;
  2. maaritelma on YKSI (backendin `gw_in_progress`), eika kumpikaan pinta
     paattele sita itse. Kaksi maaritelmaa antaisi ennen pitkaa kaksi eri
     vastausta samasta hetkesta.
"""
from __future__ import annotations

import pytest

from src.models.fpl_rate_team import gw_in_progress


@pytest.mark.parametrize("target_gw,dl_gw,next_gw,expected", [
    # GW1 kesken: deadline on jo GW2:ssa JA GW1:lla on pelaamattomia otteluita
    (1, 2, 1, True),
    (2, 2, 2, False),   # ennen deadlinea: sama kierros
    (3, 2, 3, False),   # ei koskaan taaksepain
    # 🔴 Portin loysama tapaus: kierros on PAATTYNYT (next_gameweek on jo
    # seuraavassa) mutta FPL:n is_current-lippu pitaa target_gw:n viela
    # ykkosessa. Ilman next_gw-ehtoa tama olisi ollut True ja varaus olisi
    # jaanyt roikkumaan tunneiksi kierroksen jalkeen.
    (1, 2, 2, False),
    (1, None, 1, False),   # vanha payload ilman kenttaa
    (1, "2", 1, False),    # rikkinainen tyyppi
    (1, 2, None, False),   # next_gameweek puuttuu
])
def test_in_progress_condition(target_gw, dl_gw, next_gw, expected):
    meta = {}
    if dl_gw is not None:
        meta["deadline_gameweek"] = dl_gw
    if next_gw is not None:
        meta["next_gameweek"] = next_gw
    assert gw_in_progress(target_gw, {"meta": meta}) is expected


def test_free_page_shows_the_note_only_mid_round():
    """Ilmaissivun ehto luetaan SAMOISTA kentista kuin backendin lippu."""
    from scripts.build_fpl_longtail import render_expected_points

    def page(next_gw, dl_gw):
        xp = {
            "meta": {"available": True, "next_gameweek": next_gw,
                     "deadline_gameweek": dl_gw, "season": "2026/27"},
            "players": [{
                "id": i, "web_name": f"P{i}", "team_short": "ARS",
                "pos": "MID", "price": 60, "xp_horizon_total": 30.0 - i,
                "xp_per_gw": 5.0, "xp_per_90": 5.0, "xmins": 85.0,
                "p_start": 0.9, "gameweeks": [{"gw": next_gw, "xp": 5.0}],
            } for i in range(1, 12)],
        }
        from datetime import datetime, timezone
        return render_expected_points(xp, datetime(2026, 8, 22,
                                                   tzinfo=timezone.utc)) or ""

    mid = page(1, 2)
    between = page(2, 2)
    assert "is not finished" in mid
    # Negatiivinen kontrolli: ilman sita testi lapaisisi myos silloin kun
    # varaus renderoityy AINA.
    assert "is not finished" not in between
