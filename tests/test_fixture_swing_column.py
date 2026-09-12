# -*- coding: utf-8 -*-
"""Portti: Fixture swing -listan Swing-sarake nayttaa sen luvun jolla lista on jarjestetty.

MITATTU VIKA (12.9.2026). `FixtureSwing.svelte` rakensi rivit
`swing = hi.xp - lo.xp`, jarjesti ne `b.swing - a.swing` ja jakokortti
nayttaa `r.swing` -- mutta taulukon Swing-sarake renderoi `r.ratio`
(`1.8x`, abbr "High xP divided by low xP"). Lista oli siis jarjestetty
yhden luvun mukaan ja sarake nayttaa toista: 0.5 -> 1.5 (ero 1.0, "3.0x")
nakyi korkeammalla suhdeluvulla kuin 3.0 -> 5.0 (ero 2.0, "1.7x"), vaikka
jalkimmainen oli listalla ylempana. Lukija ei voi paatella jarjestysta
sarakkeesta.

Suunnittelu (CLAUDE.md 6a): sarake ja kortti lukevat saman kentan saman
funktion lapi (`formatSwing(r.swing)` modulista `$lib/fixtureSwing.ts`),
ja suhdeluku poistettiin kokonaan, joten toista lukua ei ole saatavilla
renderoitavaksi.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FP = Path(__file__).resolve().parents[1]
COMPONENT = FP / "web" / "pro-spa" / "src" / "lib" / "components" / "FixtureSwing.svelte"
MODULE = FP / "web" / "pro-spa" / "src" / "lib" / "fixtureSwing.ts"

SWING_ABBR = "High xP minus low xP"


def _src() -> str:
    return COMPONENT.read_text(encoding="utf-8")


def _markup(src: str) -> str:
    """Komponentin markup ilman <script>- ja <style>-lohkoja."""
    src = re.sub(r"<script\b.*?</script>", "", src, flags=re.S)
    return re.sub(r"<style\b.*?</style>", "", src, flags=re.S)


def _headers(markup: str) -> list[str]:
    thead = re.search(r"<thead>(.*?)</thead>", markup, re.S)
    assert thead, "FixtureSwing: <thead> puuttuu"
    cells = re.findall(r"<th\b[^>]*>(.*?)</th>", thead.group(1), re.S)
    return [re.sub(r"<[^>]+>", "", c).strip() for c in cells]


def _data_row_cells(markup: str) -> list[str]:
    """Paarivin <td>-solut `{#each rows as r ...}` -lohkosta, ennen laajennusrivia."""
    m = re.search(r"\{#each rows as r\b[^}]*\}(.*?)\{#if expandedId", markup, re.S)
    assert m, "FixtureSwing: rivien {#each rows as r} -lohkoa ei loydy"
    return [c.strip() for c in re.findall(r"<td\b[^>]*>(.*?)</td>", m.group(1), re.S)]


def test_list_is_sorted_by_swing_difference() -> None:
    src = _src()
    assert re.search(r"swing:\s*hi\.xp\s*-\s*lo\.xp", src), (
        "swing-kentan pitaa olla high xP miinus low xP"
    )
    assert re.search(r"\.sort\(\(a,\s*b\)\s*=>\s*b\.swing\s*-\s*a\.swing\)", src), (
        "lista pitaa jarjestaa swing-kentan mukaan laskevasti"
    )


def test_swing_column_renders_the_sort_key() -> None:
    markup = _markup(_src())
    headers = _headers(markup)
    assert "Swing" in headers, f"Swing-sarake puuttuu otsikoista: {headers}"
    idx = headers.index("Swing")
    cells = _data_row_cells(markup)
    assert len(cells) == len(headers), (
        f"otsikoita {len(headers)}, paarivin soluja {len(cells)}: {cells}"
    )
    rendered = re.sub(r"\s+", "", cells[idx])
    assert rendered == "{formatSwing(r.swing)}", (
        "Swing-sarakkeen pitaa renderoida sama luku jolla lista on jarjestetty "
        f"(formatSwing(r.swing)), nyt se renderoi: {cells[idx]!r}"
    )


def test_share_card_uses_the_same_formatter() -> None:
    src = _src()
    assert re.search(r"value:\s*formatSwing\(r\.swing\)", src), (
        "jakokortin arvon pitaa kulkea saman formatSwing(r.swing) -polun kautta "
        "kuin sarakkeen, muuten kortti ja sivu voivat nayttaa eri luvun"
    )


def test_no_ratio_left_to_render() -> None:
    src = _src()
    assert not re.search(r"\bratio\b", src), (
        "suhdeluku (ratio) on poistettava: kun sita ei ole, sita ei voi "
        "vahingossa renderoida Swing-sarakkeeseen"
    )


def test_swing_abbr_describes_a_difference() -> None:
    markup = _markup(_src())
    m = re.search(r'<abbr\s+title="([^"]*)"\s*>\s*Swing\s*</abbr>', markup)
    assert m, "Swing-otsikon <abbr> puuttuu"
    assert m.group(1) == SWING_ABBR, (
        f"Swing-otsikon selitteen pitaa olla {SWING_ABBR!r}, nyt {m.group(1)!r}"
    )


def _node_supports_strip_types() -> bool:
    node = shutil.which("node")
    if node is None:
        return False
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    m = re.match(r"v(\d+)\.(\d+)", out.strip())
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


@pytest.mark.skipif(not _node_supports_strip_types(),
                    reason="node >= 22.6 (type stripping) puuttuu tasta ymparistosta")
def test_format_swing_behaviour() -> None:
    assert MODULE.exists(), f"{MODULE} puuttuu"
    inputs = [2.04, 1.0, 0.0, 0.049, 12.34]
    script = (
        f"import({json.dumps(MODULE.as_uri())})"
        f".then(m => console.log(JSON.stringify({json.dumps(inputs)}.map(m.formatSwing))))"
    )
    r = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", "-e", script],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0, f"formatSwing-ajo kaatui:\n{r.stderr}"
    got = json.loads(r.stdout)
    # Yksi desimaali ja etumerkki: ero on aina >= 0, joten positiivinen saa '+'.
    # 0.049 pyoristyy nollaan, eika nollalle anneta etumerkkia.
    assert got == ["+2.0", "+1.0", "0.0", "0.0", "+12.3"], got
