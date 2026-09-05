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


# ---------------------------------------------------------------------------
# XP-READER-DISCIPLINE-AUKKO (5.9.2026). `_scan()` yllä nakee vain
# `load_xp(`-KUTSUJA, joten se ei nae SUORAA POLKULUKUA: build_fpl_longtail.py
# (ja kaksi muuta tiedostoa) lukivat data/fpl_xp_projections.json:n omalla
# geneerisella JSON-lukijallaan (`_load(XP_PATH)`), mika ohittaa
# `load_xp_actionable()`:n kokonaan eika sisalla merkkijonoa "load_xp" - regex
# ei voi loytaa tata. Skanneri talla kertaa on AST: se seuraa mihin muuttujaan
# `.../fpl_xp_projections.json`-polku sidotaan ja katsoo annetaanko se
# muuttuja jollekin MUULLE kutsulle kuin `load_xp`/`load_xp_actionable`.
# ---------------------------------------------------------------------------
import ast

XP_PROJECTIONS_FILENAME = "fpl_xp_projections.json"

# Nama funktionimet ohittavat vartijan: `load_xp`/`load_xp_actionable` ovat
# lukijat itse, `_load_xp_page_source` on tama korjaus tuonut turvallinen
# kaare (build_fpl_page.py + build_fpl_longtail.py) joka tarkistaa ensin
# etta tiedosto on olemassa/eheä (sama nakyva sopimus kuin sen oma raaka
# lukijansa) ja kutsuu sitten `load_xp_actionable`a - se EI ole uusi ohitus.
SAFE_CALL_NAMES = {"load_xp", "load_xp_actionable", "_load_xp_page_source"}

# Tiedosto -> miksi sen suora polkuluku ei tarvitse load_xp_actionablea.
# Jokainen rivi tassa on TARKISTETTU lukemalla mita kutsuttu funktio oikeasti
# tekee datalla (ei "luultavasti ok") - katso perustelu.
RAW_PATH_ALLOWED = {
    "scripts/build_fpl_longtail.py":
        "_gw_still_running lukee vain meta.next_gameweek, ei yhtaan pelaajan "
        "gameweeks-kenttaa (funktion oma docstring perustelee tarkemmin), "
        "joten load_xp_actionablen trimmauksella ei olisi vaikutusta sen "
        "palauttamaan arvoon.",
    "scripts/push_dispatch.py":
        "pick_of_week(xp, gw) hakee NIMETYN kierroksen rivin eksplisiittisesti "
        "(g.get('gw') == gw) p.get('gameweeks')-listasta eika oleta eka "
        "rivia nykyhetkeksi - haettu gw on aina tuleva deadline, joten "
        "trimmaus ei koskaan poistaisi sita riviä.",
    "scripts/build_gw_digest.py":
        "build_facts laskee xp-payloadista vain total_players = "
        "len(players) - se ei lue yhdenkaan pelaajan gameweeks-kenttaa, "
        "joten trimmauksella ei ole vaikutusta lukuun.",
    "scripts/squad_signals_watch.py":
        "diff_signals/stale_override_flags (src/models/squad_signals.py) "
        "poimivat projektiosta vain owned_pct ja p_start pelaajan "
        "ylatasolta _projection_index:in kautta, eivat koske gameweeks-"
        "listaan - roolinvahti diffaa saatavuutta, ei kierroskohtaista xP:ta.",
}


def _path_const_names(tree: ast.AST) -> set[str]:
    """Nimet jotka on sidottu polkuun joka paattyy fpl_xp_projections.json:iin,
    esim. `XP_PATH = ROOT / "data" / "fpl_xp_projections.json"` - kavellaan
    oikealle BinOp-ketjussa (`a / b / c`) viimeiseen literaaliin asti."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            leaf = node.value
            while isinstance(leaf, ast.BinOp):
                leaf = leaf.right
            if (isinstance(leaf, ast.Constant) and isinstance(leaf.value, str)
                    and leaf.value.endswith(XP_PROJECTIONS_FILENAME)):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
    return names


def _call_fname(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _raw_path_hits_in_source(source: str, filename: str = "<test>") -> list[int]:
    """Rivit joilla joku fpl_xp_projections.json-polkuvakio annetaan
    argumenttina kutsulle joka ei ole `SAFE_CALL_NAMES`:ssa. Tyhja lista jos
    tiedosto ei edes maarittele talaista vakiota (nopea reitti enemmistolle)."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []
    names = _path_const_names(tree)
    if not names:
        return []
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_fname(node) in SAFE_CALL_NAMES:
            continue
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Name) and arg.id in names:
                hits.append(node.lineno)
    return hits


def _scan_raw_path_reads() -> dict[str, list[int]]:
    hits: dict[str, list[int]] = {}
    for base in ("api", "scripts", "src"):
        for f in sorted((ROOT / base).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            ls = _raw_path_hits_in_source(f.read_text(encoding="utf-8"), rel)
            if ls:
                hits[rel] = ls
    return hits


def test_raw_path_argument_is_used_only_where_it_is_argued_for():
    """AST-versio: nakee myos kutsut jotka eivat sisalla sanaa 'load_xp'."""
    hits = _scan_raw_path_reads()
    uusia = {f: ls for f, ls in hits.items() if f not in RAW_PATH_ALLOWED}
    assert not uusia, (
        "Nama tiedostot antavat data/fpl_xp_projections.json-polun suoraan "
        "jollekin kutsulle ohittaen load_xp/load_xp_actionable (AST loytaa "
        "taman vaikka kutsu ei sisalla sanaa load_xp). Kayta "
        "`load_xp_actionable()`a tai lisaa tiedosto RAW_PATH_ALLOWED-listaan "
        "ja kirjoita MIKSI (mita kutsuttu funktio oikeasti tekee datalla):\n"
        + "\n".join(f"  {f}: rivit {ls}" for f, ls in sorted(uusia.items())))


def test_every_raw_path_allowlist_entry_still_reads_the_raw_path():
    hits = _scan_raw_path_reads()
    kuolleet = [f for f in RAW_PATH_ALLOWED if f not in hits]
    assert not kuolleet, (
        "RAW_PATH_ALLOWED-listalla on tiedostoja jotka eivat enaa anna "
        f"raakaa polkua kutsulle, poista ne: {kuolleet}")


def test_the_raw_path_allowlist_carries_a_real_reason():
    for f, syy in RAW_PATH_ALLOWED.items():
        assert len(syy.split()) >= 6, (f, syy)


def test_MUTAATIO_polkuluku_ilman_load_xp_sanaa_kaatuu():
    """Mutaatiotesti: sama tapaus jonka VANHA (`load_xp(`-regex) skanneri ei
    olisi koskaan nahnyt, koska kutsu ei sisalla sanaa 'load_xp'."""
    bad = (
        'from pathlib import Path\n'
        'ROOT = Path(".")\n'
        'XP_PATH = ROOT / "data" / "fpl_xp_projections.json"\n'
        'def f():\n'
        '    return _load(XP_PATH)\n'
    )
    assert not CALL.search(bad), "vanha regex ei saisi nahda tata - muuten mutaatio ei mittaa mitaan"
    assert _raw_path_hits_in_source(bad) == [5]


def test_NEG_polkuluku_actionable_lukijalle_ei_kaadu():
    good = (
        'from pathlib import Path\n'
        'from src.models.fpl_xp import load_xp_actionable\n'
        'ROOT = Path(".")\n'
        'XP_PATH = ROOT / "data" / "fpl_xp_projections.json"\n'
        'def f():\n'
        '    return load_xp_actionable(XP_PATH)\n'
    )
    assert _raw_path_hits_in_source(good) == []


def test_NEG_maarittely_ilman_kayttoa_ei_kaadu():
    """Negatiivinen kontrolli: pelkka polun MAARITTELY ei ole 'raaka luku' -
    vasta kutsu argumenttina tekee siita sellaisen."""
    unused = (
        'from pathlib import Path\n'
        'ROOT = Path(".")\n'
        'XP_PATH = ROOT / "data" / "fpl_xp_projections.json"\n'
    )
    assert _raw_path_hits_in_source(unused) == []
