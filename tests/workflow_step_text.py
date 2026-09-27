"""YKSI lukija workflow-askeleen push-kayttaytymiselle (27.9.2026).

`scripts/ci_push_rebuild.sh` siirsi accuracy-login `git add`- ja
`git push` -rivit run-lohkosta ymparistomuuttujiin. Portit jotka lukevat
run-tekstia (`test_workflow_stage_paths`, `test_workflow_deploy_verify`)
lakkasivat nakemasta niita, eli ne olisivat hiljaa lakanneet mittaamasta
juuri sita workflow'ta jonka push-reitti muuttui. Tama funktio laajentaa
skriptikutsun samoiksi riveiksi, joten jokainen portti nakee saman asian.
"""
from __future__ import annotations

SKRIPTI = "ci_push_rebuild.sh"


def step_run_text(step: dict) -> str:
    """Askeleen run-teksti; ci_push_rebuild.sh-kutsu laajennettuna."""
    run = (step or {}).get("run")
    if not isinstance(run, str):
        return ""
    if SKRIPTI not in run:
        return run
    env = (step or {}).get("env") or {}
    polut = " ".join(str(env.get(k) or "") for k in ("CI_PUSH_DATA", "CI_PUSH_PAGES")).split()
    return run + "\ngit add " + " ".join(polut) + "\ngit push origin HEAD:main\n"


def workflow_text_expanded(path) -> str:
    """Koko workflow-tiedoston teksti + skriptiaskelten laajennetut rivit.

    Portit jotka lukevat raakatekstia (`test_page_deploy_discipline`) eivat
    muuten nae ci_push_rebuild.sh:n git add -polkuja lainkaan.
    """
    import yaml
    from pathlib import Path
    teksti = Path(path).read_text(encoding="utf-8", errors="replace")
    try:
        doc = yaml.safe_load(teksti) or {}
    except yaml.YAMLError:
        return teksti
    lisat = []
    for job in (doc.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            run = (step or {}).get("run")
            if isinstance(run, str) and SKRIPTI in run:
                lisat.append(step_run_text(step)[len(run):])
    return teksti + "".join(lisat)
