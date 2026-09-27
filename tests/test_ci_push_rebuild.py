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


def run_script(repo: Path, tmp: Path) -> tuple[subprocess.CompletedProcess, str]:
    out = tmp / "gh_output"
    out.write_text("", encoding="utf-8")
    py = Path(sys.executable).as_posix()
    env = {**ENV, "CI_PUSH_DATA": "data/acc.txt", "CI_PUSH_PAGES": "page.html",
           "CI_PUSH_BUILD": f'"{py}" builder.py',
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


# ---------------------------------------------------------------- kytkenta

WF = ROOT / ".github" / "workflows" / "accuracy-log.yml"


def _steps():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    return next(iter(doc["jobs"].values()))["steps"]


def test_accuracy_log_kayttaa_skriptia_eika_omaa_rebase_silmukkaa():
    push = next(s for s in _steps() if s.get("id") == "push")
    assert "scripts/ci_push_rebuild.sh" in push["run"]
    assert "git rebase" not in push["run"]
    env = push["env"]
    for avain in ("CI_PUSH_DATA", "CI_PUSH_PAGES", "CI_PUSH_BUILD", "CI_PUSH_MSG"):
        assert env.get(avain), avain
    assert "data/prediction_log.json" in env["CI_PUSH_DATA"].split()
    assert "[skip ci]" in env["CI_PUSH_MSG"]


def test_uudelleenrakennus_ajaa_samat_builderit_kuin_workflow():
    """Builderilista johdetaan workflow'sta: uusi bake-askel ilman vastinetta
    CI_PUSH_BUILDissa jattaisi sivunsa konfliktissa vanhaksi."""
    steps = _steps()
    push_i = next(i for i, s in enumerate(steps) if s.get("id") == "push")
    bakes = [s["run"].strip() for s in steps[:push_i]
             if str(s.get("id", "")).startswith("bake_")]
    assert bakes, "yhtaan bake-askelta ei loytynyt"
    build = steps[push_i]["env"]["CI_PUSH_BUILD"]
    for cmd in bakes:
        assert cmd in build, f"bake-askel puuttuu uudelleenrakennuksesta: {cmd}"
