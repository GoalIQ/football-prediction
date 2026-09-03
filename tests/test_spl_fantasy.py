"""SPL-fantasy-testit: league-parametri, RSL-pisteytyksen ydin, minuuttimalli.

Ei verkkoa, ei mallifittiä (sama linja kuin test_fpl_phase0). Endpoint-testit
nojaavat repoon committattuihin data/spl_*-projektioihin — jos ne puuttuvat,
loaderin available=False-runko EI saa muuttua 500:ksi.
"""
from __future__ import annotations

import math

import pytest

from scripts.build_spl_phase0 import MODEL_TO_SHORT, SHORT_TO_MODEL
from src.models import spl_xp as sx
from src.models.dixon_coles import DixonColesModel
from src.models.promoted_baseline import blend_thin_toward_baseline


# ---------------------------------------------------------------------------
# league-parametri: oletus fpl ennallaan, spl servaa, tuntematon 404
# ---------------------------------------------------------------------------
def test_fantasy_default_league_unchanged(client):
    r = client.get("/api/fantasy")
    assert r.status_code == 200
    # FPL-tuote — SPL-liigatunniste EI saa vuotaa oletusvastaukseen.
    assert r.json()["meta"].get("league") != "SAU-Saudi Pro League"


def test_fantasy_spl_league_serves(client):
    r = client.get("/api/fantasy?league=spl")
    assert r.status_code == 200
    meta = r.json()["meta"]
    # Committattu projektio → SPL-tunniste; puuttuva tiedosto → available=False.
    if meta.get("available"):
        assert meta["league"] == "SAU-Saudi Pro League"


def test_fantasy_unknown_league_404(client):
    assert client.get("/api/fantasy?league=elite").status_code == 404
    assert client.get("/api/fantasy/xp?league=elite").status_code == 404


def test_fantasy_xp_spl_serves_and_etag_has_league(client):
    r = client.get("/api/fantasy/xp?league=spl")
    assert r.status_code == 200
    assert '"xp-spl-' in r.headers.get("etag", "")
    r2 = client.get("/api/fantasy/xp")
    assert '"xp-fpl-' in r2.headers.get("etag", "")


# ---------------------------------------------------------------------------
# Joukkuemappaus
# ---------------------------------------------------------------------------
def test_short_map_is_bijective_18_teams():
    assert len(SHORT_TO_MODEL) == 18
    assert len(MODEL_TO_SHORT) == 18  # ei duplikaattinimiä


# ---------------------------------------------------------------------------
# e_floor-approksimaatio
# ---------------------------------------------------------------------------
def test_e_floor_zero_rate_is_zero():
    assert sx.e_floor(0.0, 3) == 0.0


def test_e_floor_below_half_threshold_is_zero():
    # keskim. 0.5 tapahtumaa, kynnys 3 → floor käytännössä aina 0
    assert sx.e_floor(0.5, 3) == 0.0


def test_e_floor_less_than_linear():
    # approksimaatio ei saa ylittää lineaarista E[X]/n-ylärajaa
    assert sx.e_floor(6.0, 3) < 6.0 / 3


# ---------------------------------------------------------------------------
# RSL-pisteytys: GK-päästetyt joka maalista ensimmäisen jälkeen
# ---------------------------------------------------------------------------
def test_expected_conceded_gk_after_first():
    # P(2 maalia) = 1 → GK-sakko täsmälleen 1 (toinen maali)
    assert sx.expected_conceded_gk([0.0, 0.0, 1.0]) == pytest.approx(1.0)
    # P(1 maali) = 1 → ei sakkoa
    assert sx.expected_conceded_gk([0.0, 1.0]) == pytest.approx(0.0)


def test_expected_conceded_def_every_two():
    assert sx.expected_conceded_def([0.0, 0.0, 1.0]) == pytest.approx(1.0)
    assert sx.expected_conceded_def([0.0, 1.0]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# xp_components: RSL-erot FPL:ään
# ---------------------------------------------------------------------------
def _rates(**over):
    base = {f"{k}90": 0.0 for k in sx.AGG_KEYS}
    base.update(over)
    return base


def _ctx(cs=0.3):
    return {"goal_mult": 1.0, "cs_prob": cs,
            "conceded_dist": [0.4, 0.35, 0.15, 0.07, 0.03], "opp_goal_mult": 1.0}


def test_mid_goal_worth_5_and_def_goal_6():
    r = _rates(goals90=1.0)
    mid = sx.xp_components(3, r, 90.0, 1.0, 0.0, _ctx())
    dfd = sx.xp_components(2, r, 90.0, 1.0, 0.0, _ctx())
    assert mid["goals"] == pytest.approx(5.0)
    assert dfd["goals"] == pytest.approx(6.0)


def test_mid_clean_sheet_worth_1():
    comp = sx.xp_components(3, _rates(), 90.0, 1.0, 0.0, _ctx(cs=1.0))
    assert comp["clean_sheet"] == pytest.approx(1.0)


def test_gk_saves_every_two():
    comp = sx.xp_components(1, _rates(saves90=4.0), 90.0, 1.0, 0.0, _ctx())
    assert comp["saves"] == pytest.approx(2.0)  # 4 torjuntaa → 2 pistettä


def test_fwd_no_clean_sheet_points():
    comp = sx.xp_components(4, _rates(), 90.0, 1.0, 0.0, _ctx(cs=1.0))
    assert comp["clean_sheet"] == 0.0


def test_components_sum_to_total():
    r = _rates(goals90=0.5, assists90=0.3, saves90=3.0, yc90=0.2,
               tackles90=2.5, passes90=45.0, bonus90=0.4)
    comp = sx.xp_components(1, r, 90.0, 1.0, 0.0, _ctx())
    assert comp["total"] == pytest.approx(
        sum(v for k, v in comp.items() if k != "total"))
    assert math.isfinite(comp["total"])


# ---------------------------------------------------------------------------
# Minuuttimalli aggregaateista
# ---------------------------------------------------------------------------
def test_minutes_model_full_season_high_start():
    mm = sx.minutes_model_from_aggregates(34 * 86.0)
    assert mm["p_start"] == pytest.approx(0.95)
    assert mm["minutes_confidence"] == "med"


def test_minutes_model_zero_minutes():
    mm = sx.minutes_model_from_aggregates(0.0)
    assert mm["p_start"] == 0.0
    assert mm["xmins"] == 0.0
    assert mm["minutes_confidence"] == "low"


def test_minutes_model_monotone_in_minutes():
    xs = [sx.minutes_model_from_aggregates(m)["xmins"]
          for m in (0, 500, 1500, 2500)]
    assert xs == sorted(xs)


def test_scale_minutes_zero_availability():
    mm = sx.scale_minutes(sx.minutes_model_from_aggregates(2500.0), 0.0)
    assert mm["p_start"] == 0.0
    assert mm["xmins"] == 0.0


def test_availability_factor():
    assert sx.availability_factor("a", None) == 1.0
    assert sx.availability_factor("d", 75) == 0.75
    assert sx.availability_factor("i", None) == 0.0


# ---------------------------------------------------------------------------
# Model squad: laillisuus ja kahden rikkovan seuran umpikuja (12.8.2026).
# Halvimmat oletushintaiset (4.0/4.5) kasautuivat nousijaseuroihin niin etta
# lahtorungossa oli KAKSI seuraa yli katon. Yksittaisvaihto korjaa vain
# toisen -> club_ok hylkasi kaikki trialit ja laiton 64m-runko julkaistiin
# "model squadina". Nama testit kaatuvat vanhalla koodilla.

def _mk_player(pid, pos, team, price, xp):
    return {"id": pid, "web_name": f"P{pid}", "team_short": team, "pos": pos,
            "price": price, "xp_per_gw": round(xp / 6, 2),
            "xp_horizon_total": xp}


def _deadlock_pool():
    """Pooli jossa halvin runko rikkoo katon kahdella seuralla (TW4 + AB4),
    ja kalliit tahdet ovat selvasti parempia."""
    players = []
    pid = 0
    # TW: halvin GKP + 3 halvinta MID + halvin DEF = 5 halpaa samasta seurasta
    for pos, n in (("GKP", 1), ("DEF", 1), ("MID", 3)):
        for _ in range(n):
            pid += 1
            players.append(_mk_player(pid, pos, "TW", 4.0, 12.0))
    # AB: 2 halvinta DEF + 2 halvinta MID
    for pos, n in (("DEF", 2), ("MID", 2)):
        for _ in range(n):
            pid += 1
            players.append(_mk_player(pid, pos, "AB", 4.0, 11.0))
    # Taytto: riittavasti halpoja muista seuroista (eri seura joka rivilla)
    fill = [("GKP", 2), ("DEF", 4), ("MID", 2), ("FWD", 4)]
    for pos, n in fill:
        for _ in range(n):
            pid += 1
            players.append(_mk_player(pid, pos, f"F{pid}", 4.5, 10.0))
    # Tahdet: kalliita ja selvasti parempia, eri seuroista
    for pos in ("FWD", "FWD", "MID", "DEF"):
        pid += 1
        players.append(_mk_player(pid, pos, f"S{pid}", 11.0, 40.0))
    return players


def test_model_squad_respects_club_cap():
    from scripts.build_spl_xp import build_model_squad
    sq = build_model_squad(_deadlock_pool())
    assert sq is not None
    counts: dict[str, int] = {}
    for p in sq["players"]:
        counts[p["team_short"]] = counts.get(p["team_short"], 0) + 1
    assert all(v <= 3 for v in counts.values()), counts
    assert sq["cost"] <= sq["budget"]


def test_model_squad_escapes_cheap_skeleton():
    """Umpikujapoolissa tahtien (40 xp) TAYTYY paatya joukkueeseen: jos
    squad jaa pelkkiin halpoihin, silmukka ei ikina arvioinut vaihtoja."""
    from scripts.build_spl_xp import build_model_squad
    sq = build_model_squad(_deadlock_pool())
    assert sq is not None
    assert any(p["price"] >= 11.0 for p in sq["players"]), (
        "yksikaan tahti ei paassyt squadiin - vaihtosilmukka umpikujassa")


# ---------------------------------------------------------------------------
# SPL-INSEASON-FIT (19.8): ohuen otoksen nousijan blend baselinea kohti.
# Mitattu artefakti jonka nama vartioivat: GW1:n naiivi lisays fittiin nosti
# Al Diriyahin GW2 CS%:n +12,4 %-yks, koska yhden ottelun estimaatti
# L2-kutistuu sarjan keskitasoon joka on nousijalle liian antelias.
# ---------------------------------------------------------------------------
def _dc_stub():
    dc = DixonColesModel(per_team_home_adv=True)
    # Viitetrio fitissa: baseline = keskiarvot (-0.2, +0.3, +0.1).
    dc.attack = {"Ref A": -0.1, "Ref B": -0.2, "Ref C": -0.3, "Uusija": 0.1}
    dc.defence = {"Ref A": 0.2, "Ref B": 0.3, "Ref C": 0.4, "Uusija": 0.0}
    dc.home_advantage_per_team = {
        "Ref A": 0.1, "Ref B": 0.1, "Ref C": 0.1, "Uusija": 0.4,
    }
    return dc


REF = ("Ref A", "Ref B", "Ref C")


def test_blend_one_match_is_one_sixth_of_the_way():
    dc = _dc_stub()
    info = blend_thin_toward_baseline(
        dc, {"Uusija": 1}, ["Uusija"], reference=REF, n_min=6)
    # base_att -0.2, fit 0.1 -> -0.2 + (1/6)*0.3 = -0.15
    assert math.isclose(dc.attack["Uusija"], -0.15)
    assert math.isclose(dc.defence["Uusija"], 0.3 + (1 / 6) * (0.0 - 0.3))
    assert math.isclose(
        dc.home_advantage_per_team["Uusija"], 0.1 + (1 / 6) * (0.4 - 0.1))
    assert info["blended"]["Uusija"]["n"] == 1
    assert info["source"] == "measured"


def test_blend_leaves_full_sample_alone():
    """n >= n_min: fitattu estimaatti jaa koskematta — blend vanhenee itse."""
    dc = _dc_stub()
    info = blend_thin_toward_baseline(
        dc, {"Uusija": 6}, ["Uusija"], reference=REF, n_min=6)
    assert dc.attack["Uusija"] == 0.1
    assert info["blended"] == {}


def test_blend_leaves_zero_sample_alone():
    """n=0 kuuluu add_promoted_baselinelle (missing-polku), ei blendille."""
    dc = _dc_stub()
    blend_thin_toward_baseline(dc, {}, ["Uusija"], reference=REF, n_min=6)
    assert dc.attack["Uusija"] == 0.1


def test_blend_ignores_team_not_in_fit():
    dc = _dc_stub()
    info = blend_thin_toward_baseline(
        dc, {"Tuntematon": 2}, ["Tuntematon"], reference=REF, n_min=6)
    assert "Tuntematon" not in dc.attack
    assert info["blended"] == {}


def test_blend_without_reference_skips_visibly():
    """Negatiivinen kontrolli: viiteryhma puuttuu eika frozen sallittu ->
    nakyvä skip, parametreihin ei kosketa, ei arvattua baselinea."""
    dc = _dc_stub()
    info = blend_thin_toward_baseline(
        dc, {"Uusija": 1}, ["Uusija"], reference=("Ei Ole",), n_min=6,
        allow_frozen=False)
    assert dc.attack["Uusija"] == 0.1
    assert info["skipped"] == ["Uusija"]


# ---------------------------------------------------------------------------
# SPL-GW1-RECON (20.8): täsmäytysartefakti ja sen läpivienti julkiselle
# pinnalle. Sivun jokainen luku tulee artefaktista, joten artefaktin on
# oltava sisäisesti konsistentti — summaluvut EIVÄT saa olla käsin
# kirjoitettuja vaan riveistä uudelleenlaskettavia.
# ---------------------------------------------------------------------------

def _recon() -> dict | None:
    import config, json
    p = config.PROJECT_ROOT / "data" / "spl_recon.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def test_recon_summary_recomputes_from_rows():
    r = _recon()
    if r is None:
        pytest.skip("spl_recon.json ei generoitu tässä ympäristössä")
    sides = [(f[f"cs_{s}_pct"] / 100.0, f[f"cs_{s}_kept"])
             for f in r["fixtures"] for s in ("home", "away")]
    # 3.9: sivujen määrä lasketaan riveistä eikä ole 18. Kierroksissa on
    # 8-10 ottelua (siirretyt ottelut), ja luku 18 oli GW1:n oma.
    assert len(sides) == r["sides"] == 2 * len(r["fixtures"])
    assert math.isclose(sum(p for p, _ in sides), r["expected_cs"], abs_tol=0.005)
    assert sum(1 for _, kept in sides if kept) == r["actual_cs"]
    brier = sum((p - float(kept)) ** 2 for p, kept in sides) / len(sides)
    assert math.isclose(brier, r["brier"], abs_tol=0.00005)
    naive = sum((r["naive_p"] - float(kept)) ** 2 for _, kept in sides) / len(sides)
    assert math.isclose(naive, r["naive_brier"], abs_tol=0.00005)


def test_recon_season_total_recomputes_from_every_gameweek():
    """Kauden luvut ovat kierroslohkojen summa, ei erikseen kirjoitettu.

    🔴 TÄMÄ TESTI KORVASI VÄITTEEN `brier < naive_brier` (20.8). Se piti
    GW1:ssä ja pinnattiin testiin, mutta GW4:ssä malli oli naiivia HUONOMPI
    (0.2158 vs 0.1876). Kierroskohtainen paremmuus ei ole invariantti eikä sitä
    saa vahtia kuin se olisi: sivun väite kuuluu kauden luvulle, ja se on
    `season_to_date`. Vrt. CLAUDE.md 6a (3): invariantti mitataan joka
    vaiheessa, ei siinä jossa se sattuu pitämään."""
    r = _recon()
    if r is None:
        pytest.skip("spl_recon.json ei generoitu tässä ympäristössä")
    s = r["season_to_date"]
    blocks = r["gameweeks"]
    assert [b["gameweek"] for b in blocks] == s["gameweeks"]
    assert sum(b["sides"] for b in blocks) == s["sides"]
    assert sum(b["actual_cs"] for b in blocks) == s["actual_cs"]
    assert math.isclose(sum(b["expected_cs"] for b in blocks),
                        s["expected_cs"], abs_tol=0.02)
    # Brier on keskiarvo, joten summa on painotettava sivujen määrällä.
    painotettu = sum(b["brier"] * b["sides"] for b in blocks) / s["sides"]
    assert math.isclose(painotettu, s["brier"], abs_tol=0.0005)
    # Uusin kierros on lohkojen viimeinen, ja ylätason luvut ovat sen omat.
    viim = blocks[-1]
    assert r["gameweek"] == viim["gameweek"]
    assert r["brier"] == viim["brier"] and r["sides"] == viim["sides"]


def test_recon_top3_matches_rows():
    r = _recon()
    if r is None:
        pytest.skip("spl_recon.json ei generoitu tässä ympäristössä")
    kaikki = sorted(
        (f[f"cs_{s}_pct"] for f in r["fixtures"] for s in ("home", "away")),
        reverse=True)
    assert [t["cs_pct"] for t in r["top3"]] == kaikki[:3]


def test_recon_flows_to_spl_meta(client):
    """Artefakti kulkee build-metan kautta API:iin — jos projektio on
    rakennettu reconin olemassa ollessa, avaimen on oltava vastauksessa
    samoilla summilla (jakopinta ei saa lukea eri tiedostoa kuin sivu)."""
    r = _recon()
    if r is None:
        pytest.skip("spl_recon.json ei generoitu tässä ympäristössä")
    resp = client.get("/api/fantasy?league=spl")
    assert resp.status_code == 200
    meta = resp.json()["meta"]
    if not meta.get("available"):
        pytest.skip("SPL-projektiota ei committattu tässä ympäristössä")
    served = meta.get("gw_reconciliation")
    assert served is not None, (
        "projektio on rakennettu ilman recon-liitosta — aja build_spl_phase0 "
        "uudelleen")
    assert served["expected_cs"] == r["expected_cs"]
    assert served["actual_cs"] == r["actual_cs"]
    assert served["brier"] == r["brier"]
    # 🔴 3.9 ILTA: kolme lukua ei riita. Korjasin `naive_note`n ja regeneroin
    # reconin, mutta en phase0:aa — ja koska API tarjoilee reconin phase0:n
    # METAN sisalta, tuotanto tarjoili viela vanhaa lausetta jonka
    # julkaisuportti oli juuri blokannut. Luvut tasmasivat koko ajan.
    # Vertaa KOKO lohko: upotettu kopio ei saa erota lahteesta miltaan osin.
    assert served == r, (
        "phase0:n metaan upotettu gw_reconciliation ei ole sama kuin "
        "data/spl_recon.json — aja build_spl_recon ENNEN build_spl_phase0:aa "
        "ja committaa molemmat")


def test_spl_recon_lohkossa_ei_ole_kasin_kirjoitettuja_lukuja():
    """Jokainen luku lohkossa tulee artefaktista, ei lahdekoodista.

    🔴 Julkaisutarkistajan loydos 3.9: lohko oli saanut kasin kirjoitetut
    "2 from 3" ja "nine clean sheets against 4.77 expected". Molemmat olivat
    tosia sina paivana ja vaaria seuraavalla kierroksella. Sivu ei voi
    ajautua artefaktista eri lukuihin jos siella ei ole lukuja.

    Sallittu: `toFixed(3)`, `>= 3`, `* 100` — kokonaisluvut ovat kynnyksia ja
    muotoiluargumentteja. Kielletty: desimaaliluku (`4.77`), joka on aina
    mittaustulos. Negatiivinen kontrolli: testi kaatuu jos sellainen
    lisataan takaisin (todennettu mutaatiolla)."""
    import re, config
    p = (config.PROJECT_ROOT / "web" / "pro-spa" / "src" / "routes" / "spl"
         / "+page.svelte")
    src = p.read_text(encoding="utf-8")
    alku = src.index("{#if recon}")
    # 🔴 Ensimmainen versio haki lopuksi seuraavan "<section>":n — mutta lohko
    # ALKAA sellaisella, joten viipale oli kaytannossa tyhja ja portti
    # lapaisi mutaatiotestin. Lohko paattyy YLATASON `{/if}`:iin, joka on
    # sisennetty yhdella tabilla (sisemmat ovat syvemmalla).
    loppu = src.index("\n\t{/if}", alku)
    lohko = src[alku:loppu]
    assert len(lohko) > 2000, f"viipale on liian lyhyt ({len(lohko)}) — rakenne muuttui"
    # Kommentit pois: perustelut saavat sisaltaa mitattuja lukuja.
    lohko = re.sub(r"<!--.*?-->", "", lohko, flags=re.S)
    desimaalit = re.findall(r"(?<![\w.])\d+\.\d+", lohko)
    assert not desimaalit, (
        f"SPL-recon-lohkossa on kasin kirjoitettuja desimaalilukuja "
        f"{desimaalit} — jokaisen luvun on tultava artefaktista")
