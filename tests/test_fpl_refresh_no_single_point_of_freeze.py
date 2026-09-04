"""Portti: yksikaan askel ei saa padota `fpl-data-refresh`in committia.

TAUSTA (4.9.2026, NELJAS KERTA). `Freeze model squad at deadline window`
kaatui kolmena yona putkeen (3.9 22:53, 4.9 02:02, 4.9 07:32) koska GW3:n
runko peri seurakaton ylityksen ({15: 4}). Askel oli fail-fast, joten sen
jalkeiset YHDEKSAN askelta ja `Commit + push` skipattiin: gw-calls,
entry-vahti, founder stats, leaders, stats, player-gw, BTM-gradaus ja pushit.
Mitaan ei committoitu 9 tuntiin.

Sama vikaluokka on osunut ennenkin, aina eri askeleesta:
  * 21.-22.8 `build_fpl_stats`        -> 5 punaista ajoa, KAIKKI data jaassa
  * 26.-27.8 `build_team_confidence`  -> 3 ajoa, commit + GW2-freeze skipattu
  * 29.8     `grade_model_squad_gw`   -> toinen jaatyminen samana aamuna
  * 3.-4.9   `freeze_model_squad_gw`  -> 3 ajoa

Joka kerta korjaus oli sama (`continue-on-error` + Step health) ja se tehtiin
YHDELLE askeleelle. Seuraava uusi askel toi vian takaisin. Tama portti tekee
vaarasta vaihtoehdosta mahdottoman: committia edeltava askel on
continue-on-error, tai sen nimi on alla olevalla poikkeuslistalla PERUSTELUN
kanssa. Unohduksesta syntyva pato on nyt mahdoton; tietoinen valinta nakyy
diffissa.

Toinen puoli samasta asiasta: `continue-on-error` ilman Step health -rivia on
fail-open - askel voi kaatua vihrean ajon takana (accuracy-log 9.8: 26
punaista ajoa joita kukaan ei nahnyt). Siksi kaksi ERILLISTA testia omine
negatiivisine kontrolleineen.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "fpl-data-refresh.yml"

COMMIT_STEP = "Commit + push to main (Render serves fresh data)"
HEALTH_STEP = "Step health (fail loud, data jo pushattu)"

# ---------------------------------------------------------------------------
# POIKKEUSLISTA 1: askel SAA kaatua ennen committia. Jokainen rivi on
# tietoinen valinta ja vaatii perustelun. Uusi askel EI paady tanne
# vahingossa - testi kaatuu ja kirjoittaja joutuu kirjoittamaan miksi.
# ---------------------------------------------------------------------------
SALLITTU_FAIL_FAST: dict[str, str] = {
    "Checkout main":
        "Ilman tyopuuta ei ole mitaan committoitavaa.",
    "Deadline-day guard (only for 09:15 run)":
        "Portti paattaa ajetaanko ajo lainkaan; se on koko jobin ehto.",
    "Setup Python 3.11":
        "Ilman tulkkia yksikaan builderi ei aja.",
    "Compute cache week":
        "Cache-avain; ilman sita seuraava askel kaatuisi joka tapauksessa.",
    "Cache soccerdata (Understat)":
        "Cachen palautus; sen kaatuminen tarkoittaa etta builderit ajavat "
        "kylmana eika tuotos ole luotettava.",
    "Install builder deps":
        "Ilman riippuvuuksia yksikaan builderi ei aja.",
    "Unpack frozen 2025/26 FPL archive":
        "Jaadytetty kausiarkisto on kaikkien buildereiden syote.",
    "Build Phase 0 projections (CS% + FDR)":
        "Ydinartefakti jonka jokainen alavirran lukija lukee. Kaatuminen voi "
        "osua kesken kirjoituksen, ja osittainen artefakti EI saa paatya "
        "committiin (muisti: osittainen data myrkyttaa cachen).",
    "Build Phase 1 xP projections":
        "Sama kuin Phase 0: ydinartefakti, osittaista ei saa committoida.",
    "Gate - xP headline gameweek is actionable":
        "Portti ajetaan builderin JALKEEN, eli virheellinen artefakti on jo "
        "levylla. Ainoa asia joka estaa sen julkaisun on juuri se, etta tama "
        "kaatuminen skippaa committin. Talla askeleella pato ON korjaus.",
}

# ---------------------------------------------------------------------------
# POIKKEUSLISTA 2: continue-on-error-askel joka EI ole Step healthissa, eli
# saa kaatua ajon punaamatta. Vain SPL - Villen ehto 7.8: SPL ei saa koskaan
# kaataa FPL-refreshia, ja pysyvasti punainen ajo tulee ohitetuksi.
# ---------------------------------------------------------------------------
SALLITTU_VAROITUS_VAIN: dict[str, str] = {
    "Vendor missing SPL deadline snapshots":
        "SPL ei saa punata FPL-refreshia (Villen ehto 7.8).",
    "Build SPL clean sheet reconciliation":
        "SPL ei saa punata FPL-refreshia (Villen ehto 7.8).",
    "Build SPL Phase 0 projections (CS% + FDR)":
        "SPL ei saa punata FPL-refreshia (Villen ehto 7.8).",
    "Build SPL xP projections":
        "SPL ei saa punata FPL-refreshia (Villen ehto 7.8).",
    "Sync SPL page data basis from the artefact":
        "SPL ei saa punata FPL-refreshia (Villen ehto 7.8).",
}


def _steps(doc: dict) -> list[dict]:
    return doc["jobs"]["build-and-commit"]["steps"]


def _lataa() -> dict:
    return yaml.safe_load(WF.read_text(encoding="utf-8"))


def _ennen_committia(steps: list[dict]) -> list[dict]:
    nimet = [s.get("name") for s in steps]
    assert COMMIT_STEP in nimet, (
        "Commit-askelen nimi on muuttunut - portti mittaisi tyhjaa. "
        "Nimet: %s" % (nimet,))
    return steps[:nimet.index(COMMIT_STEP)]


def _health_teksti(steps: list[dict]) -> str:
    for s in steps:
        if s.get("name") == HEALTH_STEP:
            return s.get("run") or ""
    raise AssertionError(
        "Step health -askelta %r ei loydy - ilman sita continue-on-error "
        "on fail-open." % (HEALTH_STEP,))


def _padottavat(steps: list[dict]) -> list[str]:
    """Committia edeltavat askeleet jotka voivat skipata sen."""
    return [s["name"] for s in _ennen_committia(steps)
            if s.get("name") not in SALLITTU_FAIL_FAST
            and s.get("continue-on-error") is not True]


def _health_aukot(steps: list[dict]) -> list[str]:
    """continue-on-error-askeleet joita Step health ei mittaa."""
    health = _health_teksti(steps)
    aukot = []
    for s in _ennen_committia(steps):
        nimi = s.get("name")
        if s.get("continue-on-error") is not True:
            continue
        if nimi in SALLITTU_VAROITUS_VAIN:
            continue
        sid = s.get("id")
        if not sid or ("steps.%s.outcome" % sid) not in health:
            aukot.append(nimi)
    return aukot


# --- 1. invariantti: mikaan askel ei pado committia -------------------------

def test_yksikaan_askel_ei_pado_committia():
    steps = _steps(_lataa())
    padottavat = _padottavat(steps)
    assert not padottavat, (
        "Nama askeleet voivat skipata `Commit + push` -askelen ja jaadyttaa "
        "KOKO refresh-datan (nain kavi 4 kertaa 21.8-4.9). Lisaa "
        "`continue-on-error: true` + Step health -rivi, tai kirjoita "
        "perustelu SALLITTU_FAIL_FAST-listaan: %s" % (padottavat,))


def test_kontrolli_ei_mennyt_tyhjana_lapi():
    """Testi joka ei mittaa mitaan lapaisee aina (muisti: kontrolli tyhjana)."""
    steps = _steps(_lataa())
    ennen = _ennen_committia(steps)
    assert len(ennen) >= 20, ennen
    suojatut = [s for s in ennen if s.get("continue-on-error") is True]
    assert len(suojatut) >= 15, [s.get("name") for s in suojatut]


def test_negatiivinen_kontrolli_fail_fast_askel_kaataa():
    """Poista continue-on-error yhdelta askeleelta -> portin ON huudettava."""
    steps = _steps(_lataa())
    kohde = next(s for s in _ennen_committia(steps)
                 if s.get("continue-on-error") is True
                 and s.get("name") not in SALLITTU_FAIL_FAST)
    mutatoitu = copy.deepcopy(steps)
    for s in mutatoitu:
        if s.get("name") == kohde["name"]:
            s.pop("continue-on-error")
    assert kohde["name"] in _padottavat(mutatoitu)


def test_poikkeuslistalla_ei_ole_kuolleita_riveja():
    """Vanhentunut poikkeuslista on hiljainen reika: nimi jota workflow'ssa ei
    ole antaa vapautuksen askeleelle jota ei ole, ja uudelleen nimetty askel
    putoaa listalta huomaamatta."""
    nimet = {s.get("name") for s in _steps(_lataa())}
    kuolleet = sorted((set(SALLITTU_FAIL_FAST) | set(SALLITTU_VAROITUS_VAIN))
                      - nimet)
    assert not kuolleet, (
        "Poikkeuslistalla on nimia joita workflow'ssa ei ole: %s" % (kuolleet,))


def test_jokaisella_poikkeuksella_on_perustelu():
    parit = (list(SALLITTU_FAIL_FAST.items())
             + list(SALLITTU_VAROITUS_VAIN.items()))
    tyhjat = [k for k, v in parit if len((v or "").strip()) < 20]
    assert not tyhjat, tyhjat


# --- 2. invariantti: continue-on-error ei ole fail-open ---------------------

def test_jokainen_suojattu_askel_nakyy_step_healthissa():
    steps = _steps(_lataa())
    aukot = _health_aukot(steps)
    assert not aukot, (
        "Nama askeleet voivat kaatua VIHREAN ajon takana (fail-open). Anna "
        "askeleelle `id` ja lisaa Step healthiin rivi, tai kirjoita perustelu "
        "SALLITTU_VAROITUS_VAIN-listaan: %s" % (aukot,))


def test_negatiivinen_kontrolli_puuttuva_health_rivi_kaataa():
    """Poista yksi health-rivi -> portin ON huudettava."""
    steps = _steps(_lataa())
    kohde = next(s for s in _ennen_committia(steps)
                 if s.get("continue-on-error") is True and s.get("id")
                 and s.get("name") not in SALLITTU_VAROITUS_VAIN)
    mutatoitu = copy.deepcopy(steps)
    for s in mutatoitu:
        if s.get("name") == HEALTH_STEP:
            s["run"] = "\n".join(
                r for r in s["run"].splitlines()
                if ("steps.%s.outcome" % kohde["id"]) not in r)
    assert kohde["name"] in _health_aukot(mutatoitu)


def test_negatiivinen_kontrolli_id_puuttuu_kaataa():
    """id:n poisto tekee askeleesta mittaamattoman -> portin ON huudettava."""
    steps = _steps(_lataa())
    kohde = next(s for s in _ennen_committia(steps)
                 if s.get("continue-on-error") is True and s.get("id")
                 and s.get("name") not in SALLITTU_VAROITUS_VAIN)
    mutatoitu = copy.deepcopy(steps)
    for s in mutatoitu:
        if s.get("name") == kohde["name"]:
            s.pop("id")
    assert kohde["name"] in _health_aukot(mutatoitu)


def test_negatiivinen_kontrolli_commit_askelen_nimi():
    """Jos commit-askelen nimi vaihtuu, portti ei saa lapaista hiljaa."""
    steps = copy.deepcopy(_steps(_lataa()))
    for s in steps:
        if s.get("name") == COMMIT_STEP:
            s["name"] = "Commit + push (uudelleennimetty)"
    with pytest.raises(AssertionError):
        _ennen_committia(steps)
