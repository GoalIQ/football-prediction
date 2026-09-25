# -*- coding: utf-8 -*-
"""/fpl/differentials on checkoutin puhdas funktio (AUTO-S16, 25.9.2026).

🔴 MITATTU 25.9.2026. fpl-data-refreshin push kaatui rebase-konfliktiin
tiedostossa `fpl/differentials.html` kolmessa ajossa 17.-25.9 (35479829273,
35547995561, 36079421360), ja joka kerta viisi yritysta perakkain, joten koko
ajon rakentama data jai pois mainista. Syy: sivu haki datansa elavasta
`api.goaliq.app/api/fantasy/differentials`-reitista. Sama builderi ajetaan
kolmessa workflow'ssa, ja jokainen sai eri vastauksen (Render palveli
edellista artefaktia, omistus tuli elavasta FPL:sta). accuracy-log kirjoitti
taulukkorivin 00:55 UTC, refresh saman rivin toisin 01:00 UTC.

Korjaus: sivu lasketaan samalla `differential_finder`illa kuin API, mutta
omistus ja saatavuus artefaktin omasta tilannekuvasta. Taman tiedoston portit:

1. builderi ei koske verkkoon lainkaan (mutaatio: palauta live-haku -> punainen)
2. sivu seuraa CHECKOUTIN artefaktia, ei deployattua
3. tilannekuva antaa saman listan kuin elava polku silloin kun FPL ei ole
   muuttunut projektion jalkeen (vartioi yksikot: hinta kymmenyksina,
   omistus merkkijonona kuten FPL:ssa)
"""
from __future__ import annotations

import copy
import json
import re
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import build_fpl_longtail as lt  # noqa: E402
from src.models import fpl_rate_team as rt  # noqa: E402
from src.models.fpl_xp import load_xp  # noqa: E402

ARTEFAKTI = ROOT / "data" / "fpl_xp_projections.json"


def _estetty(*_a, **_k):
    raise AssertionError("verkkoyhteys staattisen sivun rakennuksessa")


@pytest.fixture
def ei_verkkoa(monkeypatch):
    import requests
    monkeypatch.setattr(urllib.request, "urlopen", _estetty)
    monkeypatch.setattr(requests, "get", _estetty)
    monkeypatch.setattr(requests.Session, "request", _estetty)
    monkeypatch.setattr(rt, "get_bootstrap", _estetty)


def _artefakti_kaytettavissa() -> bool:
    try:
        d = json.loads(ARTEFAKTI.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool((d.get("meta") or {}).get("available") and d.get("players"))


pytestmark = pytest.mark.skipif(not _artefakti_kaytettavissa(),
                                reason="xP-artefakti puuttuu tai ei available")


def _sivu() -> str:
    doc = lt._differentials_doc()
    assert doc and doc.get("players"), "differentials ei rakentunut"
    return lt.render_differentials(doc, lt._data_now(load_xp()))


def _taulukko(html: str) -> list[tuple[str, ...]]:
    return re.findall(
        r'<tr><td class="n">\d+</td><td>([^<]*)</td><td>([^<]*)</td>'
        r'<td class="m-hide">[^<]*</td><td class="n">([^<]*)</td>'
        r'<td class="n">([^<]*)%</td>', html)


# ---------------------------------------------------------------------------

def test_sivu_rakentuu_ilman_verkkoa(ei_verkkoa):
    """MUTAATIO: `_differentials_doc` palautettuna elavaan API-hakuun
    (tai `as_of_projection` pois) -> esto laukeaa ja testi punastuu."""
    html = _sivu()
    assert len(_taulukko(html)) >= 1, html[:400]


def test_sama_checkout_samat_tavut(ei_verkkoa):
    """Kaksi ajoa samasta artefaktista = sama sivu. Tama on se ehto joka
    tekee toisen kirjoittajan konfliktista mahdottoman."""
    assert _sivu() == _sivu()


def test_builderissa_ei_ole_verkkokutsua():
    """Rakenteellinen: longtail-builderi ajetaan myos accuracy-logissa ja
    fpl-page-refreshissa. Jos se hakee dataa verkosta, sama sivu saa eri
    sisallon eri workflow'ssa ja pushit konfliktoivat. Luetaan AST:sta,
    jotta docstring joka kertoo historian ei laukaise porttia."""
    import ast
    puu = ast.parse((ROOT / "scripts" / "build_fpl_longtail.py")
                    .read_text(encoding="utf-8"))
    kielletyt = {"urllib.request", "requests", "http.client", "httpx",
                 "aiohttp"}
    osumat = []
    for n in ast.walk(puu):
        if isinstance(n, ast.Import):
            osumat += [a.name for a in n.names if a.name in kielletyt]
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "") in kielletyt or any(
                    f"{n.module}.{a.name}" in kielletyt for a in n.names):
                osumat.append(n.module)
        elif isinstance(n, ast.Attribute) and n.attr == "urlopen":
            osumat.append("urlopen")
    assert not osumat, osumat


def test_sivu_seuraa_checkoutin_artefaktia(monkeypatch, ei_verkkoa):
    """Refresh rakentaa sivun ENNEN omaa pushiaan. Kun lahde oli deployattu
    API, sivu naytti edellista artefaktia. Nyt artefaktin muutos nakyy heti."""
    alkup = load_xp()
    perus = _taulukko(_sivu())
    assert perus, "perustaulukko tyhja"
    karki = perus[0][0]

    muutettu = copy.deepcopy(alkup)
    for p in muutettu["players"]:
        if p.get("web_name") == karki:
            p["owned_pct"] = 55.0          # ei enaa differentiaali
    monkeypatch.setattr(rt, "load_xp", lambda: copy.deepcopy(muutettu))
    uusi = _taulukko(_sivu())
    assert karki not in [r[0] for r in uusi], (karki, uusi[:3])


def test_tilannekuva_vastaa_elavaa_kun_fpl_ei_muuttunut(monkeypatch):
    """Vaiheinvariantti yksikoille: rakennetaan FPL:n muotoinen bootstrap
    (now_cost kymmenyksina int, selected_by_percent merkkijono, team-id)
    ARTEFAKTIN arvoista ja verrataan elavaa polkua tilannekuvaan. Jos
    `projection_bootstrap` lukisi hinnan tai omistuksen vaarin, rivit eroavat."""
    from src.models.fpl_planner import differential_finder
    xp = load_xp()
    pos_id = {v: k for k, v in rt.POS_NAME.items()}
    joukkue_id = {}
    elavat = []
    for p in xp["players"]:
        joukkue_id.setdefault(p.get("team_short"), len(joukkue_id) + 1)
        elavat.append({
            "id": p["id"], "element_type": pos_id[p["pos"]],
            "team": joukkue_id[p.get("team_short")],
            "now_cost": int(round(p["price"] * 10)),
            "selected_by_percent": f"{p['owned_pct']:.1f}",
            "status": p.get("status") or "a",
            "chance_of_playing_next_round": p.get("chance_next"),
            "news": p.get("news") or "",
        })
    monkeypatch.setattr(rt, "get_bootstrap", lambda: {"elements": elavat})
    elava = differential_finder(max_ownership=10.0)
    kuva = differential_finder(max_ownership=10.0, as_of_projection=True)
    avain = ("id", "price", "owned_pct", "xp_per_gw", "xp_horizon_total")
    assert ([tuple(r[k] for k in avain) for r in kuva["players"]]
            == [tuple(r[k] for k in avain) for r in elava["players"]])
    assert kuva["meta"]["gw"] == elava["meta"]["gw"]
