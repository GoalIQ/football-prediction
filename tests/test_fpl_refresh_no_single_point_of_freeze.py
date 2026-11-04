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
    "Restore core artefacts whose builder failed":
        "Ydinbuilderit (phase0, xP) ovat continue-on-error, joten osittainen "
        "artefakti voisi muuten paatya committiin (muisti: osittainen data "
        "myrkyttaa cachen). Jos palautus itse kaatuu, levylla voi olla juuri "
        "se osittainen tiedosto: silloin pato ON korjaus.",
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
    "TLS library for Understat (authenticated)":
        "Fail-open tarkoituksella (22.10.2026): skripti varoittaa itse, ja jos Understat ei silti vastaa, "
        "vaadi_understat kaataa phase0:n, jonka health-rivi punaa ajon.",
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


def _fail_fast_listan_valheet(steps: list[dict]) -> list[str]:
    nimi_askel = {s.get("name"): s for s in steps}
    return sorted(n for n in SALLITTU_FAIL_FAST
                  if n in nimi_askel
                  and nimi_askel[n].get("continue-on-error") is True)


def test_fail_fast_poikkeus_on_oikeasti_fail_fast():
    """4.11: listalla oli 'Build Phase 0' perusteluineen kaksi kuukautta sen
    jalkeen kun askel oli muutettu continue-on-erroriksi (6.9), ja xP-rivin
    perustelu oli 'sama kuin Phase 0'. Vanhentunut perustelu piti xP-askeleen
    patona, joka jaadytti koko putken Understat-katkossa 1.11-4.11."""
    valheet = _fail_fast_listan_valheet(_steps(_lataa()))
    assert not valheet, (
        "SALLITTU_FAIL_FAST perustelee fail-fastia askeleille jotka ovat "
        "continue-on-error. Poista rivi: %s" % (valheet,))


def test_negatiivinen_kontrolli_vanhentunut_fail_fast_poikkeus_kaataa():
    steps = copy.deepcopy(_steps(_lataa()))
    kohde = next(s for s in steps if s.get("name") in SALLITTU_FAIL_FAST
                 and s.get("continue-on-error") is not True)
    kohde["continue-on-error"] = True
    assert kohde["name"] in _fail_fast_listan_valheet(steps)


# --- 3. invariantti: kaatunut ydinbuilderi ei jata osittaista artefaktia ----
# 4.11: phase0 ja xP ovat continue-on-error. Fail-closed-lupaus ("edellinen
# artefakti jaa voimaan") pitaa silti: palautusaskel vie kaatuneen builderin
# tiedoston HEADin versioon ennen kuin mikaan muu askel lukee sita.

RESTORE_STEP = "Restore core artefacts whose builder failed"
YDINBUILDERIT = {
    "build_phase0": "data/fpl_projections_phase0.json",
    "build_xp": "data/fpl_xp_projections.json",
}
XP_GATE = "Gate - xP headline gameweek is actionable"


def _palautuksen_aukot(steps: list[dict]) -> list[str]:
    nimet = [s.get("name") for s in steps]
    if RESTORE_STEP not in nimet:
        return ["palautusaskel puuttuu"]
    i_restore = nimet.index(RESTORE_STEP)
    restore = steps[i_restore]
    ehto = restore.get("if") or ""
    run = restore.get("run") or ""
    aukot = []
    id_paikka = {s.get("id"): i for i, s in enumerate(steps) if s.get("id")}
    for sid, polku in YDINBUILDERIT.items():
        if sid not in id_paikka:
            aukot.append("%s: builderin id puuttuu" % sid)
            continue
        if id_paikka[sid] > i_restore:
            aukot.append("%s: builderi ajetaan palautuksen JALKEEN" % sid)
        if ("steps.%s.outcome == 'failure'" % sid) not in ehto:
            aukot.append("%s: palautuksen if-ehto ei kata sita" % sid)
        if ("steps.%s.outcome" % sid) not in run or polku not in run:
            aukot.append("%s: palautus ei vie %s:ta HEADiin" % (sid, polku))
    # Palautuksen on oltava heti builderien jalkeen: yksikaan muu askel ei saa
    # lukea osittaista tiedostoa sita ennen.
    viimeinen_builderi = max(id_paikka.get(sid, -1) for sid in YDINBUILDERIT)
    valissa = [s.get("name") for s in steps[viimeinen_builderi + 1:i_restore]]
    if valissa:
        aukot.append("builderin ja palautuksen valissa ajetaan: %s" % valissa)
    return aukot


def test_kaatuneen_ydinbuilderin_artefakti_palautetaan():
    aukot = _palautuksen_aukot(_steps(_lataa()))
    assert not aukot, aukot


def test_negatiivinen_kontrolli_palautuksen_poisto_kaataa():
    steps = [s for s in copy.deepcopy(_steps(_lataa()))
             if s.get("name") != RESTORE_STEP]
    assert _palautuksen_aukot(steps) == ["palautusaskel puuttuu"]


def test_negatiivinen_kontrolli_palautus_ei_kata_xp_ta():
    steps = copy.deepcopy(_steps(_lataa()))
    for s in steps:
        if s.get("name") == RESTORE_STEP:
            s["run"] = s["run"].replace("data/fpl_xp_projections.json", "data/x.json")
    assert any("build_xp" in a for a in _palautuksen_aukot(steps))


def test_negatiivinen_kontrolli_askel_builderin_ja_palautuksen_valissa():
    steps = copy.deepcopy(_steps(_lataa()))
    i = [s.get("name") for s in steps].index(RESTORE_STEP)
    steps.insert(i, {"name": "Lukija valissa", "run": "true"})
    assert any("valissa" in a for a in _palautuksen_aukot(steps))


def test_xp_portti_ajetaan_vain_tuoretta_tuotosta_vasten():
    """Kaatuneen builderin jalkeen levylla on HEADin artefakti. Sen
    otsikkokierros vanhenee deadlinessa, ja fail-fast-portti sita vasten olisi
    pysyvasti punainen pato (sama vika toisesta ovesta)."""
    gate = next(s for s in _steps(_lataa()) if s.get("name") == XP_GATE)
    assert "steps.build_xp.outcome == 'success'" in (gate.get("if") or ""), gate


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
