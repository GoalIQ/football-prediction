"""Portti etusivun "Next matches, already logged" -lohkolle (19.8.2026).

MIKSI NAMA. Lohko lupaa kaksi asiaa: ennuste on kirjattu ENNEN ottelua, ja
lukija paasee sen sivulle tarkistamaan. Molemmat ovat rikottavissa hiljaa:

  1. Ratkennut tai mennyt ottelu lohkossa tekisi "logged before kick-off"
     -lupauksesta jalkiviisautta.
  2. Linkin slug rakennetaan NAYTTONIMESTA, koska build_prediction_pages
     vaihtaa nimet ennen renderointia. Raa'alla feedinimella tehty slug osuu
     olemattomaan tiedostoon neljassa liigassa (PD/SA/BL1/FL1) — ja koska
     /predictions/... palauttaa 200 + hubisivun eika 404:aa, rikkinainen
     linkki NAYTTAA toimivalta. Ensimmainen toteutus teki tasan taman:
     kuudesta rivista kaksi linkittyi.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_fpl_page import (  # noqa: E402
    NEXT_MATCHES_PATH, next_matches_block, next_matches_rows)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _log() -> dict:
    return json.loads(NEXT_MATCHES_PATH.read_text(encoding="utf-8"))


def _entry(**kw) -> dict:
    base = {
        "competition": "PL", "kickoff": "2026-12-01T15:00:00Z",
        "home_team": "Arsenal", "away_team": "Chelsea",
        "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2,
        "most_likely_score": "2-1", "logged_at": "2026-08-01T00:00:00+00:00",
        "result": None,
    }
    base.update(kw)
    return base


def test_ratkennut_ottelu_ei_paady_lohkoon():
    """Lohko lupaa ennusteen ENNEN ottelua."""
    rows = next_matches_rows({"predictions": [_entry(result={"score": "1-0"})]}, NOW)
    assert rows == []


def test_mennyt_potkaisu_ei_paady_lohkoon():
    past = (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert next_matches_rows({"predictions": [_entry(kickoff=past)]}, NOW) == []


def test_tuntematon_kilpailu_jaa_pois():
    """Ilman ottelusivua rivi olisi linkki tyhjaan."""
    assert next_matches_rows({"predictions": [_entry(competition="XXX")]}, NOW) == []


def test_jarjestys_on_potkaisujarjestys():
    a = _entry(kickoff="2026-12-02T15:00:00Z", home_team="Everton")
    b = _entry(kickoff="2026-12-01T15:00:00Z", home_team="Fulham")
    rows = next_matches_rows({"predictions": [a, b]}, NOW)
    assert [r["home"] for r in rows] == ["Fulham", "Everton"]


def test_jokainen_linkki_osoittaa_olemassa_olevaan_sivuun():
    """SLUG-ANSA. Tuotantolokilla ajettuna jokaisen linkin takana on tiedosto."""
    rows = next_matches_rows(_log(), datetime.now(timezone.utc))
    linked = [r for r in rows if r["url"]]
    assert linked, "yksikaan rivi ei linkittanyt - slug-kartta on rikki"
    for r in linked:
        polku = ROOT / (r["url"].lstrip("/") + ".html")
        assert polku.exists(), f"{r['url']} ei vastaa tiedostoa {polku}"


def test_nayttonimi_on_lyhennetty_muoto():
    """La Ligan feedinimi ei saa vuotaa etusivulle."""
    rows = next_matches_rows(
        {"predictions": [_entry(competition="PD",
                                home_team="Club Atlético de Madrid",
                                away_team="Real Betis Balompié")]}, NOW)
    assert rows[0]["home"] == "Atletico Madrid"
    assert rows[0]["away"] == "Real Betis"


def test_tyhja_loki_ei_tuota_lohkoa():
    """Tyhja merkkijono jattaa markkerin ennalleen -> sivu ei tyhjene."""
    assert next_matches_block({"predictions": []}, NOW) == ""
    assert next_matches_block(None, NOW) == ""


def test_paasivulla_on_markerit_tasan_kerran():
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    assert idx.count("<!-- GEN:NEXT-MATCHES-START -->") == 1
    assert idx.count("<!-- GEN:NEXT-MATCHES-END -->") == 1


def test_lohko_on_ENNEN_team_news_osiota() -> None:
    """Villen pyynto oli tuoda ottelumalli ESILLE, ei sivun pohjalle."""
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    assert idx.index('id="next-matches"') < idx.index('<section id="team-news">')
