# -*- coding: utf-8 -*-
"""render.yaml buildFilter: data-bottien commitit EIVAT saa laukaista buildia.

TAUSTA (mitattu 1.9.2026): 924 deployta 2.8. alkaen, mediaani 2,2 min, eli
~2 100 build-minuuttia kun kiintio on 500/kk. Suodatin oli olemassa 14.7.
lahtien mutta vuoti: se kattoi `data/**` ja `**/*.html`, kun bottien commitit
koskevat myos JUURITASON `index.html`/`fpl.html`/`predictions.html` -tiedostoja
seka `predictions/**`, `fpl/**` ja `sitemap-*.xml` -polkuja.

Tama testi ajaa oikeiden bottikommittien tiedostolistat suodattimen lapi.
Se on kirjoitettu KONSERVATIIVISELLA glob-semantiikalla: `**/*.html` EI oleteta
osuvan juuritason tiedostoon. Jos Renderin oma matcher on sallivampi, olemme
silti oikeassa - vain toisin pain ei.

Polkulistat on poimittu naista committeista:
  43b2db574  chore(accuracy): auto-log pre-match + reconcile
  445145c12  chore(accuracy): auto-log pre-match + reconcile
  e39fad7ba  chore(fpl): daily projections refresh (availability)
"""
import fnmatch
from pathlib import Path

import pytest
import yaml

RENDER_YAML = Path(__file__).resolve().parents[1] / "render.yaml"


def _ignored_paths() -> list[str]:
    doc = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    svc = next(s for s in doc["services"] if s["name"] == "goaliq-api")
    return list(svc["buildFilter"]["ignoredPaths"])


def _matches(path: str, pattern: str) -> bool:
    """Konservatiivinen glob.

    `dir/**` osuu kaikkeen hakemiston alla. `**/*.ext` osuu VAIN kun polussa on
    hakemisto (juuritason tiedosto ei osu) - juuri se oletus jonka varassa
    vanha suodatin vuoti. Tarkka literaali osuu sellaisenaan.
    """
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    if pattern.startswith("**/"):
        return "/" in path and fnmatch.fnmatch(path, pattern)
    return fnmatch.fnmatch(path, pattern)


def _build_skipped(paths: list[str], patterns: list[str] | None = None) -> bool:
    """Render skippaa buildin kun KAIKKI muuttuneet tiedostot ovat ignoroituja."""
    pats = patterns if patterns is not None else _ignored_paths()
    return all(any(_matches(p, pat) for pat in pats) for p in paths)


ACCURACY_BOT = [
    "data/accuracy.json",
    "data/prediction_log.json",
    "predictions.html",
    "index.html",
    "fpl.html",
    "llms.txt",
    "sitemap-predictions.xml",
    "predictions/brasileirao/flamengo-rj-vs-mirassol.html",
    "predictions/brasileirao/index.html",
]
FPL_REFRESH_BOT = [
    "data/fpl_xp_projections.json",
    "fpl/player-gw.json",
    "fpl/expected-points.html",
    "fpl/club/arsenal.html",
    "fpl.html",
    "sitemap-fpl.xml",
]
GEO_BOT = [
    "fpl.html",
    "index.html",
    "fpl/notes.html",
    "sitemap-core.xml",
    "outputs/cards/goaliq_standouts_gw3.png",
]

BOT_COMMITS = {
    "accuracy-autolog": ACCURACY_BOT,
    "fpl-refresh": FPL_REFRESH_BOT,
    "geo-refresh": GEO_BOT,
}


@pytest.mark.parametrize("name,paths", list(BOT_COMMITS.items()))
def test_bottikommitti_ei_laukaise_buildia(name, paths):
    leaking = [p for p in paths if not any(_matches(p, pat) for pat in _ignored_paths())]
    assert not leaking, f"{name} vuotaa buildiin: {leaking}"


def test_koodimuutos_laukaisee_buildin_yha():
    """NEGATIIVINEN KONTROLLI. Suodatin joka ignoroi kaiken ei ole suodatin
    vaan autoDeploy: false, ja silloin koodikorjaus ei paase tuotantoon."""
    for path in ("api/main.py", "src/models/fpl_rate_team.py",
                 "requirements-api.txt", "render.yaml"):
        assert not _build_skipped([path]), f"{path} EI saa olla ignoroitu"


def test_sekakommitti_laukaisee_buildin():
    """Yksikin koodimuutos riittaa: data + koodi samassa committissa deployataan."""
    assert not _build_skipped(ACCURACY_BOT + ["api/main.py"])


def test_juuritason_html_kaytannon_mutaatio():
    """MUTAATIO: jos juuritason `*.html` poistetaan listalta, accuracy-botti
    alkaa taas laukaista buildia. Tama on TASAN se vuoto joka mitattiin 1.9,
    ja ilman tata testia sama korjaus voi kadota uudelleen."""
    pats = [p for p in _ignored_paths() if p != "*.html"]
    assert not _build_skipped(ACCURACY_BOT, pats), (
        "testi ei erota juuritason kuviota - matcher on liian salliva"
    )
    assert _build_skipped(ACCURACY_BOT), "korjattu suodatin ei kata bottia"


def test_fpl_data_on_ignoroitu_ja_paivittainen_deploy_on_olemassa():
    """`fpl/player-gw.json` on API:n lukema tiedosto, joten sen ignorointi on
    perusteltu VAIN koska render-daily-deploy.yml vie datan kerran vuorokaudessa.
    Jos se workflow katoaa, tama ignorointi jaadyttaa toteumat."""
    assert any(_matches("fpl/player-gw.json", p) for p in _ignored_paths())
    wf = RENDER_YAML.parent / ".github" / "workflows" / "render-daily-deploy.yml"
    assert wf.is_file(), "fpl/** on ignoroitu mutta paivittaista deployta ei ole"
