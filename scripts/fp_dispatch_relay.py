# -*- coding: utf-8 -*-
"""FP-DISPATCH-RELAY, SAMAN REPON VERSIO (26.9.2026, QUEUE
ACTIONS-MINUUTIT-RELAY-FP:HEN, goaliq-app/cos-reports/QUEUE.md).

TAUSTA: relay eli alunperin goaliq-appissa ja laukaisi tämän repon
workflow'ja `gh workflow run -R GoalIQ/football-prediction`illa fine-grained
PATilla (`FP_DISPATCH_PAT`), koska goaliq-appin cronit toteutuvat 100 % ja
GitHubin oma cron tässä repossa laahasi (mitattu 3.9: fpl-transfer-watch
20 %, accuracy-log 50 %, fpl-data-refresh 35 %). goaliq-appin Actions-kiintiö
(2000 min/kk) oli 25.9 90 %:ssa, ja tämä relay yksin maksoi ~285 min/kk siellä
vaikka se ei laukaise mitään goaliq-appin OMAA workflow'ta.

MIKSI SAMAAN REPOON SIIRTO POISTAA PATIN TARPEEN: kun relay ajaa TÄSSÄ
repossa, `gh workflow run` kohdistuu samaan repoon jossa ajo itse on —
GitHubin oma `GITHUB_TOKEN` riittää (workflow'n `permissions: actions:
write`), koska cross-repo-kirjoitusta ei enää tarvita. Fine-grained PAT oli
tarpeen VAIN koska goaliq-app kirjoitti toiseen repoon.

MEKANIIKKA (muuttumaton goaliq-appin versiosta): ks. `decide()` + `due_since()`.
  1. Lue kohde-workflow'n YAML PAIKALLISESTA tiedostosta (ei contents-API-kutsua:
     sama checkout, sama commit — yksi lukija, ei voi eriytyä ajon omasta
     tilasta, CLAUDE.md 6a mekanismi 1).
  2. Jos jokin cron-slotti laukesi viimeisen LOOKBACK_MIN minuutin aikana, ajo
     on "due". Aikaisin due-slotti on `since`.
  3. Jos tässä repossa on jo ajo (mikä tahansa event) luotu `since`:n jälkeen,
     cron ehti itse -> ei tuplata. Muuten `gh workflow run`.
  4. Kohde ilman `workflow_dispatch:`-triggeria ohitetaan ja lokitetaan.

TARGETS on ainoa käsin ylläpidetty lista (SAMA sisältö kuin goaliq-appin
versiossa 25.9, siirretty sellaisenaan). Testi
`tests/test_fp_dispatch_relay.py` kaataa, jos tässä repossa on cron-workflow
joka ei ole TARGETS:ssa eikä EXCEPTIONS:ssa perusteluineen (mekanismi 2).

🔒 EI VIELÄ KYTKETTY: goaliq-appin `.github/workflows/fp-dispatch-relay.yml`
+ `scripts/fp_dispatch_relay.py` + `scripts/autopilot/tests/test_fp_dispatch_relay.py`
ovat KOSKEMATTA ja käynnissä ennallaan. `cf-worker/fp-cron-relay` (goaliq-app)
laukaisee goaliq-appin version tunneittain HTTP:lla; sen osoittaminen tähän
uuteen workflow'hun vaatii workerin `GITHUB_DISPATCH_TOKEN`-secretin
vaihdon PATiksi jolla on Actions-write TÄHÄN repoon (Ville, cos-reports
QUEUE-rivi ACTIONS-MINUUTIT-RELAY-FP:HEN). Kunnes se on tehty, goaliq-appin
vanhaa relayta EI POISTETA — sen poisto ilman workerin uudelleenkytkentaa
pysäyttäisi koko dispatch-mekanismin tuotannossa. Tämä haara on vain
fp-repon puoli valmiina Villen päätöstä varten.

Ajo: GH_TOKEN=<token, actions:write tähän repoon> python scripts/fp_dispatch_relay.py [--dry-run] [--now ISO]
0 EUR: vain gh CLI + tämän repon oma workflow_dispatch-oikeus.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from scripts.cron_lite import cron_exprs, parse_cron, _matches  # noqa: E402

WORKFLOW_DIR = ROOT / ".github" / "workflows"
LOOKBACK_MIN = 60

# Kohteet. `slots` = None -> kaikki tiedoston cronit; lista -> vain nama
# (osajoukon on oltava tiedoston croneja; testi tarkistaa).
# Sisältö siirretty sellaisenaan goaliq-appin versiosta 25.9 (sama päätös,
# sama TARGETS/EXCEPTIONS-jako) — ei uudelleenarvioitu tässä.
TARGETS: list[dict] = [
    {"workflow": "fpl-transfer-watch.yml", "slots": None},
    {"workflow": "ucl-refresh.yml", "slots": None},
    {"workflow": "accuracy-log.yml", "slots": None},
    # Vain 3 h -slotti: 09:15- ja :40-slotit ovat guardattuja
    # `github.event.schedule`-arvolla, joka on tyhjä dispatch-ajossa ->
    # dispatch tekisi täysrefreshin guardatun snapshotin sijaan. Guardattujen
    # slottien relay vaatii tähän workflow'hun workflow_dispatch-inputin
    # `slot` (ei rakennettu; sama rajaus kuin goaliq-appin versiossa).
    {"workflow": "fpl-data-refresh.yml", "slots": ["0 */3 * * *"]},
    {"workflow": "env-health-watch.yml", "slots": None},
]

# Tämän repon cron-workflow't joita relay EI laukaise. Jokaisella perustelu;
# uusi cron-workflow tässä repossa kaataa testin kunnes se on jommassakummassa.
EXCEPTIONS: dict[str, str] = {
    "fp-dispatch-relay.yml": "relay ei laukaise itseaan: oma schedule-triggerinsa riittaa, "
                             "ja itsensa dispatchaaminen loisi loputtoman silmukan",
    "render-daily-deploy.yml": "tuotanto-deploy Renderiin = GO-REQUIRED; relay ei saa "
                               "laukaista deployta (CLAUDE.md turvaportti)",
    "wc-knockout-refresh.yml": "kertaluontoinen cron 28.6. (MM-pudotuspelit), ohi",
    "model-squad-grade.yml": "toteuma 86 % (3.9 mittaus), ei S14-signaalia",
    "affiliate-attrib-watch.yml": "viikoittainen, ei S14-signaalia; issue-vahti sietaa viiveen",
    "fpl-page-refresh.yml": "paivittainen, ei S14-signaalia",
    "fpl-why-refresh.yml": "paivittainen, ei S14-signaalia",
    "free-window-watch.yml": "paivittainen, ei S14-signaalia",
}


# ------------------------------------------------------------- gh-kutsut
def gh(*args: str) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} -> {p.returncode}: {p.stderr.strip()}")
    return p.stdout


def read_workflow_yaml(workflow: str) -> str:
    """Sama checkout, sama commit -> paikallinen tiedosto, ei API-kutsua."""
    p = WORKFLOW_DIR / workflow
    return p.read_text(encoding="utf-8")


def recent_runs(workflow: str, since: datetime, until: datetime) -> list[dict]:
    """Ajot luotu valilla [since, until] (until = relayn now, jotta --now-testaus
    menneella ajalla ei nae tulevia ajoja)."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    out = gh("run", "list", "-w", workflow,
             "--created", f"{since.strftime(fmt)}..{until.strftime(fmt)}",
             "--json", "databaseId,event,status,createdAt", "--limit", "20")
    return json.loads(out or "[]")


def dispatch(workflow: str) -> None:
    gh("workflow", "run", workflow)


# ------------------------------------------------------------- paatos
def has_workflow_dispatch(yaml_text: str) -> bool:
    return any(line.strip().startswith("workflow_dispatch:") for line in yaml_text.splitlines())


def due_since(exprs: list[str], now: datetime, lookback_min: int = LOOKBACK_MIN) -> datetime | None:
    """Aikaisin slotti joka laukesi (now-lookback, now]; None jos ei yhtaan."""
    if not exprs:
        return None
    crons = [parse_cron(e) for e in exprs]
    t = (now - timedelta(minutes=lookback_min)).replace(second=0, microsecond=0) + timedelta(minutes=1)
    while t <= now:
        if any(_matches(c, t) for c in crons):
            return t
        t += timedelta(minutes=1)
    return None


def decide(workflow: str, yaml_text: str, slots: list[str] | None, now: datetime,
           runs_since) -> tuple[str, str]:
    """Palauttaa (action, reason); action in {dispatch, skip}."""
    exprs = cron_exprs(yaml_text)
    if slots is not None:
        missing = [s for s in slots if s not in exprs]
        if missing:
            return "skip", f"slotti {missing} ei ole enaa tiedostossa (cronit: {exprs})"
        exprs = slots
    if not exprs:
        return "skip", "ei cron-riveja tiedostossa"
    if not has_workflow_dispatch(yaml_text):
        return "skip", "ei workflow_dispatch:-triggeria"
    since = due_since(exprs, now)
    if since is None:
        return "skip", f"ei slottia viimeisen {LOOKBACK_MIN} min aikana ({', '.join(exprs)})"
    runs = runs_since(since)
    if runs:
        r = runs[0]
        return "skip", (f"ajo on jo olemassa slotin {since:%H:%M}Z jalkeen: "
                        f"{r.get('event')} {r.get('status')} {r.get('createdAt')} (#{r.get('databaseId')})")
    return "dispatch", f"slotti {since:%H:%M}Z ilman ajoa -> gh workflow run"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", help="ISO-aika testausta varten (oletus: nyt UTC)")
    a = ap.parse_args(argv)
    now = (datetime.fromisoformat(a.now).astimezone(timezone.utc) if a.now
           else datetime.now(timezone.utc))
    if not os.environ.get("GH_TOKEN"):
        print("GH_TOKEN puuttuu: relay ei voi laukaista mitaan.")
        return 2

    dispatched = 0
    for t in TARGETS:
        wf = t["workflow"]
        yaml_text = read_workflow_yaml(wf)
        action, reason = decide(wf, yaml_text, t["slots"], now,
                                lambda since, wf=wf: recent_runs(wf, since, now))
        if action == "dispatch" and not a.dry_run:
            dispatch(wf)
            dispatched += 1
        tag = "DISPATCH" if action == "dispatch" else "skip"
        if a.dry_run and action == "dispatch":
            tag = "DRY-RUN dispatch"
        print(f"[{tag:>16}] {wf}: {reason}")
    print(f"relay {now:%Y-%m-%dT%H:%MZ}: {dispatched} laukaisua, {len(TARGETS)} kohdetta"
          f"{' (dry-run)' if a.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
