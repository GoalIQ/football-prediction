"""Yksi lukija epavarmuus-sarakkeen lupaukselle.

TAUSTA (12.9.2026, DOUBT-COST-LUPAUS). Kaksi ilmaissivua sanoi samasta
sarakkeesta eri asian:

  /fpl            "...so you can see what the doubt actually costs"
  /fpl/team-news  "the number you see is what the model expects including the
                   doubt, not what the player would score if fully fit"

Toinen lupasi HINNAN, toinen sanoi ettei hintaa nayteta. Hinnan nakeminen
vaatisi kaksi lukua (terve ja epavarma); sivulla on vain toinen. Vika ei ollut
teoreettinen: julkaisutarkistaja blokkasi 12.9 postausdraftin joka kaytti
/fpl:n omaa sanamuotoa lahteena, eli oma copymme oli lahde vaaralle vaitteelle.

Molemmat pinnat lukevat lauseen taalta (saanto 6a, mekanismi 1: yksi lukija
joka ei voi palauttaa vaaraa). Jos joku joskus julkaisee myos fully-fit-luvun,
hintavaite muuttuu todeksi -- silloin muutetaan TAMA tiedosto ja
HINTAVAITE_SALLITTU alla, ei sivua kerrallaan.
"""
from __future__ import annotations

import re

# Kanoninen lause. Molemmat pinnat upottavat taman sellaisenaan.
XP_SISALTAA_EPAVARMUUDEN = (
    "the number you see is what the model expects including the doubt, "
    "not what the player would score if fully fit"
)

# Julkaistaanko fully-fit-luku missaan? Niin kauan kuin ei, hintavaite on
# epatosi riippumatta siita miten se on muotoiltu.
HINTAVAITE_SALLITTU = False

# Vaiteperhe, ei yksi merkkijono (muisti: vaiteperhe-ei-tyhjene-greppaamalla).
# Osuu muotoihin "what the doubt actually costs", "how much the injury costs",
# "the cost of the flag", "the doubt costs you", "what the knock is costing".
_HINTAVAITE_RE = re.compile(
    r"(?:what|how\s+much)\s+(?:the\s+)?(?:doubt|injury|knock|flag)\s*"
    r"(?:\w+\s+){0,3}?(?:actually\s+)?(?:costs?\b|is\s+costing\b)"
    r"|(?:the\s+)?(?:cost|price)\s+of\s+(?:the\s+|a\s+|his\s+)?"
    r"(?:doubt|injury|knock|flag)"
    r"|(?:doubt|injury|knock|flag)\s+costs?\s+(?:you|him|them|the\s+owner)"
    # 12.9: portti mittasi etta seitseman sanamuotoa lapaisi tarkistuksen,
    # vahvimpana sivun OMA H1 "Team news, with the points cost attached".
    r"|points?\s+(?:cost|price)\s+attached"
    r"|(?:cost|price|worth|damage|discount)\s+(?:of\s+)?(?:the\s+)?(?:doubt|flag|knock)"
    r"|how\s+(?:much|many\s+points)\s+(?:the\s+)?(?:doubt|injury|knock|flag)"
    r"|(?:doubt|injury|knock|flag)\s+(?:takes?\s+(?:off|away)|discount)",
    re.I,
)

_TAGIT = re.compile(r"<[^>]+>")


# Kohdesivun H1. 12.9 se lupasi "Team news, with the points cost attached" eli
# TASAN sen vaitteen joka /fpl:lta poistettiin: lukija klikkasi linkkia ja
# laskeutui hintalupaukseen. Yksi lukija tarkoittaa kaikkia vaitteita samasta
# sarakkeesta, ei yhta virkketta kolmesta.
TEAM_NEWS_H1 = "Team news, with our projected points attached"


def lauseena() -> str:
    """Sama vaite virkkeen alussa. Isotus tehdaan taalla eika pinnalla,
    jotta kopiota ei synny (saanto 6a, mekanismi 1)."""
    return XP_SISALTAA_EPAVARMUUDEN[0].upper() + XP_SISALTAA_EPAVARMUUDEN[1:]


def hintavaitteet(html: str) -> list[str]:
    """Palauttaa loydetyt hintavaitteet nakyvasta tekstista.

    Tagit poistetaan ensin, jotta vaite loytyy myos silloin kun linkki tai
    <strong> katkaisee lauseen kesken (muisti: rivi-ei-ole-skannausyksikko).
    """
    teksti = " ".join(_TAGIT.sub(" ", html).split())
    return [m.group(0) for m in _HINTAVAITE_RE.finditer(teksti)]


# Sarakeotsikko joka olisi projektioluku. Jos naita on Doubtful-taulukossa
# enemman kuin yksi, sivulla on kaksi lukua samasta pelaajasta ja hintavaite
# muuttuu mahdolliseksi lukea. Silloin copy on arvioitava uudelleen.
_PROJEKTIO_TH_RE = re.compile(r"\b\d*\s*GW\s*xP\b|\bxP\b|expected\s+points", re.I)

# Vastafaktuaalinen sarake: luku "jos pelaisi taysin terveena". Tata ei ole,
# ja juuri siksi hintaa ei voi nayttaa.
_VASTAFAKTUAALI_TH_RE = re.compile(
    r"fully\s*fit|if\s*fit|healthy|uninjured|potential\s*xP", re.I
)


def projektiosarakkeet(thead_otsikot: list[str]) -> list[str]:
    return [o for o in thead_otsikot if _PROJEKTIO_TH_RE.search(o)]


def vastafaktuaalisarakkeet(thead_otsikot: list[str]) -> list[str]:
    return [o for o in thead_otsikot if _VASTAFAKTUAALI_TH_RE.search(o)]
