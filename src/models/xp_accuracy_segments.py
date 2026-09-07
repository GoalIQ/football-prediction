# -*- coding: utf-8 -*-
"""Mista segmentista mallin harha saa kertoa, ja mista ei. YKSI LUKIJA.

🔴 TAUSTA (7.9.2026, portin kierrokset 23 ja 24).

`fpl_xp_gw_accuracy.json` kantaa kaksi segmentointia:

  * `by_class`      - pelaajat sen mukaan MITA HE TEKIVAT kierroksella
                      (dnp, blank, ticker, haul)
  * `by_pos_stats`  - pelaajat POSITION mukaan (GKP, DEF, MID, FWD)

Harhan mittaaminen `by_class`-segmentista on **valintaa selitettavan
muuttujan perusteella**: jos poimit ne joiden toteuma oli suuri,
odotusarvomalli on alle lahes joka kerta. Todiste omasta datastamme -
`|bias| == mae` TASMALLEEN molemmilla gradatuilla kierroksilla:

    dnp   GW1 n=190  mae 1.092  bias -1.092
    haul  GW1 n=19   mae 9.414  bias  9.414
    dnp   GW2 n=204  mae 1.080  bias -1.080
    haul  GW2 n=14   mae 8.954  bias  8.954

Yhtasuuruus tarkoittaa etta virheella on segmentissa vain yksi etumerkki.
Kalibroitu malli NAYTTAA talta; malli joka ei nayttaisi, tietaisi tuloksen
etukateen. `S9-bias-haul` oli auki **P1-signaalina**, ja sen mukaan
toimiminen olisi nostanut xP:ta kaikille ja huonontanut kalibrointia.

**23. kierroksella suljin sen VAIN toisesta lukijasta** (`autopilot/edge.py`),
ja `build_gw_recap.headline_miss` ajoi saman silmukan ilman suodatusta.
Kentta on suunniteltu postauksen otsikoksi, ja `data/gw_recap.json` on
JULKISESSA repossa - eli tautologia jai livene. Kaksi lukijaa, kaksi
saantoa (CLAUDE.md 6a kohta 1).

**EHTO ON LOHKO, EI NIMILISTA.** Ensimmainen korjaus oli kieltolista
arvonimista (`{"dnp","blank","ticker","haul"}`), jolloin uusi luokka (esim.
`cameo`) olisi mennyt lapi aitona loydoksena. `by_class` on
MAARITELMALTAAN toteumasegmentointi, joten ehto on lohkon nimi. Muisti:
`portin-sanalista-vanhenee`.
"""
from __future__ import annotations

# Lohko -> etuliite segmentin nimessa.
LOHKOT = (("by_class", ""), ("by_pos_stats", "pos:"))

# Lohkot jotka on maaritelty TOTEUMASTA. Naista ei raportoida harhaa.
TOTEUMALOHKOT = {"by_class"}

# Miksi, luettavaksi virheviestissa ja raportissa.
SYY = (
    "by_class on maaritelty kierroksen TOTEUMASTA (dnp/blank/ticker/haul), "
    "joten harhan mittaaminen siita on valintaa selitettavan muuttujan "
    "perusteella. Kalibroitu odotusarvomalli nayttaa aina 'aliarvioivan' "
    "hauleja ja 'yliarvioivan' pelaamattomia."
)


def bias_segments(acc_row: dict):
    """[(nimi, tilasto)] niista segmenteista joista harhasta SAA kertoa.

    Positio tiedetaan ennen kierrosta, joten sen harha on aito loydos.
    """
    ulos = []
    for lohko, etuliite in LOHKOT:
        if lohko in TOTEUMALOHKOT:
            continue
        for nimi, t in ((acc_row or {}).get(lohko) or {}).items():
            if isinstance(t, dict) and t.get("bias") is not None:
                ulos.append((etuliite + str(nimi), t))
    return ulos
