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

import ast
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

# XP-READER-DISCIPLINE-AUKKO (6.9.2026, portin sivuloydos 4.9):
# `build_fpl_longtail.py` luki `data/fpl_xp_projections.json`:n `_load(XP_PATH)`
# -lla, joka ei kutsu `load_xp(`-nimista funktiota ollenkaan -> ylla oleva
# regex ei nae SUORAA POLKULUKUA, vain suoria kutsuja lukijan OMALLA nimella.
# Tama AST-skanneri kattaa sen: se seuraa mihin muuttujaan XP-artefaktin
# polku sidotaan (esim. `XP_PATH = ROOT / "data" / "fpl_xp_projections.json"`)
# ja loytaa jokaisen lukukutsun (open/json.load(s)/.read_text/.read_bytes tai
# tiedoston OMA geneerinen lukijafunktio kuten `_load`) joka saa tuon
# muuttujan tai literaalin argumenttinaan - riippumatta funktion nimesta.
XP_LITERAL = "fpl_xp_projections.json"
_READ_ATTRS = {"read_text", "read_bytes"}
_READ_DOTTED = {"json.load", "json.loads"}


def _callee_parts(func: ast.expr) -> list[str]:
    """Paras arvaus kutsutun nimesta osina, esim. Attribute(a.b.c) -> [a,b,c]."""
    parts: list[str] = []
    node = func
    while isinstance(node, ast.Attribute):
        parts.insert(0, node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.insert(0, node.id)
    return parts


def _contains_xp_reference(node: ast.AST, aliases: set[str]) -> bool:
    """Viittaako lauseke (rekursiivisesti) XP-polkualiakseen tai literaaliin."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in aliases:
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                and XP_LITERAL in sub.value:
            return True
    return False


def _xp_path_aliases(tree: ast.AST) -> set[str]:
    """Muuttujat joiden arvo on rakennettu XP-artefaktin polusta."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _contains_xp_reference(node.value, set()):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    aliases.add(tgt.id)
    return aliases


def _local_reader_names(tree: ast.AST) -> set[str]:
    """Tiedoston OMAT funktiot jotka lukevat tiedoston (esim. `_load`).

    Tunnistetaan runkoa katsomalla, ei nimesta - `_load`, `_read_json`,
    `fetch_json` jne. tunnistuvat kaikki samalla tavalla eika uusi nimi
    paase karkuun.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    parts = _callee_parts(sub.func)
                    if parts and (parts[-1] in _READ_ATTRS
                                  or parts[-1] == "open"
                                  or ".".join(parts) in _READ_DOTTED):
                        names.add(node.name)
                        break
    return names


def _scan_path_reads(rel: str, tree: ast.AST) -> list[int]:
    aliases = _xp_path_aliases(tree)
    if not aliases:
        return []
    local_readers = _local_reader_names(tree)
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        parts = _callee_parts(node.func)
        if not parts:
            continue
        dotted = ".".join(parts)
        if parts[-1] in ("load_xp", "load_xp_actionable"):
            continue  # legitiimi lukija
        is_read = (
            parts[-1] in _READ_ATTRS
            or parts[-1] == "open"
            or dotted in _READ_DOTTED
            or (len(parts) == 1 and parts[0] in local_readers)
        )
        if not is_read:
            continue
        operands = list(node.args) + [kw.value for kw in node.keywords]
        if isinstance(node.func, ast.Attribute):
            operands.append(node.func.value)
        if any(_contains_xp_reference(op, aliases) for op in operands) \
                and node.lineno not in hits:
            hits.append(node.lineno)
    return sorted(hits)


def _scan() -> dict[str, list[int]]:
    """Alkuperainen (3.9) skanneri: suorat `load_xp(`-kutsut ja -importit
    nimella. Pidetaan blokkaavana testina sellaisenaan - RAW_ALLOWED-lista
    on jo neljan tiedoston varassa taman perusteella."""
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


def _scan_ast(base_dirs=("api", "scripts", "src")) -> dict[str, list[int]]:
    """UUSI (6.9) skanneri: nakee suoran polkuluvun riippumatta funktion
    nimesta (ks. XP_LITERAL-lohko yllä). Katso miksi tama on ERI testi kuin
    `test_raw_projection_reader_is_used_only_where_it_is_argued_for` sen
    omasta docstringista alla - tama ei viela blokkaa koko sviittia."""
    hits: dict[str, list[int]] = {}
    for base in base_dirs:
        for f in sorted((ROOT / base).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            if HISTORY_BY_DESIGN.search(rel):
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            ls = _scan_path_reads(rel, tree)
            if ls:
                hits[rel] = ls
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


# ---------------------------------------------------------------------------
# UUSI AST-skanneri (6.9.2026, tama rivi): loysi build_fpl_longtail.py:n
# lisaksi VIELA 14 tiedostoa jotka lukevat XP-artefaktia polulla
# (`XP_PATH.read_text()`, `_load_json(XP_PATH)`, jne) ohittaen
# `load_xp_actionable()`:n. build_fpl_longtail.py on korjattu edella (kaksi
# kutsua reititetty lukijan lapi); nailla 14:lla ei ole viela kumpaakaan -
# jokainen tarvitsee oman auditoinnin (naytetaanko sen tuloksesta julkista
# kopiota jossain jossa mennyt kierros voisi vuotaa nakyviin), ja se on
# isompi tyo kuin yksi yoajon rivi kantaa. Siksi tama on RATCHET eika
# hyvaksynta: se ei vaadi etta nama 14 on jo selitetty, mutta estaa
# viidennentoista ilmestymisen huomaamatta. Seuraava jonorivi: audita
# jokainen ja joko (a) reititä `load_xp_actionable`:en tai (b) kirjoita
# oikea peruste RAW_ALLOWEDiin.
KNOWN_UNAUDITED_PATH_READS = {
    "scripts/build_fpl_page.py": [3778],
    "scripts/build_fpl_why.py": [546],
    "scripts/build_gw_digest.py": [351],
    "scripts/build_team_confidence.py": [68],
    "scripts/gen_reel.py": [109],
    "scripts/gen_share_card.py": [225, 248, 913],
    "scripts/log_gw_calls.py": [58],
    "scripts/measure_promoted_bias.py": [53],
    "scripts/push_dispatch.py": [682],
    "scripts/render_frozen_squad_card.py": [166],
    "scripts/render_projected_xi_card.py": [434],
    "scripts/render_standouts_card.py": [433],
    "scripts/role_change_watch.py": [63],
    "scripts/squad_signals_watch.py": [283],
}


def test_ast_scanner_finds_no_new_unaudited_direct_reads():
    """RATCHET: uusi tiedosto TAI uusi rivi tunnettua listaa vastaan kaataa.

    Ei vaadi etta 6.9 loydetyt 14 on jo korjattu (se on oma auditointinsa),
    mutta estaa viidennentoista ilmestymisen huomaamatta.
    """
    hits = _scan_ast()
    uudet_tiedostot = sorted(set(hits) - set(KNOWN_UNAUDITED_PATH_READS))
    assert not uudet_tiedostot, (
        "AST-skanneri loysi UUDEN tiedoston joka lukee XP-artefaktia "
        "polulla lukijan ohi. Kayta load_xp_actionable() tai lisaa "
        "perusteltu poikkeus RAW_ALLOWEDiin, ala lisaa tata listaa:\n"
        + "\n".join(f"  {f}: rivit {hits[f]}" for f in uudet_tiedostot))
    for f, tunnetut in KNOWN_UNAUDITED_PATH_READS.items():
        uudet_rivit = sorted(set(hits.get(f, [])) - set(tunnetut))
        assert not uudet_rivit, (
            f"{f}: uusi raaka polkuluku rivilla {uudet_rivit} jota "
            "tunnettu-lista ei kata.")


def test_known_unaudited_path_reads_list_does_not_grow_stale():
    """Symmetrinen allowlist-testin kanssa: jos tiedosto ei enaa lue
    raakaa polkua, se pitaa poistaa listalta - muuten se opettaa etta
    listalle jaadaan ikuisesti."""
    hits = _scan_ast()
    kuolleet = [f for f in KNOWN_UNAUDITED_PATH_READS if f not in hits]
    assert not kuolleet, (
        "Nama on jo korjattu - poista KNOWN_UNAUDITED_PATH_READS-listalta: "
        f"{kuolleet}")


def test_negative_control_ratchet_would_catch_a_new_file():
    """Kontrolli ratchetin omalle vertailulogiikalle: synteettinen 'uusi
    tiedosto' jota KNOWN_UNAUDITED_PATH_READS ei tunne kaataisi testin."""
    hits = dict(KNOWN_UNAUDITED_PATH_READS)
    hits["scripts/brand_new_offender.py"] = [1]
    uudet_tiedostot = sorted(set(hits) - set(KNOWN_UNAUDITED_PATH_READS))
    assert uudet_tiedostot == ["scripts/brand_new_offender.py"]


def test_ast_scanner_catches_a_direct_path_read_by_argument_not_by_name():
    """Se mika oikeasti puuttui: `build_fpl_longtail.py` luki artefaktin
    `_load(XP_PATH)`:lla - eri nimi kuin `load_xp(`, joten regex ei nahnyt
    sita. Synteettinen kutsuja: sama muoto, eri tiedosto ja funktion nimi."""
    src = (
        'from pathlib import Path\n'
        'ROOT = Path(".")\n'
        'XP_PATH = ROOT / "data" / "fpl_xp_projections.json"\n'
        'def _load(path):\n'
        '    import json\n'
        '    return json.loads(path.read_text())\n'
        'def main():\n'
        '    xp = _load(XP_PATH)\n'
        '    return xp\n'
    )
    tree = ast.parse(src)
    hits = _scan_path_reads("synthetic_caller.py", tree)
    assert hits == [8], hits  # `xp = _load(XP_PATH)` -rivi


def test_negative_control_ast_scanner_does_not_flag_the_actionable_reader():
    """Kontrolli: sama muoto mutta oikealla lukijalla ei saa laueta."""
    src = (
        'from pathlib import Path\n'
        'from src.models.fpl_xp import load_xp_actionable\n'
        'XP_PATH = Path(".") / "data" / "fpl_xp_projections.json"\n'
        'def main():\n'
        '    xp = load_xp_actionable(XP_PATH)\n'
        '    return xp\n'
    )
    tree = ast.parse(src)
    assert _scan_path_reads("synthetic_ok.py", tree) == []


def test_negative_control_ast_scanner_ignores_unrelated_files():
    """Kontrolli: geneerinen `_load()` jota kaytetaan johonkin MUUHUN
    tiedostoon ei saa laueta - vahti koskee vain XP-artefaktia."""
    src = (
        'from pathlib import Path\n'
        'OTHER_PATH = Path(".") / "data" / "fpl_price_watch.json"\n'
        'def _load(path):\n'
        '    return path.read_text()\n'
        'def main():\n'
        '    return _load(OTHER_PATH)\n'
    )
    tree = ast.parse(src)
    assert _scan_path_reads("synthetic_unrelated.py", tree) == []


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
