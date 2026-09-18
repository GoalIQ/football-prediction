# -*- coding: utf-8 -*-
"""POIKKEUSLISTA: testi joka EI AJA CI:ssa tarvitsee perustelun (18.9.2026).

`pytest.mark.slow` tarkoittaa tassa repossa "CI ei aja tata". Se on
nakymaton paatos: markkeri on yhdella rivilla testitiedostossa, valinta
(`-m "not slow"`) toisessa tiedostossa, ja SYY siihen miksi testi ei voi ajaa
CI:ssa ei ollut missaan koneellisesti. 17.9 se maksoi vuorokauden: kirjasin
jonoriviksi etta "tests.yml on punainen test_domestic_golden-driftista ->
ESTAA GATEN", ja kuusi valmista haaraa jai pushaamatta. Testi ei aja CI:ssa
eika voinut kaataa mitaan; punainen oli LOKAALI, ja syy oli puuttuva
paikallinen resurssi, ei drift.

Tama on saannon 6a mekanismi 2: poikkeuslista jossa on PERUSTELU. Uusi
poikkeus ei paase listalle vahingossa - testi kaatuu ja kirjoittaja joutuu
kirjoittamaan tahan, MIKA paikallinen resurssi CI:sta puuttuu. Unohduksesta
syntyva vika muuttuu mahdottomaksi, tietoinen valinta jaa nakyviin diffiin.

MIKSI LISTA EI OLE "slow-merkityt tiedostot". Se olisi portti joka on yhden
muokkauksen paassa vihreasta vaarasta vastauksesta (muisti: portti-
kirjoitetaan-nahdylle-muodolle): uusi markkeri (`-m "not slow and not
uvicorn"`), uusi `--deselect` tai polkurajaus sulkee testin CI:sta ilman etta
sanaa "slow" esiintyy missaan. Siksi lista johdetaan SULKEUTUMISESTA:
`ci_test_selection.ei_aja_cissa()` kertoo mita yksikaan workflow ei valitse, olkoon
syy mika tahansa.

Ja lista on sidottu lukijaan molempiin suuntiin: jos joku poistaa
`-m "not slow"` tests.yml:sta, slow-testit alkavat ajaa CI:ssa, naiden rivien
perustelu muuttuu epatodeksi ja tama testi kaatuu. Perustelu ei siis ole
kommentti vaan vaite jota mitataan.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import ci_test_selection as lukija  # noqa: E402
from ci_reader_fixtures import (EI_MARKKERIA, FUNKTIOTASO, MODUULITASO,  # noqa: E402
                                tekorepo, workflow)


# ---------------------------------------------------------------------------
# POIKKEUSLISTA. Tiedosto -> MIKA PAIKALLINEN RESURSSI PUUTTUU CI:STA.
#
# Rivi ilman perustelua ei ole perustelu. Kirjoita mika resurssi puuttuu
# (backtickeissa: polku, ymparistomuuttuja tai endpoint) ja mika virhe siita
# seuraa, MITATTUNA - ei arvauksena. "Hidas" ei yksin ole syy olla pois
# CI:sta; syy on se ettei CI:lla ole sita mita testi tarvitsee.
# ---------------------------------------------------------------------------

CI_POIKKEUKSET = {
    "tests/test_domestic_golden.py": (
        "Neljan `-FD`-liigan caset (ESP/GER/ITA/FRA) lataavat "
        "football-data.orgista, joka vaatii joko `FOOTBALL_DATA_API_KEY`:n "
        "(`.env`, gitignorattu) tai levycachen `data/raw/football-data-org/` "
        "(myos gitignorattu). Tuoreessa checkoutissa kumpaakaan ei ole, ja "
        "lataus putoaa FBrefiin joka ei tunne naita liiganimia. MITATTU 18.9 "
        "worktreessa jossa kumpaakaan ei ole: 2 passed / 4 failed, "
        "`HTTP 404 Invalid league 'ESP-La Liga-FD'`. Sama testi on vihrea "
        "paatyopuussa jossa molemmat ovat - eli lokaali punainen ei ole "
        "drift eika CI-tila. Lisaksi golden vaatii 6 domestic-mallin "
        "on-demand-fitin."),
    "tests/test_h2h_penalties.py": (
        "Vain `test_psg_arsenal_cl_final_via_api` on poissa: se hakee "
        "CL-finaalin 30.5.2026 rivin `/api/predict`-vastauksen h2h-listalta, "
        "ja se rivi tulee football-data.orgista samalla "
        "`FOOTBALL_DATA_API_KEY` / `data/raw/football-data-org/` -ehdolla. "
        "MITATTU 18.9 ilman avainta: 'CL-finaali 30.5.2026 puuttuu "
        "h2h-listalta', vaikka UEFA-malli itse latautui esirakennettuna. "
        "Saman tiedoston 9 muuta testia ajavat CI:ssa."),
    "tests/test_parlay.py": (
        "Vain `test_domestic_and_mixed_parlay` on poissa: se pyytaa "
        "`/api/predict`-ennusteen domestic-liigalle, mika laukaisee "
        "on-demand-fitin ulkoisesta FBref-raapimisesta (verkko + minuutteja). "
        "CI:n nopea setti ajaa tarkoituksella vain esirakennetulla "
        "`data/wc_model.json`:lla. MITATTU 18.9: testi on vihrea lokaalisti "
        "verkon kanssa, eli kyse ei ole rikkinaisesta testista vaan "
        "riippuvuudesta jota CI:lle ei anneta. Saman tiedoston 9 muuta "
        "testia ajavat CI:ssa."),
}

MIN_PERUSTELU = 80
# Backtickeissa oleva resurssi: polku, ymparistomuuttuja tai endpoint.
_RESURSSI = re.compile(r"`[^`]*[/._][^`]*`|`[A-Z][A-Z0-9_]{3,}`")


def tarkista(root: Path, poikkeukset: dict) -> list:
    """Poikkeuslistan ja todellisuuden erot. Tyhja lista = kunnossa."""
    ongelmat: list = []
    ulkona = lukija.ei_aja_cissa(root)

    for rel in sorted(ulkona):
        if rel not in poikkeukset:
            ongelmat.append(
                "UUSI CI-POIKKEUS ILMAN PERUSTELUA: " + rel + " ("
                + ("koko tiedosto" if ulkona[rel] == ["*"]
                   else ", ".join(ulkona[rel]))
                + ") ei aja yhdessakaan workflow'ssa. Lisaa rivi "
                "CI_POIKKEUKSET-listaan ja kirjoita MIKA paikallinen resurssi "
                "CI:sta puuttuu. Aja `python scripts/ci_test_selection.py " + rel
                + "` nahdaksesi miksi se jaa pois.")

    for rel in sorted(poikkeukset):
        if rel not in ulkona:
            ongelmat.append(
                "VANHENTUNUT POIKKEUS: " + rel + " ajaa nyt CI:ssa. Poista "
                "rivi - jaanyt perustelu on vaite jota mikaan ei mittaa. "
                "HUOM: jos syy on se etta markkerivalinta katosi workflow'sta, "
                "korjaa workflow eika tata listaa.")
            continue
        syy = (poikkeukset[rel] or "").strip()
        if len(syy) < MIN_PERUSTELU:
            ongelmat.append(
                "PERUSTELU LIIAN LYHYT (" + str(len(syy)) + " < "
                + str(MIN_PERUSTELU) + " merkkia): " + rel)
        if not _RESURSSI.search(syy):
            ongelmat.append(
                "PERUSTELU EI NIMEA RESURSSIA: " + rel + ". Kirjoita "
                "backtickeissa mika polku, ymparistomuuttuja tai endpoint "
                "puuttuu CI:sta (esim. `FOOTBALL_DATA_API_KEY`, "
                "`data/raw/football-data-org/`).")

        # Fail-closed: "en tieda" ei kelpaa perusteluksi "CI ei aja tata".
        #
        # HUOM miksi tassa EI ole erillista `if v.runs:` -haaraa. Kirjoitin
        # sen ensin, ja mutaatiotesti (`if v.runs:` -> `if False:`) jatti
        # kaikki 61 testia vihreiksi: haara on saavuttamaton, koska `ulkona`
        # johdetaan SAMASTA lukijasta. Vartioimaton haara nayttaa portilta
        # olematta portti (muisti: exit-koodi-ei-ole-todiste-mekanismista),
        # joten se on poistettu. Workflow'n markkerivalinnan katoamisen
        # nappaa "VANHENTUNUT POIKKEUS" ylla - mitattu mutaatiolla M8.
        kohteet = [rel] if ulkona[rel] == ["*"] else ulkona[rel]
        for kohde in kohteet:
            v = lukija.ci_runs(kohde, root)
            if v.epavarmat:
                ongelmat.append(
                    "LUKIJA EI OLLUT VARMA: " + kohde + " -> "
                    + "; ".join(v.epavarmat) + ". Fail-closed: epavarma ei "
                    "ole 'ei aja'.")

    ini = lukija.pytest_ini(root)
    slow = lukija.marked_items("slow", root)
    if slow and not (ini.get("markers") or {}).get("slow"):
        ongelmat.append(
            "pytest.ini ei kuvaa `slow`-markkeria. Markkeri jonka merkitys "
            "ei ole kirjoitettu mihinkaan on juuri se jota luetaan vaarin.")
    return ongelmat


# ---------------------------------------------------------------------------
# TAMA REPO
# ---------------------------------------------------------------------------

def test_jokainen_ci_poikkeus_on_perusteltu():
    ongelmat = tarkista(ROOT, CI_POIKKEUKSET)
    assert not ongelmat, "\n".join("- " + o for o in ongelmat)


def test_poikkeuslista_kattaa_tasmalleen_ne_joita_ci_ei_aja():
    """KUTSUPAIKKA-kontrolli: lista ei ole kasin yllapidettu kopio vaan
    mitataan workflow'ista ja testitiedostoista."""
    assert set(lukija.ei_aja_cissa(ROOT)) == set(CI_POIKKEUKSET)


def test_slow_merkityt_ovat_osajoukko_poikkeuksista():
    """slow on tanaan ainoa syy jaada CI:n ulkopuolelle. Jos joku merkitsee
    tiedoston slowiksi, se nakyy poikkeuslistassa - ja jos slow lakkaa
    sulkemasta mitaan, tama kertoo sen."""
    slow = set(lukija.marked_items("slow", ROOT))
    assert slow <= set(CI_POIKKEUKSET)
    assert slow, "yksikaan tiedosto ei ole slow-merkitty - onko markkeri poistettu?"


def test_slow_merkityt_eivat_aja_tests_ymlssa():
    """17.9:n vaite mitattuna: yksikaan slow-merkitty testi ei ole tests.yml:n
    valinnassa, joten yksikaan niista ei voi tehda siita punaista."""
    for rel, nodeids in lukija.marked_items("slow", ROOT).items():
        for kohde in ([rel] if nodeids == ["*"] else nodeids):
            v = lukija.ci_runs(kohde, ROOT)
            assert v.runs is False, kohde + ": " + v.reason


def test_valtaosa_testeista_AJAA_PARI():
    """EROTTELEVA PARI. Jos lukija vastaisi aina "ei aja", ylla olevat testit
    olisivat vihreita eivatka mittaisi mitaan."""
    kaikki = lukija.all_test_files(ROOT)
    ajaa = [f for f in kaikki if lukija.ci_runs(f, ROOT).runs]
    assert len(ajaa) > 0.8 * len(kaikki), str(len(ajaa)) + "/" + str(len(kaikki))


# ---------------------------------------------------------------------------
# SYNTEETTISET VAIHEET: kaatuuko portti silloin kun sen pitaa?
# ---------------------------------------------------------------------------

def _repo(tmp_path, komento='pytest -m "not slow" -q', testit=None, **kw):
    return tekorepo(tmp_path,
                    workflows={"tests.yml": workflow(komento)},
                    testit=testit or {"tests/test_hidas.py": MODUULITASO,
                                      "tests/test_nopea.py": EI_MARKKERIA},
                    **kw)


HYVA = ("Vaatii `data/raw/football-data-org/`-levycachen tai "
        "`FOOTBALL_DATA_API_KEY`:n, joita CI-runnerilla ei ole; ilman niita "
        "lataus palauttaa 404 eika testi voi olla vihrea CI:ssa.")


def test_kunnollinen_lista_ei_tuota_ongelmia_PARI(tmp_path):
    """Kontrolli: portti ei ole aina punainen."""
    root = _repo(tmp_path)
    assert tarkista(root, {"tests/test_hidas.py": HYVA}) == []


def test_uusi_slow_tiedosto_ilman_perustelua_kaataa(tmp_path):
    root = _repo(tmp_path, testit={"tests/test_hidas.py": MODUULITASO,
                                   "tests/test_uusi.py": FUNKTIOTASO})
    ongelmat = tarkista(root, {"tests/test_hidas.py": HYVA})
    assert any("UUSI CI-POIKKEUS" in o and "test_uusi.py" in o
               for o in ongelmat), ongelmat


def test_UUSI_MARKKERINIMI_ei_paase_listan_ohi(tmp_path):
    """TAMA on se muoto joka on yhden muokkauksen paassa. Kirjoittaja lisaa
    OMAN markkerin ja laajentaa tests.yml:n valintaa - sana "slow" ei esiinny
    missaan, joten slow-kohtainen portti olisi vihrea. Lista johdetaan
    sulkeutumisesta, joten tama kaatuu."""
    uusi = ('import pytest\n\npytestmark = pytest.mark.uvicorn\n\n'
            'def test_a():\n    assert True\n')
    root = _repo(tmp_path, komento='pytest -m "not slow and not uvicorn" -q',
                 testit={"tests/test_hidas.py": MODUULITASO,
                         "tests/test_uvicorn.py": uusi})
    ongelmat = tarkista(root, {"tests/test_hidas.py": HYVA})
    assert any("UUSI CI-POIKKEUS" in o and "test_uvicorn.py" in o
               for o in ongelmat), ongelmat


def test_POLKURAJAUS_ei_paase_listan_ohi(tmp_path):
    """Toinen muoto ilman markkereita: workflow luettelee tiedostot kasin, ja
    uusi testitiedosto jaa listalta pois. Ei markkeria, ei slowia, mutta CI ei
    aja sita - sama vikaluokka."""
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow("pytest tests/test_a.py -q")},
                    testit={"tests/test_a.py": EI_MARKKERIA,
                            "tests/test_uusi.py": EI_MARKKERIA})
    ongelmat = tarkista(root, {})
    assert any("UUSI CI-POIKKEUS" in o and "test_uusi.py" in o
               for o in ongelmat), ongelmat


def test_DESELECT_ei_paase_listan_ohi(tmp_path):
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow(
                        "pytest --deselect tests/test_a.py::test_b -q")},
                    testit={"tests/test_a.py": EI_MARKKERIA})
    ongelmat = tarkista(root, {})
    assert any("UUSI CI-POIKKEUS" in o and "::test_b" in o
               for o in ongelmat), ongelmat


def test_vanhentunut_poikkeus_kaataa(tmp_path):
    root = _repo(tmp_path)
    ongelmat = tarkista(root, {"tests/test_hidas.py": HYVA,
                               "tests/test_nopea.py": HYVA})
    assert any("VANHENTUNUT" in o and "test_nopea.py" in o for o in ongelmat)


def test_liian_lyhyt_perustelu_kaataa(tmp_path):
    root = _repo(tmp_path)
    ongelmat = tarkista(root, {"tests/test_hidas.py": "hidas"})
    assert any("LIIAN LYHYT" in o for o in ongelmat)


def test_perustelu_ilman_resurssia_kaataa(tmp_path):
    """"Tama testi on hidas ja vaatii paljon paikallista dataa" ei kerro
    MITA. Perustelun on nimettava resurssi, muuten se on vain tunne."""
    root = _repo(tmp_path)
    syy = ("Tama testi on hyvin hidas ja vaatii paljon paikallista dataa "
           "jota CI-ympariston runnerilla ei valttamatta ole saatavilla.")
    assert len(syy) >= MIN_PERUSTELU
    ongelmat = tarkista(root, {"tests/test_hidas.py": syy})
    assert any("EI NIMEA RESURSSIA" in o for o in ongelmat)


# --- INVARIANTTI TOISESSA VAIHEESSA: workflow muuttuu listan alla ----------

def test_markkerivalinnan_poisto_workflowsta_kaataa_poikkeuslistan(tmp_path):
    """Tama on se vaihe jossa perustelu lakkaa olemasta tosi. Jos joku
    poistaa `-m "not slow"` tests.yml:sta, slow-testit ALKAVAT ajaa CI:ssa ja
    perustelu "CI:lla ei ole tata resurssia" tarkoittaa punaista CI:ta. Portti
    ei mittaa nykyhetkea vaan invarianttia (saanto 6a, mekanismi 3)."""
    root = _repo(tmp_path, komento="pytest -q")
    ongelmat = tarkista(root, {"tests/test_hidas.py": HYVA})
    assert any("VANHENTUNUT POIKKEUS" in o and "korjaa workflow" in o
               for o in ongelmat), ongelmat


def test_kaanteinen_markkerivalinta_kaataa_poikkeuslistan(tmp_path):
    root = _repo(tmp_path, komento='pytest -m "slow" -q')
    ongelmat = tarkista(root, {"tests/test_hidas.py": HYVA})
    assert ongelmat, "kaanteinen valinta ei kaatanut porttia"
    assert any("VANHENTUNUT POIKKEUS" in o for o in ongelmat)
    assert any("UUSI CI-POIKKEUS" in o and "test_nopea.py" in o
               for o in ongelmat), ongelmat


def test_funktiotason_poikkeus_mitataan_nodeid_tasolla(tmp_path):
    """Tiedosto ajaa CI:ssa (1/2), yksi testi ei. Poikkeus koskee sita yhta
    testia, ja premissi mitataan siita - ei tiedostosta."""
    root = _repo(tmp_path, testit={"tests/test_sekava.py": FUNKTIOTASO})
    assert tarkista(root, {"tests/test_sekava.py": HYVA}) == []
    ulkona = lukija.ei_aja_cissa(root)
    assert ulkona == {"tests/test_sekava.py": ["tests/test_sekava.py::test_hidas"]}


def test_epavarma_lukija_kaataa_listan(tmp_path):
    """Fail-closed: `-k`-valinta tekee vastauksesta epavarman, eika epavarma
    saa kelvata perusteluksi "CI ei aja tata"."""
    root = _repo(tmp_path, komento='pytest -k "not golden" -q')
    ongelmat = tarkista(root, {"tests/test_hidas.py": HYVA,
                               "tests/test_nopea.py": HYVA})
    assert any("EI OLLUT VARMA" in o for o in ongelmat), ongelmat


def test_pytest_ini_ilman_slow_kuvausta_kaataa(tmp_path):
    root = tekorepo(tmp_path,
                    workflows={"tests.yml": workflow('pytest -m "not slow" -q')},
                    testit={"tests/test_hidas.py": MODUULITASO},
                    ini="[pytest]\npythonpath = .\ntestpaths = tests\n")
    ongelmat = tarkista(root, {"tests/test_hidas.py": HYVA})
    assert any("ei kuvaa" in o for o in ongelmat)
