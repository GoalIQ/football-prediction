# -*- coding: utf-8 -*-
"""Joukkuelipun merkki ja selite, YHDESTA lukijasta.

🔴 TAUSTA (julkaisuportin huomio 4.9.2026, korjattu 7.9).
`fpl_xp_projections.json` antaa jokaiselle pelaajalle `team_flag`in, jolla on
KOLME arvoa: `promoted`, `high_turnover` ja tyhja. Long-tail-sivut tuntevat
molemmat liput (`_TFLAG_LABEL`), mutta jakokortti tarkisti vain

    (p.get("team_flag") or "") == "promoted"

joten `high_turnover` ei tuottanut korttiin mitaan merkkia.

Mitattu 7.9: Wissa (Newcastle, `team_flag: high_turnover`, 25,2 % viime
kauden minuuteista lahtenyt) sai varauksen ilmaissivulla muttei kortilla.
Koko poolissa lippuja on 99 `high_turnover` ja 80 `promoted` - eli lahes
puolet liputetuista pelaajista oli kortilla merkitsemattomia.

Kortti on JULKISIN pinta, koska kuva irtoaa sovelluksesta. Varaus joka nakyy
sivulla muttei kuvassa on sama kuin ei varausta siella missa sita eniten
tarvitaan (muisti: `jakopinta-lukee-eri-tiedostoa-kuin-sivu`).

Kynnys on ylavirrassa mitattu, ei tassa valittu: `build_team_confidence`
asettaa `high_turnover`in 51 joukkue-kausivaihdoksen jakaumasta (mediaani
13,0 %, p75 22,8 %, p90 29,4 %).
"""
from __future__ import annotations

# Lippu -> merkki kortilla. Jarjestys on merkitseva vain luettavuudelle.
MERKKI = {
    "promoted": "*",
    "high_turnover": "†",
}

# Lippu -> sana sivulla ja alaviitteessa.
SANA = {
    "promoted": "promoted",
    "high_turnover": "turnover",
}


def team_flag(p: dict) -> str:
    """Pelaajan joukkuelippu normalisoituna. Tyhja = ei lippua."""
    if not isinstance(p, dict):
        return ""
    lippu = (p.get("team_flag") or "").strip()
    return lippu if lippu in MERKKI else ""


def marker(p: dict) -> str:
    """Merkki nimen pereen kortilla. Tyhja kun lippua ei ole."""
    return MERKKI.get(team_flag(p), "")


def flags_present(players) -> list[str]:
    """Mitka liput esiintyvat NAYTETTAVISSA riveissa, vakaassa jarjestyksessa.

    Alaviite selittaa vain ne merkit jotka kortilla NAKYY. 10.8 sivun selite
    kertoi merkista jota sivulla ei ollut yhtaan - lukija etsi turhaan.
    """
    nahdyt = {team_flag(p) for p in (players or []) if isinstance(p, dict)}
    return [k for k in MERKKI if k in nahdyt]
