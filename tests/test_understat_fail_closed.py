"""Julkinen PL-malli ei saa syntya varalahteen datasta (22.10.2026), eika sekoituksesta (11.11.2026).

MITATTU 22.10 15:41 (fpl-data-refresh 39807234706): tls_requestsin kirjastolataus kaatui GitHubin API-rajaan,
Understat-haku putosi football-data.co.uk:hon, jonka nimet ("Man City", "Man United", "Newcastle",
"Nott'm Forest") eivat kohdanneet FPL-nimikarttaa. phase0 luki neljä vakiintunutta seuraa nousijoiksi, antoi
niille nousijan voiman, sanity-portti meni lapi (nousijalista oli siella "vain lokiin") ja goaliq.app/fpl
naytti 60 ottelun vaaran CS%:n (Villa v City 16 % -> 36 %). Datacommitit ovat [skip ci], joten
tests/test_cs_source_parity.py ei ajanut ennen kuin seuraava PR toi sen esiin.

MITATTU 11.11: understat.com on palauttanut huoltosivun 1.11 ~22 UTC alkaen (ei paluupaivaa). Pelkka Understat-
vaatimus jatti xP:n ja Phase 0:n 1.11:n versioon ja GW11:n projektio jai syntymatta. Nyt koko fit-ikkuna
luetaan YHDESTA hyvaksytysta xG-lahteesta: Understat tai FPL:n oma Opta-xG (src/data/fpl_match_xg).

Portit (saanto 6a):
1. YKSI LUKIJA: phase0.fit_model (jota myos xP ja cs_fdr kayttavat) ja edellisen kauden joukkueiden lataus
   kulkevat lataa_pl_fit_data:n lapi. Kutsupaikat mitataan kutsumalla niita, ei lahdetekstista.
2. POIKKEUKSETON KURI: yksikaan scripts/build_fpl_*.py ei lataa PL-otteludataa ohi lukijan.
3. YKSI LAHDE: football-datan rivit ja kahden lahteen sekoitus kieltaytyvat (vaadi_yksi_xg_lahde).
4. NIMIRISTIRIITA: add_promoted_baseline kieltaytyy, jos "nousija" on fitissa toisella nimella.
5. JUURISYY: fpl-data-refresh hakee TLS-kirjaston tunnistautuneena ennen rakentajia.
6. METATEKSTI kertoo kumpi lahde fitissa oli (team_strength_source, caveat).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.data import fpl_match_xg, loader
from src.data.loader import lataa_pl_fit_data, vaadi_yksi_xg_lahde, xg_lahde_label
from src.models.promoted_baseline import add_promoted_baseline

ROOT = Path(__file__).resolve().parents[1]


def _df(lahteet, xg=1.0):
    n = len(lahteet)
    return pd.DataFrame({"home_team": ["Arsenal"] * n, "away_team": ["Everton"] * n,
                         "home_score": [1] * n, "away_score": [0] * n,
                         "home_xg": [xg] * n, "away_xg": [0.5] * n, "lahde": lahteet})


def test_vaadi_yksi_xg_lahde_paastaa_vain_yhden_hyvaksytyn_lahteen():
    assert vaadi_yksi_xg_lahde(_df(["Understat", "Understat"]), "testi").attrs["xg_lahde"] == "Understat"
    assert vaadi_yksi_xg_lahde(_df(["FPL-Opta"] * 3), "testi").attrs["xg_lahde"] == "FPL-Opta"
    for huono in (_df(["Understat", "FPL-Opta"]), _df(["Understat", None]), _df([None, None]),
                  _df(["FBref"]), _df(["football-data.co.uk"]), _df([])):
        with pytest.raises(SystemExit, match="yhdesta hyvaksytysta xG-lahteesta"):
            vaadi_yksi_xg_lahde(huono, "testi")
    with pytest.raises(SystemExit):
        vaadi_yksi_xg_lahde(_df(["Understat"]).drop(columns="lahde"), "testi")
    with pytest.raises(SystemExit, match="puuttuu xG"):
        vaadi_yksi_xg_lahde(_df(["FPL-Opta"], xg=None), "testi")


def _varalahde(*_a, **_k):
    """Tuotannon 22.10 muoto: football-data.co.uk-rivit ilman lahde-arvoa ja lyhyin nimin."""
    return pd.DataFrame({"date": pd.to_datetime(["2026-10-18", "2026-10-19"]),
                         "home_team": ["Man City", "Nott'm Forest"], "away_team": ["Everton", "Newcastle"],
                         "home_score": [2, 1], "away_score": [0, 1], "league": "ENG-Premier League",
                         "season": "2627"})


def _understat(*_a, **_k):
    d = _df(["Understat", "Understat"])
    d["date"] = pd.to_datetime(["2026-10-18", "2026-10-19"])
    return d


def _fpl_frame(kausi):
    return pd.DataFrame({"date": pd.to_datetime(["2026-10-18"]), "home_team": ["Manchester City"],
                         "away_team": ["Everton"], "home_score": [2], "away_score": [0],
                         "league": "ENG-Premier League", "season": kausi,
                         "home_xg": [2.1], "away_xg": [0.4], "lahde": "FPL-Opta"})


def _ei_fpl_dataa(kausi):
    d = pd.DataFrame(columns=["date", "home_team", "away_team", "home_score", "away_score",
                              "league", "season", "home_xg", "away_xg", "lahde"])
    d.attrs["virhe"] = f"kausi {kausi}: testi"
    return d


def test_understat_kelpaa_sellaisenaan_eika_fpl_dataa_haeta(monkeypatch):
    monkeypatch.setattr(loader, "lataa_otteludata", _understat)
    monkeypatch.setattr(fpl_match_xg, "season_match_frame", lambda k: pytest.fail("FPL-dataa ei saa hakea"))
    df = lataa_pl_fit_data(["2526", "2627"], "PL-fitti")
    assert df.attrs["xg_lahde"] == "Understat" and set(df["lahde"]) == {"Understat"}


def test_varalahteen_riveja_ei_kayteta_vaan_koko_ikkuna_fpl_datasta(monkeypatch):
    monkeypatch.setattr(loader, "lataa_otteludata", _varalahde)
    monkeypatch.setattr(fpl_match_xg, "season_match_frame", _fpl_frame)
    df = lataa_pl_fit_data(["2526", "2627"], "PL-fitti")
    assert df.attrs["xg_lahde"] == "FPL-Opta"
    assert set(df["lahde"]) == {"FPL-Opta"}
    assert set(df["season"]) == {"2526", "2627"}
    # football-datan lyhyet nimet eivat paase fittiin
    assert not ({"Man City", "Nott'm Forest", "Newcastle"} & (set(df.home_team) | set(df.away_team)))


def test_ilman_fpl_dataa_kieltaytyy_eika_sekoita(monkeypatch):
    monkeypatch.setattr(loader, "lataa_otteludata", _varalahde)
    monkeypatch.setattr(fpl_match_xg, "season_match_frame",
                        lambda k: _fpl_frame(k) if k == "2627" else _ei_fpl_dataa(k))
    with pytest.raises(SystemExit, match="PL-fitti.*kausi 2526"):
        lataa_pl_fit_data(["2526", "2627"], "PL-fitti")


def test_phase0_fit_kieltaytyy_kun_kumpikaan_lahde_ei_vastaa(monkeypatch):
    from scripts import build_fpl_phase0 as p0
    monkeypatch.setattr(loader, "lataa_otteludata", _varalahde)
    monkeypatch.setattr(fpl_match_xg, "season_match_frame", _ei_fpl_dataa)
    with pytest.raises(SystemExit, match="PL-fitti"):
        p0.fit_model()


def test_cs_fdr_ja_xp_kayttavat_samaa_vartioitua_fittia(monkeypatch):
    from scripts import build_fpl_cs_fdr as cs
    from scripts import build_fpl_phase0 as p0
    from scripts import build_fpl_xp as xp
    assert xp.fit_model is p0.fit_model
    monkeypatch.setattr(loader, "lataa_otteludata", _varalahde)
    monkeypatch.setattr(fpl_match_xg, "season_match_frame", _ei_fpl_dataa)
    with pytest.raises(SystemExit, match="PL-fitti"):
        cs.fit_model()


def test_edellisen_kauden_joukkueet_kulkevat_lukijan_kautta(monkeypatch):
    from scripts import build_fpl_phase0 as p0
    monkeypatch.setattr(loader, "lataa_otteludata", _varalahde)
    monkeypatch.setattr(fpl_match_xg, "season_match_frame", _ei_fpl_dataa)
    with pytest.raises(SystemExit, match="edellisen PL-kauden"):
        p0.context_cfg(["Arsenal", "Man City"], [])
    # FPL-datalla edellisen kauden joukkueet ovat mallinimia: vakiintunut seura ei ole nousija
    monkeypatch.setattr(fpl_match_xg, "season_match_frame", _fpl_frame)
    _cfg, nousijat = p0.context_cfg(["Man City"], [])
    assert "Manchester City" not in nousijat


_PL_LATAUS = re.compile(r"(?:lataa_otteludata|_lataa)\(\s*\[\s*\"ENG-Premier League\"")


def test_yksikaan_pl_rakentaja_ei_lataa_ohi_lukijan():
    ohi = []
    for p in sorted((ROOT / "scripts").glob("build_fpl_*.py")):
        for i, r in enumerate(p.read_text(encoding="utf-8").splitlines()):
            if _PL_LATAUS.search(r):
                ohi.append(f"{p.name}:{i + 1}")
    assert ohi == [], f"PL-otteludata ohi src/data/loader.lataa_pl_fit_data:n: {ohi}"


def test_tunnistin_loytaa_pl_latauksen():
    assert _PL_LATAUS.search('    m = lataa_otteludata(["ENG-Premier League"], [season])')
    assert _PL_LATAUS.search('    prev = _lataa(["ENG-Premier League"], [prev_key])')
    assert not _PL_LATAUS.search('    ("ENG-Premier League", "Premier League"),')


def test_metateksti_kertoo_lahteen_ja_kausi_luetaan_yha():
    from scripts.build_fpl_cs_fdr import cs_fdr_caveat
    from scripts.build_fpl_page import _strength_window_label
    assert xg_lahde_label("Understat") == "Understat"
    assert xg_lahde_label(None) == "Understat"
    opta = xg_lahde_label("FPL-Opta")
    assert "FPL (Opta)" in opta and "Understat offline" in opta
    assert "FPL (Opta)" in cs_fdr_caveat([], ["2526", "2627"], "FPL-Opta")
    assert "Understat PL" in cs_fdr_caveat([], ["2526", "2627"])
    src = f"GoalIQ Dixon-Coles, {opta} PL ['2526', '2627'] (sama fit-config kuin /api/predict)"
    assert _strength_window_label({"team_strength_source": src}) == "2025/26 and 2026/27"


def test_rakentajien_metateksti_lukee_lahteen_fitista():
    for nimi in ("build_fpl_phase0.py", "build_fpl_xp.py", "build_fpl_cs_fdr.py"):
        s = (ROOT / "scripts" / nimi).read_text(encoding="utf-8")
        assert "Dixon-Coles, Understat PL {seasons}" not in s, f"{nimi}: kovakoodattu lahde"
        assert "xg_lahde_label(getattr(dc, 'xg_lahde', None))" in s, nimi


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
