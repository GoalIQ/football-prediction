# -*- coding: utf-8 -*-
"""FREEZEN RENDER-DEPLOY KAUDEN VAIHEISSA (22.9.2026, MALLIN-KAPTEENI-FREEZE-IKKUNA).

VIKA JOTA TAMA VARTIOI. Freeze committataan ~29 h ennen deadlinea, mutta API
nakee sen vasta seuraavassa ajastetussa Render-deployssa (jopa ~12 h). Sen
ajan goaliq.app/fpl ja API nimeavat eri kapteenin.

SAANTO 6a KOHTA 3: sama paatosfunktio ajetaan jokaisessa vaiheessa:

  a  ennen freezea        GW6 edessa, mainissa gw3-gw5        -> ok
  b  freeze mainissa, API vanha (entry_picks)                 -> dispatch
  b' sama, deploy alkoi 10 min sitten                         -> odota
  b'' sama, deploy alkoi 50 min sitten (kaatui/jumissa)       -> dispatch
  c  API lukee jo freezen                                     -> ok
  d  deadline mennyt, GW7 edessa ilman freezea                -> ok
  d' API laahaa: frozen mutta edellisen kierroksen            -> dispatch
  e  kausi paattynyt (deadline_gameweek None)                 -> ok
  f  API alhaalla / meta puuttuu                              -> tuntematon (ei dispatchia)

Portti myos workflow'lle: askel on olemassa, ajetaan pushin JALKEEN,
ei kaada ajoa (continue-on-error) ja sen kaatuminen nakyy Step healthissa.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts import render_deploy_after_freeze as rd

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "fpl-data-refresh.yml"

MAIN_ENNEN = {3, 4, 5}
MAIN_FREEZE = {3, 4, 5, 6}


def _meta(source, gw, deadline_gw):
    return {"source": source, "gw": gw, "deadline_gameweek": deadline_gw}


VAIHEET = [
    ("a_ennen_freezea", MAIN_ENNEN, _meta("entry_picks", 6, 6), None, "ok"),
    ("b_freeze_api_vanha", MAIN_FREEZE, _meta("entry_picks", 6, 6), None, "dispatch"),
    ("b1_deploy_kesken", MAIN_FREEZE, _meta("entry_picks", 6, 6), 10.0, "odota"),
    ("b2_deploy_vanha", MAIN_FREEZE, _meta("entry_picks", 6, 6), 50.0, "dispatch"),
    ("c_api_nakee", MAIN_FREEZE, _meta("frozen", 6, 6), None, "ok"),
    ("d_deadline_mennyt", MAIN_FREEZE, _meta("entry_picks", 7, 7), None, "ok"),
    ("d1_api_laahaa_kierroksen", {3, 4, 5, 6, 7}, _meta("frozen", 6, 7), None, "dispatch"),
    ("e_kausi_paattynyt", MAIN_FREEZE, _meta("frozen", 38, None), None, "ok"),
    ("f_api_alhaalla", MAIN_FREEZE, None, None, "tuntematon"),
    ("f1_meta_rikki", MAIN_FREEZE, "virhe", None, "tuntematon"),
]


@pytest.mark.parametrize("nimi,main_gws,meta,minuutit,odotettu", VAIHEET,
                         ids=[v[0] for v in VAIHEET])
def test_paatos_kauden_vaiheissa(nimi, main_gws, meta, minuutit, odotettu):
    toiminto, syy = rd.paatos(main_gws, meta, minuutit)
    assert toiminto == odotettu, f"{nimi}: {syy}"
    assert syy


def test_bool_ei_ole_kierros():
    # True == 1 Pythonissa; ilman tarkistusta gw1:n freeze "tasmaisi".
    assert rd.paatos({1}, _meta("entry_picks", 1, True), None)[0] == "ok"


def test_frozen_gws_lukee_vain_kierrostiedostot():
    rivit = ["data/model_squad_frozen/gw3.json", "data/model_squad_frozen/gw12.json",
             "data/model_squad_frozen/README.md", "data/model_squad_frozen/gw5.json.bak",
             "data\\model_squad_frozen\\gw6.json", ""]
    assert rd.frozen_gws(rivit) == {3, 12, 6}


def test_main_dispatchaa_vain_dispatch_paatoksella(monkeypatch):
    kutsut = []

    def fake_run(cmd, *a, **k):
        kutsut.append(cmd)

        class R:
            returncode = 0
            stdout = "[]"
            stderr = ""
        return R()

    monkeypatch.setattr(rd.subprocess, "run", fake_run)
    monkeypatch.setattr(rd, "_main_gws", lambda: MAIN_FREEZE)

    monkeypatch.setattr(rd, "_live_meta", lambda: _meta("frozen", 6, 6))
    assert rd.main([]) == 0
    assert not any(c[:3] == ["gh", "workflow", "run"] for c in kutsut)

    monkeypatch.setattr(rd, "_live_meta", lambda: _meta("entry_picks", 6, 6))
    assert rd.main(["--dry-run"]) == 0
    assert not any(c[:3] == ["gh", "workflow", "run"] for c in kutsut)

    assert rd.main([]) == 0
    assert ["gh", "workflow", "run", rd.WORKFLOW, "--ref", "main"] in kutsut


def test_tuntematon_ei_kaada_eika_dispatchaa(monkeypatch, capsys):
    kutsut = []
    monkeypatch.setattr(rd.subprocess, "run",
                        lambda cmd, *a, **k: kutsut.append(cmd) or type(
                            "R", (), {"returncode": 0, "stdout": "[]", "stderr": ""})())
    monkeypatch.setattr(rd, "_main_gws", lambda: MAIN_FREEZE)
    monkeypatch.setattr(rd, "_live_meta", lambda: None)
    assert rd.main([]) == 0
    assert "::warning::" in capsys.readouterr().out
    assert not any(c[:3] == ["gh", "workflow", "run"] for c in kutsut)


# ---- workflow-portti ----

def _steps():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    job = next(iter(doc["jobs"].values()))
    return job["steps"]


def _index(steps, pred):
    for i, s in enumerate(steps):
        if pred(s):
            return i
    return -1


def test_workflow_ajaa_askeleen_pushin_jalkeen():
    steps = _steps()
    i_freeze = _index(steps, lambda s: s.get("id") == "freeze_squad")
    i_push = _index(steps, lambda s: "git push origin HEAD:main" in (s.get("run") or ""))
    i_rd = _index(steps, lambda s: "scripts.render_deploy_after_freeze" in (s.get("run") or ""))
    assert i_freeze >= 0 and i_push >= 0, "freeze- tai push-askel puuttuu"
    assert i_rd > i_push > i_freeze, (
        "render_deploy_after_freeze pitaa ajaa pushin jalkeen: ennen pushia "
        "mainissa ei ole freezea ja askel sanoisi aina 'ok'")
    s = steps[i_rd]
    assert s.get("continue-on-error") is True, "askel ei saa kaataa datan pushia"
    assert s.get("id") == "render_after_freeze"
    assert "GH_TOKEN" in (s.get("env") or {}), "gh workflow run tarvitsee GH_TOKENin"


def test_workflow_step_health_nayttaa_kaatumisen():
    steps = _steps()
    health = next(s for s in steps if (s.get("name") or "").startswith("Step health"))
    assert "steps.render_after_freeze.outcome" in health["run"]


def test_workflow_saa_dispatchata():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    assert (doc.get("permissions") or {}).get("actions") == "write"
