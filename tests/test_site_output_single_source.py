"""Portti: sivuston polkulista on YKSI lahde, ja site-repo-push on fail-safe.

SITE-REPO-SPLIT vaihe 1 (10.9.2026). Sivuston output alkaa mennä kahteen
kohteeseen (CF Pages direct upload + GoalIQ/goaliq-site). Jos "mika on
sivustoa" olisi kahtena kasin yllapidettyna listana, ne ajautuisivat
erilleen samalla tavalla kuin pip-listat 17.8 (test_workflow_deps).
Siksi lista on `scripts/site_output.py` ja hub-deploy.yml kutsuu sita.

Mita mitataan:
  1. hub-deploy.yml ei sisalla omaa suodatinta vaan kutsuu site_output.py:ta.
  2. site_output.py:n lista on tasan vanha suodatin + PUBLIC_DATA (golden
     sisallytykset ja negatiiviset kontrollit, ml. ne kaksi tiedostoa jotka
     16.8 olisivat menneet julkiselle sivustolle).
  3. PUBLIC_DATA-rivilla on perustelu ja polku on repossa (kuollut rivi
     kaataa).
  4. Jokainen sivun "Source:"-linkki GitHubiin osoittaa PUBLIC_DATA-polkuun.
     Builderi ei kirjoita osoitetta itse (public_data_url on yksi lukija);
     SPA:n literaali tarkistetaan samaa listaa vasten.
  5. hub-deployn trigger-polut kattavat PUBLIC_DATA:n ja _redirectsin.
  6. Fail-safe: site-push ajetaan vain secretilla, direct upload ohitetaan
     vain eksplisiittisella moodilla, ja moodi ilman tokenia on virhe.
  7. push_site_repo.sh riisuu skip-ci-merkinnan ja kayttaa lahdecommitin
     aikaleimaa; site-repon template-deploy suojaa samat polut kuin push.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import site_output as so  # noqa: E402

HUB = ROOT / ".github" / "workflows" / "hub-deploy.yml"
PUSH = ROOT / "scripts" / "push_site_repo.sh"
TEMPLATE = ROOT / ".github" / "site-repo" / "deploy.yml"


def _hub_doc() -> dict:
    return yaml.safe_load(HUB.read_text(encoding="utf-8"))


def _hub_steps() -> dict[str, dict]:
    (job,) = _hub_doc()["jobs"].values()
    return {s.get("name", s.get("uses", "")): s for s in job["steps"]}


# --- 1. yksi lahde -----------------------------------------------------------

def test_hub_deploy_kokoaa_stagingin_site_outputilla():
    steps = _hub_steps()
    run = steps["Kokoa staging"]["run"]
    assert "scripts/site_output.py stage" in run
    teksti = "\n".join(
        r for r in HUB.read_text(encoding="utf-8").splitlines()
        if not r.strip().startswith("#"))
    assert "grep -vE" not in teksti, "hub-deploy.yml:ssa on oma suodatin"
    assert "ls-files" not in teksti, "hub-deploy.yml suodattaa itse git ls-filesia"


# --- 2. lista = vanha suodatin + PUBLIC_DATA ---------------------------------

@pytest.mark.parametrize("polku", [
    "index.html", "fpl.html", "404.html", "_redirects", "ref-bridge.js",
    "favicon.ico", "robots.txt", "llms.txt", "sitemap.xml",
    "fpl/points.html", "fpl/points/gw1.html", "ucl/index.html",
    "predictions/premier-league/arsenal-vs-chelsea.html",
    "assets/brand/og/fpl-1200x630.png",
    "data/gw_calls.json", "data/fpl_xp_frozen/gw3.json",
    "data/spl_deadline_snapshots/gw6.json",
])
def test_sivustoon_kuuluu(polku):
    assert so.is_site_path(polku), polku


@pytest.mark.parametrize("polku", [
    # 16.8: nama kaksi olivat ensimmaisessa kasin kootussa listassa.
    "pages/5_Optuna_tuning.py", "assets/brand/gen_classic_favicon.py",
    "scripts/site_output.py", "scripts/push_site_repo.sh",
    "src/models/fpl_xp.py", "tests/test_site_output_single_source.py",
    "README.md", "DEPLOY.md", "CLAUDE.md", "render.yaml", "requirements.txt",
    "requirements-api.txt", "app.py", "config.py", ".gitignore",
    ".github/workflows/hub-deploy.yml", ".github/site-repo/deploy.yml",
    ".github/site-repo/README.md", "web/pro-spa/src/routes/spl/+page.svelte",
    "supabase/migrations/x.sql", "api/main.py", "notebooks/01_full_pipeline.ipynb",
    "data/prediction_log.json", "data/fpl_xp_projections.json",
    "data/fpl_2526_archive.tar.gz", "data/international_results.csv",
    "data/model_squad_exceptions/gw2.json", "data/fpl_elite_managers.csv",
    "outputs/cards/x.png", "docs/arkkitehtuuri.md",
])
def test_sivustoon_ei_kuulu(polku):
    assert not so.is_site_path(polku), polku


def test_nykyinen_repo_tuottaa_vain_sallittuja_hakemistoja():
    """Ylatason hakemistot ovat tunnettu joukko; data/ vain PUBLIC_DATA."""
    polut = so.site_paths(so.tracked_files())
    assert len(polut) > 1000, len(polut)
    ylatasot = {p.split("/", 1)[0] for p in polut if "/" in p}
    assert ylatasot <= {"predictions", "fpl", "assets", "ucl", "data"}, ylatasot
    for p in polut:
        if p.startswith("data/"):
            assert so.is_public_data(p), p
        assert not p.endswith(so.EXCLUDED_SUFFIXES), p
    for avain in so.PUBLIC_DATA:
        assert any(p == avain or p.startswith(avain) for p in polut), (
            f"PUBLIC_DATA {avain} ei tuota yhtaan tiedostoa stagingiin")


# --- 3. poikkeuslista ---------------------------------------------------------

@pytest.mark.parametrize("avain,syy", list(so.PUBLIC_DATA.items()))
def test_public_data_rivilla_on_perustelu_ja_polku(avain, syy):
    assert len(syy.strip()) >= 20, f"{avain}: perustelu puuttuu"
    kohde = ROOT / avain
    if avain.endswith("/"):
        assert kohde.is_dir() and any(kohde.iterdir()), f"{avain}: tyhja tai puuttuu"
    else:
        assert kohde.is_file(), f"{avain}: tiedostoa ei ole repossa"


def test_public_data_selite_kattaa_jokaisen_rivin(tmp_path):
    """Julkinen MANIFEST.md syntyy stagingiin ja nimeaa jokaisen
    PUBLIC_DATA-polun; avaimet ovat tasan samat (rivi ilman selitetta tai
    selite ilman rivia kaataa)."""
    assert set(so.PUBLIC_DATA_CITED_BY) == set(so.PUBLIC_DATA)
    for avain, selite in so.PUBLIC_DATA_CITED_BY.items():
        assert "goaliq.app" in selite and len(selite) >= 40, avain
    teksti = so.manifest_text()
    for avain in so.PUBLIC_DATA:
        assert f"`{avain}`" in teksti
    n = so.stage(tmp_path)
    man = tmp_path / "data" / "MANIFEST.md"
    assert man.is_file() and man.read_text(encoding="utf-8") == teksti
    assert n == sum(1 for _ in tmp_path.rglob("*") if _.is_file()), "stage() palauttaa eri maaran kuin kirjoitti"


# --- 4. linkit ----------------------------------------------------------------

_LINK_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/(blob|tree)/main/(data/[^\"'<>\s)]+)")


def test_public_data_url_muoto():
    assert so.public_data_url("data/gw_calls.json") == (
        f"https://github.com/{so.PUBLIC_REPO}/blob/main/data/gw_calls.json")
    assert so.public_data_url("data/fpl_xp_frozen/") == (
        f"https://github.com/{so.PUBLIC_REPO}/tree/main/data/fpl_xp_frozen")
    assert so.public_data_url("data/fpl_xp_frozen") == so.public_data_url("data/fpl_xp_frozen/")
    with pytest.raises(KeyError):
        so.public_data_url("data/prediction_log.json")


def test_builderit_eivat_kirjoita_github_osoitetta_itse():
    """Yksi lukija: osoite tulee public_data_url:sta, ei literaalista."""
    rikkojat = []
    for p in sorted((ROOT / "scripts").glob("build_*.py")):
        for i, rivi in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "github.com/" in rivi and "data/" in rivi and not rivi.strip().startswith("#"):
                rikkojat.append(f"{p.name}:{i}")
    assert not rikkojat, "GitHub-data-linkki literaalina builderissa: " + ", ".join(rikkojat)


def test_kaikki_data_linkit_osoittavat_public_dataan():
    """SPA + skriptit: jokainen GitHub-data-linkki on PUBLIC_DATA-polku
    JA nykyisella isannalla. Isannan vaihto (vaihe 4) on yksi rivi
    site_output.py:ssa, ja tama testi kaataa jokaisen pinnan joka jai
    vanhaan isantaan."""
    tiedostot = list((ROOT / "scripts").glob("*.py"))
    tiedostot += list((ROOT / "web" / "pro-spa" / "src").rglob("*.svelte"))
    tiedostot += list((ROOT / "web" / "pro-spa" / "src").rglob("*.ts"))
    loydetty = 0
    viat = []
    for p in tiedostot:
        for m in _LINK_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
            loydetty += 1
            repo, kind, polku = m.groups()
            if repo != so.PUBLIC_REPO:
                viat.append(f"{p.name}: {repo} != {so.PUBLIC_REPO}")
            if not so.is_public_data(polku.rstrip("/") + ("/" if kind == "tree" else "")):
                viat.append(f"{p.name}: {polku} ei ole PUBLIC_DATA-listalla")
    assert loydetty >= 1, "kontrolli: yhtaan data-linkkia ei loytynyt (SPA /spl?)"
    assert not viat, "\n".join(viat)


def test_linkkiregex_nakee_tunnetun_linkin():
    m = _LINK_RE.search('href="https://github.com/GoalIQ/x/tree/main/data/spl_deadline_snapshots"')
    assert m and m.group(3) == "data/spl_deadline_snapshots"


# --- 5. trigger-polut ---------------------------------------------------------

def test_hub_deploy_trigger_kattaa_public_datan_ja_redirectsin():
    paths = _hub_doc()[True]["push"]["paths"]  # yaml lukee `on:` avaimen True:ksi
    assert "_redirects" in paths
    for avain in so.PUBLIC_DATA:
        odotettu = avain + "**" if avain.endswith("/") else avain
        assert odotettu in paths, f"trigger ei kata {avain} (odotettiin {odotettu})"


# --- 6. fail-safe -------------------------------------------------------------

def test_site_push_vain_secretilla_ja_direct_upload_oletuksena():
    (job,) = _hub_doc()["jobs"].values()
    env = job["env"]
    assert env["SITE_DEPLOY_TOKEN"] == "${{ secrets.SITE_DEPLOY_TOKEN }}"
    assert env["SITE_PUBLISH"] == "${{ vars.SITE_PUBLISH }}"
    steps = _hub_steps()
    push = steps["Push output site-repoon"]
    assert push["if"] == "env.SITE_DEPLOY_TOKEN != ''"
    assert "scripts/push_site_repo.sh" in push["run"]
    cf = steps["Deploy Cloudflare Pagesiin"]
    assert cf["if"] == "env.SITE_PUBLISH != 'site'"
    assert "goaliq-hub" in cf["with"]["command"]
    # Verifiointi domainilta on ehdoton: ei `if:`-ehtoa.
    assert "if" not in steps["Verifioi domainilta"]


def test_moodi_site_ilman_tokenia_on_virhe():
    run = _hub_steps()["Portti - julkaisumoodi on ehja"]["run"]
    assert '= "site"' in run and "-z \"${SITE_DEPLOY_TOKEN" in run and "exit 1" in run


# --- 7. push-skripti ja template ------------------------------------------------

def _sed_lauseke() -> str:
    m = re.search(r"SRC_SUBJ=.*\| sed -E '([^']+)'", PUSH.read_text(encoding="utf-8"))
    assert m, "push_site_repo.sh ei riisu commit-otsikkoa sedilla"
    return m.group(1)


def test_push_skripti_riisuu_skip_ci_merkinnan():
    lauseke = _sed_lauseke()
    assert "skip" in lauseke and "ci" in lauseke
    bash = shutil.which("bash")
    if sys.platform == "win32" or not bash:
        pytest.skip("sed-lauseke ajetaan vain POSIX-ymparistossa (CI)")
    for otsikko in ("chore(fpl): refresh [skip ci]", "x [ci skip] y", "z [skip actions]"):
        ulos = subprocess.run(["sed", "-E", lauseke], input=otsikko, capture_output=True,
                              text=True, check=True).stdout.strip()
        assert "[" not in ulos, (otsikko, ulos)
    ulos = subprocess.run(["sed", "-E", lauseke], input="geo(fpl): [GW4] refresh",
                          capture_output=True, text=True, check=True).stdout.strip()
    assert ulos == "geo(fpl): [GW4] refresh", "muut hakasulkeet on sailytettava"


def test_push_skripti_kayttaa_lahdecommitin_aikaleimaa():
    s = PUSH.read_text(encoding="utf-8")
    assert "git log -1 --format=%cI HEAD" in s
    assert 'GIT_COMMITTER_DATE="$SRC_DATE"' in s and 'GIT_AUTHOR_DATE="$SRC_DATE"' in s
    assert "source: football-prediction@${SRC_SHA}" in s
    assert ": \"${SITE_DEPLOY_TOKEN:?" in s, "skripti ei kaadu ilman secretia"


def test_push_ja_template_suojaavat_samat_polut():
    """push_site_repo.sh jattaa .github ja README.md site-repon omiksi;
    template-deploy jattaa samat pois stagingista. Jos toinen muuttuu,
    toinen on muutettava - ja tama huutaa."""
    s = PUSH.read_text(encoding="utf-8")
    assert "! -name .github ! -name README.md" in s
    t = TEMPLATE.read_text(encoding="utf-8")
    assert ".github/*|README.md) continue" in t


def test_template_deploy_on_ehja_workflow():
    doc = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    assert doc[True]["push"]["branches"] == ["main"]
    (job,) = doc["jobs"].values()
    nimet = [s.get("name", "") for s in job["steps"]]
    assert "Portti - ei lahdekoodia" in nimet and "Verifioi domainilta" in nimet
    cf = next(s for s in job["steps"] if s.get("uses", "").startswith("cloudflare/wrangler-action"))
    assert "--project-name=goaliq-hub" in cf["with"]["command"]
