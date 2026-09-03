# -*- coding: utf-8 -*-
"""CHIP-EV-BUDGET (3.9): joukkueen arvo ja FT-saldo julkisesta historiasta."""
from src.models.fpl_entry_history import infer_free_transfers, team_value_tenths


def _row(gw, transfers=0, value=1000):
    return {"event": gw, "event_transfers": transfers, "event_transfers_cost": 0,
            "bank": 0, "value": value}


def test_team_value_is_latest_gw_value():
    h = {"current": [_row(1, value=1000), _row(2, value=999)]}
    assert team_value_tenths(h) == 999
    assert team_value_tenths({"current": []}) is None
    assert team_value_tenths(None) is None


def test_first_gameweek_leaves_exactly_one_free_transfer():
    """3.9 PORTTI: GW1 on rajattomien siirtojen kierros -> GW2:een tullaan
    yhdella FT:lla. Aiempi versio sanoi kaksi, ja portti mittasi 450 entrysta
    ettei yksikaan saanut toista siirtoa ilmaiseksi GW2:ssa."""
    assert infer_free_transfers({"current": [_row(1, 0)], "chips": []}) == 1


def test_ft_accrues_one_per_gw_capped_at_five():
    h = {"current": [_row(g) for g in range(1, 8)], "chips": []}
    assert infer_free_transfers(h) == 5


def test_ft_consumed_by_transfers_and_hits_do_not_go_negative():
    # GW1: 0 siirtoa -> 1; GW2: 3 siirtoa (2 hittia) -> max(1-3,0)+1 = 1
    h = {"current": [_row(1, 0), _row(2, 3)], "chips": []}
    assert infer_free_transfers(h) == 1
    # kontrolli: yksi siirto GW2:ssa kuluttaa saldon -> 1
    assert infer_free_transfers(
        {"current": [_row(1, 0), _row(2, 1)], "chips": []}) == 1
    # kontrolli: siirtamatta jattaminen kerryttaa -> 2
    assert infer_free_transfers(
        {"current": [_row(1, 0), _row(2, 0)], "chips": []}) == 2


def test_wildcard_gw_preserves_and_accrues():
    # entry 116920 3.9: GW1 0 siirtoa, GW2 wildcard (FPL raportoi
    # event_transfers 0) -> GW3 saldo 2
    h = {"current": [_row(1, 0), _row(2, 0)],
         "chips": [{"name": "wildcard", "event": 2}]}
    assert infer_free_transfers(h) == 2
    # negatiivinen kontrolli: sama historia ilman chippia mutta 5 siirtoa
    # GW2:ssa -> saldo 1
    h2 = {"current": [_row(1, 0), _row(2, 5)], "chips": []}
    assert infer_free_transfers(h2) == 1


def test_no_history_is_none_not_a_guess():
    assert infer_free_transfers(None) is None
    assert infer_free_transfers({"current": []}) is None
