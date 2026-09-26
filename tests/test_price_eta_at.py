"""PRICE-ETA-ABSOLUUTTINEN-AIKA (26.9.2026): price watchin rivi kantaa
hintapaivityksen absoluuttisen ajan FPL:n omasta listasta.

Tausta: julkaisutarkistaja blokkasi MP-10:n hintarivit. Paivasana
("tonight") johdettiin `eta_days`-offsetista ilman kellonaikaa, ja se oli
vaarin Amerikoissa joka ilta seka kaikkialla paivityksen ja seuraavan buildin
valissa. FPL julkaisee paivitysajat itse
(`game_config.settings.price_change_deadlines`, 26.9: 3 x 23:00Z).

Portit:
  1. eta_at = lista[eta_days] virallisella polulla.
  2. Puuttuva, vajaa tai vaaranmuotoinen lista -> ei eta_at (fail-closed).
  3. Heuristiikkapolku ei tuota eta_at:ia (se ei tieda paivaa).
  4. Omistetut rivit valittavat eta_at:n; OWNED_NOTE ei vaita paivaa.
"""
from __future__ import annotations

from scripts.build_fpl_price_watch import (
    build_payload, eta_at_for, price_update_times,
)
from src.models.fpl_price_watch import OWNED_NOTE, annotate_owned

TIMES = ["2026-09-26T23:00:00Z", "2026-09-27T23:00:00Z", "2026-09-28T23:00:00Z"]


def _proj(*pairs):
    return [{"offset": o, "projected_percent": str(p), "likelihood": 1}
            for o, p in pairs]


def _official(pid, pct, proj, cost=60):
    return {"id": pid, "web_name": f"P{pid}", "team": 1, "now_cost": cost,
            "transfers_in_event": 0, "transfers_out_event": 0,
            "selected_by_percent": "10.0", "cost_change_event": 0,
            "element_type": 3, "price_change_percent": pct,
            "price_change_projections": proj}


def _boot(elements, times=TIMES):
    b = {"total_players": 10_000_000, "elements": elements}
    if times is not None:
        b["game_config"] = {"settings": {"price_change_deadlines": times}}
    return b


ELEMENTS = [
    _official(1, 95.0, _proj((0, 101.0), (1, 130.0))),          # eta 0
    _official(2, 60.0, _proj((0, 80.0), (1, 104.0))),           # eta 1
    _official(3, 40.0, _proj((0, 55.0), (1, 80.0), (2, 101.0))),  # eta 2
    _official(4, -97.0, _proj((0, -102.0))),                     # falling eta 0
]


def _rows(payload):
    return {r["id"]: r for r in payload["risers"] + payload["fallers"]}


def test_eta_at_tulee_fpln_listasta_offsetin_kohdalta():
    rows = _rows(build_payload(_boot(ELEMENTS)))
    assert rows[1]["eta_days"] == 0 and rows[1]["eta_at"] == TIMES[0]
    assert rows[2]["eta_days"] == 1 and rows[2]["eta_at"] == TIMES[1]
    assert rows[3]["eta_days"] == 2 and rows[3]["eta_at"] == TIMES[2]
    assert rows[4]["eta_at"] == TIMES[0]


def test_puuttuva_lista_ei_tuota_eta_at():
    rows = _rows(build_payload(_boot(ELEMENTS, times=None)))
    assert rows[1]["eta_days"] == 0
    assert all("eta_at" not in r for r in rows.values())


def test_vajaa_lista_pudottaa_vain_puuttuvan_offsetin():
    rows = _rows(build_payload(_boot(ELEMENTS, times=TIMES[:1])))
    assert rows[1]["eta_at"] == TIMES[0]
    assert "eta_at" not in rows[2] and "eta_at" not in rows[3]


def test_vaaranmuotoinen_lista_ei_tuota_eta_at():
    for bad in (["tomorrow night"], [None, TIMES[1]], "2026-09-26T23:00:00Z",
                ["2026-09-26 23:00"]):
        assert price_update_times(_boot([], times=bad)) == []
        rows = _rows(build_payload(_boot(ELEMENTS, times=bad)))
        assert all("eta_at" not in r for r in rows.values()), bad


def test_heuristiikkapolku_ei_tuota_eta_at():
    """Ilman FPL:n virallisia kenttia luokitellaan net-transfer-vauhdista,
    joka ei tieda paivaa: eta_at puuttuu vaikka lista olisi bootstrapissa."""
    els = [{"id": 9, "web_name": "H", "team": 1, "now_cost": 50,
            "transfers_in_event": 900_000, "transfers_out_event": 0,
            "selected_by_percent": "10.0", "cost_change_event": 0,
            "element_type": 3}]
    p = build_payload(_boot(els))
    assert p["meta"]["official_projection"] is False
    assert all("eta_at" not in r and "eta_days" not in r
               for r in p["risers"] + p["fallers"])


def test_eta_at_for_rajat():
    assert eta_at_for(TIMES, 0) == TIMES[0]
    assert eta_at_for(TIMES, 3) is None
    assert eta_at_for(TIMES, -1) is None
    assert eta_at_for(TIMES, None) is None
    assert eta_at_for([], 0) is None


def test_omistetut_rivit_valittavat_eta_at():
    p = annotate_owned(build_payload(_boot(ELEMENTS)), {1, 2, 4, 99})
    own = {r["id"]: r for r in p["owned"]["rising"] + p["owned"]["falling"]}
    assert own[1]["eta_at"] == TIMES[0]
    assert own[2]["eta_at"] == TIMES[1]
    assert own[4]["eta_at"] == TIMES[0]


def test_owned_note_ei_vaita_paivaa():
    low = OWNED_NOTE.lower()
    for sana in ("tonight", "today", "tomorrow"):
        assert sana not in low, sana
