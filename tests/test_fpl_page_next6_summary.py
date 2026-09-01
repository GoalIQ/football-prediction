# -*- coding: utf-8 -*-
"""NEXT6-PINTA (30.8.2026): CS-ruudukon yhteenvetosarakkeet fpl.html:ssa.

Tausta. Sivulla oli YKSI sarake otsikolla "Avg", ja se naytti FDR-keskiarvon
prosenttirivin paassa. Arsenalin rivi oli livena 38/37/48/35/49/48 % ja
Avg-sarake "1.00". Lukija joka laskee rivin keskiarvon saa 42,5 %, eika
sivulla ollut mitaan mika kertoisi etta luku on eri suure. SPA
(CleanSheets.svelte) ja mobiili (FantasyScreen, fantasy.horizon.avg_cs_fdr)
nayttivat molemmat luvut nimettyina jo -> tama sivu oli ainoa pinta jossa
lukua ei ollut, ja se on ilmais- ja SEO-pinta.

Portit tassa:
  1. Avg CS% on rivin OMIEN solujen keskiarvo (se luku jonka lukija voi laskea)
  2. sarakkeet ovat nimettyja, paljasta "Avg"-otsikkoa ei saa palata
  3. blank GW (n == 0) -> viiva, EI "0.0%" (nolla ei ole sama kuin ei tietoa)
Jokaisella on negatiivinen kontrolli: portti joka ei voi kaatua ei mittaa
mitaan (muisti: gate-substring-osuma-on-sokea, kontrolli-lapasi-tyhjana).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _fx(gw, cs, fdr=2):
    return {"gw": gw, "opponent": "Testers", "opponent_short": "TST",
            "venue": "H", "fdr": fdr, "cs_pct": cs}


def _row(name, cells, avg_cs, avg_fdr, n):
    return {"team": name, "cells": cells, "avg_cs": avg_cs,
            "avg_fdr": avg_fdr, "n": n}


def _ctx(rows, gws=(2, 3, 4)):
    return {"gws": list(gws), "fdr_rows": rows}


def _summary_nums(html, team):
    """Rivin kolme yhteenvetosolua: (avg_cs, avg_fdr, games)."""
    row = re.search(r'<td class="team">%s</td>.*?</tr>' % re.escape(team), html)
    assert row, "riviä %s ei loytynyt" % team
    tail = row.group(0)
    cs = re.search(r'<td class="num"><strong>([0-9.]+)%</strong></td>', tail)
    rest = re.findall(r'<td class="num m-hide">([^<]*)</td>', tail)
    return (cs.group(1) if cs else None), rest[-2], rest[-1]


# ---------------------------------------------------------------------------
# 1. Avg CS% = rivin omien solujen keskiarvo
# ---------------------------------------------------------------------------
def test_avg_cs_equals_mean_of_the_rows_own_cells():
    from scripts.build_fpl_page import fdr_grid_html
    cells = [_fx(2, 38.0), _fx(3, 37.0), _fx(4, 48.0)]
    mean = round(sum(c["cs_pct"] for c in cells) / len(cells), 1)  # 41.0
    html = fdr_grid_html(_ctx([_row("Arsenal", cells, mean, 1.0, 3)]))
    cs, fdr, games = _summary_nums(html, "Arsenal")
    assert cs == "41.0", cs
    assert fdr == "1.00", fdr
    assert games == "3", games


def test_negative_control_avg_cs_that_contradicts_its_cells_is_visible():
    """Kontrolli: jos Avg CS% ei ole solujen keskiarvo, testi 1 kaatuu.

    Tama on se vika joka oli livena (sarakkeessa oli FDR eika CS%), joten
    portin on erotettava se. Ilman tata kontrollia testi 1 lapaisisi silla
    etta se lukee saman luvun jonka se itse syotti.
    """
    from scripts.build_fpl_page import fdr_grid_html
    cells = [_fx(2, 38.0), _fx(3, 37.0), _fx(4, 48.0)]
    mean = round(sum(c["cs_pct"] for c in cells) / len(cells), 1)
    # Vaara luku: FDR-keskiarvo CS-sarakkeessa, kuten sivulla oli
    html = fdr_grid_html(_ctx([_row("Arsenal", cells, 1.0, 1.0, 3)]))
    cs, _, _ = _summary_nums(html, "Arsenal")
    assert cs != "%.1f" % mean, "kontrolli ei erottanut vaaraa lukua"
    assert cs == "1.0"


# ---------------------------------------------------------------------------
# 2. Sarakkeet ovat nimettyja
# ---------------------------------------------------------------------------
def test_summary_columns_are_named():
    from scripts.build_fpl_page import fdr_grid_html
    html = fdr_grid_html(_ctx([_row("Arsenal", [_fx(2, 38.0)], 38.0, 1.0, 1)]))
    assert '<th scope="col" class="num">Avg CS%</th>' in html
    assert 'Avg FDR</th>' in html
    assert 'Games</th>' in html


def test_negative_control_bare_avg_header_must_not_return():
    """Paljas "Avg" oli koko vian ydin: se ei kerro mita suuretta katsotaan."""
    from scripts.build_fpl_page import fdr_grid_html
    html = fdr_grid_html(_ctx([_row("Arsenal", [_fx(2, 38.0)], 38.0, 1.0, 1)]))
    assert '<th scope="col" class="num">Avg</th>' not in html


# ---------------------------------------------------------------------------
# 3. Blank GW: viiva eika mitattu nolla
# ---------------------------------------------------------------------------
def test_blank_gameweek_renders_dash_not_zero_percent():
    """build_fpl_phase0 antaa tyhjalle ikkunalle next_avg_cs_pct = 0.0.

    Jos sivu renderoisi sen sellaisenaan, se vaittaisi MITATUN nollan
    todennakoisyyden joukkueelle jolla ei ole otteluita lainkaan.
    """
    from scripts.build_fpl_page import fdr_grid_html
    html = fdr_grid_html(_ctx([_row("Blankers", [None], 0.0, 0.0, 0)]))
    cs, fdr, games = _summary_nums(html, "Blankers")
    assert cs is None, "blank GW ei saa renderoida CS-prosenttia"
    assert "0.0%" not in html
    assert fdr == "-"
    assert games == "0"


def test_negative_control_non_blank_row_still_shows_numbers():
    """Kontrolli: viiva-haara ei saa niella tavallista rivia."""
    from scripts.build_fpl_page import fdr_grid_html
    html = fdr_grid_html(_ctx([_row("Playing", [_fx(2, 30.0)], 30.0, 2.0, 1)]))
    cs, fdr, games = _summary_nums(html, "Playing")
    assert cs == "30.0"
    assert fdr == "2.00"
    assert games == "1"


# ---------------------------------------------------------------------------
# 4. Double gameweek: testi ajaa OIKEAN rakennuspolun
# ---------------------------------------------------------------------------
# Aiempi versio tasta syotti rivin kasin `fdr_grid_html`:lle ja meni lapi.
# Se ei koskaan ajanut `fdr_rows_from_teams`:ia, eli portti mittasi eri
# koodipolkua kuin tuotanto: testi oli vihrea samalla kun oikea buildi
# pudotti doublen toisen ottelun (muisti: portti-voi-mitata-eri-koodipolkua).


def _team(name, fixtures, avg_cs, avg_fdr, n):
    return {"name": name, "fixtures": fixtures, "next_avg_cs_pct": avg_cs,
            "next_avg_fdr": avg_fdr, "next_n": n}


def test_games_column_comes_from_the_real_row_builder():
    from scripts.build_fpl_page import fdr_grid_html, fdr_rows_from_teams
    teams = [_team("Singles", [_fx(2, 30.0), _fx(3, 40.0)], 35.0, 2.0, 2)]
    rows = fdr_rows_from_teams(teams, [2, 3])
    html = fdr_grid_html({"gws": [2, 3], "fdr_rows": rows})
    cs, fdr, games = _summary_nums(html, "Singles")
    assert (cs, fdr, games) == ("35.0", "2.00", "2")


def test_double_gameweek_keeps_both_fixtures_in_the_grid():
    """KORJATTU 1.9 (QUEUE: FDR-GRID-DGW). Ennen: rivilla oli yksi solu ja

    toinen ottelu oli olemassa vain keskiarvossa ja Games-luvussa. Nyt
    `fdr_rows_from_teams` palauttaa molemmat otteluita `cells`-listassa
    (xfail-merkinta poistettu, testi XPASSasi ennen tata siivousta)."""
    from scripts.build_fpl_page import fdr_rows_from_teams
    teams = [_team("Doublers", [_fx(2, 30.0), _fx(2, 40.0)], 35.0, 2.0, 2)]
    rows = fdr_rows_from_teams(teams, [2])
    kept = [c for c in rows[0]["cells"] if c is not None]
    assert len(kept) == 2, "doublen molempien otteluiden pitaisi sailya"


# ---------------------------------------------------------------------------
# 5. Solun vari ja solun luku samasta arvosta (portti k2, B3)
# ---------------------------------------------------------------------------
# Caption lupaa "hard ones (20% or less) in coral". Luokka laskettiin ennen
# raakaarvosta ja luku naytettiin :.0f:lla, joten 20.1 luki "20%" ilman
# coralia. Livena kolme solua (MCI GW4, MUN GW4, EVE GW6) kumosi captionin.
import re as _re  # noqa: E402


def _cells_with_class(html):
    return _re.findall(
        r'<td class="num([^"]*)"><a class="fdr"[^>]*>[^<]*?(\d+)%</a></td>', html)


def test_cell_colour_matches_the_number_the_reader_sees():
    from scripts.build_fpl_page import fdr_grid_html, fdr_rows_from_teams
    # 20.1 nakyy "20%" -> captionin mukaan sen ON oltava coral
    teams = [_team("Edge", [_fx(2, 20.1), _fx(3, 43.6)], 31.9, 3.0, 2)]
    rows = fdr_rows_from_teams(teams, [2, 3])
    html = fdr_grid_html({"gws": [2, 3], "fdr_rows": rows})
    got = _cells_with_class(html)
    assert len(got) == 2, got
    by_num = {n: c for c, n in got}
    assert "is-hard" in by_num["20"], f'20% ilman coralia: {by_num["20"]!r}'
    assert "is-easy" in by_num["44"], f'44% ilman goldia: {by_num["44"]!r}'


def test_negative_control_values_clearly_inside_the_band_get_no_class():
    """Kontrolli: ilman tata edellinen lapaisisi toteutuksella joka
    varittaa jokaisen solun."""
    from scripts.build_fpl_page import fdr_grid_html, fdr_rows_from_teams
    teams = [_team("Mid", [_fx(2, 30.0)], 30.0, 3.0, 1)]
    rows = fdr_rows_from_teams(teams, [2])
    html = fdr_grid_html({"gws": [2], "fdr_rows": rows})
    cls, num = _cells_with_class(html)[0]
    assert num == "30"
    assert "is-hard" not in cls and "is-easy" not in cls, cls


def test_negative_control_raw_value_below_the_line_is_not_promoted():
    """19.4 nakyy "19%" ja on coral kummallakin laskutavalla; 20.6 nakyy
    "21%" eika saa olla coral vaikka raaka-arvo on lahella rajaa."""
    from scripts.build_fpl_page import fdr_grid_html, fdr_rows_from_teams
    teams = [_team("Two", [_fx(2, 19.4), _fx(3, 20.6)], 20.0, 4.0, 2)]
    rows = fdr_rows_from_teams(teams, [2, 3])
    html = fdr_grid_html({"gws": [2, 3], "fdr_rows": rows})
    by_num = {n: c for c, n in _cells_with_class(html)}
    assert "is-hard" in by_num["19"]
    assert "is-hard" not in by_num["21"], by_num["21"]


def test_double_gameweek_renders_both_fixtures_in_one_cell_via_real_build_path():
    """1.9, FDR-GRID-DGW: proof from the REAL path (fdr_rows_from_teams ->
    fdr_grid_html), not hand-fed HTML (muisti: portti-voi-mitata-eri-koodipolkua).

    Rivilla on double GW2:ssa, yksittainen ottelu GW3:ssa ja blank GW4:ssa.
    Tama todistaa etta double ei enaa hukkaa ottelua eika luo ylimaaraista
    saraketta (rivin <td>-maara pysyy tasan gws-listan mittaisena + team +
    kolme yhteenvetosolua), ja etta yhden ottelun sarakkeet renderoivat
    tismalleen kuten ennenkin.
    """
    from scripts.build_fpl_page import fdr_grid_html, fdr_rows_from_teams
    teams = [_team("Doublers", [_fx(2, 30.0), _fx(2, 40.0), _fx(3, 50.0)],
                    35.0, 2.0, 3)]
    rows = fdr_rows_from_teams(teams, [2, 3, 4])
    html = fdr_grid_html({"gws": [2, 3, 4], "fdr_rows": rows})
    row = re.search(r'<td class="team">Doublers</td>.*?</tr>', html)
    assert row, "riviä ei löytynyt"
    tail = row.group(0)
    # team + 3 GW-saraketta (GW2 double, GW3 single, GW4 blank) + 3 yhteenvetosolua
    assert tail.count("<td") == 7, f"sarakemaara muuttui: {tail!r}"
    assert tail.count('<a class="fdr"') == 3, (
        "GW2:n molemmat ottelut + GW3:n yksi ottelu = 3 linkkia yhteensa")
    assert "40%" in tail and "30%" in tail, "molemmat GW2-otteluista puuttuvat solusta"
    assert "50%" in tail, "GW3:n yksittäinen ottelu ei säilynyt"
    assert '<td class="num">-</td>' in tail, "GW4:n blank ei renderoinut viivaa"


def test_negative_control_single_fixture_cell_html_is_unchanged():
    """Kontrolli: DGW-korjaus ei saa muuttaa tavallisen (ei-double) solun
    HTML-muotoa. Ilman tata edellinen testi lapaisisi myos toteutuksella
    joka rikkoo GW3:n yhden ottelun solun (esim. kietoo senkin dgw-haaraan)."""
    from scripts.build_fpl_page import fdr_grid_html, fdr_rows_from_teams
    teams = [_team("Singles", [_fx(2, 30.0), _fx(3, 40.0)], 35.0, 2.0, 2)]
    rows = fdr_rows_from_teams(teams, [2, 3])
    html = fdr_grid_html({"gws": [2, 3], "fdr_rows": rows})
    assert '<td class="num dgw">' not in html, "ei-double solu meni dgw-haaraan"
    assert html.count('<a class="fdr"') == 2


def test_negative_control_normal_row_still_returns_one_row():
    """Kontrolli: rakennuspolku ei saa kadottaa tai kahdentaa rivia."""
    from scripts.build_fpl_page import fdr_rows_from_teams
    teams = [_team("Normal", [_fx(2, 30.0), _fx(3, 40.0)], 35.0, 2.0, 2)]
    assert len(fdr_rows_from_teams(teams, [2, 3])) == 1


def test_negative_control_blank_gameweek_does_not_trip_the_guard():
    """Blank GW: soluja enemman kuin otteluita, ei vahemman. Ei saa kaatua."""
    from scripts.build_fpl_page import fdr_rows_from_teams
    teams = [_team("Blank", [], 0.0, 0.0, 0)]
    assert fdr_rows_from_teams(teams, [2, 3])[0]["n"] == 0
