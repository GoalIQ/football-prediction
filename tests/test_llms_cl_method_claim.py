"""LLMS-CL-MENETELMA (28.9.2026, yoajo).

llms.txt rivi 104 (nyt ~106) ja predictions.html:n FAQ-vastaus (JSON-LD + nakyva
<dd>, kaksi kopiota jotka olivat jo ennen tata sanasta sanaan samat) vaittivat
etta "Club fixtures are fitted on the league's own results" - blanko vaite
JOKA klubiottelulle. Se ei pida Mestarien liigalle, Eurooppa-liigalle eika
konferenssiliigalle: ne fitataan YHTEISMALLINA yhdeksan liigan datasta 8.9
alkaen (src/models/uefa_joint.py, kytketty api/main.py:hyn dynaamisella
`tournament_league`-parametrilla mille tahansa UEFA-turnaukselle, ei vain
CL:lle - `BRIDGE_LEAGUES` sisaltaa Europa League + Conference League +
CL-karsinnat siltaotteluina).

Tama testi ei mittaa etta LAUSE ON KAUNIS. Se mittaa etta jos Mestarien liiga
mainitaan menetelmakuvauksessa, sita ei kuvata "oman liigansa tuloksiin"
fitatuksi ilman yhteisfitin mainintaa - ja etta predictions.html:n kaksi
kopiota (JSON-LD ja nakyva teksti) eivat karkaa toisistaan, koska mikaan
aiempi portti ei vartioinut niiden yhtasuuruutta.

Negatiivinen kontrolli jokaiselle vaitteelle (kontrolli-lapaisi-tyhjana):
vanha sanamuoto syotettyna pitaa kaataa testi.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LLMS = ROOT / "llms.txt"
PREDICTIONS = ROOT / "predictions.html"

OLD_BLANKET_CLAIM = (
    "Club fixtures are fitted on the league's own results, weighted on both "
    "goals and per-match xG in the five leagues with an xG feed (Premier "
    "League, La Liga, Bundesliga, Serie A, Ligue 1); every other competition "
    "is fitted on goals alone."
)

OLD_FAQ_PARAGRAPH = (
    "GoalIQ uses a Dixon-Coles statistical model with the tau correction for "
    "low scores, time decay so recent matches count more, and shrinkage "
    "toward the league mean. For a club fixture it is fitted on that "
    "league's own results, last full season plus the current one as it "
    "plays, weighted on both goals and the xG those matches produced where "
    "an xG feed exists. For any fixture it estimates the win probability "
    "for each side and the draw, expected goals for both teams, and "
    "scoreline probabilities."
)


def _method_line(txt: str) -> str:
    for line in txt.splitlines():
        if line.strip().startswith("- Method:"):
            return line
    return ""


def _cl_sentence(line: str) -> str:
    """Poimii sen virkkeen jossa 'Champions League' mainitaan, tai tyhjan."""
    for sent in re.split(r"(?<=[.!?])\s+", line):
        if "Champions League" in sent:
            return sent
    return ""


# ---------------------------------------------------------------------------
# 1. Koodi todella fittaa CL/EL/ECL:n yhteismallina - jos tama ei enaa pida,
#    testi 2 vartioi vaaraa asiaa.
# ---------------------------------------------------------------------------
def test_uefa_joint_bridge_covers_europa_and_conference_league():
    from src.models.uefa_joint import BRIDGE_LEAGUES
    assert "INT-Europa League" in BRIDGE_LEAGUES
    assert "INT-Conference League" in BRIDGE_LEAGUES


# ---------------------------------------------------------------------------
# 2. llms.txt: CL-virke ei saa olla blanko "oma liiga" -vaite ilman
#    yhteisfitin mainintaa.
# ---------------------------------------------------------------------------
def test_llms_method_line_does_not_claim_cl_is_single_league_fit():
    line = _method_line(LLMS.read_text(encoding="utf-8"))
    assert line, "llms.txt: Method-rivia ei loytynyt - rivi poistui tai muutti muotoaan"
    cl = _cl_sentence(line)
    assert cl, "llms.txt: Method-rivi ei mainitse Champions Leaguea lainkaan"
    assert "jointly" in cl, cl
    assert "own results" not in cl, cl


def test_negative_control_old_llms_wording_fails():
    """Kontrolli: vanha, jo julkaistu sanamuoto EI mainitse CL:aa lainkaan
    - se on tasan se puute jonka takia lause luki totena kaikille
    kilpailuille. Jos tama kontrolli lapaisisi hiljaa, portti ei mittaisi
    mitaan."""
    line = "- Method: " + OLD_BLANKET_CLAIM
    assert _cl_sentence(line) == ""


# ---------------------------------------------------------------------------
# 3. predictions.html: FAQ-vastaus (JSON-LD + nakyva <dd>) on sanasta sanaan
#    sama, JA sen CL-virke ei ole blanko-vaite.
# ---------------------------------------------------------------------------
def _faq_texts(html: str) -> list[str]:
    jsonld = re.search(
        r'"text":\s*"(GoalIQ uses a Dixon-Coles statistical model[^"]*)"', html)
    dd = re.search(
        r"<dd>(GoalIQ uses a Dixon-Coles statistical model[^<]*)</dd>", html)
    assert jsonld, "predictions.html: JSON-LD FAQ-vastausta ei loytynyt"
    assert dd, "predictions.html: nakyvaa <dd>-FAQ-vastausta ei loytynyt"
    return [jsonld.group(1), dd.group(1)]


def test_predictions_faq_jsonld_matches_visible_dd():
    a, b = _faq_texts(PREDICTIONS.read_text(encoding="utf-8"))
    assert a == b, (
        "predictions.html: JSON-LD ja nakyva FAQ-teksti erosivat toisistaan "
        "- kumpikaan portti ei ole vartioinut etta ne pysyvat samana")


def test_predictions_faq_does_not_claim_cl_is_single_league_fit():
    for text in _faq_texts(PREDICTIONS.read_text(encoding="utf-8")):
        cl = _cl_sentence(text)
        assert cl, "predictions.html FAQ ei mainitse Champions Leaguea"
        assert "jointly" in cl, cl
        assert "own results" not in cl, cl


def test_negative_control_old_faq_wording_fails():
    assert _cl_sentence(OLD_FAQ_PARAGRAPH) == ""
