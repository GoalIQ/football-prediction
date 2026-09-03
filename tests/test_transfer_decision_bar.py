"""Siirtopaatoksen kynnys: lahi-ikkuna, hitin marginaali, entry-kohtaisuus.

MIKSI (3.9.2026, Villen GO - `cos-reports/siirtomoottorin-paatoskynnykset.md`).
Kuusi muutosta joista jokainen epaonnistuisi HILJAA: suunnitelma nayttaisi
edelleen siirtoja, ne olisivat vain vaaria siirtoja. Mikaan pinta ei huutaisi.

Hermeettinen: synteettinen pooli, ei verkkoa eika artefaktia. Jokaiselle
ehdolle NEGATIIVINEN KONTROLLI - tapaus jossa saannon pitaa olla laukeamatta.
Pelkka "toimii oikein" -tapaus ei erota toimivaa ehtoa ehdosta joka on aina
tosi.
"""
from __future__ import annotations

import src.models.fpl_rate_team as rt
from src.models import fpl_transfers as e

GWS = [3, 4, 5, 6, 7, 8]


def mk(pid: int, pos: int, club: int, price: int, per_gw, **extra) -> dict:
    """Poolin muotoinen pelaaja. `per_gw` = luku tai lista kierroksittain."""
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
    """Laillinen 15: 2 GKP, 5 DEF, 5 MID, 3 FWD, korkeintaan 3/klubi."""
    squad = [mk(1, 1, 1, 45, 3.0), mk(2, 1, 2, 40, 1.0)]
    for i, pid in enumerate(range(10, 15)):
        squad.append(mk(pid, 2, 3 + i, 45, 3.0))
    for i, pid in enumerate(range(20, 25)):
        squad.append(mk(pid, 3, 8 + i, 60, 4.0))
    for i, pid in enumerate(range(30, 33)):
        squad.append(mk(pid, 4, 13 + i, 70, 4.5))
    return squad


# ---------------------------------------------------------------------------
# (1) Paatos tehdaan LAHI-ikkunasta, ei kuuden kierroksen summasta
# ---------------------------------------------------------------------------

def test_hyoty_horisontin_hannassa_ei_kelpaa():
    """Kaikki hyoty GW7-GW8:ssa -> ei ehdoteta GW3:ssa (voit ostaa myohemmin)."""
    squad = base_squad()
    tail = mk(99, 3, 20, 60, [4.0, 4.0, 4.0, 4.0, 12.0, 12.0])
    step = e.plan_gw(squad, [tail], 0, GWS, ft=1)
    assert step["moves"] == []


def test_NEG_etupainoinen_hyoty_kelpaa():
    """Negatiivinen kontrolli: sama kokonaishyoty ETUPAINOISENA -> ehdotetaan."""
    squad = base_squad()
    front = mk(99, 3, 20, 60, [12.0, 12.0, 4.0, 4.0, 4.0, 4.0])
    step = e.plan_gw(squad, [front], 0, GWS, ft=1)
    assert [m["in"]["id"] for m in step["moves"]] == [99]
    assert step["moves"][0]["gain_near"] > 0


def test_lahi_ikkuna_on_kaksi_kierrosta():
    assert e.near_gws(GWS) == [3, 4]
    assert e.near_gws([]) is None
    assert e.near_gws(None) is None


# ---------------------------------------------------------------------------
# (2)+(5) Yksi kynnys, kaksi ikkunaa - molemmat JOHDETTU samasta luvusta
# ---------------------------------------------------------------------------

def test_kynnykset_johdetaan_samasta_luvusta():
    """Kaatuu jos joku asettaa kynnykset toisistaan riippumatta.

    Tama on koko kohdan 5 vika: sama ruutu naytti hold-verdiktin (2.0
    horisontille) ja suunnitelman (0.5 per siirto), ja ne antoivat eri
    vastauksen samaan kysymykseen.
    """
    assert e.MIN_GAIN_PER_TRANSFER == round(
        rt.DECISION_BAR_XP_PER_GW * e.NEAR_WINDOW_GWS, 2)
    assert rt.HOLD_THRESHOLD_XP == round(
        rt.DECISION_BAR_XP_PER_GW * rt.HOLD_HORIZON_GWS, 2)
    assert rt.hold_threshold_for(3) == round(rt.DECISION_BAR_XP_PER_GW * 3, 2)
    assert (e.MIN_GAIN_PER_TRANSFER / e.NEAR_WINDOW_GWS
            == rt.HOLD_THRESHOLD_XP / rt.HOLD_HORIZON_GWS)


def test_kynnyksen_alle_jaava_siirto_ei_kelpaa():
    squad = base_squad()
    weak = mk(99, 3, 20, 60, 4.3)      # +0.6 lahi-ikkunassa < 1.0
    assert e.plan_gw(squad, [weak], 0, GWS, ft=1)["moves"] == []
    ok = mk(98, 3, 21, 60, 4.6)        # +1.2 lahi-ikkunassa > 1.0
    assert [m["in"]["id"]
            for m in e.plan_gw(squad, [ok], 0, GWS, ft=1)["moves"]] == [98]


# ---------------------------------------------------------------------------
# (3) Hitille oma marginaali - ja valtaosa hyodysta lahi-ikkunasta
# ---------------------------------------------------------------------------

def test_hitti_ei_kelpaa_vanhalla_rimalla():
    """gain 4.6 + ft=0: vanha saanto (netto >= 0.5) olisi hyvaksynyt taman.

    Yhden kierroksen erotuksen keskihajonta on +-4.34 p (mitattu n=607), eli
    se olisi varma -4 kolikonheitosta.
    """
    squad = base_squad()
    cand = mk(99, 3, 20, 60, [6.3, 6.3, 4.0, 4.0, 4.0, 4.0])
    assert round(cand["xp_horizon_total"] - 24.0, 1) == 4.6
    assert e.plan_gw(squad, [cand], 0, GWS, ft=0)["moves"] == []


def test_NEG_riittavan_iso_etupainoinen_hitti_kelpaa():
    squad = base_squad()
    cand = mk(99, 3, 20, 60, [8.5, 8.5, 4.0, 4.0, 4.0, 4.0])
    moves = e.plan_gw(squad, [cand], 0, GWS, ft=0)["moves"]
    assert [m["in"]["id"] for m in moves] == [99]
    assert moves[0]["hit"] == rt.HIT_COST_XP


def test_iso_mutta_hantapainoinen_hitti_ei_kelpaa():
    """Sama kokonaishyoty hanta edella: -4 maksetaan nyt, hyoty tulee myohemmin."""
    squad = base_squad()
    cand = mk(99, 3, 20, 60, [4.2, 4.2, 4.0, 4.0, 8.4, 8.4])
    assert e.plan_gw(squad, [cand], 0, GWS, ft=0)["moves"] == []


# ---------------------------------------------------------------------------
# (6) Kynnys on entry-kohtainen: (ft, runko)
# ---------------------------------------------------------------------------

def test_bar_ft_porras():
    assert e.transfer_bar(1)["reason"] == "default"
    assert e.transfer_bar(2)["reason"] == "default"
    assert e.transfer_bar(3)["reason"] == "bank_deep"
    assert e.transfer_bar(3)["min_net"] < e.transfer_bar(1)["min_net"]
    assert e.transfer_bar(5)["reason"] == "bank_full"
    assert e.transfer_bar(5)["min_net"] < e.transfer_bar(3)["min_net"]
    assert e.transfer_bar(0)["hit"] is True
    assert e.transfer_bar(0)["min_gain"] == e.MIN_GAIN_FOR_HIT


def test_NEG_ilman_entrya_kynnys_on_moduulivakio():
    """Manual/draft-moodi: ei ft-tietoa -> kynnys ei saa muuttua."""
    for ft in (0, 1, 3, 5):
        bar = e.transfer_bar(ft, entry_known=False)
        if ft <= 0:
            assert bar["reason"] == "hit"
        else:
            assert bar["min_net"] == e.MIN_GAIN_PER_TRANSFER
            assert bar["reason"] == "default"


def test_ft5_ottaa_siirron_jonka_ft1_jattaa():
    """Pankki katossa: kayttamatta jattaminen hukkaa kertyman -> rima ~0."""
    squad = base_squad()
    small = mk(99, 3, 20, 60, 4.3)
    assert e.plan_gw(squad, [small], 0, GWS, ft=1)["moves"] == []
    moves5 = e.plan_gw(squad, [small], 0, GWS, ft=5)["moves"]
    assert [m["in"]["id"] for m in moves5] == [99]
    assert moves5[0]["gain"] > 0


def test_korjaus_lapaisee_matalamman_riman():
    """Pelaaja jota ei voi pelata (0 xP joka kierros) = korjaus, ei optimointi.

    Rikkinainen pelaaja syo runkopaikan: XI on 11 parasta NELJASTATOISTA. Kun
    hanen tilalleen tulee pelaaja joka mahtuu XI:hin, hyoty on aito vaikka
    pieni — ja juuri se on korjaus jonka pitaa lapaista matalampi rima.
    """
    squad = [p for p in base_squad() if p["id"] != 20]
    squad.append(mk(20, 3, 8, 60, 0.0, no_projection=True))
    repl = mk(99, 3, 20, 60, 4.3)     # +0.6 lahi-ikkunassa: ALLE 1.0:n riman
    moves = e.plan_gw(squad, [repl], 0, GWS, ft=1)["moves"]
    assert [m["out"]["id"] for m in moves] == [20]
    assert moves[0]["bar"]["reason"] == "repair"


def test_NEG_saman_kokoinen_optimointi_ei_lapaise():
    """Negatiivinen kontrolli: TASAN sama hyoty TOIMIVAA pelaajaa vastaan.

    Sama tulija, sama +0.6 lahi-ikkunassa, ainoa ero on ettei lahtija ole
    rikki. Ilman tata paria "korjaus lapaisee" ei erottaisi matalasta rimasta
    ehtoa joka paastaa kaiken lapi.
    """
    squad = base_squad()
    repl = mk(99, 3, 20, 60, 4.3)
    assert e.plan_gw(squad, [repl], 0, GWS, ft=1)["moves"] == []


def test_needs_repair_lahteet():
    assert e.needs_repair({"no_projection": True}) is True
    assert e.needs_repair({"status": "u"}) is True
    assert e.needs_repair({"status": "a", "chance_next": 0}) is True
    assert e.needs_repair({"status": "a", "chance_next": 100}) is False
    assert e.needs_repair({}) is False


def test_placeholder_tuo_projektiottoman_takaisin_runkoon():
    boot = {"elements": [{"id": 7, "web_name": "Dovin", "team": 3,
                          "element_type": 1, "now_cost": 45, "status": "u",
                          "news": "Season loan"}],
            "teams": [{"id": 3, "short_name": "SUN"}]}
    ph = e.placeholder_player(7, boot)
    assert ph["xp_horizon_total"] == 0.0 and ph["gameweeks"] == []
    assert ph["team_short"] == "SUN" and ph["price"] == 45
    assert e.needs_repair(ph) is True
    assert e.placeholder_player(999, boot) is None


# ---------------------------------------------------------------------------
# (4) LAUSE JA VERTAILU — julkaisuportin vaatima invariantti (3.9)
#
# Portti rakensi tapauksen jossa lause vaitti luvun 1.33 olevan alle 0.50:n:
# luku haettiin eri haulla (ilman lahi-ikkunaa) ja verrattiin moduulivakioon,
# kun paatos tehtiin lahi-ikkunalla ja entry-kohtaisella rimalla. Tama testi
# ei etsi sita virhetta vaan tekee siita mahdottoman: JOS lause sanoo "under",
# tulostetun luvun on oltava aidosti pienempi kuin tulostetun riman — ajettuna
# jokaisella ft-arvolla ja korjaustapauksella.
# ---------------------------------------------------------------------------
import re

from src.models.fpl_planner import hold_message


def _printed(msg: str) -> tuple[float, float] | None:
    """Lauseesta tulostetut luvut. Kuvio ilman kenoviivoja tarkoituksella:
    kenoviiva katoaa tyokaluketjussa (ks. muisti regexin-b-backspace)."""
    m = re.search("([+-][0-9.]+) xP per gameweek .*?under your "
                  "([0-9.]+) threshold", msg)
    return (float(m.group(1)), float(m.group(2))) if m else None


def test_under_lause_vain_kun_luku_on_riman_alla():
    squad = base_squad()
    pools = {
        "ei mitaan": [],
        "hyvin pieni": [mk(99, 3, 20, 60, 4.05)],
        "pieni": [mk(98, 3, 21, 60, 4.3)],
        "iso": [mk(97, 3, 22, 60, [12.0, 12.0, 4.0, 4.0, 4.0, 4.0])],
        "hantapainoinen": [mk(96, 3, 23, 60, [4.0, 4.0, 4.0, 4.0, 12.0, 12.0])],
    }
    seen_under = 0
    for name, pool in pools.items():
        for ft in (0, 1, 3, 5):
            best = e.best_move_summary(squad, pool, 0, GWS, ft)
            step = e.plan_gw(squad, pool, 0, GWS, ft)
            msg = hold_message(len(step["moves"]), 0.0, GWS, best)
            pr = _printed(msg)
            if pr is None:
                continue
            seen_under += 1
            val, bar = pr
            assert val < bar, f"{name} ft={ft}: lause vaittaa {val} < {bar}: {msg}"
    # Kontrolli: jos yksikaan haara ei tulostanut "under"-lausetta, testi ei
    # ole mitannut mitaan (portti joka lapaisee tyhjana, ks. muisti).
    assert seen_under >= 4, f"vain {seen_under} 'under'-lausetta - testi ei mittaa"


def test_under_lause_ei_synny_kun_luku_ylittaa_riman():
    """NEGATIIVINEN KONTROLLI: riman ylittava siirto EI saa lausetta 'under'."""
    over = {"case": "over_bar", "value_xp_per_gw": 2.0, "bar_xp_per_gw": 0.5,
            "window_gws": [3, 4]}
    msg = hold_message(0, 0.0, GWS, over)
    assert "under" not in msg
    assert "No move the model checked" in msg


def test_hylattya_sanamuotoa_ei_palaa_lauseeseen():
    """'Best move available' oli portin 29.8 hylkaama kattavuusvaite."""
    cases = [
        None,
        {"case": "below_bar", "value_xp_per_gw": 0.06, "bar_xp_per_gw": 0.5,
         "window_gws": [3, 4]},
        {"case": "later", "window_gws": [3, 4]},
    ]
    for best in cases:
        for n in (0, 3):
            msg = hold_message(n, 4.2, GWS, best)
            low = msg.lower()
            assert "available" not in low, msg
            assert "beats" not in low, msg
            assert "no plan" not in low, msg


def test_per_kierros_luku_tasmaa_naytettyyn_kokonaislukuun():
    """Lukija joka jakaa nakemansa luvun kierroksilla saa saman vastauksen."""
    msg = hold_message(5, 5.4567, GWS, None)
    m = re.search(r"([+-][0-9.]+) xP net, ([+-][0-9.]+) xP per gameweek", msg)
    assert m, msg
    total, per_gw = float(m.group(1)), float(m.group(2))
    assert round(total / len(GWS), 2) == per_gw
    assert "spread across" in msg   # 5 siirtoa EI ole taman kierroksen siirtoja
