"""Automergen työkalut: riskiluokka, testivertailu ja ehdokkaiden esisuodatus (18.10.2026, kohta 3).

Automerge nojaa kolmeen päätökseen, joista jokainen voisi hiljaa päästää läpi väärän muutoksen:
  * riskiluokka.py: vain backlog, benchmark, skeeman tilannekuva ja UUDET testitiedostot ovat
    sisäisiä. Olemassa olevan testin muutos, conftest, poisto, lukitus tai skip on aina ihmisen asia.
  * testivertailu.py: mainin ennestään punaiset eivät estä, PR:n tuomat estävät, ja tyhjä tai
    rikkinäinen junit on virhe, ei vihreä.
  * automerge.py: vain työnkulun avaamat auto/- ja aallonharja/-PR:t, veto- ja punainen-label kunnioitetaan.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

JUURI = Path(__file__).resolve().parent.parent
KANSIO = JUURI / ".github" / "auto-kehitys"


def _lataa(nimi):
    spec = importlib.util.spec_from_file_location(f"auto_{nimi}", KANSIO / f"{nimi}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


rl = _lataa("riskiluokka")
tv = _lataa("testivertailu")
am = _lataa("automerge")


@pytest.mark.parametrize("profiili,muutokset", [
    ("aallonharja", [("M", "docs/BENCHMARK.md"), ("M", "docs/AUTO-BACKLOG.md"), ("M", "data/fpl_schema_snapshot.json")]),
    ("kehitys", [("M", "docs/AUTO-BACKLOG.md"), ("A", "tests/test_uusi_vartija.py")]),
])
def test_sisaiset(profiili, muutokset):
    assert rl.luokittele(profiili, muutokset, {})[0] == "sisainen"


@pytest.mark.parametrize("profiili,muutokset", [
    ("kehitys", [("M", "tests/test_olemassa.py")]),
    ("kehitys", [("D", "tests/test_vartija.py")]),
    ("kehitys", [("A", "tests/conftest.py")]),
    ("kehitys", [("M", "src/models/fpl_xp.py")]),
    ("kehitys", [("M", "docs/AUTO-BACKLOG.md"), ("M", "fpl/index.html")]),
    ("kehitys", [("A", "tests/test_auto_kehitys_uusi.py")]),
    ("kehitys", [("M", "docs/BENCHMARK.md")]),
    ("aallonharja", [("A", "tests/test_x.py")]),
    ("aallonharja", [("M", "docs/TUOTEPERIAATTEET.md")]),
    ("kehitys", []),
    ("tuntematon", [("M", "docs/AUTO-BACKLOG.md")]),
])
def test_go(profiili, muutokset):
    assert rl.luokittele(profiili, muutokset, {})[0] == "go"


@pytest.mark.parametrize("rivi", ["      Pisteet: (lukittu) arvo 3/3", "pytestmark = pytest.mark.skip", "    pytest.skip('x')"])
def test_lisatty_rivi_tekee_goksi(rivi):
    assert rl.luokittele("kehitys", [("A", "tests/test_x.py")], {"tests/test_x.py": [rivi]})[0] == "go"


def _junit(tmp_path, nimi, tapaukset):
    rivit = ['<testsuites><testsuite>']
    for c, n, tila in tapaukset:
        sisalto = {"ok": "", "fail": "<failure/>", "error": "<error/>"}[tila]
        rivit.append(f'<testcase classname="{c}" name="{n}">{sisalto}</testcase>')
    rivit.append("</testsuite></testsuites>")
    p = tmp_path / nimi
    p.write_text("".join(rivit), encoding="utf-8")
    return str(p)


def test_vain_pr_n_tuomat_punaiset_estavat(tmp_path):
    pr = _junit(tmp_path, "pr.xml", [("tests.test_a", "t1", "fail"), ("tests.test_b.TestX", "t2", "error"),
                                     ("tests.test_c", "t3", "ok")])
    main_sama = _junit(tmp_path, "m1.xml", [("tests.test_a", "t1", "fail"), ("tests.test_b.TestX", "t2", "error")])
    main_vihrea = _junit(tmp_path, "m2.xml", [("tests.test_a", "t1", "fail"), ("tests.test_b.TestX", "t2", "ok")])
    assert tv.main(["vertaa", "--pr", pr, "--main", main_sama]) == 0
    assert tv.main(["vertaa", "--pr", pr, "--main", main_vihrea]) == 1
    assert tv.main(["vertaa", "--pr", pr]) == 1, "ilman mainin vertailua jokainen punainen on uusi"


def test_tyhja_tai_rikki_junit_ei_ole_vihrea(tmp_path):
    tyhja = _junit(tmp_path, "t.xml", [])
    assert tv.main(["vertaa", "--pr", tyhja]) == 1
    rikki = tmp_path / "r.xml"
    rikki.write_text("<testsuite", encoding="utf-8")
    assert tv.main(["vertaa", "--pr", str(rikki)]) == 1
    assert tv.main(["vertaa", "--pr", str(tmp_path / "puuttuu.xml")]) == 1


def test_tiedostoksi():
    assert tv.tiedostoksi("tests.test_a") == "tests/test_a.py"
    assert tv.tiedostoksi("tests.test_b.TestX") == "tests/test_b.py"
    assert tv.tiedostoksi("joku") == ""


def _pr(**kw):
    pohja = {"number": 5, "headRefName": "aallonharja/2026-10-25", "headRefOid": "abc",
             "author": {"login": "app/github-actions"}, "labels": [], "isDraft": False}
    return {**pohja, **kw}


def test_esisuodatus():
    assert am.esisuodata(_pr()) is None
    assert am.esisuodata(_pr(headRefName="feat/x"))
    assert am.esisuodata(_pr(author={"login": "Veikkoville"}))
    assert am.esisuodata(_pr(isDraft=True))
    assert am.esisuodata(_pr(labels=[{"name": "ei-automergea"}]))
    assert am.esisuodata(_pr(labels=[{"name": "automerge-punainen"}]))


# ------------------------------------------------------------------ työnkulku (Villen päätös 18.10)

import yaml  # noqa: E402

WF = JUURI / ".github" / "workflows"


def _am():
    teksti = (WF / "auto-merge.yml").read_text(encoding="utf-8")
    return teksti, yaml.safe_load(teksti)


def _runit(job):
    return "\n".join(str(s.get("run", "")) for s in job.get("steps", []))


def test_pr_koodia_ajetaan_vain_lukuoikeuksin():
    """testaa ja jalkitesti ajavat PR:n koodia (pytest): ei kirjoitusoikeutta, ei tunnuksia gitissä."""
    _, doc = _am()
    for nimi in ("luokittele", "testaa", "jalkitesti"):
        job = doc["jobs"][nimi]
        assert all(v in ("read", "none") for v in job["permissions"].values()), nimi
        for s in job["steps"]:
            if str(s.get("uses", "")).startswith("actions/checkout"):
                assert s["with"]["persist-credentials"] is False, nimi
    for nimi in ("mergea", "peru"):
        assert "pytest" not in _runit(doc["jobs"][nimi]), f"{nimi}: kirjoitusoikeudella ei ajeta PR:n koodia"


def test_portit_mainista_ennen_mergea_tyopuuhun():
    _, doc = _am()
    run = _runit(doc["jobs"]["testaa"])
    assert 'git show "origin/main:.github/auto-kehitys/$f"' in run
    assert run.index("git show") < run.index("git merge")
    assert "riskiluokka.py\" --profiili" in run and "guard.py\" --profile" in run


def test_merge_vain_testatusta_commitista_ja_squashina():
    _, doc = _am()
    run = _runit(doc["jobs"]["mergea"])
    merget = [r for r in run.splitlines() if "gh pr merge" in r]
    assert merget and all("--match-head-commit" in r and "--squash" in r for r in merget)
    assert "ok/pr-$n.json" in run, "merge vain, kun testaa-työ kirjoitti vihreän tuloksen"


def test_ainoa_push_mainiin_on_revert():
    teksti, doc = _am()
    for nimi, job in doc["jobs"].items():
        run = _runit(job)
        if "git push" in run:
            assert nimi == "peru" and "git revert" in run, nimi
    assert "claude-code-action" not in teksti
    assert set(re.findall(r"secrets\.([A-Za-z0-9_]+)", teksti)) <= {"GITHUB_TOKEN"}


def test_veto_ja_punainen_kunnioitetaan():
    assert am.VETO == "ei-automergea" and am.PUNAINEN == "automerge-punainen"
    run = _runit(_am()[1]["jobs"]["luokittele"])
    assert "automerge.py luokittele" in run


def test_aallonharja_ja_auto_kehitys_kaynnistavat_automergen():
    for nimi in ("aallonharja.yml", "auto-kehitys.yml"):
        doc = yaml.safe_load((WF / nimi).read_text(encoding="utf-8"))
        run = _runit(doc["jobs"]["julkaise"])
        assert "gh workflow run auto-merge.yml" in run, nimi
        assert run.index("gh pr create") < run.index("gh workflow run auto-merge.yml"), nimi
