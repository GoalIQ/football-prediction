# -*- coding: utf-8 -*-
"""Points-sivun jaadytetty xP vs gameweek calls -loki (25.9.2026).

/fpl/points/gw{n} lupaa "the projection this model published before the
deadline". GW2:lla kutsut (data/gw_calls.json) oli laskettu 28.8 korjatusta
projektiosta ja sivun xP 27.8 jaadytyksesta: Bruno 5.74 kutsussa, 3.96
sivulla, eika sivu kertonut miksi. GW3-5 kutsujen luvut ovat jaadytyksen
lukuja (ero enintaan 0.08).

CLAUDE.md 6a(2): selite on poikkeuslista. Jos uusi kierros eroaa yli
kynnyksen, tama kaatuu ja kirjoittajan on lisattava selite
`FROZEN_VS_CALLS_NOTE`:en (tai korjattava loki). Ajetaan jokaiselle
kierrokselle jolla on seka kutsut etta jaadytys, ei vain nykyiselle.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import build_fpl_longtail as lt

ROOT = Path(__file__).resolve().parents[1]
KYNNYS = 0.5


def _kierrokset() -> list[tuple[int, dict, dict]]:
    calls_path = ROOT / "data" / "gw_calls.json"
    if not calls_path.exists():
        pytest.skip("gw_calls.json puuttuu")
    doc = json.loads(calls_path.read_text(encoding="utf-8"))
    out = []
    for row in doc.get("gameweeks") or []:
        fr = lt._latest_frozen_gw(int(row["gw"]))
        if fr:
            out.append((int(row["gw"]), row, fr))
    if not out:
        pytest.skip("ei kierroksia joilla seka kutsut etta jaadytys")
    return out


def _max_ero(row: dict, fr: dict) -> float:
    fx = {int(r["id"]): float(r.get("xp") or 0.0)
          for r in fr.get("players") or [] if r.get("id")}
    erot = []
    for c in row.get("calls") or []:
        pid = c.get("player_id")
        gx = c.get("gw_xp")
        if gx is None and c.get("metric") == "gw_xp":
            gx = c.get("value")
        if pid in fx and gx is not None:
            erot.append(abs(float(gx) - fx[pid]))
    return max(erot, default=0.0)


def test_poikkeava_kierros_on_selitetty():
    selittamatta = [(gw, round(_max_ero(row, fr), 2))
                    for gw, row, fr in _kierrokset()
                    if _max_ero(row, fr) > KYNNYS
                    and gw not in lt.FROZEN_VS_CALLS_NOTE]
    assert not selittamatta, selittamatta


def test_selite_vain_poikkeavalle_kierrokselle():
    """Selite joka ei enaa vastaa dataa on itse vaite: jos GW:n kutsut
    korjataan jaadytyksen luvuiksi, selite pitaa poistaa."""
    erot = {gw: _max_ero(row, fr) for gw, row, fr in _kierrokset()}
    for gw in lt.FROZEN_VS_CALLS_NOTE:
        assert erot.get(gw, 0.0) > KYNNYS, gw


def _pvm(iso: str) -> str:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return f"{d.day} {d:%B}"


def test_selitteen_paivat_tulevat_datasta():
    """'frozen on 27 August' = jaadytyksen projektioajo, 'fixed on 28
    August' = kutsujen projektioajo. Kovakoodattu paiva ei saa erota."""
    rivit = {gw: (row, fr) for gw, row, fr in _kierrokset()}
    for gw, teksti in lt.FROZEN_VS_CALLS_NOTE.items():
        row, fr = rivit[gw]
        jaadytys = _pvm(fr["meta"]["projection_generated_at"])
        kutsut = _pvm(row["source"]["projection_generated_at"])
        assert f"frozen on {jaadytys}" in teksti
        assert f"fixed on {kutsut}" in teksti
        assert f"from the {jaadytys} freeze" in teksti


def test_gw2_sivu_nayttaa_selitteen():
    """MUTAATIO: poista selite render_pointsista -> punainen."""
    pg = lt._load(lt.PLAYER_GW_PATH) if hasattr(lt, "PLAYER_GW_PATH") else None
    if not pg:
        pytest.skip("player-gw puuttuu")
    html = lt.render_points(pg, datetime.now(timezone.utc), gw=2, archive=True)
    if html is None:
        pytest.skip("GW2-sivu ei renderoidy tassa ymparistossa")
    assert html.count("For GW2 this is the projection frozen on 27 August") == 1
    html3 = lt.render_points(pg, datetime.now(timezone.utc), gw=3, archive=True)
    if html3 is not None:
        assert html3.count("projection frozen on") == 0
