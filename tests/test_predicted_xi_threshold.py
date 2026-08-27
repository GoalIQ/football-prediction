# -*- coding: utf-8 -*-
"""PREDICTED-XI-KYNNYS (27.8): "Model Predicted XI" nimeaa pelaajan vain kun
malli pitaa avausta todennakoisempana kuin penkkia.

Mitattu 27.8: slotit taytettiin jarjestyksessa, joten Cherki (17 %) ja
Marmoush (38 %) olivat Man Cityn XI:ssa ja sivun otsikko lupasi enemman kuin
luvut kestavat. Portti lukee renderoidun sivun: nimetty rivi >= kynnys,
"No clear starter" -rivi < kynnys, ja kynnys tulee vakiosta eika luvusta.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _rivit(rel: str):
    p = ROOT / "fpl" / rel
    if not p.exists():
        pytest.skip(f"{rel} ei ole rakennettu")
    h = p.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r'<tr( class="noclear")?>(.*?)</tr>', h, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", m.group(2), re.S)
        if len(tds) != 4:
            continue
        pm = re.fullmatch(r"(\d+)%", html.unescape(re.sub(r"<[^>]+>", "", tds[-1])).strip())
        if not pm:
            continue
        nimi = html.unescape(re.sub(r"<[^>]+>", "", tds[0])).strip()
        out.append((bool(m.group(1)), nimi, int(pm.group(1))))
    assert out, f"{rel}: ei XI-riveja"
    return out


@pytest.mark.parametrize("rel", ["predicted-lineups.html", "club/manchester-city.html"])
def test_named_rows_are_at_or_above_floor_and_noclear_below(rel):
    from scripts.build_fpl_longtail import XI_STARTER_FLOOR
    floor = round(XI_STARTER_FLOOR * 100)
    rivit = _rivit(rel)
    nimetyt = [(n, v) for nc, n, v in rivit if not nc]
    noclear = [(n, v) for nc, n, v in rivit if nc]
    assert nimetyt, "yhtaan nimettya rivia ei ole"
    alle = [(n, v) for n, v in nimetyt if v < floor]
    assert not alle, f"nimetty rivi kynnyksen alla: {alle[:5]}"
    yli = [(n, v) for n, v in noclear if v >= floor]
    assert not yli, f"'No clear starter' vaikka luku >= {floor}: {yli[:5]}"
    for n, _ in noclear:
        assert n.startswith("No clear starter"), n
        assert "best option" in n, n


def test_floor_is_a_majority():
    from scripts.build_fpl_longtail import XI_STARTER_FLOOR
    assert XI_STARTER_FLOOR == 0.5
