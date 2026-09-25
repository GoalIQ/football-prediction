# -*- coding: utf-8 -*-
"""Julkinen lupaus "every match prediction is logged before kick-off" on
tarkistettavissa julkisesta lokista (TARKKUUSLOKI-KICKOFF-VAITE, 25.9.2026).

Mitattu 25.9: 657 gradatusta rivista 609:lla on `kickoff`, ja niilla KAIKILLA
`logged_at`, `first_logged_at` ja `refreshed_at` ovat ennen kickoffia. Loput 48
ovat kesan MM-hubin rivejä (`wc_hub_seed` 40 ilman paivaa ja aikaleimaa,
`wc_hub_upcoming_backfill` 8 kirjattu ennen ottelupaivaa). Portti pitaa tilan:

1. gradattu rivi jolla on kickoff: jokainen kirjausaika < kickoff
2. rivi ilman kickoffia sallitaan VAIN perustellulta vanhalta lahteelta
   (poikkeuslista, CLAUDE.md 6a mek. 2): uusi lahde ilman kickoffia kaatuu
3. positiivinen kontrolli: kickoffin jalkeinen paivitys havaitaan
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOKI = ROOT / "data" / "prediction_log.json"

# Lahde -> miksi sen riveilla ei ole kickoffia. Uusi merkinta vaatii perustelun.
ILMAN_KICKOFFIA = {
    "wc_hub_seed": "MM 2026 -hubista kesalla siemennetyt 40 rivia: ei paivaa eika "
                   "aikaleimaa. Julkaisupaatos (poisto track recordista vai copyn "
                   "rajaus) on Villella, jonorivi TARKKUUSLOKI-KICKOFF-VAITE.",
    "wc_hub_upcoming_backfill": "MM 2026 -hubin tulevat ottelut, kirjattu ennen "
                                "ottelupaivaa (logged_at < date), kickoff-kellonaika puuttuu.",
}
AJAT = ("logged_at", "first_logged_at", "refreshed_at")


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def rikkeet(rivit: list[dict]) -> list[str]:
    ulos = []
    for r in rivit:
        k = r.get("kickoff")
        if not k:
            if r.get("source") not in ILMAN_KICKOFFIA:
                ulos.append(f"{r.get('match_id')}: ei kickoffia, lahde {r.get('source')!r} ei poikkeuslistalla")
            continue
        if not r.get("result"):
            continue
        for kentta in AJAT:
            if r.get(kentta) and _t(r[kentta]) >= _t(k):
                ulos.append(f"{r.get('match_id')}: {kentta} {r[kentta]} >= kickoff {k}")
    return ulos


def _rivit() -> list[dict]:
    return json.loads(LOKI.read_text(encoding="utf-8"))["predictions"]


def test_julkinen_loki_kirjattu_ennen_kickoffia():
    r = rikkeet(_rivit())
    assert not r, f"{len(r)} rikettä, ensimmaiset: {r[:5]}"


def test_portti_mittaa_jotain():
    """Ilman tata portti olisi vihrea tyhjalla tai kickoffittomalla lokilla."""
    rivit = _rivit()
    gradattu_kickoff = [r for r in rivit if r.get("result") and r.get("kickoff")]
    assert len(gradattu_kickoff) >= 600, len(gradattu_kickoff)


def test_positiivinen_kontrolli_kickoffin_jalkeinen_paivitys():
    rivi = {"match_id": "x", "source": "fd", "kickoff": "2026-09-20T15:00:00Z",
            "logged_at": "2026-09-19T10:00:00+00:00",
            "refreshed_at": "2026-09-20T15:30:00+00:00", "result": {"hit_1x2": True}}
    assert rikkeet([rivi]) == ["x: refreshed_at 2026-09-20T15:30:00+00:00 >= kickoff 2026-09-20T15:00:00Z"]


def test_uusi_lahde_ilman_kickoffia_kaatuu():
    assert rikkeet([{"match_id": "y", "source": "uusi_lahde", "result": None}])
