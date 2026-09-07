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
# 🔴 SUORA POLKULUKU (7.9.2026). Ylla oleva skanneri etsii `load_xp(`-KUTSUJA,
# joten se ei nae tiedostoa joka avaa `data/fpl_xp_projections.json`:n suoraan
# polulla. Mitattu: **21 tiedostoa** lukee artefaktin nain, eika yksikaan
# nakynyt lukijakurin portille. Saanto 6a kohta 1 sanoo etta lukijan on oltava
# yksi joka ei voi palauttaa vaaraa; tama oli reika siina, ja se oli suurempi
# kuin itse vartioitu polku.
#
# Skannaus tehdaan AST:lla eika regexilla: kommentit eivat ole AST:ssa
# lainkaan, ja docstringit suodatetaan erikseen, joten tiedoston MAININTA
# (esim. "Datalahteet: data/fpl_xp_projections.json") ei laukaise porttia -
# vain koodissa oleva merkkijonoliteraali.
#
# Poikkeuslista vaatii perustelun, ja perustelun on kerrottava MITEN tiedosto
# rajaa kierrokset. Uusi tiedosto ei paase listalle vahingossa.
XP_ARTIFACT = "fpl_xp_projections.json"

PATH_ALLOWED = {
    "src/models/fpl_xp.py":
        "Lukija itse: `load_xp` ja `load_xp_actionable` avaavat tiedoston, "
        "joten polkuluku on tassa valttamaton.",
    "src/models/fpl_player_stats.py":
        "Kutsuu `load_xp_actionable(XP_PATH)`, eli polku on vain argumentti "
        "rajatulle lukijalle - ei ohitus.",
    "scripts/build_fpl_xp.py":
        "KIRJOITTAJA: tama skripti tuottaa artefaktin (`OUT_PATH`). Se ei voi "
        "lukea sita rajatun lukijan lapi, koska lukijaa ei ole ennen kuin "
        "tiedosto on olemassa.",
    "scripts/build_fpl_longtail.py":
        "Rajaa itse `actionable_gameweek`illa (5 osumaa): otsikko lupaa "
        "'Best FPL Captain GW{n}', ja `next_gameweek` osoittaa kesken "
        "kierroksen jo lukittuun kierrokseen. Rajaus on tiukempi kuin "
        "lukijan, koska se koskee myos `xp_dist`-lohkoa.",
    "scripts/build_fpl_page.py":
        "Sivu nayttaa myos gradatun kierroksen tuloksen elavan projektion "
        "vieressa (tarkistusreitti lukijalle); rajaus piilottaisi sen. "
        "Deadline-hetken lahde on eksplisiittisesti `deadline_gameweek` "
        "miinus yksi.",
    "scripts/build_fpl_why.py":
        "Sama tarkistusreitti kuin `build_fpl_page`: miksi-sivu selittaa "
        "juuri gradatun kierroksen, joten se tarvitsee MENNEEN kierroksen. "
        "Rajaus tehdaan `deadline_gameweek`ista kayttokohdassa.",
    "scripts/build_gw_digest.py":
        "Lukee vain `meta`-lohkon, ei kierroslistaa lainkaan (mitattu 7.9: "
        "0 osumaa), joten kierrosrajauksella ei ole kohdetta.",
    "scripts/build_team_confidence.py":
        "Lukee vain `meta`n ja joukkuetason lukuja (0 osumaa "
        "kierroslistaan); nousijavaite ei ole kierroskohtainen.",
    "scripts/gen_reel.py":
        "Lukee pelaajatason `xp_horizon_total`in, ei kierroslistaa (0 "
        "osumaa `gameweeks[]`:hin). 🔴 HUOM: horisonttisumma sisaltaa "
        "menneen kierroksen heti kun lista alkaa menneisyydesta, ja reelin "
        "tekstissa lukee 'First six gameweeks' - ikkunan nimeaminen on oma "
        "rivinsa (QUEUE REEL-HORISONTTI-IKKUNA). Rajaus ei silti kuulu "
        "lukijalle: reel nayttaa horisontin, ei yhta kierrosta.",
    "scripts/gen_share_card.py":
        "Valitsee kierroksen eksplisiittisesti (`g.get('gw') == gw`) eika "
        "listan jarjestyksesta, ja ikkunan otsikko tulee `window_label`ista "
        "joka johtaa sen todellisista kierroksista. Kortti nayttaa myos "
        "gradatun kierroksen, joten rajaus veisi silta sisallon.",
    "scripts/log_gw_calls.py":
        "Importoi `actionable_gameweek`in nimenomaan tata varten (portti: "
        "ei `next_gameweek` suoraan); kutsu kirjataan sille kierrokselle "
        "johon voi viela vaikuttaa.",
    "scripts/measure_promoted_bias.py":
        "Mittausskripti: lukee `meta`n eika kierroslistaa (0 osumaa). Tulos "
        "ei mene millekaan kayttajan nakemalle pinnalle.",
    "scripts/push_dispatch.py":
        "Valitsee kierroksen eksplisiittisesti (`g.get('gw') == gw`), missa "
        "`gw` tulee kutsujalta - ei listan ensimmaisesta alkiosta.",
    "scripts/render_frozen_squad_card.py":
        "Jaadytyskortti nayttaa MENNEEN kierroksen ennusteen toteumaa "
        "vasten; se on kortin koko tarkoitus, joten rajattu lukija ei kelpaa. "
        "Kierros valitaan eksplisiittisesti kutsujan antamana.",
    "scripts/render_projected_xi_card.py":
        "Importoi `actionable_gameweek`in (portti: ei `next_gameweek` "
        "suoraan); kortti julkaistaan ennen deadlinea ja koskee sita "
        "kierrosta johon voi viela vaikuttaa.",
    "scripts/render_standouts_card.py":
        "Importoi `actionable_gameweek`in (6 rajausosumaa) ja rajaa lisaksi "
        "`claim_scope()`lla; kortin superlatiivit koskevat tasan sita "
        "kierrosta jota otsikko lupaa.",
    "scripts/role_change_watch.py":
        "Vahti lukee `meta`n ja pelaajatason kenttia, ei kierroslistaa "
        "(0 osumaa); roolimuutos ei ole kierroskohtainen.",
    "scripts/squad_signals_watch.py":
        "Antaa koko dokumentin `diff_signals`ille, joka indeksoi sen "
        "`_projection_index`illa PELAAJA-ID:N mukaan ja lukee vain "
        "pelaajatason kenttia - ei kierroslistaa (0 osumaa "
        "`gameweeks[]`:hin missaan haarassa). Signaali on tilamuutos "
        "(status, erikoistilanteet, ohitukset), ei kierroskohtainen luku.",
    "scripts/check_copy_style.py":
        "Tiedostonimi esiintyy SKANNATTAVIEN tiedostojen listassa, ei "
        "datalukuna. Portti ei avaa artefaktia projektiona lainkaan.",
}

# Gradaus, jaadytys ja tarkistusskriptit lukevat menneisyytta tyokseen -
# sama poikkeus kuin `load_xp`-skannerilla.
PATH_HISTORY_BY_DESIGN = HISTORY_BY_DESIGN


def _string_literals(path) -> list[int]:
    """Rivit joilla artefaktin nimi esiintyy KOODIN merkkijonona.

    Docstringit suodatetaan; kommentit eivat ole AST:ssa lainkaan. Nain
    tiedoston maininta dokumentaatiossa ei laukaise porttia.
    """
    import ast
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    if XP_ARTIFACT not in src:
        return []
    tree = ast.parse(src)
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            if (n.body and isinstance(n.body[0], ast.Expr)
                    and isinstance(getattr(n.body[0], "value", None), ast.Constant)
                    and isinstance(n.body[0].value.value, str)):
                docs.add(id(n.body[0].value))
    return sorted({n.lineno for n in ast.walk(tree)
                   if isinstance(n, ast.Constant)
                   and isinstance(n.value, str)
                   and XP_ARTIFACT in n.value
                   and id(n) not in docs})


def _scan_paths() -> dict[str, list[int]]:
    hits: dict[str, list[int]] = {}
    for base in ("api", "scripts", "src"):
        for f in sorted((ROOT / base).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            if PATH_HISTORY_BY_DESIGN.search(rel):
                continue
            rivit = _string_literals(f)
            if rivit:
                hits[rel] = rivit
    return hits


def test_direct_path_reads_are_argued_for():
    """Uusi tiedosto ei paase lukemaan artefaktia polulla ilman perustelua."""
    hits = _scan_paths()
    uudet = {f: ls for f, ls in hits.items() if f not in PATH_ALLOWED}
    assert not uudet, (
        "Nama tiedostot avaavat data/fpl_xp_projections.json:n SUORAAN "
        "polulla, ohittaen load_xp_actionable()-lukijan. Kayta lukijaa tai "
        "lisaa tiedosto PATH_ALLOWED-listaan ja kirjoita MITEN se rajaa "
        "kierrokset:\n"
        + "\n".join(f"  {f}: rivit {ls}" for f, ls in sorted(uudet.items())))


def test_path_allowlist_has_no_dead_entries():
    hits = _scan_paths()
    kuolleet = [f for f in PATH_ALLOWED if f not in hits]
    assert not kuolleet, (
        "PATH_ALLOWED-listalla on tiedostoja jotka eivat enaa lue polkua "
        f"suoraan, poista ne: {kuolleet}")


def test_path_allowlist_reasons_name_the_bounding():
    """Perustelun on kerrottava MITEN kierrokset rajataan, ei vain etta
    tiedosto on tarkea. Rivi ilman rajauksen nimeamista ei ole perustelu."""
    rajaussanat = ("actionable_gameweek", "deadline_gameweek", "window_label",
                   "load_xp_actionable", "eksplisiittisesti", "meta",
                   "KIRJOITTAJA", "Lukija itse", "claim_scope",
                   "SKANNATTAVIEN", "0 osumaa", "MENNEEN")
    huonot = [f for f, syy in PATH_ALLOWED.items()
              if len(syy.split()) < 10 or not any(w in syy for w in rajaussanat)]
    assert not huonot, (
        "Perustelu ei nimea rajausta (miten tiedosto valitsee kierroksen tai "
        f"miksi rajausta ei tarvita): {huonot}")


def test_the_ast_scanner_ignores_documentation_mentions(tmp_path):
    """NEGATIIVINEN KONTROLLI. Ilman tata portti voisi olla vihrea siksi
    etta se laukeaa joka tiedostosta joka MAINITSEE artefaktin - jolloin
    poikkeuslista taytettaisiin merkityksettomilla riveilla."""
    vain_doc = tmp_path / "doc.py"
    vain_doc.write_text(
        '"""Datalahteet: data/fpl_xp_projections.json ja muuta."""\n'
        "# kommentti: data/fpl_xp_projections.json\n"
        "X = 1\n", encoding="utf-8")
    assert _string_literals(vain_doc) == []

    oikea = tmp_path / "koodi.py"
    oikea.write_text(
        '"""Docstring joka mainitsee data/fpl_xp_projections.json."""\n'
        'P = "data/fpl_xp_projections.json"\n', encoding="utf-8")
    assert _string_literals(oikea) == [2]
