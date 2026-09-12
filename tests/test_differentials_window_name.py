# -*- coding: utf-8 -*-
"""Differentials-sivu nimeaa IKKUNAN jota se nayttaa.

🔴 MITATTU 12.9.2026. Sivun taulukko on KUUDEN kierroksen projektio
(sarake "xP, 6 GWs", note: "xP/GW is the 6-gameweek projection divided by 6"),
mutta H1, title-tagi ja meta-description sanoivat **"this gameweek"**. Sanoja
"six" tai "next 6" ei esiintynyt sivulla kertaakaan.

Syy oli mekaaninen eika sanavalinta: `differential_finder`in palauttamasta
metasta puuttui `gw`, joten `render_differentials` fallbackasi AINA
merkkijonoon "this gameweek". Interpolointi oli kirjoitettu valmiiksi, se ei
vain koskaan lauennut.

Miksi talla on valia: postaus joka sanoo "over the next six gameweeks"
lahettaa lukijan sivulle joka ei sano sita. Sama vikaluokka kuin
`FPL-SIVU-OTTELUIDEN-XG` (kortti vaittaa, sivu ei nayta) - ja se on juuri se
ehto jonka julkaisutarkistaja mittaa.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_fpl_longtail import render_differentials  # noqa: E402

NYT = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)


def _diff(meta_extra: dict | None = None, n: int = 3) -> dict:
    players = [{"web_name": f"P{i}", "team_short": "ARS", "pos": "DEF",
                "price": 5.5, "owned_pct": 7.6 - i, "xp_per_gw": 4.6 - i * 0.1,
                "xp_horizon_total": 28.0 - i} for i in range(n)]
    meta = {"max_ownership": 10.0, "pos": None,
            "generated_at": "2026-09-12T06:30:13+00:00", "horizon_gw": 6}
    meta.update(meta_extra or {})
    return {"players": players, "meta": meta,
            "model_vs_crowd": [], "template_missing": []}


def _teksti(html: str) -> str:
    ilman = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    ilman = re.sub(r"<style.*?</style>", " ", ilman, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ilman))


# ---------------------------------------------------------------------------

def test_ikkuna_nimetaan_gw_ja_horisontin_perusteella():
    html = render_differentials(_diff({"gw": 4}), NYT)
    assert "GW4-GW9" in html, _teksti(html)[:300]


@pytest.mark.parametrize("gw,horizon,odotus", [
    (4, 6, "GW4-GW9"),
    (1, 6, "GW1-GW6"),
    (33, 6, "GW33-GW38"),
    (38, 1, "GW38"),      # kauden viimeinen: ikkuna on yksi kierros
])
def test_ikkunan_muoto_kauden_eri_vaiheissa(gw, horizon, odotus):
    """Vaiheinvariantti: ehto mitataan synteettisilla kausivaiheilla, ei
    silla mika kierros sattuu olemaan tanaan (CLAUDE.md 6a mek. 3)."""
    html = render_differentials(_diff({"gw": gw, "horizon_gw": horizon}), NYT)
    assert odotus in html
    if horizon > 1:
        assert f"GW{gw}:" not in html, "yksittainen kierros ei saa jaada"


def test_vanha_sanamuoto_ei_saa_palata():
    """MUTAATIO: 'this gameweek' on kuuden kierroksen taulukossa epatosi."""
    for meta in ({"gw": 4}, {"gw": None}, {}):
        html = render_differentials(_diff(meta), NYT)
        assert "this gameweek" not in html, meta


def test_fallback_on_tosi_myos_ilman_gw_ta():
    """Ilman `gw`:ta sivu ei saa vaittaa yhta kierrosta eika keksia numeroa."""
    html = render_differentials(_diff({"gw": None}), NYT)
    assert "the coming gameweeks" in html
    assert not re.search(r"GW\d", _teksti(html))


def test_ikkuna_nakyy_otsikossa_kuvauksessa_ja_h1ssa():
    """Yksi paikka ei riita: lukija tulee hakutuloksesta (title + description)
    tai linkista (H1)."""
    html = render_differentials(_diff({"gw": 4}), NYT)
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
    h1 = re.search(r"<h1>(.*?)</h1>", html, re.S)
    assert title and "GW4-GW9" in title.group(1)
    assert desc and "GW4-GW9" in desc.group(1)
    assert h1 and "GW4-GW9" in h1.group(1)


def test_payload_kantaa_gw_n():
    """KONTROLLI: ilman tata sivukorjaus olisi vihrea vaikka datalahde ei
    koskaan anna `gw`:ta - eli tuotannossa fallback olisi yha paalla."""
    from src.models.fpl_planner import differential_finder
    meta = differential_finder(max_ownership=10.0)["meta"]
    assert isinstance(meta.get("gw"), int), meta
    assert isinstance(meta.get("horizon_gw"), int), meta
