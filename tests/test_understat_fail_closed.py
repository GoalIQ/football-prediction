"""Julkinen PL-malli ei saa syntya varalahteen datasta (22.10.2026).

MITATTU 22.10 15:41 (fpl-data-refresh 39807234706): tls_requestsin kirjastolataus kaatui GitHubin API-rajaan,
Understat-haku putosi football-data.co.uk:hon, jonka nimet ("Man City", "Man United", "Newcastle",
"Nott'm Forest") eivat kohdanneet FPL-nimikarttaa. phase0 luki neljä vakiintunutta seuraa nousijoiksi, antoi
niille nousijan voiman, sanity-portti meni lapi (nousijalista oli siella "vain lokiin") ja goaliq.app/fpl
naytti 60 ottelun vaaran CS%:n (Villa v City 16 % -> 36 %). Datacommitit ovat [skip ci], joten
tests/test_cs_source_parity.py ei ajanut ennen kuin seuraava PR toi sen esiin.

Portit (saanto 6a):
1. YKSI LUKIJA: phase0.fit_model (jota myos xP ja cs_fdr kayttavat) ja edellisen kauden joukkueiden lataus
   kulkevat vaadi_understatin lapi. Kutsupaikat mitataan kutsumalla niita, ei lahdetekstista.
2. POIKKEUKSETON KURI: jokainen scripts/build_fpl_*.py, joka lataa PL-otteludataa, vaatii Understatin.
3. NIMIRISTIRIITA: add_promoted_baseline kieltaytyy, jos "nousija" on fitissa toisella nimella.
4. JUURISYY: fpl-data-refresh hakee TLS-kirjaston tunnistautuneena ennen rakentajia.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.data import loader
from src.data.loader import vaadi_understat
from src.models.promoted_baseline import add_promoted_baseline

ROOT = Path(__file__).resolve().parents[1]


def _df(lahteet):
    return pd.DataFrame({"home_team": ["Arsenal"] * len(lahteet), "away_team": ["Everton"] * len(lahteet),
                         "home_score": [1] * len(lahteet), "away_score": [0] * len(lahteet), "lahde": lahteet})


def test_vaadi_understat_paastaa_vain_kokonaan_understatin():
    assert len(vaadi_understat(_df(["Understat", "Understat"]), "testi")) == 2
    for huono in (_df(["Understat", None]), _df([None, None]), _df(["FBref"]), _df([])):
        with pytest.raises(SystemExit, match="ei ole kokonaan Understatia"):
            vaadi_understat(huono, "testi")
    with pytest.raises(SystemExit):
        vaadi_understat(_df(["Understat"]).drop(columns="lahde"), "testi")


def _varalahde(*_a, **_k):
    """Tuotannon 22.10 muoto: football-data.co.uk-rivit ilman lahde-arvoa ja lyhyin nimin."""
    return pd.DataFrame({"date": pd.to_datetime(["2026-10-18", "2026-10-19"]),
                         "home_team": ["Man City", "Nott'm Forest"], "away_team": ["Everton", "Newcastle"],
                         "home_score": [2, 1], "away_score": [0, 1], "league": "ENG-Premier League",
                         "season": "2627"})


def test_phase0_fit_kieltaytyy_varalahteen_datasta(monkeypatch):
    from scripts import build_fpl_phase0 as p0
    monkeypatch.setattr(p0, "lataa_otteludata", _varalahde)
    with pytest.raises(SystemExit, match="PL-fitti"):
        p0.fit_model()


def test_cs_fdr_ja_xp_kayttavat_samaa_vartioitua_fittia(monkeypatch):
    from scripts import build_fpl_cs_fdr as cs
    from scripts import build_fpl_phase0 as p0
    from scripts import build_fpl_xp as xp
    assert xp.fit_model is p0.fit_model
    monkeypatch.setattr(p0, "lataa_otteludata", _varalahde)
    with pytest.raises(SystemExit, match="PL-fitti"):
        cs.fit_model()


def test_edellisen_kauden_joukkueet_vaativat_understatin(monkeypatch):
    from scripts import build_fpl_phase0 as p0
    monkeypatch.setattr(loader, "lataa_otteludata", _varalahde)
    with pytest.raises(SystemExit, match="edellisen PL-kauden"):
        p0.context_cfg(["Arsenal", "Man City"], [])


_PL_LATAUS = re.compile(r"(?:lataa_otteludata|_lataa)\(\s*\[\s*\"ENG-Premier League\"")


def test_jokainen_pl_rakentaja_vaatii_understatin():
    puuttuu = []
    for p in sorted((ROOT / "scripts").glob("build_fpl_*.py")):
        rivit = p.read_text(encoding="utf-8").splitlines()
        for i, r in enumerate(rivit):
            if _PL_LATAUS.search(r) and not any("vaadi_understat(" in x for x in rivit[i:i + 4]):
                puuttuu.append(f"{p.name}:{i + 1}")
    assert puuttuu == [], f"PL-otteludata ilman vaadi_understatia: {puuttuu}"


def test_tunnistin_loytaa_pl_latauksen():
    assert _PL_LATAUS.search('    m = lataa_otteludata(["ENG-Premier League"], [season])')
    assert _PL_LATAUS.search('    prev = _lataa(["ENG-Premier League"], [prev_key])')
    assert not _PL_LATAUS.search('    ("ENG-Premier League", "Premier League"),')


def _dc(*joukkueet):
    return SimpleNamespace(attack={t: 0.1 for t in joukkueet}, defence={t: -0.1 for t in joukkueet},
                           home_advantage_per_team={t: 0.2 for t in joukkueet})


def test_nousija_toisella_nimella_fitissa_on_virhe():
    with pytest.raises(ValueError, match="toisella nimella"):
        add_promoted_baseline(_dc("Man City", "Arsenal"), ["Manchester City"])
    with pytest.raises(ValueError, match="Man United"):
        add_promoted_baseline(_dc("Man United", "Arsenal"), ["Manchester United"])
    dc = _dc("Manchester City", "Arsenal")
    assert add_promoted_baseline(dc, ["Coventry"])["applied_to"] == ["Coventry"]


def test_tyonkulku_hakee_tls_kirjaston_ennen_rakentajia():
    wf = (ROOT / ".github/workflows/fpl-data-refresh.yml").read_text(encoding="utf-8")
    assert "run: bash scripts/ci_tls_library.sh" in wf
    i = wf.index("run: bash scripts/ci_tls_library.sh")
    assert i < wf.index("python -m scripts.build_fpl_phase0") < wf.index("python -m scripts.build_fpl_xp")
    assert "GH_TOKEN: ${{ github.token }}" in wf[wf.rindex("- name:", 0, i):i]


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash puuttuu")
def test_tls_skripti_on_kelvollista_bashia():
    r = subprocess.run(["bash", "-n", str(ROOT / "scripts/ci_tls_library.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    sisalto = (ROOT / "scripts/ci_tls_library.sh").read_text(encoding="utf-8")
    assert "TLS_LIBRARY_PATH=" in sisalto and "tls-client-linux-ubuntu-amd64-" in sisalto
