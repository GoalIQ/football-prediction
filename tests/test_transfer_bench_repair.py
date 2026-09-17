"""Kuollut paikka: pelaamaton penkkilainen ei jaa runkoon mittarin sokeuden takia.

🔴 MITATTU 12.9 ja uudelleen 17.9 (SIIRTOMOOTTORI-EI-MYY-PENKIN-PELAAMATONTA)
entry 116920:n GW4-rungolla, oikealla artefaktilla (data/fpl_xp_projections.json
17.9 02:32Z, ikkuna GW5-GW10, budjetti 100.2 FPL:n historiasta, pankki 0.6):

    Dovin (171, status u, lainalla Leyton Orientissa) penkilla, korvaus
    parhaalla saatavilla olevalla vahdilla (Leno 4.5) -> xi_value-hyoty 0.0000.
    plan_gw(ft=1) max_moves 1 / 2 / 5: Dovin jaa JOKA KERTA.

Korjausrima 0.01 oli olemassa ja matala, mutta `single_moves` pudotti
kandidaatin rivilla `gain_w <= 0` ennen kuin rimaa edes luettiin, ja top_k-
karsinta olisi pudottanut nollan joka tapauksessa. Rima ei ollut vika;
MITTARI EI NAHNYT PENKKIA.

Korjaus CLAUDE.md 6a:n kolmella mekanismilla:
  (1) YKSI LUKIJA `unplayable_members` paattaa onko rungossa kuollut paikka
      (FPL: ei voi pelata JA malli: 0 xP koko ikkunalle).
  (2) `plan_gw`:n on PAKKO kutsua sita: lahdeportti alla lukee lahdetiedoston
      AST:na, ja siirtoja tuottava funktio joka ohittaa lukijan tarvitsee
      POIKKEUSLISTAN rivin perusteluineen. Vanhentunut poikkeus kaataa testin.
  (3) Invariantti mitataan SYNTEETTISILLA VAIHEILLA: ft 1..5, jokainen positio,
      penkki ja XI, entry- ja draft-moodi — ei nykyhetken artefaktilla.

Jokaiselle ehdolle NEGATIIVINEN KONTROLLI: pelaava penkkilainen (ei myyda),
d-status projektiolla (ei myyda nollahyodylla, ei parinakaan), ft 0 (ei hittia
kuolleeseen paikkaan), ei korvaajaa budjetilla (jaa nakyviin, ei hiljaa).

Hermeettinen: synteettinen pooli, ei verkkoa eika artefaktia. Fikstuurit ovat
samat kuin churn-vahdilla (fix/siirtosuunnitelma-churn 12.9), jotta "ei churnia"
mitataan samalla rungolla jolla se on aiemmin todistettu.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.models import fpl_transfers as e
from tests.test_transfer_churn_guard import GWS, base_squad, mk

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "models" / "fpl_transfers.py"


def dead_gk(pid: int = 2, price: int = 40, **extra) -> dict:
    """Dovinin muotoinen rivi: ei projektiota, status u, 0 xP joka kierros."""
    row = mk(pid, 1, 2, price, 0.0, status="u", chance_next=0,
             no_projection=True, no_projection_reason="unavailable")
    row.update(extra)
    return row


def squad_with_dead_bench_gk() -> list[dict]:
    """base_squad, mutta kakkosvahti (id 2) on kuollut paikka."""
    return [p for p in base_squad() if p["id"] != 2] + [dead_gk()]


def bench_gk(xp: float = 1.0) -> dict:
    """Korvaaja joka EI paase XI:hin (ykkosvahti 3.0/GW) -> XI-hyoty tasan 0."""
    return mk(90, 1, 20, 40, xp)


def _ids(step: dict) -> list[tuple[int, int]]:
    return [(m["out"]["id"], m["in"]["id"]) for m in step["moves"]]


# ---------------------------------------------------------------------------
# 1. Se tapaus: penkin pelaamaton, XI-hyoty 0 -> vanha koodi jatti, uusi myy
# ---------------------------------------------------------------------------

def test_kuollut_penkkipaikka_myydaan_vaikka_xi_hyoty_on_nolla():
    squad = squad_with_dead_bench_gk()
    dead = next(p for p in squad if p["id"] == 2)
    repl = bench_gk()
    # KONTROLLI: tama ON se tapaus. Jos XI-hyoty ei olisi nolla, vanha koodi
    # olisi myynyt hanet korjausrimalla ja testi mittaisi vaaraa asiaa.
    assert e.xi_value(e._apply(squad, [dead], [repl]), GWS) - e.xi_value(squad, GWS) == 0.0
    assert e.unplayable_members(squad, GWS) == [dead]

    step = e.plan_gw(squad, [repl], 0, GWS, ft=1)
    assert _ids(step) == [(2, 90)], step["moves"]
    m = step["moves"][0]
    assert m["gain"] == 0.0 and m["gain_weighted"] == 0.0, "nolla nayteaan nollana"
    assert m["hit"] == 0.0 and m["pair"] is False
    assert m["bar"]["reason"] == "dead_slot"
    assert m["repair"] is True
    assert m["repair_reason"] == "no_projection:unavailable"
    assert e.unplayable_members(step["squad"], GWS) == []
    assert step["ft_left"] == 0, "siivous kaytti vapaan siirron, ei hittia"
    assert step["hits"] == 0


def test_siivous_ei_riipu_max_moves_arvosta():
    """12.9 mitattu: max_moves 1/2/5 antoi saman tuloksen (Dovin jaa).
    Nyt saman tuloksen on oltava 'Dovin myyty' jokaisella arvolla."""
    squad = squad_with_dead_bench_gk()
    for mm in (1, 2, 5):
        step = e.plan_gw(squad, [bench_gk()], 0, GWS, ft=1, max_moves=mm)
        assert _ids(step) == [(2, 90)], (mm, step["moves"])


# ---------------------------------------------------------------------------
# 2. NEGATIIVISET KONTROLLIT: mita siivous EI saa tehda
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ft", [1, 2, 3, 4, 5])
def test_NEG_pelaava_penkkilainen_ei_myyda_turhaan(ft):
    """Pelaava kakkosvahti (status a, 1.0/GW) + parempi penkkivahti tarjolla
    (2.0/GW, XI-hyoty 0). Ei siirtoa millaan ft:lla — myoskaan ft 5:lla, jonka
    rima on 0.01: penkin optimointi ei ole XI-parannus. Tama on churn-vahdin
    (12.9) sama periaate: penkkivahdin vaihto ei tuota pisteita."""
    squad = base_squad()
    assert e.unplayable_members(squad, GWS) == [], "lukija: ei kuollutta paikkaa"
    step = e.plan_gw(squad, [bench_gk(2.0)], 0, GWS, ft=ft)
    assert step["moves"] == [], (ft, step["moves"])
    assert step["ft_left"] == ft, "siirto rullaa, sita ei polteta penkkiin"


def test_NEG_d_status_projektiolla_ei_ole_kuollut_paikka():
    """White-tapaus 17.9: status d, 75 %, xP > 0. `needs_repair` on True
    (korjausrima XI-parannukselle, Villen GO 3.9), mutta han EI ole kuollut
    paikka: hanta ei siivota pois nollahyodylla."""
    squad = [p for p in base_squad() if p["id"] != 2]
    doubtful = mk(2, 1, 2, 40, 1.0, status="d", chance_next=75)
    squad.append(doubtful)
    assert e.needs_repair(doubtful) is True
    assert e.is_unplayable(doubtful, GWS) is False
    assert e.unplayable_members(squad, GWS) == []
    for ft in (1, 2, 5):
        assert e.plan_gw(squad, [bench_gk(2.0)], 0, GWS, ft=ft)["moves"] == []


def test_NEG_d_status_ei_myyda_parina_nollahyodylla():
    """🔴 Oman ensimmaisen version vika. Kokeilin BAR_REPAIR = 0.0, ja se
    vakio on myos parihaun lattiassa (`_bs + pari_min`): pari 'aito
    MID-siirto + d-status-penkkivahdin nollahyotyinen vaihto' TASASI
    yksittaisen siirron ja voitti sen -> moottori olisi polttanut toisen
    vapaan siirron pelaavaan penkkilaiseen. Kuollut paikka sai oman riman
    (BAR_DEAD_SLOT) juuri siksi. Tama testi pitaa BAR_REPAIRin nollan
    ylapuolella toiminnallisesti, ei vakiota lukemalla."""
    squad = [p for p in base_squad() if p["id"] != 2]
    squad.append(mk(2, 1, 2, 40, 1.0, status="d", chance_next=75))
    mid_upgrade = mk(91, 3, 21, 60, 5.0)      # +1.0/GW = +2.0 lahi-ikkunassa
    step = e.plan_gw(squad, [mid_upgrade, bench_gk(2.0)], 0, GWS, ft=2)
    assert [i for _, i in _ids(step)] == [91], step["moves"]
    assert not any(o == 2 for o, _ in _ids(step)), "d-status-vahti myytiin parina"
    assert step["ft_left"] == 1, "toinen siirto rullaa"


def test_NEG_kuolleeseen_paikkaan_ei_makseta_hittia():
    squad = squad_with_dead_bench_gk()
    step = e.plan_gw(squad, [bench_gk()], 0, GWS, ft=0, max_moves=2)
    assert step["moves"] == [] and step["hits"] == 0
    # ...ja paikka jaa NAKYVIIN lukijalle, ei hiljaa.
    assert [p["id"] for p in e.unplayable_members(step["squad"], GWS)] == [2]


def test_ei_korvaajaa_budjetilla_jaa_nakyviin_eika_jumita():
    squad = squad_with_dead_bench_gk()            # pankki 0, lahtija 4.0
    liian_kallis = mk(90, 1, 20, 45, 1.0)          # 4.5 ei mahdu
    step = e.plan_gw(squad, [liian_kallis], 0, GWS, ft=2, max_moves=2)
    assert step["moves"] == []
    assert [p["id"] for p in e.unplayable_members(step["squad"], GWS)] == [2]
    assert e.repair_moves(squad, [liian_kallis], 0, GWS) == []


# ---------------------------------------------------------------------------
# 3. Jarjestys: XI-pisteet ensin, siivous sitten
# ---------------------------------------------------------------------------

def test_xi_parannus_voittaa_siivouksen_yhdella_siirrolla():
    """ft 1: vapaa siirto menee siirtoon joka tuottaa pisteita; kuollut paikka
    jaa ja lukija KERTOO sen. ft 2: molemmat. Tama on tietoinen jarjestys
    (penkkivahdin vaihto ei tuota pisteita), ja se on kirjattu tahan jotta
    muutos siihen on paatos eika vahinko."""
    squad = squad_with_dead_bench_gk()
    pool = [bench_gk(), mk(91, 3, 21, 60, 5.0)]   # MID +1.0/GW
    yksi = e.plan_gw(squad, pool, 0, GWS, ft=1)
    assert [i for _, i in _ids(yksi)] == [91], yksi["moves"]
    assert [p["id"] for p in e.unplayable_members(yksi["squad"], GWS)] == [2]
    kaksi = e.plan_gw(squad, pool, 0, GWS, ft=2)
    assert [i for _, i in _ids(kaksi)] == [91, 90], kaksi["moves"]
    assert e.unplayable_members(kaksi["squad"], GWS) == []
    assert kaksi["hits"] == 0


def test_jaanyt_kuollut_paikka_nakyy_paluuarvossa_eika_hiljaa():
    """MITATTU 17.9 OIKEALLA ARTEFAKTILLA (GW5, entry 116920:n GW4-runko):
    freeze-reitin ainoa vapaa siirto menee White->Thomas (+5.18) ja hitti
    De Cuyper->Calafiori; Dovin (171) jaa penkille OIKEIN (nollahyoty ei
    voita +5.18:aa eika kuolleeseen paikkaan makseta hittia). Mutta ilman
    tata kenttaa jaaminen olisi nakymaton: sama vika "hiljaa" eri muodossa.
    Lukijan vastaus lopulliselle rungolle on paluuarvossa AINA, myos tyhjana."""
    squad = squad_with_dead_bench_gk()
    pool = [bench_gk(), mk(91, 3, 21, 60, 5.0)]   # MID +1.0/GW voittaa siivouksen
    yksi = e.plan_gw(squad, pool, 0, GWS, ft=1)
    assert [i for _, i in _ids(yksi)] == [91]
    assert yksi["unplayable_left"] == [2], "jaanyt kuollut paikka on kerrottava"
    kaksi = e.plan_gw(squad, pool, 0, GWS, ft=2)
    assert yksi["ft_left"] == 0 and kaksi["unplayable_left"] == []
    # ft 0: ei hittia, paikka jaa ja se sanotaan.
    assert e.plan_gw(squad, [bench_gk()], 0, GWS, ft=0)["unplayable_left"] == [2]
    # Terve runko: tyhja lista, ei puuttuva avain (klientti ei paattele).
    assert e.plan_gw(base_squad(), [bench_gk(2.0)], 0, GWS, ft=1)["unplayable_left"] == []


# ---------------------------------------------------------------------------
# 4. MEKANISMI 3: invariantti joka vaiheessa, ei nykyhetkessa
# ---------------------------------------------------------------------------

_DEAD_BY_POS = {1: 2, 2: 14, 3: 24, 4: 32}   # base_squadin jasen per positio
_PRICE_BY_POS = {1: 40, 2: 45, 3: 60, 4: 70}
#: Korvaajan xP/GW per paikkatyyppi. "penkki": ei ohita ketaan XI:sta -> XI-hyoty
#: tasan 0. "xi_pieni": ohittaa, mutta hyoty jaa ALLE moduulivakion (0.5/GW):
#: GK/DEF/MID +0.3, FWD +0.4 (kuollut FWD pakottaa 3-5-2:een, joten jo 4.5
#: antaisi +0.5). "xi_iso": ylittaa moduulivakion selvasti.
_REPL_XP = {
    "penkki": {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0},
    "xi_pieni": {1: 3.3, 2: 3.3, 3: 4.3, 4: 4.4},
    "xi_iso": {1: 6.0, 2: 6.0, 3: 6.0, 4: 6.0},
}


@pytest.mark.parametrize("ft", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("pos", [1, 2, 3, 4])
@pytest.mark.parametrize("paikka", ["penkki", "xi_pieni", "xi_iso"])
@pytest.mark.parametrize("entry_known", [True, False])
def test_kuollut_paikka_korjataan_jokaisessa_vaiheessa(ft, pos, paikka, entry_known):
    """Ulkoinen tila joka voi vaihtua moottorin alla: ft-pankki (1..5),
    positio, korvaajan taso (penkki / XI pienella hyodylla / XI isolla) ja
    tunnetaanko entry. KAIKISSA 120 tapauksessa: kuollut paikka on poissa,
    lukija palauttaa tyhjan, ja siihen kaytettiin tasan yksi vapaa siirto
    (ei hittia, ei rullausta kuolleen paikan yli). Riman SYY kertoo minka
    vaiheen kautta siirto tuli — se on se osa jota mutaatio ei saa muuttaa
    hiljaa."""
    pid = _DEAD_BY_POS[pos]
    squad = [p for p in base_squad() if p["id"] != pid]
    squad.append(mk(pid, pos, pid, _PRICE_BY_POS[pos], 0.0, status="u",
                    chance_next=0, no_projection=True))
    repl = mk(90, pos, 20, _PRICE_BY_POS[pos], _REPL_XP[paikka][pos])
    assert [p["id"] for p in e.unplayable_members(squad, GWS)] == [pid]
    xi_gain = e.xi_value(e._apply(squad, [squad[-1]], [repl]), GWS) - e.xi_value(squad, GWS)
    if paikka == "penkki":
        assert xi_gain == 0.0, "fikstuuri: penkkikorvaajan XI-hyoty ei ole nolla"
    elif paikka == "xi_pieni":
        assert 0 < xi_gain / len(GWS) < e.DECISION_BAR_XP_PER_GW, xi_gain
    else:
        assert xi_gain / len(GWS) >= e.DECISION_BAR_XP_PER_GW, xi_gain

    step = e.plan_gw(squad, [repl], 0, GWS, ft=ft, entry_known=entry_known)
    assert _ids(step) == [(pid, 90)], (ft, pos, paikka, entry_known, step["moves"])
    assert e.unplayable_members(step["squad"], GWS) == []
    assert step["hits"] == 0 and step["ft_left"] == ft - 1
    assert step["unplayable_left"] == []
    m = step["moves"][0]
    assert m["repair"] is True
    if paikka == "penkki":
        assert m["gain"] == 0.0 and m["bar"]["reason"] == "dead_slot"
    elif entry_known:
        # Vaihe 1 hoitaa XI-tason korjauksen korjausrimalla (0.01, 3.9).
        assert m["gain"] > 0 and m["bar"]["reason"] == "repair"
    elif paikka == "xi_pieni":
        # Draft-moodi: vaihe 1:n rima on moduulivakio (3.9, EI muutettu), joten
        # pieni XI-hyoty ei lapaise sita — vaihe 2 ottaa saman siirron kuolleen
        # paikan rimalla. Ilman vaihetta 2 draft-runko jaisi vajaaksi.
        assert m["gain"] > 0 and m["bar"]["reason"] == "dead_slot"
    else:
        assert m["gain"] > 0 and m["bar"]["reason"] == "default"


# ---------------------------------------------------------------------------
# 5. Lukijan maaritelma ja riman luokka
# ---------------------------------------------------------------------------

def test_is_unplayable_on_needs_repairin_osajoukko():
    variants = [
        mk(2, 1, 2, 40, 0.0, no_projection=True),
        mk(2, 1, 2, 40, 0.0, status="u"),
        mk(2, 1, 2, 40, 0.0, status="i"),
        mk(2, 1, 2, 40, 0.0, status="a", chance_next=0),
        mk(2, 1, 2, 40, 1.0, status="d", chance_next=75),     # White
        mk(2, 1, 2, 40, 0.0, status="a"),                     # 4.0 penkkistrategia
        mk(2, 1, 2, 40, 3.0, status="a"),
    ]
    for p in variants:
        if e.is_unplayable(p, GWS):
            assert e.needs_repair(p), p
    assert e.is_unplayable(variants[0], GWS) is True
    assert e.is_unplayable(variants[4], GWS) is False, "d + projektio ei ole kuollut"
    assert e.is_unplayable(variants[5], GWS) is False, "pelaava 0 xP ei ole vika"
    # gws=None = horisontti (rate-teamin lista): sama vastaus artefaktin summasta.
    assert e.is_unplayable(variants[0], None) is True
    assert e.is_unplayable(variants[6], None) is False


def test_repair_reason_on_rakenteinen_ja_seuraa_needs_repairia():
    assert e.repair_reason({"no_projection": True, "no_projection_reason": "below_min_xp"}) == "no_projection:below_min_xp"
    assert e.repair_reason({"no_projection": True}) == "no_projection:unavailable"
    assert e.repair_reason({"status": "d"}) == "status:d"
    assert e.repair_reason({"status": "a", "chance_next": 0}) == "chance_next:0"
    assert e.repair_reason({"status": "a", "chance_next": 100}) is None
    assert e.repair_reason({}) is None
    # Jokainen move kantaa lipun — myos tavallinen siirto (False), jotta
    # klientti ei paattele sita puuttuvasta kentasta.
    step = e.plan_gw(base_squad(), [mk(91, 3, 21, 60, 9.0)], 0, GWS, ft=1)
    assert step["moves"][0]["repair"] is False and step["moves"][0]["repair_reason"] is None


def test_dead_slot_rima_on_oma_luokkansa():
    assert e.BAR_DEAD_SLOT == 0.0
    assert e.BAR_REPAIR > 0.0, "parihaun lattia: ks. test_NEG_d_status_ei_myyda_parina"
    bar = e.transfer_bar(1, dead_slot=True)
    assert bar["reason"] == "dead_slot" and bar["min_net"] == 0.0 and bar["hit"] is False
    assert e.transfer_bar(0, dead_slot=True)["reason"] == "hit", "hitti on hitti"
    assert e.transfer_bar(1, dead_slot=True, repair=True)["reason"] == "dead_slot"
    assert e.transfer_bar(1, repair=True)["reason"] == "repair"


def test_NEG_draft_moodin_rima_on_yha_moduulivakio_paitsi_kuollut_paikka():
    """3.9:n negatiivinen kontrolli pysyy: ilman entrya ft-portaat ja
    XI-korjaus lukevat moduulivakiota. Vain kuollut paikka on rungon
    ominaisuus ja luetaan ennen entry-ehtoa."""
    for ft in (1, 3, 5):
        bar = e.transfer_bar(ft, entry_known=False, repair=True)
        assert bar["reason"] == "default" and bar["min_net"] == e.MIN_GAIN_PER_TRANSFER
        assert e.transfer_bar(ft, entry_known=False, dead_slot=True)["reason"] == "dead_slot"
    assert e.transfer_bar(0, entry_known=False, dead_slot=True)["reason"] == "hit"


# ---------------------------------------------------------------------------
# 6. MEKANISMI 2: lahdeportti — kutsupaikka lukee lukijaa, poikkeus perustellaan
# ---------------------------------------------------------------------------

def _fns() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _calls(fn: ast.FunctionDef) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


#: Siirtoja tuottavat funktiot jotka saavat OHITTAA lukijan — ja MIKSI.
#: Uusi funktio joka kutsuu `_move`/`single_moves`/`best_pair`/`repair_moves`
#: eika lue lukijaa kaatuu testiin, kunnes se on talla listalla perusteluineen.
#: Poikkeus joka alkaa lukea lukijaa on vanhentunut ja kaataa testin myos.
LUKIJAN_OHITTAVAT: dict[str, str] = {
    "single_moves": ("lista, ei paatos: rate-teamin top-5 ja plan_gw:n vaihe 1 "
                     "(XI-parannus). Kuolleen paikan hoitaa plan_gw:n vaihe 2, "
                     "jotta rate-teamin listaan ei ilmesty +0.00-rivia ilman "
                     "pinnan omaa copya (copy-sync, GO)."),
    "best_pair": ("parihaku plan_gw:n vaiheelle 1. Nollahyotyinen pari ei saa "
                  "tasata yksittaista siirtoa (BAR_REPAIR > 0), joten kuollut "
                  "paikka ei kuulu tahan hakuun."),
    "best_move_summary": ("hold-lauseen luku ja rima. Lause seuraa suunnitelmaa "
                          "(n_moves == 0 -haara), ja suunnitelma lukee plan_gw:ta "
                          "joka lukee lukijaa."),
}

_TUOTTAJAMERKIT = {"_move", "single_moves", "best_pair", "repair_moves"}


def test_plan_gw_kutsuu_korjaushakua_joka_lukee_yhta_lukijaa():
    """KUTSUPAIKKATODISTUS: vaiheen 2 poisto plan_gw:sta kaataa taman
    riippumatta siita mita muut testit sattuvat mittaamaan."""
    fns = _fns()
    assert "repair_moves" in _calls(fns["plan_gw"])
    # ...ja paluuarvo kantaa lukijan vastauksen (`unplayable_left`), joten
    # plan_gw lukee lukijaa myos itse, ei vain repair_movesin kautta.
    assert "unplayable_members" in _calls(fns["plan_gw"])
    assert "unplayable_members" in _calls(fns["repair_moves"])
    assert "is_unplayable" in _calls(fns["unplayable_members"])
    assert {"needs_repair", "window_xp"} <= _calls(fns["is_unplayable"])
    # Vaihe 2 lukee saman rimalukijan ja saman vertailun kuin vaihe 1.
    assert "transfer_bar" in _calls(fns["plan_gw"])


def test_siirtoja_tuottava_funktio_lukee_lukijaa_tai_on_poikkeuslistalla():
    fns = _fns()
    tuottajat = {name for name, fn in fns.items()
                 if (_calls(fn) & _TUOTTAJAMERKIT) or name == "best_pair"}
    tuottajat.discard("repair_moves")            # se ON lukijan kutsuja
    assert "plan_gw" in tuottajat and "single_moves" in tuottajat
    lukee = {"repair_moves", "unplayable_members"}
    for name in sorted(tuottajat):
        if _calls(fns[name]) & lukee:
            assert name not in LUKIJAN_OHITTAVAT, \
                f"{name} lukee jo lukijaa: poikkeus on vanhentunut, poista se"
            continue
        assert name in LUKIJAN_OHITTAVAT, \
            f"{name} tuottaa siirtoja lukematta unplayable_members: lisaa perustelu"
        assert len(LUKIJAN_OHITTAVAT[name].strip()) >= 40, name
    for name in LUKIJAN_OHITTAVAT:
        assert name in fns, f"poikkeus nimeaa funktion jota ei ole: {name}"
