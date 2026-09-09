# -*- coding: utf-8 -*-
"""Portti: esirakennettu UEFA-malli on sama olio kuin live-fitti, ja se
kelpaa VAIN tuoreena, oikealle kaudelle ja oikealla decaylla.

Tausta 9.9.2026: kylma yhteisfitti kesti Renderilla 161-211 s ja katkaisi
accuracy-login kahdesti (CL jai track recordista). Ks. src/models/uefa_prebuilt.py.

Tuoreusehto mitataan SYNTEETTISILLA aikaleimoilla (CLAUDE.md 6a mek. 3):
tuore, 25 h, 27 h, tulevaisuus - ei nykyhetkesta.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from src.models import uefa_prebuilt as up
from src.models.dixon_coles import DixonColesModel

ROOT = Path(__file__).resolve().parents[1]
CL = "INT-Champions League"
PARI = ["2526", "2627"]
NYT = dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc)


def _dc() -> DixonColesModel:
    return DixonColesModel(
        attack={"Arsenal FC": 0.31, "SSC Napoli": 0.12},
        defence={"Arsenal FC": -0.22, "SSC Napoli": -0.05},
        home_advantage=0.21,
        home_advantage_per_team={"Arsenal FC": 0.0, "SSC Napoli": 0.0},
        rho=-0.05,
        teams_=["Arsenal FC", "SSC Napoli"],
        per_team_home_adv=False,
        model_type_="dc",
    )


def test_kierros_sailyttaa_ennusteen_bittitarkasti(tmp_path):
    p = tmp_path / "m.json"
    alk = _dc()
    up.save(alk, tournament=CL, season_pair=PARI, decay=0.0035, path=p, now=NYT)
    dc, syy = up.load(tournament=CL, season_pair=PARI, decay=0.0035, path=p, now=NYT)
    assert dc is not None, syy
    assert dc.expected_goals("Arsenal FC", "SSC Napoli") == \
        alk.expected_goals("Arsenal FC", "SSC Napoli")
    import numpy as np
    assert np.array_equal(dc.score_matrix("SSC Napoli", "Arsenal FC"),
                          alk.score_matrix("SSC Napoli", "Arsenal FC"))
    assert sorted(dc.teams_) == sorted(alk.teams_)


@pytest.mark.parametrize("tunteja,kelpaa", [(0.5, True), (25.0, True),
                                             (26.5, False), (-2.0, False)])
def test_tuoreus_mitataan_ikana(tmp_path, tunteja, kelpaa):
    """26 h = yksi epaonnistunut vuorokausi sallittu; sen yli fitataan livena."""
    p = tmp_path / "m.json"
    up.save(_dc(), tournament=CL, season_pair=PARI, decay=0.0035, path=p, now=NYT)
    dc, syy = up.load(tournament=CL, season_pair=PARI, decay=0.0035, path=p,
                      now=NYT + dt.timedelta(hours=tunteja))
    assert (dc is not None) is kelpaa, syy


@pytest.mark.parametrize("kwargs,osa", [
    ({"tournament": "INT-Europa League"}, "tournament"),
    ({"season_pair": ["2425", "2526"]}, "season_pair"),
    ({"decay": 0.0065}, "decay"),
])
def test_vaara_avain_ei_kelpaa(tmp_path, kwargs, osa):
    """Kausivaihto tai decayn muutos ei saa palauttaa vanhaa mallia."""
    p = tmp_path / "m.json"
    up.save(_dc(), tournament=CL, season_pair=PARI, decay=0.0035, path=p, now=NYT)
    args = {"tournament": CL, "season_pair": PARI, "decay": 0.0035, **kwargs}
    dc, syy = up.load(path=p, now=NYT, **args)
    assert dc is None and osa in syy, syy


def test_puuttuva_tai_rikki_artefakti_fittaa_livena(tmp_path):
    dc, syy = up.load(tournament=CL, season_pair=PARI, decay=0.0035,
                      path=tmp_path / "ei.json", now=NYT)
    assert dc is None and "ei ole" in syy
    p = tmp_path / "rikki.json"
    p.write_text("{not json", encoding="utf-8")
    dc, syy = up.load(tournament=CL, season_pair=PARI, decay=0.0035, path=p, now=NYT)
    assert dc is None and "ei aukea" in syy
    p.write_text('{"meta": {}, "attack": {}}', encoding="utf-8")
    dc, syy = up.load(tournament=CL, season_pair=PARI, decay=0.0035, path=p, now=NYT)
    assert dc is None


def test_api_kayttaa_esirakennettua_eika_fittaa(monkeypatch):
    """Kun artefakti kelpaa, live-fittia EI kutsuta. Kun se ei kelpaa,
    kutsutaan (mutaatio: fit nostaa poikkeuksen -> nakyy)."""
    import api.main as M
    from src.models import uefa_joint

    valmis = _dc()
    monkeypatch.setattr(up, "load", lambda **kw: (valmis, "testi"))
    out = M._fit_uefa_yhteismalli((CL,), tuple(M._UEFA_SEASONS), 0.0035)
    assert out is valmis

    monkeypatch.setattr(up, "load", lambda **kw: (None, "testi: ei kelpaa"))

    def kaatuu(*a, **k):
        raise RuntimeError("LIVE-FITTI KUTSUTTIIN")
    monkeypatch.setattr(uefa_joint, "fit_uefa_joint", kaatuu)
    monkeypatch.setattr(M, "_lataa_otteludata_cached",
                        lambda *a, **k: __import__("pandas").DataFrame(
                            {"home_team": ["A"], "away_team": ["B"]}))
    with pytest.raises(RuntimeError, match="LIVE-FITTI"):
        M._fit_uefa_yhteismalli((CL,), tuple(M._UEFA_SEASONS), 0.0035)
    # allow_prebuilt=False ohittaa artefaktin vaikka se kelpaisi (bake-skripti)
    monkeypatch.setattr(up, "load", lambda **kw: (valmis, "testi"))
    with pytest.raises(RuntimeError, match="LIVE-FITTI"):
        M._fit_uefa_yhteismalli((CL,), tuple(M._UEFA_SEASONS), 0.0035,
                                allow_prebuilt=False)


def test_bake_kayttaa_samaa_decayta_kuin_api():
    """Artefaktin avain = API:n oletusdecay. Jos _saa_mallin oletus muuttuu,
    bake seuraa automaattisesti eika artefakti jaa hiljaa kelpaamattomaksi."""
    import inspect
    import api.main as M
    assert M.uefa_prebuilt_decay() == \
        inspect.signature(M._saa_malli).parameters["decay"].default


def test_ucl_refresh_committaa_artefaktin_jonka_bake_kirjoittaa():
    """Sama portti kuin test_refresh_commits_what_it_writes, ucl-refreshille:
    levylle kirjoitettu malli joka ei paady git addiin katoaa ajon mukana."""
    wf = (ROOT / ".github" / "workflows" / "ucl-refresh.yml").read_text(encoding="utf-8")
    assert "scripts.build_uefa_model" in wf
    assert re.search(r"git add data/uefa_joint_model\.json", wf), \
        "bake kirjoittaa data/uefa_joint_model.json mutta commit-askel ei lisaa sita"
    assert ".venv" not in wf


def test_artefakti_ei_ole_gitignoressa():
    """9.9: `data/*.json` on ignoressa ja ensimmainen commit-yritys kaatui
    siihen. Ilman poikkeusta ucl-refreshin `git add` kaatuu joka ajossa ja
    artefakti jaa runnerin levylle (muisti gitignored-fix-silent-regression)."""
    import subprocess
    r = subprocess.run(["git", "check-ignore", "-q", "data/uefa_joint_model.json"],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 1, "data/uefa_joint_model.json on gitignoressa"
