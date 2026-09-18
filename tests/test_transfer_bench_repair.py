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
    assert e.unplayable_members(squad) == [dead]

    step = e.plan_gw(squad, [repl], 0, GWS, ft=1)
    assert _ids(step) == [(2, 90)], step["moves"]
    m = step["moves"][0]
    assert m["gain"] == 0.0 and m["gain_weighted"] == 0.0, "nolla nayteaan nollana"
    assert m["hit"] == 0.0 and m["pair"] is False
    assert m["bar"]["reason"] == "dead_slot"
    assert m["repair"] is True
    # 18.9: syy on TARKISTETTAVUUSJARJESTYKSESSA. Dovinin status "u" on
    # FPL:n ilmaispinnalla; artefaktin oma syy tulee vasta sen jalkeen.
    assert m["repair_reason"] == "status:u"
    assert e.unplayable_members(step["squad"]) == []
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
    assert e.unplayable_members(squad) == [], "lukija: ei kuollutta paikkaa"
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
    assert e.is_unplayable(doubtful) is False
    assert e.unplayable_members(squad) == []
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
    assert [p["id"] for p in e.unplayable_members(step["squad"])] == [2]


def test_NEG_vaihe_2_ei_ole_takaovi_hitille_lahi_ikkunasaannon_ohi():
    """🔴 Mitattu 17.9 ilta ensimmaisesta versiosta: kuollut XI-paikka (FWD
    32, status u, 0 xP), tulijan hyoty 8.0 horisontissa mutta 0.0 lahi-
    ikkunassa. Vaihe 1 hylkasi hitin NEAR_SHARE_FOR_HIT-saannolla (3.9: -4
    maksetaan vain etupainotteisesta hyodysta), ja vaihe 2 hyvaksyi SAMAN
    siirron hitilla, koska hitin rima (MIN_GAIN_FOR_HIT - 4) lukee vain
    horisonttia: `plan_gw ft=0 -> [(32, 90, hit 4.0, 'hit')]`. Kuolleen paikan
    siivous on vapaan siirron paatos; hitti on aina vaiheen 1 paatos."""
    squad = [p for p in base_squad() if p["id"] != 32]
    dead = mk(32, 4, 15, 70, 0.0, status="u", chance_next=0, no_projection=True)
    squad.append(dead)
    repl = mk(90, 4, 20, 70, [0.0, 0.0, 8.0, 8.0, 8.0, 8.0])
    near = e.near_gws(GWS)
    gain = e.xi_value(e._apply(squad, [dead], [repl]), GWS) - e.xi_value(squad, GWS)
    gain_near = (e.xi_value(e._apply(squad, [dead], [repl]), near)
                 - e.xi_value(squad, near))
    # KONTROLLIT: hitin horisonttirima ylittyy, lahi-ikkunan osuus ei -> vaihe 1
    # hylkaa juuri lahi-ikkunasaannolla, ja vaihe 2:n haku LOYTAA siirron.
    # Ilman naita testi voisi olla vihrea siksi ettei siirtoa ole tarjolla.
    assert gain >= e.MIN_GAIN_FOR_HIT and gain_near == 0.0, (gain, gain_near)
    assert e.single_moves(squad, [repl], 0, GWS, top_k=3, near=near,
                          near_min_share=e.NEAR_SHARE_FOR_HIT) == []
    assert [m["in"]["id"] for m in
            e.repair_moves(squad, [repl], 0, GWS, near=near)] == [90]
    step = e.plan_gw(squad, [repl], 0, GWS, ft=0)
    assert step["moves"] == [] and step["hits"] == 0, step["moves"]
    assert step["unplayable_left"] == [32], "paikka jaa ja se sanotaan"
    # ...ja vapaalla siirrolla sama paikka siivotaan (vaihe 2, ei hittia).
    vapaa = e.plan_gw(squad, [repl], 0, GWS, ft=1)
    assert _ids(vapaa) == [(32, 90)] and vapaa["hits"] == 0, vapaa["moves"]
    assert vapaa["moves"][0]["bar"]["reason"] == "dead_slot"


def test_ei_korvaajaa_budjetilla_jaa_nakyviin_eika_jumita():
    squad = squad_with_dead_bench_gk()            # pankki 0, lahtija 4.0
    liian_kallis = mk(90, 1, 20, 45, 1.0)          # 4.5 ei mahdu
    step = e.plan_gw(squad, [liian_kallis], 0, GWS, ft=2, max_moves=2)
    assert step["moves"] == []
    assert [p["id"] for p in e.unplayable_members(step["squad"])] == [2]
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
    assert [p["id"] for p in e.unplayable_members(yksi["squad"])] == [2]
    kaksi = e.plan_gw(squad, pool, 0, GWS, ft=2)
    assert [i for _, i in _ids(kaksi)] == [91, 90], kaksi["moves"]
    assert e.unplayable_members(kaksi["squad"]) == []
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
                    chance_next=0, no_projection=True,
                    no_projection_reason="unavailable"))
    repl = mk(90, pos, 20, _PRICE_BY_POS[pos], _REPL_XP[paikka][pos])
    assert [p["id"] for p in e.unplayable_members(squad)] == [pid]
    xi_gain = e.xi_value(e._apply(squad, [squad[-1]], [repl]), GWS) - e.xi_value(squad, GWS)
    if paikka == "penkki":
        assert xi_gain == 0.0, "fikstuuri: penkkikorvaajan XI-hyoty ei ole nolla"
    elif paikka == "xi_pieni":
        assert 0 < xi_gain / len(GWS) < e.DECISION_BAR_XP_PER_GW, xi_gain
    else:
        assert xi_gain / len(GWS) >= e.DECISION_BAR_XP_PER_GW, xi_gain

    step = e.plan_gw(squad, [repl], 0, GWS, ft=ft, entry_known=entry_known)
    assert _ids(step) == [(pid, 90)], (ft, pos, paikka, entry_known, step["moves"])
    assert e.unplayable_members(step["squad"]) == []
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

def test_is_unplayable_vaatii_myonteisen_todisteen_ja_koko_projektion():
    """Kaksi ehtoa, molemmat ankarampia kuin `needs_repair` (18.9).

    Vanha versio oli `needs_repair(p) and window_xp(p, gws) <= 0.0`, ja se
    vaitti riveilla 323-327 etta pelkka `no_projection`-lippu tekee
    kuolleen paikan. Se vaite oli EPATOSI Lewisin luokalle (alla), ja
    juuri se rivi antoi moottorille luvan myyda pelikelpoinen penkkilainen
    vapaalla siirrolla hyodylla 0.00.
    """
    kuolleet = [
        mk(2, 1, 2, 40, 0.0, status="u"),
        mk(2, 1, 2, 40, 0.0, status="i"),
        mk(2, 1, 2, 40, 0.0, status="a", chance_next=0),
        # Artefakti pudotti hanet SAATAVUUSSYYSTA: syy on rivilla.
        mk(2, 1, 2, 40, 0.0, status="a", no_projection=True,
           no_projection_reason="unavailable"),
    ]
    elavat = [
        mk(2, 1, 2, 40, 1.0, status="d", chance_next=75),      # White
        mk(2, 1, 2, 40, 0.0, status="a"),                      # 4.0 penkkistrategia
        mk(2, 1, 2, 40, 3.0, status="a"),
        # 🔴 LEWIS (395): artefakti pudotti syylla `below_min_xp`, FPL sanoo
        # status "a" ja tyhjan news-kentan. `needs_repair` on True (rima),
        # kuollut paikka EI (lupa myyda).
        mk(2, 2, 2, 44, 0.0, status="a", no_projection=True,
           no_projection_reason="below_min_xp"),
        # Gruev (344): sama syy, status "d" 25 %.
        mk(2, 3, 2, 45, 0.0, status="d", chance_next=25, no_projection=True,
           no_projection_reason="below_min_xp"),
        # 🔴 TUNTEMATON SYY EI OLE TODISTE: tuottaja unohti syyn -> paikka
        # ei kuole. Vaarin muistaminen maksaa korkeintaan siivoamatta
        # jaaneen paikan, ei kayttajan vapaata siirtoa.
        mk(2, 1, 2, 40, 0.0, status="a", no_projection=True),
        # Saatavuussyy MUTTA projektio ei ole nolla (artefakti rakennettu
        # ennen loukkaantumista): korjausrima kylla, siivouslupa ei.
        mk(2, 1, 2, 40, 2.0, status="u"),
        # Nolla VAIN nykyisessa/viimeisessa kierroksessa (blank tai
        # palaamassa): kumpikaan yksittainen kierros ei ole koko projektio.
        mk(2, 1, 2, 40, [0.0, 0.0, 0.0, 0.0, 0.0, 3.0], status="u"),
        mk(2, 1, 2, 40, [3.0, 0.0, 0.0, 0.0, 0.0, 0.0], status="u"),
    ]
    for pl in kuolleet:
        assert e.is_unplayable(pl) is True, pl
        assert e.needs_repair(pl) is True, "kuollut paikka on needs_repairin osajoukko"
    for pl in elavat:
        assert e.is_unplayable(pl) is False, pl
    # ...ja lukija kysyy molemmat kysymykset erikseen, ei yhta.
    lewis = elavat[3]
    assert e.needs_repair(lewis) is True and e.projected_zero(lewis) is True
    assert e.unavailable_by_fpl(lewis) is False, "below_min_xp ei ole saatavuuslippu"
    # `projected_zero` lukee MOLEMMAT artefaktin luvut: valmiin
    # horisonttisumman JA per-kierros-rivit. Vanhentunut summa ei saa
    # yksin todistaa nollaa, eika yksittainen nollakierros kumota sita.
    vanhentunut = mk(2, 1, 2, 40, [0.0, 0.0, 0.0, 0.0, 0.0, 4.0], status="u")
    vanhentunut["xp_horizon_total"] = 0.0
    assert e.projected_zero(vanhentunut) is False, "per-kierros-rivit ovat myos lahde"
    assert e.is_unplayable(vanhentunut) is False
    vain_summa = mk(2, 1, 2, 40, 0.0, status="u")
    vain_summa["xp_horizon_total"] = 2.0
    assert e.projected_zero(vain_summa) is False, "summa on myos lahde"


@pytest.mark.parametrize("ft", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("pos", [1, 2, 3, 4])
@pytest.mark.parametrize("syy", ["below_min_xp", None])
@pytest.mark.parametrize("entry_known", [True, False])
def test_NEG_pelikelpoista_penkkilaista_ei_myyda_nollahyodylla(ft, pos, syy, entry_known):
    """🔴 KAANTEISVIKA (18.9, adversariaalinen tarkistus). Lewisin muoto:
    FPL:n bootstrap sanoo status "a", news "", chance_next None, ja artefakti
    pudotti hanet syylla `below_min_xp` (min_xp_total 1.0). Mitattu ennen
    korjausta: `plan_gw(ft=1)` myi hanet, gain 0.00, bar reason "dead_slot",
    pankki 1.6 -> 0.0. Kayttajalle: "myy pelikelpoinen penkkipelaajasi ja
    polta vapaa siirto + koko pankki, +0.00 xP".

    Luokan koko kasvaa kun horisontti lyhenee kauden lopussa (yha useampi
    halpa penkkifilleri putoaa rajan alle), joten tama mitataan jokaisella
    ft-arvolla, jokaisessa positiossa, molemmissa moodeissa ja seka
    artefaktin syylla etta ILMAN syyta (tuottaja unohti)."""
    pid = _DEAD_BY_POS[pos]
    squad = [p for p in base_squad() if p["id"] != pid]
    lewis = mk(pid, pos, pid, _PRICE_BY_POS[pos], 0.0, status="a",
               chance_next=None, news="", no_projection=True,
               no_projection_reason=syy)
    squad.append(lewis)
    # KONTROLLIT: han on `needs_repair` (lavea lippu) ja mallin nolla — eli
    # tasan se luokka jonka vanha `is_unplayable` luki kuolleeksi paikaksi.
    assert e.needs_repair(lewis) is True and e.projected_zero(lewis) is True
    repl = mk(90, pos, 20, _PRICE_BY_POS[pos], 1.0)
    assert e.unplayable_members(squad) == [], "pelikelpoinen ei ole kuollut paikka"
    step = e.plan_gw(squad, [repl], 16, GWS, ft=ft, entry_known=entry_known)
    assert step["moves"] == [], (ft, pos, syy, entry_known, step["moves"])
    assert step["ft_left"] == ft, "vapaa siirto rullaa, sita ei polteta"
    assert step["bank_tenths"] == 16, "pankki jaa koskematta"
    assert step["unplayable_left"] == []
    # ...eika siivoushaku edes tarjoa hanta.
    assert e.repair_moves(squad, [repl], 16, GWS) == []


#: Ikkunat joita `plan_transfers` syottaa: silmukka antaa `gws[idx:]`, joka
#: KUTISTUU viimeista kierrosta kohti (fpl_planner.py: `gws_left = gws[idx:]`).
_IKKUNAT = {"koko": GWS, "kaksi_viimeista": GWS[-2:], "viimeinen": GWS[-1:]}


@pytest.mark.parametrize("ikkuna", sorted(_IKKUNAT))
@pytest.mark.parametrize("ft", [1, 2, 5])
def test_kuollut_paikka_siivotaan_jokaisessa_paatosikkunassa(ikkuna, ft):
    """VAIHEAKSELI 3 (18.9): sama kuollut pelaaja, eri paatosikkuna."""
    gws = _IKKUNAT[ikkuna]
    dead = mk(2, 1, 2, 40, 0.0, status="u", chance_next=0, no_projection=True,
              no_projection_reason="unavailable")
    squad = [p for p in base_squad() if p["id"] != 2] + [dead]
    step = e.plan_gw(squad, [bench_gk()], 0, gws, ft=ft)
    assert _ids(step) == [(2, 90)], (ikkuna, ft, step["moves"])
    assert step["unplayable_left"] == []


@pytest.mark.parametrize("ikkuna", sorted(_IKKUNAT))
@pytest.mark.parametrize("ft", [1, 2, 5])
def test_NEG_blankkaava_pelaaja_ei_ole_kuollut_paikka_missaan_ikkunassa(ikkuna, ft):
    """🔴 VAIHEINVARIANTTI MITATTIIN VAARASTA IKKUNASTA (18.9).

    Pelaaja: status "d", 75 %, xP 4.0/GW viidella kierroksella ja 0.0
    viimeisella, jolla seuralla on BLANK (`opponents: []` on artefaktin oma
    merkinta blankille, build_fpl_xp.py). Horisonttisumma 20.0.

    Mitattu ennen korjausta: `is_unplayable(gws=GWS)` False,
    `is_unplayable(gws=GWS[-2:])` False, `is_unplayable(gws=GWS[-1:])` True
    -> `plan_gw(gws=[8], ft=1)` myi hanet nollan arvoiseen pelaajaan, gain
    0.0, bar "dead_slot", repair_reason "status:d". Altistus tanaan on 0
    (GW5-GW10:n artefaktissa ei ole blankkeja), joten vanha portti olisi
    ollut vihrea siihen asti kun ensimmainen blank tulee.

    120-tapauksen matriisi ei voinut loytaa tata: sen kuolleilla pelaajilla
    xP on 0 JOKA kierroksella, joten ikkunan pituus ei muuta vastausta."""
    gws = _IKKUNAT[ikkuna]
    blank = mk(2, 1, 2, 40, [4.0, 4.0, 4.0, 4.0, 4.0, 0.0],
               status="d", chance_next=75)
    blank["gameweeks"][-1]["opponents"] = []      # artefaktin merkinta blankille
    # KONTROLLIT: ikkunan summa ON nolla mitatussa kierroksessa (muuten testi
    # mittaisi vaaraa asiaa), mutta koko projektio ei ole.
    assert e.window_xp(blank, GWS[-1:]) == 0.0
    assert blank["xp_horizon_total"] == 20.0 and e.projected_zero(blank) is False
    squad = [p for p in base_squad() if p["id"] != 2] + [blank]
    arvoton = mk(90, 1, 20, 40, 0.0)
    assert e.is_unplayable(blank) is False
    assert e.unplayable_members(squad) == []
    step = e.plan_gw(squad, [arvoton], 0, gws, ft=ft)
    assert step["moves"] == [], (ikkuna, ft, step["moves"])
    assert step["unplayable_left"] == []
    assert e.repair_moves(squad, [arvoton], 0, gws) == []


def test_lukijalla_ei_ole_ikkunaparametria():
    """🔴 KUTISTUVAA IKKUNAA EI VOI EDES SYOTTAA (18.9).

    Vian juuri ei ollut vaara arvo vaan se ETTA IKKUNAN SAI ANTAA: kutsuja
    piti kadessaan `gws[idx:]`-viipaletta ja antoi sen hyvassa uskossa.
    Portti ei mittaa arvoa vaan allekirjoitusta — jos ikkunaparametri
    palautetaan, tama kaatuu ennen kuin yhtaakaan kierrosta on ajettu."""
    import inspect
    for fn in (e.is_unplayable, e.unplayable_members, e.projected_zero,
               e.unavailable_by_fpl):
        params = list(inspect.signature(fn).parameters)
        assert len(params) == 1, (fn.__name__, params)
    with pytest.raises(TypeError):
        e.is_unplayable(mk(2, 1, 2, 40, 0.0, status="u"), GWS)
    with pytest.raises(TypeError):
        e.unplayable_members(base_squad(), GWS)


def test_repair_reason_ei_koskaan_vaita_unavailablea_ilman_lahdetta():
    """🔴 PORTTI 16.9 PALASI UUDESSA GENERAATTORISSA (18.9).

    `repair_reason` kovakoodasi puuttuvan syyn sanaksi "unavailable" — sama
    sanamuoto jonka julkaisuportti hylkasi 16.9 ja jonka takia
    `fpl_planner._no_xp_reason` on olemassa. Sen dokumentti nimeaa Lewisin:
    "FPL:n oma bootstrap sanoo status: 'a' ja tyhjan news-kentan. Sanoimme
    siis eri asian kuin lahde." Kentta on suunniteltu pinnalle nayttamiseen,
    joten oletusarvo on lupaus."""
    # 1. Tarkistettavuusjarjestys: ilmaispinnalta luettava syy ensin.
    assert e.repair_reason({"status": "u", "no_projection": True,
                            "no_projection_reason": "unavailable"}) == "status:u"
    assert e.repair_reason({"status": "d", "chance_next": 25}) == "status:d"
    assert e.repair_reason({"status": "a", "chance_next": 0}) == "chance_next:0"
    # 2. Artefaktin oma syy kulkee lapi sellaisenaan.
    assert e.repair_reason({"status": "a", "no_projection": True,
                            "no_projection_reason": "below_min_xp"}) == "no_projection:below_min_xp"
    # 3. TUNTEMATON ON TUNTEMATON, ei "unavailable".
    assert e.repair_reason({"status": "a", "no_projection": True}) == "no_projection:unknown"
    assert e.repair_reason({"no_projection": True}) == "no_projection:unknown"
    assert e.repair_reason({"status": "a", "chance_next": 100}) is None
    assert e.repair_reason({}) is None
    # 4. LAHDEPORTTI: merkkijonoa "unavailable" ei saa esiintya funktion
    #    RUNGOSSA lainkaan (dokumentaatio saa puhua siita). Kovakoodattu
    #    oletus palaisi yhdella muokkauksella (oletusarvo or-lausekkeessa),
    #    ja
    #    kayttaytymisportti yksin ei nayttaisi sita ennen kuin joku
    #    tuottaja unohtaa syyn.
    fn = _fns()["repair_reason"]
    runko = list(fn.body)
    if (runko and isinstance(runko[0], ast.Expr)
            and isinstance(runko[0].value, ast.Constant)):
        runko = runko[1:]                      # docstring pois
    for solmu in runko:
        for n in ast.walk(solmu):
            assert not (isinstance(n, ast.Constant)
                        and n.value == "unavailable"),                 "repair_reason kovakoodaa sanan 'unavailable' (portti 16.9)"
    # 5. Jokainen move kantaa lipun — myos tavallinen siirto (False), jotta
    #    klientti ei paattele sita puuttuvasta kentasta.
    step = e.plan_gw(base_squad(), [mk(91, 3, 21, 60, 9.0)], 0, GWS, ft=1)
    assert step["moves"][0]["repair"] is False and step["moves"][0]["repair_reason"] is None


def test_placeholder_kantaa_artefaktin_syyn_eika_keksi_sita():
    """TUOTTAJAPUOLI: `placeholder_player` on toinen repon kahdesta
    placeholder-rakentajasta (`fpl_rate_team.zero_projection_row` on toinen),
    ja vain jalkimmainen kantoi `excluded_reason`in. Nyt molemmat."""
    boot = {"elements": [{"id": 395, "web_name": "Lewis", "team": 3,
                          "element_type": 2, "now_cost": 44, "status": "a",
                          "news": "", "chance_of_playing_next_round": None}],
            "teams": [{"id": 3, "short_name": "MCI"}]}
    ph = e.placeholder_player(395, boot, {"id": 395, "excluded_reason": "below_min_xp"})
    assert ph["no_projection"] is True
    assert ph["no_projection_reason"] == "below_min_xp"
    assert e.needs_repair(ph) is True, "korjausrima sailyy (3.9/12.9)"
    assert e.unavailable_by_fpl(ph) is False and e.is_unplayable(ph) is False
    assert e.repair_reason(ph) == "no_projection:below_min_xp"
    # Ilman artefaktin rivia: syy on tuntematon, EI "unavailable".
    tyhja = e.placeholder_player(395, boot)
    assert tyhja["no_projection_reason"] is None
    assert e.repair_reason(tyhja) == "no_projection:unknown"
    assert e.is_unplayable(tyhja) is False
    # Saatavuussyy: sama funktio, kuollut paikka.
    dovin = e.placeholder_player(395, dict(boot, elements=[
        dict(boot["elements"][0], status="u", news="On loan")]),
        {"id": 395, "excluded_reason": "unavailable"})
    assert e.is_unplayable(dovin) is True


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


def _calls_in(nodes: list[ast.stmt]) -> set[str]:
    out: set[str] = set()
    for n in nodes:
        out |= _calls(n)
    return out


def _calls(fn: ast.AST) -> set[str]:
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
    assert {"unavailable_by_fpl", "projected_zero"} <= _calls(fns["is_unplayable"])
    # 18.9: kuolleisuus EI saa lukea paatosikkunaa (ks. projected_zero).
    assert "window_xp" not in _calls(fns["is_unplayable"])
    assert "window_xp" not in _calls(fns["projected_zero"])
    assert "needs_repair" not in _calls(fns["is_unplayable"]), \
        "lavea korjauslippu ei ole lupa myyda (ks. unavailable_by_fpl)"
    # Vaihe 2 lukee saman rimalukijan ja saman vertailun kuin vaihe 1.
    assert "transfer_bar" in _calls(fns["plan_gw"])
    # Vaihe 2 on VAPAAN SIIRRON haara: repair_moves-kutsun on oltava if-lohkossa
    # jonka ehto lukee `fts`. 17.9 ilta: ilman ehtoa vaihe 2 maksoi hitin
    # vaiheen 1 lahi-ikkunasaannon ohi (behavioraalinen pari:
    # test_NEG_vaihe_2_ei_ole_takaovi_hitille_lahi_ikkunasaannon_ohi).
    vartijat = [n for n in ast.walk(fns["plan_gw"]) if isinstance(n, ast.If)
                and "repair_moves" in _calls_in(n.body)]
    assert vartijat, "repair_moves-kutsu ei ole ehdollinen"
    for v in vartijat:
        ehto = {n.id for n in ast.walk(v.test) if isinstance(n, ast.Name)}
        assert "fts" in ehto, f"vaihe 2:n ehto ei lue ft-pankkia: {ast.dump(v.test)}"


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


#: Tuotantopolut jotka rakentavat projektiottoman rungon jasenen. Jokaisen on
#: annettava `placeholder_player`ille artefaktin `excluded`-rivi, jotta
#: `no_projection_reason` on artefaktin oma syy eika tuntematon.
#: POIKKEUS vaatii perustelun, ja perustelu vanhenee nakyvasti: jos poikkeus
#: alkaa antaa rivin, testi kaatuu ja poikkeus on poistettava.
PLACEHOLDER_ILMAN_SYYTA: dict[str, str] = {}

#: (tiedosto, funktio) -parit jotka kutsuvat `placeholder_player`ia
#: tuotannossa. Uusi kutsupaikka ei paase tanne vahingossa: testi vaatii
#: etta jokainen LOYDETTY kutsu antaa kolme argumenttia.
_TUOTTAJATIEDOSTOT = ("src/models/fpl_planner.py",
                      "scripts/freeze_model_squad_gw.py")


def test_placeholder_kutsupaikat_antavat_artefaktin_syyn():
    """🔴 KUTSUPAIKKAPORTTI (18.9). `repair_reason` on pinnalle tarkoitettu
    kentta, ja sen totuus syntyy TUOTTAJASSA. Yksikkotesti joka vain
    todistaa etta funktio OSAA kantaa syyn dokumentoi kyvyn jota putki ei
    kayta — tasan se tilanne joka 17.9:n haarassa oli
    (`test_repair_reason_on_rakenteinen_...` oli vihrea samalla kun
    tuotantopolku antoi jokaiselle riville "no_projection:unavailable").

    Tama lukee lahdetiedostot ja vaatii etta jokainen `placeholder_player`-
    kutsu antaa kolmannen argumentin."""
    loydetty = 0
    for suht in _TUOTTAJATIEDOSTOT:
        tiedosto = ROOT / suht
        puu = ast.parse(tiedosto.read_text(encoding="utf-8"))
        for node in ast.walk(puu):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            nimi = (f.id if isinstance(f, ast.Name)
                    else f.attr if isinstance(f, ast.Attribute) else None)
            if nimi != "placeholder_player":
                continue
            loydetty += 1
            avain = f"{suht}:{node.lineno}"
            if avain in PLACEHOLDER_ILMAN_SYYTA:
                assert len(PLACEHOLDER_ILMAN_SYYTA[avain].strip()) >= 40, avain
                assert len(node.args) + len(node.keywords) < 3, \
                    f"{avain} antaa jo syyn: poikkeus on vanhentunut, poista se"
                continue
            assert len(node.args) + len(node.keywords) >= 3, (
                f"{avain}: placeholder_player ilman artefaktin excluded-rivia. "
                f"Syy jaa tuntemattomaksi ja pinta saa 'no_projection:unknown'. "
                f"Anna rivi tai lisaa perusteltu poikkeus "
                f"PLACEHOLDER_ILMAN_SYYTA-listalle.")
    assert loydetty >= 2, f"kutsupaikkoja ei loytynyt ({loydetty}) — portti ei mittaa mitaan"


def test_freeze_ei_keksi_saatavuuslippua_projektiottomalle():
    """🔴 KOLMAS PLACEHOLDER-RAKENTAJA (18.9). `freeze_model_squad_gw.
    _departed_player` ylikirjoitti `chance_next`in nollalla ja
    `minutes_source`n arvolla "left_league". `chance_next == 0` on YKSI
    `unavailable_by_fpl`in kolmesta myonteisesta todisteesta, joten keksitty
    nolla olisi tehnyt Lewisin luokasta kuolleen paikan freeze-polulla ja
    ohittanut koko korjauksen. Kentta ei saa palata."""
    lahde = (ROOT / "scripts" / "freeze_model_squad_gw.py").read_text(encoding="utf-8")
    puu = ast.parse(lahde)
    fn = next(n for n in ast.walk(puu)
              if isinstance(n, ast.FunctionDef) and n.name == "_departed_player")
    keksityt = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and k.value in (
                        "chance_next", "status", "news", "no_projection_reason"):
                    keksityt.add(k.value)
    assert "chance_next" not in keksityt, \
        "_departed_player keksii chance_nextin uudelleen (= saatavuuslippu)"
    assert "status" not in keksityt, "status tulee bootstrapista, ei taalta"
    assert "no_projection_reason" not in keksityt, "syy tulee artefaktista"
