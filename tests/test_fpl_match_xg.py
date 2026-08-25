"""xG-syote FPL:n omasta datasta kun Understat ei vastaa (25.8.2026).

🔴 TAUSTA. Mallin xG tuli Understatista, ja Understat lakkasi palvelemasta
palvelinhakuja. Mitattu KONTROLLIN kanssa:
    understat.com/league/EPL/2026 -> HTTP 200, 18 689 B, ei datalohkoa
    understat.com/league/EPL/2025 -> HTTP 200, 18 689 B, ei datalohkoa
Identtiset, eli kyse ei ole uuden kauden puuttumisesta vaan JS-kuoresta
kaikille kausille. Seuraus: 26/27:n otteluista 0/10 kantoi xG:ta ja DC-fitti
sovitti pelkkiin maaleihin - HILJAA, koska `home_xg` on vain `NA`.
"""
from __future__ import annotations

import pandas as pd

from src.data import fpl_match_xg as mx
from src.data.loader import _taydenna_xg_fpl_datasta as taydenna


def _df(rivit):
    return pd.DataFrame(rivit, columns=["home_team", "away_team", "season",
                                        "home_xg", "away_xg"])


def test_taydentaa_vain_puuttuvat(monkeypatch):
    """🔴 Understatin xG jaa koskemattomaksi siella missa se on. Kahden
    lahteen sekoittaminen samalle riville tekisi fitista epamaaraisen."""
    monkeypatch.setattr(mx, "match_xg_rows", lambda k: [
        {"home_team": "Arsenal", "away_team": "Coventry",
         "home_xg": 1.88, "away_xg": 0.21},
        {"home_team": "Hull", "away_team": "Man United",
         "home_xg": 1.08, "away_xg": 1.82},
    ])
    df = _df([
        ["Arsenal", "Coventry", "2627", None, None],      # puuttuu -> taytetaan
        ["Hull", "Man United", "2627", 9.99, 9.99],       # ON -> ei kosketa
    ])
    out = taydenna(df)
    assert out.at[0, "home_xg"] == 1.88
    assert out.at[1, "home_xg"] == 9.99, "olemassa olevaa xG:ta ei saa korvata"


def test_ottelu_jota_ei_loydy_jaa_tyhjaksi(monkeypatch):
    """Puuttuva rivi EI nollaudu: 0.0 xG olisi eri VAITE kuin 'emme tieda'."""
    monkeypatch.setattr(mx, "match_xg_rows", lambda k: [])
    df = _df([["Arsenal", "Coventry", "2627", None, None]])
    out = taydenna(df)
    assert pd.isna(out.at[0, "home_xg"])


def test_lahteen_vika_ei_kaada_latausta(monkeypatch):
    """🔴 Fitti jatkaa maaleilla kuten ennen tata funktiota. Latauksen
    kaataminen xG-rikastuksen takia olisi pahempi kuin puuttuva xG."""
    def rikki(_k):
        raise RuntimeError("FPL alhaalla")
    monkeypatch.setattr(mx, "match_xg_rows", rikki)
    df = _df([["Arsenal", "Coventry", "2627", None, None]])
    out = taydenna(df)
    assert len(out) == 1 and pd.isna(out.at[0, "home_xg"])


def test_tyhja_tai_kentaton_ei_kaadu():
    assert taydenna(pd.DataFrame()).empty
    d = pd.DataFrame([{"home_team": "A", "away_team": "B"}])
    assert len(taydenna(d)) == 1


def test_nimikartta_ei_saa_jattaa_aukkoja():
    """🔴 FPL:n ja football-datan nimet eroavat viidessa kohdassa. Jos uusi
    kausi nimeaa joukkueen uudelleen, kartoittamaton nimi pudottaisi sen
    ottelut HILJAA - ja hiljainen pudotus nayttaa 'ei xG:ta talle ottelulle'.
    """
    fd_nimet = {"Coventry", "Hull", "Ipswich", "Man United", "Tottenham",
                "Arsenal", "Liverpool"}
    tiimit = [{"name": "Coventry City"}, {"name": "Hull City"},
              {"name": "Ipswich Town"}, {"name": "Man Utd"},
              {"name": "Spurs"}, {"name": "Arsenal"}]
    assert mx.nimikartta_aukot(tiimit, fd_nimet) == []
    # ...ja kartoittamaton nimi LOYTYY
    aukot = mx.nimikartta_aukot(tiimit + [{"name": "Wrexham AFC"}], fd_nimet)
    assert aukot and "Wrexham" in aukot[0]


def test_puolikas_ottelu_jatetaan_pois():
    """Toinen puoli yksin ei ole ottelun xG. `match_xg_rows` palauttaa rivin
    vain kun MOLEMMILLA on luku - tama pinnaa sen sopimuksen."""
    import inspect
    src = inspect.getsource(mx.match_xg_rows)
    assert "h not in per_team or a not in per_team" in src, (
        "molempien joukkueiden xG:n vaatimus katosi match_xg_rows:sta")
