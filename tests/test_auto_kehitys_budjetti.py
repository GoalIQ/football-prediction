"""0 euroa ja Max-kiintiö: Claude vain harkintaan (18.10.2026, Villen GO, automaatiokohta 6).

Max-tilauksen viikkoraja on yhteinen ylläpitäjän omien sessioiden kanssa, joten jokainen
automaattinen Claude-ajo vie samasta potista. Tämä portti tekee kolme sääntöä mekaanisiksi:

1. Claude ajetaan vain anthropics/claude-code-actionilla ja tilauksen OAuth-tokenilla. Mikään
   työnkulku ei viittaa maksulliseen avaimeen eikä asenna Anthropicin SDK:ta (oma valjas
   tilaustokenilla ei ole tuettu reitti, ja SDK + avain on maksullinen API).
2. Jokainen Claude-työnkulku on BUDJETTI-listalla perusteluineen, max-turns ei ylitä listaa, ja
   viikkoajojen summa pysyy katon alla. Uusi Claude-ajo ei pääse läpi unohtamalla budjettia.
3. Jokaisella Claude-askeleella on deterministinen ehto (`if:`): kone päättää ensin, onko harkittavaa.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

JUURI = Path(__file__).resolve().parent.parent
WF = JUURI / ".github" / "workflows"

# {työnkulku: (ajoja viikossa enintään, max-turns enintään, perustelu)}
BUDJETTI = {
    "auto-kehitys.yml": (3, 80, "ma/ke/pe yksi backlog-rivi; ei ajoa, kun 2 auto-PR:ää on auki"),
    "aallonharja.yml": (1, 90, "su benchmark ja mittareiden sulku; avoin aallonharja-PR estää ajon"),
    "bsky-bot.yml": (14, 60, "aivot vain should-think-päätöksellä, noin 2 kertaa vuorokaudessa"),
    "julkaisutarkistus.yml": (3, 30, "vain auto-PR, jonka julkinen teksti muuttuu (enintään auto-kehityksen "
                                     "3 PR:ää viikossa); ei tekstiä -> Claudea ei ajeta"),
}
VIIKKOKATTO = 25

MAKSULLISET = (
    re.compile(r"ANTHROPIC_API_KEY\s*:"), re.compile(r"secrets\.ANTHROPIC"), re.compile(r"anthropic_api_key\s*:"),
    re.compile(r"api\.anthropic\.com"), re.compile(r"pip install[^\n]*\banthropic\b"),
    re.compile(r"@anthropic-ai/(sdk|claude-agent-sdk)"), re.compile(r"claude[-_]agent[-_]sdk"),
)


def _tyonkulut():
    return sorted(WF.glob("*.yml"))


def _claude_askeleet(doc):
    for job in (doc.get("jobs") or {}).values():
        for s in job.get("steps") or []:
            if "claude-code-action" in str(s.get("uses", "")):
                yield s


@pytest.mark.parametrize("polku", _tyonkulut(), ids=lambda p: p.name)
def test_ei_maksullista_kielimallirajapintaa(polku):
    teksti = polku.read_text(encoding="utf-8")
    koodi = "\n".join(r for r in teksti.splitlines() if not r.lstrip().startswith("#"))
    for k in MAKSULLISET:
        assert not k.search(koodi), f"{polku.name}: {k.pattern}"


def test_jokainen_claude_tyonkulku_on_budjetissa():
    loydetyt = set()
    for polku in _tyonkulut():
        doc = yaml.safe_load(polku.read_text(encoding="utf-8"))
        askeleet = list(_claude_askeleet(doc))
        if not askeleet:
            continue
        loydetyt.add(polku.name)
        assert polku.name in BUDJETTI, f"{polku.name}: uusi Claude-työnkulku, lisää BUDJETTIin perustelu"
        _, turnit, _ = BUDJETTI[polku.name]
        for s in askeleet:
            w = s.get("with") or {}
            assert w.get("claude_code_oauth_token") == "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}", polku.name
            assert "anthropic_api_key" not in w
            m = re.search(r"--max-turns (\d+)", str(w.get("claude_args", "")))
            assert m and int(m.group(1)) <= turnit, f"{polku.name}: max-turns puuttuu tai yli budjetin"
            assert s.get("if"), f"{polku.name}: Claude-askeleella ei ole determinististä ehtoa"
    assert loydetyt == set(BUDJETTI), f"BUDJETTI-listalla on työnkulku ilman Claudea: {set(BUDJETTI) - loydetyt}"


def test_viikkokatto():
    assert sum(v[0] for v in BUDJETTI.values()) <= VIIKKOKATTO
    assert all(len(v[2]) > 20 for v in BUDJETTI.values()), "perustelu on pakollinen"
