# -*- coding: utf-8 -*-
"""hub-deployn domain-verifiointi lukee tickerin samalla kuviolla jolla
generaattori sen kirjoittaa (27.9.2026).

TAUSTA: TRACK-RECORD-NIMIKKEET muutti tickerin muotoon
"<b>609 completed matches, all competitions</b>". Verifiointiaskel etsi
`<b>[0-9]+ completed matches</b>`, EXPECT jai tyhjaksi ja `set -o pipefail`
kaatoi askeleen (ajo 36327766705), vaikka goaliq.app tarjoili uuden sisallon.
Vahti ja generaattori olivat eri mielta tekstista, eika kumpikaan testi
mitannut niita yhdessa.

Portti ajaa workflow'n OMAN kuvion (luettu YAMLista, ei kopioitu tanne)
repon index.html:aa vasten: kahden ticker-kopion on osuttava.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "hub-deploy.yml"


def _verify_run() -> str:
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    for job in doc["jobs"].values():
        for step in job.get("steps") or []:
            if step.get("name") == "Verifioi domainilta":
                return step["run"]
    raise AssertionError("hub-deploy: 'Verifioi domainilta' -askel puuttuu")


def _kuviot(run: str) -> list[str]:
    return re.findall(r"grep -oE '([^']+)'", run)


def test_verifiointi_kuvio_osuu_generoituun_tickeriin():
    kuviot = _kuviot(_verify_run())
    assert len(kuviot) == 2, f"odotettiin EXPECT + LIVE -kuvio: {kuviot}"
    assert kuviot[0] == kuviot[1], "EXPECT ja LIVE lukevat eri kuviolla"
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    # grep -E on POSIX ERE; tama kuvio on myos Pythonin regex.
    osumat = re.findall(kuviot[0], html)
    assert len(osumat) >= 2, (
        f"kuvio {kuviot[0]!r} ei loyda tickeria index.html:sta ({osumat}); "
        "hub-deployn verifiointi kaatuisi tyhjaan EXPECTiin")


def test_kontrolli_vanha_tiukka_kuvio_ei_osu_nykyiseen_tickeriin():
    """Negatiivinen kontrolli: todistaa etta portti erottaa kuviot. Jos
    ticker palaa vanhaan muotoon, tama kaatuu ja kertoo etta kontrolli on
    vanhentunut (ei hiljaa vihrea)."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert not re.findall(r"<b>[0-9]+ completed matches</b>", html)
