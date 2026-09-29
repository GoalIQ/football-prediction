# -*- coding: utf-8 -*-
"""Portti: SPA:n ennustepinnat lukevat xP-rivit `actionableRows`in kautta (29.9.2026).

XP-HORISONTIN-ALKU: `gameweeks[]` alkaa kesken olevasta kierroksesta. Kesken
GW6:n PlayerCard naytti "GW6 · ARS (H)" seuraavana otteluna ja XpTable
GW6-sarakkeen + lajittelun lukitulle kierrokselle. Korjaus on yksi lukija
`$lib/gameweek.actionableRows`. SPA:n vitest-portit ajetaan vain
deploy-workflow'ssa, joten tama Python-portti vartioi pushilla (kuten
test_horizon_window_label_discipline.py).

Mekanismi (saanto 6a kohta 2): raakarivikuvio SPA:ssa kaataa testin, ellei
tiedosto ole POIKKEUKSET-listalla perustelun kanssa. Tyhja perustelu ei
vapauta.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "pro-spa" / "src"

RAAKA = re.compile(
    r"gameweeks\?\.\[0\]"                       # p.gameweeks?.[0]
    r"|gameweeks \?\? \[\]\)\[0\]"              # (p.gameweeks ?? [])[0]
    r"|\.gameweeks\?\.map\("                    # p.gameweeks?.map(
    r"|#each [\w.]+\.gameweeks "                # {#each player.gameweeks as g}
    r"|\.gameweeks \?\? \[\]\)\.(map|filter|forEach)"
    r"|of [\w.]+\.gameweeks( \?\? \[\])?\)")    # for (const g of p.gameweeks ?? [])

POIKKEUKSET: dict[str, str] = {
    "lib/api.ts": "windowXp(p, from, to) summaa eksplisiittisen ikkunan; kutsuja antaa "
                  "vaikutettavan alun (xpHorizon/actionableGameweek)",
    "lib/components/ProjectionsPanel.svelte": "RateTeamin paneeli: kuluva kierros on kentan "
                  "pari (Team xP GW6 + kentta), korostus meta.gw; suunniteltu",
    "lib/components/TeamPitchManager.svelte": "rate-teamin rivit (min_gw rajattu backendissa), "
                  "kuluva kierros kentalla; suunniteltu",
    "routes/spl/+page.svelte": "SPL:n oma artefakti (spl_xp) ja kierroslogiikka, ei FPL:n "
                  "deadline_gameweekia; eri tarkastus",
    "routes/ucl/+page.svelte": "UCL:n matchday-artefakti (ucl_xp), oma MD-logiikka; eri tarkastus",
}


def _osumat() -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for p in sorted(SRC.rglob("*")):
        if p.suffix not in (".svelte", ".ts") or p.name.endswith(".test.ts"):
            continue
        rel = p.relative_to(SRC).as_posix()
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith(("//", "*", "/*", "<!--")):
                continue
            if RAAKA.search(line):
                out.setdefault(rel, []).append(i)
    return out


def test_raakarivit_vain_perustelluissa_tiedostoissa():
    vaarat = {f: rivit for f, rivit in _osumat().items()
              if not POIKKEUKSET.get(f, "").strip()}
    assert not vaarat, (
        "xP-rivit luettu raakana ennustepinnassa: kesken kierroksen nama nayttavat "
        "lukitun kierroksen. Kayta $lib/gameweek.actionableRows tai kirjaa perustelu "
        f"POIKKEUKSET-listaan: {vaarat}")


def test_poikkeuslista_ei_vanhene():
    """Poikkeus tiedostolle jossa ei enaa ole osumaa on kuollut kirjaus."""
    osumat = _osumat()
    kuolleet = [f for f in POIKKEUKSET if f not in osumat]
    assert not kuolleet, kuolleet


@pytest.mark.parametrize("rel,odotettu", [
    ("lib/components/PlayerCard.svelte", "actionableRows(meta, player.gameweeks)[0]"),
    ("lib/components/PlayerCard.svelte", "{@const gws = actionableRows(meta, player.gameweeks)}"),
    ("lib/components/XpTable.svelte", "actionableRows(data.meta, data.players[0]?.gameweeks)"),
    ("lib/components/FixtureSwing.svelte", "actionableRows(data?.meta, gws)"),
])
def test_kutsupaikat_lukevat_lukijan(rel, odotettu):
    assert odotettu in (SRC / rel).read_text(encoding="utf-8")


def test_negatiivinen_kontrolli_kuvio_osuu():
    """Ilman tata portti voisi olla vihrea rikkinaisella regexilla."""
    for vanha in ("{@const nextGwRow = (player.gameweeks ?? [])[0]}",
                  "let gwCols = $derived(data.players[0]?.gameweeks?.map((g) => g.gw) ?? []);",
                  "{#each player.gameweeks as g (g.gw)}"):
        assert RAAKA.search(vanha), vanha
