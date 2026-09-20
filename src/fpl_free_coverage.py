"""YKSI LUKIJA: mita goaliq.app/fpl kattaa ilmaiseksi, ja mita kortti saa siita sanoa.

MITATTU VIKA (20.9.2026):

    scripts/gen_share_card.py:1235  # 17.9 PORTTI: "both columns" oli epatosi
    data/rejected_phrases.json      "both columns, on goaliq.app/fpl"
    scripts/gen_share_card.py:1453  "All 20 teams, every gameweek: goaliq.app/fpl"  <- livena
    scripts/gen_reel.py:103         "Every team, every gameweek"                    <- livena

17.9 hylattiin sanamuoto joka vaitti ilmaissivusta enemman kuin sivulla on, ja
korjaus kirjoitettiin YHTEEN funktioon. Saman tiedoston sisarfunktio ja
reel-generaattori sanoivat saman vaitteen eri sanoin ja lapaisivat portin,
koska rekisteroity hylkays oli MERKKIJONO eika VAITE. Tama on tasan se luokka
jonka `data/rejected_phrases.json` kuvaa omassa `_miksi`-kentassaan 4.9:lta:
"hylkays joka asuu yhden tiedoston kommentissa ei ole portti".

MITTA (fpl.html, 20.9.2026, sivun omat sanat):

- Nollapeli-% on ottelukohtaisena enintaan kuudelle kierrokselle: taulukon
  sarake "Next 6 CS%" ja gridi jossa on kuusi GW-saraketta. Sivu sanoo itse:
  "Clean sheet % appears as each gameweek moves closer. [...] Each column
  averages the model's difficulty over six gameweeks, so this shows where the
  swings are, not a number for any single match." Myohemmat lohkot (GW11-16,
  GW17-22, ...) ovat keskiarvoja, eivat kierroskohtaisia lukuja.
- Projisoidut maalit ovat VAIN seuraavassa ottelussa: "projected goals
  MCI 2.14 v SUN 0.75" Next opponent -solussa, kerran per joukkue. Sivulla ei
  ole kierroskohtaista maaligridia.

Eli "every gameweek" on epatosi MOLEMMISTA luvuista, ja luvuilla on lisaksi
ERI horisontti keskenaan. Horisonttisanat tulevat nyt tasta yhdesta
funktiosta. Portti `tests/test_fpl_free_coverage_claims.py` kaataa buildin jos
ne kirjoitetaan kasin korttiin tai videoon, ja mittaa sivusta etta yllaoleva
kate pitaa yha (kate voi kasvaa: silloin testi kaatuu ja luvut paivitetaan
tanne, ei korttiin).
"""
from __future__ import annotations

#: Ilmaissivu johon kortit ja reelit lahettavat lukijan tarkistamaan.
FPL_LANDING = "goaliq.app/fpl"

#: Enintaan nain monta kierrosta nollapeli-% on sivulla KIERROSKOHTAISENA.
CLEAN_SHEET_GAMEWEEKS = 6

#: Enintaan nain monta kertaa "projected goals" esiintyy sivulla: kerran per
#: joukkue, Next opponent -solussa. Suurempi luku tarkoittaisi ettei maaliluku
#: ole enaa vain seuraavasta ottelusta.
PROJECTED_GOALS_MENTIONS = 20

#: Sanamuodot joilla pysyva kuva tai video vaittaisi laajempaa katetta kuin
#: ilmaissivulla on. Naita ei kirjoiteta kasin korttipinnoille: kortti ei voi
#: kantaa sita tasmennysta joka tekisi vaitteesta toden.
HORIZON_OVERCLAIMS = (
    "every gameweek",
    "each gameweek",
    "all gameweeks",
    "every week",
    "all 38",
    "whole season",
    "every column",
    "both columns",
)

#: Pinnat jotka renderoivat pysyvan kuvan tai videon: PNG ja MP4 leviavat
#: ilman linkkia ja ilman kontekstia, joten niissa vaite on tarkistettava
#: sellaisenaan. Sivugeneraattorit EIVAT ole tassa: sivu saa sanoa
#: "every gameweek" Premiumista, koska Premium kattaa ne.
CARD_SURFACES = (
    "scripts/gen_share_card.py",
    "scripts/gen_reel.py",
    "scripts/render_projected_xi_card.py",
    "scripts/render_standouts_card.py",
)

_NUMEROT = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def fpl_free_claim(*, projected_goals: bool) -> str:
    """Mita goaliq.app/fpl kattaa, sanoina jotka ovat tosia juuri tasta kortista.

    `projected_goals=True` tarkoittaa etta kortti nayttaa MOLEMMAT luvut.
    Niilla on eri horisontti (nollapeli kuusi kierrosta, maalit seuraava
    ottelu), joten yksi horisonttisana olisi epatosi toisesta. Silloin
    sanotaan mika on ilmaista, ei kuinka pitkalle se yltaa.
    """
    if projected_goals:
        return "both numbers"
    return f"next {_NUMEROT[CLEAN_SHEET_GAMEWEEKS]} gameweeks"


#: Poikkeuslista: "polku::sanamuoto" -> PERUSTELU (saanto 6a kohta 2).
#: Uusi pinta ei paase listalle vahingossa - portti kaatuu ja kirjoittaja
#: joutuu kirjoittamaan miksi vaite on tosi juuri siina.
POIKKEUKSET: dict[str, str] = {}
