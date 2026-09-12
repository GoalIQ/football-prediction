# -*- coding: utf-8 -*-
"""Portti: XpTablen 'Group by team' -nimirivi ulottuu koko taulukon levyiseksi.

MITATTU VIKA (12.9.2026). `XpTable.svelte`:n ryhmarivi kaytti
`colspan={7 + (hasPrice ? 1 : 0) + (hasStarts ? 1 : 0) + (hasOwned ? 1 : 0) + gwCols.length}`,
mutta <thead>:ssa on 11 kiinteaa saraketta (#, Player, Team, Pos, xMins,
xP/GW, 10+, Blank, Ceiling, xP/90, Total xP) ja lisaksi ehdollinen
`{#if sortWin}` -sarake jota lauseke ei laskenut lainkaan. Joukkueen nimirivi
loppui siis 4-5 saraketta ennen taulukon reunaa. Syy: sarakkeita lisattiin
otsikkoon (10+, Blank, Ceiling, xP/90, sortWin) eika kukaan muistanut
kasin kirjoitettua lukua toisessa kohdassa.

Suunnittelu (CLAUDE.md 6a): colspan lukee YHDEN johdetun arvon
(`columnCount`), ja tama portti johtaa saman luvun <thead>:n rakenteesta
(kiinteat <th>:t + jokainen {#if X} + jokainen {#each L}). Uusi sarake
otsikkoon ilman lausekkeen paivitysta kaataa testin ja kertoo mika puuttuu.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

FP = Path(__file__).resolve().parents[1]
COMPONENT = FP / "web" / "pro-spa" / "src" / "lib" / "components" / "XpTable.svelte"


def _src() -> str:
    return COMPONENT.read_text(encoding="utf-8")


def _script(src: str) -> str:
    m = re.search(r"<script\b[^>]*>(.*?)</script>", src, re.S)
    assert m, "XpTable: <script> puuttuu"
    return m.group(1)


def _markup(src: str) -> str:
    src = re.sub(r"<script\b.*?</script>", "", src, flags=re.S)
    src = re.sub(r"<style\b.*?</style>", "", src, flags=re.S)
    return re.sub(r"<!--.*?-->", "", src, flags=re.S)


def _group_table(markup: str) -> str:
    """Se <table> jossa ryhmarivi on."""
    for m in re.finditer(r"<table\b.*?</table>", markup, re.S):
        if 'class="group-row"' in m.group(0):
            return m.group(0)
    raise AssertionError("XpTable: taulukkoa jossa on group-row ei loydy")


def _header_model(table: str) -> tuple[int, Counter, Counter]:
    """(kiinteat <th>, {#if ehto} -> <th>-maara, {#each lista} -> lista)."""
    thead = re.search(r"<thead>(.*?)</thead>", table, re.S)
    assert thead, "XpTable: <thead> puuttuu"
    token = re.compile(r"\{#if\s+([^}]+?)\s*\}|\{/if\}|\{#each\s+([\w.]+)\s+as\b[^}]*\}|\{/each\}|<th\b")
    stack: list[tuple[str, str]] = []
    fixed = 0
    ifs: Counter = Counter()
    eaches: Counter = Counter()
    for m in token.finditer(thead.group(1)):
        t = m.group(0)
        if t.startswith("{#if"):
            stack.append(("if", m.group(1).strip()))
        elif t.startswith("{#each"):
            stack.append(("each", m.group(2).strip()))
        elif t in ("{/if}", "{/each}"):
            assert stack, f"XpTable <thead>: pariton {t}"
            stack.pop()
        else:
            if not stack:
                fixed += 1
            else:
                assert len(stack) == 1, f"XpTable <thead>: sisakkaisia lohkoja <th>:n ymparilla: {stack}"
                kind, expr = stack[0]
                (ifs if kind == "if" else eaches)[expr] += 1
    assert not stack, f"XpTable <thead>: sulkematon lohko {stack}"
    return fixed, ifs, eaches


def _colspan_expr(table: str) -> str:
    m = re.search(r'<tr class="group-row">\s*<td\s+colspan=\{(.*?)\}\s*>', table, re.S)
    assert m, "XpTable: ryhmarivin <td colspan={...}> ei loydy"
    return m.group(1).strip()


def _balanced_call(text: str, start: int) -> str:
    """Palauttaa sulkeiden sisallon alkaen kohdasta jossa text[start] == '('."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    raise AssertionError("pariton sulku")


def _resolve(expr: str, script: str, depth: int = 0) -> tuple[int, Counter, Counter]:
    """Lausekkeen summatermit: (vakio, {X: n} termeista `(X ? 1 : 0)`, {L: n} termeista `L.length`)."""
    assert depth < 5, "colspan-lausekkeen resoluutio ei paaty"
    const = 0
    flags: Counter = Counter()
    lists: Counter = Counter()
    expr = re.sub(r"\s+", " ", expr).strip()
    # Pilko ylimman tason '+' -merkeista.
    terms, buf, lvl = [], "", 0
    for ch in expr:
        if ch == "(":
            lvl += 1
        elif ch == ")":
            lvl -= 1
        if ch == "+" and lvl == 0:
            terms.append(buf.strip())
            buf = ""
        else:
            buf += ch
    terms.append(buf.strip())
    for t in terms:
        if re.fullmatch(r"\d+", t):
            const += int(t)
            continue
        m = re.fullmatch(r"\(\s*([\w.!]+)\s*\?\s*1\s*:\s*0\s*\)", t)
        if m:
            flags[m.group(1)] += 1
            continue
        m = re.fullmatch(r"([\w.]+)\.length", t)
        if m:
            lists[m.group(1)] += 1
            continue
        if re.fullmatch(r"\w+", t):
            dm = re.search(rf"\b(?:let|const)\s+{t}\s*=\s*\$derived\s*\(", script)
            if dm:
                inner = _balanced_call(script, dm.end() - 1)
                c2, f2, l2 = _resolve(inner, script, depth + 1)
                const += c2
                flags += f2
                lists += l2
                continue
            cm = re.search(rf"\bconst\s+{t}\s*=\s*(\d+)\s*;", script)
            if cm:
                const += int(cm.group(1))
                continue
        raise AssertionError(f"colspan-lausekkeen termia ei tunnisteta: {t!r}")
    return const, flags, lists


def test_group_row_colspan_matches_header_columns() -> None:
    src = _src()
    table = _group_table(_markup(src))
    fixed, ifs, eaches = _header_model(table)
    const, flags, lists = _resolve(_colspan_expr(table), _script(src))
    assert const == fixed, (
        f"ryhmarivin colspan laskee {const} kiinteaa saraketta, <thead>:ssa niita on {fixed}"
    )
    assert flags == ifs, (
        f"ryhmarivin colspanin ehdolliset sarakkeet {dict(flags)} eivat vastaa "
        f"<thead>:n {{#if}}-sarakkeita {dict(ifs)}"
    )
    assert lists == eaches, (
        f"ryhmarivin colspanin listasarakkeet {dict(lists)} eivat vastaa "
        f"<thead>:n {{#each}}-sarakkeita {dict(eaches)}"
    )


def test_group_row_colspan_reads_one_derived_value() -> None:
    src = _src()
    expr = _colspan_expr(_group_table(_markup(src)))
    assert re.fullmatch(r"[A-Za-z_]\w*", expr), (
        "ryhmarivin colspanin pitaa lukea yksi johdettu arvo (esim. {columnCount}), "
        f"ei kasin kirjoitettua laskutoimitusta: colspan={{{expr}}}"
    )
    assert re.search(rf"\b(?:let|const)\s+{expr}\s*=\s*\$derived\s*\(", _script(src)), (
        f"{expr} pitaa maaritella $derived-arvona, jotta se seuraa sarakelippuja"
    )
