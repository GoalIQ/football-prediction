"""Tier-vaitteiden skanneri. Yksi lukija myos portille.

MIKSI OMA MODUULI. Kierroksen 1 portti eli yhdessa testitiedostossa ja
skannasi RIVEJA. Adversariaalinen kumoaja mittasi siita kaksi lapimenoa:
sama vaite kolmelle riville katkaistuna (11 passed, portti vihrea) ja sama
vaite tiedostossa joka importtaa lukijan (25 passed, portti vihrea).
Molemmat olivat samaa luokkaa: portti vartioi NAHTYA MUOTOILUA eika
vaitetta (muisti `portti-kirjoitetaan-nahdylle-muodolle`). Skannaus on nyt
erillaan porteista, jotta sama koodi ajetaan seka oikeaa puuta vasten etta
synteettisia fikstuureja vasten — ja fikstuurit ovat tasan ne muodot jotka
menivat lapi.

KOLME ASIAA JOTKA TEKEVAT VAITTEESTA LOYDETTAVAN:

1. **Normalisointi.** `rate-my-team`, `Rate my team`, `rate_my_team` ja
   `RateMyTeam` ovat sama nimi. Kierroksen 1 fraasilista tunsi vain
   valilyontimuodon, ja `Rate-my-team` viivoilla meni ohi.
2. **Liittaminen.** Vaite luetaan siita tekstista joka paatyy ULOS
   VIEREKKAIN, ei lahdekoodin rivityksesta. Implisiittinen konkatenaatio,
   `+`-ketju, f-string ja `" ".join(...)` litistetaan; moduulitason
   merkkijonovakiot sijoitetaan sisaan, jotta nimi yhdessa vakiossa ja
   tier-sana toisaalla loytyvat samasta vaitteesta.
3. **Lukijan kutsu on ainoa vapautus.** `tier_sentence(...)`-kutsun
   lahdealue nollataan ennen skannausta: sen argumentit ovat SLUGEJA, ja
   lukija kaataa ajon tuntemattomasta slugista. Tiedostotasoista vapautusta
   EI ole — import ei vapauta mitaan.
"""
from __future__ import annotations

import ast
import re

# Lukijan lausefunktiot. Naiden tuottama teksti on rekisterista johdettua,
# eika niiden argumentti (slug-lista) ole vaite. Muut lukijan funktiot EIVAT
# ole listalla: `phrase()` palauttaa pelkan nimen, joten rivi joka kirjoittaa
# tier-sanan sen viereen kirjoittaa sen itse ja kuuluu jaada kiinni.
READER_FUNCS = frozenset({"tier_sentence", "free_sentence", "premium_sentence"})

# Ikkunan korkeus riveina. Liittaminen hoitaa pitkat ketjut; ikkuna on sita
# varten etta myos proosa (docstring, kommenttilohko) luetaan lauseina eika
# riveina.
WINDOW = 3

# Litistetyn yksikon yllaraja. Ilman tata koko sivupohja olisi yksi yksikko,
# jolloin mika tahansa tyokalun nimi osuisi mihin tahansa tier-sanaan samalla
# sivulla. 800 merkkia on pitka kappale, ei sivu.
MAX_UNIT = 800


def norm(text: str) -> str:
    """Vertailumuoto: camelCase auki, valimerkit pois, yksi valilyonti.

    Reunoille jaa valilyonti, jotta hakusanan voi ankkuroida sanarajaan
    ilman erillista regexia.
    """
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"[^0-9A-Za-z]+", " ", text.lower())
    return " " + " ".join(text.split()) + " "


# Sanat jotka tekevat tekstista TIER-vaitteen. Suomi on mukana koska 18.9
# loydetyn vian perustelu oli suomenkielisessa docstringissa ("pysyvat
# premiumina"), eika englanninkielinen lista olisi nahnyt sita.
TIER_RE = re.compile(
    # 🔴 Hakusanat kirjoitetaan NORMALISOITUUN muotoon. `GoalIQ` on
    # camelCasea, joten normalisoituna se on "goal iq" — ensimmainen
    # versio etsi "goaliq premium" eika se osunut koskaan mihinkaan.
    r"goal iq premium|part of premium|is free|are free|free as well"
    r"|needs no account|need no account|tier free|tier premium"
    r"|is premium|are premium|premium only"
    r"|premiumi[a-z]*|pysyv[a-z]* premium|maksullis[a-z]*|maksullin[a-z]*"
    r"|ilmainen|ilmaisia|ilmaise[a-z]*"
)


# --------------------------------------------------------------------------
# Lahteen esikasittely
# --------------------------------------------------------------------------


def _reader_call_spans(tree: ast.AST) -> list[tuple[int, int, int, int]]:
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in READER_FUNCS and node.end_lineno is not None:
            spans.append(
                (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)
            )
    return spans


def blank_reader_calls(text: str, tree: ast.AST) -> str:
    """Lukijan kutsut pois lahteesta ennen skannausta.

    Rivinumerot sailyvat (teksti korvataan valilyonneilla), jotta osuman
    paikka viittaa yha oikeaan riviin.
    """
    lines = text.split("\n")
    for (l1, c1, l2, c2) in _reader_call_spans(tree):
        for ln in range(l1, l2 + 1):
            i = ln - 1
            if i >= len(lines):
                break
            row = lines[i]
            a = c1 if ln == l1 else 0
            b = c2 if ln == l2 else len(row)
            a, b = min(a, len(row)), min(b, len(row))
            if a < b:
                lines[i] = row[:a] + " " * (b - a) + row[b:]
    return "\n".join(lines)


def module_consts(tree: ast.AST) -> dict[str, str]:
    """Moduulitason merkkijonovakiot.

    Nama ovat se reitti jolla vaite koostuu KAHDESTA PAIKASTA: nimi on
    vakiossa, tier-sana lauseessa joka viittaa vakioon. Ilman sijoitusta
    kumpikaan puolisko ei yksin nayta vaitteelta.
    """
    out: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None or len(targets) != 1:
                continue
            if not isinstance(targets[0], ast.Name):
                continue
            flat = flatten(value, {})
            if flat.strip():
                out[targets[0].id] = flat
    return out


def flatten(node: ast.AST, consts: dict[str, str], depth: int = 0) -> str:
    """Solmun tuottama TEKSTI siina jarjestyksessa kuin se paatyy ulos."""
    if depth > 8:
        return " "
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else " "
    if isinstance(node, ast.JoinedStr):
        return "".join(flatten(v, consts, depth + 1) for v in node.values)
    if isinstance(node, ast.FormattedValue):
        return flatten(node.value, consts, depth + 1)
    if isinstance(node, ast.Name):
        return consts.get(node.id, " ")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (
            flatten(node.left, consts, depth + 1)
            + flatten(node.right, consts, depth + 1)
        )
    if isinstance(node, ast.IfExp):
        return (
            flatten(node.body, consts, depth + 1)
            + " "
            + flatten(node.orelse, consts, depth + 1)
        )
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return " ".join(flatten(e, consts, depth + 1) for e in node.elts)
    if isinstance(node, ast.Dict):
        return " ".join(
            flatten(k, consts, depth + 1) + " " + flatten(v, consts, depth + 1)
            for k, v in zip(node.keys, node.values)
            if k is not None
        )
    if isinstance(node, ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in READER_FUNCS:
            # Rekisterista johdettu teksti; argumentit ovat slugeja.
            return " "
        if name == "join" and isinstance(func, ast.Attribute):
            sep = flatten(func.value, consts, depth + 1)
            parts = []
            for arg in node.args:
                if isinstance(arg, (ast.List, ast.Tuple, ast.Set)):
                    parts += [flatten(e, consts, depth + 1) for e in arg.elts]
                elif isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
                    parts.append(flatten(arg.elt, consts, depth + 1))
                else:
                    parts.append(flatten(arg, consts, depth + 1))
            return sep.join(parts)
        return " "
    return " "


_UNIT_NODES = (ast.BinOp, ast.JoinedStr, ast.Call, ast.List, ast.Tuple, ast.Dict)


def units(text: str) -> list[tuple[int, str]]:
    """(rivinumero, normalisoitu teksti) jokaiselle skannattavalle yksikolle."""
    try:
        tree: ast.AST | None = ast.parse(text)
    except SyntaxError:
        tree = None

    consts: dict[str, str] = {}
    scanned = text
    if tree is not None:
        scanned = blank_reader_calls(text, tree)
        consts = module_consts(tree)

    out: list[tuple[int, str]] = []
    lines = scanned.split("\n")
    sub = None
    if consts:
        sub = re.compile(r"\b(" + "|".join(map(re.escape, sorted(consts))) + r")\b")
    for i in range(len(lines)):
        window = "\n".join(lines[i : i + WINDOW])
        if sub is not None:
            window = sub.sub(lambda m: consts[m.group(1)], window)
        out.append((i + 1, norm(window)))

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, _UNIT_NODES) or (
                isinstance(node, ast.Constant) and isinstance(node.value, str)
            ):
                flat = flatten(node, consts)
                if 8 < len(flat.strip()) <= MAX_UNIT:
                    out.append((getattr(node, "lineno", 0), norm(flat)))
    return out


# --------------------------------------------------------------------------
# Vaitteiden poiminta
# --------------------------------------------------------------------------


class Vaite:
    """Yksi loydetty tier-vaite: mista, milta rivilta, mika teksti."""

    def __init__(self, path: str, line: int, text: str, names: tuple[str, ...]) -> None:
        self.path = path
        self.line = line
        self.text = text
        self.names = names

    def __repr__(self) -> str:
        return f"{self.path}:{self.line} {list(self.names)} :: {self.text[:200]!r}"


def tool_phrases(reader) -> list[str]:
    """Erottelevat tyokalunimet REKISTERISTA.

    Nimet tulevat `titles()`ista eivatka `phrase()`ista: nimi on rekisterin
    fakta, `phrase()` on julkaistavaa copya jota ei ole jokaiselle slugille
    (src/tool_tiers.py `_COPY`). Slug otetaan mukaan nimen rinnalle, koska
    normalisoituna `rate-my-team` ja `Rate my team` ovat sama merkkijono ja
    osa slugeista eroaa otsikosta. Yksisanaiset nimet ("Value", "Table")
    osuisivat tuhansiin riveihin joilla ei ole tekemista tierin kanssa;
    "watchlist" on mukana erikseen, koska se oli toinen 18.9 vaarin
    luokitelluista.
    """
    names = []
    for slug, title in reader.titles().items():
        for candidate in (title, slug):
            n = norm(candidate).strip()
            if len(n.split()) > 1:
                names.append(n)
    names.append("watchlist")
    return sorted(set(names))


def claims(path: str, text: str, phrases: list[str]) -> list[Vaite]:
    """Tiedoston tier-vaitteet, yksi per rivi (pisin yksikko voittaa)."""
    seen: dict[int, Vaite] = {}
    for line, unit in units(text):
        if not TIER_RE.search(unit):
            continue
        hit = tuple(p for p in phrases if p in unit)
        if not hit:
            continue
        prev = seen.get(line)
        if prev is None or len(unit) > len(prev.text):
            seen[line] = Vaite(path, line, unit, hit)
    return [seen[k] for k in sorted(seen)]
