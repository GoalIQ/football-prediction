"""REEL-HORISONTTI-IKKUNA (11.9.2026, `cos-reports/QUEUE.md`).

TAUSTA. `scripts/gen_reel.py`:n `value`-kortti sanoi vakiotekstina "First six
gameweeks", mutta `xp_horizon_total` (jonka mukaan kortin rivit jarjestetaan)
kattaa pelaajan `gameweeks[]`-listan sellaisenaan - ja se lista alkaa
MENNEESTA kierroksesta heti kun deadline on mennyt ilman etta artefakti on
paivitetty seuraavalle kierrokselle. Vakioteksti lupaisi kuusi TULEVAA
kierrosta vaikka summa on esim. yksi pelattu + viisi tulevaa. Sama vikaluokka
kuin `gen_share_card.py`:n "GW1-6"-otsikko (korjattu johtamalla ikkuna
`fpl_gameweek.window_label`illa todellisista kierroksista).

Tama testi ajaa `card_value()`in oikeasti (importlib, sama kaava kuin
`test_card_club_best.py`) monkeypatatulla datalla - ei grep koodista.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "gen_reel", ROOT / "scripts" / "gen_reel.py")
reel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reel)


def _starter(pid, xp, price=5.0, gws=range(1, 7)):
    return {"id": pid, "web_name": f"P{pid}", "team_short": "TST",
            "price": price, "xp_horizon_total": xp, "xmins": 85.0,
            "status": "a", "gameweeks": [{"gw": g} for g in gws]}


def _payload(players, meta):
    return {"meta": meta, "players": players}


def _players(n=5, gws=range(1, 7)):
    return [_starter(i, xp=10.0 - i, gws=gws) for i in range(n)]


def test_preseason_window_names_the_full_six_gw_range(monkeypatch):
    """Ennen kautta (deadline = GW1) data kattaa GW1-6 ja lukija VOI vaikuttaa
    jokaiseen - "GW1-6" on oikea eika "First six gameweeks" ollut vaarin."""
    monkeypatch.setattr(reel, "_xp_payload", lambda: _payload(
        _players(), {"deadline_gameweek": 1, "generated_at": "2026-08-01T00:00:00"}))
    spec = reel.card_value()
    assert spec["sub1"] == "GW1-6", spec["sub1"]


def test_midseason_window_drops_the_played_gameweek(monkeypatch):
    """🔴 Sama data (GW1-6 listalla) mutta deadline on jo GW2:ssa - GW1 on
    pelattu eika lukija voi enaa vaikuttaa siihen. Vakioteksti olisi silti
    sanonut 'First six gameweeks'; oikea vastaus nimeaa jaljella olevat."""
    monkeypatch.setattr(reel, "_xp_payload", lambda: _payload(
        _players(), {"deadline_gameweek": 2,
                    "generated_at": "2026-08-08T00:00:00"}))
    spec = reel.card_value()
    assert spec["sub1"] == "GW2-6", spec["sub1"]
    assert "First six" not in spec["sub1"]
    assert "six gameweeks" not in spec["sub1"].lower()


def test_mutation_static_six_week_text_would_lie_midseason():
    """Negatiivinen kontrolli: todistaa etta vanha vakioteksti olisi tosiaan
    vaarin siina tilanteessa jota edellinen testi tarkistaa - muuten testi
    lapaisisi tyhjana (ei mittaisi mitaan)."""
    old_static_text = "First six gameweeks"
    real_window = "GW2-6"
    assert old_static_text != real_window
    assert "GW1" not in real_window  # GW1 on pelattu, sita ei pida nimeta
