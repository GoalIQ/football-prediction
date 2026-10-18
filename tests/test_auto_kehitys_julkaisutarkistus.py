"""Julkaisutarkistaja CI:ssä (18.10.2026, Villen GO, automaatiokohta 2).

Portti kaatuu, jos
  * poiminta päästää käyttäjälle näkyvän tekstin läpi "ei muutoksia" -väitteellä (diff voittaa rungon),
  * tarkistajan ohje tai tulosportti luetaan PR:n haarasta eikä mainista (agentti voisi löysätä niitä),
  * tarkistustyö saa kirjoitusoikeuden tai työnkulku voi mergetä,
  * auto-kehitys lakkaa käynnistämästä tarkistusta PR:n avattuaan.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

JUURI = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("auto_jt", JUURI / ".github" / "auto-kehitys" / "julkinen_teksti.py")
jt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jt)
WF = JUURI / ".github" / "workflows"


def test_osio_ja_ei_muutoksia():
    runko = ("Riskiluokka: julkaiseva\nMittari: x\n\n## Mitä\nteki\n\n## Julkinen teksti\nei muutoksia\n\n"
             "## Free vai Premium\nilmainen\n")
    assert jt.osio(runko) == "ei muutoksia" and jt.ei_muutoksia(jt.osio(runko))
    runko2 = "**Julkinen teksti:** ei muutoksia.\n**Julkaisu:** pro-spa-deploy\n"
    assert jt.ei_muutoksia(jt.osio(runko2))
    runko3 = "## Julkinen teksti\n- \"Captain pick for your team\"\n- \"No data yet\"\n## Riskit\n- ei\n"
    o = jt.osio(runko3)
    assert "Captain pick" in o and "Riskit" not in o and not jt.ei_muutoksia(o)


DIFF = """diff --git a/web/pro-spa/src/lib/X.svelte b/web/pro-spa/src/lib/X.svelte
+++ b/web/pro-spa/src/lib/X.svelte
+<p class="hint">Your captain pick for this gameweek</p>
+  // kommentti jota ei näytetä käyttäjälle lainkaan
+++ b/tests/test_x.py
+    assert "this is a test string here" in out
+++ b/src/models/fpl_xp.py
+    meta["caveat"] = "Players on loan cannot face their parent club"
+    x = "ab"
"""


def test_diff_voittaa_rungon():
    poimitut = jt.poimi_diffista(DIFF)
    tekstit = [t for _, t in poimitut]
    assert "Your captain pick for this gameweek" in tekstit
    assert "Players on loan cannot face their parent club" in tekstit
    assert not any("test string" in t or "kommentti" in t for t in tekstit)
    tarvitaan, syote = jt.rakenna("## Julkinen teksti\nei muutoksia\n", DIFF)
    assert tarvitaan, "agentin 'ei muutoksia' ei saa ohittaa diffissä näkyvää tekstiä"
    assert "Your captain pick" in syote


def test_ei_tekstia_ei_claudea():
    tarvitaan, _ = jt.rakenna("## Julkinen teksti\nei muutoksia\n", "+++ b/src/x.py\n+    y = 1\n")
    assert not tarvitaan


def _doc(nimi):
    return yaml.safe_load((WF / nimi).read_text(encoding="utf-8"))


def test_tarkistus_lukee_ohjeen_ja_portit_mainista_ja_on_vain_luku():
    doc = _doc("julkaisutarkistus.yml")
    teksti = (WF / "julkaisutarkistus.yml").read_text(encoding="utf-8")
    assert "git show origin/main:.claude/agents/julkaisutarkistaja-ci.md" in teksti
    assert "git show origin/main:.github/auto-kehitys/julkinen_teksti.py" in teksti
    assert "git show origin/main:.github/auto-kehitys/tulos.py" in teksti
    for nimi in ("poimi", "tarkista"):
        job = doc["jobs"][nimi]
        assert all(v in ("read", "none") for v in job["permissions"].values()), nimi
        for s in job["steps"]:
            if str(s.get("uses", "")).startswith("actions/checkout"):
                assert s["with"]["persist-credentials"] is False
    # Ohje kopioidaan ennen kuin PR:n haara checkoutataan.
    run = str(next(s for s in doc["jobs"]["tarkista"]["steps"] if "ohje.md" in str(s.get("run", "")))["run"])
    assert run.index("ohje.md") < run.index("git checkout")
    for kielletty in ("gh pr merge", "push origin", "HEAD:main", "wrangler", "RENDER_DEPLOY_HOOK"):
        assert kielletty not in teksti
    kommentoi = doc["jobs"]["kommentoi"]
    assert not any("claude-code-action" in str(s.get("uses", "")) for s in kommentoi["steps"])


def test_vain_auto_haarat():
    run = str(next(s for s in _doc("julkaisutarkistus.yml")["jobs"]["poimi"]["steps"]
                   if s.get("id") == "pr")["run"])
    assert "auto/*" in run and "*[!0-9]*" in run


def test_auto_kehitys_kaynnistaa_tarkistuksen():
    run = "\n".join(str(s.get("run", "")) for s in _doc("auto-kehitys.yml")["jobs"]["julkaise"]["steps"])
    assert "gh workflow run julkaisutarkistus.yml" in run
    assert run.index("gh pr create") < run.index("gh workflow run julkaisutarkistus.yml")


def test_ohje_on_olemassa_ja_vaatii_verdiktin():
    ohje = (JUURI / ".claude" / "agents" / "julkaisutarkistaja-ci.md").read_text(encoding="utf-8")
    assert "/tmp/jt/verdikti.md" in ohje and "VERDIKTI: JULKAISTAVISSA | BLOKATTU" in ohje
    assert "personalLock.ts" in ohje
