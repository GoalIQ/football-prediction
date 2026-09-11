# -*- coding: utf-8 -*-
"""UCL-kauden vaihe: yksi lukija jota pinta ei voi ohittaa.

🔴 MIKSI TAMA ON OMA MODUULINSA (saanto 6a).

UCL-artefaktissa on kaksi kenttaparia jotka tarkoittavat eri asiaa eri
kauden vaiheessa:

    prev_season_points   = viime kauden UCL-pisteet, kannettu syotteessa
    points               = taman kauden pisteet, olemassa VASTA kun
                           kierroksia on pelattu

Jos jokainen pinta joutuu muistamaan kumpi on voimassa nyt, joku unohtaa -
ja unohdus nakyy lukijalle numerona jonka vieressa on vaara vuosiluku. Se
on tasan sama vikaluokka kuin `lause-ja-luku-eri-lahteesta`: otsikko tulee
yhdesta paikasta ja luku toisesta, ja ne ajautuvat erilleen.

Siksi `pistekentta()` palauttaa KENTAN JA OTSIKON SAMASTA KUTSUSTA. Pinta
ei voi ottaa toista ja unohtaa toista, koska niita ei ole erikseen.

Vaihe paatellaan DATASTA, ei kellonajasta eika kovakoodatusta
paivamaarasta: `kausi_alkanut()` kertoo onko kierroksia pelattu ja
deadlinet kertovat onko kausi ohi. Kalenteriin sidottu vaihe olisi oikein
siihen asti kun se lakkaa olemasta oikein, eika mikaan huutaisi.

🔴 11.9.2026: `matchdays_played` (syotteen `teamPlayed`) EI OLE kumulatiivinen.
UEFA nollaa sen kun kierros vaihtuu: MD1 pelattu, syote siirtyi MD2:een ja
`teamPlayed == 0` kaikilla 1 163 pelaajalla, vaikka `totPts` oli jo taman
kauden (Haaland 12, ei viime kauden 100+). Lukija joka katsoo vain sita
palautti ESIKAUDEN kesken kauden, ja ingest olisi nimennyt taman kauden
pisteet `prev_season_points`iksi. Portti (`test_pistesarake_on_tyhja_eika_nolla`)
pysaytti julkaisun, mutta putki oli punainen 5 ajoa ja /ucl jaatyi.
Siksi kauden alku luetaan KAHDESTA syotteen omasta signaalista joista
kumpikaan ei palaa takaisin: lukittu kierros (`is_locked`) TAI pelattu
kierros (`matchdays_played > 0`). Sama funktio on ingestin ja pinnan ainoa
lukija (saanto 6a kohta 1).
"""
from __future__ import annotations

import datetime as dt

# Vaiheet. `complete` on erikseen `in_progress`ista siksi etta paattyneella
# kaudella "next deadline" -copy on valhe, ei vain tyhja.
ESIKAUSI = "preseason"
KESKEN = "in_progress"
OHI = "complete"


def _deadlinet(doc: dict) -> list[dt.datetime]:
    ulos = []
    for k in doc.get("matchdays") or []:
        raw = k.get("deadline_utc")
        if not raw:
            continue
        try:
            ulos.append(dt.datetime.fromisoformat(raw))
        except ValueError:
            continue
    return sorted(ulos)


def kausi_alkanut_raw(kierrokset, team_played) -> bool:
    """Onko taman kauden kierroksia pelattu. AINOA LUKIJA, myos ingestille.

    True jos yksikin kierros on syotteessa lukittu (`is_locked`) TAI
    yhdellakin pelaajalla `teamPlayed`/`matchdays_played` > 0. Kumpikaan ei
    palaa takaisin epatodeksi kauden aikana, joten tulos on monotoninen:
    se ei voi vaihtua ESIKAUDEKSI kesken kauden niin kuin pelkka
    `teamPlayed` teki 11.9 (ks. moduulin docstring).

    `kierrokset` = artefaktin/ingestin `matchdays`-lista (dictit joissa
    `is_locked`), `team_played` = iteroitava kokonaislukuja.
    """
    if any(bool(k.get("is_locked")) for k in (kierrokset or [])):
        return True
    return any(int(x or 0) > 0 for x in (team_played or []))


def kausi_alkanut(doc: dict) -> bool:
    """`kausi_alkanut_raw` artefaktille."""
    pelaajat = doc.get("players") or []
    return kausi_alkanut_raw(doc.get("matchdays") or [],
                             (p.get("matchdays_played") for p in pelaajat))


def vaihe(doc: dict, nyt: dt.datetime | None = None) -> str:
    """Kauden vaihe artefaktista.

    ESIKAUSI  yhtakaan kierrosta ei ole pelattu
    KESKEN    kierroksia on pelattu ja deadlineja on jaljella
    OHI       viimeinen deadline on mennyt
    """
    nyt = nyt or dt.datetime.now(dt.timezone.utc)
    dls = _deadlinet(doc)
    if dls and dls[-1] <= nyt:
        return OHI
    return KESKEN if kausi_alkanut(doc) else ESIKAUSI


def pistekentta(doc: dict, nyt: dt.datetime | None = None) -> tuple[str, str]:
    """(kentan_nimi, sarakeotsikko) - AINA samasta kutsusta.

    🔴 Palautusarvo on pari juuri siksi ettei otsikko ja luku voi tulla eri
    paikasta. Esikaudella kentta on `prev_season_points` ja otsikko sanoo
    aaneen etta se on VIIME kaudelta; muuten `points` ja "Pts".
    """
    if vaihe(doc, nyt) == ESIKAUSI:
        return "prev_season_points", "Pts (last season)"
    return "points", "Pts"


def arvo(pelaaja: dict, kentta: str) -> int:
    """Pelaajan luku annetusta kentasta. Puuttuva = 0.

    Erillinen funktio siksi etta `points` puuttuu esikaudella kokonaan -
    `p["points"]` nostaisi KeyErrorin ja `p.get("points")` palauttaisi
    Nonen, joka lajittelussa kaatuu.
    """
    return int(pelaaja.get(kentta) or 0)


def seuraava_kierros(doc: dict, nyt: dt.datetime | None = None) -> dict | None:
    """Ensimmainen kierros jonka deadline on viela edessa, tai None."""
    nyt = nyt or dt.datetime.now(dt.timezone.utc)
    for k in sorted(doc.get("matchdays") or [], key=lambda x: x.get("md") or 0):
        raw = k.get("deadline_utc")
        if not raw:
            continue
        try:
            if dt.datetime.fromisoformat(raw) > nyt:
                return k
        except ValueError:
            continue
    return None
