"""Portti: jokainen etusivun kortin luku on tarkistettavissa ilmaissivulta.

🔴 TAUSTA (22.9.2026, julkaisutarkistaja BLOKKASI molemmat kortit). Kortti
lupaa alapalkissaan tarkistusreitin (`goaliq.app/fpl/expected-points#top-100`
ja `#gw-xp`), mutta:
  * standouts-kortin "8 weeks in 10 between p10 and p90" ja "median 4 pts"
    eivat olleet sivulla missaan sarakkeessa,
  * projected-XI-kortin penkin nelja lukua (Phillips 1.0, Emersonn 3.8,
    Slater 3.4, Thomas-Asante 2.9) eivat olleet #gw-xp-listalla (top 20).
Portti oli siis vaite ilman reittia (muisti: vaite-tarvitsee-reitin).

KORJAUS ON RAJAUS SAMALLA FUNKTIOLLA KUIN SIVU (CLAUDE.md 6a kohta 1):
  * standouts-pooli = sivun #top-100 (`horizon_top_ids_actionable`, joka
    kayttaa samaa `horizon_ranked`ia kuin `render_expected_points`)
  * XI:n luku naytetaan vain #gw-xp-listan pelaajalle (`gw_xp_list_ids` ->
    `free_rows`, sama kuin `_gw_xp_section`), penkki aina ilman lukuja.
Tama tiedosto mittaa (1) rakenteen: sivu ja kortti kutsuvat samaa funktiota,
(2) kayttaytymisen synteettisella syotteella ja (3) todellisen committoidun
datan ja committoidun sivun parin.
"""
from __future__ import annotations

import html as _html
import inspect
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# (1) RAKENNE ----------------------------------------------------------------

def test_sivu_ja_kortti_jarjestavat_top_100_samalla_funktiolla():
    import scripts.build_fpl_longtail as L
    src = inspect.getsource(L.render_expected_points)
    assert "rows = horizon_ranked(players)" in src
    assert "sorted(players" not in src, "sivulla oma jarjestys -> voi ajautua erilleen"
    assert "rows[:100]" not in src and "rows[:HORIZON_TOP_N]" in src


def test_sivu_ja_kortti_lukevat_gw_xp_listan_samalla_funktiolla():
    import scripts.build_fpl_longtail as L
    from src.models import fpl_gw_xp
    assert "free_rows(xp" in inspect.getsource(L._gw_xp_section)
    assert "free_rows(xp" in inspect.getsource(fpl_gw_xp.gw_xp_list_ids)


# (2) KAYTTAYTYMINEN ---------------------------------------------------------

def _pl(pid, name, gw6, gw7, p_start=0.9, club=None, haul=0.2, blank=0.2, p90=12):
    return {"id": pid, "web_name": name, "pos": "MID", "team_short": club or f"C{pid}",
            "team": club or f"C{pid}", "price": 6.0, "status": "a",
            "p_start": p_start, "xp_horizon_total": gw6 + gw7,
            "gameweeks": [{"gw": 6, "xp": gw6}, {"gw": 7, "xp": gw7}],
            "xp_dist": {"gw": 6, "n": 2000, "mean": gw6, "p_haul": haul,
                        "p_blank": blank, "p10": 1, "median": 4, "p90": p90,
                        "haul_pts": 10, "blank_pts": 2}}


META = {"deadline_gameweek": 6, "next_gameweek": 6, "available": True,
        "deadline_utc": "2026-10-10T10:00:00+00:00",
        "generated_at": "2026-09-22T08:07:47+00:00"}
# XI-fikstuurille OMA generated_at: free_optimumin valimuisti avaintaa sen
# mukaan (projected-xi-gw6-<generated_at>), ja sama avain kuin oikealla
# datalla palauttaisi toisen testin XI:n.
META_XI = dict(META, generated_at="2000-01-01T00:00:00+00:00")


def _kentta(tahti_gw6: float = 9.0, n_tayte: int = 98) -> list[dict]:
    """100 tayttoa korkealla horisontilla (p_start 0.3: eivat kortille) +
    'Tahti', jolla paras GW6-xP mutta horisontti sijalla 101, + kaksi
    tavallista ehdokasta sivun top-100:ssa."""
    tayte = [_pl(1000 + i, f"Filler{i}", 1.0, 30.0 - i * 0.01, p_start=0.3)
             for i in range(n_tayte)]
    return tayte + [_tahti(tahti_gw6),
                    _pl(2, "Kakkonen", 6.0, 20.0),
                    _pl(3, "Kolmonen", 5.0, 19.0, haul=0.1, blank=0.4)]


def _tahti(gw6: float = 9.0) -> dict:
    """Raakakentta `xp_horizon_total` on VANHA (999): sivun builder laskee sen
    uudelleen (`attach_horizon_total_actionable`), joten sivulla Tahti on
    sijalla 101. Jos kutsupaikka unohtaa `meta`n ja jarjestaa raakakentalla,
    Tahti nousee kortille - ja testi kaatuu (muisti: testi kutsuu funktiota,
    ei kutsupaikkaa)."""
    t = _pl(1, "Tahti", gw6, 0.0)
    t["xp_horizon_total"] = 999.0
    return t


def test_top_100_ulkopuolinen_ei_ole_kortilla_seuraava_ehdokas_on():
    from scripts.render_standouts_card import pick_standouts
    from src.models.fpl_gw_xp import horizon_top_ids_actionable
    players = _kentta()
    taulussa = horizon_top_ids_actionable({"meta": META, "players": players})
    assert 1 not in taulussa and {2, 3} <= taulussa   # fikstuuri tekee mita vaittaa
    s = pick_standouts(players, META)
    nimet = {k: (p or {}).get("web_name") for k, p in s.items()}
    assert "Tahti" not in nimet.values(), nimet
    assert nimet["captain"] == "Kakkonen", nimet
    # Negatiivinen kontrolli: ilman rajausta Tahti olisi kapteeni.
    assert pick_standouts(players[-3:])["captain"]["web_name"] == "Tahti"


def test_ei_ehdokasta_top_100_sisalla_on_no_pick():
    from scripts.render_standouts_card import build_html
    players = [p for p in _kentta(n_tayte=100) if p["id"] >= 1000] + [_tahti()]
    html, s = build_html({"meta": META, "players": players}, log=None)
    assert all(v is None for v in s.values()), s
    assert html.count("no pick this week") == 4 and "Tahti" not in html


def test_standouts_kortilla_ei_ole_sivulta_puuttuvia_lukuja():
    from scripts.render_standouts_card import build_html
    html, _ = build_html({"meta": META, "players": _kentta()}, log=None)
    teksti = re.sub(r"<[^>]+>", " ", html)
    assert "weeks in 10" not in teksti and "median" not in teksti
    assert "GW6 deadline Sat 10 Oct 10:00 UTC · projection run 22 Sep 08:07 UTC" in teksti
    assert "gamble" not in teksti.lower() and "Boom or bust" in teksti


def _xi_kentta():
    """20 kenttapelaajan 'tahtea' tayttaa sivun #gw-xp-listan (top 20), joten
    maalivahti ja halvat tayttopelaajat jaavat sen ulkopuolelle - XI:ssa on
    aina vahintaan yksi listan ulkopuolinen (maalivahti)."""
    clubs = ["ARS", "MCI", "LIV", "CHE", "TOT", "MUN", "NEW", "AVL"]
    ps, pid = [], 0

    def p(name, pos, club, price, xp):
        nonlocal pid
        pid += 1
        return {"id": pid, "web_name": name, "pos": pos, "team": club,
                "team_short": club, "price": price, "status": "a",
                "xmins": 90.0, "p_start": 0.9, "owned_pct": 5.0,
                "xp_per_gw": xp, "xp_horizon_total": xp * 6,
                "gameweeks": [{"gw": 6, "xp": xp,
                               "opponents": [{"opp": "BOU", "venue": "H"}]}]}
    for i in range(3):
        ps.append(p(f"Gk{i}", "GKP", clubs[i], 4.5, [3.0, 2.5, 1.0][i]))
    tahdet = ["DEF"] * 7 + ["MID"] * 7 + ["FWD"] * 6
    for i, pos in enumerate(tahdet):
        ps.append(p(f"Star{i}", pos, clubs[i % 8], 6.0, 8.0 - i * 0.1))
    for i, pos in enumerate(["DEF", "DEF", "MID", "MID", "FWD"]):
        ps.append(p(f"Cheap{i}", pos, clubs[(i + 2) % 8], 4.0, 2.0))
    return ps


def test_xi_luku_vain_gw_xp_listan_pelaajalle_ja_penkki_ilman_lukuja():
    from scripts.render_projected_xi_card import build_html
    from src.models.fpl_gw_xp import gw_xp_list_ids
    data = {"meta": META_XI, "players": _xi_kentta()}
    html, payload = build_html(data, log=None, blocklist=[])
    listalla = gw_xp_list_ids(data, [])
    sq = payload["squad"]
    ulkona = [p for p in sq["xi"] if p["id"] not in listalla]
    assert ulkona, "fikstuurin XI:ssa pitaa olla listan ulkopuolinen pelaaja"
    for p in ulkona + sq["bench"]:
        solu = re.search(r'<b>%s</b><span>([^<]*)(<i>[^<]*</i>)?</span>'
                         % re.escape(p["web_name"]), html)
        assert solu and not solu.group(2), (p["web_name"], solu and solu.group(0))
    for p in sq["xi"]:
        if p["id"] in listalla:
            assert f'<b>{p["web_name"]}</b><span>{p["team_short"]} · <i>' in html
    assert "projected, captain doubled" not in html, (
        "summa jonka kaikki osat eivat nay kortilla ei ole tarkistettavissa")


# (3) TODELLINEN DATA + COMMITTOITU SIVU -------------------------------------

def _osio(page: str, anchor: str) -> str:
    a = page.index(f'id="{anchor}"')
    return page[a:page.index("</table>", a)]


@pytest.fixture(scope="module")
def data():
    p = ROOT / "data" / "fpl_xp_projections.json"
    if not p.exists():
        pytest.skip("artefaktia ei ole")
    return json.loads(p.read_text(encoding="utf-8"))


def test_kortin_nimet_ja_luvut_loytyvat_committoidulta_sivulta(data):
    """Committoitu data + committoitu /fpl/expected-points (sama pari jonka
    tests/test_committed_pages_match_builder.py sitoo yhteen)."""
    from scripts.render_projected_xi_card import build_html as xi_html
    from scripts.render_standouts_card import pick_standouts
    from scripts.publish_gate import load_blocklist
    from src.models.fpl_gw_xp import gw_xp_list_ids
    page = _html.unescape((ROOT / "fpl" / "expected-points.html").read_text(
        encoding="utf-8"))
    top100, gwxp = _osio(page, "top-100"), _osio(page, "gw-xp")
    s = pick_standouts(data["players"], data["meta"])
    for k, p in s.items():
        if p:
            assert f">{p['web_name']}" in top100, (k, p["web_name"])
    bl = load_blocklist()
    _, payload = xi_html(data, log=None, blocklist=bl)
    listalla = gw_xp_list_ids(data, bl)
    for p in payload["squad"]["xi"]:
        if p["id"] in listalla:
            assert f">{p['web_name']}" in gwxp, p["web_name"]
            assert f"{float(p['gw_xp']):.1f}" in gwxp, (p["web_name"], p["gw_xp"])


def test_lokin_ja_kortin_kutsupaikat_antavat_metan():
    """Loki ja kortti valitsevat samat nimet vain jos MOLEMMAT rajaavat poolin
    sivun #top-100:aan (reconcile_with_log kaatuu muuten ennen deadlinea)."""
    import scripts.log_gw_calls as LG
    import scripts.render_standouts_card as S
    assert "pick_standouts(players, meta)" in inspect.getsource(LG)
    assert "pick_standouts(players, meta)" in inspect.getsource(S.build_html)
