# -*- coding: utf-8 -*-
"""FP-DISPATCH-RELAY: laukaisee taman repon ajastetut workflow't
`gh workflow run`-kutsulla, koska GitHubin cron laahaa repotasolla
(mitattu 7 vrk 10.9: fpl-transfer-watch 26 %, ucl-refresh 39 %,
fpl-data-refresh 46 %, accuracy-log 59 %).

HISTORIA. Rakennettu 10.9.2026 goaliq-appiin (AUTO-S14) ja siirretty tanne
27.9.2026 (ACTIONS-MINUUTIT-RELAY-FP:HEN): goaliq-app on yksityinen repo, ja
relay ajoi siella ~29 kertaa vuorokaudessa, jokainen ~15 s mutta laskutettuna
taytena minuuttina (~870 min/kk, Veikkoville-tilin suurin kulu). Tassa
julkisessa repossa ajot ovat ilmaisia, ja relay laukaisee kohteet omalla
`GITHUB_TOKEN`illaan (workflow_dispatch-tapahtuma kaynnistaa workflow'n myos
GITHUB_TOKENilla), joten erillista PAT:ia ei tarvita.

LAUKAISIN on Cloudflare-worker `cf-worker/fp-cron-relay` (`50 * * * *`),
koska myos taman workflow'n oma cron laahaa. Oma cron jaa varmistukseksi.

Mekaniikka (ajetaan tunneittain `.github/workflows/fp-dispatch-relay.yml`):
  1. Lue kohde-workflow'n YAML taman repon tyopuusta (ajo on main-haaralla)
     ja poimi cron-rivit. Cronit EI ole kopioitu tanne: yksi lukija
     (kohteen oma tiedosto), joten slotti ei voi eriytya (CLAUDE.md 6a).
  2. Jos jokin slotti laukesi viimeisen LOOKBACK_MIN minuutin aikana, ajo on
     "due". Aikaisin due-slotti on `since`.
  3. Jos kohteella on jo ajo (mika tahansa event) luotu `since`:n jalkeen,
     cron ehti itse -> ei tuplata. Muuten `gh workflow run`.
  4. Kohde ilman `workflow_dispatch:`-triggeria ohitetaan ja lokitetaan.

TARGETS on ainoa kasin yllapidetty lista. Portti
`tests/test_fp_dispatch_relay.py` kaataa, jos repossa on cron-workflow joka
ei ole TARGETS:ssa eika EXCEPTIONS:ssa perusteluineen.

Ajo: GH_TOKEN=<token> python -m scripts.fp_dispatch_relay [--dry-run] [--now ISO]
0 EUR: vain gh CLI + GitHub API julkisessa repossa.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.cron_expr import _matches, cron_exprs, parse_cron

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FP_REPO = os.environ.get("GITHUB_REPOSITORY") or "GoalIQ/football-prediction"
FP_REF = "main"
LOOKBACK_MIN = 60

# Kohteet. `slots` = None -> kaikki tiedoston cronit; lista -> vain nama
# (osajoukon on oltava tiedoston croneja; portti tarkistaa).
TARGETS: list[dict] = [
    {"workflow": "fpl-transfer-watch.yml", "slots": None},
    # ucl-refresh.yml poistettu 3.10.2026 (UCL Fantasy lopetettu, Villen paatos).
    {"workflow": "accuracy-log.yml", "slots": None},
    # Vain 3 h -slotti: 09:15- ja :40-slotit ovat guardattuja
    # `github.event.schedule`-arvolla, joka on tyhja dispatch-ajossa ->
    # dispatch tekisi taysrefreshin guardatun snapshotin sijaan. Guardattujen
    # slottien relay vaatii workflow_dispatch-inputin `slot`.
    {"workflow": "fpl-data-refresh.yml", "slots": ["0 */3 * * *"]},
    # 21.9: ymparistovahti (20.9 pyyhkiytynyt ymparisto antoi Premiumin
    # ilmaiseksi ja katkaisi ostamisen ilman yhtaan virhetta). Vahti on
    # arvokas vain ajallaan: GitHubin cron on laahannut 5-12 h.
    {"workflow": "env-health-watch.yml", "slots": None},
    # 28.9 (AUTO-S14): kolme workflow'ta oli poikkeuksina perusteella "viive
    # ei haittaa". S14 ei tieda sita, ja elite-tick toteutui 2/4 = 50 %
    # ensimmaisena vuorokautenaan. Kaikki kolme paattavat tilasta itse
    # (tick: otos/valinnat/none, grade: gradaa uudelleen, page-refresh:
    # rakentaa sivun), joten myohassa tuleva cron-tupla ei tee mitaan uutta.
    {"workflow": "fpl-elite-tick.yml", "slots": None},
    {"workflow": "model-squad-grade.yml", "slots": None},
    {"workflow": "fpl-page-refresh.yml", "slots": None},
]

# S14-mittarin (goaliq-app scripts/autopilot/cron_realization.py) ikkuna ja
# kynnys: alle S14_MIN_REQUESTED slottia S14_WINDOW_DAYS vuorokaudessa ei
# mitata lainkaan. Pariteetin vartioi goaliq-appin
# scripts/autopilot/tests/test_cron_expr_parity.py.
S14_WINDOW_DAYS = 7
S14_MIN_REQUESTED = 4

# Poikkeuksen sallitut syyt. "Viive ei haittaa" EI ole syy: S14 mittaa
# toteumaa perustelusta riippumatta, ja GitHubin cron laahaa koko repossa,
# joten jokainen mitattava workflow joka jatetaan relayn ulkopuolelle nostaa
# signaalin ennen pitkaa (28.9: fpl-elite-tick 2/4 heti ensimmaisena
# vuorokautena). Mitattava ja uudelleen ajettava workflow kuuluu TARGETS:iin.
EXCEPTION_CATEGORIES: dict[str, str] = {
    "relay": "relay itse",
    "go_required": "laukaisu olisi tuotanto-deploy tai muu GO-REQUIRED",
    "kertaluonteinen": "cron on kertaluonteinen ja ohi",
    "ei_idempotentti": "toinen ajo samasta slotista vaaristaa datan (esim. lisaa rivin sarjaan)",
    "maksullinen": "ajo kutsuu maksullista rajapintaa; tupla-ajo maksaa",
    "alle_s14_kynnyksen": "alle S14_MIN_REQUESTED slottia ikkunassa, S14 ei mittaa (portti laskee)",
}

# Cron-workflow't joita relay EI laukaise: {nimi: (kategoria, perustelu)}.
# Uusi cron-workflow kaataa portin kunnes se on jommassakummassa, ja
# kategorian on oltava EXCEPTION_CATEGORIES:ssa.
EXCEPTIONS: dict[str, tuple[str, str]] = {
    "fp-dispatch-relay.yml": ("relay", "relay itse: sen oma cron on varmistus CF-workerin "
                                       ":50-laukaisulle, ei relayn kohde"),
    "render-daily-deploy.yml": ("go_required", "tuotanto-deploy Renderiin = GO-REQUIRED; relay "
                                               "ei saa laukaista deployta (CLAUDE.md turvaportti)"),
    "wc-knockout-refresh.yml": ("kertaluonteinen", "kertaluontoinen cron 28.6. "
                                                   "(MM-pudotuspelit), ohi"),
    "affiliate-attrib-watch.yml": ("alle_s14_kynnyksen", "viikoittainen (1 slotti / 7 vrk); "
                                                         "issue-vahti sietaa viiveen"),
    "fpl-why-refresh.yml": ("maksullinen", "kutsuu Claude Batches API:a (ANTHROPIC_API_KEY); "
                                           "myohastynyt cron + relay = kaksi maksullista ajoa"),
    "free-window-watch.yml": ("ei_idempotentti", "lisaa rivin free_window_log.jsonl:iin ja "
                                                 "affiliate_cohort_log.jsonl:iin joka ajolla "
                                                 "ilman paivakohtaista tarkistusta; tupla-ajo "
                                                 "tuplaa sarjan rivin"),
}


# ------------------------------------------------------------- gh-kutsut
def gh(*args: str) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} -> {p.returncode}: {p.stderr.strip()}")
    return p.stdout


def read_workflow_yaml(workflow: str, root: Path = WORKFLOWS) -> str:
    """Kohteen YAML tyopuusta. Relay ajaa main-haaralla, joten tyopuu = main."""
    return (root / workflow).read_text(encoding="utf-8")


def recent_runs(workflow: str, since: datetime, until: datetime,
                repo: str = FP_REPO) -> list[dict]:
    """Ajot luotu valilla [since, until] (until = relayn now, jotta --now-testaus
    menneella ajalla ei nae tulevia ajoja)."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    out = gh("run", "list", "-R", repo, "-w", workflow,
             "--created", f"{since.strftime(fmt)}..{until.strftime(fmt)}",
             "--json", "databaseId,event,status,createdAt", "--limit", "20")
    return json.loads(out or "[]")


def dispatch(workflow: str, repo: str = FP_REPO, ref: str = FP_REF) -> None:
    gh("workflow", "run", "-R", repo, workflow, "--ref", ref)


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
        return "skip", "ei workflow_dispatch:-triggeria (kohteen muutos tarvitaan)"
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
        print("GH_TOKEN puuttuu: relay ei voi lukea ajoja eika laukaista kohteita.")
        return 2

    dispatched = 0
    failed: list[str] = []
    for t in TARGETS:
        wf = t["workflow"]
        yaml_text = read_workflow_yaml(wf)
        action, reason = decide(wf, yaml_text, t["slots"], now,
                                lambda since, wf=wf: recent_runs(wf, since, now))
        if action == "dispatch" and not a.dry_run:
            # 3.10.2026: yksi epaonnistuva kohde (esim. disabloitu workflow)
            # ei saa estaa muiden kohteiden laukaisua. Ennen tata RuntimeError
            # katkaisi silmukan ja loput datapaivitykset jaivat laukaisematta.
            try:
                dispatch(wf)
                dispatched += 1
            except RuntimeError as e:
                failed.append(wf)
                action, reason = "failed", f"laukaisu epaonnistui: {e}"
        tag = {"dispatch": "DISPATCH", "failed": "FAILED"}.get(action, "skip")
        if a.dry_run and action == "dispatch":
            tag = "DRY-RUN dispatch"
        print(f"[{tag:>16}] {wf}: {reason}")
    print(f"relay {now:%Y-%m-%dT%H:%MZ}: {dispatched} laukaisua, {len(TARGETS)} kohdetta"
          f"{' (dry-run)' if a.dry_run else ''}")
    if failed:
        print(f"EPAONNISTUI: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
