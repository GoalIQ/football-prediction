# -*- coding: utf-8 -*-
"""XP-READER-DISCIPLINE-AUKKO (6.9.2026): build_fpl_longtail.py luki
data/fpl_xp_projections.json:n `_load(XP_PATH)`:lla, ohittaen
`load_xp_actionable()`-lukijan (portin sivuloydos 4.9, tests/test_xp_reader_
discipline.py). Sama tiedosto on jo kolmesti korjannut kapteenivikoja jotka
syntyivat juuri talta rakenteelta (ks. render_captain-docstring, 25.8/30.8):
pinta luki `gameweeks[]`-listan raakana ja indeksoi vaarin.

Molemmat kutsupaikat (`_gw_still_running`, `main()`) reititetaan nyt
`load_xp_actionable`:n lapi. Tama tiedosto testaa etta reititys pysyy
paikallaan ja etta se aidosti poistaa mennen kierroksen main():n polulta.
"""
import json


def test_gw_still_running_reads_via_the_actionable_reader(tmp_path, monkeypatch):
    """`_gw_still_running` katsoo vain `meta.next_gameweek`ia, joten tulos
    ei riipu siita reitittaako se `load_xp_actionable`:n vai `_load`:n
    lapi - mutta lukijan on oltava sama joka muuallakin, ei oma poikkeus."""
    from scripts import build_fpl_longtail as m
    doc = {"meta": {"available": True, "next_gameweek": 3}, "players": []}
    p = tmp_path / "xp.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(m, "XP_PATH", p)
    assert m._gw_still_running(3) is True
    assert m._gw_still_running(2) is False


def test_negative_control_missing_next_gameweek_defaults_to_running(
        tmp_path, monkeypatch):
    """Kontrolli: puuttuva `next_gameweek` ei saa lukita 'kierros ohi'
    -tilaan (liikaa varausta on halvempaa kuin liian vahan, ks. docstring)."""
    from scripts import build_fpl_longtail as m
    doc = {"meta": {"available": True}, "players": []}
    p = tmp_path / "xp.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(m, "XP_PATH", p)
    assert m._gw_still_running(1) is True


def test_mains_xp_pipeline_never_sees_a_past_gameweek(tmp_path):
    """Se konkreettinen vika jota rivi korjaa: artefaktissa on kierros jonka
    deadline on jo mennyt, eika `main()`:n `xp`-muuttuja (rakennettu samalla
    kutsulla kuin taalla) saa enaa kantaa sita per-pelaaja-listassaan."""
    doc = {"meta": {"available": True, "deadline_gameweek": 4,
                    "next_gameweek": 4},
           "players": [{"id": 1,
                        "gameweeks": [{"gw": g, "xp": 1.0}
                                      for g in (2, 3, 4, 5)]}]}
    p = tmp_path / "xp.json"
    p.write_text(json.dumps(doc), encoding="utf-8")

    from src.models.fpl_xp import load_xp_actionable
    xp = load_xp_actionable(p)  # sama kutsu kuin scripts/build_fpl_longtail.py:main()
    gws = [g["gw"] for g in xp["players"][0]["gameweeks"]]
    assert gws == [4, 5], f"mennyt kierros vuoti lapi: {gws}"


def test_negative_control_build_fpl_longtail_has_no_raw_xp_path_read():
    """Rakenteellinen kontrolli: discipline-skanneri (tests/test_xp_reader_
    discipline.py) ei enaa loyda taman tiedoston kahta vanhaa `_load(XP_PATH)`
    -kutsua. Jos joku palauttaa raa'an luvun, tama kaataa - riippumatta
    siita muistaako kukaan ajaa toisen testitiedoston."""
    import ast
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_xp_reader_discipline as disc

    target = (Path(__file__).resolve().parents[1]
              / "scripts" / "build_fpl_longtail.py")
    tree = ast.parse(target.read_text(encoding="utf-8"))
    hits = disc._scan_path_reads("scripts/build_fpl_longtail.py", tree)
    assert not hits, f"raaka XP-polkuluku palasi riveille {hits}"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
