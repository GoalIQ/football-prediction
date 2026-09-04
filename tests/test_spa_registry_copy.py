"""Portti: tyokalurekisterin nakyva teksti noudattaa kovia copy-saantoja.

🔴 MITATTU VIKA (4.9.2026, julkaisuportti blokkasi). Uusi tyokalurekisteri
`web/pro-spa/src/lib/tools.ts` toi kaksi hylattya sanamuotoa takaisin:

  * `'Which legal 15 fits around the players I have already locked in?'`
    "legal" on Villen 28.7.2026 kieltama termi (no-solver-jargon). Se
    poistettiin silloin neljalta pinnalta — ja SAMAN komponentin
    (`FitChecker.svelte`) oma kommentti sanoo sen suoraan, samalla kun sen
    nakyva copy kayttaa muotoa "the strongest valid 15-player…". Uusi kortti
    ja komponentti nayttivat siis eri sanaa samalla ruudulla.

  * `'What does every player project per gameweek…'`
    Datakattavuuslupaus jota data ei kata: artefaktissa `n_players: 503`,
    `n_excluded: 148`. Sama saanto kuin muistissa `honest-data-labels`.

Molemmat ovat tasan se kuvio jonka muisti nimeaa:
`hylatty-sanamuoto-palaa-uudessa-generaattorissa` — hylkays elaa yhden
artefaktin kentassa, ja seuraava generaattori ei tieda siita. Siksi rekisteri
saa oman porttinsa: se on nyt YKSI paikka josta 22 tyokalun nakyva teksti
tulee, eli myos yksi paikka jossa kielto voidaan pitaa.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "web" / "pro-spa" / "src" / "lib" / "tools.ts"
)

# Termi -> miksi kielletty. Perustelu on osa porttia: ilman sita seuraava
# lukija ei tieda saako listaa muuttaa.
BANNED = {
    "legal": "Villen paatos 28.7.2026 (no-solver-jargon): saantojen mukainen "
             "kokoonpano sanotaan 'valid', ei 'legal'",
    "solver": "sisainen menetelmatermi, ei kayttajan kielta",
    "optimiser": "sama kuin solver",
    "optimizer": "sama kuin solver",
    "every player": "datakattavuuslupaus: artefaktissa on poissulkulista "
                    "(n_excluded 148), joten 'every' ei ole tosi",
    "all players": "sama kattavuuslupaus",
    "guarantee": "lupaus tuloksesta",
    "best odds": "uhkapelisanasto",
}

EM_DASH = "—"


def _visible_strings() -> list[tuple[str, str]]:
    """(kentta, teksti) jokaiselle kayttajalle nakyvalle rekisterikentalle."""
    src = REGISTRY.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for key in ("title", "question", "label"):
        for m in re.finditer(rf"\b{key}:\s*\n?\s*(['\"])(.*?)\1", src, re.S):
            out.append((key, m.group(2)))
    return out


def _banned_hits(strings: list[tuple[str, str]]) -> list[str]:
    bad = []
    for key, text in strings:
        low = text.lower()
        for term, why in BANNED.items():
            if term in low:
                bad.append(f"{key}: {text!r} sisaltaa {term!r} — {why}")
        if EM_DASH in text:
            bad.append(f"{key}: {text!r} sisaltaa em dashin")
    return bad


def test_rekisteri_ei_ole_tyhja() -> None:
    """Ilman tata koko portti menisi lapi tyhjana jos jasennin rikkoutuu."""
    strings = _visible_strings()
    assert len(strings) >= 40, f"vain {len(strings)} nakyvaa merkkijonoa"


def test_ei_kiellettyja_termeja_nakyvassa_tekstissa() -> None:
    ongelmat = _banned_hits(_visible_strings())
    assert not ongelmat, "\n".join(ongelmat)


def test_kysymykset_ovat_kysymyksia() -> None:
    """`question` on maaritelty kysymykseksi: se on kortin lupaus siita mihin
    tyokalu vastaa. Vaitelause samassa paikassa olisi eri asia."""
    for key, text in _visible_strings():
        if key == "question":
            assert text.rstrip().endswith("?"), f"{text!r} ei ole kysymys"


def test_negatiivinen_kontrolli_kielletty_termi_palaa() -> None:
    rikottu = [("question", "Which legal 15 fits around my locked players?")]
    assert _banned_hits(rikottu), "portti ei nappaisi 'legal'-termia"


def test_negatiivinen_kontrolli_kattavuuslupaus() -> None:
    rikottu = [("question", "What does every player score this gameweek?")]
    assert _banned_hits(rikottu), "portti ei nappaisi kattavuuslupausta"


def test_negatiivinen_kontrolli_em_dash() -> None:
    rikottu = [("title", f"Rate my team {EM_DASH} fast")]
    assert _banned_hits(rikottu), "portti ei nappaisi em dashia"


@pytest.mark.parametrize("term", sorted(BANNED))
def test_jokaisella_kiellolla_on_perustelu(term: str) -> None:
    assert BANNED[term].strip(), f"{term}: kiellolle ei ole kirjattu syyta"
