"""scripts/ci_push_rebuild.sh OIKEALLA GITILLA (27.9.2026, AUTO-S16).

Tapaus jota tama vartioi, mitattu 26.9 13:35 UTC (accuracy-log 36245702189):
builder-muutos kaynnisti kaksi muuta sivuja regeneroivaa workflow'ta, ne
pushasivat samat sivut eri syotteesta, ja accuracy-login rebase konfliktoi
viidesti -> koko ajon data jai mainin ulkopuolelle.

Fikstuuri: bare origin + kaksi kloonia (A = taman ajon workflow, B = toinen).
Sivu on builderin tulos KAHDESTA datatiedostosta, joten oikea vastaus
konfliktin jalkeen on sivu jossa on MOLEMPIEN data. Se erottaa kolme
toteutusta: vanha rebase-silmukka (exit 1), "meidan versio voittaa"
(sivu jossa B:n data puuttuu) ja uudelleenrakennus (oikein).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ci_push_rebuild.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(not BASH or not shutil.which("git"),
                                reason="bash tai git puuttuu")

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

BUILDER = (
    "from pathlib import Path\n"
    "a = Path('data/acc.txt').read_text().strip()\n"
    "f = Path('data/fpl.txt').read_text().strip()\n"
    "Path('page.html').write_text(f'<p>acc={a} fpl={f}</p>\\n')\n"
)


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, (args, r.stderr)
    return r.stdout.strip()


def build(repo: Path) -> None:
    subprocess.run([sys.executable, "builder.py"], cwd=repo, check=True)


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text + "\n", encoding="utf-8")


@pytest.fixture()
def repos(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(origin), str(seed))
    git(seed, "checkout", "-q", "-b", "main")
    (seed / "builder.py").write_text(BUILDER, encoding="utf-8")
    write(seed, "data/acc.txt", "1")
    write(seed, "data/fpl.txt", "1")
    write(seed, "other.txt", "x")
    build(seed)
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "seed")
    git(seed, "push", "-q", "origin", "main")
    a, b = tmp_path / "a", tmp_path / "b"
    git(tmp_path, "clone", "-q", str(origin), str(a))
    git(tmp_path, "clone", "-q", str(origin), str(b))
    return origin, a, b, tmp_path


_OLETUS = object()


def run_script(repo: Path, tmp: Path, *, data=_OLETUS, pages="page.html",
               build=_OLETUS) -> tuple[subprocess.CompletedProcess, str]:
    out = tmp / "gh_output"
    out.write_text("", encoding="utf-8")
    py = Path(sys.executable).as_posix()
    env = {**ENV,
           "CI_PUSH_DATA": "data/acc.txt" if data is _OLETUS else data,
           "CI_PUSH_PAGES": pages,
           "CI_PUSH_BUILD": f'"{py}" builder.py' if build is _OLETUS else build,
           "CI_PUSH_MSG": "chore(test): auto [skip ci]",
           "CI_PUSH_SLEEP": "0", "CI_PUSH_TRIES": "3", "GITHUB_OUTPUT": str(out)}
    r = subprocess.run([BASH, SCRIPT.as_posix()], cwd=repo, capture_output=True,
                       text=True, env=env)
    return r, out.read_text(encoding="utf-8")


def origin_file(origin: Path, rel: str) -> str:
    return git(origin, "show", f"main:{rel}")


def test_konflikti_sivussa_rakennetaan_uudelleen_molempien_datalla(repos):
    origin, a, b, tmp = repos
    # B (toinen workflow) pushaa ensin: FPL-data 2, sivu regeneroitu.
    write(b, "data/fpl.txt", "2")
    build(b)
    git(b, "commit", "-qam", "b: fpl 2")
    git(b, "push", "-q", "origin", "main")
    # A (accuracy-log) on rakentanut sivunsa VANHAN fpl:n paalle.
    write(a, "data/acc.txt", "2")
    build(a)
    r, out = run_script(a, tmp)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "uudelleenrakennettuna" in r.stdout
    assert origin_file(origin, "page.html") == "<p>acc=2 fpl=2</p>"
    assert origin_file(origin, "data/acc.txt") == "2"
    assert origin_file(origin, "data/fpl.txt") == "2"
    assert "pushed=true" in out


def test_toisen_datan_muutos_kaataa_eika_ylikirjoita(repos):
    origin, a, b, tmp = repos
    write(b, "data/acc.txt", "9")
    build(b)
    git(b, "commit", "-qam", "b: acc 9 (toinen kirjoittaja samalle datalle)")
    git(b, "push", "-q", "origin", "main")
    write(a, "data/acc.txt", "2")
    build(a)
    r, out = run_script(a, tmp)
    assert r.returncode == 1
    assert "EI ylikirjoiteta" in r.stdout
    assert origin_file(origin, "data/acc.txt") == "9"
    assert "pushed=true" not in out


def test_puhdas_rebase_menee_normaalisti(repos):
    origin, a, b, tmp = repos
    write(b, "other.txt", "y")
    git(b, "commit", "-qam", "b: other")
    git(b, "push", "-q", "origin", "main")
    write(a, "data/acc.txt", "2")
    build(a)
    before = int(git(origin, "rev-list", "--count", "main"))
    r, out = run_script(a, tmp)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "uudelleenrakennettuna" not in r.stdout
    assert int(git(origin, "rev-list", "--count", "main")) == before + 1
    assert origin_file(origin, "page.html") == "<p>acc=2 fpl=1</p>"
    assert origin_file(origin, "other.txt") == "y"
    assert "pushed=true" in out


def test_ei_muutoksia_ei_committia(repos):
    origin, a, _b, tmp = repos
    before = git(origin, "rev-parse", "main")
    r, out = run_script(a, tmp)
    assert r.returncode == 0
    assert git(origin, "rev-parse", "main") == before
    assert "pushed=true" not in out


def test_toisen_muuttama_datatiedosto_jota_me_emme_muuttaneet_jaa_voimaan(repos):
    """27.9 (CI-PUSH-REBUILD-MUUT-WORKFLOWT): fpl-data-refreshin DATA-lista on
    ~30 polkua. Jos toinen kirjoittaja muutti listan tiedostoa jota TAMA ajo
    ei muuttanut, ajo ei saa kaatua eika palauttaa tiedostoa vanhaksi.
    Vanha tarkistus (koko DATA-lista pohja..origin) kaatui tassa turhaan."""
    origin, a, b, tmp = repos
    write(b, "data/fpl.txt", "2")
    build(b)
    git(b, "commit", "-qam", "b: fpl 2")
    git(b, "push", "-q", "origin", "main")
    write(a, "data/acc.txt", "2")
    build(a)
    r, out = run_script(a, tmp, data="data/acc.txt data/fpl.txt")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "uudelleenrakennettuna" in r.stdout
    assert origin_file(origin, "data/fpl.txt") == "2", "B:n data palautettiin vanhaksi"
    assert origin_file(origin, "data/acc.txt") == "2"
    assert origin_file(origin, "page.html") == "<p>acc=2 fpl=2</p>"
    assert "pushed=true" in out


def test_tyhja_data_sivuajo_rakentaa_tuoreen_mainin_datasta(repos):
    """fpl-page-refresh ei kirjoita dataa (CI_PUSH_DATA tyhja). Konfliktissa
    sivu rakennetaan mainin datasta. Tyhja polkulista EI saa muuttua
    `git diff A B --`:ksi, joka listaisi koko puun ja nayttaisi sivun
    omalta datalta."""
    origin, a, b, tmp = repos
    write(b, "data/fpl.txt", "3")
    build(b)
    git(b, "commit", "-qam", "b: fpl 3")
    git(b, "push", "-q", "origin", "main")
    # A:n sivu on rakennettu eri syotteesta (simuloi sivuajon omaa bakea).
    (a / "page.html").write_text("<p>acc=1 fpl=1 vanha</p>\n", encoding="utf-8")
    before = git(origin, "rev-parse", "main")
    r, out = run_script(a, tmp, data="")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "rakennetaan uudelleen" in r.stdout
    # Mainin datasta rakennettu sivu on sama kuin B:n: vanhentunut A:n sivu
    # hylataan eika turhaa committia synny.
    assert origin_file(origin, "page.html") == "<p>acc=1 fpl=3</p>"
    assert git(origin, "rev-parse", "main") == before
    assert "pushed=true" not in out


def test_vain_data_ilman_sivuja_pushataan(repos):
    """fpl-why-refresh: CI_PUSH_PAGES ja CI_PUSH_BUILD tyhjia."""
    origin, a, b, tmp = repos
    write(b, "other.txt", "z")
    git(b, "commit", "-qam", "b: other")
    git(b, "push", "-q", "origin", "main")
    write(a, "data/acc.txt", "5")
    r, out = run_script(a, tmp, pages="", build="")
    assert r.returncode == 0, r.stdout + r.stderr
    assert origin_file(origin, "data/acc.txt") == "5"
    assert origin_file(origin, "other.txt") == "z"
    assert "pushed=true" in out


def test_molemmat_listat_tyhjia_kaatuu(repos):
    _origin, a, _b, tmp = repos
    r, _ = run_script(a, tmp, data="", pages="", build="")
    assert r.returncode == 1
    assert "molemmat tyhjia" in r.stdout + r.stderr


# ---------------------------------------------------------------- kytkenta

WORKFLOWS = ROOT / ".github" / "workflows"

# Workflow -> datatiedosto joka listalla on oltava. 27.9: vanha viiden
# rebasen silmukka oli kaikissa neljassa; accuracy-log siirtyi ensin (S16).
PUSH_WORKFLOWT = {
    "accuracy-log.yml": "data/prediction_log.json",
    "fpl-data-refresh.yml": "data/fpl_xp_projections.json",
    "fpl-page-refresh.yml": None,  # ei kirjoita dataa
    "fpl-why-refresh.yml": "data/fpl_why.json",
    "fpl-elite-tick.yml": "data/fpl_elite_ownership.json",
}

_PY_RE = re.compile(r"python3?\s+(?:-m\s+)?(scripts[./][\w./]+)")


def _moduulit(teksti: str) -> set[str]:
    """`python scripts/x.py` ja `python -m scripts.x` ovat sama builderi."""
    return {m.removesuffix(".py").replace("/", ".")
            for m in _PY_RE.findall(teksti or "")}


def _steps(nimi: str):
    doc = yaml.safe_load((WORKFLOWS / nimi).read_text(encoding="utf-8"))
    return next(iter(doc["jobs"].values()))["steps"]


def _push(nimi: str) -> dict:
    return next(s for s in _steps(nimi) if s.get("id") == "push")


@pytest.mark.parametrize("nimi", sorted(PUSH_WORKFLOWT))
def test_workflow_kayttaa_skriptia_eika_omaa_rebase_silmukkaa(nimi):
    push = _push(nimi)
    assert "scripts/ci_push_rebuild.sh" in push["run"]
    assert "git rebase" not in push["run"]
    env = push["env"]
    for avain in ("CI_PUSH_DATA", "CI_PUSH_PAGES", "CI_PUSH_BUILD", "CI_PUSH_MSG"):
        assert avain in env, f"{nimi}: {avain} puuttuu (skripti kaatuu)"
    assert "[skip ci]" in env["CI_PUSH_MSG"]
    data = (env["CI_PUSH_DATA"] or "").split()
    if PUSH_WORKFLOWT[nimi]:
        assert PUSH_WORKFLOWT[nimi] in data
    assert data or (env["CI_PUSH_PAGES"] or "").split(), f"{nimi}: molemmat listat tyhjia"


def test_mikaan_listattu_workflow_ei_kayta_vanhaa_rebase_silmukkaa():
    """Push-askel ei saa palauttaa silmukkaa jonka konflikti oli
    deterministinen (S16 26.9). Poikkeus vaatii perustelun."""
    poikkeukset: dict[str, str] = {}
    for nimi in sorted(PUSH_WORKFLOWT):
        for s in _steps(nimi):
            run = s.get("run") or ""
            if "git rebase" in run and "git push" in run:
                rivi = f"{nimi}: {s.get('name')}"
                assert poikkeukset.get(rivi, "").strip(), rivi


@pytest.mark.parametrize("nimi", sorted(PUSH_WORKFLOWT))
def test_uudelleenrakennus_ajaa_samat_builderit_kuin_workflow(nimi):
    """Builderilista johdetaan workflow'sta: uusi bake-askel ilman vastinetta
    CI_PUSH_BUILDissa jattaisi sivunsa konfliktissa vanhaksi."""
    steps = _steps(nimi)
    push_i = next(i for i, s in enumerate(steps) if s.get("id") == "push")
    bakes = [s.get("run") or "" for s in steps[:push_i]
             if str(s.get("id", "")).startswith("bake_")]
    env = steps[push_i]["env"]
    build = _moduulit(env["CI_PUSH_BUILD"] or "")
    if not (env["CI_PUSH_PAGES"] or "").split():
        assert not bakes and not build, f"{nimi}: sivuton ajo ei rakenna sivuja"
        return
    assert bakes, f"{nimi}: yhtaan bake-askelta ei loytynyt"
    for run in bakes:
        moduulit = _moduulit(run)
        assert moduulit, f"{nimi}: bake-askeleesta ei loytynyt builderia: {run[:80]}"
        puuttuu = moduulit - build
        assert not puuttuu, f"{nimi}: bake-askel puuttuu uudelleenrakennuksesta: {puuttuu}"


def test_moduulinormalisointi_erottaa_builderit():
    """Negatiivinen kontrolli: normalisointi ei saa tehda kaikista samaa."""
    assert _moduulit("python scripts/build_fpl_page.py") == {"scripts.build_fpl_page"}
    assert _moduulit("python -m scripts.build_fpl_page") == {"scripts.build_fpl_page"}
    assert _moduulit("python -m scripts.build_fpl_longtail") != {"scripts.build_fpl_page"}
    assert _moduulit("echo ei builderia") == set()
