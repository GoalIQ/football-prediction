# -*- coding: utf-8 -*-
"""MINUUTTILIPPU-SEURANVAIHDOS (5.9.2026).

Mitattu 4.9: Anderson siirtyi Cityyn deadline-paivana, sai
`minutes_source: price_blend` ja perustelun "thin Premier League sample",
mutta EI lippua, koska lipun ehto katsoi viime kauden minuutteja (3 332) jotka
kertyivat EDELLISESSA seurassa. Khusanov sai lipun 1 427 minuutista.

Julkaisuportti (5.9, k1) loysi ensimmaisesta versiosta kolme koodivikaa:
  B1 lippu ei rauennut (copy "until he has played here" oli vaarin 35/42:lla)
  B3 FPL:n team_join_date antoi uuden paivan lainalta vakinaistetulle
     (Rohl, Guessand, Hincapie, Grealish: minuutit kertyivat SAMASSA seurassa)
  B5 /fpl/expected-points ei renderoinyt lippua lainkaan (0 osumaa livena)
Nama testit on kirjoitettu niista tapauksista, ei alkuperaisesta naytteesta.
"""
from __future__ import annotations

import importlib
import re
from datetime import datetime, timezone

xpb = importlib.import_module("scripts.build_fpl_xp")
lt = importlib.import_module("scripts.build_fpl_longtail")

MCI, NFO, EVE = 43, 17, 11  # FPL team_code (kausien yli vakaa)


def _row(**kw):
    base = {
        "web_name": "Anderson", "team_short": "MCI", "team_code": MCI,
        "pos": "MID", "price": 6.0, "data_basis": "pl_history",
        "predicted_starts": 77.0, "minutes_source": "price_blend",
        "last_season": {"minutes": 3332, "starts": 37, "team_code": NFO,
                        "team_name": "Nottingham Forest"},
    }
    base.update(kw)
    return base


# --- kuka saa lipun ---------------------------------------------------------

def test_anderson_case_gets_new_club():
    rows = [_row()]
    assert xpb.attach_minutes_basis_flag(rows) == 1
    assert rows[0]["minutes_basis_flag"] == "new_club"


def test_full_season_same_club_gets_nothing():
    """Van Dijk: price_blend JA taysi kausi JA sama seura -> ei lippua.
    Tama on se rivi joka erottaa lipun `minutes_source`-lipusta."""
    rows = [_row(web_name="Virgil", team_code=14,
                 last_season={"minutes": 3420, "starts": 38, "team_code": 14,
                              "team_name": "Liverpool"})]
    assert xpb.attach_minutes_basis_flag(rows) == 0
    assert "minutes_basis_flag" not in rows[0]


def test_loan_made_permanent_is_not_a_new_club():
    """Portti B3: Rohl/Grealish saivat uuden team_join_daten mutta viime
    kauden minuutit kertyivat Evertonissa. Seura luetaan arkistosta, ei
    liittymispaivasta -> ei lippua vaikka join-paiva olisi tama kesa."""
    rows = [_row(web_name="Grealish", team_short="EVE", team_code=EVE,
                 joined="2026-07-01",
                 last_season={"minutes": 1627, "starts": 17, "team_code": EVE,
                              "team_name": "Everton"},
                 minutes_source="price_blend")]
    xpb.attach_minutes_basis_flag(rows)
    assert rows[0].get("minutes_basis_flag") != "new_club"


def test_flag_lapses_when_blend_stops():
    """Portti B1: kun pelaajan omat minuutit tassa seurassa ylittavat
    sekoituskynnyksen, minutes_source katoaa ja lipun on rauettava.
    Ilman tata copy muuttuisi vaarammaksi joka kierros (saanto 6a)."""
    rows = [_row(minutes_source=None), _row()]
    del rows[0]["minutes_source"]
    xpb.attach_minutes_basis_flag(rows)
    assert "minutes_basis_flag" not in rows[0]
    assert rows[1]["minutes_basis_flag"] == "new_club"


def test_price_prior_also_counts():
    rows = [_row(minutes_source="price_prior")]
    xpb.attach_minutes_basis_flag(rows)
    assert rows[0]["minutes_basis_flag"] == "new_club"


def test_new_club_beats_short_season():
    """Khusanov-tyyppi: alle 1500 min JA uusi seura -> new_club, koska se on
    tarkempi syy. Lippu ei saa vaihdella sen mukaan kumpi ehto luetaan
    ensin."""
    rows = [_row(last_season={"minutes": 900, "starts": 9, "team_code": NFO,
                              "team_name": "Nottingham Forest"})]
    xpb.attach_minutes_basis_flag(rows)
    assert rows[0]["minutes_basis_flag"] == "new_club"


def test_short_season_still_fires_same_club():
    rows = [_row(last_season={"minutes": 900, "starts": 9, "team_code": MCI,
                              "team_name": "Manchester City"})]
    xpb.attach_minutes_basis_flag(rows)
    assert rows[0]["minutes_basis_flag"] == "short_season"


def test_missing_team_code_is_not_a_change():
    """Puuttuva koodi kummalla tahansa puolella ei ole seuranvaihto."""
    a = _row(team_code=None)
    b = _row(last_season={"minutes": 3332, "starts": 37})
    assert xpb.attach_minutes_basis_flag([a, b]) == 0


def test_override_and_no_history_are_left_alone():
    a = _row(minutes_source="override")
    b = _row(data_basis="no_history")
    assert xpb.attach_minutes_basis_flag([a, b]) == 0


def test_no_flagged_row_can_share_its_last_season_club():
    """Invariantti (portin testi a): liputettu rivi ei koskaan tayta
    last_season.team_code == team_code. Ajetaan sekalaisella joukolla."""
    rows = [_row(team_code=c, last_season={"minutes": m, "starts": 10,
                                            "team_code": pc, "team_name": "X"},
                 minutes_source=src)
            for c in (MCI, NFO) for pc in (MCI, NFO) for m in (800, 3000)
            for src in ("price_blend", "price_prior", None)]
    for r in rows:
        if r["minutes_source"] is None:
            del r["minutes_source"]
    xpb.attach_minutes_basis_flag(rows)
    for r in rows:
        if r.get("minutes_basis_flag") == "new_club":
            assert r["last_season"]["team_code"] != r["team_code"]
            assert r.get("minutes_source") in ("price_blend", "price_prior")


def test_prev_baselines_carry_the_club():
    """Lahde: arkistoitu 25/26-bootstrap -> last_season.team_code/team_name.
    Ilman naita kenttia lippu ei voi laueta millekaan riville."""
    import json
    import config
    d = json.loads((config.PROJECT_ROOT / "data/fpl_prev_baselines_2526.json"
                    ).read_text(encoding="utf-8"))
    rows = [p["last_season"] for p in d["players"].values() if p.get("last_season")]
    assert rows
    assert all(isinstance(r.get("team_code"), int) for r in rows)
    assert all(r.get("team_name") for r in rows)


# --- mita lukija nakee ------------------------------------------------------

def _no_direction(html):
    for kielletty in ("will start", "nailed", "rotation risk", "priced",
                      "until he has played"):
        assert kielletty not in html, kielletty


def test_tooltip_names_the_club_and_makes_no_direction_claim():
    html = lt._no_history_flag(_row(minutes_basis_flag="new_club"))
    assert 'class="flag"' in html
    assert "3332 minutes were for Nottingham Forest" in html
    assert "does not say which way" in html
    _no_direction(html)


def test_omissions_note_names_first_and_reads_as_sentences():
    """Portti B4: nimet lauseen alkuun, iso alkukirjain pisteen jalkeen."""
    lyhyt = _row(web_name="Khusanov", minutes_basis_flag="short_season",
                 last_season={"minutes": 1427, "team_code": MCI,
                              "team_name": "Manchester City"}, price=5.0)
    uusi = _row(minutes_basis_flag="new_club")
    html = lt._xi_omissions([lyhyt, uusi], [])
    text = re.sub(r"<[^>]+>", "", html)
    assert text.startswith("Missing from that eleven: Khusanov (")
    assert "Anderson (" in text and "for Nottingham Forest" in text
    assert re.search(r"\. [a-z]", text) is None, text
    assert "same in each case" not in text
    _no_direction(text)


def test_omissions_note_joins_names_with_and():
    a = _row(minutes_basis_flag="new_club")
    b = _row(web_name="Senesi", team_short="TOT", minutes_basis_flag="new_club",
             last_season={"minutes": 3288, "team_code": 91,
                          "team_name": "Bournemouth"})
    text = re.sub(r"<[^>]+>", "", lt._xi_omissions([a, b], []))
    assert "Anderson (77%, 3332 min) for Nottingham Forest and Senesi (77%, 3288 min) for Bournemouth played last season" in text


def test_expected_points_page_renders_the_flag():
    """Portti B5: sivu itse, ei apufunktio. Negatiivinen kontrolli ilman
    lippua."""
    def page(flagged):
        players = []
        for i in range(1, 12):
            p = {"id": i, "web_name": f"P{i}", "team_short": "ARS",
                 "pos": "MID", "price": 60, "xp_horizon_total": 30.0 - i,
                 "xp_per_gw": 5.0, "xp_per_90": 5.0, "xmins": 85.0,
                 "p_start": 0.9, "gameweeks": [{"gw": 2, "xp": 5.0}]}
            if flagged and i == 1:
                p["minutes_basis_flag"] = "new_club"
                p["last_season"] = {"minutes": 3332, "team_code": NFO,
                                    "team_name": "Nottingham Forest"}
            players.append(p)
        xp = {"meta": {"available": True, "next_gameweek": 2,
                       "deadline_gameweek": 2, "season": "2026/27"},
              "players": players}
        return lt.render_expected_points(
            xp, datetime(2026, 8, 22, tzinfo=timezone.utc)) or ""
    with_flag = page(True)
    without = page(False)
    assert "3332 minutes were for Nottingham Forest" in with_flag
    assert 'class="flag"' in with_flag
    assert 'class="flag"' not in without


def test_spa_and_mobile_render_the_new_flag():
    """Pinta-pariteetti: web + mobiili (Villen saanto 17.7)."""
    from pathlib import Path
    import config
    spa = (config.PROJECT_ROOT / "web/pro-spa/src/lib/components/PlayerCard.svelte"
           ).read_text(encoding="utf-8")
    assert "minutes_basis_flag === 'new_club'" in spa
    assert "until he has played" not in spa and "priced" not in spa.split("new_club")[1][:600]
    mob = Path(r"C:/Users/vvsaa/Documents/goaliq-app/screens/FantasyScreen.tsx")
    if mob.exists():  # vain Villen koneella; CI:ssa mobiilirepoa ei ole
        assert "minutes_basis_flag === 'new_club'" in mob.read_text(encoding="utf-8")
