# -*- coding: utf-8 -*-
"""FREEZE-BANK-MYYNTIHINTA (17.9.2026): pankki on FPL:n oma luku ja lahtijasta
saa myyntihinnan, ei nykyhintaa.

🔴 MITATTU 12.9 JA 17.9 (entry 116920). Ketjun ja reseedin pankki oli
`budget*10 - sum(nykyhinnat)`: GW4-rivi value 1002, bank 8; nykyhinnat 12.9
1000 -> "pankki" 2, 17.9 996 -> "pankki" 6. FPL:n bank oli koko ajan 8.
Identiteetti `value - nykyhinnat = bank` pitaa VAIN deadline-hetkella ja vain
jos kaikki 15 myydaan. Yhdella siirrolla moottori sai `2 + nykyhinta(out)`
kun totuus on `8 + myyntihinta(out)` - ja myyntihinta on nykyhintaa pienempi
aina kun hinta on noussut (FPL: puolet voitosta alaspain pyoristettyna).
Mitattu 17.9: De Cuyper 4.6 -> 4.9 myy 4.7, Tzolakis 4.5 -> 4.6 myy 4.5,
Mendy 4.0 -> 4.1 myy 4.0.

Mika ei ole julkista: `entry/{id}/event/{gw}/picks/` -> `picks[]` kantaa vain
element/element_type/is_captain/is_vice_captain/multiplier/position (mitattu
17.9). Myyntihinta on siis PAATELMA FPL:n omista luvuista: ostohinta
siirtolistalta (`element_in_cost`) tai kauden alkuhinta bootstrapista
(`now_cost - cost_change_start`), ja saanto.

Kolme mekanismia (CLAUDE.md 6a):
  (1) yksi lukija: `fpl_entry_history.entry_state` (pankki + myyntihinnat)
      ja `fpl_transfers.sell_price` (lahtijan hinta moottorissa); puuttuva
      lahde on virhe, ei oletus.
  (2) freezen `_constrained_from_prev` VAATII `meta.bank_tenths` ja rivien
      `selling_price`n - vanhaa kaavaa ei ole olemassa.
  (3) lahdeportti: kutsupaikat lukevat uutta lukijaa eivatka ohita sita.

Hermeettinen: synteettiset dictit FPL:n muodossa, ei verkkoa.
"""
from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

import pytest

from src.models import fpl_entry_history as hist
from src.models import fpl_transfers as tr

ROOT = Path(__file__).resolve().parents[1]


def _load_freeze():
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fikstuuri: entry 116920 GW4 sellaisena kuin FPL sen julkaisee (17.9.2026)
# ---------------------------------------------------------------------------
#: id -> (web_name, now_cost, cost_change_start, element_type, team)
_BOOT_116920 = {
    4: ("Gabriel", 80, 0, 2, 1), 10: ("White", 55, 0, 2, 1),
    51: ("Hemmings", 45, 0, 3, 2), 68: ("Tavernier", 61, 1, 3, 3),
    115: ("De Cuyper", 49, 4, 2, 5), 171: ("Dovin", 40, 0, 1, 7),
    569: ("Gonzalo", 60, 0, 4, 10), 290: ("Slater", 45, 0, 3, 11),
    572: ("Tzolakis", 46, 1, 1, 11), 586: ("Mendy", 41, 1, 2, 11),
    346: ("Calvert-Lewin", 60, 0, 4, 13), 388: ("Guehi", 60, 0, 2, 15),
    411: ("Haaland", 155, 0, 4, 15), 426: ("B.Fernandes", 120, 0, 3, 16),
    427: ("Mbeumo", 79, -1, 3, 16),
}
#: (element_in, element_in_cost, event) - wildcard GW2, 11 siirtoa
_TRANSFERS_116920 = [
    (569, 60, 2), (51, 45, 2), (290, 45, 2), (427, 80, 2), (4, 80, 2),
    (586, 40, 2), (171, 40, 2), (572, 45, 2), (10, 55, 2), (115, 46, 2),
    (388, 60, 2),
]
_PICKS_116920 = list(_BOOT_116920)


def _bootstrap(rows=None):
    rows = rows or _BOOT_116920
    return {"elements": [
        {"id": i, "web_name": n, "now_cost": nc, "cost_change_start": ccs,
         "element_type": et, "team": t, "status": "a"}
        for i, (n, nc, ccs, et, t) in rows.items()]}


def _transfers(rows=None, freehit_time=None):
    rows = rows if rows is not None else _TRANSFERS_116920
    return [{"element_in": i, "element_in_cost": c, "element_out": 0,
             "element_out_cost": 0, "event": ev, "entry": 116920,
             "time": f"2026-08-28T17:18:{k:02d}Z"}
            for k, (i, c, ev) in enumerate(rows)]


def _history(bank=8, value=1002, gw=4, chips=None):
    return {"current": [{"event": g, "event_transfers": 0,
                         "event_transfers_cost": 0, "bank": bank,
                         "value": value} for g in range(1, gw + 1)],
            "chips": chips if chips is not None else [
                {"name": "wildcard", "event": 2}, {"name": "3xc", "event": 3}]}


# ---------------------------------------------------------------------------
# 1. Myyntihinnan saanto ja lukija
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("osto,nyt,myynti", [
    (45, 46, 45),    # Tzolakis: +0.1 -> voitto 0.05 -> alaspain 0
    (46, 49, 47),    # De Cuyper: +0.3 -> 0.15 -> 0.1
    (40, 41, 40),    # Mendy
    (80, 79, 79),    # Mbeumo: laskenut -> nykyhinta
    (50, 50, 50),    # ei liiketta
    (44, 50, 47),    # +0.6 -> 0.3
    (60, 61, 60),    # Tavernier (GW1:sta asti, alkuhinta 60)
])
def test_myyntihinta_on_fpln_saanto(osto, nyt, myynti):
    assert hist.selling_price(osto, nyt) == myynti


def test_entry_state_toistaa_mitatun_gw4_rahatilan():
    """Entry 116920 GW4, luvut 17.9: bank 8, value 1002, myyntihintasumma 991,
    nykyhintasumma 996. `value - bank` = 994 oli nykyhintasumma DEADLINELLA;
    17.9 se oli jo 996, joten vanha kaava antoi pankiksi 6 eika 8."""
    tila = hist.entry_state(_history(), 4, _PICKS_116920, _transfers(),
                            _bootstrap())
    assert tila["bank_tenths"] == 8
    assert tila["value_tenths"] == 1002
    assert tila["selling"][115] == 47 and tila["now"][115] == 49
    assert tila["selling"][572] == 45 and tila["now"][572] == 46
    assert tila["selling"][586] == 40 and tila["now"][586] == 41
    assert tila["selling"][427] == 79 and tila["purchase"][427] == 80
    # GW1:sta asti rungossa: ostohinta = now_cost - cost_change_start
    assert tila["purchase"][68] == 60 and tila["selling"][68] == 60
    assert tila["purchase"][411] == 155
    assert tila["selling_value_tenths"] == 991
    assert sum(tila["now"].values()) == 996
    # ...ja vanha kaava olisi antanut vaaran pankin:
    assert tila["value_tenths"] - sum(tila["now"].values()) == 6 != tila["bank_tenths"]
    assert tila["bank_source"] == "fpl_entry_history"


def test_bank_on_kierroksen_rivilta_ei_viimeisimmasta():
    """Pankki luetaan source_gw:n rivilta. Jos historiassa on jo myohempi
    rivi (freeze ajettu deadlinen jalkeen, tai ketju perii gw-2:n), sen
    pankki ei saa vuotaa perittyyn runkoon."""
    h = _history(bank=8, gw=4)
    h["current"].append({"event": 5, "event_transfers": 2,
                         "event_transfers_cost": 0, "bank": 1, "value": 1003})
    tila = hist.entry_state(h, 4, _PICKS_116920, _transfers(), _bootstrap())
    assert tila["bank_tenths"] == 8


def test_puuttuva_lahde_on_virhe_ei_oletus():
    # siirtolista None (ei saatu) != [] (ei siirtoja)
    with pytest.raises(hist.EntryStateError, match="siirtolistaa"):
        hist.entry_state(_history(), 4, _PICKS_116920, None, _bootstrap())
    # historiasta puuttuu kierros
    with pytest.raises(hist.EntryStateError, match="GW4"):
        hist.entry_state(_history(gw=3), 4, _PICKS_116920, _transfers(),
                         _bootstrap())
    # bootstrap ilman cost_change_start: oletus 0 antaisi vaaran ostohinnan
    boot = _bootstrap()
    for e in boot["elements"]:
        if e["id"] == 68:
            del e["cost_change_start"]
    with pytest.raises(hist.EntryStateError, match="68"):
        hist.entry_state(_history(), 4, _PICKS_116920, _transfers(), boot)
    # pelaaja jota ei ole bootstrapissa eika siirtolistalla
    with pytest.raises(hist.EntryStateError, match="999"):
        hist.entry_state(_history(), 4, _PICKS_116920 + [999], _transfers(),
                         _bootstrap())


def test_ostohinta_on_viimeisin_siirto_ennen_kierrosta():
    """Sama pelaaja ostettu kahdesti: viimeisin `element_in_cost` voittaa.
    Myohempi kuin `upto_gw` ei kelpaa (se on tulevan kierroksen siirto)."""
    rows = [(115, 46, 2), (115, 48, 3)]
    boot = _bootstrap({115: _BOOT_116920[115]})
    assert hist.purchase_prices([115], _transfers(rows), boot, upto_gw=3)[115] == 48
    assert hist.purchase_prices([115], _transfers(rows), boot, upto_gw=2)[115] == 46
    # Free hit -kierroksen osto ei jaa voimaan: runko palautuu.
    assert hist.purchase_prices([115], _transfers(rows), boot, upto_gw=3,
                                freehit_gws=[3])[115] == 46


# ---------------------------------------------------------------------------
# 2. Moottori: lahtijasta saa myyntihinnan
# ---------------------------------------------------------------------------
def _p(pid, pos, price, xp, club=None, **extra):
    row = {"id": pid, "web_name": f"P{pid}", "team_short": "T", "element_type": pos,
           "club": club if club is not None else pid, "price": price,
           "owned_pct": 1.0, "xp_per_gw": xp, "xp_horizon_total": xp,
           "status": "a", "chance_next": 100,
           "gameweeks": [{"gw": 2, "opponents": [], "xp": xp}]}
    row.update(extra)
    return row


def _legal_squad(price=50, selling=None, xp=5.0):
    """2 GK, 5 DEF, 5 MID, 3 FWD, eri seurat. `selling` != price mallintaa
    nousseen hinnan: FPL maksaa vain osan voitosta."""
    squad, pid = [], 1
    for pos, n in ((1, 2), (2, 5), (3, 5), (4, 3)):
        for _ in range(n):
            extra = {} if selling is None else {"selling_price": selling}
            squad.append(_p(pid, pos, price, xp, **extra))
            pid += 1
    return squad


def test_sell_price_lukee_myyntihinnan_tai_nykyhinnan():
    assert tr.sell_price({"price": 50, "selling_price": 47}) == 47
    assert tr.sell_price({"price": 50}) == 50, "tulokas: myynti = ostohinta = nykyhinta"
    assert tr.sell_price({"price": 50, "selling_price": None}) == 50
    assert tr.sell_price({"price": 50, "selling_price": True}) == 50, "bool ei ole hinta"


def test_yksittainen_siirto_ei_saa_nykyhintaa_lahtijasta():
    """Pankki 0.2m, lahtijat nykyhinta 5.0 / myynti 4.7. Tulokas 5.2:
    vanha aritmetiikka (2 + 50 = 52) ostaisi, FPL (2 + 47 = 49) ei."""
    squad = _legal_squad(selling=47)
    pool = squad + [_p(90, 3, 52, 9.0)]
    moves = tr.single_moves(squad, pool, 2, [2], top_k=5)
    assert all(m["in"]["id"] != 90 for m in moves), \
        "moottori luuli saavansa lahtijasta nykyhinnan"
    # Erotteleva kontrolli 1: sama runko ilman hintaliiketta -> mahtuu.
    kontrolli = tr.single_moves(_legal_squad(), pool, 2, [2], top_k=5)
    assert any(m["in"]["id"] == 90 for m in kontrolli)
    # Erotteleva kontrolli 2: tulokas 4.9 mahtuu myyntihinnallakin.
    pool2 = squad + [_p(90, 3, 49, 9.0)]
    assert any(m["in"]["id"] == 90
               for m in tr.single_moves(squad, pool2, 2, [2], top_k=5))


def test_plan_gw_pankki_muuttuu_myyntihinnalla():
    """Pankki 0.5 + myynti 4.7 - osto 5.0 = 0.2. Vanha: 0.5 + 5.0 - 5.0 = 0.5."""
    squad = _legal_squad(selling=47)
    pool = squad + [_p(90, 3, 50, 9.0)]
    step = tr.plan_gw(squad, pool, 5, [2], 1)
    assert [m["in"]["id"] for m in step["moves"]] == [90]
    assert step["moves"][0]["selling_price_out"] == 47
    assert step["bank_tenths"] == 2, "pankki laskettiin nykyhinnalla"


def test_pari_ei_saa_nykyhintaa_lahtijoista():
    """Sama asetelma kuin `test_pair_search_finds_money_freeing_combo`, mutta
    lahtijoiden myyntihinta on 4.7: parin tulokkaat 5.2 + 4.5 = 9.7 ei mahdu
    0 + 4.7 + 4.7 = 9.4:aan. Vanha aritmetiikka (0 + 5.0 + 5.0 = 10.0) loysi
    parin."""
    squad = _legal_squad(selling=47)
    x = _p(90, 2, 52, 12.0)
    y = _p(91, 3, 45, 5.3)
    step = tr.plan_gw(squad, squad + [x, y], 0, [2], 2)
    assert step["moves"] == [], [(m["out"]["id"], m["in"]["id"]) for m in step["moves"]]
    # Erotteleva kontrolli: ilman hintaliiketta pari loytyy.
    kontrolli = tr.plan_gw(_legal_squad(), _legal_squad() + [x, y], 0, [2], 2)
    assert {m["in"]["id"] for m in kontrolli["moves"]} == {90, 91}


# ---------------------------------------------------------------------------
# 3. Freeze: pankki metasta, myyntihinta riveilta, ei kaavaa
# ---------------------------------------------------------------------------
def _prev(squad, meta, selling="keep"):
    rivit = []
    for p in squad:
        r = {"id": p["id"], "web_name": p["web_name"], "pos": p["element_type"],
             "price": p["price"], "club": p["club"]}
        if selling == "keep" and "selling_price" in p:
            r["selling_price"] = p["selling_price"]
        rivit.append(r)
    return {"meta": dict(meta), "xi": rivit[:11], "bench": rivit[11:]}


def test_constrained_lukee_pankin_fpln_kentasta_ei_budjetista():
    """`meta.budget` 100.0 on mukana HOUKUTTIMENA: vanha kaava antaisi
    1000 - 750 = 250 ja ostaisi 5.6:n tulokkaan. FPL:n pankki 0.8 + myynti
    4.7 = 5.5 ei riita."""
    m = _load_freeze()
    squad = _legal_squad(selling=47)
    prev = _prev(squad, {"budget": 100.0, "bank_tenths": 8})
    pool = squad + [_p(90, 3, 56, 9.0)]
    out = m._constrained_from_prev(prev, pool, 2, ft=1)
    assert out["transfers"] == [], "pankki tuli budjetista, ei FPL:n kentasta"
    assert out["bank_before"] == 8 and out["bank"] == 8
    # Kontrolli: 5.5 mahtuu, ja pankin muutos on tarkistettavissa rivilta.
    pool = squad + [_p(90, 3, 55, 9.0)]
    out = m._constrained_from_prev(prev, pool, 2, ft=1)
    assert [t["in"] for t in out["transfers"]] == [90]
    assert out["transfers"][0]["out_selling_price"] == 47
    assert out["transfers"][0]["in_price"] == 55
    assert out["bank_before"] == 8 and out["bank"] == 8 + 47 - 55 == 0


def test_constrained_kieltaytyy_ilman_fpln_pankkia():
    """Pelkka `budget` ei riita: vanhaa kaavaa ei saa ajaa hiljaa."""
    m = _load_freeze()
    squad = _legal_squad(selling=47)
    pool = squad + [_p(90, 3, 50, 9.0)]
    for meta in ({"budget": 100.0}, {"bank_tenths": True},
                 {"bank_tenths": -1}, {"bank_tenths": "8"}):
        with pytest.raises(m.FreezeInputError, match="bank_tenths"):
            m._constrained_from_prev(_prev(squad, meta), pool, 2, ft=1)


def test_constrained_kieltaytyy_ilman_myyntihintaa():
    """Yksikin rivi ilman `selling_price` -> ei lasketa nykyhinnalla."""
    m = _load_freeze()
    squad = _legal_squad(selling=47)
    prev = _prev(squad, {"bank_tenths": 8})
    del prev["bench"][-1]["selling_price"]
    with pytest.raises(m.FreezeInputError, match="selling_price"):
        m._constrained_from_prev(prev, squad, 2, ft=1)


def test_myyntihinta_ei_vuoda_pooliin():
    """Rungon rivin `selling_price` liitetaan kopioon: pooli on ostettavien
    lista ja tulokkaan myyntihinta on hanen ostohintansa."""
    m = _load_freeze()
    squad = _legal_squad()
    prev = _prev(squad, {"bank_tenths": 0})
    for r in prev["xi"] + prev["bench"]:
        r["selling_price"] = 47
    m._constrained_from_prev(prev, squad, 2, ft=1)
    assert all("selling_price" not in p for p in squad)


def test_reseed_polku_kirjoittaa_myyntihinnat_ja_moottori_lukee_ne():
    """Huomisen GW5-polku: `entry_seed` -> `attach_entry_state` ->
    `_constrained_from_prev`. Fikstuuri on entry 116920:n mitattu tila.
    Vanha aritmetiikka: bank 1002 - 996 = 6. FPL: 8."""
    m = _load_freeze()
    ids = _PICKS_116920
    pool = [_p(i, et, nc, 5.0, club=t)
            for i, (n, nc, ccs, et, t) in _BOOT_116920.items()]
    siemen, virhe = m.entry_seed(
        4, pool, _bootstrap(),
        hae=lambda e, gw: [{"element": i} for i in ids],
        hae_historia=lambda e: (_history(), None),
        hae_siirrot=lambda e: (_transfers(), None))
    assert virhe is None, virhe
    meta = siemen["meta"]
    assert meta["bank_tenths"] == 8 and meta["budget"] == 100.2
    assert meta["selling_value_tenths"] == 991 and meta["value_tenths"] == 1002
    by_id = {p["id"]: p for p in siemen["xi"] + siemen["bench"]}
    assert by_id[115]["selling_price"] == 47
    assert by_id[572]["selling_price"] == 45
    # Moottori, maalivahtipaikka (vain Tzolakis 4.6/myy 4.5 ja Dovin 4.0):
    # pankki 0.8 + myynti 4.5 = 5.3. Tulokas GK 5.4 mahtuu VAIN nykyhinnalla
    # (0.8 + 4.6 = 5.4) -> ei saa ostaa.
    pool2 = pool + [_p(900, 1, 54, 30.0, club=18)]
    out = m._constrained_from_prev(siemen, pool2, 5, ft=1, bootstrap=_bootstrap())
    assert out is not None
    assert all(t["in"] != 900 for t in out["transfers"]), \
        "moottori sai lahtijasta nykyhinnan"
    assert out["bank_before"] == 8
    # GK 5.3 mahtuu FPL:n pankilla (0.8 + 4.5 = 5.3), muttei vanhalla
    # kaavalla (1002 - 996 = 0.6 -> 0.6 + 4.6 = 5.2) -> pitaa ostaa.
    pool3 = pool + [_p(900, 1, 53, 30.0, club=18)]
    out = m._constrained_from_prev(siemen, pool3, 5, ft=1, bootstrap=_bootstrap())
    assert [(t["out"], t["in"]) for t in out["transfers"]] == [(572, 900)]
    assert out["transfers"][0]["out_selling_price"] == 45
    assert out["bank"] == 8 + 45 - 53 == 0


# ---------------------------------------------------------------------------
# 4. Lahdeportti: kutsupaikat lukevat uutta lukijaa eivatka ohita sita
# ---------------------------------------------------------------------------
#: Vanha muoto: pankkiin lisataan lahtijan `["price"]` suoraan.
_VANHA_BUDJETTI = re.compile(r'bank\w*\s*\+\s*\w+\["price"\]')


def test_moottorin_budjettiehdot_lukevat_sell_pricea():
    """HUOM: tama on LAHDEPORTTI eika mittaus. Mitattu 18.9 ettei se yksin
    riita: `best_pair`in jarjestysrivin voi kirjoittaa ekvivalenttiin muotoon
    (`(i1["price"] - o1["price"]) > (i2["price"] - o2["price"])`) joka
    ohittaa jokaisen merkkijonon alla ja palauttaa vian. Kayttoksellinen
    portti on `tests/test_transfer_bank_walk.py`.
    """
    for fn, vahintaan in ((tr.single_moves, 1), (tr.best_pair, 4)):
        src = inspect.getsource(fn)
        assert src.count("sell_price(") >= vahintaan, fn.__name__
        assert not _VANHA_BUDJETTI.search(src), \
            f"{fn.__name__}: pankki + nykyhinta on vanha aritmetiikka"
    pair_src = inspect.getsource(tr.best_pair)
    assert 'o1["price"] + o2["price"]' not in pair_src
    assert '(o1["price"] - i1["price"])' not in pair_src
    # 18.9: plan_gw ei laske pankkia itse — saldo muuttuu VAIN `bank_walk`issa,
    # joka on sama lukija joka kieltaa negatiivisen valisaldon.
    plan_src = inspect.getsource(tr.plan_gw)
    assert 'm["out"]["price"]' not in plan_src
    assert "bank_walk(" in plan_src
    assert not _VANHA_BUDJETTI.search(plan_src)
    assert inspect.getsource(tr.bank_walk).count("sell_price(") >= 1


def test_freeze_ei_laske_pankkia_budjetista():
    m = _load_freeze()
    src = inspect.getsource(m._constrained_from_prev)
    body = src.split('"""', 2)[2]          # docstring pois
    assert "_bank_tenths(prev)" in body
    assert "budget" not in body, "budjettia ei saa lukea perityn rungon metasta"
    assert not re.search(r"\*\s*10\b", body), "budjetti * 10 on vanha kaava"
    assert 'p.get("price")' not in body
    assert "_with_selling_price(" in body
    assert not hasattr(m, "budget_from_history")
    assert list(inspect.signature(m._entry_history).parameters) == ["entry"]


def test_freeze_reseed_ja_ketju_kulkevat_saman_lukijan_kautta():
    m = _load_freeze()
    seed_src = inspect.getsource(m.entry_seed)
    assert "entry_state_for(" in seed_src and "attach_entry_state(" in seed_src
    lahde = Path(m.__file__).read_text(encoding="utf-8")
    i = lahde.index("edellinen = _prev_freeze(gw)")
    j = lahde.index("siirtotiedot = None", i)
    ketju = lahde[i:j]
    assert "entry_state_for(" in ketju and "attach_entry_state(" in ketju
    assert "budget_from_history" not in lahde
    # Ainoa kirjoittaja kentille on attach_entry_state.
    assert lahde.count('["bank_tenths"] =') == 1
    assert lahde.count('"selling_price"] =') == 1


def test_freezen_rivi_kantaa_myyntihinnan():
    """Jaadytetty rivi kirjoittaa `selling_price`n, jotta `bank_after =
    bank_before + sum(out_selling - in_price)` on tarkistettavissa
    artefaktista eika vain ajon lokista."""
    m = _load_freeze()
    rivi = m.slim({"id": 1, "price": 50, "selling_price": 47,
                   "gameweeks": [{"gw": 2, "xp": 1.0}]}, 2,
                   element={"status": "a"})
    assert rivi["selling_price"] == 47 and rivi["price"] == 50
    tulokas = m.slim({"id": 2, "price": 50, "gameweeks": []}, 2,
                     element={"status": "a"})
    assert tulokas["selling_price"] == 50
