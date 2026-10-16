"""Auto-kehityksen ja aallonharjan turvainvariantit työnkuluissa (16.10.2026).

Agentti ajetaan repossa, jossa on tuotantosalaisuuksia (Stripe, Cloudflare, Render-hook) ja jonka main
deployaa tuotantoon. Turva ei saa olla promptin varassa. Tämä portti kaatuu, jos
  * agentin työ saa kirjoitusoikeuden tai checkout jättää tunnukset agentin gitille,
  * työnkulku viittaa muuhun salaisuuteen kuin tilauksen OAuth-tokeniin (0 euron sääntö, ei API-avainta),
  * agentin työkalulistaan tulee gh, curl tai wget,
  * julkaisutyö pushaa ennen kieltoporttia, ajaa portin agentin haaran versiosta tai pushaa muuhun kuin
    omaan haaraansa,
  * jokin työ mergeää tai deployaa.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

JUURI = Path(__file__).resolve().parent.parent
WF = JUURI / ".github" / "workflows"
AGENTTITYONKULUT = {"auto-kehitys.yml": "kehitys", "aallonharja.yml": "aallonharja"}


def _lue(nimi):
    teksti = (WF / nimi).read_text(encoding="utf-8")
    return teksti, yaml.safe_load(teksti)


def _agenttiaskel(job):
    return [s for s in job.get("steps", []) if "claude-code-action" in str(s.get("uses", ""))]


@pytest.mark.parametrize("nimi", sorted(AGENTTITYONKULUT))
def test_agentilla_vain_lukuoikeus(nimi):
    _, doc = _lue(nimi)
    agenttityot = [j for j in doc["jobs"].values() if _agenttiaskel(j)]
    assert len(agenttityot) == 1, "täsmälleen yksi agenttityö"
    job = agenttityot[0]
    perms = job.get("permissions")
    assert isinstance(perms, dict), "agenttityölle oikeudet eksplisiittisesti (muuten oletus voi olla write)"
    assert all(v in ("read", "none") for v in perms.values()), perms
    checkout = [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
    assert checkout and all((s.get("with") or {}).get("persist-credentials") is False for s in checkout)


@pytest.mark.parametrize("nimi", sorted(AGENTTITYONKULUT))
def test_vain_tilauksen_token(nimi):
    teksti, _ = _lue(nimi)
    assert "ANTHROPIC_API_KEY" not in teksti
    assert "anthropic_api_key" not in teksti
    salaisuudet = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", teksti))
    assert salaisuudet <= {"CLAUDE_CODE_OAUTH_TOKEN", "GITHUB_TOKEN"}, salaisuudet


@pytest.mark.parametrize("nimi", sorted(AGENTTITYONKULUT))
def test_agentin_tyokaluissa_ei_verkko_eika_gh(nimi):
    _, doc = _lue(nimi)
    for job in doc["jobs"].values():
        for s in _agenttiaskel(job):
            args = s["with"]["claude_args"]
            tyokalut = re.search(r'--allowedTools "([^"]+)"', args).group(1)
            for kielletty in ("Bash(gh", "Bash(curl", "Bash(wget", "Bash(npx wrangler"):
                assert kielletty not in tyokalut, kielletty


@pytest.mark.parametrize("nimi,profiili", sorted(AGENTTITYONKULUT.items()))
def test_julkaisu_portin_jalkeen_mainin_versiosta(nimi, profiili):
    _, doc = _lue(nimi)
    job = doc["jobs"]["julkaise"]
    assert job.get("needs") == "agentti"
    runit = [str(s.get("run") or "") for s in job["steps"]]
    portti = [i for i, r in enumerate(runit) if "git show origin/main:.github/auto-kehitys/guard.py" in r]
    assert portti, "portti luetaan mainista, ei agentin haarasta"
    assert f"--profile {profiili}" in runit[portti[0]]
    pushit = [i for i, r in enumerate(runit) if "git push" in r]
    assert pushit and min(pushit) > portti[0], "push vasta portin jälkeen"
    for i in pushit:
        assert 'git push origin "refs/heads/$HAARA:refs/heads/$HAARA"' in runit[i]
        assert "main" not in re.sub(r"--base main", "", runit[i].split("git push", 1)[1].splitlines()[0])


@pytest.mark.parametrize("nimi", sorted(AGENTTITYONKULUT) + ["auto-pr-muistutus.yml"])
def test_ei_mergea_eika_deployta(nimi):
    teksti, _ = _lue(nimi)
    for kielletty in ("gh pr merge", "wrangler", "pages deploy", "RENDER_DEPLOY_HOOK", "pro-spa-deploy.yml --ref",
                      "push origin main", "HEAD:main"):
        assert kielletty not in teksti, kielletty
