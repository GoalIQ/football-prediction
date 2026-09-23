"""UCL-MENUT (23.9.2026): UCL-artefaktin joukkuetaso Teams-nakymaa varten.

Villen valinta 23.9: UCL saa saman rakenteen kuin FPL ja RSL (Players-
esiasetukset + Teams: clean sheet % ja otteluvaikeus kierroksittain).

Mekanismit (CLAUDE.md 6a):
  (1) yksi lahde: joukkueen CS% tulee samasta `odotus`-funktiosta kuin
      puolustajien nollapeli-komponentti, joten ne eivat voi erota
      (kutsupaikka AST:lla: `tuota` antaa joukkuetasolle saman `odotus`in),
  (2) puuttuva ei ole nolla: ottelu jota malli ei tunne jaa pois,
  (3) vaiheet: vanhentunut artefakti (deadline + VANHA_H mennyt) tyhjentaa
      joukkuetason samalla kun pelaajarivit, jottei pelatun kierroksen CS%
      jaa tarjolle.
"""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

from scripts import build_ucl_xp as B
from src.models import ucl_xp as X

ROOT = Path(__file__).resolve().parents[1]

SYOTE = [{"tId": 1, "tName": "Arsenal", "cCode": "ARS"},
         {"tId": 2, "tName": "Galatasaray", "cCode": "GAL"},
         {"tId": 3, "tName": "Qarabag", "cCode": "QAR"},
         {"tId": 4, "tName": "Unknown FC", "cCode": "UNK"}]
KIERROKSET = {2: {"1": ("1", "2"), "2": ("1", "2"), "3": ("3", "4"), "4": ("3", "4")},
              3: {"2": ("2", "1"), "1": ("2", "1")}}


def odotus(koti, vieras):
    if "4" in (koti, vieras):
        return None  # malli ei tunne seuraa
    base = {"1": 0.45, "2": 0.20, "3": 0.30}
    return {koti: {"cs": base[koti], "xg": 1.8, "xga": 0.9},
            vieras: {"cs": base[vieras] / 2, "xg": 0.9, "xga": 1.8}}


def test_joukkuetaso_kierroksittain_molemmille_puolille():
    t = {x["short"]: x for x in B.joukkuetaso([2, 3], KIERROKSET, odotus, SYOTE)}
    assert [f["gw"] for f in t["ARS"]["fixtures"]] == [2, 3]
    ars2 = t["ARS"]["fixtures"][0]
    assert ars2 == {"gw": 2, "opp": "GAL", "venue": "H", "cs_pct": 45.0, "xg": 1.8, "xga": 0.9}
    gal3 = t["GAL"]["fixtures"][1]
    assert gal3["venue"] == "H" and gal3["opp"] == "ARS" and gal3["cs_pct"] == 20.0
    assert t["ARS"]["fixtures"][1]["venue"] == "A"


def test_tuntematon_ottelu_jaa_pois_eika_ole_nolla():
    t = {x["short"]: x for x in B.joukkuetaso([2, 3], KIERROKSET, odotus, SYOTE)}
    assert "UNK" not in t and "QAR" not in t
    assert all(f["cs_pct"] > 0 for x in t.values() for f in x["fixtures"])


def test_jarjestys_keskimaaraisen_cs_mukaan():
    t = B.joukkuetaso([2, 3], KIERROKSET, odotus, SYOTE)
    avg = [sum(f["cs_pct"] for f in x["fixtures"]) / len(x["fixtures"]) for x in t]
    assert avg == sorted(avg, reverse=True)


def test_tuota_antaa_joukkuetasolle_saman_odotuksen_kuin_pelaajille():
    """Kutsupaikka: sama `odotus` kuin `rakenna`-kutsulla (muisti
    testi-kutsuu-funktiota-ei-kutsupaikkaa)."""
    src = (ROOT / "scripts" / "build_ucl_xp.py").read_text(encoding="utf-8")
    tuota = next(n for n in ast.parse(src).body
                 if isinstance(n, ast.FunctionDef) and n.name == "tuota")
    calls = {ast.unparse(n.func): n for n in ast.walk(tuota) if isinstance(n, ast.Call)}
    jt = calls["joukkuetaso"]
    assert [ast.unparse(a) for a in jt.args] == ["horisontti", "kierrokset", "odotus", "syote"]
    rak = calls["rakenna"]
    assert {k.arg: ast.unparse(k.value) for k in rak.keywords}["odotus"] == "odotus"
    ret = next(n for n in ast.walk(tuota) if isinstance(n, ast.Return)
               and isinstance(n.value, ast.Dict)
               and "teams" in [ast.literal_eval(k) for k in n.value.keys if k is not None])
    assert ret is not None


def _payload(deadline_h_ago: float) -> dict:
    now = dt.datetime(2026, 10, 14, 12, tzinfo=dt.timezone.utc)
    dl = now - dt.timedelta(hours=deadline_h_ago)
    return {"meta": {"available": True, "deadline_utc": dl.isoformat(),
                     "deadline_gameweek": 2, "league_phase_last_md": 8},
            "players": [{"id": 1}], "teams": [{"id": 1, "fixtures": [{"gw": 2}]}]}, now


def test_ennen_deadlinea_joukkuetaso_tarjolla():
    p, now = _payload(-5)
    assert X.tuoreus(p, now)["teams"]


def test_kesken_kierroksen_joukkuetaso_pysyy():
    p, now = _payload(1)
    out = X.tuoreus(p, now)
    assert out["meta"]["deadline_passed"] and out["teams"]


def test_vanhentunut_tyhjentaa_joukkuetason_pelaajien_kanssa():
    p, now = _payload(X.VANHA_H + 1)
    out = X.tuoreus(p, now)
    assert out["meta"]["available"] is False
    assert out["players"] == [] and out["teams"] == []
