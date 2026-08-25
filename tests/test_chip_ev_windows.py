"""Chip-EV: ikkuna jonka deadline on mennyt ei saa olla tarjolla (25.8).

🔴 Tama on datavika eika copy-vika. Mitattu tuotannosta 24.8:
`/api/fantasy/chip-ev` palautti `horizon_gws: [1,2,3,4,5,6]` ja
`windows[0].gw = 1` samalla kun `meta.deadline_gameweek` oli 2 ja GW1:n
deadline oli mennyt 21.8. Tyokalu kehotti pelaamaan chipin kierrokselle jota
ei voi enaa pelata, ja `best`-lohkon "paras ikkuna" saattoi osua siihen.

Sama vikaluokka korjattiin siirtosuunnitteluun 22.8
(`fpl_rate_team.planning_start_gw`), mutta chip-EV jai ulos. Testi sitoo
molemmat samaan lahteeseen: `meta.deadline_gameweek`.
"""
from __future__ import annotations

from api.fantasy_edge import _playable_gws


def _pool(gws):
    return [{"gameweeks": [{"gw": g} for g in gws]}]


def test_menneen_deadlinen_kierros_pudotetaan():
    """Tuotannon 24.8 tilanne tasan: horisontti 1-6, deadline jo GW2:ssa."""
    out = _playable_gws(_pool([1, 2, 3, 4, 5, 6]),
                        {"meta": {"deadline_gameweek": 2}})
    assert out == [2, 3, 4, 5, 6]
    assert 1 not in out, "GW1:n deadline meni 21.8 - sita ei saa tarjota"


def test_kulumassa_oleva_kierros_sailyy_kun_deadline_on_edessa():
    """Ennen deadlinea GW1 on taysin kelvollinen ikkuna. Suodatin ei saa olla
    'pudota aina ensimmainen' vaan sen on luettava deadlinea."""
    out = _playable_gws(_pool([1, 2, 3]), {"meta": {"deadline_gameweek": 1}})
    assert out == [1, 2, 3]


def test_puuttuva_kentta_ei_muuta_kaytosta():
    """Vanha xp-payload ilman `deadline_gameweek`:ia -> bittitarkasti entinen
    kaytos. Fail-open on tassa oikein: kentan puuttuminen ei ole todiste siita
    etta deadline olisi mennyt."""
    gws = [1, 2, 3]
    assert _playable_gws(_pool(gws), {"meta": {}}) == gws
    assert _playable_gws(_pool(gws), {}) == gws
    assert _playable_gws(_pool(gws), {"meta": {"deadline_gameweek": None}}) == gws
    # ...eika merkkijono saa lapaista int-tarkistusta
    assert _playable_gws(_pool(gws), {"meta": {"deadline_gameweek": "2"}}) == gws


def test_kaikki_kierrokset_menneet_palauttaa_tyhjan_eika_kaada():
    """Jos horisontissa ei ole yhtaan pelattavaa kierrosta, oikea vastaus on
    tyhja lista. Tyhja on rehellinen; vanhan kierroksen tarjoaminen ei ole."""
    assert _playable_gws(_pool([1, 2]), {"meta": {"deadline_gameweek": 9}}) == []
