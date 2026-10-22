"""PELIKIELTO-IKKUNA (22.10.2026): istuttu pelikielto ei ole valinta.

Ennen: minuutti-ikkuna luki kieltokierrosten nollat penkitykseksi. Mitattu
tapaus (GW1-7 26/27): punainen GW4:lla 22 min, 0 min GW5-6, avaus GW7:lla ->
p_start_raw 0.48 / xMins 31, ilman kieltokierroksia 0.80 / 55. Walk-forward
viidella kaudella: ks. fpl_xp.BAN_RED_MAX_ROUNDS-kommentti.

Mekanismit (CLAUDE.md 6a):
  (1) yksi lukija: `fpl_xp.window_minutes` (kayttaa `served_ban_rounds`) on
      ainoa tapa koota live-kauden minuutti-ikkuna builderissa ja backtestissa.
  (2) kutsupaikat AST:lla: builder ja ship-gaten backtest kutsuvat sita, eika
      builderissa ole enaa omaa kierrossummausta.
  (3) vaiheet: kielto kesken (historia loppuu kieltoon), kielto istuttu,
      kielto + aito pudotus, tuplakierros, blank, keltaisten raja ennen ja
      jalkeen viimeisen kierroksen. Invariantit ajetaan jokaisella
      historian katkaisulla.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.models import fpl_xp as xp

ROOT = Path(__file__).resolve().parents[1]


def _r(rnd, minutes, starts=None, red=0, yc=0):
    return {"round": rnd, "minutes": minutes,
            "starts": (1 if minutes >= 45 else 0) if starts is None else starts,
            "red_cards": red, "yellow_cards": yc}


# Mitattu tapaus sellaisenaan (FPL element-summary 398, 22.10.2026).
FODEN = [_r(1, 81, 1, yc=1), _r(2, 90, 1), _r(3, 24, 0), _r(4, 22, 1, red=1),
         _r(5, 0, 0), _r(6, 0, 0), _r(7, 76, 1)]


def _plain(rows):
    mr, sr = {}, {}
    for r in rows:
        mr[r["round"]] = mr.get(r["round"], 0) + r["minutes"]
        sr[r["round"]] = sr.get(r["round"], 0) + r["starts"]
    return mr, sr


# ---------------------------------------------------------------- lukija
def test_mitattu_tapaus_kieltokierrokset_pois():
    assert xp.served_ban_rounds(FODEN) == {5, 6}
    mr, sr = xp.window_minutes(FODEN)
    assert sorted(mr) == [1, 2, 3, 4, 7] and 5 not in sr and 6 not in sr


def test_mitattu_tapaus_minuutit_nousevat():
    raaka = xp.minutes_model(*_plain(FODEN), sorted(_plain(FODEN)[0]), n_last=6)
    mr, sr = xp.window_minutes(FODEN)
    uusi = xp.minutes_model(mr, sr, sorted(mr), n_last=6)
    assert raaka["xmins"] == pytest.approx(31.4, abs=0.1)
    assert uusi["xmins"] == pytest.approx(54.7, abs=0.1)
    assert uusi["p_start_raw"] == pytest.approx(0.8)


def test_nollaputki_ilman_laukaisijaa_sailyy():
    """9.8: '0-putki pois' hylattiin (varamaalivahdin nollat ovat signaali)."""
    rows = [_r(1, 90), _r(2, 0), _r(3, 0), _r(4, 0), _r(5, 90)]
    assert xp.served_ban_rounds(rows) == set()
    assert sorted(xp.window_minutes(rows)[0]) == [1, 2, 3, 4, 5]


def test_heti_palannut_ei_menetä_kierroksia():
    rows = [_r(1, 90, red=1), _r(2, 90), _r(3, 0)]
    assert xp.served_ban_rounds(rows) == set()


def test_katto_rajaa_aidon_pudotuksen():
    rows = [_r(1, 60, 1, red=1)] + [_r(k, 0, 0) for k in range(2, 7)]
    assert xp.served_ban_rounds(rows) == set(range(2, 2 + xp.BAN_RED_MAX_ROUNDS))


def test_laukaisija_jaa_ikkunaan_oletuksena():
    assert 4 in xp.window_minutes(FODEN)[0]
    assert 4 in xp.served_ban_rounds(FODEN, drop_trigger=True)


@pytest.mark.parametrize("viides,odotettu", [(19, {20}), (20, set())])
def test_keltaisten_raja_vain_ennen_viimeista_kierrosta(viides, odotettu):
    rows = [_r(k, 90, yc=1 if k in (3, 6, 9, 12, viides) else 0)
            for k in range(1, viides + 1)] + [_r(viides + 1, 0, 0)]
    assert xp.served_ban_rounds(rows) == odotettu


def test_kymmenes_keltainen_kaksi_ottelua():
    yc_rounds = {2, 4, 6, 8, 10, 12, 14, 16, 18, 22}
    rows = [_r(k, 90, yc=1 if k in yc_rounds else 0) for k in range(1, 23)]
    rows += [_r(23, 0, 0), _r(24, 0, 0), _r(25, 0, 0)]
    # 5. keltainen kierroksella 10 laukaisi myos, mutta kierros 11 pelattiin.
    assert xp.served_ban_rounds(rows) == {23, 24}


def test_tuplakierros_summataan_kierrokseksi():
    rows = [_r(1, 90), _r(2, 30, 1, red=1), _r(2, 0, 0), _r(3, 0, 0), _r(4, 90)]
    assert xp.served_ban_rounds(rows) == {3}
    mr, _sr = xp.window_minutes(rows)
    assert mr == {1: 90, 2: 30, 4: 90}


def test_blank_ei_kuluta_kieltoa():
    """Kierros jolla rivia ei ole (blank) ei ole ehdokas eika katkaise putkea."""
    rows = [_r(1, 90, red=1), _r(3, 0, 0), _r(4, 0, 0), _r(5, 0, 0), _r(6, 90)]
    assert xp.served_ban_rounds(rows) == {3, 4}


# ---------------------------------------------------------- vaiheet (6a-3)
@pytest.mark.parametrize("rows", [
    FODEN,
    [_r(1, 90), _r(2, 45, 1, red=1), _r(3, 0, 0), _r(4, 0, 0), _r(5, 0, 0)],
    [_r(k, 70, yc=1) for k in range(1, 8)] + [_r(8, 0, 0), _r(9, 90)],
    [_r(1, 0, 0), _r(2, 0, 0), _r(3, 90), _r(4, 0, 0)],
])
def test_invariantit_jokaisella_historian_katkaisulla(rows):
    """Sama funktio jokaisessa kauden vaiheessa: kielto kesken, istuttu, ohi."""
    for k in range(1, max(r["round"] for r in rows) + 1):
        upto = [r for r in rows if r["round"] <= k]
        ban = xp.served_ban_rounds(upto)
        mins = _plain(upto)[0]
        assert all(mins[b] == 0 for b in ban), (k, ban)
        assert ban <= set(mins)
        mr, sr = xp.window_minutes(upto)
        assert set(mr) == set(mins) - ban == set(sr)
        assert all(mr[x] == mins[x] for x in mr)
        # kielto on aina laukaisijan jalkeen
        first_trigger = min((r["round"] for r in upto if r["red_cards"]), default=None)
        if ban and first_trigger is not None and not any(r["yellow_cards"] for r in upto):
            assert min(ban) > first_trigger


def test_walk_forward_ei_nae_tulevaa():
    """Kierroksen k ikkuna riippuu vain kierroksista < k (backtestin ehto)."""
    for k in range(2, 8):
        before = [r for r in FODEN if r["round"] < k]
        mr, _ = xp.window_minutes(before)
        assert max(mr) < k


# -------------------------------------------------------------- kutsupaikat
def _calls(path: str, func: str) -> list[ast.Call]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and ast.unparse(n.func) == func]


def test_builder_kokoaa_ikkunan_yhdella_lukijalla():
    assert _calls("scripts/build_fpl_xp.py", "xp.window_minutes"), \
        "build_fpl_xp ei kokoa live-kauden ikkunaa window_minutesilla"


def test_builderissa_ei_omaa_kierrossummausta():
    """Raaka `mr[r['round']] += minutes` palauttaisi istutun kiellon valintana."""
    src = (ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript):
            assert "round" not in ast.unparse(n.target.slice), ast.unparse(n)


def test_ship_gaten_backtest_mittaa_samaa_ikkunaa():
    assert _calls("scripts/backtest_fpl_xp.py", "xp.window_minutes"), \
        "backtest_fpl_xp mittaa eri minuutti-ikkunaa kuin builder"
