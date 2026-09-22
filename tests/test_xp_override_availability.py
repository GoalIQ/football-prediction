"""XP-OVERRIDE-OHITTAA-SAATAVUUDEN (22.9.2026): pelaajaohitus ei saa ohittaa
FPL:n saatavuutta.

Julkaisutarkistajan loydos 12.9: `set_p_start` korvasi p_startin ajamatta
`apply_availability`a uudelleen. Roolirivi (varamiesvahti 0.08) on arvio
ALOITTAMISESTA, ei saatavuudesta: jos pelaaja loukkaantuu, ohitus palautti
pelaamistodennakoisyyden jonka FPL:n status oli nollannut. /fpl ja
/fpl/team-news vaittavat samalla etta saatavuus on xP:ssa (src/doubt_copy.py).

Suunnittelu (saanto 6a, mekanismi 1): `status` ja `chance` ovat pakollisia
avainsana-argumentteja, joten kutsuja ei voi unohtaa saatavuutta. Poikkeus on
eksplisiittinen `availability_in_value=True` (ehdollinen `until_available`-rivi,
jonka luku on jo poissaolon luku).

Vaiheet (saanto 6a, kohta 3): saatavilla (a), epavarma (d 25 / 50 / 75,
chance puuttuu), sivussa (i / s / u / n), ehdollinen rivi.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from src.models import fpl_xp as xp

ROOT = Path(__file__).resolve().parents[1]


def _gated(status: str, chance) -> dict:
    """Minuuttimalli joka on kulkenut builderin saatavuusportin lapi, kuten
    set_p_startin ainoalla kutsupaikalla (build_fpl_xp.py)."""
    mins = {r: 90.0 for r in range(1, 11)}
    starts = {r: 1 for r in range(1, 11)}
    mm = xp.minutes_model(mins, starts, list(range(1, 11)), n_last=None)
    return xp.apply_availability(mm, status, chance)


def test_saatavilla_ohitus_asettaa_luvun_sellaisenaan():
    out = xp.set_p_start(_gated("a", None), 0.08, status="a", chance=None,
                         availability_in_value=False)
    assert out["p_start"] == pytest.approx(0.08)
    assert out["p_start_raw"] == pytest.approx(0.08)


@pytest.mark.parametrize("chance,f", [(25, 0.25), (50, 0.5), (75, 0.75), (None, 0.5)])
def test_epavarma_ohitus_skaalataan_saatavuudella(chance, f):
    """DoD: override statukselle d -> xP skaalattu. Vanha koodi antoi 0.8."""
    out = xp.set_p_start(_gated("d", chance), 0.8, status="d", chance=chance,
                         availability_in_value=False)
    assert out["p_start"] == pytest.approx(0.8 * f)
    assert out["p_start_raw"] == pytest.approx(0.8 * f)


@pytest.mark.parametrize("status", ["i", "s", "u", "n"])
def test_sivussa_ohitus_ei_herata_minuutteja(status):
    out = xp.set_p_start(_gated(status, 0), 0.9, status=status, chance=0,
                         availability_in_value=False)
    assert out["p_start"] == 0.0
    assert out["xmins"] == pytest.approx(0.0)


def test_p_sub_ei_skaalaudu_kahdesti():
    """Syote on jo portitettu: koko apply_availability uudelleen olisi
    kertonut p_subin toiseen kertaan (0.5 * 0.5)."""
    gated = _gated("d", 50)
    out = xp.set_p_start(gated, 0.6, status="d", chance=50, availability_in_value=False)
    assert out["p_sub"] == pytest.approx(gated["p_sub"])


def test_ehdollinen_rivi_on_jo_poissaolon_luku():
    out = xp.set_p_start(_gated("d", 50), 0.3, status="d", chance=50,
                         availability_in_value=True)
    assert out["p_start"] == pytest.approx(0.3)


def test_saatavuutta_ei_voi_unohtaa():
    """Mekanismi 1: ilman statusta ja chancea kutsu kaatuu, se ei oleta 'a'."""
    params = inspect.signature(xp.set_p_start).parameters
    for name in ("status", "chance", "availability_in_value"):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert params[name].default is inspect.Parameter.empty, f"{name} ei saa olla oletusarvollinen"
    with pytest.raises(TypeError):
        xp.set_p_start(_gated("a", None), 0.5)  # type: ignore[call-arg]


def test_kutsupaikka_antaa_fpln_saatavuuden_ja_ehdollisuuden():
    """Muisti 'testi kutsuu funktiota, ei kutsupaikkaa': builderin ainoa
    kutsu lukee statuksen ja chancen bootstrapista ja ehdollisuuden rivilta."""
    src = (ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(r"xp\.set_p_start\(", src)]
    assert len(calls) == 1, "uusi set_p_start-kutsupaikka: tarkista saatavuus sielta"
    call = src[calls[0]:calls[0] + 400]
    assert 'status=el_ov.get("status", "a")' in call
    assert 'chance=el_ov.get("chance_of_playing_next_round")' in call
    assert 'availability_in_value=bool(ov.get("until_available"))' in call
