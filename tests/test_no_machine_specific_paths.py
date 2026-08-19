"""Portti: koodissa ei saa olla konekohtaisia absoluuttisia polkuja.

MIKSI (19.8.2026). `scripts/squad_signals_watch.py` sisalsi rivin

    HUB_WATCH_DIR = Path(r"C:\\Users\\vvsaa\\Documents\\goaliq-app\\cos-reports\\watch")
    HUB_ROOT = HUB_WATCH_DIR.parents[1]

Windows-absoluuttinen polku on Linuxilla YKSI suhteellinen segmentti, joten
`.parents[1]` nosti `IndexError`in heti importissa. Moduuli tuodaan testeissa,
joten koko `tests`-workflow oli punaisena viisi ajoa perakkain 14.8 lahtien.
Se ei nakynyt lokaalisti lainkaan: Windowsilla rivi toimii.

Portti kattaa myos POSIX-kotipolut (/home/..., /Users/...), koska sama vika
toiseen suuntaan kaataisi ajon Villen koneella.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KANSIOT = ("scripts", "src", "api")

# Aja-drive ("C:\\...") tai konekohtainen kotipolku. Rajattu merkkijonoihin:
# kommentissa oleva polku on dokumentaatiota, ei suoritettavaa koodia.
KIELLETYT = re.compile(
    r"""["'](?:[A-Za-z]:[\\/]|/home/|/Users/)[^"']*["']"""
)


def _lahdetiedostot() -> list[Path]:
    out: list[Path] = []
    for kansio in KANSIOT:
        out += sorted((ROOT / kansio).rglob("*.py"))
    return [p for p in out if "__pycache__" not in p.parts]


@pytest.mark.parametrize("polku", _lahdetiedostot(), ids=lambda p: p.name)
def test_ei_konekohtaisia_absoluuttisia_polkuja(polku: Path):
    osumat = []
    for i, rivi in enumerate(polku.read_text(encoding="utf-8").splitlines(), 1):
        koodi = rivi.split("#", 1)[0]
        if KIELLETYT.search(koodi):
            osumat.append(f"{polku.name}:{i}: {rivi.strip()[:100]}")
    assert not osumat, (
        "konekohtainen absoluuttinen polku koodissa (kaatuu toisella "
        "kayttojarjestelmalla):\n  " + "\n  ".join(osumat))


def test_squad_signals_watch_tuonti_ei_kaadu():
    """Tama tuonti oli se joka kaatui — pidetaan se nimeltä testeissa."""
    from scripts import squad_signals_watch as w
    assert w.HUB_WATCH_DIR.name == "watch"
    assert w.HUB_WATCH_DIR.parent.name == "cos-reports"
    assert w.HUB_ROOT == w.HUB_WATCH_DIR.parent.parent


def test_hub_polku_on_ylikirjoitettavissa(monkeypatch, tmp_path):
    """CI:lla ja toisella koneella polku ei ole Villen kotihakemistossa."""
    import importlib

    from scripts import squad_signals_watch as w
    monkeypatch.setenv("GOALIQ_HUB_DIR", str(tmp_path / "hub"))
    importlib.reload(w)
    assert w.HUB_ROOT == tmp_path / "hub"
    assert w.HUB_WATCH_DIR == tmp_path / "hub" / "cos-reports" / "watch"
    monkeypatch.delenv("GOALIQ_HUB_DIR", raising=False)
    importlib.reload(w)
