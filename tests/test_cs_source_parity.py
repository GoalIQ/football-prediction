"""Sama ottelu, sama puhtaan pelin todennakoisyys joka pinnalla (CS-FDR-META-ERI-MIELTA).

MITATTU 22.9.2026 ENNEN KORJAUSTA: `data/fpl_cs_fdr.json` ja
`data/fpl_projections_phase0.json` (= goaliq.app/fpl#clean-sheets) olivat eri
mielta 12 ottelusta GW6-11:ssa, kaikki Coventryn tai Hullin otteluita. Suurin
ero HUL v IPS: 16,8 % vs 33,0 %. Syy ei ollut kaava (Poissonin P(0) ja
DC-matriisin marginaali ovat sama luku) vaan nimikartta: cs_fdr:n kopiosta
puuttuivat "Coventry City" ja "Hull City", joten se ei loytanyt niita
mallista ja antoi niille nousijabaselinen, vaikka kummallakin oli viisi
liigaottelua dataa. `caveat` vaitti samaa ("Nousijat Coventry/Hull =
empiirinen promoted baseline").

Portit (saanto 6a):
1. DATA: kommitoidut artefaktit samaa mielta jokaisesta yhteisesta ottelusta,
   raja 1 %-yks. Tama on se luku jonka lukija naeksi.
2. RAKENNE: cs_fdr laskee luvut SAMALLA funktiolla ja SAMALLA nimikartalla
   kuin phase0 - erottelevalla fikstuurilla, jossa vaara nimikartta TAI
   puuttuva kontekstikerros oikeasti muuttaisi lukua.
3. CAVEAT: sanoo vain sen mita ajo teki.
"""
from __future__ import annotations

import json

import pytest

import config

RAJA_PP = 1.0


def _lue(nimi: str) -> dict:
    p = config.DATA_DIR / nimi
    if not p.exists():
        pytest.skip(f"{nimi} puuttuu (ei generoitu tassa ymparistossa)")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Data: kommitoidut tiedostot
# ---------------------------------------------------------------------------
def test_same_fixture_same_clean_sheet_pct_in_both_artifacts():
    from src.models.fpl_team_names import map_name
    cs_fdr = _lue("fpl_cs_fdr.json")
    phase0 = _lue("fpl_projections_phase0.json")
    # Avain rakennetaan LAHDENIMESTA jaetulla kartalla, EI cs_fdr:n omasta
    # `home_model`-kentasta: vika oli juuri siina kentassa ("Coventry City"),
    # ja sen varaan rakennettu avain olisi ohittanut vialliset ottelut hiljaa
    # (mitattu 22.9: vanhalla datalla 48/60 osui ja testi oli vihrea).
    cs_by_key = {(f["gameweek"], int(f["kickoff_ms"] or 0),
                  map_name(f["home"]), map_name(f["away"])): f
                 for f in cs_fdr.get("fixtures") or []}
    loydetty = 0
    erot = []
    puuttuu = []
    for g in phase0.get("fixtures") or []:
        avain = (g["gameweek"], int(g["kickoff_ms"] or 0), g["home"], g["away"])
        f = cs_by_key.get(avain)
        if f is None:
            puuttuu.append(f"GW{g['gameweek']} {g['home']} v {g['away']}")
            continue
        loydetty += 1
        for puoli in ("home", "away"):
            a, b = f[f"cs_{puoli}_pct"], g[f"cs_{puoli}_pct"]
            if abs(a - b) > RAJA_PP:
                erot.append(f"GW{f['gameweek']} {f['home']} v {f['away']} "
                            f"({puoli}): cs_fdr {a} vs /fpl {b}")
    # Tyhja leikkaus ei ole vihrea: se tarkoittaisi etta avaimet (mallinimet)
    # eivat enaa kohtaa, eli juuri sita nimikarttavikaa jota tama vartioi.
    # Jokainen /fpl-sivun ottelu on loydyttava cs_fdr:sta. Puuttuva ottelu ei
    # ole "ei vertailtavaa" vaan nimikartta- tai kickoff-ajautuma.
    assert loydetty >= 10 and not puuttuu, (
        f"{len(puuttuu)} /fpl-sivun ottelua puuttuu cs_fdr:sta: {puuttuu[:10]}")
    assert not erot, (
        "Sama ottelu, eri CS% (raja %.1f %%-yks.). /fpl-sivu ja cs_fdr:n "
        "lukijat (wildcard, chip-EV) kertovat eri tarinaa:\n  " % RAJA_PP
        + "\n  ".join(erot[:20]))


def test_committed_caveat_names_only_teams_that_got_the_baseline():
    meta = _lue("fpl_cs_fdr.json").get("meta") or {}
    applied = set((meta.get("promoted_baseline_values") or {}).get("applied_to") or [])
    caveat = str(meta.get("caveat") or "")
    for seura in ("Coventry", "Hull", "Ipswich", "Sunderland", "Leeds", "Burnley"):
        if seura in caveat and not any(seura in a for a in applied):
            pytest.fail(f"caveat mainitsee {seura}:n vaikka baselinea ei "
                        f"sovellettu sille (applied_to={sorted(applied)}): {caveat}")


# ---------------------------------------------------------------------------
# 2. Rakenne: sama funktio, sama nimikartta, sama kontekstikerros
# ---------------------------------------------------------------------------
def _dc():
    from src.models.dixon_coles import DixonColesModel
    return DixonColesModel(
        attack={"Coventry": 0.05, "Arsenal": 0.45, "Hull": -0.10},
        defence={"Coventry": 0.20, "Arsenal": -0.35, "Hull": 0.10},
        home_advantage=0.20, home_advantage_per_team={}, rho=-0.08,
        teams_=["Coventry", "Arsenal", "Hull"])


def _ctx_with_override():
    # Coventry vuotaa enemman: tama rivi LIIKUTTAA Arsenalin CS%:a vs COV.
    return {"promoted": set(), "first_home_gw": {},
            "overrides": [{"scope": "manual", "team": "Coventry", "opponent": None,
                           "venue": None, "gw_from": 6, "gw_to": 6,
                           "attack_mult": 1.3, "defence_mult": 1.0,
                           "xmins_mult": 1.0, "note": "testi"}]}


FIXTURES = [
    # pulselive-muoto: pitkat nimet. "Coventry City" on nimi joka putosi.
    {"gameweek": 6, "kickoff": "x", "kickoff_ms": 1, "finished": False,
     "home": "Arsenal", "away": "Coventry City"},
    {"gameweek": 6, "kickoff": "x", "kickoff_ms": 2, "finished": False,
     "home": "Hull City", "away": "Arsenal"},
]


def test_cs_fdr_and_phase0_compute_identical_numbers_for_long_names():
    import scripts.build_fpl_cs_fdr as cs
    import scripts.build_fpl_phase0 as p0
    ctx = _ctx_with_override()
    a = cs.compute_fixtures(_dc(), FIXTURES, ctx_cfg=ctx)
    b = p0.compute_fixtures(_dc(), FIXTURES, ctx_cfg=ctx)
    # Molemmat ottelut mukana: vaara nimikartta pudottaisi ne (h not in dc.attack)
    # tai veisi baselinelle ennen tata funktiota.
    assert len(a) == len(b) == 2
    for x, y in zip(a, b):
        assert (x["home_model"], x["away_model"]) == (y["home"], y["away"])
        for k in ("cs_home_pct", "cs_away_pct", "xg_home", "xg_away",
                  "p_home_win", "p_draw", "p_away_win"):
            assert x[k] == y[k], (k, x, y)


def test_fixture_is_discriminating_override_moves_the_number():
    """Exit-koodi ei ole todiste: jos yliajo ei liikuttaisi lukua, yllaoleva
    testi menisi lapi myos cs_fdr:lla joka ohittaa kontekstikerroksen."""
    import scripts.build_fpl_cs_fdr as cs
    ilman = cs.compute_fixtures(_dc(), FIXTURES[:1], ctx_cfg=None)[0]
    kanssa = cs.compute_fixtures(_dc(), FIXTURES[:1], ctx_cfg=_ctx_with_override())[0]
    assert abs(ilman["cs_home_pct"] - kanssa["cs_home_pct"]) > RAJA_PP


def test_one_name_map_for_every_fpl_surface():
    import scripts.build_fpl_cs_fdr as cs
    import scripts.build_fpl_phase0 as p0
    from src.models import fpl_team_names, fpl_wildcard
    assert cs.map_name is fpl_team_names.map_name
    assert p0.map_name is fpl_team_names.map_name
    assert fpl_wildcard.FPL_TO_MODEL is fpl_team_names.NAME_MAP
    # Mitattu 22.9: FPL:n bootstrap-static team.name 26/27 ja pulselive-nimet.
    for pitka, malli in (("Coventry City", "Coventry"), ("Hull City", "Hull"),
                         ("Ipswich Town", "Ipswich"), ("Man City", "Manchester City"),
                         ("Brighton & Hove Albion", "Brighton")):
        assert fpl_team_names.map_name(pitka) == malli


FPL_BOOTSTRAP_2627 = [  # mitattu 22.9.2026 fantasy.premierleague.com/api/bootstrap-static/
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Chelsea",
    "Coventry City", "Crystal Palace", "Everton", "Fulham", "Hull City",
    "Ipswich Town", "Leeds", "Liverpool", "Man City", "Man Utd", "Newcastle",
    "Nott'm Forest", "Spurs", "Sunderland"]


def test_wildcard_finds_every_fpl_team_in_committed_cs_fdr():
    from src.models import fpl_wildcard
    fixtures = _lue("fpl_cs_fdr.json").get("fixtures") or []
    mallinimet = {f.get(k) for f in fixtures for k in ("home_model", "away_model")} - {None}
    aukot = fpl_wildcard.nimikartta_aukot(
        [{"name": n} for n in FPL_BOOTSTRAP_2627], mallinimet)
    assert not aukot, f"wildcard pudottaisi nama seurat pitkasta nakymasta: {aukot}"


def test_caveat_is_derived_from_the_run():
    from scripts.build_fpl_cs_fdr import cs_fdr_caveat
    tyhja = cs_fdr_caveat([], ["2526", "2627"])
    assert "Coventry" not in tyhja and "Hull" not in tyhja
    assert "nousijabaselinea ei" in tyhja
    yksi = cs_fdr_caveat(["Hull"], ["2526", "2627"])
    assert "Hull" in yksi and "Coventry" not in yksi
