"""Portti: UCL Fantasyn xP julkaistaan Premiumina samaa polkua kuin FPL.

Villen paatos 21.9.2026: UCL xP on Premium (linja "raakaluvut ilmaiseksi,
malli maksaa"). Kolme asiaa voi kadota hiljaa ja kukin mitataan erikseen:

  1. `/api/fantasy/xp?league=ucl` maskaa ilmaiskayttajalle (top-10 teaser
     kuten FPL); ilman maskia koko Premium-lista menisi ilmaiseksi.
  2. Artefaktin skeema on se jota SPA ja mobiili lukevat (sama kuin FPL/SPL).
  3. ucl-refresh sekä RAKENTAA etta COMMITTAA tiedoston (muisti:
     gw_recap.json oli 7 vrk jaassa koska `git add` puuttui).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POS = ("GKP", "DEF", "MID", "FWD")
DATA_BASIS = {"domestic_league", "uefa_matches", "no_history"}


def _artefakti(n: int = 14) -> dict:
    pelaajat = []
    for i in range(n):
        xp = 10.0 - i * 0.5
        pelaajat.append({
            "id": 250000000 + i, "web_name": f"P{i}", "full_name": f"Player {i}",
            "team": "Club", "team_short": "CLB", "pos": POS[i % 4], "price": 5.0 + i % 3,
            "owned_pct": 1.0, "status": "a", "news": "", "xmins": 70.0, "p_start": 0.8,
            "data_basis": "domestic_league" if i % 2 else "uefa_matches",
            "xp_per_gw": round(xp / 3, 2), "xp_horizon_total": xp, "xp_next": round(xp / 3, 2),
            "xp_components": {"esiintyminen": 1.5},
            "gameweeks": [{"gw": g, "opponents": [{"opp": "OPP", "venue": "H"}],
                           "xp": round(xp / 3, 2)} for g in (2, 3, 4)],
        })
    return {"meta": {"product": "GoalIQ UCL Fantasy - expected points (xP)", "available": True,
                     "league": "INT-Champions League", "generated_at": "2026-09-21T16:00:00",
                     "deadline_gameweek": 2, "next_gameweek": 2, "current_gameweek": 2,
                     "horizon_gw": 3},
            "players": pelaajat}


@pytest.fixture
def ucl_tiedosto(tmp_path, monkeypatch):
    from src.models import fpl_xp
    p = tmp_path / "ucl_xp_projections.json"
    p.write_text(json.dumps(_artefakti()), encoding="utf-8")
    monkeypatch.setitem(fpl_xp.XP_PATHS, "ucl", p)
    return p


def test_ucl_on_rekisterissa():
    from src.models import fpl_xp
    assert fpl_xp.XP_PATHS["ucl"].name == "ucl_xp_projections.json"


def test_ilmaiskayttaja_saa_vain_teaserin(client, ucl_tiedosto, monkeypatch):
    import api.main as M
    monkeypatch.setattr(M, "is_premium_request", lambda request: False)
    r = client.get("/api/fantasy/xp?league=ucl")
    assert r.status_code == 200
    d = r.json()
    assert d["meta"].get("masked") is True
    assert len(d["players"]) == 10, "top-10 teaser kuten FPL"
    assert all("why" not in p for p in d["players"]), "why on vain FPL:n Premium-kentta"


def test_premium_saa_koko_listan(client, ucl_tiedosto, monkeypatch):
    import api.main as M
    monkeypatch.setattr(M, "is_premium_request", lambda request: True)
    d = client.get("/api/fantasy/xp?league=ucl").json()
    assert not d["meta"].get("masked")
    assert len(d["players"]) == 14
    # Jarjestys summan mukaan (sama sopimus kuin FPL:lla).
    tot = [p["xp_horizon_total"] for p in d["players"]]
    assert tot == sorted(tot, reverse=True)


def test_artefaktin_skeema_on_klienttien_skeema():
    """Rakentaja kirjoittaa kentat joita SPA/mobiili lukevat. Mitataan
    rakentajan omasta koodista (ei verkkoa): kenttalista tuota()-funktiossa."""
    src = (ROOT / "scripts" / "build_ucl_xp.py").read_text(encoding="utf-8")
    for kentta in ("web_name", "team_short", "pos", "price", "owned_pct", "status",
                   "xmins", "p_start", "data_basis", "xp_per_gw", "xp_horizon_total",
                   "xp_next", "gameweeks", "deadline_gameweek", "horizon_gw"):
        assert f'"{kentta}"' in src, kentta
    from scripts.build_ucl_xp import DATA_BASIS as DB, STATUS
    assert set(DB.values()) == DATA_BASIS
    assert set(STATUS.values()) <= {"a", "d", "i", "s", "u"}


def test_workflow_rakentaa_ja_committaa():
    wf = (ROOT / ".github" / "workflows" / "ucl-refresh.yml").read_text(encoding="utf-8")
    assert "python -m scripts.build_ucl_xp" in wf
    assert "git add data/ucl_xp_projections.json" in wf
    assert wf.index("scripts.build_uefa_model") < wf.index("scripts.build_ucl_xp"), \
        "xP lasketaan juuri bakatulla CL-mallilla"


def test_artefakti_ei_ole_gitignoressa():
    import subprocess
    r = subprocess.run(["git", "check-ignore", "-q", "data/ucl_xp_projections.json"],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 1


# ---------------------------------------------------------------------------
# Tuoreus (julkaisutarkistaja 21.9, blokkaava 1): vanha kierros ei saa nakya
# tulevana. Vaiheet synteettisina ajanhetkina (CLAUDE.md 6a, mek. 3).
# ---------------------------------------------------------------------------
import datetime as _dt

_DL = _dt.datetime(2026, 10, 13, 18, 45, tzinfo=_dt.timezone.utc)


def _payload(md=2, viimeinen=8):
    d = _artefakti()
    d["meta"].update({"deadline_utc": _DL.isoformat(), "deadline_gameweek": md,
                      "league_phase_last_md": viimeinen})
    return d


@pytest.mark.parametrize("tunnit,available,passed,syy", [
    (-24, True, None, None),            # ennen deadlinea
    (5, True, True, None),              # deadline mennyt, uusi build tulossa
    (40, False, True, "stale"),         # build ei edennyt 36 h:ssa
])
def test_tuoreus_vaiheittain(tunnit, available, passed, syy):
    from src.models.ucl_xp import tuoreus
    p = tuoreus(_payload(), _DL + _dt.timedelta(hours=tunnit))
    assert p["meta"]["available"] is available
    assert p["meta"].get("deadline_passed") is passed
    assert p["meta"].get("reason") == syy
    assert (len(p["players"]) > 0) is available, "rivit pois kun ei tarjolla"


def test_sarjavaiheen_viimeisen_kierroksen_jalkeen_syy_on_sarjavaihe():
    from src.models.ucl_xp import tuoreus
    p = tuoreus(_payload(md=8, viimeinen=8), _DL + _dt.timedelta(days=3))
    assert p["meta"]["available"] is False
    assert p["meta"]["reason"] == "league_phase_over"


def test_endpoint_ajaa_tuoreuden_ja_etag_vaihtuu(client, tmp_path, monkeypatch):
    """Kutsupaikka, ei vain funktio (muisti testi-kutsuu-funktiota-ei-
    kutsupaikkaa): vanhentunut artefakti ei saa tulla ulos API:sta."""
    import api.main as M
    from src.models import fpl_xp
    p = tmp_path / "ucl.json"
    vanha = _payload()
    vanha["meta"]["deadline_utc"] = "2020-01-01T00:00:00+00:00"
    p.write_text(json.dumps(vanha), encoding="utf-8")
    monkeypatch.setitem(fpl_xp.XP_PATHS, "ucl", p)
    monkeypatch.setattr(M, "is_premium_request", lambda request: True)
    r = client.get("/api/fantasy/xp?league=ucl")
    d = r.json()
    assert d["meta"]["available"] is False and d["players"] == []
    etag_vanha = r.headers["ETag"]
    tuore = _payload()
    tuore["meta"]["deadline_utc"] = "2099-01-01T00:00:00+00:00"
    p.write_text(json.dumps(tuore), encoding="utf-8")
    r2 = client.get("/api/fantasy/xp?league=ucl")
    assert r2.json()["meta"]["available"] is True
    assert r2.headers["ETag"] != etag_vanha


def test_suljettu_artefakti_ja_lukitsematon_kierros():
    from scripts.build_ucl_xp import seuraava_kierros, suljettu
    kaikki_lukittu = {"matchdays": [{"md": i, "deadline_utc": "x", "is_locked": True}
                                    for i in range(1, 9)]}
    assert seuraava_kierros(kaikki_lukittu) == (None, None)
    s = suljettu(None, None, "league_phase_over")
    assert s["meta"]["available"] is False and s["players"] == []
    assert s["meta"]["reason"] == "league_phase_over"


def test_komponenttiavaimet_ovat_englanniksi():
    from scripts.build_ucl_xp import KOMPONENTIT
    from src.models import ucl_xp as X
    jo = {"xg": 1.5, "xga": 1.0, "cs": 0.3, "gc2": 0.2}
    r = X.xp_pelaajalle("MID", joukkue=jo, minuutit=X.minuuttiarvio(0.9, 0.0, 1.0),
                        g90=0.2, a90=0.1, yc90=0.1, riisto3_90=0.3, kaukaa_osuus=0.1,
                        torjunnat_per_paastetty=2.5, p_mom=0.0)
    assert set(r["komponentit"]) == set(KOMPONENTIT), "uusi komponentti ilman julkista nimea"
    assert all(v.isascii() and "_" in v or v.isalpha() for v in KOMPONENTIT.values())
