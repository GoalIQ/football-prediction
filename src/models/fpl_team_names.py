"""Lahdenimi -> mallin (Understat) joukkuenimi: YKSI kartta kaikille FPL-pinnoille.

MIKSI TAMA ON OMA MODUULI (22.9.2026, CS-FDR-META-ERI-MIELTA)
------------------------------------------------------------
`build_fpl_cs_fdr.py`:lla oli oma nimikartta, josta puuttui kaksi rivia:
"Coventry City" -> "Coventry" ja "Hull City" -> "Hull". Kun nousijat saivat
GW1:n jalkeen oman Understat-historiansa, `build_fpl_phase0` loysi ne
mallista, mutta cs_fdr ei: sen silmissa "Coventry City" puuttui mallista, ja
se antoi seuralle EMPIIRISEN NOUSIJABASELINEN liveharvion sijaan. Sama ottelu
sai kaksi eri puhtaan pelin todennakoisyytta (mitattu 22.9: 12 ottelua GW6-11,
suurin ero HUL v IPS 16,8 % vs 33,0 %), ja `caveat` vaitti baselinea
seuroista joilla oli jo viisi ottelua dataa.

Vika oli hiljainen, koska puuttuva kartta ei kaada mitaan: tuntematon nimi
on laillinen syote `add_promoted_baseline`ille. Siksi kartta on nyt yksi
sanakirja jota jokainen builderi ja `fpl_wildcard` lukee. Uusi kausi, uusi
seura -> yksi rivi tahan, ja kaikki pinnat nakevat sen.

Kartta kattaa kolme lahdetta: pulselive (premierleague.com, pitkat nimet),
FPL:n bootstrap-static `team.name` (lyhyet nimet) ja identiteetti kaikelle
muulle. Mallinimet ovat Understatin (ks. SHORT_MAP build_fpl_phase0:ssa).
"""
from __future__ import annotations

NAME_MAP: dict[str, str] = {
    # pulselive (premierleague.com) ja FPL:n pitkat muodot
    "Brighton & Hove Albion": "Brighton",
    "Tottenham Hotspur": "Tottenham",
    "Leeds United": "Leeds",
    "Ipswich Town": "Ipswich",
    "Coventry City": "Coventry",
    "Hull City": "Hull",
    "Leicester City": "Leicester",
    "Luton Town": "Luton",
    "Norwich City": "Norwich",
    "Sheffield United": "Sheffield United",
    "West Ham United": "West Ham",
    "West Bromwich Albion": "West Bromwich Albion",
    # FPL-API (bootstrap-static team.name)
    "Man City": "Manchester City",
    "Man Utd": "Manchester United",
    "Spurs": "Tottenham",
    "Nott'm Forest": "Nottingham Forest",
    "Newcastle": "Newcastle United",
    "Wolves": "Wolverhampton Wanderers",
    "Sheffield Utd": "Sheffield United",
}


def map_name(source_name: str) -> str:
    """Lahdenimi (pulselive tai FPL) -> mallinimi. Tuntematon = sellaisenaan."""
    return NAME_MAP.get(source_name, source_name)
