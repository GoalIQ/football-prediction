"""Portti: DefCon-rivin tarina on tosi JOKAISESSA ottelun vaiheessa.

MITATTU VIKA (4.9.2026, kilpailija-UI-auditointi). DefCon-lista oli 13 rivia
muodossa `Tavernier BOU · MID · 90'  11/12` — numeroseina jossa lukijan piti
paatella itse mita luku tarkoittaa. Sama luku tarkoittaa kahta vastakkaista
asiaa: "11/12 ja peli kesken" on kannustava, "11/12 ja peli ohi" on menetetty
piste. Payloadissa ei ollut ottelun tilaa lainkaan, joten kayttoliittyma EI
OLISI VOINUT kertoa eroa vaikka olisi halunnut.

Tama portti toteuttaa saannon 6a kohdan 3: invariantti mitataan **joka
vaiheessa**, ei siina vaiheessa jossa se sattuu pitamaan. Testi ajaa saman
funktion synteettisilla vaiheilla (ennen ottelua, kesken, lopussa) eika nojaa
siihen mika kauden vaihe nyt on.

Haarojen laukeamisosuudet on mitattu ENNEN copyn kirjoittamista
(`scripts/measure_defcon_rows.py`, 8 077 pelaaja-GW-rivia 2025/26):
lopputila osui 13,9 % · jai <= 2 vajaaksi 9,6 % · jai kauemmas 76,5 %;
kesken ottelun (75', lineaarinen arvio) <= 2 puuttuu 15,3 %. Jokainen haara
siis laukeaa oikeasti (muisti: syyn-haara-joka-ei-laukea-on-copyn-lupaus).
"""
from __future__ import annotations

import pytest

from src.models.fpl_defcon_live import defcon_story

THR = 12

# (nimi, dc, hit, match_state, odotettu tag)
PHASES = [
    ("ennen ottelua", 0, False, "upcoming", "NOT STARTED"),
    ("kesken, kaukana", 4, False, "live", "BUILDING"),
    ("kesken, lahella", 10, False, "live", "CLOSE"),
    ("kesken, osunut", 12, True, "live", "SCORED"),
    ("paattynyt, niukasti vajaa", 11, False, "finished", "JUST SHORT"),
    ("paattynyt, kaukana", 5, False, "finished", "SHORT"),
    ("paattynyt, osunut", 14, True, "finished", "SCORED"),
    ("tila tuntematon", 7, False, None, None),
]

# Sanat jotka VAATIVAT etta ottelu on kesken / ohi.
_LIVE_WORDS = ("still on", "away with")
_FINISHED_WORDS = ("finished",)


def _story(dc: int, hit: bool, state: str | None) -> dict:
    s = defcon_story(dc, THR, hit, state)
    assert s is not None
    return s


# --------------------------------------------------------------------------
# Tarkistimet (negatiiviset kontrollit ajavat naita muokatuilla arvoilla)
# --------------------------------------------------------------------------


def _tense_problem(story: dict, state: str | None) -> str | None:
    line = story["line"].lower()
    if state == "finished" and any(w in line for w in _LIVE_WORDS):
        return f"paattynyt ottelu vaittaa olevansa kesken: {story['line']!r}"
    if state == "live" and any(w in line for w in _FINISHED_WORDS):
        return f"kesken oleva ottelu vaittaa paattyneensa: {story['line']!r}"
    if state is None and (
        any(w in line for w in _LIVE_WORDS) or any(w in line for w in _FINISHED_WORDS)
    ):
        return f"tuntematon tila vaittaa aikamuodon: {story['line']!r}"
    return None


def _shape_problem(story: dict) -> str | None:
    """Rivin on oltava kategoria + lause. Pelkka lause on taas numeroseina."""
    if "tag" not in story:
        return "kategoria puuttuu kokonaan"
    if not story.get("line"):
        return "lause puuttuu"
    return None


def _number_problem(story: dict, dc: int, threshold: int) -> str | None:
    """Lause ja luku samasta lahteesta: rivin oma luku on lauseessa."""
    line = story["line"]
    if "kicked off" in line:
        return None  # ei numeroa, eika saa ollakaan
    remaining = str(max(0, threshold - dc))
    if str(threshold) not in line:
        return f"kynnys {threshold} puuttuu lauseesta {line!r}"
    if str(dc) not in line and remaining not in line:
        return f"rivin oma luku ({dc}/{remaining}) puuttuu lauseesta {line!r}"
    return None


# --------------------------------------------------------------------------
# Vaitteet
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nimi,dc,hit,state,odotettu", PHASES)
def test_jokainen_vaihe_antaa_oikean_kategorian(
    nimi: str, dc: int, hit: bool, state: str | None, odotettu: str | None
) -> None:
    story = _story(dc, hit, state)
    assert story["tag"] == odotettu, f"{nimi}: sai {story['tag']!r}"


@pytest.mark.parametrize("nimi,dc,hit,state,odotettu", PHASES)
def test_lause_ei_vaita_vaaraa_aikamuotoa(
    nimi: str, dc: int, hit: bool, state: str | None, odotettu: str | None
) -> None:
    story = _story(dc, hit, state)
    ongelma = _tense_problem(story, state)
    assert ongelma is None, f"{nimi}: {ongelma}"


@pytest.mark.parametrize("nimi,dc,hit,state,odotettu", PHASES)
def test_lause_ja_luku_samasta_rivista(
    nimi: str, dc: int, hit: bool, state: str | None, odotettu: str | None
) -> None:
    story = _story(dc, hit, state)
    ongelma = _number_problem(story, dc, THR)
    assert ongelma is None, f"{nimi}: {ongelma}"


def test_kaikki_kategoriat_ovat_saavutettavissa() -> None:
    """Haara jota ei voi saavuttaa on copya jota kukaan ei nae."""
    tags = set()
    for state in ("upcoming", "live", "finished", None):
        for dc in range(0, THR + 3):
            s = defcon_story(dc, THR, dc >= THR, state)
            assert s is not None
            tags.add(s["tag"])
    assert tags == {
        "NOT STARTED",
        "BUILDING",
        "CLOSE",
        "SCORED",
        "JUST SHORT",
        "SHORT",
        None,
    }, tags


def test_ei_toimintoverbia_ilman_kohdetta() -> None:
    """Tietoinen valinta 4.9: rivilla ei ole "Watch ->" -verbia, koska
    tuotteessa ei ole paikkaa johon se veisi (live-ottelusivua ei ole,
    pelaajakortti avautuisi tyhjana hakuna). Umpikujaan vieva verbi on
    huonompi kuin ei verbia. Jos kohde joskus rakennetaan, tama testi
    muutetaan — ja silloin muutos nakyy diffissa."""
    for state in ("upcoming", "live", "finished", None):
        for dc in range(0, THR + 3):
            s = defcon_story(dc, THR, dc >= THR, state)
            assert s is not None
            assert "action" not in s, s


@pytest.mark.parametrize("nimi,dc,hit,state,odotettu", PHASES)
def test_rivilla_on_kategoria_ja_lause(
    nimi: str, dc: int, hit: bool, state: str | None, odotettu: str | None
) -> None:
    ongelma = _shape_problem(_story(dc, hit, state))
    assert ongelma is None, f"{nimi}: {ongelma}"


def test_maalivahdilla_ei_ole_tarinaa() -> None:
    assert defcon_story(0, None, False, "live") is None


# --------------------------------------------------------------------------
# Negatiiviset kontrollit
# --------------------------------------------------------------------------


def test_negatiivinen_kontrolli_vaara_aikamuoto() -> None:
    vaarin = {"tag": "SHORT", "line": "2 away with the match still on.", "action": None}
    assert _tense_problem(vaarin, "finished") is not None


def test_negatiivinen_kontrolli_luku_toisesta_lahteesta() -> None:
    vaarin = {"tag": "BUILDING", "line": "On track for a big score.", "action": None}
    assert _number_problem(vaarin, 8, THR) is not None


def test_negatiivinen_kontrolli_kategoria_katoaa() -> None:
    """Jos tarina palauttaisi pelkan lauseen ilman kategoriaa, rivi olisi taas
    numeroseina. Tarkistin ajetaan rikottuun arvoon."""
    rikottu = {"line": "10 of 12."}
    assert _shape_problem(rikottu) is not None
