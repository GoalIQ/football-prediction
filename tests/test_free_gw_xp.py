# -*- coding: utf-8 -*-
"""FREE-GW-XP (Villen GO 30.8.2026): yhden kierroksen xP top 20 ilmaispinnalla.

Tama on samalla KORTTI-TARKISTUSREITTI-rivin portti. Kortin alapalkki lupaa
etta luvut voi tarkistaa, ja 30.8 mitattu ettei sivulla ollut yhtakaan kortin
lukua: sivu rankkasi kuuden kierroksen summalla (Haaland 35.6 / 5.94) ja
kortti yhden kierroksen xP:lla (6.2). Portti mittaa etta molemmat pinnat
lukevat SAMAA funktiota, ei etta ne nayttavat samankaltaisilta.

Jokaiselle vahdille positiivinen JA negatiivinen kontrolli (muisti:
gate-substring-osuma-on-sokea, kontrolli-lapaisi-tyhjana).

Ajo: .venv/Scripts/python -m pytest tests/test_free_gw_xp.py -q
"""
import re
from unittest import mock

import pytest

from src.models.fpl_gw_xp import (FREE_TOP_N, eligible, excluded, free_rows,
                                  gw_xp, opponent_text, top_projected)


def _pl(pid, name, team, xp3, pos="MID", status="a", price=6.0, gw=3):
    return {"id": pid, "web_name": name, "team": team, "team_short": team[:3].upper(),
            "pos": pos, "status": status, "price": price, "p_start": 0.9,
            "predicted_starts": 90,
            "gameweeks": [{"gw": gw, "opponents": [{"opp": "XYZ", "venue": "H"}],
                           "xp": xp3}]}


def _meta(deadline=3, nxt=2, available=True):
    return {"available": available, "deadline_gameweek": deadline,
            "next_gameweek": nxt, "generated_at": "2026-08-30T14:10:20+00:00"}


# --- gw_xp: EI xp_per_gw ---------------------------------------------------

def test_gw_xp_lukee_kierroksen_oman_luvun():
    p = _pl(1, "A", "Man City", 6.2)
    p["xp_per_gw"] = 5.94          # ansa: horisontin keskiarvo
    p["xp_horizon_total"] = 35.66
    assert gw_xp(p, 3) == 6.2


def test_gw_xp_on_none_kun_kierros_puuttuu():
    # Negatiivinen kontrolli: blank GW ei saa palauttaa 0.0, joka lukisi
    # "ei tuota pisteita" (muisti: nolla-ei-ole-sama-kuin-ei-tietoa).
    assert gw_xp(_pl(1, "A", "Man City", 6.2, gw=3), 4) is None


# --- kierrosvalinta: actionable, ei next ------------------------------------

def test_ilmaispinta_kayttaa_deadline_kierrosta_ei_next_gameweekia():
    """🔴 Tama on se vika joka on toistunut viidesti (fpl_gameweek-docstring).

    `next_gameweek` oli 30.8 **2** ja `deadline_gameweek` **3**: GW2 oli
    kesken. Ranking kierrokselle johon ei voi enaa siirtaa ketaan ei ole
    ennuste.
    """
    p = _pl(1, "A", "Man City", 6.2, gw=3)
    p["gameweeks"].insert(0, {"gw": 2, "opponents": [{"opp": "CRY", "venue": "A"}],
                              "xp": 5.77})
    gw, rows = free_rows({"meta": _meta(deadline=3, nxt=2), "players": [p]})
    assert gw == 3
    assert gw_xp(rows[0], gw) == 6.2, "otti KESKEN olevan kierroksen luvun"


def test_kierros_seuraa_metaa_eika_ole_kovakoodattu():
    p = _pl(1, "A", "Man City", 7.7, gw=9)
    gw, rows = free_rows({"meta": _meta(deadline=9, nxt=9), "players": [p]})
    assert (gw, len(rows)) == (9, 1)


# --- seurakatto -------------------------------------------------------------

def test_seurakatto_rajaa_kolmeen_per_seura():
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(8)]
    rows = top_projected(players, 3, FREE_TOP_N)
    assert len(rows) == 3


def test_ilman_kattoa_lista_olisi_yhta_seuraa_negatiivinen_kontrolli():
    """Ilman tata testi yllä lapaisisi myos silloin kun pooli sattuu olemaan
    pieni: nyt on osoitettu etta katto NIMENOMAAN pudottaa rivit pois."""
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(8)]
    with mock.patch("src.models.fpl_rate_team.MAX_PER_CLUB", 8):
        assert len(top_projected(players, 3, FREE_TOP_N)) == 8


def test_katto_luetaan_jaetusta_vakiosta_kutsuhetkella():
    # Jos katto tuotaisiin nimena import-hetkella, kortti ja sivu voisivat
    # ajautua eri saantoon ilman etta mikaan huutaa.
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(8)]
    with mock.patch("src.models.fpl_rate_team.MAX_PER_CLUB", 2):
        assert len(top_projected(players, 3, FREE_TOP_N)) == 2


def test_katto_ei_lyhenna_listaa_kun_seuroja_riittaa():
    players = [_pl(i, f"P{i}", f"Club{i}", 9.0 - i * 0.1) for i in range(25)]
    assert len(top_projected(players, 3, FREE_TOP_N)) == FREE_TOP_N


# --- estot ------------------------------------------------------------------

def test_loukkaantunut_ei_nouse_ilmaispinnalle():
    players = [_pl(1, "Hurt", "Aston Villa", 9.9, status="i"),
               _pl(2, "Fit", "Brentford", 4.0)]
    assert [r["web_name"] for r in top_projected(players, 3, FREE_TOP_N)] == ["Fit"]


def test_estolistan_nimi_ei_nouse_ilmaispinnalle():
    # Sukunimiosalla: "M.Thiaw" ja "Thiaw" ovat sama pelaaja.
    assert excluded("M.Thiaw") and excluded("Thiaw")
    players = [_pl(1, "M.Thiaw", "Newcastle", 9.9), _pl(2, "Fit", "Brentford", 4.0)]
    assert [r["web_name"] for r in top_projected(players, 3, FREE_TOP_N)] == ["Fit"]


def test_estolista_tiedostosta_luetaan_myos():
    players = [_pl(1, "Banned", "Newcastle", 9.9), _pl(2, "Fit", "Brentford", 4.0)]
    bl = [{"name": "Banned"}]
    assert [r["web_name"] for r in top_projected(players, 3, FREE_TOP_N, bl)] == ["Fit"]


def test_tavallinen_nimi_ei_esty_negatiivinen_kontrolli():
    assert not excluded("Haaland")
    assert len(eligible([_pl(1, "Haaland", "Man City", 6.2)], 3)) == 1


# --- jarjestys ja tasapelit -------------------------------------------------

def test_jarjestys_on_laskeva_gw_xp():
    players = [_pl(1, "Low", "A", 2.0), _pl(2, "High", "B", 8.0), _pl(3, "Mid", "C", 5.0)]
    assert [r["web_name"] for r in top_projected(players, 3, FREE_TOP_N)] == \
        ["High", "Mid", "Low"]


def test_tasapeli_ratkeaa_idlla_eika_nimella():
    # web_name ei ole avain (muisti: web-name-ei-ole-avain). Ilman
    # deterministista ratkaisijaa kortti ja sivu voisivat jarjestaa eri tavalla.
    a = [_pl(7, "Same", "A", 4.8), _pl(3, "Same", "B", 4.8)]
    b = list(reversed(a))
    assert [r["id"] for r in top_projected(a, 3, FREE_TOP_N)] == \
           [r["id"] for r in top_projected(b, 3, FREE_TOP_N)] == [3, 7]


# --- double gameweek --------------------------------------------------------

def test_doublen_molemmat_ottelut_nakyvat():
    """🔴 FDR-GRID-DGW: ruudukossa doublen jalkimmainen ottelu katosi, koska
    ottelut avainnettiin gameweekilla. Tassa lahde on lista, ja se pysyy."""
    p = _pl(1, "A", "Man City", 9.0)
    p["gameweeks"][0]["opponents"] = [{"opp": "COV", "venue": "H"},
                                      {"opp": "AVL", "venue": "A"}]
    teksti = opponent_text(p, 3)
    assert "COV (H)" in teksti and "AVL (A)" in teksti


def test_blank_gw_sanotaan_sanana_ei_tyhjana():
    p = _pl(1, "A", "Man City", 0.0)
    p["gameweeks"][0]["opponents"] = []
    assert opponent_text(p, 3) == "blank"


# --- free_rows: fail-closed -------------------------------------------------

@pytest.mark.parametrize("xp", [
    {"meta": _meta(available=False), "players": [_pl(1, "A", "B", 5.0)]},
    {"meta": _meta(), "players": []},
    {"meta": {"available": True}, "players": [_pl(1, "A", "B", 5.0)]},
    {},
])
def test_osio_jaa_pois_kun_lahde_ei_kelpaa(xp):
    # Tyhja osio on parempi kuin osio joka nayttaa vaaran kierroksen lukuja.
    assert free_rows(xp) == (None, [])


def test_kelvollinen_lahde_tuottaa_rivit_negatiivinen_kontrolli():
    gw, rows = free_rows({"meta": _meta(), "players": [_pl(1, "A", "Brentford", 5.0)]})
    assert (gw, len(rows)) == (3, 1)


def test_rivimaara_on_villen_hyvaksyma_20():
    # FREE_TOP_N ei ole viritysparametri: sen kasvattaminen on
    # hinnoittelupaatos (Villen GO 30.8 koski tasmalleen lukua 20).
    assert FREE_TOP_N == 20


# --- integraatio: kortti ja sivu ovat SAMA lista ----------------------------

def test_kortti_ja_ilmaissivu_kayttavat_samaa_valintafunktiota():
    """Ei "samankaltainen taulukko" vaan sama funktio.

    Jos kortti saisi oman silmukkansa, listat ajautuisivat erilleen hiljaa ja
    tarkistusreitti nayttaisi ERI luvun kuin kortti - pahempi kuin puuttuva
    reitti, koska se nayttaa toimivalta.
    """
    import scripts.render_projected_xi_card as card
    import src.models.fpl_gw_xp as shared
    assert card.top_projected(
        [_pl(i, f"P{i}", f"C{i}", 9.0 - i) for i in range(5)], 3, 3
    ) == shared.top_projected(
        [_pl(i, f"P{i}", f"C{i}", 9.0 - i) for i in range(5)], 3, 3)
    for fn in ("gw_xp", "eligible"):
        assert getattr(card, fn) is getattr(shared, fn), f"{fn} eriytyi"


def test_kortin_alapalkki_osoittaa_ankkuriin_ei_sivun_juureen():
    """KORTTI-TARKISTUSREITTI: juuri rankkaa 6 GW:n summalla, ankkuri ei."""
    src = (__import__("pathlib").Path(__file__).resolve().parents[1]
           / "scripts" / "render_projected_xi_card.py").read_text(encoding="utf-8")
    ftr = re.search(r"'<span>([^<]*goaliq\.app/fpl/expected-points[^<]*)</span></div>'", src)
    assert ftr, "alapalkin tarkistusreitti puuttuu kokonaan"
    assert ftr.group(1).endswith("#gw-xp"), ftr.group(1)


def test_kortin_luvut_loytyvat_RENDEROIDULTA_sivulta():
    """Tarkistusreitti mitataan sivun HTML:sta, ei valintafunktiosta.

    Funktiotason identiteetti ei riita: renderointi voi pyoristaa toisin,
    pudottaa rivin tai jarjestaa uudelleen, ja lukija kavelee reitin sivulle
    eika funktioon (muisti: generoitu-sivu-verifioi-regeneroimalla,
    verifiointitaulukko-taytettiin-kavelematta).
    """
    import html as _html
    import json
    from pathlib import Path

    from scripts.publish_gate import load_blocklist
    from scripts.render_projected_xi_card import top_projected as card_top
    from src.models.fpl_gameweek import actionable_gameweek
    from src.models.fpl_gw_xp import gw_xp as _gwxp

    root = Path(__file__).resolve().parents[1]
    sivu = root / "fpl" / "expected-points.html"
    data = root / "data" / "fpl_xp_projections.json"
    if not (sivu.exists() and data.exists()):
        pytest.skip("sivua tai artefaktia ei ole rakennettu")

    xp = json.loads(data.read_text(encoding="utf-8"))
    gw = actionable_gameweek(xp["meta"])
    kortti = card_top(xp["players"], gw, 15, load_blocklist())

    h = sivu.read_text(encoding="utf-8")
    i = h.find('<h2 id="gw-xp">')
    assert i > 0, "sivulta puuttuu #gw-xp -osio"
    sec = h[i:h.find("<h2", i + 5)]
    solut = re.findall(
        r'<td>([^<]+)</td><td class="tm">.*?<td class="n">[\d.]+</td>'
        r'<td class="n hi">([\d.]+)</td>', sec)
    ren = {_html.unescape(n): v for n, v in solut}
    assert len(ren) == FREE_TOP_N, f"sivulla {len(ren)} rivia, odotettu {FREE_TOP_N}"

    puuttuu = [r["web_name"] for r in kortti if r["web_name"] not in ren]
    assert not puuttuu, f"kortin rivit joita ei voi tarkistaa sivulta: {puuttuu}"
    eroaa = {r["web_name"]: (f"{_gwxp(r, gw):.1f}", ren[r["web_name"]])
             for r in kortti if ren[r["web_name"]] != f"{_gwxp(r, gw):.1f}"}
    assert not eroaa, f"kortti ja sivu nayttavat eri luvun: {eroaa}"


def test_kortin_lista_on_sivun_listan_alkuosa():
    """Prefiksiominaisuus: top 15 == top 20:n 15 ensimmaista.

    Copy lupaa etta kortin lista ON sivun lista. Greedy-seurakatto on
    prefiksistabiili, joten lupaus pitaa - mutta se oli tahan asti vain
    IMPLISIITTINEN. Jos katto joskus muuttuu esim. tasapainottavaksi (tayta
    20 paikkaa mahdollisimman monesta seurasta), prefiksi katkeaisi ja copy
    valehtelisi ilman etta mikaan huutaa.
    """
    players = ([_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(6)]
               + [_pl(100 + i, f"P{i}", f"Club{i}", 8.0 - i * 0.1) for i in range(30)])
    top15 = top_projected(players, 3, 15)
    top20 = top_projected(players, 3, FREE_TOP_N)
    assert len(top15) == 15 and len(top20) == FREE_TOP_N
    assert [p["id"] for p in top15] == [p["id"] for p in top20[:15]]


def test_prefiksitesti_kaataisi_tasapainottavan_katon():
    """Negatiivinen kontrolli: osoita etta testi ylla mittaa jotain.

    Pienemmalla katolla lista lyhenee, ja prefiksi sailyy silti - se on
    juuri se ominaisuus jota copy nojaa.
    """
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(6)]
    with mock.patch("src.models.fpl_rate_team.MAX_PER_CLUB", 4):
        assert [p["id"] for p in top_projected(players, 3, 2)] == \
               [p["id"] for p in top_projected(players, 3, 4)][:2]


# --- standouts-kortti: otsikko ja luvut samalta kierrokselta ---------------

def _standouts_data(dist_gw: int, title_gw: int):
    p = _pl(1, "A", "Man City", 6.2, gw=title_gw)
    p["gameweeks"].append({"gw": dist_gw, "opponents": [{"opp": "CRY", "venue": "A"}],
                           "xp": 5.77})
    p["xp_dist"] = {"gw": dist_gw, "p_haul": 0.14, "p_blank": 0.17, "p10": 2, "p90": 11}
    return {"meta": _meta(deadline=title_gw, nxt=dist_gw), "players": [p]}


def test_standouts_kaatuu_kun_otsikko_ja_luvut_eri_kierrokselta():
    """🔴 Kortti sanoi GW3 ja naytti GW2:n luvut (captain 5.77 vs 6.2)."""
    import scripts.render_standouts_card as card
    with pytest.raises(SystemExit) as e:
        card.build_html(_standouts_data(dist_gw=2, title_gw=3))
    assert "STANDOUTS-KIERROSRISTIRIITA" in str(e.value)


def test_myos_gw_calls_loki_perii_saman_vahdin():
    """🔴 `pick_standouts`illa on KAKSI kuluttajaa. Vahti vain kortilla olisi
    jattanyt lokipolun auki, ja loki on gradattava kutsu eli virhe jaisi
    pysyvaksi. Tanaan lokipolku on turvassa vain koska GW3:n freezea ei ole -
    se on sattuma, ei vaite (muisti: yksi-renderointipolku-kahdesta)."""
    import scripts.log_gw_calls as lg
    assert hasattr(lg, "assert_dist_gameweek"), "loki ei importoi vahtia"
    src = (__import__("pathlib").Path(__file__).resolve().parents[1]
           / "scripts" / "log_gw_calls.py").read_text(encoding="utf-8")
    assert "assert_dist_gameweek(players, gw)" in src, "vahtia ei kutsuta"


def test_vahti_on_valintafunktion_luona_ei_vain_renderoijassa():
    import scripts.render_standouts_card as card
    with pytest.raises(SystemExit):
        card.assert_dist_gameweek(
            [{"xp_dist": {"gw": 2}}, {"xp_dist": {"gw": 2}}], 3)
    card.assert_dist_gameweek([{"xp_dist": {"gw": 3}}], 3)   # ei kaadu
    card.assert_dist_gameweek([{"web_name": "ei distia"}], 3)  # ei dataa -> ei vaitetta


def test_standouts_ei_kaadu_kun_kierrokset_tasmaavat():
    """Negatiivinen kontrolli: ilman tata vahti voisi kaataa kortin aina."""
    import scripts.render_standouts_card as card
    html, _ = card.build_html(_standouts_data(dist_gw=3, title_gw=3))
    assert "GW3" in html


# --- kapteenikandidaattien seurakatto (Villen paatos 30.8) -----------------

def test_kapteenikatto_on_kaksi_ei_kolme():
    from src.models.fpl_gw_xp import MAX_CAPTAIN_PER_CLUB
    assert MAX_CAPTAIN_PER_CLUB == 2


def test_kolmen_karki_ei_voi_olla_yhta_seuraa():
    """🔴 Mitattu: GW3 ja GW5 antoivat karjen jossa kaikki kolme olivat MCI:n.

    Kolme saman joukkueen pelaajaa samaa vastustajaa vastaan on yksi veto
    kolmella nimella - jos joukkue epaonnistuu, kaikki kolme kaatuvat yhdessa.
    """
    from src.models.fpl_gw_xp import MAX_CAPTAIN_PER_CLUB
    players = ([_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(6)]
               + [_pl(50 + i, f"Muu{i}", f"Club{i}", 4.0 - i * 0.1) for i in range(5)])
    top3 = top_projected(players, 3, 3, max_per_club=MAX_CAPTAIN_PER_CLUB)
    seurat = {p["team"] for p in top3}
    assert len(top3) == 3
    assert len(seurat) >= 2, f"kolmen karki on yhta seuraa: {seurat}"


def test_oletuskatto_on_yha_fpl_saanto_eika_kapteenikatto():
    """Negatiivinen kontrolli: ilmaispinnan taulukko EI saa kaventua kahteen -
    se noudattaa FPL:n saantoa (3), ja kapteenikatto on eri paatos."""
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(6)]
    assert len(top_projected(players, 3, FREE_TOP_N)) == 3


def test_kapteenisivu_kayttaa_kapteenikattoa():
    src = (__import__("pathlib").Path(__file__).resolve().parents[1]
           / "scripts" / "build_fpl_longtail.py").read_text(encoding="utf-8")
    assert "max_per_club=MAX_CAPTAIN_PER_CLUB" in src, "kapteenisivu ei raja kahteen"


def test_tuotannon_kapteenisivulla_on_vahintaan_kaksi_seuraa():
    """Elava mittaus rakennetulta sivulta."""
    import json
    from pathlib import Path
    from scripts.publish_gate import load_blocklist
    from src.models.fpl_gameweek import actionable_gameweek
    from src.models.fpl_gw_xp import MAX_CAPTAIN_PER_CLUB
    f = Path(__file__).resolve().parents[1] / "data" / "fpl_xp_projections.json"
    if not f.exists():
        pytest.skip("artefaktia ei ole")
    xp = json.loads(f.read_text(encoding="utf-8"))
    gw = actionable_gameweek(xp["meta"])
    top3 = top_projected(xp["players"], gw, 3, load_blocklist(),
                         max_per_club=MAX_CAPTAIN_PER_CLUB)
    assert len({p["team_short"] for p in top3}) >= 2, [p["web_name"] for p in top3]
