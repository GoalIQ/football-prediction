# -*- coding: utf-8 -*-
"""BOTIN KAYNNISTAMA CLAUDE-AJO EI KAADU BOTTIESTEESEEN (21.10.2026).

claude-code-action hylkaa ajon, jonka kaynnisti github-actions[bot], ellei
askeleella ole `allowed_bots: 'github-actions'`. Rele (scripts/fp_dispatch_relay.py)
ja `gh workflow run` toisesta workflowsta kaynnistavat ajot GITHUB_TOKENilla,
joten actor on aina botti. Sama vika kahdesti: bsky-aivot 3/3 16.-17.10 ja
auto-kehitys ke 21.10 (fp #11 lisasi sen releeseen ilman rivia, job punainen
ennen mallia, korjauskierros jai tekematta).

Portti ei luettele tiedostoja kasin: botin kaynnistamat workflowt johdetaan
releen TARGETS-listasta ja `gh workflow run <tiedosto>` -kutsuista. Uusi
releen kohde tai uusi dispatch-kutsu kaataa taman, jos rivi puuttuu.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from scripts import fp_dispatch_relay as relay

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
DISPATCH_RE = re.compile(r"gh workflow run ([\w.-]+\.ya?ml)")


def _botin_kaynnistamat() -> set[str]:
    nimet = {t["workflow"] for t in relay.TARGETS}
    lahteet = list(WF.glob("*.yml")) + list((ROOT / "scripts").glob("*.py"))
    for p in lahteet:
        nimet.update(DISPATCH_RE.findall(p.read_text(encoding="utf-8")))
    return nimet


def _claude_askeleet(doc: dict) -> list[dict]:
    return [
        s
        for job in (doc.get("jobs") or {}).values()
        for s in job.get("steps") or []
        if "anthropics/claude-code-action" in str(s.get("uses", ""))
    ]


def _botit(askel: dict) -> list[str]:
    return [b.strip() for b in str((askel.get("with") or {}).get("allowed_bots", "")).split(",") if b.strip()]


def test_botin_kaynnistama_claude_askel_sallii_vain_github_actionsin():
    kaynnistetyt = _botin_kaynnistamat()
    tarkistetut = []
    for p in sorted(WF.glob("*.yml")):
        if p.name not in kaynnistetyt:
            continue
        askeleet = _claude_askeleet(yaml.safe_load(p.read_text(encoding="utf-8")))
        for s in askeleet:
            assert _botit(s) == ["github-actions"], f"{p.name}: {s.get('name')}: allowed_bots={_botit(s)}"
        if askeleet:
            tarkistetut.append(p.name)
    # Ei vihreaa tyhjalla: nama kolme ovat botin kaynnistamia tanaan.
    assert {"auto-kehitys.yml", "bsky-bot.yml", "julkaisutarkistus.yml"} <= set(tarkistetut), tarkistetut


def test_johdettu_joukko_loytaa_releen_ja_dispatch_kutsun():
    kaynnistetyt = _botin_kaynnistamat()
    assert "auto-kehitys.yml" in kaynnistetyt  # releen TARGETS
    assert "julkaisutarkistus.yml" in kaynnistetyt  # auto-kehityksen gh workflow run
    assert "aallonharja.yml" not in kaynnistetyt  # vain oma cron; jos tama muuttuu, ylempi testi kattaa sen
