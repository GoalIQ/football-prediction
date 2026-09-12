"""Suunnitelma ei saa myyda sita jonka se itse osti.

🔴 MITATTU 7.9 ja uudelleen 12.9 tuotannon datalla:
`plan_transfers(entry=4089628, horizon=6, ft=5)` antoi

    GW7: Enciso -> Ndiaye      (gain 1.38)
    GW8: Ndiaye -> Gibbs-White (gain 1.83)

Suunnitelma poltti KAKSI siirtoa paatyakseen Gibbs-Whiteen, vaikka suora osto
GW7:ssa olisi ollut vahintaan yhta hyva. Juurisyy: `plan_transfers` kutsuu
`plan_gw`:ta kierros kerrallaan eika moottori muista keta sama suunnitelma on
jo ostanut.

MITATTU VAIKUTUS (`python -m scripts.measure_transfer_bar`, sama skripti
molemmilla puolilla):
    ennen: entry 4089628 ft=5 -> 9 siirtoa, netto 38.68, churn 1 (5/80 rivia)
    jalkeen:                     7 siirtoa, netto 38.28, churn 0 (0/80)
Kauppa on siis **kaksi siirtoa vahemman, -0.40 xP kuudelle kierrokselle**
(kaikkien entryjen keskiarvo 21.04 -> 20.84). Se on tietoinen valinta: neuvo
joka nakyvasti kumoaa itsensa maksaa enemman kuin 0.4 xP.

Hermeettinen: synteettinen pooli, ei verkkoa eika artefaktia. Jokaiselle
ehdolle NEGATIIVINEN KONTROLLI.
"""
from __future__ import annotations

from src.models import fpl_transfers as e

GWS = [3, 4, 5, 6, 7, 8]


def mk(pid: int, pos: int, club: int, price: int, per_gw, **extra) -> dict:
    vals = [per_gw] * len(GWS) if isinstance(per_gw, (int, float)) else list(per_gw)
    row = {
        "id": pid, "web_name": f"P{pid}", "team_short": f"C{club:02d}",
        "element_type": pos, "club": club, "price": price,
        "owned_pct": 5.0,
        "xp_per_gw": round(sum(vals) / len(vals), 3),
        "xp_horizon_total": round(sum(vals), 3),
        "gameweeks": [{"gw": g, "opponents": [], "xp": v}
                      for g, v in zip(GWS, vals)],
        "status": "a",
    }
    row.update(extra)
    return row


def base_squad() -> list[dict]:
    squad = [mk(1, 1, 1, 45, 3.0), mk(2, 1, 2, 40, 1.0)]
    for i, pid in enumerate(range(10, 15)):
        squad.append(mk(pid, 2, 3 + i, 45, 3.0))
    for i, pid in enumerate(range(20, 25)):
        squad.append(mk(pid, 3, 8 + i, 60, 4.0))
    for i, pid in enumerate(range(30, 33)):
        squad.append(mk(pid, 4, 13 + i, 70, 4.5))
    return squad


# ---------------------------------------------------------------------------
# 1. churn_bar: ehto yksin
# ---------------------------------------------------------------------------

def test_suojaamaton_lahtija_saa_tavallisen_riman():
    out = mk(20, 3, 8, 60, 4.0)
    assert e.churn_bar(1.0, out, set()) == 1.0
    assert e.churn_bar(1.0, out, None) == 1.0
    assert e.churn_bar(1.0, out, {999}) == 1.0


def test_suojattu_lahtija_saa_kaksinkertaisen_riman():
    out = mk(20, 3, 8, 60, 4.0)
    assert e.churn_bar(1.0, out, {20}) == 2.0
    assert e.churn_bar(0.5, out, {20}) == 1.0


def test_korjaus_ohittaa_korotuksen():
    """NEGATIIVINEN KONTROLLI: ostettu pelaaja joka menettaa pelikelpoisuutensa.

    Jos korotettu rima patisi myos taha, suunnitelmaan jaisi pelaaja jota ei
    voi pelata - ja se on pahempi kuin churn."""
    loukkaantunut = mk(20, 3, 8, 60, 4.0, status="i")
    assert e.needs_repair(loukkaantunut) is True
    assert e.churn_bar(1.0, loukkaantunut, {20}) == 1.0
    ei_projektiota = mk(21, 3, 9, 60, 0.0, no_projection=True)
    assert e.churn_bar(1.0, ei_projektiota, {21}) == 1.0


# ---------------------------------------------------------------------------
# 2. plan_gw: osta->myy ei mahdu edes saman kierroksen kahteen siirtoon
# ---------------------------------------------------------------------------

def test_saman_kierroksen_osto_ei_ole_seuraavan_siirron_lahtija():
    """Kahden siirron kierros ei saa ostaa ja myyda samaa pelaajaa."""
    squad = base_squad()
    hyva = mk(90, 3, 20, 60, 9.0)
    viela_parempi = mk(91, 3, 21, 60, 12.0)
    step = e.plan_gw(squad, [hyva, viela_parempi], 0, GWS, ft=2, max_moves=2)
    ostetut = {m["in"]["id"] for m in step["moves"]}
    myydyt = {m["out"]["id"] for m in step["moves"]}
    assert not (ostetut & myydyt), step["moves"]


def test_kutsujan_suojaus_estaa_myynnin():
    """Edellisen kierroksen osto ei kelpaa lahtijaksi ilman selvaa hyotya."""
    squad = base_squad()
    # 90 on jo rungossa ja se on "ostettu aiemmin tassa suunnitelmassa".
    # 90 on rungon heikoin MID, joten han on luonnollinen lahtija.
    squad = [p for p in squad if p["id"] != 20] + [mk(90, 3, 20, 60, 3.8)]
    # +0.8/GW = 1.2 lahi-ikkunassa: ylittaa tavallisen riman (1.0), ei
    # kaksinkertaista (2.0).
    parempi = mk(91, 3, 21, 60, 4.6)
    ilman = e.plan_gw(squad, [parempi], 0, GWS, ft=1)
    suojattu = e.plan_gw(squad, [parempi], 0, GWS, ft=1, protected_ids={90})
    assert any(m["out"]["id"] == 90 for m in ilman["moves"]), \
        "KONTROLLI: ilman suojausta myynti tapahtuu - muuten testi on inertti"
    assert not any(m["out"]["id"] == 90 for m in suojattu["moves"]), \
        suojattu["moves"]
    # ...ja suojaus OHJAA, se ei jaadyta: moottori myy jonkun muun.
    assert suojattu["moves"], "suojaus ei saa estaa kaikkia siirtoja"
    assert suojattu["moves"][0]["in"]["id"] == 91


def test_selvasti_parempi_myynti_sallitaan_yha():
    """NEGATIIVINEN KONTROLLI: suojaus on RIMA, ei kielto.

    Jos se olisi kielto, suunnitelma jaisi loukkuun omaan ostoonsa silloinkin
    kun maailma on muuttunut selvasti."""
    squad = base_squad()
    squad = [p for p in squad if p["id"] != 20] + [mk(90, 3, 20, 60, 3.8)]
    # +2.2/GW = 4.0 lahi-ikkunassa: ylittaa kaksinkertaisen riman selvasti.
    paljon_parempi = mk(91, 3, 21, 60, 6.0)
    step = e.plan_gw(squad, [paljon_parempi], 0, GWS, ft=1, protected_ids={90})
    assert any(m["out"]["id"] == 90 for m in step["moves"]), step["moves"]


def test_protected_ids_palautuu_kutsujalle():
    """Ilman tata `plan_transfers` ei voisi kantaa tilaa kierrosten yli."""
    squad = base_squad()
    hyva = mk(90, 3, 20, 60, 9.0)
    step = e.plan_gw(squad, [hyva], 0, GWS, ft=1)
    assert 90 in step["protected_ids"]
    assert isinstance(step["protected_ids"], set)


def test_myyty_pelaaja_ei_jaa_suojatuksi():
    """Jos suunnitelma myy pelaajan, hanen takaisinostoaan ei pida estaa
    vanhalla suojauksella."""
    squad = base_squad()
    hyva = mk(90, 3, 20, 60, 9.0)
    step = e.plan_gw(squad, [hyva], 0, GWS, ft=1, protected_ids={20})
    myydyt = {m["out"]["id"] for m in step["moves"]}
    if 20 in myydyt:
        assert 20 not in step["protected_ids"]


# ---------------------------------------------------------------------------
# 3. Suojaus ei saa muuttaa mitaan kun ketaan ei ole ostettu
# ---------------------------------------------------------------------------

def test_tyhja_suojaus_antaa_tasmalleen_entisen_tuloksen():
    """MUTAATIO: jos churn_bar korottaisi rimaa vahingossa aina, tama kaatuu."""
    squad = base_squad()
    pool = [mk(90, 3, 20, 60, 9.0), mk(92, 2, 22, 45, 7.0)]
    a = e.plan_gw(squad, pool, 0, GWS, ft=2, max_moves=2)
    b = e.plan_gw(squad, pool, 0, GWS, ft=2, max_moves=2, protected_ids=set())
    avain = lambda s: [(m["out"]["id"], m["in"]["id"]) for m in s["moves"]]
    assert avain(a) == avain(b)
    assert avain(a), "KONTROLLI: vertailu tyhjilla siirroilla ei mittaa mitaan"
