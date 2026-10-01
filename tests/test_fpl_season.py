# -*- coding: utf-8 -*-
"""DATAPOHJA-JATKOT kohta 2 (1.10.2026): edellisen kauden arkisto ja kauden
nimi tarkistetaan bootstrapia vasten.

Vika jota tama estaa: `PREV_BASELINES_PATH` on kovakoodattu
`fpl_prev_baselines_2526.json` ja `SEASON_LABEL` "2026/27". Kun FPL kaantyy
kaudelle 2027/28, builder jatkaisi hiljaa ja kortin 'last season' -luvut
olisivat kahden kauden takaa mutta nayttaisivat oikeilta.

Saanto 6a kohta 3: invariantti mitataan joka vaiheessa (esikausi, kesken
kauden, kauden jalkeen, kaantymisen jalkeen), ei vain nykyhetkessa jolloin se
sattuu pitamaan.
"""
import ast
import json
from pathlib import Path

import pytest

from src.models.fpl_season import (
    SeasonMismatch,
    check_season_label,
    load_prev_archive,
    prev_season_key,
    season_label,
)

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_fpl_xp.py"
ARCHIVE = ROOT / "data" / "fpl_prev_baselines_2526.json"


def _boot(gw1_deadline: str, finished_upto: int = 0) -> dict:
    """38 kierrosta viikon valein GW1:sta; `finished_upto` kierrosta pelattu."""
    import datetime as dt
    d0 = dt.datetime.fromisoformat(gw1_deadline.replace("Z", "+00:00"))
    return {"events": [
        {"id": i, "deadline_time": (d0 + dt.timedelta(days=7 * (i - 1))).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "finished": i <= finished_upto}
        for i in range(1, 39)]}


# Kauden 26/27 kaikki vaiheet: esikausi, kesken (myos tammikuussa), lopussa.
KAUSI_2627 = {
    "esikausi": _boot("2026-08-21T17:30:00Z", 0),
    "kesken_syksy": _boot("2026-08-21T17:30:00Z", 5),
    "kesken_tammikuu": _boot("2026-08-21T17:30:00Z", 22),
    "kausi_paattynyt": _boot("2026-08-21T17:30:00Z", 38),
}
KAANTYNYT_2728 = _boot("2027-08-20T17:30:00Z", 0)


@pytest.mark.parametrize("vaihe", sorted(KAUSI_2627))
def test_kausi_paatellaan_samaksi_joka_vaiheessa(vaihe):
    b = KAUSI_2627[vaihe]
    assert season_label(b) == "2026/27"
    assert prev_season_key(b) == "2526"


def test_tammikuun_kalenterivuosi_ei_vaihda_kautta():
    """Negatiivinen kontrolli: kalenterivuodesta paatelty kausi olisi 2027/28
    tammikuussa. Bootstrapin GW1 ratkaisee, ei nykyhetki."""
    b = {"events": [{"id": 1, "deadline_time": "2026-08-21T17:30:00Z"},
                    {"id": 22, "deadline_time": "2027-01-16T11:00:00Z"}]}
    assert season_label(b) == "2026/27"


def test_kaantymisen_jalkeen_vanha_arkisto_kaataa_ajon(tmp_path):
    p = tmp_path / "fpl_prev_baselines_2526.json"
    p.write_text(json.dumps({"meta": {"season_key": "2526"}, "players": {"1": {}}}), encoding="utf-8")
    assert prev_season_key(KAANTYNYT_2728) == "2627"
    with pytest.raises(SeasonMismatch, match="2627"):
        load_prev_archive(p, KAANTYNYT_2728)
    with pytest.raises(SeasonMismatch, match="2027/28"):
        check_season_label("2026/27", KAANTYNYT_2728)


@pytest.mark.parametrize("vaihe", sorted(KAUSI_2627))
def test_oikea_arkisto_kelpaa_joka_vaiheessa(tmp_path, vaihe):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"meta": {"season_key": "2526"}, "players": {"7": {"x": 1}}}), encoding="utf-8")
    assert load_prev_archive(p, KAUSI_2627[vaihe])["players"] == {"7": {"x": 1}}
    check_season_label("2026/27", KAUSI_2627[vaihe])


def test_arkisto_ilman_kausiavainta_ei_kelpaa(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"meta": {}, "players": {"7": {}}}), encoding="utf-8")
    with pytest.raises(SeasonMismatch):
        load_prev_archive(p, KAUSI_2627["kesken_syksy"])


def test_puuttuva_arkisto_on_tyhja_kuten_ennen(tmp_path):
    assert load_prev_archive(tmp_path / "ei_ole.json", KAUSI_2627["esikausi"]) == {
        "players": {}, "meta": {}}


def test_committoitu_arkisto_on_nykykauden_edellinen():
    """Repon oikea tiedosto: jos joku vaihtaa sen, tama kertoo heti."""
    arch = load_prev_archive(ARCHIVE, KAUSI_2627["kesken_syksy"])
    assert arch["meta"]["season_key"] == "2526"
    assert len(arch["players"]) > 500


def _main_src() -> str:
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    return ast.get_source_segment(BUILDER.read_text(encoding="utf-8"), fn)


def test_builder_lukee_arkiston_tarkistavan_lukijan_kautta():
    """Kutsupaikka: funktiotesti pysyy vihreana jos builder palaa lukemaan
    tiedostoa suoraan. Raaka luku on kielletty koko tiedostossa."""
    src = _main_src()
    assert "load_prev_archive(PREV_BASELINES_PATH, boot)" in src
    assert "check_season_label(SEASON_LABEL, boot)" in src
    assert "PREV_BASELINES_PATH.read_text" not in BUILDER.read_text(encoding="utf-8")
    # Tarkistus ennen kuin arkistoa kaytetaan mihinkaan.
    assert src.index("load_prev_archive(") < src.index("prev_by_code")
