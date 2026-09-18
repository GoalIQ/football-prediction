# -*- coding: utf-8 -*-
"""IKKUNAN ALKU ON LUPA, EI PELKKA FAKTA (18.9.2026, julkaisutarkistajan B3).

MITATTU VIKA. `/api/fantasy/xp?league=spl` palauttaa tuotannossa (mitattu
18.9.2026):

    next_gameweek     8
    deadline_gameweek None
    horizon_gw        6
    rivit             GW8-GW13

`attach_horizon_total_actionable` rajasi summan `actionable_gameweek`illa, ja
se putoaa ilman deadlinea takaisin `current_gameweek`iin eli
`next_gameweek`iin. Vanha koodi julkaisi siis `horizon_total_from: 8`, ja
klientti — joka lukee kentan lupauksena "summa alkaa seuraavasta deadlinesta"
— olisi kirjoittanut JULKISEEN KUVAAN "GW8-GW13" ja "next 6 GWs" ikkunalle
joka on johdettu kentasta jonka drift on SPL-feedissa MITTAAMATTA (jono
SPL-DEADLINE-GW-MITTAUS). PNG:ta ei voi korjata jalkikateen.

Molemmat klientit (mobiilin `lib/xpHorizon.ts`, SPA:n
`web/pro-spa/src/lib/xpHorizon.ts`) kieltaytyvat lukemasta `next_gameweek`ia
ikkunan alkuna. Backend kiersi sen kiellon puolestaan. Tama testi lukitsee
molemman paan saman saannon:

    horizon_total_from julkaistaan VAIN kun se tulee `deadline_gameweek`ista.
    Ilman sita: lukumaara (`horizon_total_gw`) on tosi, kierrosvali ja sana
    "next" eivat ole.

SUMMA EI MUUTU. Rajaus tehdaan yha actionable-kierroksella, joten luvut ovat
bittitarkasti entiset — vain lupa nimeta ikkuna katoaa. Sita vartioi
`test_sum_is_unchanged_without_a_deadline`.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.fpl_xp import (  # noqa: E402
    attach_horizon_total_actionable, horizon_sum_gw, horizon_total_licence,
    horizon_total_meta,
)

# RSL:n muoto 18.9: rivit GW8-13, ei deadlinea.
SPL_GWS = [8, 9, 10, 11, 12, 13]
SPL_XP = {8: 7.0, 9: 7.0, 10: 7.0, 11: 7.0, 12: 7.0, 13: 7.07}


def _payload(deadline_gw, next_gw=8, gws=None):
    gws = gws or SPL_GWS
    return {
        "meta": {
            "league": "spl",
            "season": "2026/27",
            "next_gameweek": next_gw,
            "deadline_gameweek": deadline_gw,
            "horizon_gw": len(gws),
        },
        "players": [{
            "id": 1,
            "web_name": "A",
            "xp_horizon_total": 999.0,  # putken luku: on korvauduttava
            "gameweeks": [{"gw": g, "xp": SPL_XP[g]} for g in gws],
        }],
    }


# ---------------------------------------------------------------------------
# 1. SPL: ei deadlinea -> ei alkua
# ---------------------------------------------------------------------------

def test_spl_shape_publishes_no_window_start():
    """Mitattu muoto: deadline_gameweek None, next_gameweek 8."""
    out = attach_horizon_total_actionable(_payload(None))
    meta = out["meta"]
    assert meta["horizon_total_from"] is None, (
        "ikkunan alku julkaistiin ilman deadlinea - se on `next_gameweek` "
        "toisessa asussa, ja klientti lukee sen 'next'-lupauksena")
    assert meta["horizon_total_gw"] == 6, "lukumaara on mitattu fakta ja jaa"
    # Eika `next_gameweek` saa vuotaa kentan lapi missaan asussa.
    assert meta["horizon_total_from"] != meta["next_gameweek"]


@pytest.mark.parametrize("deadline", [None, "8", 8.0, True, False, {}])
def test_only_a_real_int_deadline_is_a_licence(deadline):
    """Roska ei ole deadline. `True` on Pythonissa int-alityyppi, ja
    `horizon_total_from: True` olisi renderoitunut kierrokseksi 1."""
    meta = attach_horizon_total_actionable(_payload(deadline))["meta"]
    assert meta["horizon_total_from"] is None, deadline


def test_sum_is_unchanged_without_a_deadline():
    """LUVUT EIVAT MUUTU: vain lupa nimeta ikkuna katoaa.

    Ilman deadlinea rajaus tulee yha `next_gameweek`ista, eli jos GW8 olisi
    jo alkanut, summa on sama kuin ennen tata committia. Kaytos on
    bittitarkasti entinen; muuttunut on se mita metassa LUVATAAN."""
    # next_gameweek 9 -> GW8 pudotettu summasta, kuten ennenkin
    out = attach_horizon_total_actionable(_payload(None, next_gw=9))
    p = out["players"][0]
    assert p["xp_horizon_total"] == round(sum(
        x for g, x in SPL_XP.items() if g >= 9), 2)
    assert out["meta"]["horizon_total_gw"] == 5
    assert out["meta"]["horizon_total_from"] is None
    # rivit ennallaan
    assert [g["gw"] for g in p["gameweeks"]] == SPL_GWS


# ---------------------------------------------------------------------------
# 2. EROTTELEVA: deadline lapsena -> alku JA vali
# ---------------------------------------------------------------------------

def test_deadline_present_still_publishes_the_start():
    """Ilman tata testi olisi vihrea siksi etta kentta katosi kokonaan.

    PL:n muoto (mitattu 18.9: deadline_gameweek 5) saa yha alun, ja se on
    tasan deadline-kierros — ei rivien ensimmainen eika `next_gameweek`."""
    out = attach_horizon_total_actionable(_payload(9, next_gw=8))
    meta = out["meta"]
    assert meta["horizon_total_from"] == 9
    assert meta["horizon_total_gw"] == 5
    assert meta["next_gameweek"] == 8, "deadline ja next ovat eri kierros"
    # Ja summa alkaa sielta mihin meta osoittaa.
    assert out["players"][0]["xp_horizon_total"] == round(sum(
        x for g, x in SPL_XP.items() if g >= 9), 2)


def test_meta_helper_carries_the_same_answer_to_every_route():
    """`horizon_total_meta()` on se mita rate-team, fit, compare ym.
    liittavat omaan metaansa. Jos se keksisi alun, korjaus koskisi vain
    /api/fantasy/xp:ta ja kaikki muut reitit vuotaisivat vanhan lupauksen."""
    spl = attach_horizon_total_actionable(_payload(None))["meta"]
    assert horizon_total_meta(spl) == {
        "horizon_total_from": None, "horizon_total_gw": 6}
    pl = attach_horizon_total_actionable(_payload(9))["meta"]
    assert horizon_total_meta(pl) == {
        "horizon_total_from": 9, "horizon_total_gw": 5}


# ---------------------------------------------------------------------------
# 3. Sama saanto otsikkolukijalle: ei keksittya kuutosta
# ---------------------------------------------------------------------------

def test_horizon_sum_gw_does_not_invent_a_six():
    """Julkaisutarkistajan "MUUT": mobiili kieltaytyi keksimasta, web ei.

    `horizon_sum_gw(meta, gws=None, fallback=6)` palautti kuusi payloadille
    joka ei kertonut ikkunastaan mitaan, ja sivut kirjoittivat sen otsikkoon.
    Oletus on nyt None; kutsupaikka joka haluaa oletuksen antaa sen itse ja
    se nakyy diffissa."""
    assert horizon_sum_gw({}) is None
    assert horizon_sum_gw(None) is None
    assert horizon_sum_gw({"season": "2026/27"}) is None
    # Tosi tieto kelpaa yha, samassa jarjestyksessa kuin ennen.
    assert horizon_sum_gw({"horizon_gw": 6}) == 6
    assert horizon_sum_gw({"horizon_gw": 6, "horizon_total_gw": 5}) == 5
    # Eksplisiittinen oletus on yha mahdollinen - mutta nakyva.
    assert horizon_sum_gw({}, fallback=6) == 6
    # SPL-muoto: lukumaara tulee, alku ei.
    spl = attach_horizon_total_actionable(_payload(None))["meta"]
    assert horizon_sum_gw(spl) == 6
    assert spl["horizon_total_from"] is None


def test_licence_reads_only_the_deadline():
    """Yksikkotaso: lupa tulee vain deadlinesta, roska ei ole lupa."""
    assert horizon_total_licence({"deadline_gameweek": 9}) == 9
    assert horizon_total_licence({"deadline_gameweek": None,
                                  "next_gameweek": 8}) is None
    assert horizon_total_licence({"next_gameweek": 8}) is None
    assert horizon_total_licence({}) is None
    assert horizon_total_licence(None) is None
    assert horizon_total_licence({"deadline_gameweek": True}) is None


def test_source_does_not_fall_back_to_next_gameweek():
    """LAHDEPORTTI. Yksikkotesti nakee VASTAUKSEN, ei sita mista alku tulee:
    `meta["horizon_total_from"] = gw` nayttaisi oikealta jokaisessa
    fikstuurissa jossa deadline on olemassa, ja vuotaisi vain siella missa
    sita ei ole - eli SPL:ssa, jota yksikaan fikstuuri ei ennen 18.9
    kattanut. Luetaan lupafunktion runko.

    Lupa on OMA funktionsa juuri tata varten: kun paatos asui
    `attach_horizon_total_actionable`in sisalla, portti joutui arvaamaan
    mihin asti lause ulottuu.
    """
    src = (ROOT / "src" / "models" / "fpl_xp.py").read_text(encoding="utf-8")
    alku = src.index("def horizon_total_licence(")
    runko = src[alku:src.index("\ndef ", alku + 10)]
    # Docstring ja kommentit pois: ne SELITTAVAT vian sanomalla
    # `next_gameweek`, ja skanneri loytaisi oman selityksensa.
    koodi = runko.split('"""')[-1]
    koodi = "\n".join(l for l in koodi.split("\n")
                       if not l.strip().startswith("#"))
    assert "deadline_gameweek" in koodi, koodi
    for kielletty in ("next_gameweek", "current_gameweek",
                      "actionable_gameweek", "min("):
        assert kielletty not in koodi, (
            "ikkunan alku johdetaan %s:sta - se on sama luku ilman lupaa:%s"
            % (kielletty, koodi))
    # Ja kutsupaikka kayttaa TATA funktiota, ei omaa kaavaansa.
    att = src[src.index("def attach_horizon_total_actionable("):]
    att = att[:att.index("\ndef ")]
    rivi = [l for l in att.split("\n")
            if 'meta["horizon_total_from"]' in l and "=" in l]
    assert rivi == [
        '    meta["horizon_total_from"] = horizon_total_licence(meta)'], rivi
