# -*- coding: utf-8 -*-
"""Julkinen mallisarja = mallin jaadytetty rivi (Villen paatos 21.9.2026).

YDININVARIANTTI: Villen yliajo entryyn EI voi siirtya mallin lukuun. 18.9
Ville vaihtoi GW5:n XI:hin De Cuyperin jaadytetyn Bobby Thomasin tilalle, ja
graderi luki entryn pisteet - julkinen track record, Season race ja Beat the
Model mittasivat mallin ja Villen yhdistelmaa.

Invariantti mitataan joka vaiheessa (CLAUDE.md 6a kohta 3), synteettisilla
tiloilla, ei tamanhetkisella datalla:
  * ennen deadlinea: freeze on, gradausta ei viela kummallakaan
  * kesken kierroksen: entry-graderilla on provisionaalinen rivi,
    jaadytettya ei ole gradattu (FPL ei ole finished+data_checked)
  * gradattu: jaadytetty rivi on sarjassa
"""
from __future__ import annotations

import pytest

from src.models import model_squad_scores as mss


def _freeze(gw, *, rebuilt=None, source="chain", hits=0):
    meta = {"gw": gw, "squad_source": source, "hits": hits}
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
         "transfer_cost": 0, "transfer_cost_source": "fpl_entry_same_squad",
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


EXC4 = {"gw": 4, "reason": "gw4.json on runko jota malli ei voi saavuttaa",
        "decided_by": "Ville", "decided_at": "2026-09-12"}


def _pub(frozen_rows=(), entry_rows=(), freezes=None, exceptions=None):
    return mss.public_model_series(_doc(*frozen_rows), _doc(*entry_rows),
                                   freezes or {}, exceptions or {})


def _by_gw(doc):
    return {r["gw"]: r for r in doc["gameweeks"]}


# --- ydininvariantti -------------------------------------------------------

def test_villen_yliajo_ei_siirry_mallin_lukuun():
    """GW5: jaadytetty rivi 43, entry (yliajettu) 40 -> julkinen luku 43."""
    d = _pub([_frozen_row(5, 43, entry_diverged=True)], [_entry_row(5, 40)],
             {5: _freeze(5, source="entry_picks")})
    r = _by_gw(d)[5]
    assert r["points"] == 43 and r["row_basis"] == "frozen"
    assert r["source"] == "frozen_squad" and r["entry_diverged"] is True


@pytest.mark.parametrize("vaihe", ["ennen_deadlinea", "kesken", "gradattu"])
def test_entry_ei_paase_sarjaan_kelvollisen_freezen_kierroksella(vaihe):
    """Vaiheinvariantti: kelvollisen freezen kierroksella entryn luku ei ole
    sarjassa MISSAAN vaiheessa. Ennen gradausta kierrosta ei ole lainkaan
    (puuttuva on parempi kuin vaara)."""
    freezes = {1: _freeze(1), 5: _freeze(5, source="entry_picks")}
    frozen = [_frozen_row(1, 41)]
    entry = [_entry_row(1, 41)]
    if vaihe == "kesken":
        entry.append(_entry_row(5, 40, provisional=True))
    if vaihe == "gradattu":
        entry.append(_entry_row(5, 40))
        frozen.append(_frozen_row(5, 43, entry_diverged=True))
    d = _by_gw(_pub(frozen, entry, freezes))
    if vaihe == "gradattu":
        assert d[5]["points"] == 43 and d[5]["row_basis"] == "frozen"
    else:
        assert 5 not in d, f"{vaihe}: entryn luku paasi mallin sarjaan"
    assert all(r["row_basis"] == "frozen" for r in d.values())


# --- epakelpo freeze ja poikkeuspaatos ------------------------------------

def test_epakelpo_freeze_kirjatulla_poikkeuksella_kayttaa_entrya():
    d = _pub([_frozen_row(3, 63)], [_entry_row(3, 72), _entry_row(4, 64)],
             {3: _freeze(3), 4: _freeze(4, rebuilt=True)}, {4: EXC4})
    r = _by_gw(d)[4]
    assert r["points"] == 64 and r["row_basis"] == "entry_fallback"
    assert "saavuttaa" in r["fallback_reason"]
    assert r["fallback_decided"] == "Ville 2026-09-12"
    assert d["meta"]["fallback_gws"] == [4]
    assert _by_gw(d)[3]["points"] == 63, "GW3 on jaadytetyn rivin luku"


def test_epakelpo_freeze_ilman_poikkeusta_puuttuu_eika_arvata():
    d = _pub([], [_entry_row(4, 64)], {3: _freeze(3), 4: _freeze(4, rebuilt=True)})
    assert 4 not in _by_gw(d)
    assert "poikkeuspaatosta ei ole" in d["meta"]["missing_gws"]["4"]


def test_rikkinainen_poikkeus_ei_ole_vapaakortti():
    rikki = dict(EXC4, reason="")
    d = _pub([], [_entry_row(4, 64)], {3: _freeze(3), 4: _freeze(4, rebuilt=True)},
             {4: rikki})
    assert 4 not in _by_gw(d)
    assert "puuttuvat" in d["meta"]["missing_gws"]["4"]


def test_kelvollinen_freeze_poikkeuksella_ei_kayta_entrya():
    """GW2:n tapaus: poikkeustiedosto on olemassa (entry poikkesi
    tarkoituksella), mutta freeze on KELVOLLINEN - mallin rivi on freeze.
    Poikkeus yksin ei vaihda perustaa, vain epakelpo freeze + poikkeus."""
    exc2 = {"gw": 2, "reason": "wildcard", "decided_by": "Ville",
            "decided_at": "2026-08-28"}
    d = _pub([], [_entry_row(2, 108, active_chip="wildcard")],
             {1: _freeze(1), 2: _freeze(2, hits=2)}, {2: exc2})
    assert 2 not in _by_gw(d), "entry-luku 108 paasi mallin sarjaan"


def test_kauden_ensimmainen_vapaa_optimi_ei_ole_epakelpo():
    f = _freeze(1, rebuilt=True, source="free_optimum")
    assert mss.freeze_invalid(f, earlier_exists=False) is None
    assert mss.freeze_invalid(f, earlier_exists=True)


# --- kustannus ja muoto ------------------------------------------------------

def test_vanha_rivi_ilman_kustannusta_hyvaksytaan_vain_nollalla_hitilla():
    vanha = _frozen_row(3, 63)
    for k in ("transfer_cost", "transfer_cost_source"):
        vanha.pop(k)
    ok = _by_gw(_pub([vanha], [], {3: _freeze(3, hits=0)}))
    assert ok[3]["transfer_cost"] == 0
    d = _pub([vanha], [], {3: _freeze(3, hits=1)})
    assert 3 not in _by_gw(d), "kustannus arvattiin"
    assert "arvata" in d["meta"]["missing_gws"]["3"]


def test_jaadytetty_rivi_ei_kanna_chippia_eika_ole_provisionaalinen():
    r = _by_gw(_pub([_frozen_row(3, 63)], [], {3: _freeze(3)}))[3]
    assert r["active_chip"] is None and r["provisional"] is False


def test_race_lukee_julkista_sarjaa_nettona():
    """Integraatio: Season race laskee mallin kauden julkisesta sarjasta,
    nettona (jaadytetyn rivin oma hitti vahennetaan)."""
    from src.models.fpl_model_race import build_race
    d = _pub([_frozen_row(1, 41), _frozen_row(2, 69, transfer_cost=8,
                                              transfer_cost_source="freeze_hits")],
             [], {1: _freeze(1), 2: _freeze(2, hits=2)})
    race = build_race(d, None)
    assert race["totals"]["model_season"] == 41 + 69 - 8
    assert race["meta"]["chips_played"] == []


# --- elava tila ------------------------------------------------------------

def test_repon_julkinen_sarja_luetaan_ja_fallback_on_perusteltu():
    """Elava data: sarja luetaan, ja jokainen entry-fallback-rivi nojaa
    kirjattuun poikkeukseen epakelvolle freezelle."""
    d = mss.load_public_model_series()
    assert d["meta"]["series_source"] == "frozen_squad"
    for r in d["gameweeks"]:
        if r["row_basis"] == "entry_fallback":
            assert r["fallback_reason"] and r["fallback_decided"]
