"""FPL:n pelaajastatus — YKSI LUKIJA sille kuka on yha valittavissa.

🔴 MITATTU VIKA (3.9.2026 leaders/DefCon, 4.9.2026 team news). FPL PITAA
liigasta lahteneen pelaajan bootstrapissa kauden loppuun asti: Watkins oli
yha id 55, seura AVL, ja `news` luki "Has joined Al Hilal permanently".
Status on `u`. Se ei siis putoa mistaan "ei ole bootstrapissa" -ehdosta, ja
jokainen pinta joka listaa pelaajia nimella joutuu suodattamaan sen itse.

Mitattu 3.9: 52/499 leaders-rivia ja 45 DefCon-matriisin rivia oli status u.
Mitattu 4.9: etusivun ja `/fpl/team-news`:n "ruled out" -luku oli **146,
josta 89 oli lahteneita** (status u) ja vain 57 oikeasti poissa seuraavasta
deadlinesta (56 loukkaantunutta + 1 pelikielto). Sivu myos NIMESI eniten
omistetuksi poissaolijaksi Watkinsin, joka ei ole enaa liigassa.

Siksi tama on oma moduulinsa eika kopioitu apufunktio: kolmas kerta samasta
vikaluokasta eri pinnalla tarkoittaa etta suodatus ei voi jaada kirjoittajan
muistin varaan (CLAUDE.md saanto 6a kohta 1).

Loukkaantuneet ja pelikiellossa olevat (`i`, `d`, `s`) EIVAT ole lahteneita:
he ovat valittavissa ja palaavat. Heidat naytetaan.
"""
from __future__ import annotations

# FPL:n status-koodit: a = available, d = doubtful, i = injured,
# s = suspended, u = unavailable (ei enaa valittavissa), n = not in squad.
LEFT_LEAGUE_STATUS = "u"


def left_league(player: dict) -> bool:
    """True kun pelaaja ei ole enaa valittavissa (siirtynyt pois liigasta).

    Tyhja tai puuttuva status tulkitaan `a`:ksi (valittavissa) — puuttuva
    tieto ei saa pudottaa pelaajaa listalta.
    """
    return (player.get("status") or "a") == LEFT_LEAGUE_STATUS


def selectable(players: list[dict]) -> list[dict]:
    """Suodata pois liigasta lahteneet. Kayta jokaisessa nimilistassa."""
    return [p for p in players if not left_league(p)]
