"""COPY-SYNC-portti: oman XI:n kapteeni on ilmainen, ei Premium-lupaus (2.11.2026).

Tausta: fp #77 (1.11) avasi lukitussa rate-team-vastauksessa oman XI:n
kapteenin ilmaiseksi (api/premium.py RATE_TEAM_FREE_OPEN), ja sovellus nayttaa
sen WP9-OTA:sta alkaen. Silti 2.11 hubin julkiset sivut myivat sita Premiumina
13 kohdassa (index hero + Premium-paneeli + JSON-LD, faq, fpl-upsell, career,
llms.txt). Julkaisutarkistaja loysi kuusi niista vasta, kun ensimmainen
korjauskierros oli ohittanut ne: fraasi katkesi rivinvaihtoon, ja grep katsoi
vain yhta rivia. SPA:n portti (paywallBullets.gate.test.ts) ei lue hubia.

Saanto: jokaisen "captain pick for your squad/XI" -maininnan on oltava
ilmaislistan muodossa ("... and the captain pick for your ...") ja
Premium-muotoiset lauseet ovat kiellettyja. Haku tehdaan valilyonnit ja
rivinvaihdot normalisoituina.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _public_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html", "llms.txt"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    files = [ROOT / f for f in out if not f.startswith(("web/", "tests/", "node_modules/"))]
    assert len(files) > 5, files  # glob ei saa hiljaa tyhjentya
    return files


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


MENTION = re.compile(r"captain pick for your (?:own )?(?:squad|XI)\b", re.I)
FREE_FORM = re.compile(r"and the $", re.I)
FORBIDDEN = [
    re.compile(r"who to captain", re.I),
    re.compile(r"a captain for your squad", re.I),
    re.compile(r"captain, transfer and chip call", re.I),
    re.compile(r"your own captain", re.I),
]


def offenders(text: str) -> list[str]:
    t = _norm(text)
    bad = []
    for m in MENTION.finditer(t):
        if not FREE_FORM.search(t[max(0, m.start() - 8):m.start()]):
            bad.append(t[max(0, m.start() - 80):m.end() + 20])
    for rx in FORBIDDEN:
        bad += [t[max(0, m.start() - 80):m.end() + 20] for m in rx.finditer(t)]
    return bad


def test_hub_ei_myy_omaa_kapteenia_premiumina():
    viat = {}
    for f in _public_files():
        b = offenders(f.read_text(encoding="utf-8", errors="replace"))
        if b:
            viat[f.relative_to(ROOT).as_posix()] = b
    assert not viat, viat


def test_generaattori_ei_myy_omaa_kapteenia_premiumina():
    """build_fpl_page.py: merkkijonon katkot ("...\\n    ...") yhdistetaan ennen hakua."""
    src = (ROOT / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    joined = re.sub(r'"\s*\n\s*"', "", src)
    assert not offenders(joined)


def test_erotteleva_kontrolli():
    assert offenders("GoalIQ Premium: the weak spot in your XI, the captain\n   pick for your squad, the hold")
    assert offenders("Premium is for your own team at the deadline: who to captain")
    assert not offenders("Free: a rating and the captain\n pick for your squad from rate my team")
