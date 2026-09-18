# -*- coding: utf-8 -*-
"""CI-LUKIJAN INVARIANTIT (18.9.2026).

Mita nama vartioivat: `scripts/ci_test_selection.py` vastaa kysymykseen "ajaako CI
taman testin". 17.9 vastasin siihen itse vaarin ("tests.yml on punainen
test_domestic_golden-driftista") ja kuusi valmista haaraa jai pushaamatta
vuorokaudeksi. Lukija on nyt yksi lahde - mutta lukija joka lakkaa lukemasta
markkerivalintaa antaisi saman vaaran vastauksen hiljaa.

Siksi lukijaa EI mitata vain tasta reposta. Tama repo on yksi kohta
avaruudessa: yksi `-m "not slow"` -kutsu ja yksi polkurajattu kutsu. Testit
ajavat lukijan SYNTEETTISILLA workflow-konfiguraatioilla (saanto 6a,
mekanismi 3): `-m "not slow"`, `-m "slow"`, ei markkerivalintaa, polkurajaus,
`--deselect`, `--ignore`, ja moduulitason `pytestmark` vs funktiotason
`@pytest.mark.slow`.

EROTTELEVUUS (muisti: exit-koodi-ei-ole-todiste-mekanismista). Jokaisella
"EI AJA" -testilla on pari joka vaatii "AJAA" samalla konfiguraatiolla.
Ilman paria lukija joka palauttaa aina False olisi vihrea - ja se on
tasmalleen se virhe jota tama estaa.

MUTAATIOT jotka todistettu punaisiksi 18.9:
  1. `-m` pois `_VALUE_OPTS`-listalta ("not slow" -> polkuargumentti)
  2. markkerivalinnan ohitus `_valinta`:ssa (`if o.marker:` -> `if False:`)
  3. polkurajauksen ohitus (`if not any(_sisaltyy(...))` -> `if False`)
  4. moduulitason `pytestmark` jaa lukematta (`_pytestmark` -> `set()`)
  5. `--deselect` jaa lukematta
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import ci_test_selection as lukija  # noqa: E402
from ci_reader_fixtures import (EI_MARKKERIA, FUNKTIOTASO, LUOKKATASO,  # noqa: E402
                                MODUULITASO, MODUULITASO_LISTA, tekorepo,
                                workflow)


def _repo(tmp_path, komento, testit=None, **kw):
    return tekorepo(tmp_path,
                    workflows={"tests.yml": workflow(komento, **kw)},
                    testit=testit or {"tests/test_hidas.py": MODUULITASO,
                                      "tests/test_nopea.py": EI_MARKKERIA})


# ---------------------------------------------------------------------------
# VAIHE: -m "not slow"   (= taman repon nykyinen tests.yml)
# ---------------------------------------------------------------------------

def test_not_slow_sulkee_moduulitason_slown_pois(tmp_path):
    root = _repo(tmp_path, 'pytest -m "not slow" -q')
    v = lukija.ci_runs("tests/test_hidas.py", root)
    assert v.runs is False
    assert "not slow" in " ".join(v.rivit)
    assert "Lokaali punainen EI ole CI-tila" in v.reason


def test_not_slow_ajaa_merkitsemattoman_PARI(tmp_path):
    """EROTTELEVA PARI. Ilman tata lukija joka palauttaa aina False olisi
    vihrea - ja "ei aja" on juuri se vastaus jonka vaarin antaminen maksoi
    17.9 vuorokauden."""
    root = _repo(tmp_path, 'pytest -m "not slow" -q')
    v = lukija.ci_runs("tests/test_nopea.py", root)
    assert v.runs is True
    assert v.workflows == (".github/workflows/tests.yml",)


# ---------------------------------------------------------------------------
# VAIHE: -m "slow"  (kaanteinen valinta)
# ---------------------------------------------------------------------------

def test_slow_valinta_ajaa_slown(tmp_path):
    root = _repo(tmp_path, 'pytest -m "slow" -q')
    assert lukija.ci_runs("tests/test_hidas.py", root).runs is True


def test_slow_valinta_ei_aja_merkitsematonta_PARI(tmp_path):
    root = _repo(tmp_path, 'pytest -m "slow" -q')
    v = lukija.ci_runs("tests/test_nopea.py", root)
    assert v.runs is False


# ---------------------------------------------------------------------------
# VAIHE: ei markkerivalintaa lainkaan
# ---------------------------------------------------------------------------

def test_ilman_markkerivalintaa_slow_AJAA(tmp_path):
    """TAMA on se vaihe jossa slow-markkeri lakkaa suojaamasta. Jos joku
    poistaa `-m "not slow"` tests.yml:sta, lokaalia dataa vaativat testit
    ALKAVAT ajaa CI:ssa ja kaatavat sen. Poikkeuslistan perustelu
    ("ei aja CI:ssa, koska downloaded_files puuttuu") muuttuu silloin
    epatodeksi, ja `test_slow_marker_discipline` kaatuu."""
    root = _repo(tmp_path, "pytest -q")
    assert lukija.ci_runs("tests/test_hidas.py", root).runs is True
    assert lukija.ci_runs("tests/test_nopea.py", root).runs is True


def test_markkerin_arvoa_ei_luulla_poluksi(tmp_path):
    """Jos `-m` ei ole arvon syovien optioiden listalla, "not slow" menee
    polkuargumentiksi ja KAIKKI jaa valitsematta - vastaus olisi "ei aja"
    myos merkitsemattomalle testille. Mutaatio 1."""
    root = _repo(tmp_path, 'pytest -m "not slow" -q')
    o = lukija.parse_pytest_argv(["-m", "not slow", "-q"])
    assert o.marker == "not slow"
    assert o.paths == []
    assert lukija.ci_runs("tests/test_nopea.py", root).runs is True


# ---------------------------------------------------------------------------
# VAIHE: polkurajaus
# ---------------------------------------------------------------------------

def test_polkurajaus_sulkee_tiedoston_pois(tmp_path):
    root = _repo(tmp_path, "pytest tests/test_nopea.py -q")
    v = lukija.ci_runs("tests/test_hidas.py", root)
    assert v.runs is False
    assert "polkurajaus" in " ".join(v.rivit)


def test_polkurajaus_ajaa_nimetyn_PARI(tmp_path):
    root = _repo(tmp_path, "pytest tests/test_nopea.py -q")
    assert lukija.ci_runs("tests/test_nopea.py", root).runs is True


def test_kansiorajaus_kattaa_alihakemiston(tmp_path):
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow("pytest tests/osa -q")},
                    testit={"tests/osa/test_a.py": EI_MARKKERIA,
                            "tests/test_b.py": EI_MARKKERIA})
    assert lukija.ci_runs("tests/osa/test_a.py", root).runs is True
    assert lukija.ci_runs("tests/test_b.py", root).runs is False


def test_ignore_sulkee_pois(tmp_path):
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow(
                        "pytest --ignore=tests/osa -q")},
                    testit={"tests/osa/test_a.py": EI_MARKKERIA,
                            "tests/test_b.py": EI_MARKKERIA})
    assert lukija.ci_runs("tests/osa/test_a.py", root).runs is False
    assert lukija.ci_runs("tests/test_b.py", root).runs is True


# ---------------------------------------------------------------------------
# VAIHE: --deselect yksittaiselle nodeid:lle
# ---------------------------------------------------------------------------

def test_deselect_sulkee_yhden_nodeidin(tmp_path):
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow(
                        "pytest --deselect tests/test_nopea.py::test_a -q")},
                    testit={"tests/test_nopea.py": EI_MARKKERIA})
    poissa = lukija.ci_runs("tests/test_nopea.py::test_a", root)
    mukana = lukija.ci_runs("tests/test_nopea.py::test_b", root)
    assert poissa.runs is False and "--deselect" in " ".join(poissa.rivit)
    assert mukana.runs is True


def test_deselect_ei_kaada_koko_tiedostoa(tmp_path):
    """Tiedosto ajaa OSITTAIN: 1/2 testia. Jos lukija vastaisi tiedoston
    tasolla "ei aja", se olisi sama virhe kuin 17.9 toisin painvastoin."""
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow(
                        "pytest --deselect tests/test_nopea.py::test_a -q")},
                    testit={"tests/test_nopea.py": EI_MARKKERIA})
    v = lukija.ci_runs("tests/test_nopea.py", root)
    assert v.runs is True
    assert "1/2" in v.reason


def test_deselect_inline_muoto(tmp_path):
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow(
                        "pytest --deselect=tests/test_nopea.py::test_a -q")},
                    testit={"tests/test_nopea.py": EI_MARKKERIA})
    assert lukija.ci_runs("tests/test_nopea.py::test_a", root).runs is False


# ---------------------------------------------------------------------------
# VAIHE: markkerin taso (moduuli / luokka / funktio)
# ---------------------------------------------------------------------------

def test_moduulitason_pytestmark_koskee_kaikkia(tmp_path):
    root = _repo(tmp_path, 'pytest -m "not slow" -q',
                 testit={"tests/test_hidas.py": MODUULITASO})
    v = lukija.ci_runs("tests/test_hidas.py", root)
    assert v.runs is False
    assert {i.nodeid for i in v.items} == {"tests/test_hidas.py::test_a",
                                           "tests/test_hidas.py::test_b"}
    assert all("slow" in i.markers for i in v.items)


def test_funktiotason_markkeri_koskee_vain_omaansa(tmp_path):
    """Ero moduulitasoon on juuri se jonka 17.9 vaite ohitti: `test_parlay.py`
    on 9/10 CI:ssa, `test_domestic_golden.py` 0/10."""
    root = _repo(tmp_path, 'pytest -m "not slow" -q',
                 testit={"tests/test_sekava.py": FUNKTIOTASO})
    tiedosto = lukija.ci_runs("tests/test_sekava.py", root)
    assert tiedosto.runs is True and "1/2" in tiedosto.reason
    assert lukija.ci_runs("tests/test_sekava.py::test_hidas", root).runs is False
    assert lukija.ci_runs("tests/test_sekava.py::test_nopea", root).runs is True


def test_pytestmark_lista_luetaan(tmp_path):
    root = _repo(tmp_path, 'pytest -m "not slow" -q',
                 testit={"tests/test_lista.py": MODUULITASO_LISTA})
    v = lukija.ci_runs("tests/test_lista.py", root)
    assert v.runs is False
    assert "slow" in v.items[0].markers and "usefixtures" in v.items[0].markers


def test_luokkatason_pytestmark_luetaan(tmp_path):
    root = _repo(tmp_path, 'pytest -m "not slow" -q',
                 testit={"tests/test_luokka.py": LUOKKATASO})
    assert lukija.ci_runs(
        "tests/test_luokka.py::TestHidas::test_a", root).runs is False
    assert lukija.ci_runs(
        "tests/test_luokka.py::test_moduulin_oma", root).runs is True


# ---------------------------------------------------------------------------
# MARKKERILAUSEKKEEN SEMANTIIKKA
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expr,markers,odotus", [
    ("not slow", {"slow"}, False),
    ("not slow", set(), True),
    ("slow", {"slow"}, True),
    ("slow", {"uvicorn"}, False),
    ("not slow and not uvicorn", {"uvicorn"}, False),
    ("not slow and not uvicorn", {"muu"}, True),
    ("slow or uvicorn", {"uvicorn"}, True),
    ("(slow or uvicorn) and not wc", {"slow", "wc"}, False),
    ("", {"slow"}, True),
])
def test_markkerilauseke(expr, markers, odotus):
    assert lukija.marker_expr_matches(expr, markers) is odotus


def test_tuntematon_markkerinimi_on_epatosi_ei_poikkeus():
    assert lukija.marker_expr_matches("outoa", {"slow"}) is False


def test_jasentymaton_markkerilauseke_nostaa_virheen():
    """Fail-closed: lauseke jota ei ymmarreta ei ole hiljainen True/False."""
    with pytest.raises(ValueError):
        lukija.marker_expr_matches("slow and $$", {"slow"})


# ---------------------------------------------------------------------------
# WORKFLOW'N LUKEMINEN: mika ON pytest-kutsu ja mika ei
# ---------------------------------------------------------------------------

def test_pip_install_pytest_ei_ole_pytest_kutsu(tmp_path):
    """`pip install -r requirements.txt pytest httpx` sisaltaa sanan pytest.
    Jos se laskettaisiin kutsuksi, se nayttaisi ajavan KAIKEN ilman
    markkerivalintaa ja jokainen slow-testi olisi "AJAA"."""
    root = _repo(tmp_path, 'pytest -m "not slow" -q')
    kutsut = lukija.pytest_kutsut(root)
    assert len(kutsut) == 1
    assert kutsut[0].argv == ("-m", "not slow", "-q")


def test_kommentoitu_pytest_rivi_ohitetaan(tmp_path):
    wf = ("name: x\n\non:\n  push:\n    branches: [main]\n\njobs:\n  t:\n"
          "    runs-on: ubuntu-latest\n    steps:\n"
          "      - name: Run\n"
          "        run: |\n"
          "          # aiemmin: pytest -q  (ajoi kaiken, ks. 17.9)\n"
          '          pytest -m "not slow" -q\n')
    root = tekorepo(tmp_path, workflows={"tests.yml": wf},
                    testit={"tests/test_hidas.py": MODUULITASO})
    kutsut = lukija.pytest_kutsut(root)
    assert len(kutsut) == 1 and kutsut[0].argv == ("-m", "not slow", "-q")
    assert lukija.ci_runs("tests/test_hidas.py", root).runs is False


def test_kenoviivajatko_on_yksi_kutsu(tmp_path):
    wf = ("name: x\n\non:\n  schedule:\n    - cron: '0 6 * * *'\n\njobs:\n  t:\n"
          "    runs-on: ubuntu-latest\n    steps:\n"
          "      - name: Gate\n"
          "        run: |\n"
          "          python -m pytest tests/test_a.py tests/test_b.py \\\n"
          "                           tests/test_c.py -q || {\n"
          '            echo "::error::portti punainen"\n'
          "            exit 1\n"
          "          }\n")
    root = tekorepo(tmp_path, workflows={"gate.yml": wf},
                    testit={"tests/test_a.py": EI_MARKKERIA,
                            "tests/test_d.py": EI_MARKKERIA})
    kutsut = lukija.pytest_kutsut(root)
    assert len(kutsut) == 1
    assert kutsut[0].argv == ("tests/test_a.py", "tests/test_b.py",
                              "tests/test_c.py", "-q")
    assert lukija.ci_runs("tests/test_a.py", root).runs is True
    assert lukija.ci_runs("tests/test_d.py", root).runs is False


def test_triggerit_ja_haara_nakyvat(tmp_path):
    root = _repo(tmp_path, 'pytest -m "not slow" -q',
                 triggers="  workflow_dispatch:\n  push:\n    branches: [main]\n"
                          "  pull_request:\n")
    k = lukija.pytest_kutsut(root)[0]
    assert k.triggers == ("workflow_dispatch", "push:main", "pull_request")


def test_schedule_only_workflow_nakyy_triggereissa(tmp_path):
    """Muisti: vain-schedule-ajot-mittarissa. Workflow joka ajaa vain cronilla
    EI ole pushin portti, ja vastauksessa on nakytava kumpi se on."""
    root = _repo(tmp_path, "pytest tests/test_nopea.py -q",
                 triggers="  schedule:\n    - cron: '0 6 * * *'\n")
    k = lukija.pytest_kutsut(root)[0]
    assert k.triggers == ("schedule",)


def test_ilman_workflow_kansiota_ei_kaadu(tmp_path):
    root = tekorepo(tmp_path, workflows={},
                    testit={"tests/test_a.py": EI_MARKKERIA})
    v = lukija.ci_runs("tests/test_a.py", root)
    assert v.runs is False and v.rivit == ()


# ---------------------------------------------------------------------------
# FAIL-CLOSED: epavarma ei ole "ei aja"
# ---------------------------------------------------------------------------

def test_k_valinta_on_epavarma_ei_ei_aja(tmp_path):
    """`-k` valitsee nimen mukaan. Staattinen lukija ei voi paattaa sita, ja
    "en tieda" EI saa nayttaa samalta kuin "ei aja"."""
    root = _repo(tmp_path, 'pytest -k "not golden" -q',
                 testit={"tests/test_hidas.py": MODUULITASO})
    v = lukija.ci_runs("tests/test_hidas.py", root)
    assert v.epavarmat, "-k jai kirjaamatta epavarmaksi"
    assert "-k" in v.epavarmat[0]


def test_jasentymaton_komento_on_epavarma(tmp_path):
    root = _repo(tmp_path, "pytest -m \"not slow -q",
                 testit={"tests/test_hidas.py": MODUULITASO})
    v = lukija.ci_runs("tests/test_hidas.py", root)
    assert v.epavarmat
    assert "ei saatu jasennettya" in v.epavarmat[0]


def test_varma_kutsu_ei_tuota_epavarmoja_PARI(tmp_path):
    """Parikontrolli: jos kaikki olisi aina epavarmaa, ylla olevat testit
    olisivat vihreita ilman etta lukija lukee mitaan."""
    root = _repo(tmp_path, 'pytest -m "not slow" -q')
    assert lukija.ci_runs("tests/test_hidas.py", root).epavarmat == ()


# ---------------------------------------------------------------------------
# ANKKURITAPAUS: tama repo, 17.9:n vaite
# ---------------------------------------------------------------------------

def test_domestic_golden_ei_aja_cissa():
    """17.9:n vaite: "tests.yml on punainen test_domestic_golden-driftista ->
    ESTAA GATEN". Lukija vastaa lahteista: CI ei aja tata testia."""
    v = lukija.ci_runs("tests/test_domestic_golden.py", ROOT)
    assert v.runs is False
    assert "downloaded_files" in Path(
        ROOT / "tests" / "test_domestic_golden.py").read_text(encoding="utf-8")
    assert "ei CI" in v.reason


def test_tests_yml_ajaa_valtaosan_testeista_PARI():
    """EROTTELEVA PARI ankkurille. Lukija joka vastaa aina "ei aja" tekisi
    ylla olevasta testista vihrean."""
    ajaa = [f for f in lukija.all_test_files(ROOT) if lukija.ci_runs(f, ROOT).runs]
    kaikki = lukija.all_test_files(ROOT)
    assert len(ajaa) > 0.8 * len(kaikki), (
        f"vain {len(ajaa)}/{len(kaikki)} testitiedostoa ajaa CI:ssa - "
        "lukija tai tests.yml on rikki")


def test_parlay_ajaa_osittain():
    """Funktiotason slow: tiedosto EI ole poissa CI:sta, vain yksi testi on."""
    v = lukija.ci_runs("tests/test_parlay.py", ROOT)
    assert v.runs is True and "/" in v.reason
    assert lukija.ci_runs(
        "tests/test_parlay.py::test_domestic_and_mixed_parlay", ROOT).runs is False


# ---------------------------------------------------------------------------
# KUTSUPAIKKA: CLI on se pinta jota ihminen ajaa
# ---------------------------------------------------------------------------

def test_cli_tulostaa_ei_aja_ankkurille(capsys):
    """Lukijan korjaus on arvoton jos kutsupaikka ei kayta sita. Tama ajaa
    saman reitin jonka ihminen ajaa (muisti: testi-kutsuu-funktiota-ei-
    kutsupaikkaa)."""
    assert lukija.main(["tests/test_domestic_golden.py",
                        "--root", str(ROOT)]) == 0
    ulos = capsys.readouterr().out
    assert ulos.startswith("EI AJA")
    assert "tests.yml" in ulos
    assert "not slow" in ulos


def test_cli_tulostaa_ajaa_toiselle_PARI(capsys):
    assert lukija.main(["tests/test_parlay.py", "--root", str(ROOT)]) == 0
    assert capsys.readouterr().out.startswith("AJAA")


def test_cli_slow_files_listaa_kaikki(capsys):
    assert lukija.main(["--slow-files", "--root", str(ROOT)]) == 0
    ulos = capsys.readouterr().out
    assert "tests/test_domestic_golden.py" in ulos
    for rel in lukija.marked_items("slow", ROOT):
        assert rel in ulos


# ---------------------------------------------------------------------------
# LUKIJA EI SAA OLLA KERATTAVA TESTI
# ---------------------------------------------------------------------------

def test_lukijan_nimi_ei_osu_pytestin_keruukuvioon():
    """Ensimmainen nimi oli `scripts/ci_runs_test.py`, joka osuu pytestin
    oletuskuvioon `*_test.py`. Tiedosto ei ollut `testpaths`in alla, joten se
    ei kerattynyt - mutta `pytest scripts/` tai `testpaths`in laajennus olisi
    kerannyt sen, ja sen julkiset funktiot `test_items(path, root)` ja
    `test_files(root)` olisivat nayttaneet testeilta joilta puuttuu fixture.
    Portti joka kaatuu vaarasta syysta on huonompi kuin ei porttia."""
    nimi = Path(lukija.__file__).name
    assert not nimi.startswith("test_")
    assert not nimi.endswith("_test.py")


def test_lukijassa_ei_ole_test_alkuisia_julkisia_funktioita():
    """Sama ansa funktiotasolla: `test_`-alkuinen julkinen funktio muuttuu
    kerattavaksi testiksi sina paivana kun tiedosto paatyy keruupolulle."""
    import inspect
    osumat = [n for n, o in vars(lukija).items()
              if n.startswith("test") and inspect.isfunction(o)]
    assert osumat == [], osumat
