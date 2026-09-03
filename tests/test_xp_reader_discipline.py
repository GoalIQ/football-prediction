# -*- coding: utf-8 -*-
"""LUKIJAKURI (3.9.2026). Villen pyynto: "suunnittelet ne siten ettei niihin
vaan tule bugeja."

Kierrosvaihdon viat syntyivat aina samalla tavalla: pinta luki
`data/fpl_xp_projections.json`:n `gameweeks[]`-listan RAAKANA, lista alkaa
menneesta kierroksesta, ja jokainen lukija joutui MUISTAMAAN suodattaa sen.
Muistaminen on huono suunnittelu: se pettaa juuri silloin kun uusi pinta
kirjoitetaan kesken kauden.

Siksi oletus on kaannetty. `fpl_xp.load_xp_actionable()` ei voi antaa
mennytta kierrosta, ja raaka `load_xp()` on sallittu vain nimetyille
tiedostoille nimetysta syysta. Uusi tiedosto EI paase listalle vahingossa:
testi kaatuu ja kirjoittaja joutuu perustelemaan valinnan tassa.

Tama ei estä kaikkia kierrosvaihdon vikoja. Se estaa sen luokan jossa vika
syntyy UNOHDUKSESTA, ja jattaa jaljelle vain ne jotka joku on tietoisesti
valinnut - ja ne nakyvat diffissa.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Tiedosto -> miksi se saa lukea raakaa projektiota.
# Rivi ilman perustelua ei ole perustelu: kirjoita mita kierroksia tiedosto
# tarvitsee menneisyydesta ja miksi rajattu lukija ei kelpaa.
RAW_ALLOWED = {
    "src/models/fpl_xp.py":
        "Lukija itse: `load_xp_actionable` on kaare taman ympärilla, joten "
        "raaka kutsu on tassa tiedostossa valttamaton.",
    "src/models/fpl_rate_team.py":
        "Rate my team nayttaa KESKEN olevan kierroksen ('Team xP, GW3' kesken "
        "GW3:a on oikein, se on mita joukkue juuri nyt keraa), joten "
        "`deadline_gameweek`-rajaus veisi silta oman kierroksensa. Rajaus "
        "tehdaan vastauksessa: `_player_gameweeks(min_gw=target_gw)`.",
    "api/fantasy_edge.py":
        "Chip-EV ja siirtoketjut rajaavat itse `_playable_gws()`:lla, joka on "
        "tiukempi kuin lukijan rajaus (se lukee saman `deadline_gameweek`:n "
        "mutta suodattaa myos poolin ulkopuoliset kierrokset).",
    "api/main.py":
        "Ilmaispinnan xP-endpointit palauttavat koko horisontin "
        "tarkoituksella: sivu nayttaa myos gradatun kierroksen tuloksen "
        "vieressa, ja rajaus piilottaisi tarkistusreitin.",
}

# Gradaus, backtest ja jaadytys LUKEVAT menneisyytta tyokseen.
HISTORY_BY_DESIGN = re.compile(
    r"(^|/)(grade_|backtest_|freeze_|check_xp_headline_gw|build_gw_recap)")

CALL = re.compile(r"\bload_xp\s*\(")
IMPORT = re.compile(r"\bfrom\s+src\.models\.fpl_xp\s+import\s+([^\n]+)")


def _scan() -> dict[str, list[int]]:
    hits: dict[str, list[int]] = {}
    for base in ("api", "scripts", "src"):
        for f in sorted((ROOT / base).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            if HISTORY_BY_DESIGN.search(rel):
                continue
            lines = f.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines, start=1):
                if line.lstrip().startswith("#"):
                    continue
                if CALL.search(line) and "load_xp_actionable" not in line:
                    hits.setdefault(rel, []).append(i)
                m = IMPORT.search(line)
                if m and re.search(r"\bload_xp\b(?!_actionable)", m.group(1)):
                    hits.setdefault(rel, []).append(i)
    return hits


def test_raw_projection_reader_is_used_only_where_it_is_argued_for():
    hits = _scan()
    uusia = {f: ls for f, ls in hits.items() if f not in RAW_ALLOWED}
    assert not uusia, (
        "Nama tiedostot lukevat raakaa projektiota ilman perustelua. Kayta "
        "`load_xp_actionable()` (se ei voi antaa mennytta kierrosta) tai "
        "lisaa tiedosto RAW_ALLOWED-listaan ja kirjoita MIKSI:\n"
        + "\n".join(f"  {f}: rivit {ls}" for f, ls in sorted(uusia.items())))


def test_every_allowlist_entry_still_reads_the_raw_reader():
    """Vanhentunut poikkeus on huonompi kuin ei poikkeusta: se opettaa etta
    listalle paasee eika sielta poistuta."""
    hits = _scan()
    kuolleet = [f for f in RAW_ALLOWED if f not in hits]
    assert not kuolleet, (
        "RAW_ALLOWED-listalla on tiedostoja jotka eivat enaa lue raakaa "
        f"projektiota, poista ne: {kuolleet}")


def test_the_allowlist_carries_a_real_reason():
    for f, syy in RAW_ALLOWED.items():
        assert len(syy.split()) >= 6, (f, syy)


def test_actionable_reader_drops_past_gameweeks_and_says_so(tmp_path,
                                                            monkeypatch):
    """Negatiivinen kontrolli: sama data ilman `deadline_gameweek` palautuu
    muuttumattomana, eli suodatin ei ole 'pudota aina ensimmainen'."""
    import json

    from src.models import fpl_xp

    doc = {"meta": {"available": True, "deadline_gameweek": 4},
           "players": [{"id": 1, "gameweeks": [{"gw": g} for g in (2, 3, 4, 5)]}]}
    p = tmp_path / "xp.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    out = fpl_xp.load_xp_actionable(p)
    assert [g["gw"] for g in out["players"][0]["gameweeks"]] == [4, 5]
    assert out["meta"]["trimmed_from"] == 4

    doc["meta"].pop("deadline_gameweek")
    doc["meta"]["current_gameweek"] = None
    p.write_text(json.dumps(doc), encoding="utf-8")
    out2 = fpl_xp.load_xp_actionable(p)
    assert [g["gw"] for g in out2["players"][0]["gameweeks"]] == [2, 3, 4, 5]
    assert "trimmed_from" not in out2["meta"]
