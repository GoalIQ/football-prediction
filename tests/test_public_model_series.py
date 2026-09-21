# -*- coding: utf-8 -*-
"""Kaksi julkista sarjaa, malli ensin (Villen paatos 21.9.2026).

  MALLISARJA   mallin jaadytetty rivi FPL:n pisteilla = track record,
               Season racen "Model", tuloskortin mallisolu.
  ENTRY-SARJA  FPL-entry 116920 (malli + ihmisen chip-paatokset) = ratkaisee
               Beat the Model -miniliigan. Naytetaan ERIKSEEN.

YDININVARIANTIT, mitattu synteettisilla vaiheilla (CLAUDE.md 6a.3):
  1. Entryn luku ei paase mallisarjaan millaan polulla: ei yliajetulla
     kierroksella, ei epakelvon freezen kierroksella (GW4), ei kirjatulla
     poikkeuksella.
  2. Epakelpo freeze = kierros pois mallisarjasta NAKYVALLA koodilla, ei
     nollaa eika korviketta.
  3. Entry-sarja kulkee payloadissa omassa kentassaan eika koskaan
     vaikuta mallin summiin.
  4. Todentamaton hittikustannus = brutto + nakyva merkinta, ei arvausta.
"""
from __future__ import annotations

import inspect

import pytest

from src.models import model_squad_scores as mss
from src.models.fpl_model_race import build_race, vs_average


def _freeze(gw, *, rebuilt=None, source="chain", transfers=0):
    meta = {"gw": gw, "squad_source": source,
            "transfers": [{"out": i, "in": 100 + i} for i in range(transfers)]}
    if rebuilt is not None:
        meta["squad_rebuilt"] = rebuilt
    return {"meta": meta, "captain": 1, "vice_captain": 2, "xi": [], "bench": []}


def _frozen_row(gw, points, **kw):
    r = {"gw": gw, "points": points, "points_before_captain": points - 5,
         "captain_reason": "captain", "captain_id": 1,
         "captain_points_added": 5, "bench_points": 3, "autosubs": [],
         "fpl_average": 50, "xi_ids": list(range(1, 12)),
         "graded_at": "2026-09-22T10:00:00Z", "frozen_at": "2026-09-17T12:00:00Z",
         "source": "frozen_squad", "provenance": "entry_picks",
         "transfer_cost": 0, "transfer_cost_source": "no_transfers",
         "entry_diverged": False, "entry_diff": {}}
    r.update(kw)
    return r


def _entry_row(gw, points, **kw):
    r = {"gw": gw, "points": points, "bench_points": 4, "transfer_cost": 0,
         "fpl_average": 50, "captain_id": 1, "captain_points_added": 5,
         "active_chip": None, "autosubs": [], "provisional": False,
         "graded_at": "2026-09-22T11:00:00Z", "source": "entry"}
    r.update(kw)
    return r


def _doc(*rows):
    return {"meta": {}, "gameweeks": list(rows)}


def _model(frozen_rows=(), freezes=None):
    return mss.public_model_series(_doc(*frozen_rows), freezes or {})


def _entry(*rows):
    return mss.public_entry_series(_doc(*rows))


def _by_gw(doc):
    return {r["gw"]: r for r in doc["gameweeks"]}


# --- 1. entryn luku ei paase mallisarjaan ----------------------------------

def test_mallisarjan_ydin_ei_edes_saa_entry_sarjaa():
    """Rakenne, ei ehto: julkisen mallisarjan ydinfunktio ei ota entry-
    sarjaa parametrina, joten mikaan haara ei voi lukea sita."""
    params = set(inspect.signature(mss.public_model_series).parameters)
    assert params == {"frozen_doc", "freezes"}
    params = set(inspect.signature(mss.load_public_model_series).parameters)
    assert not any("entry" in p for p in params)


def test_villen_yliajo_ei_siirry_mallin_lukuun():
    """GW5: jaadytetty rivi 43, entry (yliajettu) 40 -> mallin luku 43."""
    d = _model([_frozen_row(5, 43, entry_diverged=True)],
               {5: _freeze(5, source="entry_picks")})
    r = _by_gw(d)[5]
    assert r["points"] == 43 and r["source"] == "frozen_squad"
    assert r["entry_diverged"] is True


@pytest.mark.parametrize("vaihe", ["ennen_deadlinea", "kesken", "gradattu"])
def test_mallisarja_joka_vaiheessa(vaihe):
    """Vaiheinvariantti: kelvollisen freezen kierros on mallisarjassa VAIN
    gradattuna jaadytettyna rivina. Ennen sita kierrosta ei ole lainkaan
    (puuttuva on parempi kuin vaara), eika se ole unscored."""
    freezes = {1: _freeze(1), 5: _freeze(5, source="entry_picks")}
    frozen = [_frozen_row(1, 41)]
    if vaihe == "gradattu":
        frozen.append(_frozen_row(5, 43))
    d = _model(frozen, freezes)
    if vaihe == "gradattu":
        assert _by_gw(d)[5]["points"] == 43
    else:
        assert 5 not in _by_gw(d)
    assert d["meta"]["unscored_gws"] == []


# --- 2. epakelpo freeze: pois, nakyvasti ------------------------------------

def test_gw4_epakelpo_freeze_on_unscored_eika_entryn_luku():
    """GW4: freeze putosi vapaaseen optimiin. Kierros jaa pois koodilla
    `no_valid_frozen_squad`. Entryn 64 EI korvaa sita, vaikka Villen
    poikkeustiedosto on olemassa (poikkeus koskee vahtia, ei mallisarjaa)."""
    d = _model([_frozen_row(3, 63)],
               {3: _freeze(3), 4: _freeze(4, rebuilt=True)})
    assert 4 not in _by_gw(d)
    assert d["meta"]["unscored_gws"] == [{"gw": 4, "code": "no_valid_frozen_squad", "would_have_scored": None, "fpl_average": None}]
    assert {u["code"] for u in d["meta"]["unscored_gws"]} <= mss.UNSCORED_CODES


def test_kauden_ensimmainen_vapaa_optimi_ei_ole_epakelpo():
    f = _freeze(1, rebuilt=True, source="free_optimum")
    assert mss.freeze_invalid(f, earlier_exists=False) is None
    assert mss.freeze_invalid(f, earlier_exists=True)


def test_ratkeamaton_kelvollinen_kierros_ei_ole_unscored():
    """Negatiivinen kontrolli: gradaamaton KELVOLLINEN freeze ei saa
    nakya "not scored" -merkintana - se odottaa gradausta."""
    d = _model([], {1: _freeze(1), 2: _freeze(2)})
    assert d["meta"]["unscored_gws"] == []


# --- 3. entry-sarja erikseen --------------------------------------------------

def test_entry_sarja_kantaa_chipit_ja_hitit_sellaisenaan():
    e = _by_gw(_entry(_entry_row(2, 108, active_chip="wildcard"),
                      _entry_row(5, 40, transfer_cost=4)))
    assert e[2]["chip"] == "wildcard" and e[2]["points"] == 108
    assert e[5]["points_net"] == 36


def test_race_pitaa_sarjat_erillaan():
    """Entry-sarja on payloadissa omassa lohkossaan eika liikuta mallin
    summia, riveja tai chip-listaa."""
    malli = _model([_frozen_row(1, 41), _frozen_row(3, 63)],
                   {1: _freeze(1), 3: _freeze(3)})
    entry = _entry(_entry_row(1, 41), _entry_row(3, 72, active_chip="3xc"))
    ilman = build_race(malli, None)
    kanssa = build_race(malli, None, entry_series=entry)
    assert kanssa["totals"] == ilman["totals"]
    assert kanssa["gameweeks"] == ilman["gameweeks"]
    assert kanssa["meta"]["chips_played"] == [], "entryn 3xc vuoti mallille"
    eb = kanssa["entry_series"]
    assert eb["chips_played"] == [{"gw": 3, "chip": "3xc"}]
    assert eb["vs_average"]["points"] == 41 + 72
    assert kanssa["totals"]["model_vs_average"]["points"] == 41 + 63


def test_race_kantaa_unscored_gw4():
    malli = _model([_frozen_row(3, 63)],
                   {3: _freeze(3), 4: _freeze(4, rebuilt=True)})
    race = build_race(malli, None)
    assert race["meta"]["unscored_gws"] == [{"gw": 4, "code": "no_valid_frozen_squad", "would_have_scored": None, "fpl_average": None}]
    assert 4 not in [r["gw"] for r in race["gameweeks"]]


def test_vs_average_vain_lopulliset_brutto():
    rows = [{"gw": 1, "points": 41, "fpl_average": 50},
            {"gw": 2, "points": 69, "fpl_average": 81, "transfer_cost": 8},
            {"gw": 5, "points": 40, "fpl_average": 44, "provisional": True}]
    v = vs_average(rows)
    assert v == {"gameweeks": 2, "points": 110, "average": 131, "diff": -21,
                 "hits_deducted": False, "gws": [1, 2]}


def test_mallin_vs_average_on_netto_kuten_paneelin_rivit():
    """Julkaisuportti 21.9: paneelin rivit ja summa ovat nettoja (GW2 61),
    joten mallin keskiarvovertailu vahentaa hitit: 41+61+63 = 165 vs 182
    = -17, ei brutto -9. Entry-lohko pysyy bruttona."""
    malli = _model([_frozen_row(1, 41, fpl_average=50),
                    _frozen_row(2, 69, fpl_average=81, transfer_cost=8,
                                transfer_cost_source="fpl_rules_gw2"),
                    _frozen_row(3, 63, fpl_average=51)],
                   {1: _freeze(1), 2: _freeze(2, transfers=3), 3: _freeze(3)})
    race = build_race(malli, None, entry_series=_entry(
        _entry_row(2, 108, fpl_average=81, transfer_cost=4)))
    mv = race["totals"]["model_vs_average"]
    assert (mv["points"], mv["average"], mv["diff"]) == (165, 182, -17)
    assert mv["hits_deducted"] is True
    assert race["totals"]["model_season"] == mv["points"], (
        "paneelin summa ja keskiarvovertailu eri perusteella")
    ev = race["entry_series"]["vs_average"]
    assert ev["points"] == 108 and ev["hits_deducted"] is False


# --- 4. todentamaton kustannus -------------------------------------------------

def test_vanha_rivi_nollalla_siirrolla_on_todennettu_nolla():
    vanha = _frozen_row(3, 63)
    for k in ("transfer_cost", "transfer_cost_source"):
        vanha.pop(k)
    r = _by_gw(_model([vanha], {3: _freeze(3, transfers=0)}))[3]
    assert r["transfer_cost"] == 0 and r["transfer_cost_verified"] is True


def test_todentamaton_kustannus_on_brutto_nakyvalla_merkinnalla():
    vanha = _frozen_row(3, 63)
    for k in ("transfer_cost", "transfer_cost_source"):
        vanha.pop(k)
    malli = _model([vanha], {3: _freeze(3, transfers=2)})
    r = _by_gw(malli)[3]
    assert r["transfer_cost"] is None and r["transfer_cost_verified"] is False
    race = build_race(malli, None)
    assert race["gameweeks"][0]["model_points"] == 63, "brutto"
    assert race["gameweeks"][0]["model_cost_verified"] is False
    assert race["meta"]["cost_unverified_gws"] == [3]


def test_graderin_null_kustannus_sailyy_todentamattomana():
    r = _by_gw(_model([_frozen_row(6, 50, transfer_cost=None,
                                   transfer_cost_source="unverified")],
                      {6: _freeze(6, transfers=3)}))[6]
    assert r["transfer_cost_verified"] is False


# --- 5. elava tila ------------------------------------------------------------

def test_repon_sarjat_luetaan_ja_gw4_on_unscored():
    malli = mss.load_public_model_series()
    assert malli["meta"]["series_source"] == "frozen_squad"
    assert all(r["source"] == "frozen_squad" for r in malli["gameweeks"])
    unscored = {u["gw"] for u in malli["meta"]["unscored_gws"]}
    if (mss.FROZEN_DIR / "gw4.json").exists():
        assert 4 in unscored, "gw4.json on epakelpo freeze"
    entry = mss.load_public_entry_series()
    assert entry["meta"]["series_source"] == "entry"


# --- 6. kutsupaikat: pinnat nayttavat molemmat, erillaan ----------------------

def _malli_ja_entry():
    malli = _model([_frozen_row(1, 41), _frozen_row(3, 63)],
                   {1: _freeze(1), 3: _freeze(3), 4: _freeze(4, rebuilt=True)})
    entry = _entry(_entry_row(1, 41), _entry_row(3, 72, active_chip="3xc"),
                   _entry_row(4, 64))
    return malli, entry


def test_model_race_endpoint_kantaa_molemmat_sarjat(monkeypatch):
    """Kutsupaikka: API lukee kummankin lukijan ja antaa entry-sarjan omassa
    kentassaan. Ilman tata build_racen testit olisivat vihreita vaikka
    endpoint unohtaisi entry-sarjan."""
    from fastapi.testclient import TestClient

    import api.main as m
    malli, entry = _malli_ja_entry()
    monkeypatch.setattr(mss, "load_public_model_series", lambda **kw: malli)
    monkeypatch.setattr(mss, "load_public_entry_series", lambda **kw: entry)
    d = TestClient(m.app).get("/api/fantasy/model-race").json()
    assert d["totals"]["model_season"] == 41 + 63, "GW4:n 64 vuoti malliin"
    assert d["meta"]["unscored_gws"] == [{"gw": 4, "code": "no_valid_frozen_squad", "would_have_scored": None, "fpl_average": None}]
    assert [r["gw"] for r in d["entry_series"]["gameweeks"]] == [1, 3, 4]
    assert d["entry_series"]["chips_played"] == [{"gw": 3, "chip": "3xc"}]


def test_recap_main_kirjoittaa_sarjat_erillaan(monkeypatch, tmp_path):
    import json

    import scripts.build_gw_recap as br
    malli, entry = _malli_ja_entry()
    monkeypatch.setattr(br, "_load_model_series", lambda: malli)
    monkeypatch.setattr(br, "_load_entry_series", lambda: entry)
    monkeypatch.setattr(br, "_load", lambda p: None)
    monkeypatch.setattr(br, "OUT_PATH", tmp_path / "gw_recap.json")
    assert br.main() == 0
    doc = json.loads((tmp_path / "gw_recap.json").read_text(encoding="utf-8"))
    assert [g["gw"] for g in doc["gameweeks"]] == [1, 3]
    assert doc["running"]["gw_list"] == [1, 3]
    assert doc["unscored_gws"] == [{"gw": 4, "code": "no_valid_frozen_squad", "would_have_scored": None, "fpl_average": None}]
    es = doc["entry_series"]
    assert es["running"]["gw_list"] == [1, 3, 4]
    assert es["running"]["basis"].startswith("FPL entry points")
    assert doc["running"]["basis"].startswith("model points")


def test_tuloskortin_mallisolun_reitti_on_jaadytetty_artefakti():
    """Tarkistusreitti ei ole entry: GW3:n entry nayttaa 72 (3xc), malli 63."""
    import src.models.fpl_rate_team as rt
    malli, _ = _malli_ja_entry()
    m3 = rt.model_squad_gw(3, series=malli)
    assert m3["entry_id"] is None
    assert m3["route"]["kind"] == "frozen_squad" and m3["route"]["gw"] == 3
    # Julkaisuportti 21.9: reitti on pisteytettyjen kierrosten tiedosto, ei
    # rungon gw{n}.json (suomenkielinen reseed.reason, ei lukua).
    assert m3["route"]["url"].endswith("data/model_squad_frozen_gw_scores.json")
    assert m3["points"] == 63
    assert rt.model_squad_gw(4, series=malli) is None, "GW4 ei ole mallin rivi"


# --- 7. SPA-pinnat renderoivat molemmat sarjat (kutsupaikka lahteessa) ---------

def _spa(polku: str) -> str:
    """Lahde ilman HTML- ja //-kommentteja (merkkijonoportti ei saa osua
    omaan perustelukommenttiinsa, muisti 12.9)."""
    import re
    from pathlib import Path
    s = (Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src"
         / "lib" / "components" / polku).read_text(encoding="utf-8")
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return "\n".join(r.split("//", 1)[0] for r in s.split("\n"))


def test_spa_season_race_nayttaa_entry_sarjan_ja_unscored():
    s = _spa("SeasonRace.svelte")
    for tarvittava in ("data?.entry_series", "unscored_gws", "cost_unverified_gws",
                       "model_vs_average", "MODEL_SERIES_COPY.entryTitle",
                       "MODEL_SERIES_COPY.unscoredNoValidFreeze",
                       "u.would_have_scored", "reseeded_gws",
                       "MODEL_SERIES_COPY.reseeded", "x.entry_chip",
                       "model_cost_verified"):
        assert tarvittava in s, f"SeasonRace ei renderoi: {tarvittava}"


def test_spa_tuloskortti_kayttaa_jaadytettya_reittia():
    s = _spa("TeamPitchManager.svelte")
    assert "model_route" in s and "MODEL_SERIES_COPY.cardModelKey" in s
    assert "sourceNote: modelRoute" in s and "MODEL_SERIES_COPY.cardSourceNote" in s


# --- 8. GW4: syy JA luku, luku vain payloadista ---------------------------

def test_gw4_luku_tulee_graderin_diagnostiikasta():
    """Villen paatos 21.9: GW4 pois summasta, mutta syy ja luku nakyviin.
    Luku ja keskiarvo tulevat jaadytetyn lokin `unscored`-listasta."""
    doc = _doc(_frozen_row(3, 63))
    doc["unscored"] = [{"gw": 4, "code": "no_valid_frozen_squad",
                        "would_have_scored": 49, "fpl_average": 69}]
    d = mss.public_model_series(doc, {3: _freeze(3), 4: _freeze(4, rebuilt=True)})
    assert d["meta"]["unscored_gws"] == [{"gw": 4, "code": "no_valid_frozen_squad",
                                          "would_have_scored": 49,
                                          "fpl_average": 69}]
    assert 4 not in _by_gw(d), "diagnostinen luku ei saa tulla mallisarjaan"


def test_gw4_ilman_diagnostiikkaa_ei_ole_lukua():
    """Luku jota lokissa ei ole ei voi ilmestya: pinta saa None."""
    d = _model([_frozen_row(3, 63)], {3: _freeze(3), 4: _freeze(4, rebuilt=True)})
    u = d["meta"]["unscored_gws"][0]
    assert u["would_have_scored"] is None and u["fpl_average"] is None


# --- 9. GW3-reseed johdetaan payloadista ------------------------------------

def _reseed_freeze(gw, source_gw):
    f = _freeze(gw, source="entry_picks")
    f["meta"]["reseed"] = {"gw": gw, "source_gw": source_gw, "reason": "x",
                           "decided_by": "Ville", "decided_at": "2026-09-04"}
    return f


def test_reseed_kierros_ja_entryn_chip_johdetaan():
    malli = _model([_frozen_row(2, 69), _frozen_row(3, 63)],
                   {2: _freeze(2), 3: _reseed_freeze(3, 2)})
    assert malli["meta"]["reseeded_gws"] == [{"gw": 3, "from_gw": 2}]
    entry = _entry(_entry_row(2, 108, active_chip="wildcard"), _entry_row(3, 72))
    race = build_race(malli, None, entry_series=entry)
    assert race["meta"]["reseeded_gws"] == [{"gw": 3, "from_gw": 2,
                                             "entry_chip": "wildcard"}]


def test_reseed_ilman_entry_sarjaa_ei_vaita_chippia():
    malli = _model([_frozen_row(3, 63)], {3: _reseed_freeze(3, 2)})
    race = build_race(malli, None)
    assert race["meta"]["reseeded_gws"] == [{"gw": 3, "from_gw": 2,
                                             "entry_chip": None}]


def test_ketjufreeze_ei_ole_reseed():
    """Negatiivinen kontrolli: tavallinen ketju ei tuota selitetta."""
    malli = _model([_frozen_row(2, 69)], {1: _freeze(1), 2: _freeze(2)})
    assert malli["meta"]["reseeded_gws"] == []


def test_reseed_selite_vain_pisteytetylle_kierrokselle():
    """GW5 on reseed mutta ei viela gradattu: ei selitetta ennen rivia."""
    malli = _model([_frozen_row(3, 63)],
                   {3: _reseed_freeze(3, 2), 5: _reseed_freeze(5, 4)})
    assert [x["gw"] for x in malli["meta"]["reseeded_gws"]] == [3]


def test_repon_gw3_on_reseed_gw2_wildcardista():
    """Elava tila: gw3.json on reseed GW2:sta, ja entry pelasi siella
    wildcardin. Jos tama kaatuu, selite olisi vaara."""
    malli = mss.load_public_model_series()
    if 3 not in _by_gw(malli):
        pytest.skip("GW3 ei ole jaadytetyssa sarjassa")
    entry = mss.load_public_entry_series()
    race = build_race(malli, None, entry_series=entry)
    r3 = [x for x in race["meta"]["reseeded_gws"] if x["gw"] == 3]
    assert r3 == [{"gw": 3, "from_gw": 2, "entry_chip": "wildcard"}]


def test_recap_kantaa_reseedin_ja_gw4_luvun(monkeypatch, tmp_path):
    import json

    import scripts.build_gw_recap as br
    doc = _doc(_frozen_row(2, 69), _frozen_row(3, 63))
    doc["unscored"] = [{"gw": 4, "code": "no_valid_frozen_squad",
                        "would_have_scored": 49, "fpl_average": 69}]
    malli = mss.public_model_series(doc, {2: _freeze(2), 3: _reseed_freeze(3, 2),
                                          4: _freeze(4, rebuilt=True)})
    entry = _entry(_entry_row(2, 108, active_chip="wildcard"))
    monkeypatch.setattr(br, "_load_model_series", lambda: malli)
    monkeypatch.setattr(br, "_load_entry_series", lambda: entry)
    monkeypatch.setattr(br, "_load", lambda p: None)
    monkeypatch.setattr(br, "OUT_PATH", tmp_path / "gw_recap.json")
    assert br.main() == 0
    out = json.loads((tmp_path / "gw_recap.json").read_text(encoding="utf-8"))
    assert out["unscored_gws"][0]["would_have_scored"] == 49
    assert out["reseeded_gws"] == [{"gw": 3, "from_gw": 2, "entry_chip": "wildcard"}]
