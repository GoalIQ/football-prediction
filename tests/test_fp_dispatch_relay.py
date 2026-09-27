# -*- coding: utf-8 -*-
"""FP-DISPATCH-RELAY-PORTTI (AUTO-S14 10.9.2026, siirretty goaliq-appista 27.9).

Kaataa jos relayn kohdelista (scripts/fp_dispatch_relay.py TARGETS +
EXCEPTIONS) ja taman repon cron-ajastetut workflow't eriytyvat: uusi
cron-workflow, poistettu kohde, kohteelta kadonnut workflow_dispatch tai
osajoukkoslotti jota tiedostossa ei enaa ole.

Ennen siirtoa tama portti asui goaliq-appissa ja luki taman repon tiedostot
sisarpolusta tai julkisesta API:sta (ja skippasi ilman kumpaakaan). Nyt
tiedostot ovat samassa repossa: portti ei voi skipata.

Paatoslogiikalle positiivinen JA negatiivinen kontrolli ilman verkkoa.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import fp_dispatch_relay as relay
from scripts.cron_expr import cron_exprs

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
RELAY_YML = WF / "fp-dispatch-relay.yml"


@pytest.fixture(scope="module")
def fp() -> dict[str, str]:
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted(WF.glob("*.yml"))}
    assert len(files) >= 10, f"workflow'ja vain {len(files)}: onko polku oikein?"
    return files


def _cron_workflows(fp: dict[str, str]) -> dict[str, list[str]]:
    return {name: cron_exprs(y) for name, y in fp.items() if cron_exprs(y)}


# ------------------------------------------------------------- listojen pariteetti
def test_every_cron_workflow_is_target_or_documented_exception(fp):
    crons = _cron_workflows(fp)
    covered = {t["workflow"] for t in relay.TARGETS} | set(relay.EXCEPTIONS)
    missing = sorted(set(crons) - covered)
    assert not missing, (
        f"cron-workflow ilman relay-paatosta: {missing}. "
        "Lisaa TARGETS:iin tai EXCEPTIONS:iin perustelun kanssa.")


def test_targets_and_exceptions_exist_and_have_cron(fp):
    crons = _cron_workflows(fp)
    for t in relay.TARGETS:
        assert t["workflow"] in crons, f"kohde {t['workflow']} ei ole cron-workflow"
    stale = sorted(set(relay.EXCEPTIONS) - set(crons))
    assert not stale, f"EXCEPTIONS viittaa workflow'hun jolla ei ole enaa cronia: {stale}"


def test_targets_and_exceptions_are_disjoint_and_reasons_nonempty():
    targets = {t["workflow"] for t in relay.TARGETS}
    assert not targets & set(relay.EXCEPTIONS)
    for name, reason in relay.EXCEPTIONS.items():
        assert reason and len(reason) >= 15, f"{name}: perustelu puuttuu"


def test_every_target_has_workflow_dispatch(fp):
    lacking = [t["workflow"] for t in relay.TARGETS
               if not relay.has_workflow_dispatch(fp[t["workflow"]])]
    assert not lacking, f"kohde ilman workflow_dispatch: (relay ei voi laukaista): {lacking}"


def test_slot_subsets_exist_in_file(fp):
    for t in relay.TARGETS:
        if t["slots"] is None:
            continue
        exprs = cron_exprs(fp[t["workflow"]])
        missing = [s for s in t["slots"] if s not in exprs]
        assert not missing, f"{t['workflow']}: slotti {missing} ei ole tiedostossa {exprs}"


def test_relay_reads_the_same_files_the_gate_reads():
    """Relay lukee kohteen YAMLin tyopuusta; sama hakemisto kuin portilla."""
    assert relay.WORKFLOWS == WF
    assert relay.read_workflow_yaml("env-health-watch.yml") == (WF / "env-health-watch.yml").read_text(
        encoding="utf-8")


def test_relay_workflow_is_hourly_and_dispatches_with_github_token():
    y = RELAY_YML.read_text(encoding="utf-8")
    exprs = cron_exprs(y)
    assert len(exprs) == 1 and exprs[0].split()[1] == "*", f"relayn on oltava tunneittainen: {exprs}"
    assert "workflow_dispatch:" in y
    assert "python3 -m scripts.fp_dispatch_relay" in y
    # GITHUB_TOKEN tarvitsee actions: write voidakseen laukaista kohteet.
    assert "actions: write" in y
    assert "GH_TOKEN: ${{ github.token }}" in y
    # Ei PAT:ia: sen vanheneminen pysayttaisi relayn hiljaa (vanha PAT
    # umpeutui 10.10.2026, samana paivana kuin GW6-deadline).
    assert "secrets." not in y


# ------------------------------------------------------------- paatoslogiikka
Y_HOURLY = 'on:\n  schedule:\n    - cron: "20 * * * *"\n  workflow_dispatch: {}\n'
Y_NO_DISPATCH = 'on:\n  schedule:\n    - cron: "20 * * * *"\n'
NOW = datetime(2026, 9, 10, 12, 50, tzinfo=timezone.utc)


def test_due_since_finds_slot_in_lookback_and_not_outside():
    assert relay.due_since(["20 * * * *"], NOW) == NOW.replace(minute=20)
    assert relay.due_since(["0 */3 * * *"], NOW) == NOW.replace(hour=12, minute=0)
    assert relay.due_since(["0 */3 * * *"], NOW.replace(hour=13)) is None
    assert relay.due_since(["15 9 * * *"], NOW) is None


def test_decide_dispatches_when_slot_passed_without_run():
    action, reason = relay.decide("x.yml", Y_HOURLY, None, NOW, lambda since: [])
    assert action == "dispatch", reason


def test_decide_skips_when_run_exists_after_slot():
    runs = [{"databaseId": 1, "event": "schedule", "status": "completed",
             "createdAt": "2026-09-10T12:31:00Z"}]
    action, reason = relay.decide("x.yml", Y_HOURLY, None, NOW, lambda since: runs)
    assert action == "skip" and "jo olemassa" in reason


def test_decide_passes_slot_time_as_since_to_run_lookup():
    seen = {}

    def lookup(since):
        seen["since"] = since
        return []

    relay.decide("x.yml", Y_HOURLY, None, NOW, lookup)
    assert seen["since"] == NOW.replace(minute=20)


def test_decide_skips_without_workflow_dispatch_and_outside_window():
    action, reason = relay.decide("x.yml", Y_NO_DISPATCH, None, NOW, lambda since: [])
    assert action == "skip" and "workflow_dispatch" in reason
    y6 = 'on:\n  schedule:\n    - cron: "20 */6 * * *"\n  workflow_dispatch: {}\n'
    action, reason = relay.decide("x.yml", y6, None, NOW.replace(hour=13), lambda since: [])
    assert action == "skip" and "ei slottia" in reason
    action, _ = relay.decide("x.yml", y6, None, NOW, lambda since: [])
    assert action == "dispatch"


def test_decide_slot_subset_ignores_other_slots_and_skips_if_subset_gone():
    y = ('on:\n  schedule:\n    - cron: "0 */3 * * *"\n    - cron: "40 7-18 * * *"\n'
         '  workflow_dispatch: {}\n')
    # 13:50: vain :40-slotti osui, mutta se ei ole osajoukossa -> skip
    action, reason = relay.decide("x.yml", y, ["0 */3 * * *"], NOW.replace(hour=13), lambda s: [])
    assert action == "skip" and "ei slottia" in reason
    action, _ = relay.decide("x.yml", y, ["0 */3 * * *"], NOW, lambda s: [])
    assert action == "dispatch"
    action, reason = relay.decide("x.yml", y, ["0 */2 * * *"], NOW, lambda s: [])
    assert action == "skip" and "ei ole enaa" in reason


def test_main_without_token_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert relay.main([]) == 2
    assert "GH_TOKEN puuttuu" in capsys.readouterr().out
