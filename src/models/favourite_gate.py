"""SUOSIKKI-VAIN-KUN-ERO-YLITTAA-VIRHEEN (QUEUE, korjattu 10.9.2026).

Villen havainto 8.9: tuotanto nimesi Club Brugge suosikiksi (40,5 %) kun
tasapeli oli 24,0 % ja Aston Villa 35,5 % — ero kärkeen on 5,0 pp, ja
mallin oma mitattu keskipoikkeama Optan todennäköisyyksistä oli mitattuna
8,2 pp eli SUUREMPI kuin tuo ero. Mallia EI säädetä osumaan markkinaan —
se olisi jälkifittausta. Korjaus on tuotepuolella: kun tulokset ovat
lähempänä toisiaan kuin mallin oma mitattu virhe, pinnan ei pidä
implikoida suosikkia (korostus, järjestys, "model favours X" -copy).

Tämä on YKSI lukija jota jokainen pinta (ottelusivu, jakokortti, mobiili,
SPA, postaus) voi kutsua sen sijaan että kukin toteuttaisi saman kynnyksen
itse — muisti: sama-vaite-monella-renderointipolulla ("joku unohtaa").
"""

from __future__ import annotations


def calibration_error_pp(calibration: list[dict] | None) -> float | None:
    """Otoskoolla painotettu MAE ennustetun ja toteutuneen todennäköisyyden
    välillä, prosenttiyksikköinä (`data/accuracy.json`:n `calibration`-taulukko).

    Palauttaa None jos kalibrointidataa ei ole tai yhdelläkään binillä ei ole
    havaintoja — virhettä EI silloin tunneta, eikä puuttuva mittaus saa
    oletusarvoisesti näyttäytyä nollana (se sallisi minkä tahansa eron näyttää
    suosikin) eikä äärettömänä (se piilottaisi jokaisen suosikin).
    """
    if not calibration:
        return None
    total_n = sum(int(b.get("n") or 0) for b in calibration)
    if total_n <= 0:
        return None
    weighted = sum(
        abs(float(b["predicted"]) - float(b["actual"])) * int(b.get("n") or 0)
        for b in calibration
    )
    return (weighted / total_n) * 100.0


def is_close_call(p_home: float, p_draw: float, p_away: float,
                   error_pp: float | None) -> bool:
    """True kun kahden TODENNÄKÖISIMMÄN lopputuloksen ero on pienempi kuin
    mallin oma mitattu virhe — silloin pinnan ei pidä implikoida suosikkia.

    Vertailu on kolmen tuloksen KESKINÄINEN järjestys, ei pelkkä
    koti–vieras-ero: tasapeli voi olla se toiseksi todennäköisin tulos, ja
    silloin juuri se ero ratkaisee (esim. koti 50 %, tasapeli 45 %, vieras
    5 % — ero kärkeen on 5 pp, ei 45 pp).

    error_pp=None (virhettä ei ole mitattu) → False: puuttuva mittaus ei saa
    vaimentaa pintaa arvauksella, se olisi sama virhe kuin ennenkin (muisti:
    jonorivi-ei-ole-todiste-tilasta koskee myös puuttuvaa mittausta).
    """
    if error_pp is None:
        return False
    top, second, _ = sorted([p_home * 100, p_draw * 100, p_away * 100],
                             reverse=True)
    return (top - second) < error_pp
