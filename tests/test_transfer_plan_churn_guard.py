"""SIIRTOSUUNNITELMA-CHURN (11.9.2026, `cos-reports/QUEUE.md`).

Mitattu 3.9 tuotannosta (entry 116920): moniviikkoinen suunnitelma osti ja
myi saman pelaajan sisaisesti (GW5 -> Wissa -> GW8 Wissa pois). Juurisyy:
`plan_transfers` kutsuu `fpl_transfers.plan_gw`:ta kierros kerrallaan eika
muista keta se on jo ostanut - jokainen kierros arvioi vain SEN HETKISEN
jaljella olevan ikkunan, joten pelaaja joka nayttaa hyvalta lyhyella
tahtaimella (esim. yhden ottelun piikki) ostetaan, ja heti seuraavalla
kierroksella tavallinen parannus riittaa myymaan hanet pois.

Korjaus: `recent_buys` ({pid: gain_weighted ostohetkella}), jota `plan_gw`
yllapitaa paikallaan ja `plan_transfers` jakaa kierrosten yli. Rungon juuri
ostamaa pelaajaa ei tarjota lahtijaksi ellei uusi hyoty ylita ostohyotya
SELVASTI (`fpl_transfers.CHURN_CLEAR_FACTOR`, ks. `clears_recent_buy`).

Testit kahdella tasolla:
  1. `single_moves`/`best_pair` suoraan - eristetty mekanismi, molemmat
     kontrollit (ilman recent_buysia sama loydos ehdotetaan; selva
     parannus paasee lapi kaikkiaan).
  2. `plan_gw` kahdella perakkaisella kierroksella (sama tapa jolla
     `plan_transfers` sita kayttaa) - sama tapaus kuin tuotannossa: GW1
     ostaa piikkipelaajan, GW2 EI myy hanta marginaalisesta parannuksesta
     mutta EI estä muuta aitoa parannusta eika esta selvaa kaannetta.

Hermeettinen: synteettinen pooli, ei verkkoa (sama kaava kuin
tests/test_transfer_engine_parity.py:n `_p`).
"""
from __future__ import annotations

from src.models import fpl_transfers as tr

FT_CARRY_MAX = 5


def _p(pid, pos, price, xp_by_gw, name=None):
    """Synteettinen poolipelaaja usealla kierroksella: xp_by_gw = {gw: xp}."""
    return {"id": pid, "web_name": name or f"P{pid}", "team_short": "T",
            "element_type": pos, "club": pid, "price": price, "owned_pct": 1.0,
            "xp_per_gw": sum(xp_by_gw.values()) / len(xp_by_gw),
            "xp_horizon_total": round(sum(xp_by_gw.values()), 2),
            "gameweeks": [{"gw": g, "opponents": [], "xp": xp}
                         for g, xp in sorted(xp_by_gw.items())]}


def _legal_squad(xp=1.0, price=45):
    """2 GK, 5 DEF, 5 MID, 3 FWD, tasainen xp joka kierrokselle."""
    squad = []
    pid = 1
    for pos, n in ((1, 2), (2, 5), (3, 5), (4, 3)):
        for _ in range(n):
            squad.append(_p(pid, pos, price, {1: xp, 2: xp, 3: xp}))
            pid += 1
    return squad, pid


# ---------------------------------------------------------------------------
# 1. Mekanismi eristetty: single_moves + best_pair
# ---------------------------------------------------------------------------
def test_single_moves_blocks_marginal_sale_of_recent_buy():
    squad, next_pid = _legal_squad()
    x_id = next_pid
    for i, p in enumerate(squad):
        if p["element_type"] == 3:  # MID
            squad[i] = _p(x_id, 3, 60, {2: 8.0}, "X")
            break
    marginal = _p(300, 3, 60, {2: 9.0}, "Marginal")   # gain_weighted 1.0
    clear = _p(301, 3, 60, {2: 20.0}, "Clear")        # gain_weighted 12.0
    pool = squad + [marginal, clear]
    gws = [2]
    recent_buys = {x_id: 3.0}  # X ostettiin 3.0 xP:n hyodylla

    guarded = tr.single_moves(squad, pool, 0, gws, top_k=5, recent_buys=recent_buys)
    assert all(m["out"]["id"] != x_id or m["in"]["id"] != 300 for m in guarded), guarded
    assert any(m["out"]["id"] == x_id and m["in"]["id"] == 301 for m in guarded), guarded

    # NEGATIIVINEN KONTROLLI: sama pooli ilman recent_buysia TARJOAA marginaalin
    # myos - muuten testi lapaisisi tyhjana (portti joka ei koskaan estanyt mitaan).
    unguarded = tr.single_moves(squad, pool, 0, gws, top_k=5)
    assert any(m["out"]["id"] == x_id and m["in"]["id"] == 300 for m in unguarded), unguarded


def test_best_pair_blocks_marginal_pair_touching_recent_buy():
    squad, next_pid = _legal_squad()
    x_id = next_pid
    for i, p in enumerate(squad):
        if p["element_type"] == 3:
            squad[i] = _p(x_id, 3, 60, {2: 8.0}, "X")
            break
    def_out_id = next(p["id"] for p in squad if p["element_type"] == 2)
    gws = [2]
    recent_buys = {x_id: 3.0}  # needed clearance = 4.5

    marginal_pool = squad + [_p(300, 3, 60, {2: 9.0}, "MarginalMid"),
                             _p(400, 2, 45, {2: 1.2}, "MarginalDef")]
    assert tr.best_pair(squad, marginal_pool, 0, gws, recent_buys=recent_buys) is None
    # Kontrolli: sama pari kelpaa ilman recent_buysia.
    unguarded = tr.best_pair(squad, marginal_pool, 0, gws)
    assert unguarded is not None
    assert {unguarded["moves"][0][0]["id"], unguarded["moves"][1][0]["id"]} == {x_id, def_out_id}

    clear_pool = squad + [_p(301, 3, 60, {2: 20.0}, "ClearMid"),
                         _p(401, 2, 45, {2: 15.0}, "ClearDef")]
    clear = tr.best_pair(squad, clear_pool, 0, gws, recent_buys=recent_buys)
    assert clear is not None
    outs = {clear["moves"][0][0]["id"], clear["moves"][1][0]["id"]}
    assert x_id in outs, clear


# ---------------------------------------------------------------------------
# 2. plan_gw kahdella perakkaisella kierroksella (sama kayttotapa kuin
#    plan_transfers): GW1 ostaa piikkipelaajan, GW2 koettelee myyntia.
# ---------------------------------------------------------------------------
def test_plan_gw_holds_spike_buy_against_marginal_follow_up():
    """Tuotannon tapaus (3.9, entry 116920): GW5 osti Wissan, GW8 myi hanet
    pois tavallisesta parannuksesta. Tama toistaa saman kahdella
    peräkkäisellä `plan_gw`-kutsulla jaetulla `recent_buys`-tilalla."""
    squad, next_pid = _legal_squad()
    x_id = next_pid
    # X: piikki GW1:lla (8.0), sitten tyhjaa (0.0) - sama profiili kuin
    # tuotannon "yhden ottelun nousija" -tapaus.
    pool = squad + [_p(x_id, 3, 45, {1: 8.0, 2: 0.0, 3: 0.0}, "X")]

    recent_buys: dict[int, float] = {}
    gw1 = tr.plan_gw(squad, pool, 0, [1, 2, 3], 1, recent_buys=recent_buys)
    assert [(m["out"]["id"], m["in"]["id"]) for m in gw1["moves"]] == [
        (next((p["id"] for p in squad if p["element_type"] == 3)), x_id)]
    assert recent_buys == {x_id: gw1["moves"][0]["gain_weighted"]}
    squad_after_gw1 = gw1["squad"]
    ft2 = min(FT_CARRY_MAX, gw1["ft_left"] + 1)

    # GW2: marginaali parannus ilmestyy. Sama vahvuus kuin X:n vertaiset
    # (2.0/GW), joten TAVALLINEN ostettava mutta ei riittava korvaamaan
    # sita minka takia X ostettiin (kynnys = ostohyoty * CHURN_CLEAR_FACTOR).
    marginal_pool = squad_after_gw1 + [_p(300, 3, 45, {2: 2.0, 3: 2.0}, "Marginal")]
    gw2_guarded = tr.plan_gw(squad_after_gw1, marginal_pool, gw1["bank_tenths"],
                             [2, 3], ft2, recent_buys=dict(recent_buys))
    sold = [m["out"]["id"] for m in gw2_guarded["moves"]]
    assert x_id not in sold, (
        "churn: X myytiin pois marginaalista parannuksesta heti oston jalkeen")

    # NEGATIIVINEN KONTROLLI: sama tilanne ILMAN recent_buysia MYY X:n pois -
    # tama on juuri se tuotantovika joka korjattiin. Jos tama assertio
    # lakkaa pitamasta, ylla oleva testi lapaisee tyhjana (ei mittaa mitaan).
    gw2_unguarded = tr.plan_gw(squad_after_gw1, marginal_pool, gw1["bank_tenths"],
                               [2, 3], ft2)
    sold_unguarded = [m["out"]["id"] for m in gw2_unguarded["moves"]]
    assert x_id in sold_unguarded, (
        "kontrolli epaonnistui: ilman korjausta churnia ei edes toistu, "
        "eika testi siis mittaa mitaan")

    # Mutta guard EI jaadyta koko rungon parannusta: Marginal on silti
    # parempi kuin joku muu heikko pelaaja, joten se ostetaan JOHONKIN
    # muuhun paikkaan.
    assert gw2_guarded["moves"], "aito parannus toiseen paikkaan ei saa estya"


def test_plan_gw_allows_genuine_reversal_of_recent_buy():
    """Negatiivinen kontrolli koko mekanismille: kun uusi loyto on SELVASTI
    parempi (ei vain nipin napin), X saa silti myyda pois - muuten guard
    olisi liian tiukka ja estaisi aidon kaanteen (rivin oma vaatimus)."""
    squad, next_pid = _legal_squad()
    x_id = next_pid
    pool = squad + [_p(x_id, 3, 45, {1: 8.0, 2: 0.0, 3: 0.0}, "X")]

    recent_buys: dict[int, float] = {}
    gw1 = tr.plan_gw(squad, pool, 0, [1, 2, 3], 1, recent_buys=recent_buys)
    squad_after_gw1 = gw1["squad"]
    ft2 = min(FT_CARRY_MAX, gw1["ft_left"] + 1)

    clear_pool = squad_after_gw1 + [_p(301, 3, 45, {2: 20.0, 3: 20.0}, "Clear")]
    gw2 = tr.plan_gw(squad_after_gw1, clear_pool, gw1["bank_tenths"], [2, 3], ft2,
                     recent_buys=dict(recent_buys))
    sold = [(m["out"]["id"], m["in"]["id"]) for m in gw2["moves"]]
    assert (x_id, 301) in sold, sold
