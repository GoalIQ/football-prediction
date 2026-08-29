"""Portti: rate-team ja planner kayttavat SAMAA siirtohorisonttia.

Loydos 29.8.2026 (julkaisuportti k2, mitattu tuotannosta samalle entrylle
samalla sekunnilla): `/api/fantasy/rate-team` palautti `horizon_gws: 6` ja
`/api/fantasy/plan` `5`. Rate-team luki artefaktin nimellisen
`meta.horizon_gw`:n, joka sisaltaa kesken olevan kierroksen jonka deadline on
jo mennyt. Siihen kierrokseen ei voi tehda siirtoa, mutta sen xP oli mukana
jokaisen siirtoehdotuksen hyodyssa -- ja jakokortti julkaisi sen luvun.

Negatiivinen kontrolli on tassa se tarkein: `test_kontrolli_havaitsee_eron`
mittaa etta testi OIKEASTI kaatuisi jos moottorit eroaisivat.
"""

from __future__ import annotations

import pytest

from src.models.fpl_rate_team import planning_start_gw, transfer_horizon_gws


def _pool(gws: list[int]) -> list[dict]:
    return [{"id": 1, "gameweeks": [{"gw": g, "xp": 1.0} for g in gws]}]


def _xp(deadline_gw: int | None, horizon_gw: int = 6) -> dict:
    meta = {"horizon_gw": horizon_gw}
    if deadline_gw is not None:
        meta["deadline_gameweek"] = deadline_gw
    return {"meta": meta}


def test_kesken_oleva_kierros_pudotetaan():
    # Tuotannon tilanne 29.8: artefaktissa GW2-7, deadline_gameweek 3.
    pool = _pool([2, 3, 4, 5, 6, 7])
    gws = transfer_horizon_gws(pool, _xp(3), target_gw=2)
    assert gws == [3, 4, 5, 6, 7]
    assert len(gws) == 5, "rate-team sanoi 6, planner 5 - taman piti korjaantua"


def test_sama_tulos_kuin_plannerin_omalla_laskennalla():
    from src.models.fpl_planner import _horizon_gws

    pool = _pool([2, 3, 4, 5, 6, 7])
    xp = _xp(3)
    start = planning_start_gw(2, pool, xp)
    assert transfer_horizon_gws(pool, xp, 2) == _horizon_gws(pool, start, 6)


def test_cap_rajaa_mutta_ei_muuta_alkua():
    pool = _pool([2, 3, 4, 5, 6, 7])
    assert transfer_horizon_gws(pool, _xp(3), 2, cap=3) == [3, 4, 5]


def test_vanha_payload_ilman_deadlinea_kayttaytyy_entiseen_tapaan():
    # deadline_gameweek puuttuu -> ei saa pudottaa mitaan.
    pool = _pool([2, 3, 4, 5, 6, 7])
    assert transfer_horizon_gws(pool, _xp(None), target_gw=2) == [2, 3, 4, 5, 6, 7]


def test_kauden_lopussa_yksi_kierros_ei_kaadu():
    pool = _pool([38])
    assert transfer_horizon_gws(pool, _xp(38), target_gw=38) == [38]


def test_kontrolli_havaitsee_eron():
    """Jos moottorit eroaisivat, pariteettitesti kaatuisi.

    Ilman tata `test_sama_tulos...` voisi olla vihrea siksi, etta molemmat
    palauttavat saman VAARAN listan, tai etta vertailu on tautologia.
    """
    pool = _pool([2, 3, 4, 5, 6, 7])
    naive = [g["gw"] for g in pool[0]["gameweeks"]]          # vanha rate-team
    fixed = transfer_horizon_gws(pool, _xp(3), target_gw=2)  # uusi
    assert naive != fixed, "kontrolli ei havaitse eroa - testi olisi tyhja"
    assert len(naive) - len(fixed) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ---------------------------------------------------------------------------
# OIKEA POLKU. Kaikki ylla oleva testaa apufunktiota ERILLAAN, eika mikaan
# niista vaita etta `rate_team()` kutsuu sita. Portti k7 mittasi sen:
# molemmat mutaatiot (nimellinen horisontti takaisin, deltat takaisin koko
# artefaktin ikkunalle) jattivat koko 2264 testin sviitin vihreaksi.
# Nama kaksi ajavat oikeat moottorit.

ENTRY = 116920


def _live():
    from src.models.fpl_planner import plan_transfers
    from src.models.fpl_rate_team import rate_team
    return rate_team(entry=ENTRY), plan_transfers(entry=ENTRY, horizon=6)


def test_moottorit_sanovat_saman_horisontin_oikealla_polulla():
    r, p = _live()
    rhv, phv = r["transfers"]["hold_verdict"], p["hold_verdict"]
    assert rhv["horizon_gws"] == phv["horizon_gws"], (
        f"rate-team {rhv['horizon_gws']} vs planner {phv['horizon_gws']}"
    )
    assert rhv["horizon_gws"] == r["meta"]["transfer_horizon_gw"]
    assert (rhv["gw_from"], rhv["gw_to"]) == (phv["gw_from"], phv["gw_to"])


def test_kontrolli_artefaktissa_on_mennyt_deadline():
    """Ilman tata edellinen testi olisi vihrea myos silloin, kun artefaktissa
    ei ole kesken olevaa kierrosta - eli se ei mittaisi mitaan."""
    r, _ = _live()
    assert r["meta"]["transfer_horizon_gw"] < r["meta"]["horizon_gw"], (
        "artefaktissa ei ole mennytta deadlinea; testi ei mittaa eroa. "
        "Ala poista testia - odota kunnes kierros on kaynnissa, tai rakenna "
        "artefakti jossa deadline_gameweek > pienin gameweeks-gw."
    )


def test_deltan_ikkuna_on_sama_kuin_raportoitu_horisontti():
    """Mutaatio joka palauttaa deltat koko artefaktin ikkunaan EI nakynyt
    missaan, koska raportoitu `horizon_gws` tulee eri lahteesta. Deltan ikkuna
    on nyt payloadissa, joten siita voi vaittaa."""
    r, p = _live()
    win = r["transfers"]["window_gws"]
    hv = r["transfers"]["hold_verdict"]
    assert win, "window_gws puuttuu - delta laskettiin koko horisontilta"
    assert len(win) == hv["horizon_gws"]
    assert (win[0], win[-1]) == (hv["gw_from"], hv["gw_to"])
    assert win == list(range(p["meta"]["start_gw"], p["meta"]["start_gw"] + len(win)))
