"""Season race -datan kokoaminen (BTM V2 vaihe c) — puhdas logiikka.

Luvut ovat eri joka kierroksella, jotta väärä kaava (esim. summa erotusten
sijaan tai käänteinen etumerkki) tuottaa eri tuloksen.

Rehellisyyssäännöt joita nämä vartioivat:
  - ennen ensimmäistä gradausta ei arvata mitään
  - puuttuvaa kierrosta EI tulkita nollaksi
  - malli ei pelaa chippejä ja se lukee datassa
"""
from __future__ import annotations

from src.models.fpl_model_race import (
    NOTE_NOT_STARTED,
    build_race,
)


def _log(*rows: dict) -> dict:
    return {"gameweeks": list(rows)}


def _mrow(gw: int, points: int, **extra) -> dict:
    r = {"gw": gw, "points": points, "fpl_average": 50 + gw,
         "captain_id": 100 + gw, "captain_reason": "captain",
         "captain_points_added": gw, "bench_points": gw * 2,
         "autosubs": [{"out": 1, "in": 12, "pos": 1}]}
    r.update(extra)
    return r


def _hist(*pairs: tuple[int, int], bench: int = 3) -> dict:
    return {"current": [{"event": gw, "points": p, "points_on_bench": bench,
                         "event_transfers_cost": 0} for gw, p in pairs]}


# --- tyhjä tila -----------------------------------------------------------

def test_ennen_ensimmaista_gradausta_ei_arvata():
    r = build_race(None, None)
    assert r["meta"]["available"] is False
    assert r["meta"]["note"] == NOTE_NOT_STARTED
    assert r["gameweeks"] == []
    assert r["totals"]["you"] is None


def test_tyhja_loki_kohdellaan_samoin_kuin_puuttuva():
    assert build_race({"gameweeks": []}, None)["meta"]["available"] is False


# --- mallin puoli ilman käyttäjää ----------------------------------------

def test_mallin_rivit_naytetaan_ilman_entrya():
    r = build_race(_log(_mrow(1, 61), _mrow(2, 45)), None)
    assert r["meta"]["available"] is True
    assert r["totals"]["model"] == 106
    assert r["totals"]["you"] is None and r["totals"]["diff"] is None
    assert [g["gw"] for g in r["gameweeks"]] == [1, 2]
    assert all(g["your_points"] is None for g in r["gameweeks"])
    assert "Add your FPL team ID" in r["meta"]["note"]


def test_malli_ei_pelaa_chippeja_lukee_datassa():
    r = build_race(_log(_mrow(1, 61)), None)
    assert r["meta"]["model_plays_chips"] is False


def test_rivit_jarjestetaan_kierroksen_mukaan():
    r = build_race(_log(_mrow(3, 30), _mrow(1, 61), _mrow(2, 45)), None)
    assert [g["gw"] for g in r["gameweeks"]] == [1, 2, 3]


# --- kumulatiivinen ero ---------------------------------------------------

def test_kumulatiivinen_ero_on_juokseva_summa_eika_summien_erotus():
    """GW1 sinä 70 vs malli 61 (+9), GW2 sinä 40 vs 45 (-5) -> 9, 4."""
    r = build_race(_log(_mrow(1, 61), _mrow(2, 45)), _hist((1, 70), (2, 40)))
    diffs = [g["diff"] for g in r["gameweeks"]]
    cums = [g["cumulative_diff"] for g in r["gameweeks"]]
    assert diffs == [9, -5]
    assert cums == [9, 4]
    assert r["totals"]["diff"] == 4
    assert r["totals"]["you"] == 110


def test_etumerkki_on_sina_miinus_malli():
    """Häviötilanne saa näkyä negatiivisena — molemmat suunnat samalla painolla."""
    r = build_race(_log(_mrow(1, 61)), _hist((1, 50)))
    assert r["gameweeks"][0]["diff"] == -11
    assert r["totals"]["diff"] == -11


def test_puuttuvaa_kierrosta_ei_tulkita_nollaksi():
    """Käyttäjä liittyi GW2:ssa: GW1 jää vertailun ulkopuolelle, EI -61."""
    r = build_race(_log(_mrow(1, 61), _mrow(2, 45)), _hist((2, 50)))
    g1, g2 = r["gameweeks"]
    assert g1["your_points"] is None and g1["diff"] is None
    assert g2["diff"] == 5
    assert r["totals"]["diff"] == 5
    assert r["meta"]["compared_gws"] == 1
    assert r["totals"]["model"] == 106      # mallin summa on silti koko kausi


def test_ei_yhteisia_kierroksia_kerrotaan():
    r = build_race(_log(_mrow(1, 61)), _hist((5, 50)))
    assert r["totals"]["diff"] is None
    assert "No overlapping gameweeks" in r["meta"]["note"]


# --- premium-portitus -----------------------------------------------------

def test_free_saa_eron_muttei_erittelya():
    r = build_race(_log(_mrow(1, 61)), _hist((1, 70)), premium=False)
    g = r["gameweeks"][0]
    assert g["diff"] == 9                    # kilpailun tulos on ilmainen
    assert g["cumulative_diff"] == 9
    assert "model_captain_id" not in g       # syy on premium
    assert "model_bench_points" not in g
    assert "model_autosubs" not in g
    assert r["meta"]["masked"] is True


def test_premium_saa_erittelyn_molemmilta_puolilta():
    r = build_race(_log(_mrow(1, 61)), _hist((1, 70)), premium=True)
    g = r["gameweeks"][0]
    assert g["model_captain_id"] == 101
    assert g["model_captain_points"] == 1
    assert g["model_bench_points"] == 2
    assert g["model_autosubs"] == [{"out": 1, "in": 12, "pos": 1}]
    assert g["your_bench_points"] == 3
    assert r["meta"]["masked"] is False


def test_fpl_keskiarvo_kulkee_mukana_molemmissa():
    for prem in (True, False):
        r = build_race(_log(_mrow(1, 61)), None, premium=prem)
        assert r["gameweeks"][0]["fpl_average"] == 51


# --- 7.9: kolme tilaa, ei yksi "provisional" -------------------------------

def test_row_state_erottaa_kesken_olevan_ja_vahvistamattoman():
    """🔴 Mitattu tuotannosta 7.9: GW3 oli `is_current`, `finished` False -
    otteluita oli KESKEN - ja `fantasy.race.provisional_note` sanoi lukijalle
    *"FPL hasn't confirmed bonus points yet"*. Vaarin nimetty mekanismi on
    pahempi kuin nimeamaton: lukija voi tarkistaa aritmetiikan ja todeta
    meidat vaaraksi (muisti: mekanismin-nimeaminen-on-vaite)."""
    from src.models.fpl_model_race import row_state
    assert row_state({"provisional": False}) == "final"
    assert row_state({"provisional": False, "finished": False}) == "final"
    assert row_state({"provisional": True, "finished": False}) == "in_progress"
    assert row_state({"provisional": True, "finished": True}) == "awaiting_check"
    # Kolmas haara: kentta puuttuu -> emme voi sanoa kummasta on kyse.
    assert row_state({"provisional": True}) == "unknown"
    assert row_state(None) == "unknown"


def test_race_payload_kantaa_tilan_jokaiselle_riville():
    from src.models.fpl_model_race import build_race
    loki = {"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 50, "provisional": False,
         "finished": True},
        {"gw": 2, "points": 108, "fpl_average": 81, "provisional": True,
         "finished": True},
        {"gw": 3, "points": 30, "fpl_average": 51, "provisional": True,
         "finished": False},
    ]}
    out = build_race(loki, None)
    tilat = [r["state"] for r in out["gameweeks"]]
    assert tilat == ["final", "awaiting_check", "in_progress"], tilat
    assert out["meta"]["provisional_states"] == {"2": "awaiting_check",
                                                 "3": "in_progress"}
    # Kontrolli: lopullinen kierros EI ole listalla.
    assert "1" not in out["meta"]["provisional_states"]
