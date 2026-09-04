"""Portti: team news ei laske liigasta lahteneita, ja projektio-otsikko
seuraa dataa.

🔴 KAKSI MITATTUA VIKAA (4.9.2026, Villen havainnot samassa istunnossa).

**1. "146 players are ruled out."** Etusivu ja `/fpl/team-news` laskivat
poissaoleviksi jokaisen jolla oli `news` ja `chance_next == 0`. Mitattu
artefaktista `data/fpl_xp_projections.json`: 146 rivista **89 oli liigasta
lahteneita** (status `u`, esim. Watkins "Has joined Al Hilal permanently").
Oikea luku oli 57 (56 loukkaantunutta + 1 pelikielto). Sivu myos NIMESI
eniten omistetuksi poissaolijaksi Watkinsin, joka ei ollut enaa pelattavissa.

Sama vikaluokka loytyi 3.9 leaders- ja DefCon-pinnoilta. Kolmas kerta =
suodatus ei voi jaada kirjoittajan muistin varaan, joten lukija on nyt yksi
(`src/models/fpl_status.left_league`) ja tama portti vahtii sita.

**2. "Live model projections · GW1-6."** Taulukon RIVIT generoitiin
artefaktista, mutta OTSIKKO oli kovakoodattu GEN-markerien ulkopuolelle. Data
oli GW3-8, otsikko lupasi GW1-6 — teksti vanheni koska mikaan ei paivittanyt
sita (muisti: ehto-ei-vanhene-teksti-vanhenee).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
XP_PATH = ROOT / "data" / "fpl_xp_projections.json"
INDEX = ROOT / "index.html"


def _xp() -> dict:
    if not XP_PATH.exists():  # pragma: no cover
        pytest.skip("xP-artefaktia ei ole")
    return json.loads(XP_PATH.read_text(encoding="utf-8"))


def _synthetic() -> dict:
    """Pooli jossa on tasan yksi lahtenyt ja se on ENITEN omistettu.

    Nain testi kaataa seka laskennan etta nimilistan, jos suodatus katoaa.
    """
    return {
        "meta": {"available": True, "season": "2026/27", "horizon_gw": 6},
        "players": [
            {
                "web_name": "Departed",
                "team_short": "AVL",
                "status": "u",
                "news": "Has joined Al Hilal permanently",
                "chance_next": 0,
                "owned_pct": 55.0,
                "gameweeks": [{"gw": 3}],
            },
            {
                "web_name": "Injured",
                "team_short": "CRY",
                "status": "i",
                "news": "Hamstring injury",
                "chance_next": 0,
                "owned_pct": 3.0,
                "gameweeks": [{"gw": 3}],
            },
            {
                "web_name": "Doubtful",
                "team_short": "NEW",
                "status": "d",
                "news": "Knock",
                "chance_next": 50,
                "owned_pct": 2.0,
                "gameweeks": [{"gw": 3}],
            },
        ],
        "excluded": [],
    }


# --------------------------------------------------------------------------
# 1. Team news
# --------------------------------------------------------------------------


def test_lahtenytta_ei_lasketa_eika_nimeta() -> None:
    from scripts.build_fpl_page import team_news_block

    html = team_news_block(_synthetic())
    assert "Departed" not in html, "lahtenyt pelaaja nimettiin team newsissa"
    assert "<strong>1 players are ruled out and 1 are doubtful</strong>" in html, html


def test_loukkaantunut_ja_epavarma_sailyvat() -> None:
    """Negatiivinen kontrolli suodatukselle: se ei saa pudottaa liikaa."""
    from scripts.build_fpl_page import team_news_block

    html = team_news_block(_synthetic())
    assert "Injured" in html
    assert "1 are doubtful" in html


def test_oikealla_artefaktilla_ei_yhtaan_lahteneen_nimea() -> None:
    from scripts.build_fpl_page import team_news_block

    xp = _xp()
    html = team_news_block(xp)
    if not html:
        pytest.skip("artefaktissa ei ole team newsia")
    left = {
        str(r.get("web_name"))
        for r in list(xp.get("players") or []) + list(xp.get("excluded") or [])
        if (r.get("status") or "a") == "u"
    }
    named = re.findall(r"Most owned among them: ([^<]+)\.", html)
    assert named, html
    for name in left:
        assert f"{name} (" not in named[0], (
            f"liigasta lahtenyt {name} nimettiin etusivun team newsissa"
        )


def test_ruled_out_luku_vastaa_suodatettua_poolia() -> None:
    from scripts.build_fpl_page import team_news_block

    xp = _xp()
    html = team_news_block(xp)
    if not html:
        pytest.skip("artefaktissa ei ole team newsia")
    rows = [
        r
        for r in list(xp.get("players") or []) + list(xp.get("excluded") or [])
        if (r.get("status") or "a") != "u"
        and (r.get("news") or "").strip()
        and r.get("chance_next") is not None
    ]
    odotettu = sum(1 for r in rows if r.get("chance_next") == 0)
    m = re.search(r"<strong>(\d+) players are ruled out", html)
    assert m and int(m.group(1)) == odotettu, (m.group(0) if m else html[:200])


# --------------------------------------------------------------------------
# 2. Projektio-otsikon ikkuna
# --------------------------------------------------------------------------


def test_otsikon_ikkuna_on_generoitu_markerien_sisalla() -> None:
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(
        r"<!-- GEN:XP-WINDOW-START -->(.*?)<!-- GEN:XP-WINDOW-END -->", html, re.S
    )
    assert m, "GEN:XP-WINDOW-markerit puuttuvat index.html:sta"
    assert "Live model projections" in m.group(1)


def test_otsikon_ikkuna_vastaa_dataa() -> None:
    from src.models.fpl_gameweek import window_label

    xp = _xp()
    meta = xp.get("meta") or {}
    gws = ((xp.get("players") or [{}])[0] or {}).get("gameweeks") or []
    odotettu = window_label(meta, gws, meta.get("horizon_gw") or 6)
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(
        r"<!-- GEN:XP-WINDOW-START -->(.*?)<!-- GEN:XP-WINDOW-END -->", html, re.S
    )
    assert m and odotettu in m.group(1), (
        f"etusivun otsikko lupaa {m.group(1) if m else '?'} kun data on {odotettu}. "
        "Aja `python scripts/build_fpl_page.py` (update_index)."
    )


def test_negatiivinen_kontrolli_kovakoodattu_ikkuna_jaa_kiinni() -> None:
    """Jos ikkuna kirjoitetaan markerien ULKOPUOLELLE, tarkistin ei loyda
    sita — ja juuri se oli vika. Kontrolli varmistaa etta vertailu on
    merkityksellinen eika mene lapi tyhjana."""
    rikottu = "<div>Live model projections · GW1-6 · 2026/27</div>"
    assert not re.search(
        r"<!-- GEN:XP-WINDOW-START -->(.*?)<!-- GEN:XP-WINDOW-END -->", rikottu, re.S
    )
