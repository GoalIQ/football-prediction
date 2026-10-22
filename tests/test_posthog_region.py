"""PostHog-projekti 427890 on US Cloudissa (22.10.2026).

EU-alueen osoite hukkaa tapahtumat hiljaa: push_dispatchin oletus oli EU, ja push_sent sekä push_personal jaivat
tallentumatta kaksi kuukautta. Lahdekoodissa ei saa olla EU-osoitetta; uusi palvelinpuolen lahettaja kayttaa
samaa osoitetta kuin mobiili (goaliq-app eas.json) ja web (web/pro-spa/src/lib/config.ts).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("scripts", "src", "api", "web/pro", "web/pro-spa/src", ".github")
SUFFIXES = {".py", ".ts", ".js", ".svelte", ".yml", ".yaml"}
EU = re.compile(r"\beu(?:\.i)?\.posthog\.com", re.I)


def _eu_hits() -> list[str]:
    hits = []
    for d in DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.suffix in SUFFIXES and p.is_file() and "node_modules" not in p.parts:
                for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if EU.search(line):
                        hits.append(f"{p.relative_to(ROOT)}:{n}")
    return hits


def test_lahdekoodissa_ei_eu_posthog_osoitetta():
    assert _eu_hits() == []


def test_tunnistin_loytaa_eu_osoitteen():
    assert EU.search('host = os.environ.get("POSTHOG_HOST", "https://' + 'eu.i.posthog.com")')
    assert EU.search("https://" + "eu.posthog.com/api/projects/1/")
    assert not EU.search("https://us.i.posthog.com")
