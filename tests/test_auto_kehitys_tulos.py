"""Vihreä agenttiajo ilman tulosta on punainen (18.10.2026, Villen GO, automaatiokohta 5).

Viikossa kaksi hiljaista nollaa: Bluesky-aivot vihreänä ilman jonoa (17.10) ja auto-kehitys vihreänä
ilman haaraa. Autopilotin S1 lukee vain ajon värin, joten vihreä nolla oli näkymätön. Tämä portti
kaatuu, jos
  * tulos.py hyväksyy puuttuvan tuotoksen tai liian lyhyen ohitussyyn, tai
  * jonkin työnkulun Claude-askeleen jälkeen samassa työssä ei ajeta tulosporttia (uusi Claude-
    työnkulku ei pääse läpi unohtamalla sitä; poikkeus vaatii perustelun TULOSPORTIN_VASTINEET-listaan).
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

JUURI = Path(__file__).resolve().parent.parent
WF = JUURI / ".github" / "workflows"
spec = importlib.util.spec_from_file_location("auto_tulos", JUURI / ".github" / "auto-kehitys" / "tulos.py")
tulos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tulos)

# Askeleet, jotka tekevät saman kuin tulos.py omalla tavallaan. Perustelu pakollinen.
TULOSPORTIN_VASTINEET = {
    "python -m scripts.bsky_bot brain-trace": "18.10: puuttuva queue.json on punainen ja loki kertoo "
                                              "työkalujen nimet ilman sisältöä (tests/test_bsky_bot.py)",
}


def test_tiedosto_ja_vaadittu_rivi(tmp_path):
    f = tmp_path / "v.md"
    assert tulos.tiedoston_tulos(str(f), None) is None
    f.write_text("   \n", encoding="utf-8")
    assert tulos.tiedoston_tulos(str(f), None) is None
    f.write_text("jotain\nVERDIKTI: BLOKATTU\n", encoding="utf-8")
    assert tulos.tiedoston_tulos(str(f), r"^VERDIKTI: (JULKAISTAVISSA|BLOKATTU)")
    assert tulos.tiedoston_tulos(str(f), r"^VERDIKTI: JULKAISTAVISSA") is None


def test_ohitus_vaatii_syyn(tmp_path):
    f = tmp_path / "o.txt"
    assert tulos.ohituksen_syy(str(f)) is None
    f.write_text("ei", encoding="utf-8")
    assert tulos.ohituksen_syy(str(f)) is None
    f.write_text("Kaikki avoimet rivit ovat varattuja kahdelle avoimelle PR:lle.", encoding="utf-8")
    assert tulos.ohituksen_syy(str(f))


def test_paatos():
    assert tulos.paata("haara auto/x (1 committia)", None)[0] == 0
    assert tulos.paata(None, "kaikki rivit varattuja kahdelle PR:lle")[0] == 0
    assert tulos.paata(None, None)[0] == 1


def test_haara_vaatii_commitin(tmp_path, monkeypatch):
    def git(*a):
        subprocess.run(("git",) + a, cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "a")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.chdir(tmp_path)
    git("checkout", "-q", "-b", "auto/testi")
    assert tulos.haaran_tulos("auto/") is None, "haara ilman committia ei ole tulos"
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "b")
    assert tulos.haaran_tulos("auto/")
    assert tulos.haaran_tulos("aallonharja/") is None


def _claude_tyot():
    for polku in sorted(WF.glob("*.yml")):
        doc = yaml.safe_load(polku.read_text(encoding="utf-8"))
        for jnimi, job in (doc.get("jobs") or {}).items():
            askeleet = job.get("steps") or []
            for i, s in enumerate(askeleet):
                if "claude-code-action" in str(s.get("uses", "")):
                    yield polku.name, jnimi, askeleet, i


@pytest.mark.parametrize("nimi,jnimi,askeleet,i", list(_claude_tyot()),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_jokaisen_claude_askeleen_jalkeen_tulosportti(nimi, jnimi, askeleet, i):
    agentti = askeleet[i]
    jalkeen = askeleet[i + 1:]
    osumat = [s for s in jalkeen
              if "tulos.py" in str(s.get("run", ""))
              or any(k in str(s.get("run", "")) for k in TULOSPORTIN_VASTINEET)]
    assert osumat, f"{nimi}/{jnimi}: Claude-askeleen jälkeen ei ajeta tulosporttia (.github/auto-kehitys/tulos.py)"
    # Portti ajetaan aina, kun agentti ajettiin: sama ehto tai ei ehtoa.
    assert any(s.get("if") in (None, agentti.get("if")) for s in osumat), \
        f"{nimi}/{jnimi}: tulosportin ehto eroaa agenttiaskeleen ehdosta"


def test_tyonkulut_lukevat_tulosportin_talteen_otetusta_kopiosta():
    """Agentti voi muokata työpuuta; portti luetaan RUNNER_TEMPiin ennen agenttia tai mainista."""
    for nimi, jnimi, askeleet, i in _claude_tyot():
        for s in askeleet[i + 1:]:
            run = str(s.get("run", ""))
            if "tulos.py" in run:
                assert "$RUNNER_TEMP/portit/tulos.py" in run, f"{nimi}/{jnimi}: {run[:120]}"
