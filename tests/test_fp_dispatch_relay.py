# -*- coding: utf-8 -*-
"""FP-DISPATCH-RELAY-PORTTI, saman repon versio (26.9.2026).

Portoitu goaliq-app/scripts/autopilot/tests/test_fp_dispatch_relay.py:sta.
Tama versio on YKSINKERTAISEMPI kuin alkuperainen: relay ja sen kohteet
elavat nyt SAMASSA checkoutissa, joten ei tarvita sisarpolku-/API-fallbackia
eika skip-if-missing-logiikkaa — `.github/workflows/*.yml` on aina lasna.

Kaataa jos relayn kohdelista (TARGETS + EXCEPTIONS) ja taman repon
cron-ajastetut workflow't eriytyvat: uusi cron-workflow, poistettu kohde,
kohteelta kadonnut workflow_dispatch tai osajoukkoslotti jota tiedostossa
ei enaa ole.

Lisatty tahan versioon (ei alkuperaisessa, koska ei relevanttia silloin):
testi joka kaataa jos workflow YAML:sta katoaa `actions: write` -permissio —
ilman sita `gh workflow run` epaonnistuisi HILJAA tuotannossa (ensimmainen
merkki olisi "0 dispatchia ikina", ei valitonta virhetta) koska
oletus-GITHUB_TOKENilla ei enaa olisi Actions-write-oikeutta.

Ajo: python -m pytest tests/test_fp_dispatch_relay.py -q
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fp_dispatch_relay as relay  # noqa: E402
from cron_lite import cron_exprs  # noqa: E402

WORKFLOW_DIR = ROOT / ".github" / "workflows"
RELAY_YML = WORKFLOW_DIR / "fp-dispatch-relay.yml"


def _all_workflows() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(WORKFLOW_DIR.glob("*.yml"))}


def _cron_workflows(all_wf: dict[str, str]) -> dict[str, list[str]]:
    return {name: cron_exprs(y) for name, y in all_wf.items() if cron_exprs(y)}


# ------------------------------------------------------------- listojen pariteetti
def test_every_cron_workflow_is_target_or_documented_exception():
    all_wf = _all_workflows()
    crons = _cron_workflows(all_wf)
    targets = {t["workflow"] for t in relay.TARGETS}
    covered = targets | set(relay.EXCEPTIONS)
    missing = sorted(set(crons) - covered)
    assert not missing, (
        f"cron-workflow ilman relay-paatosta: {missing}. "
        "Lisaa TARGETS:iin tai EXCEPTIONS:iin perustelun kanssa.")
    # Relay itse ei saa laukaista itseaan (ei omaa nimeaan TARGETS:issa).
    assert RELAY_YML.name not in targets


def test_targets_and_exceptions_exist_and_have_cron():
    all_wf = _all_workflows()
    crons = _cron_workflows(all_wf)
    for t in relay.TARGETS:
        assert t["workflow"] in crons, f"kohde {t['workflow']} ei ole cron-workflow"
    stale = sorted(set(relay.EXCEPTIONS) - set(crons))
    assert not stale, f"EXCEPTIONS viittaa workflow'hun jolla ei ole enaa cronia: {stale}"


def test_targets_and_exceptions_are_disjoint_and_reasons_nonempty():
    targets = {t["workflow"] for t in relay.TARGETS}
    assert not targets & set(relay.EXCEPTIONS)
    for name, reason in relay.EXCEPTIONS.items():
        assert reason and len(reason) >= 15, f"{name}: perustelu puuttuu"


def test_every_target_has_workflow_dispatch():
    all_wf = _all_workflows()
    lacking = [t["workflow"] for t in relay.TARGETS
               if not relay.has_workflow_dispatch(all_wf[t["workflow"]])]
    assert not lacking, f"kohde ilman workflow_dispatch: (relay ei voi laukaista): {lacking}"


def test_slot_subsets_exist_in_file():
    all_wf = _all_workflows()
    for t in relay.TARGETS:
        if t["slots"] is None:
            continue
        exprs = cron_exprs(all_wf[t["workflow"]])
        missing = [s for s in t["slots"] if s not in exprs]
        assert not missing, f"{t['workflow']}: slotti {missing} ei ole tiedostossa {exprs}"


def test_relay_workflow_is_hourly_and_runs_the_script():
    y = RELAY_YML.read_text(encoding="utf-8")
    exprs = cron_exprs(y)
    assert len(exprs) == 1 and exprs[0].split()[1] == "*", f"relayn on oltava tunneittainen: {exprs}"
    assert "workflow_dispatch:" in y
    assert "scripts/fp_dispatch_relay.py" in y


def test_relay_workflow_grants_actions_write():
    """Negatiivinen kontrolli: ilman tata `gh workflow run` epaonnistuu
    hiljaa oletustokenilla, ja relay nayttaisi vihrealta (exit 0, 'skip')
    silla se ei koskaan paase dispatch-haaraan asti testeissa — vain
    tuotannossa `gh` palauttaisi 403:n. Sama vikaluokka kuin FP_DISPATCH_PAT
    goaliq-appin versiossa: puuttuva oikeus on ero puuttuvaan tyohon, ei
    puuttuvaan ajoon."""
    y = RELAY_YML.read_text(encoding="utf-8")
    assert "actions: write" in y, (
        "fp-dispatch-relay.yml: 'permissions: actions: write' puuttuu — "
        "GITHUB_TOKEN ei silloin voi laukaista workflow_dispatchia.")


# ------------------------------------------------------------- paatoslogiikka
Y_HOURLY = 'on:\n  schedule:\n    - cron: "20 * * * *"\n  workflow_dispatch: {}\n'
Y_NO_DISPATCH = 'on:\n  schedule:\n    - cron: "20 * * * *"\n'
NOW = datetime(2026, 9, 26, 12, 50, tzinfo=timezone.utc)


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
             "createdAt": "2026-09-26T12:31:00Z"}]
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


def test_main_without_gh_token_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    rc = relay.main(["--dry-run"])
    assert rc == 2
    assert "GH_TOKEN puuttuu" in capsys.readouterr().out
