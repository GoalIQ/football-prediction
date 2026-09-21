"""Wildcard-arvio lukee chip-tilan yhdesta lukijasta (21.9.2026).

🔴 MIKSI TAMA ON OLEMASSA. `data/model_squad_frozen/gw5.json` kirjasi
`chip_evaluation = {available: true, chip: wildcard, recommend: true,
wildcard_ev_total: 14.09}` entrylle 116920, joka pelasi wildcardin GW2:ssa
(FPL `entry/116920/history` chips: wildcard 2, 3xc 3). Mallin artefakti
suositteli chippia jota ei ole.

Juurisyy oli saannon 6a oppikirjatapaus: `wildcard_plan` palautti
`available: False` vain tyhjalle `gws`:lle ja siirsi chip-tilan kutsujan
vastuulle docstringissa, ja freeze-kutsuja antoi pelkan deadline-suodatuksen.
Oikea lukija (`fpl_chips.chip_state`) oli repossa jo, ja sama vika oli
korjattu kerran toisessa pinnassa (chips_payload 11.9).

Korjaus kolmessa kerroksessa, ja jokainen on vartioitu:
  1. `wildcard_plan(..., *, chips)` - pakollinen, ei oletusta. Unohdus on
     TypeError; hypoteettinen suunnitelma vaatii `CHIPS_HYPOTHETICAL`in
     nimeamisen kutsupaikassa (API tekee sen tietoisesti, 3.9 paatos).
  2. `_chip_evaluation` lukee tilan `fpl_chips.chip_state`in kautta, ja
     `chips_played=None` (historiaa ei luettu) on nakyva kieltaytyminen.
  3. `entry_state_for` -> `attach_entry_state` kuljettaa FPL:n
     `history.chips`in samasta historiasta kuin pankki ja FT; main() antaa
     sen `_chip_evaluation`ille. Paasta paahan -testi ajaa main():n.

Vaiheet (6a.3) mitataan synteettisilla chip-historioilla, ei taman kauden
tilasta: ei pelattu / pelattu tassa kierroksessa / pelattu aiemmin samalla
puoliskolla / toisen puoliskon wildcard auki / horisontti puoliskorajan yli.
Puoliskoraja luetaan bootstrapin `chips`-listasta kuten tuotannossa
(fpl_chips.chip_windows), ei kovakoodata.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from src.models import fpl_chips  # noqa: E402
from src.models import fpl_wildcard as wc  # noqa: E402
from test_wildcard_plan import _rivisto, _xi_fn  # noqa: E402

#: FPL 26/27 -muoto: wildcard kerran per puolisko (bootstrap `chips`).
BOOT = {"chips": [
    {"name": "wildcard", "start_event": 1, "stop_event": 19},
    {"name": "wildcard", "start_event": 20, "stop_event": 38},
]}


def _freeze_moduuli():
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _plan(monkeypatch, gws, played, current_gw):
    """wildcard_plan oikealla chip-tilalla. Uusi runko on selvasti parempi,
    joten kun chip ON pelattavissa, suunnitelma suosittelee sita - eli
    kieltaytyminen johtuu chip-tilasta eika datasta."""
    uusi = _rivisto(100, 6.0, gws=gws)
    monkeypatch.setattr(wc, "_optimi", lambda pool, g: {
        "xi": uusi[:11], "bench": uusi[11:], "proven": True})
    vanha = _rivisto(1, 1.0, gws=gws)
    tila = fpl_chips.chip_state(
        BOOT, {"chips": [{"name": "wildcard", "event": e} for e in played]},
        current_gw)
    return wc.wildcard_plan(vanha, vanha + uusi, list(gws), [], {}, _xi_fn,
                            "model", chips=tila)


# ---------------------------------------------------------------------------
# 1. Vaiheet
# ---------------------------------------------------------------------------
def test_ei_pelattu_suosittelee(monkeypatch):
    """Negatiivinen kontrolli: sama data ilman pelattua chippia suosittelee.
    Ilman tata alla olevat kieltaytymiset voisivat johtua datasta."""
    out = _plan(monkeypatch, range(5, 11), played=[], current_gw=5)
    assert out["available"] is True and out["recommend"] is True
    assert out["chip_available"] is True
    assert out["gw"] in range(5, 11)


def test_pelattu_tassa_kierroksessa_kieltaytyy(monkeypatch):
    out = _plan(monkeypatch, range(5, 11), played=[5], current_gw=5)
    assert out["available"] is False and out["chip_available"] is False
    assert "GW5" in out["note"]
    assert "recommend" not in out


def test_pelattu_aiemmin_samalla_puoliskolla_kieltaytyy(monkeypatch):
    """Tasan entry 116920:n tila GW5:ssa: wildcard pelattu GW2:ssa."""
    out = _plan(monkeypatch, range(5, 11), played=[2], current_gw=5)
    assert out["available"] is False and out["chip_available"] is False
    assert out["played_gws"] == [2]
    assert out["next_window_gw"] == 20
    assert "GW2" in out["note"] and "GW20" in out["note"]


def test_toisen_puoliskon_wildcard_auki(monkeypatch):
    """Ensimmaisen puoliskon wildcard pelattu, toinen puolisko auki."""
    out = _plan(monkeypatch, range(21, 27), played=[2], current_gw=21)
    assert out["available"] is True and out["chip_available"] is True
    assert out["gw"] >= 21


def test_horisontti_yli_puoliskorajan_vaihtopisteet_vain_auki_olevalla(monkeypatch):
    """GW17-22, ensimmainen puolisko kaytetty: vaihtopiste voi olla vain
    GW20+, mutta arviointi-ikkuna on koko horisontti."""
    out = _plan(monkeypatch, range(17, 23), played=[2], current_gw=17)
    assert out["available"] is True
    assert out["gw"] >= 20
    assert {c["gw"] for c in out["candidates"]} == {20, 21, 22}


def test_molemmat_puoliskot_kaytetty(monkeypatch):
    out = _plan(monkeypatch, range(25, 31), played=[2, 21], current_gw=25)
    assert out["available"] is False
    assert out["next_window_gw"] is None
    assert "No Wildcard window left" in out["note"]


# ---------------------------------------------------------------------------
# 2. Unohdus on mahdoton
# ---------------------------------------------------------------------------
def test_chips_on_pakollinen_avainsana_ilman_oletusta():
    p = inspect.signature(wc.wildcard_plan).parameters["chips"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is inspect.Parameter.empty


@pytest.mark.parametrize("arvo", [None, [], "wc", 0])
def test_tuntematon_chip_tila_ei_kelpaa(arvo):
    with pytest.raises(TypeError):
        wc.wildcard_plan([], [], [5], [], {}, _xi_fn, chips=arvo)


def test_api_valitsee_hypoteettisen_tietoisesti():
    """Poikkeus nakyy kutsupaikassa: API:n wildcard-plan nayttaa luvun
    hypoteettisena ja kertoo chip-tilan erikseen (3.9 portin paatos)."""
    src = (ROOT / "api" / "fantasy_edge.py").read_text(encoding="utf-8")
    assert "chips=fpl_wildcard.CHIPS_HYPOTHETICAL" in src


def test_freeze_ei_valitse_hypoteettista():
    """Mallin oma artefakti ei saa ohittaa chip-tilaa."""
    src = (ROOT / "scripts" / "freeze_model_squad_gw.py").read_text(
        encoding="utf-8")
    assert "CHIPS_HYPOTHETICAL" not in src


# ---------------------------------------------------------------------------
# 3. _chip_evaluation lukee lukijan kautta
# ---------------------------------------------------------------------------
def _eval(monkeypatch, played, gw=5):
    m = _freeze_moduuli()
    gws = range(gw, gw + 6)
    uusi = _rivisto(100, 6.0, gws=gws)
    monkeypatch.setattr(wc, "_optimi", lambda pool, g: {
        "xi": uusi[:11], "bench": uusi[11:], "proven": True})
    vanha = _rivisto(1, 1.0, gws=gws)
    chips = (None if played is None else
             [{"name": "wildcard", "event": e} for e in played])
    return m._chip_evaluation(vanha, vanha + uusi, gw, {}, bootstrap=BOOT,
                              chips_played=chips)


def test_chip_evaluation_pelattu_wildcard_ei_suosittele(monkeypatch):
    """GW5-tapaus: artefakti ei saa enaa kirjata available/recommend true."""
    out = _eval(monkeypatch, played=[2])
    assert out["available"] is False
    assert "recommend" not in out
    assert out["chip_played_gws"] == [2] and out["next_window_gw"] == 20


def test_chip_evaluation_ei_pelattu_suosittelee(monkeypatch):
    """Negatiivinen kontrolli: sama syote ilman pelattua chippia."""
    out = _eval(monkeypatch, played=[])
    assert out["available"] is True and out["recommend"] is True


def test_chip_evaluation_tuntematon_historia_kieltaytyy(monkeypatch):
    out = _eval(monkeypatch, played=None)
    assert out["available"] is False
    assert "chip history" in out["error"]


def test_chip_evaluation_parametrit_pakollisia():
    m = _freeze_moduuli()
    ps = inspect.signature(m._chip_evaluation).parameters
    for nimi in ("bootstrap", "chips_played"):
        assert ps[nimi].kind is inspect.Parameter.KEYWORD_ONLY
        assert ps[nimi].default is inspect.Parameter.empty


# ---------------------------------------------------------------------------
# 4. Kuljetus: entry_state_for -> attach_entry_state -> main()
# ---------------------------------------------------------------------------
def test_entry_state_for_kantaa_chipit_samasta_historiasta(monkeypatch):
    m = _freeze_moduuli()
    historia = {"current": [], "chips": [{"name": "wildcard", "event": 2}]}
    monkeypatch.setattr(m.hist_mod, "entry_state",
                        lambda *a, **k: {"gw": 4})
    tila, virhe = m.entry_state_for(
        4, [], {}, hae_historia=lambda e: (historia, None),
        hae_siirrot=lambda e: ([], None))
    assert virhe is None
    assert tila["chips"] == [{"name": "wildcard", "event": 2}]


def test_puuttuva_chips_kentta_on_tuntematon_ei_tyhja(monkeypatch):
    m = _freeze_moduuli()
    monkeypatch.setattr(m.hist_mod, "entry_state",
                        lambda *a, **k: {"gw": 4})
    tila, _ = m.entry_state_for(
        4, [], {}, hae_historia=lambda e: ({"current": []}, None),
        hae_siirrot=lambda e: ([], None))
    assert tila["chips"] is None


def _aja_main(monkeypatch, tmp_path, chips):
    """test_freeze_chain_continuityn main()-ajo, mutta entryn rahatila kantaa
    `chips`-kentan kuten oikea `entry_state_for`."""
    import test_freeze_chain_continuity as tfc
    alkuperainen = tfc._tila
    monkeypatch.setattr(tfc, "_tila",
                        lambda gw, ids: dict(alkuperainen(gw, ids), chips=chips))
    _m, rc, out = tfc._aja_freeze_main(monkeypatch, tmp_path,
                                       bootstrap_ids=[15])
    assert rc == 0 and out.exists()
    return json.loads(out.read_text(encoding="utf-8"))["meta"]["chip_evaluation"]


def test_main_kirjaa_pelatun_wildcardin(monkeypatch, tmp_path):
    """Paasta paahan: kutsupaikka main():ssa antaa chip-historian eteenpain."""
    ev = _aja_main(monkeypatch, tmp_path,
                   chips=[{"name": "wildcard", "event": 2}])
    assert ev["available"] is False
    assert ev.get("chip_played_gws") == [2], ev


def test_main_ilman_pelattua_ei_kirjaa_pelattua(monkeypatch, tmp_path):
    """Negatiivinen kontrolli: tyhja historia ei tuota 'already played'."""
    ev = _aja_main(monkeypatch, tmp_path, chips=[])
    assert "chip_played_gws" not in ev
    assert "error" not in ev, ev
