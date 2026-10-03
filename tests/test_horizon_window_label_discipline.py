# -*- coding: utf-8 -*-
"""IKKUNAN NIMEAMINEN: kuka saa lukea `horizon_gw`:n — ja miksi.

🔴 MIKSI (18.9, adversariaalinen tarkistus haarasta XP-HORIZON-ALKANUT-
KIERROS): backend korjasi LUVUN (17.9: `xp_horizon_total` summaa vain
kierrokset joihin voi viela vaikuttaa) mutta ei LAPPUA. `meta.horizon_gw`
on yha GW-SARAKKEIDEN maara riveissa, ja rivit kantavat tarkoituksella myos
jo alkanutta kierrosta. Kesken kierroksen ne ovat eri luku: 6 saraketta,
5 kierrosta summassa. Jokainen pinta joka kirjoitti otsikkoon
`meta.horizon_gw ?? 6` sanoi siis "next 6 GWs" viiden kierroksen summalle —
TASAN se vaite jonka backend-korjaus poisti, nyt lapun puolella ja
ilmaispinnalla. Mitattu 18.9 tuotantoartefaktilla (synteettinen
deadline_gameweek = next_gameweek + 1): Haaland 31.97 (5 GW) otsikolla
"6 GWs", ja SPA:n XpTable naytti otsikon "GW5-GW10" summalle GW6-10.

KAKSI SAANTOA, MOLEMMAT KIRJOITETTU MITATULLE MUODOLLE:

  R1  KOODIRIVI joka LUKEE `horizon_gw`:n on argumentoitava. Yksi lukija
      hoitaa ikkunan: pythonissa `fpl_xp.horizon_sum_gw`, SPA:ssa
      `$lib/xpHorizon` (`xpHorizon(meta)`). Kommentit ja tyypit eivat ole
      lukuja; dictin AVAIN (`"horizon_gw": ...`) on kirjoittaja, ei lukija
      — sopimuksen kentta saa ja pitaa sailya.

  R2  RIVI jolla on SEKA horisonttisumma ETTA pituus (`.length`) tai
      `horizon_gw` on argumentoitava. Tama on se muoto joka mitattiin
      mobiilissa: ``${player.xp_horizon_total.toFixed(1)} xP projected over
      the next ${gws.length} gameweeks``.

POIKKEUS EI OLE TIEDOSTOKOHTAINEN VAAN RIVIKOHTAINEN. Tiedostotason
poikkeus olisi yhden muokkauksen paassa siita etta sama vika palaa samaan
tiedostoon vihrean portin alle (muisti: "portti kirjoitetaan nahdylle
muodolle"). Kun argumentoitu rivi muuttuu, portti kaatuu ja kirjoittaja
joutuu perustelemaan uudelleen.

MOBIILI EI OLE TASSA REPOSSA: goaliq-app:n vastaava portti on
`lib/xpHorizon.test.ts` (gate.yml ajaa `lib/*.test.ts` globilla). Mobiili
valitsi SAMAN lukijan kuin SPA (`lib/xpHorizon.ts`, haara
`feat/mobiili-yksi-ikkunalukija`), joten nimi on sama molemmissa
klienteissa eika kumpikaan peri havinneen haaran `horizonWindow`-nimea.

🔴 MIKSI TAMA PORTTI ON YHA OLEMASSA VAIKKA SPA:LLA ON OMA (18.9, SPA:n
haarojen purku): SPA:n lahdeportti on
`web/pro-spa/src/lib/xpHorizon.gate.test.ts`, joka on saannoiltaan
TIUKEMPI — se lukee vaitteen, ei kenttaa. Mutta se ajetaan vain
`pro-spa-deploy.yml`:ssa, ja se workflow on `workflow_dispatch`-only
(SPA-deploy on GO-portin takana). Portti joka ajetaan vasta
julkaisuhetkella ei estä vaaran tekstin mergeamista, ja mitattu 18.9:
`npm test` ei aja yhdessakaan push-triggeroidussa workflow'ssa. TAMA
portti ajaa `tests.yml`:ssa joka pushilla. Kaksi saantoa, sama muoto:
R2 tassa vastaa vitest-portin saantoa E, ja kumpikin kaataa mitatun
muodon (summa + rivilistan pituus samalla rivilla).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src"

SUM_KEYS = ("xp_horizon_total", "team_xp_horizon", "xi_xp_horizon",
            "margin_xp_horizon", "optimal_xp_horizon", "xp_horizon")
SUM_RE = re.compile("|".join(SUM_KEYS))
# `horizon_gw` tasan — ei `horizon_gws`, `near_horizon_gw`,
# `transfer_horizon_gw` eika `horizon_total_gw`.
HG_RE = re.compile(r"(?<![A-Za-z_])horizon_gw(?![A-Za-z_s])")
LEN_RE = re.compile(r"\.length\b")
LABEL_RE = re.compile(r"GWs|gameweeks|GW horizon|gameweek horizon")
# RIVI JOKA ASETTAA KENTAN = kirjoittaja, ei ikkunan nimeaja. Sopimuksen
# kentta saa ja pitaa sailya vastauksissa, eika `"horizon_gw": <mika
# tahansa>` voi kirjoittaa otsikkoon vaaraa lukua.
WRITER_RE = re.compile(r"""^\s*["']?horizon_gw["']?\??\s*:""")
# tyyppimaarittely (.ts/.svelte): `horizon_gw?: number | null;`
TYPE_RE = re.compile(r"^\s*(?:readonly\s+)?horizon_gw\??\s*:\s*[A-Za-z(]")


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _code_lines(p: Path) -> list[str]:
    """Tiedoston rivit ILMAN kommentteja ja docstringeja.

    🔴 EI "rivi alkaa kommenttimerkilla" -heuristiikkaa: docstringin ja
    JSDocin JATKORIVIT eivat ala sellaisella, ja juuri ne saivat taman
    portin ensimmaisen version huutamaan omista perusteluteksteistaan
    (18.9). Portti joka huutaa vaarasta syysta opitaan ohittamaan."""
    src = p.read_text(encoding="utf-8", errors="replace")
    lines = src.splitlines()
    if p.suffix == ".py":
        import ast as _ast
        try:
            tree = _ast.parse(src)
        except SyntaxError:
            return lines
        skip: set[int] = set()
        for n in _ast.walk(tree):
            if (isinstance(n, _ast.Expr) and isinstance(n.value, _ast.Constant)
                    and isinstance(n.value.value, str)):
                skip.update(range(n.lineno, (n.end_lineno or n.lineno) + 1))
        return [ln.split("#", 1)[0] for i, ln in enumerate(lines, 1)
                if i not in skip]
    # .ts / .svelte / .js: lohko- ja HTML-kommentit tilakoneella
    out: list[str] = []
    in_block = in_html = False
    for line in lines:
        rest, kept = line, ""
        while rest:
            if in_block:
                i = rest.find("*/")
                rest, in_block = ("", True) if i < 0 else (rest[i + 2:], False)
            elif in_html:
                i = rest.find("-->")
                rest, in_html = ("", True) if i < 0 else (rest[i + 3:], False)
            else:
                cands = [(i, k) for i, k in ((rest.find("//"), "line"),
                                             (rest.find("/*"), "blk"),
                                             (rest.find("<!--"), "html"))
                         if i >= 0]
                if not cands:
                    kept, rest = kept + rest, ""
                    break
                i, kind = min(cands)
                kept += rest[:i]
                if kind == "line":
                    rest = ""
                elif kind == "blk":
                    rest, in_block = rest[i + 2:], True
                else:
                    rest, in_html = rest[i + 4:], True
        out.append(kept)
    return out


# --------------------------------------------------------------------------
# R1: argumentoidut `horizon_gw`-luvut. Avain: "polku:rivin teksti".
# --------------------------------------------------------------------------
ALLOWED_READS: dict[str, str] = {
    'src/models/fpl_xp.py::n = m.get("horizon_gw")':
        "YKSI LUKIJA (`horizon_sum_gw`): tama ON se paikka jossa "
        "`horizon_gw` luetaan, ja vain viimeisena fallbackina kun "
        "`horizon_total_gw`:ta eika kierroslistaa ole.",
    'scripts/build_fpl_page.py::_window = window_label(_meta, _gws, _meta.get("horizon_gw") or 6)':
        "`window_label` johtaa ikkunan TODELLISISTA kierroksista ja rajaa "
        "ne `actionable_gameweeks`illa; kolmas argumentti on fallback-teksti "
        "vain silloin kun kierroslista on tyhja, eli silloin kun mitaan "
        "summaa ei ole naytettavaksi.",
    'src/models/fpl_planner.py::horizon = xp_data["meta"].get("horizon_gw")':
        "Menee `_no_xp_reason`iin: SYY miksi pelaaja ei ole projektiossa. "
        "Kynnys (`MIN_XP_TOTAL`) mitataan putkessa KOKO horisontin summasta "
        "(build_fpl_xp.py), joten `horizon_total_gw` nimeaisi eri ikkunan "
        "kuin se joka pelaajan pudotti.",
    'src/models/fpl_planner.py::xp_data["meta"].get("horizon_gw"),':
        "Sama `_no_xp_reason` kuin ylla (replacements-vastauksen teksti).",
    'src/models/fpl_fit.py::horizon_cols = int(xp_data["meta"].get("horizon_gw") or 6)':
        "Kirjoitetaan sopimuksen `meta.horizon_gw`-kenttaan sellaisenaan; "
        "lauseen ikkuna tulee `horizon_sum_gw`ista rivia aiemmin.",
    'src/models/fpl_rate_team.py::cap=int(xp_data["meta"].get("horizon_gw") or 6))':
        "Kattaa siirtoikkunan pituuden RIVIEN maaraan, ei nimea mitaan "
        "otsikkoon: tulos on `transfer_horizon_gw`, joka nimetaan itse.",
    'src/models/fpl_rate_team.py::len(_t_gws) or int(xp_data["meta"].get("horizon_gw") or 6), ft,':
        "Sama siirtoikkunan pituus kuin ylla (fallback kun `_t_gws` on tyhja).",
    'web/pro-spa/src/lib/xpHorizon.ts::const rows = gwInt(m.horizon_gw);':
        "YKSI LUKIJA (SPA, `$lib/xpHorizon`): tama ON se paikka jossa "
        "`horizon_gw` luetaan. Se menee kenttaan `rows` (= sarakkeiden "
        "maara) EIKA kenttaan `count` (= summan pituus), eika lukija "
        "keksi `?? 6` -oletusta: kun `horizon_total_gw` puuttuu, "
        "`actionableOnly` on false eika yksikaan teksti sano \"next\".",
    'api/main.py::"meta": {**meta, "horizon_gw": max(0, span_actual)},':
        "KIRJOITTAJA (/api/fantasy, phase0-ottelulista): laskee montako "
        "kierrosta TASSA vastauksessa on ja kirjoittaa sen kenttaan. Ei "
        "xP-summaa koko reitilla (EXEMPT test_xp_horizon_total_meta_routes:ssa), "
        "joten se ei voi nimeta yhtaan horisonttisummaa.",
}

# --------------------------------------------------------------------------
# R2: argumentoidut rivit joilla summa ja pituus ovat samalla rivilla.
# --------------------------------------------------------------------------
ALLOWED_SUM_AND_LENGTH: dict[str, str] = {}


def _py_label_files() -> list[Path]:
    """Python-tiedostot jotka SEKA kasittelevat horisonttisummaa ETTA
    kirjoittavat ikkunatekstia. Lista LASKETAAN, ei yllapideta kasin:
    kasinlista vanhenee hiljaa (muisti: kuratoitu lista)."""
    out = []
    for d in ("scripts", "src", "api"):
        for p in sorted((ROOT / d).rglob("*.py")):
            t = p.read_text(encoding="utf-8", errors="replace")
            if SUM_RE.search(t) and LABEL_RE.search(t):
                out.append(p)
    return out


def _spa_files() -> list[Path]:
    """SPA:n PINNAT. `*.test.ts` on rajattu pois — ja vain se.

    🔴 MIKSI (18.9): vitest-portin oma negatiivinen kontrolli on
    `xpHorizon.gate.test.ts`, jonka fikstuurit SISALTAVAT tarkoituksella
    juuri ne muodot joita tama portti jahtaa (`data.meta.horizon_gw ?? 6`,
    `xp_horizon_total ... gameweeks.length`). Ilman rajausta tama portti
    huutaisi toisen portin todistusaineistosta, ja portti joka huutaa
    vaarasta syysta opitaan ohittamaan (sama opetus kuin `_code_lines`in
    docstringissa). Rajaus on TIEDOSTOPAATTEELLE, ei tiedostonimelle:
    uusi pinta ei voi luiskahtaa ulos skannauksesta nimeamalla itsensa
    poikkeuksen nakoiseksi. `test_the_exclusion_does_not_blind_the_gate`
    todistaa, etta pinta-tiedostossa sama muoto jaa yha kiinni."""
    return sorted([p for p in SPA.rglob("*")
                   if p.suffix in (".ts", ".svelte", ".js")
                   and not p.name.endswith(".test.ts")])


def _breaks(line: str, rule: str) -> bool:
    if TYPE_RE.match(line):
        return False
    if rule == "read":
        return bool(HG_RE.search(line)) and not WRITER_RE.match(line)
    return bool(SUM_RE.search(line)
                and (LEN_RE.search(line) or HG_RE.search(line)))


def _scan(paths, rule) -> list[tuple[str, str]]:
    """[(avain, rivi)] jokaisesta KOODIrivista joka rikkoo saannon."""
    hits = []
    for p in paths:
        rel = _rel(p)
        for line in _code_lines(p):
            if _breaks(line, rule):
                hits.append((f"{rel}::{line.strip()}", line.strip()))
    return hits


def test_python_label_surfaces_read_the_window_from_one_reader():
    hits = _scan(_py_label_files(), "read")
    assert hits, "skanneri ei loytanyt yhtaan horizon_gw-lukua - regex rikki?"
    missing = [k for k, _ in hits if k not in ALLOWED_READS]
    assert not missing, (
        "horizon_gw luetaan ilman perustelua:\n  " + "\n  ".join(missing)
        + "\n\nIkkunan pituus tulee `fpl_xp.horizon_sum_gw`ista. Jos tama "
        "rivi EI nimea horisonttisummaa, lisaa se ALLOWED_READS-listalle "
        "perusteluineen.")


def test_spa_surfaces_read_the_window_from_one_reader():
    hits = _scan(_spa_files(), "read")
    assert hits, "skanneri ei loytanyt yhtaan horizon_gw-lukua SPA:sta"
    missing = [k for k, _ in hits if k not in ALLOWED_READS]
    assert not missing, (
        "SPA lukee horizon_gw:n ilman perustelua:\n  " + "\n  ".join(missing)
        + "\n\nIkkuna tulee `$lib/xpHorizon`ista (xpHorizon(meta)). Jos "
        "rivi ei nimea horisonttisummaa, lisaa se "
        "ALLOWED_READS-listalle perusteluineen.")


def test_no_surface_names_the_window_from_a_row_count_next_to_the_sum():
    """R2: mitattu muoto mobiilista — summa ja `gws.length` samalla rivilla."""
    hits = _scan(_py_label_files() + _spa_files(), "sumlen")
    missing = [k for k, _ in hits if k not in ALLOWED_SUM_AND_LENGTH]
    assert not missing, (
        "horisonttisumma nimetaan rivien maaralla:\n  " + "\n  ".join(missing))


def test_allowed_entries_have_a_real_reason_and_still_exist():
    """Poikkeus vanhenee: jos rivi on poistunut, perustelu poistuu mukana —
    muuten lista kasvaa perusteluilla jotka eivat vartioi mitaan."""
    for k, why in {**ALLOWED_READS, **ALLOWED_SUM_AND_LENGTH}.items():
        assert why and len(why) > 40, k
    keys = {k for k, _ in _scan(_py_label_files() + _spa_files(), "read")}
    keys |= {k for k, _ in _scan(_py_label_files() + _spa_files(), "sumlen")}
    stale = [k for k in {**ALLOWED_READS, **ALLOWED_SUM_AND_LENGTH} if k not in keys]
    assert not stale, f"poikkeus jonka riviä ei enaa ole: {stale}"


@pytest.mark.parametrize("line,is_read", [
    ('	let horizonN = $derived(data.meta.horizon_gw ?? gwCols.length ?? 6);', True),
    ('	horizon = int(xp_data["meta"].get("horizon_gw") or 6)', True),
    ('            "horizon_gw": HORIZON_GW,', False),        # kirjoittaja
    ('	horizon_gw?: number | null;', False),                 # tyyppi
    ('    "horizon_gws": [1, 2],', False),                    # eri avain
    ('	let n = data.meta.near_horizon_gw ?? 6;', False),      # eri avain
    ('	let n = data.meta.horizon_total_gw ?? 6;', False),     # uusi avain
])
def test_the_scanner_tells_a_read_from_a_write(line, is_read):
    """EXIT-KOODI EI OLE TODISTE: ilman tata portti voisi olla vihrea siksi
    ettei se tunnista lukua lainkaan."""
    assert _breaks(line, "read") is is_read, line


def test_code_lines_strips_comments_and_docstrings(tmp_path):
    """Skannerin toinen puoli: perustelutekstit EIVAT ole lukuja, mutta
    koodi kommentin jalkeen samalla rivilla ON. Ilman tata portti joko
    huutaa omista docstringeistaan tai (pahempi) menettaa koodirivin joka
    on lohkokommentin perassa."""
    py = tmp_path / "a.py"
    py.write_text('"""doc: meta.horizon_gw on sarakkeiden maara"""\n'
                  '# horizon_gw kommentissa\n'
                  'n = m.get("horizon_gw")  # luku\n', encoding="utf-8")
    got = [ln for ln in _code_lines(py) if _breaks(ln, "read")]
    assert got == ['n = m.get("horizon_gw")  '], got

    ts = tmp_path / "b.svelte"
    ts.write_text("/**\n * `meta.horizon_gw` on sarakkeiden maara\n */\n"
                  "// horizon_gw kommentissa\n"
                  "<!-- horizon_gw HTML-kommentissa -->\n"
                  "let n = data.meta.horizon_gw ?? 6;\n"
                  "/* auki */ let k = meta.horizon_gw;\n", encoding="utf-8")
    got = [ln.strip() for ln in _code_lines(ts) if _breaks(ln, "read")]
    assert got == ["let n = data.meta.horizon_gw ?? 6;",
                   "let k = meta.horizon_gw;"], got


# --------------------------------------------------------------------------
# 18.9 (SPA:n haarojen purku): erotteleva fikstuuri KAHDESTA MITATUSTA
# muodosta jotka SPA:n oma vitest-portti paastaa lapi.
# --------------------------------------------------------------------------
# Mitattu 18.9 istuttamalla muoto oikeaan tiedostoon ja ajamalla
# `npx vitest run` (62/62 VIHREA molemmilla). Syy: vitest-portin saanto A
# (`claimProblems`) laukeaa vain kun rivilla on tunnistettu vaitemerkki
# ("Total xP", "xP projected", "Sum of expected points", "next ${"). Sana
# joka ei ole listalla ("pts across", "rounds ahead") vie saman vaitteen
# portin ohi. R2 ei kysy sanoja vaan MUOTOA: summa ja rivilistan pituus
# samalla rivilla. Siksi kumpikin saanto tarvitaan.
MUTATIONS_THE_VITEST_GATE_PASSES = [
    # MUT-1: jakokortin/pelaajakortin sivulause, ei vaitemerkkia
    '\tconst blurb = `${(player.xp_horizon_total ?? 0).toFixed(1)} pts '
    'across ${(player.gameweeks ?? []).length} GWs`;',
    # MUT-2: johdettu summa-avain (RateTeam), ei vaitemerkkia
    '\tconst teamBlurb = `${(data?.team_xp_horizon ?? 0).toFixed(1)} pts, '
    '${(gwCols ?? []).length} rounds ahead`;',
]


@pytest.mark.parametrize("line", MUTATIONS_THE_VITEST_GATE_PASSES)
def test_r2_catches_what_the_vitest_claim_rule_lets_through(line):
    """EROTTELEVA FIKSTUURI: vaara haara oikeasti onnistuisi ilman tata.

    Jos R2 poistetaan tai sen regex loystyy, nama kaksi riviä paasevat
    julkaisuun — ne ovat SPA:n oman portin mittaamia aukkoja, eivat
    keksittyja. Kumpikin sanoo actionable-summan pituudeksi RIVIEN maaran,
    joka kesken kierroksen on yksi liikaa."""
    assert _breaks(line, "sumlen") is True, line
    # ...ja sama rivi ilman rivilistan pituutta EI laukaise: portti ei
    # kiellä summan nayttamista, vain sen nimeamista sarakkeilla.
    clean = line.split("${(")[0] + "`;"
    assert _breaks(clean, "sumlen") is False, clean


def test_the_exclusion_does_not_blind_the_gate(tmp_path, monkeypatch):
    """`*.test.ts` on rajattu skannauksesta — todista ettei rajaus vuoda.

    EXIT-KOODI EI OLE TODISTE: ilman tata `_spa_files` voisi palauttaa
    tyhjan listan ja koko SPA-puoli olisi vihrea tyhjyyttaan."""
    surface = tmp_path / "Surface.svelte"
    surface.write_text(MUTATIONS_THE_VITEST_GATE_PASSES[0] + "\n", encoding="utf-8")
    fixture = tmp_path / "Surface.test.ts"
    fixture.write_text(MUTATIONS_THE_VITEST_GATE_PASSES[0] + "\n", encoding="utf-8")
    import sys
    monkeypatch.setattr(sys.modules[__name__], "SPA", tmp_path)
    files = _spa_files()
    assert surface in files, "pinta katosi skannauksesta"
    assert fixture not in files, "testifikstuuri on yha skannauksessa"
    # ...ja pinnan rivi laukaisee yha R2:n (rajaus ei sokaissut skanneria).
    hits = [ln for ln in _code_lines(surface) if _breaks(ln, "sumlen")]
    assert hits, "rajaus sokaisi portin: pinnan rivi ei enaa laukaise R2:ta"


def test_the_spa_source_gate_still_exists_and_is_the_one_we_defer_to():
    """R1:n SPA-puoli nojaa siihen etta `$lib/xpHorizon` on ainoa lukija.

    Jos vitest-portti poistetaan, tama portti jaisi ainoaksi — ja se on
    saannoiltaan loysempi (kentta, ei vaite). Silloin sen poisto pitaa
    nakya diffissa TAALLA, ei hiljaa toisessa kansiossa."""
    gate = ROOT / "web" / "pro-spa" / "src" / "lib" / "xpHorizon.gate.test.ts"
    assert gate.exists(), (
        "SPA:n lahdeportti on poistettu. Se vartioi VAITTEEN muotoa "
        "(kutsupaikkakate, jakokortit); tama portti vartioi kentan "
        "lukemista. Ala poista toista ilman etta korvaat sen katteen.")
    reader = ROOT / "web" / "pro-spa" / "src" / "lib" / "xpHorizon.ts"
    assert reader.exists(), "SPA:n yksi lukija on poistettu"
    txt = gate.read_text(encoding="utf-8", errors="replace")
    assert "lib/xpHorizon.ts" in txt, "vitest-portti ei enaa nimea lukijaa"
