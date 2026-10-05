"""xGI/90-todiste kauden jokaisessa vaiheessa (5.10.2026, Villen havainto).

GW5:n jalkeen pelaajakortin "Attacking output" sanoi Haalandille
"0.86 xGI/90 last season", vaikka samalla kortilla oli jo GW1-5 luvut.
Kolme pintaa lukee nyt yhden lukijan (`fpl_xp.xgi_per90`):
kortin ajuririvi (`driver_facts`), /fpl-listan ja jakokortin todiste
(`fact_text_ctx`) ja why-lause (`build_fpl_why`).

Saanto 6a(3): invariantti mitataan joka vaiheessa, ei vain tanaan.
Sama pelaaja ajetaan synteettisilla vaiheilla: esikausi (bootstrap on
viime kauden), ohut otos (alle minuuttirajan), kesken kauden.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import build_fpl_why as why
from scripts.build_fpl_xp import _this_season_block
from src.models.fpl_why_drivers import fact_context, fact_text, fact_text_ctx
from src.models.fpl_leaders import MIN_CURRENT_GAMES
from src.models.fpl_xp import XGI_SEASON_MIN_MINUTES, driver_facts, xgi_per90

ROOT = Path(__file__).resolve().parent.parent
CTX = {"team_cs": {}, "season": "2026/27", "prev_season": "2025/26"}
LAST = {"season": "2025/26", "minutes": 2953, "per90": {"xgi": 0.86}}


def _bootstrap(minutes: int, xgi: float) -> dict:
    return {"minutes": minutes, "expected_goal_involvements": f"{xgi:.2f}",
            "expected_goal_involvements_per_90": round(xgi / minutes * 90, 2) if minutes else 0}


def _row(phase: str, last: dict | None = LAST, pos: str = "FWD") -> dict:
    """Builderin rivi vaiheessa `phase`, samalla funktiolla kuin tuotanto."""
    e, pre = {
        # Esikaudella bootstrap kantaa VIIME kauden lukuja: jos builder
        # kirjoittaisi ne this_season-nimella, kortti vaittaisi viime kautta
        # kuluvaksi.
        "preseason": (_bootstrap(2953, 28.17), True),
        "thin": (_bootstrap(180, 2.0), False),
        "mid": (_bootstrap(450, 4.95), False),
    }[phase]
    return {"id": 1, "web_name": "H", "pos": pos, "xmins": 90,
            "last_season": last, "this_season": _this_season_block(e, pre)}


def test_raja_on_sama_kuin_leaders_sivulla():
    """Kortti ja Leaders vaihtavat kuluvaan kauteen samassa kohdassa."""
    assert XGI_SEASON_MIN_MINUTES == MIN_CURRENT_GAMES * 90


def test_esikausi_ei_kirjoita_kuluvaa_kautta():
    assert _this_season_block(_bootstrap(2953, 28.17), True) is None
    r = _row("preseason")
    assert xgi_per90(r) == {"this": None, "last": 0.86}
    assert driver_facts(r)["attacking_output"] == "0.86 xGI/90 last season"
    assert fact_text_ctx(r, CTX) == "0.86 xGI/90 in 2025/26"


def test_ohut_otos_pysyy_viime_kaudessa():
    r = _row("thin")
    assert r["this_season"]["minutes"] < XGI_SEASON_MIN_MINUTES
    assert xgi_per90(r)["this"] is None
    assert driver_facts(r)["attacking_output"] == "0.86 xGI/90 last season"
    assert fact_text_ctx(r, CTX) == "0.86 xGI/90 in 2025/26"
    facts = why.player_facts(r, gw=6, horizon=3)
    assert "this_season" not in facts
    assert "per 90 last season" in why.template_sentence(facts)


def test_kesken_kauden_kuluva_kausi_kaikilla_pinnoilla():
    r = _row("mid")
    assert xgi_per90(r) == {"this": 0.99, "last": 0.86}
    # Ajuririvi: molemmat, koska malli painottaa viela viime kautta.
    assert driver_facts(r)["attacking_output"] == "0.99 xGI/90 this season, 0.86 last season"
    assert fact_text_ctx(r, CTX) == "0.99 xGI/90 in 2026/27"
    facts = why.player_facts(r, gw=6, horizon=3)
    s = why.template_sentence(facts)
    assert "0.99 expected goal involvements per 90 this season" in s
    assert "last season" not in s
    assert "attacking_output" in why.template_drivers(facts)
    # Lauseen luku on faktalohkossa (lukuprovenienssiportti).
    assert why.ungrounded_numbers(s, facts) == []
    for lang, word in (("es", "esta temporada"), ("pt", "nesta temporada")):
        assert word in why.template_sentence(facts, lang)


def test_kuluva_pieni_luku_ei_pudota_viime_kauteen():
    """Kuluvalla kaudella pelaaja ei tuota: vanha 0.86 vaittaisi muuta."""
    r = _row("mid", pos="MID")
    r["this_season"]["per90"]["xgi"] = 0.05
    assert fact_text_ctx(r, CTX) == ""
    facts = why.player_facts(r, gw=6, horizon=3)
    assert "expected goal involvements" not in why.template_sentence(facts)
    assert "attacking_output" not in why.template_drivers(facts)
    assert driver_facts(r)["attacking_output"].startswith("0.05 xGI/90 this season")


def test_nousija_ilman_viime_kautta_saa_kuluvan():
    r = _row("mid", last=None)
    assert driver_facts(r)["attacking_output"] == "0.99 xGI/90 this season"
    assert fact_text_ctx(r, CTX) == "0.99 xGI/90 in 2026/27"


def test_kausi_puuttuu_tyhja_eika_viime_kausi():
    r = _row("mid")
    assert fact_text(r, {}, "2025/26", None) == ""


def test_fact_context_kantaa_kauden(monkeypatch):
    ctx = fact_context({"meta": {"season": "2026/27"}})
    assert ctx["season"] == "2026/27" and ctx["prev_season"] == "2025/26"
    assert fact_context({"meta": {"season": "syksy"}})["season"] is None


@pytest.mark.parametrize("path", ["scripts", "api", "src"])
def test_kutsupaikat_lukevat_kontekstista(path):
    """Saanto 6a(2): sivu ja jakokortti kutsuvat `fact_text_ctx`ia. Suora
    `fact_text(` kutsupaikalla unohti kauden ja tyhjensi todisteen hiljaa."""
    bad = []
    for f in (ROOT / path).rglob("*.py"):
        if f.name == "fpl_why_drivers.py":
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"(?<![\w.])fact_text\(", line):
                bad.append(f"{f.relative_to(ROOT)}:{i}")
    assert not bad, f"kayta fact_text_ctx(player, ctx): {bad}"
