"""Portti: workflow asentaa ne riippuvuudet jotka sen oma entry point importtaa.

🔴 SAMA VIKA KOLMESTI, KAKSI KERTAA HAVAITTU VASTA VUOROKAUSIEN PAASTA.

  9.8   `f6418b8e` toi `scripts/build_fpl_page.py`:hyn rivin
        `from scripts.build_fpl_phase0 import map_name`. Se vetaa numpyn.
        `fpl-page-refresh.yml`:n kommentti sanoi "stdlib-only, ei pip
        installia" ja se oletus oli ollut tosi siihen paivaan asti.
        Bake kaatui joka ajossa **8 vuorokautta**.
  17.8  Korjaus kirjoitettiin YHTEEN tiedostoon kasin kopioituna pakettilistana
        ja kommenttiin "sama lista kuin fpl-data-refreshissa, jotta ne eivat
        ajaudu erilleen". Lista on ihmisen muistin varassa, ei portin.
  20.8  `fpl-transfer-watch.yml` asensi vain `requests`, mutta
        `check_fpl_transfers.py` importtaa saman `build_fpl_phase0`:n.
        Vahti oli kuollut **20 vuorokautta** - ja VIHREA 200/200 ajossa,
        koska askel nosti punaiseksi vain exit-koodin 2.
  7.9   `ucl-refresh.yml` luotiin ilman asennusaskelta lainkaan.
        Epaonnistui **3/3 ajossa**; `ingest_ucl` (stdlib) onnistui joka
        kerta, joten tuore syote kirjoitettiin levylle kolmesti ja
        committiin nolla kertaa.

Kahdesti korjattiin TAPAUS. Tama tiedosto korjaa LUOKAN (CLAUDE.md 6a):
riippuvuudet johdetaan entry pointin AST:sta eika listasta tai kommentista,
joten unohdus kaataa testin sina hetkena kun workflow kirjoitetaan - ei
vuorokausia myohemmin cronissa, eika koskaan jos putki sattuu olemaan vihrea
vaarasta syysta.

MITA MITATAAN. Vain MODUULITASON importit, ja vain niiden transitiivinen
sulkeuma oman repon moduulien kautta. Juuri ne kaatavat ajon
`ModuleNotFoundError`iin ennen kuin riviakaan logiikkaa on ajettu. Funktion
sisainen tai `try/except ImportError`-suojattu importti EI ole tassa: se on
tietoinen pehmea riippuvuus, ja vaara positiivinen opettaa ohittamaan portin
yhta tehokkaasti kuin puuttuva portti.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
REQUIREMENTS = ROOT / "requirements.txt"

# Oman repon ylimman tason paketit. Naiden lapi kavellaan; kaikki muu
# ei-stdlib on kolmannen osapuolen riippuvuus joka on asennettava.
OMAT = ("scripts", "src", "api", "tests", "config")

# Importtinimi -> pip-paketin nimi silloin kun ne eroavat.
# Tuntematon kolmannen osapuolen importti KAATAA testin ja pakottaa
# lisaamaan rivin tanne: kartta ei saa hiljaa vaieta uudesta paketista.
IMPORTTI_PAKETIKSI = {
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "bs4": "beautifulsoup4",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "google": "google-api-python-client",
    "jwt": "pyjwt",
    "OpenSSL": "pyopenssl",
    "cv2": "opencv-python",
}

# (workflow, importtinimi) -> MIKSI se saa puuttua asennuksesta.
# Rivi ilman perustelua ei ole perustelu: kirjoita milla ehdolla importtia
# EI ajeta tassa workflow'ssa.
DEPS_ALLOWED: dict[tuple[str, str], str] = {}


# ---------------------------------------------------------------------------
# Workflow'n lukeminen: entry pointit ja asennetut paketit
# ---------------------------------------------------------------------------

# `python -m scripts.build_ucl_page` / `python3 -m src.foo`
_MODULI = re.compile(r"\bpython3?\s+(?:-\w+\s+)*-m\s+([A-Za-z_][\w.]*)")
# `python scripts/build_fpl_page.py` / `python3 scripts/x.py`
_SKRIPTI = re.compile(r"\bpython3?\s+(?:-\w+\s+)*([\w./-]+\.py)\b")
# `pytest tests/a.py tests/b.py` tai `python -m pytest tests/...`
_PYTEST = re.compile(r"\bpytest\b([^\n|&;]*)")
_TESTIPOLKU = re.compile(r"(tests/[\w./-]+\.py)")

_PIP = re.compile(r"\bpip\s+install\b([^\n]*)")

# 🔴 Shellin rivinjatko `\` + rivinvaihto on purettava ENNEN poimintaa.
# Ensimmainen versio yritti tehda sen regexissa (`(?:\\\n[^\n]*)*`) ja
# pudotti hiljaa kaikki jatkoriveilla olevat paketit: `fpl-transfer-watch`
# nayttiin asentavan vain pandas/numpy/scipy, ja portti olisi vaittanyt
# puuttuvaksi `requests`in joka oli rivia alempana. Vaara positiivinen on
# yhta paha kuin puuttuva portti - `test_portti_ei_valita_ylimaaraisesta_
# paketista` on tassa juuri siksi.
_JATKORIVI = re.compile(r"\\\s*\n\s*")


def _workflow_tiedostot() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.yml"))


def _run_lohkot(doc: dict) -> list[str]:
    """Kaikki `run:`-merkkijonot workflow'sta, jobista riippumatta."""
    ulos: list[str] = []

    def kavele(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "run" and isinstance(v, str):
                    ulos.append(v)
                else:
                    kavele(v)
        elif isinstance(o, list):
            for v in o:
                kavele(v)

    kavele(doc)
    return ulos


def _entry_pointit(runit: list[str]) -> set[Path]:
    """Entry pointit repopolkuina. Olematon polku jatetaan pois (esim.
    heredocissa generoitu tilapaisskripti)."""
    ulos: set[Path] = set()
    for r in runit:
        for m in _MODULI.finditer(r):
            nimi = m.group(1)
            if nimi == "pytest" or not nimi.startswith(OMAT):
                continue
            p = ROOT / (nimi.replace(".", "/") + ".py")
            if p.exists():
                ulos.add(p)
        for m in _SKRIPTI.finditer(r):
            p = ROOT / m.group(1)
            if p.exists() and p.is_file():
                ulos.add(p)
        for m in _PYTEST.finditer(r):
            loput = m.group(1)
            testit = _TESTIPOLKU.findall(loput)
            if not testit:
                continue
            # conftest ajetaan JOKAISESSA testissa, joten se kuuluu
            # sulkeumaan aina kun pytest ajetaan taman repon tests/-polulle.
            conftest = ROOT / "tests" / "conftest.py"
            if conftest.exists():
                ulos.add(conftest)
            for t in testit:
                p = ROOT / t
                if p.exists():
                    ulos.add(p)
    return ulos


def _asennetut(runit: list[str]) -> tuple[set[str], bool]:
    """(paketit pienella, asennetaanko -r requirements.txt)."""
    paketit: set[str] = set()
    requirements = False
    for r in runit:
        for m in _PIP.finditer(_JATKORIVI.sub(" ", r)):
            argit = m.group(1)
            if re.search(r"-r\s+requirements\.txt", argit):
                requirements = True
            for tokeni in re.findall(r'["\']?([A-Za-z][\w.-]*)[^\s"\']*["\']?', argit):
                t = tokeni.lower()
                if t in {"-r", "requirements", "txt", "pip", "install",
                         "upgrade", "quiet", "u", "q"}:
                    continue
                paketit.add(t.replace("_", "-"))
    return paketit, requirements


def _requirements_paketit() -> set[str]:
    if not REQUIREMENTS.exists():
        return set()
    ulos = set()
    for rivi in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        rivi = rivi.split("#")[0].strip()
        if not rivi or rivi.startswith("-"):
            continue
        nimi = re.split(r"[=<>!~\[; ]", rivi)[0].strip().lower()
        if nimi:
            ulos.add(nimi.replace("_", "-"))
    return ulos


# ---------------------------------------------------------------------------
# Importtisulkeuma AST:sta
# ---------------------------------------------------------------------------


def _moduulitason_importit(puu: ast.Module) -> set[str]:
    """Ylimman tason importit. `try:`- ja `if TYPE_CHECKING:` -lohkot ohitetaan:
    ne ovat tahallisia pehmeita riippuvuuksia eivatka kaada ajoa."""
    ulos: set[str] = set()
    for solmu in puu.body:
        if isinstance(solmu, ast.Import):
            for a in solmu.names:
                ulos.add(a.name.split(".")[0])
        elif isinstance(solmu, ast.ImportFrom):
            if solmu.level:  # suhteellinen importti pysyy repon sisalla
                continue
            if solmu.module:
                ulos.add(solmu.module.split(".")[0])
    return ulos


def _moduulipolku(nimi: str) -> Path | None:
    kanta = ROOT / nimi.replace(".", "/")
    for kandidaatti in (kanta.with_suffix(".py"), kanta / "__init__.py"):
        if kandidaatti.exists():
            return kandidaatti
    return None


def _täysi_nimi(puu: ast.Module, ylin: str) -> set[str]:
    """Palauta oman repon moduulien TAYDET nimet (src.data.loader), jotta
    kavely osuu oikeaan tiedostoon eika pelkkaan pakettiin."""
    ulos: set[str] = set()
    for solmu in puu.body:
        if isinstance(solmu, ast.Import):
            for a in solmu.names:
                if a.name.split(".")[0] == ylin:
                    ulos.add(a.name)
        elif isinstance(solmu, ast.ImportFrom):
            if solmu.module and solmu.module.split(".")[0] == ylin:
                ulos.add(solmu.module)
    return ulos


def kolmannen_osapuolen_sulkeuma(entry: Path) -> set[str]:
    """Entry pointin transitiivinen moduulitason importtisulkeuma, josta on
    jaljella vain kolmannen osapuolen ylimman tason importtinimet."""
    nahty: set[Path] = set()
    jono = [entry]
    kolmannet: set[str] = set()

    while jono:
        tiedosto = jono.pop()
        if tiedosto in nahty or not tiedosto.exists():
            continue
        nahty.add(tiedosto)
        try:
            puu = ast.parse(tiedosto.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for ylin in _moduulitason_importit(puu):
            if ylin in sys.stdlib_module_names or ylin == "__future__":
                continue
            if ylin in OMAT:
                for taysi in _täysi_nimi(puu, ylin):
                    p = _moduulipolku(taysi)
                    if p is not None:
                        jono.append(p)
                p = _moduulipolku(ylin)
                if p is not None:
                    jono.append(p)
                continue
            kolmannet.add(ylin)
    return kolmannet


def _kattaa(importti: str, paketit: set[str], requirements: bool,
            req_paketit: set[str]) -> bool:
    pakettinimi = IMPORTTI_PAKETIKSI.get(importti, importti).lower().replace("_", "-")
    if pakettinimi in paketit:
        return True
    if requirements and pakettinimi in req_paketit:
        return True
    return False


def _puutteet() -> dict[tuple[str, str], Path]:
    """(workflow, importti) -> entry point joka sita tarvitsee."""
    req_paketit = _requirements_paketit()
    puutteet: dict[tuple[str, str], Path] = {}
    for wf in _workflow_tiedostot():
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        runit = _run_lohkot(doc)
        paketit, requirements = _asennetut(runit)
        for entry in sorted(_entry_pointit(runit)):
            for imp in sorted(kolmannen_osapuolen_sulkeuma(entry)):
                if _kattaa(imp, paketit, requirements, req_paketit):
                    continue
                puutteet.setdefault((wf.name, imp), entry)
    return puutteet


# ---------------------------------------------------------------------------
# Assertiot
# ---------------------------------------------------------------------------


def test_jokainen_workflow_asentaa_mita_sen_entry_point_importtaa():
    puutteet = _puutteet()
    uudet = {k: v for k, v in puutteet.items() if k not in DEPS_ALLOWED}
    assert not uudet, (
        "Nama workflow't ajavat Pythonia asentamatta sita mita entry point "
        "importtaa MODUULITASOLLA. Ajo kaatuu ModuleNotFoundErroriin ennen "
        "kuin riviakaan logiikkaa on ajettu. Lisaa asennus, tai lisaa rivi "
        "DEPS_ALLOWED-listaan ja kirjoita MIKSI importtia ei ajeta:\n"
        + "\n".join(
            f"  {wf}: puuttuu '{imp}' (tarvitsee {entry.relative_to(ROOT).as_posix()})"
            for (wf, imp), entry in sorted(uudet.items())))


def test_poikkeuslistalla_ei_ole_kuolleita_rivaja():
    """Vanhentunut poikkeus opettaa etta listalle paasee eika sielta poistuta."""
    puutteet = _puutteet()
    kuolleet = [k for k in DEPS_ALLOWED if k not in puutteet]
    assert not kuolleet, (
        "DEPS_ALLOWED-listalla on rivejä joita mikaan puute ei enaa vastaa, "
        f"poista ne: {kuolleet}")


def test_poikkeuslista_kantaa_oikean_perustelun():
    for avain, syy in DEPS_ALLOWED.items():
        assert len(syy.split()) >= 6, (avain, syy)


def test_jokainen_kolmannen_osapuolen_importti_on_kartalla():
    """Tuntematon importtinimi ei saa naittaa katetulta vain siksi ettei
    kartta tunne sen pip-nimea."""
    tunnetut = _requirements_paketit()
    tuntemattomat: set[str] = set()
    for wf in _workflow_tiedostot():
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        # Workflow'n oma eksplisiittinen asennus tekee nimesta tunnetun myos
        # silloin kun paketti ei ole requirements.txt:ssa (esim. pytest).
        tunnetut |= _asennetut(_run_lohkot(doc))[0]
    for wf in _workflow_tiedostot():
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        for entry in _entry_pointit(_run_lohkot(doc)):
            for imp in kolmannen_osapuolen_sulkeuma(entry):
                nimi = IMPORTTI_PAKETIKSI.get(imp, imp).lower().replace("_", "-")
                if imp not in IMPORTTI_PAKETIKSI and nimi not in tunnetut:
                    tuntemattomat.add(imp)
    assert not tuntemattomat, (
        "Nama importit eivat ole requirements.txt:ssa eivatka "
        "IMPORTTI_PAKETIKSI-kartassa. Lisaa pip-nimi karttaan, muuten portti "
        f"vertaa vaaraa nimea eika nae puutetta: {sorted(tuntemattomat)}")


# ---------------------------------------------------------------------------
# 🔴 NEGATIIVISET KONTROLLIT. Portti joka ei voi mennä punaiseksi ei ole
# portti, ja vaara positiivinen opettaa ohittamaan sen.
# ---------------------------------------------------------------------------


def _puutteet_kansiosta(kansio: Path) -> set[tuple[str, str]]:
    req_paketit = _requirements_paketit()
    ulos: set[tuple[str, str]] = set()
    for wf in sorted(kansio.glob("*.yml")):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        runit = _run_lohkot(doc)
        paketit, requirements = _asennetut(runit)
        for entry in _entry_pointit(runit):
            for imp in kolmannen_osapuolen_sulkeuma(entry):
                if not _kattaa(imp, paketit, requirements, req_paketit):
                    ulos.add((wf.name, imp))
    return ulos


def test_portti_kaataa_workflown_josta_asennus_on_poistettu(tmp_path):
    """Positiivinen mutaatio: sama tiedosto ilman pip-rivia on puute."""
    lahde = WORKFLOWS / "ucl-refresh.yml"
    teksti = lahde.read_text(encoding="utf-8")
    assert "pip install" in teksti, "lahde ei enaa asenna mitaan - valitse toinen"
    riisuttu = "\n".join(
        r for r in teksti.splitlines() if "pip install" not in r)
    (tmp_path / "ucl-refresh.yml").write_text(riisuttu, encoding="utf-8")
    loydot = _puutteet_kansiosta(tmp_path)
    assert any(imp == "numpy" for _, imp in loydot), (
        "portti ei havainnut puuttuvaa numpyta ilman asennusaskelta - "
        f"loydot: {sorted(loydot)}")


def test_portti_ei_valita_ylimaaraisesta_paketista(tmp_path):
    """Negatiivinen mutaatio: liikaa asennettu ei ole vika. Vaara positiivinen
    opettaisi ohittamaan portin yhta tehokkaasti kuin puuttuva portti."""
    lahde = WORKFLOWS / "ucl-refresh.yml"
    teksti = lahde.read_text(encoding="utf-8")
    lisatty = teksti.replace(
        "pip install -r requirements.txt pytest httpx",
        "pip install -r requirements.txt pytest httpx rich",
    )
    assert lisatty != teksti, "asennusrivia ei loytynyt - paivita kontrolli"
    (tmp_path / "ucl-refresh.yml").write_text(lisatty, encoding="utf-8")
    assert not _puutteet_kansiosta(tmp_path), "ylimaarainen paketti luettiin viaksi"


def test_portti_nakee_edes_yhden_entry_pointin():
    """Jos entry point -poiminta lakkaa osumasta, kaikki yllaoleva lapaisee
    tyhjana (muisti: kontrolli-lapaisi-tyhjana)."""
    yhteensa = 0
    for wf in _workflow_tiedostot():
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            yhteensa += len(_entry_pointit(_run_lohkot(doc)))
    assert yhteensa >= 5, f"vain {yhteensa} entry pointia - poiminta on rikki"


def test_sulkeuma_kavelee_oman_repon_lapi():
    """Sulkeuman on loydettava numpy `build_ucl_page`ista, joka ei importtaa
    sita itse vaan kolmen oman moduulin takaa. Tama on tasan se ketju joka
    kaatoi ucl-refreshin 3/3 ajossa."""
    entry = ROOT / "scripts" / "build_ucl_page.py"
    if not entry.exists():
        pytest.skip("build_ucl_page.py poistettu")
    assert "numpy" in kolmannen_osapuolen_sulkeuma(entry)
