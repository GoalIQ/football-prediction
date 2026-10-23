"""Auto-kehityksen kieltoportti (.github/auto-kehitys/guard.py) ja FPL-skeemavahti (16.10.2026).

Portti on ainoa asia agentin ja tuotannon välissä ennen ihmisen mergeä: jos se hyväksyy kielletyn polun
tai sisällön, PR avautuu ja nojaa katselmoijan muistiin. Siksi jokainen kielto ja poikkeus mitataan tässä.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

JUURI = Path(__file__).resolve().parent.parent
KANSIO = JUURI / ".github" / "auto-kehitys"


def _lataa(nimi: str):
    spec = importlib.util.spec_from_file_location(f"auto_{nimi}", KANSIO / f"{nimi}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _lataa("guard")
schema = _lataa("fpl_schema_watch")


@pytest.mark.parametrize("polku", [
    "src/models/fpl_xp.py", "api/main.py", "scripts/build_fpl_page.py", "tests/test_uusi.py",
    "web/pro-spa/src/routes/+page.svelte", "fpl/expected-points.html", "predictions/premier-league/index.html",
    "fpl.html", "llms.txt", "ref-bridge.js", "docs/AUTO-BACKLOG.md",
])
def test_kehitys_sallii_tuotekoodin(polku):
    assert guard.tarkista_polut("kehitys", [polku]) == []


@pytest.mark.parametrize("polku", [
    ".github/workflows/auto-kehitys.yml", ".github/auto-kehitys/guard.py", "docs/TUOTEPERIAATTEET.md",
    "docs/BENCHMARK.md", "CLAUDE.md", "render.yaml", "requirements.txt", "requirements-api.txt",
    "web/pro-spa/package.json", "data/accuracy.json", "data/fpl_schema_snapshot.json", "supabase/x.sql",
    "cf-worker/index.js", "api/premium.py", "src/regional_pricing.py",
    "web/pro-spa/src/routes/checkout/+page.svelte", "index.html", "faq.html", "privacy.html",
    "tests/test_auto_kehitys_guard.py", "tests/test_auto_kehitys_workflow.py", "README.md",
])
def test_kehitys_hylkaa_kielletyn(polku):
    virheet = guard.tarkista_polut("kehitys", [polku])
    assert virheet, polku
    # Eksplisiittinen kielto, ei vain "ei sallituissa": kielto ei saa kadota, jos sallittuja laajennetaan.
    if polku not in ("README.md", "docs/BENCHMARK.md"):
        assert "kielletty" in virheet[0], virheet


def test_aallonharja_sallii_vain_benchmarkin():
    ok = ["docs/BENCHMARK.md", "docs/AUTO-BACKLOG.md", "data/fpl_schema_snapshot.json"]
    assert guard.tarkista_polut("aallonharja", ok) == []
    for p in ("src/models/fpl_xp.py", "data/accuracy.json", "docs/TUOTEPERIAATTEET.md", "fpl/x.html"):
        assert guard.tarkista_polut("aallonharja", [p]), p


def test_poikkeus_koskee_vain_omaa_profiilia():
    assert "data/fpl_schema_snapshot.json" in guard.POIKKEUKSET["aallonharja"]
    assert guard.tarkista_polut("kehitys", ["data/fpl_schema_snapshot.json"])


@pytest.mark.parametrize("rivi", [
    "stripe.Customer.create(email=e)", "key = os.environ['ANTHROPIC_API_KEY']",
    "url = 'https://gaming.uefa.com/en/uclfantasy'", "<p>Premium 3,99 € a month</p>", "Only 3.99",
    "BASE = 'https://understat.com/league/EPL/2026'",
    "<p>Model picks — captain</p>",
])
def test_kielletty_sisalto_tuotantokoodissa(rivi):
    assert guard.tarkista_rivit({"src/x.py": [rivi]})
    assert guard.tarkista_rivit({"tests/test_x.py": [rivi]}) == []
    assert guard.tarkista_rivit({"docs/AUTO-BACKLOG.md": [rivi]}) == []


def test_tavallinen_rivi_lapi():
    assert guard.tarkista_rivit({"src/x.py": ["xp = round(p * 2, 1)  # £7.5m budget"]}) == []


ALATUNNISTE = '<footer>© 2026 GoalIQ · <a href="/predictions">Free</a> · Premium is 3.99 €/month</footer>'


def test_generoidun_sivun_mainissa_oleva_rivi_ei_ole_uutta_tekstia():
    """23.10.2026: ottelusivurivin ajo hylättiin, koska uudelleen luoduilla sivuilla oli mainin
    sivujen oma hinnallinen alatunniste."""
    assert guard.tarkista_rivit({"predictions/serie-a/a-vs-b.html": [ALATUNNISTE]}, {ALATUNNISTE}) == []
    # Negatiivinen kontrolli: ilman mainin vastinetta sama rivi kaatuu.
    assert guard.tarkista_rivit({"predictions/serie-a/a-vs-b.html": [ALATUNNISTE]})
    # Pohja tarkistetaan aina, vaikka sama teksti olisi mainissa.
    assert guard.tarkista_rivit({"scripts/build_prediction_pages.py": [ALATUNNISTE]}, {ALATUNNISTE})
    # Muutettu hinta generoidulla sivulla on uutta tekstiä.
    assert guard.tarkista_rivit({"predictions/serie-a/a-vs-b.html": [ALATUNNISTE.replace("3.99", "4.99")]},
                                {ALATUNNISTE})


def test_koko_raja_ei_laske_generoituja():
    assert guard.tarkista_koko("kehitys", {"src/x.py": 200, "fpl/x.html": 5000, "fpl.html": 900}) == []
    assert guard.tarkista_koko("kehitys", {"src/x.py": 600, "api/main.py": 400})


def test_diffin_jasennys():
    diff = ("diff --git a/src/x.py b/src/x.py\n--- a/src/x.py\n+++ b/src/x.py\n@@ -1 +1,2 @@\n-vanha\n+uusi\n+toinen\n"
            "diff --git a/old.py b/old.py\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-poistettu\n")
    assert guard.jasenna_diff(diff) == {"src/x.py": ["uusi", "toinen"]}
    assert guard.jasenna_numstat("2\t1\tsrc/x.py\n-\t-\tassets/k.png\n") == {"src/x.py": 3, "assets/k.png": 1}


def _git(cwd, *args):
    subprocess.run(("git",) + args, cwd=cwd, check=True, capture_output=True)


def test_main_mittaa_oikeaa_haaraa(tmp_path, monkeypatch):
    # Hookin GIT_*-ympäristö ei saa vuotaa väliaikaiseen repoon (muisti 27.9: worktree muuttui bare-repoksi).
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(k, raising=False)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "checkout", "-q", "-b", "auto/tyhja")
    assert guard.main(["--profile", "kehitys", "--base", "main", "--head", "auto/tyhja"]) == 3
    (tmp_path / "src" / "a.py").write_text("x = 2\n")
    _git(tmp_path, "commit", "-q", "-am", "ok")
    assert guard.main(["--profile", "kehitys", "--base", "main", "--head", "auto/tyhja"]) == 0
    (tmp_path / "render.yaml").write_text("services: []\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "kielletty")
    assert guard.main(["--profile", "kehitys", "--base", "main", "--head", "auto/tyhja"]) == 1


def test_main_sallii_mainin_alatunnisteen_uudella_generoidulla_sivulla(tmp_path, monkeypatch):
    """Kutsupaikka: main() hakee mainin rivit git grepillä ja antaa ne rivikiellolle. Tiedostot tavuina:
    Windowsin write_text kirjoittaisi CRLF:n, jolloin git grep -x ei osu (CI ajaa Linuxilla)."""
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(k, raising=False)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    sivut = tmp_path / "predictions" / "serie-a"
    sivut.mkdir(parents=True)
    (sivut / "a-vs-b.html").write_bytes(f"<h1>A v B</h1>\n{ALATUNNISTE}\n".encode("utf-8"))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "checkout", "-q", "-b", "auto/sivut")
    (sivut / "c-vs-d.html").write_bytes(f"<h1>C v D</h1>\n{ALATUNNISTE}\n".encode("utf-8"))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "sama alatunniste")
    assert guard.main(["--profile", "kehitys", "--base", "main", "--head", "auto/sivut"]) == 0
    # Osa mainin rivistä ei ole sama rivi: git grep -F osuisi, koko rivin vertailu ei.
    (sivut / "g-vs-h.html").write_bytes("Premium is 3.99 €/month\n".encode("utf-8"))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "osa rivista")
    assert guard.main(["--profile", "kehitys", "--base", "main", "--head", "auto/sivut"]) == 1
    _git(tmp_path, "rm", "-q", str(sivut / "g-vs-h.html"))
    _git(tmp_path, "commit", "-q", "-m", "pois")
    (sivut / "e-vs-f.html").write_bytes(
        f"<h1>E v F</h1>\n{ALATUNNISTE.replace('3.99', '4.99')}\n".encode("utf-8"))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "uusi hinta")
    assert guard.main(["--profile", "kehitys", "--base", "main", "--head", "auto/sivut"]) == 1


BOOT = {
    "events": [{"id": 1, "deadline_time": "x"}],
    "teams": [{"id": 1, "name": "A"}],
    "elements": [{"id": 1, "web_name": "P", "defensive_contribution": 3}],
    "element_stats": [{"name": "minutes"}, {"name": "defensive_contribution"}],
    "element_types": [{"singular_name_short": "DEF", "squad_select": 5}],
    "chips": [{"name": "wildcard", "start_event": 2, "stop_event": 19}],
    "game_settings": {"squad_squadsize": 15, "timezone": "UTC"},
    "game_config": {"scoring": {"goals_scored": {"DEF": 6}}, "rules": {"max_extra_free_transfers": 4}},
}


def test_skeema_havaitsee_uuden_kentan_chipin_ja_saannon():
    import copy
    vanha = schema.tilannekuva(BOOT)
    b = copy.deepcopy(BOOT)
    b["elements"][0]["expected_bonus"] = 1.2
    b["chips"].append({"name": "assistant_manager", "start_event": 20, "stop_event": 38})
    b["game_config"]["scoring"]["goals_scored"]["DEF"] = 5
    b["game_settings"]["new_flag"] = True
    rivit = "\n".join(schema.erot(vanha, schema.tilannekuva(b)))
    assert "expected_bonus" in rivit
    assert "assistant_manager gw20-38" in rivit
    assert "goals_scored.DEF 6 -> 5" in rivit
    assert "new_flag" in rivit


def test_skeema_ensimmainen_ja_muuttumaton():
    s = schema.tilannekuva(BOOT)
    assert "ensimmäinen" in schema.raportti(None, s)
    assert "ei muutoksia" in schema.raportti(s, s)
    assert schema.erot(s, s) == []
