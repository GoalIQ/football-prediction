"""XP-DOUBT-HORISONTTI (23.9.2026): FPL:n d-lippu koskee otsikkokierrosta,
myohemmille kierroksille mitattu palautuminen.

FPL:n `chance_of_playing_next_round` koskee seuraavaa kierrosta, mutta builder
kertoi sen koko horisonttiin GW n..n+5. Mitattu kauden 26/27 GW1-5
deadlineilta (`scripts/measure_doubt_horizon.py`): d/75-pelaajan odotettu
saatavuus pysyy FPL:n omana lukuna ~0.75:ssa, mutta suhteessa terveisiin
(jotka putoavat 0.944 -> 0.830) haitta vaimenee 0.78 -> 0.85 -> 0.94. d/25- ja
d/50-lippu palautuu samalle tasolle jo seuraavalla deadlinella, joten niiden
kertominen koko horisonttiin myi pelaajan kuudeksi kierrokseksi.

Mekanismit (CLAUDE.md 6a):
  (1) yksi lukija: `fpl_xp.round_availability_factor` antaa kertoimen
      kierrokselle k, ja `build_fpl_xp.round_minutes` on ainoa paikka jossa
      builder johtaa kierroksen minuutit.
  (2) kutsupaikka tarkistetaan AST:lla (muisti testi-kutsuu-funktiota-ei-
      kutsupaikkaa): silmukan xP lasketaan round_minutesin tuloksesta.
  (3) vaiheet: ennen deadlinea (otsikko = horisontin ensimmainen kierros),
      ja kesken kierroksen (otsikko = toinen kierros, ensimmainen on kesken).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts import build_fpl_xp as b
from src.models import fpl_xp as xp

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8")

REC = xp.DOUBT_RECOVERY


def _mm(p_start=0.8, p_sub=0.5):
    return xp.recompute_minutes({
        "p_start_raw": p_start, "p_start": p_start * 0.95, "p_sub": p_sub,
        "e_min_start": 84.0, "e_min_sub": 22.0, "p60_start": 0.88,
        "p60_sub": 0.05, "n_obs": 12, "confidence": "high"})


def _el(status, chance):
    return {"id": 1, "status": status, "chance_of_playing_next_round": chance}


# ---------------------------------------------------------------- kerroin
def test_mitatut_tasot_ovat_nousevia_ja_alle_yhden():
    """Palautuminen on monotoninen eika ylita tervetta (1.0): data ei kerro
    kolmannen kierroksen jalkeisesta, joten viimeinen taso pidetaan."""
    assert list(REC) == sorted(REC) and all(0.0 < r < 1.0 for r in REC)


@pytest.mark.parametrize("chance", [25, 50, 75, None])
def test_otsikkokierros_on_fpln_oma_luku(chance):
    assert xp.round_availability_factor("d", chance, 0) == xp.availability_factor("d", chance)


@pytest.mark.parametrize("chance", [25, 50, 75, None])
def test_myohemmat_kierrokset_mitatulla_palautumisella(chance):
    f = xp.availability_factor("d", chance)
    got = [xp.round_availability_factor("d", chance, k) for k in range(1, 7)]
    assert got == [max(f, REC[0]), max(f, REC[1])] + [max(f, REC[2])] * 4


def test_kerroin_ei_koskaan_alle_fpln_prosentin():
    """FPL ei anna 90:ta nykyisin, mutta jos antaa, lippu ei saa pudottaa
    myohempaa kierrosta alle FPL:n oman luvun."""
    assert xp.round_availability_factor("d", 90, 1) == pytest.approx(0.90)


@pytest.mark.parametrize("status,chance", [("a", None), ("i", 0), ("s", 0),
                                           ("u", 0), ("n", None), ("d", 0)])
def test_terve_ja_varma_poissaolo_ennallaan_koko_horisontissa(status, chance):
    f = xp.availability_factor(status, chance)
    assert {xp.round_availability_factor(status, chance, k) for k in range(-1, 7)} == {f}


def test_kesken_oleva_kierros_kayttaa_fpln_lukua():
    assert xp.round_availability_factor("d", 25, -1) == 0.25


# ---------------------------------------------------------------- minuutit
@pytest.mark.parametrize("chance", [25, 50, 75, None])
@pytest.mark.parametrize("k", [0, 1, 2, 3, 5])
def test_kierroksen_minuutit_ovat_terve_kertaa_kierroksen_kerroin(chance, k):
    """Invariantti: round_minutes(terve x f, k) == terve x f_k. Sama
    riippumatta siita milla polulla lipullinen malli syntyi."""
    healthy = _mm()
    flagged = xp.apply_availability(healthy, "d", chance)
    got = b.round_minutes(flagged, _el("d", chance), 6 + k, 6,
                          availability_in_value=False)
    want = xp.scale_availability(healthy, xp.round_availability_factor("d", chance, k))
    for key in ("xmins", "p60", "p1_59", "p_start", "p_sub"):
        assert got[key] == pytest.approx(want[key], rel=1e-12), key


def test_kasiohituksen_polku_skaalautuu_samoin():
    """set_p_start kertoo uuden p_startin f:lla ja p_sub kantaa f:n valmiiksi."""
    healthy = _mm()
    flagged = xp.set_p_start(xp.apply_availability(healthy, "d", 50), 0.9,
                             status="d", chance=50, availability_in_value=False)
    got = b.round_minutes(flagged, _el("d", 50), 7, 6, availability_in_value=False)
    ref = xp.set_p_start(healthy, 0.9, status="a", chance=None,
                         availability_in_value=False)
    want = xp.scale_availability(ref, REC[0])
    for key in ("xmins", "p60", "p1_59"):
        assert got[key] == pytest.approx(want[key], rel=1e-12), key


def test_ehdollinen_ohitus_ei_skaalaudu():
    """until_available-rivin luku on jo poissaolon luku."""
    mm = xp.apply_availability(_mm(), "d", 25)
    assert b.round_minutes(mm, _el("d", 25), 9, 6, availability_in_value=True) is mm


def test_terve_pelaaja_on_sama_olio():
    mm = _mm()
    for g in range(5, 12):
        assert b.round_minutes(mm, _el("a", None), g, 6, availability_in_value=False) is mm


def test_poissa_oleva_pysyy_nollassa():
    mm = xp.apply_availability(_mm(), "i", 0)
    assert b.round_minutes(mm, _el("i", 0), 9, 6, availability_in_value=False)["xmins"] == 0.0


# ---------------------------------------------------------------- vaiheet (6a kohta 3)
def _horizon_xmins(chance, horizon, headline):
    healthy = _mm()
    flagged = xp.apply_availability(healthy, "d", chance)
    return [b.round_minutes(flagged, _el("d", chance), g, headline,
                            availability_in_value=False)["xmins"] for g in horizon]


@pytest.mark.parametrize("chance", [25, 75])
def test_ennen_deadlinea_ensimmainen_kierros_on_lipun_kierros(chance):
    h = list(range(6, 12))
    xm = _horizon_xmins(chance, h, headline=6)
    healthy = _mm()["xmins"]
    f = chance / 100
    assert xm[0] == pytest.approx(xp.scale_availability(_mm(), f)["xmins"])
    assert xm[1] == pytest.approx(xp.scale_availability(_mm(), max(f, REC[0]))["xmins"])
    assert all(x < healthy for x in xm), "lippu ei saa nostaa yli terveen"


def test_kesken_kierroksen_lippu_koskee_seuraavaa_kierrosta():
    """next_gw = 5 on kesken, otsikko = 6. FPL:n prosentti koskee GW6:ta,
    joten GW5 ja GW6 kantavat sen ja palautuminen alkaa GW7:sta."""
    h = list(range(5, 11))
    xm = _horizon_xmins(25, h, headline=6)
    f25 = xp.scale_availability(_mm(), 0.25)["xmins"]
    assert xm[0] == pytest.approx(f25) and xm[1] == pytest.approx(f25)
    assert xm[2] == pytest.approx(xp.scale_availability(_mm(), REC[0])["xmins"])


def test_vanha_kaytos_olisi_kertonut_koko_horisontin():
    """Erotteleva: ennen korjausta jokainen kierros oli f x terve. Nyt d/25
    horisontin summa on yli kaksinkertainen."""
    h = list(range(6, 12))
    uusi = sum(_horizon_xmins(25, h, headline=6))
    vanha = xp.apply_availability(_mm(), "d", 25)["xmins"] * len(h)
    assert uusi > 2 * vanha


# ---------------------------------------------------------------- kutsupaikka
def _gw_loop() -> ast.For:
    main = next(n for n in ast.parse(SRC).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    loops = [n for n in ast.walk(main) if isinstance(n, ast.For)
             and ast.unparse(n.target) == "g" and ast.unparse(n.iter) == "horizon"
             and "xp_components" in ast.unparse(n)]
    assert len(loops) == 1
    return loops[0]


def test_silmukka_johtaa_minuutit_round_minutesista():
    loop = _gw_loop()
    calls = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
             and ast.unparse(n.func) == "round_minutes"]
    assert len(calls) == 1
    c = calls[0]
    assert [ast.unparse(a) for a in c.args] == ["mm", "e", "g", "headline_gw"]
    assert {k.arg: ast.unparse(k.value) for k in c.keywords} == {
        "availability_in_value": "conditional_ov"}
    src = ast.unparse(loop)
    # Silmukka ei saa lukea pelaajatason minuutteja suoraan (vanha polku).
    for vanha in ("xmins * mult", "p60 * mult", "p1_59 * mult"):
        assert vanha not in src, vanha
    assert "mm_r['xmins'] * mult" in src


def test_ehdollinen_ohitus_luetaan_ohitusrivilta():
    assert ('conditional_ov = bool((override_applied.get(pid) or {})'
            '.get("until_available"))') in SRC
