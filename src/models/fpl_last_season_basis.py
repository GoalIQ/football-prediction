# -*- coding: utf-8 -*-
"""Selittaako viime kauden lohko mitaan? YKSI lukija kaikille pinnoille.

VILLEN HAVAINTO 11.9.2026: "Pelaajakortti nayttaa turhaan edelliskauden
tilastoja." Mitattu samana iltana: `meta.data_coverage.baseline_mode` on
`live_history` ja `baseline_season` 2526, eli malli ei enaa noja viime
kauteen - mutta kortin ehto oli pelkka "onko riveja"
(`PlayerCard.svelte` `lsTotals.length > 0 || lsPer90.length > 0`), joten lohko
nakyi 475 kortilla riippumatta siita kertooko se mitaan.

🔴 JONORIVIN EHTO OLISI TEHNYT REGRESSION, ja se mitattiin ennen koodausta
(12.9): ehto `data_basis in (limited_history, no_history) or
minutes_basis_flag in (short_season, new_club)` olisi
  (a) PIILOTTANUT lohkon kaikilta 125 `excluded[]`-kortilta joilla se nyt
      nakyy. Niista 99:lla on oikeaa sisaltoa (Watkins 2 833 min / 167 p,
      Mateta 2 210 / 114, Caicedo 2 796 / 110) eika niille lasketa xP:ta
      lainkaan - viime kausi on kortin AINOA tuotantoluku. Ilmaispinnalla
      osuma olisi ollut viela kovempi: maski typistaa `players[]`:n kymmeneen
      muttei koske `excluded[]`-listaan, joten ilmaiskayttajan korttipooli on
      10 + 171.
  (b) SAILYTTANYT ne 29 `no_history`-rivia jotka ovat kauttaaltaan nollia
      (minutes 0, goals 0, xG 0.0). Ne eivat valehtele - Obi (MUN) pelasi
      aidosti 0 minuuttia 25/26 - mutta ne eivat kerro mitaan.

Kolme haaraa, ei kahta. Ja koska sama kysymys kysytaan kolmelta pinnalta
(pro-SPA:n pelaajakortti, SPA:n jakokortti, mobiilin jakokortti) KAHDESSA
ERI REPOSSA, vastaus lasketaan tassa ja kulkee payloadissa: yksi lukija ei voi
palauttaa vaaraa, kolme toteutusta voi (CLAUDE.md 6a, mekanismi 1).

Pinta paattaa MITEN lohko piirretaan; se ei paata milloin.
"""
from __future__ import annotations

#: Kentat jotka voivat kertoa jotain. Muu (season, league, team_name,
#: team_code) on tunnistetietoa eika tuotantoa.
_LUKUKENTAT = ("minutes", "starts", "goals", "assists", "xg", "xa",
               "cs", "points")

#: Syykoodit. Pinta lokalisoi; tama ei kirjoita kayttajalle nakyvaa tekstia.
SYY_EI_PROJEKTIOTA = "no_projection"
SYY_UUSI_SEURA = "new_club"
SYY_LYHYT_KAUSI = "short_season"
SYY_OHUT_OTOS = "thin_sample"


def _kaikki_nollia(last_season: dict) -> bool:
    """Onko jokainen luku nolla (tai puuttuu)?

    Tyhja lohko ja pelkkia nollia sisaltava lohko ovat lukijalle sama asia:
    kumpikaan ei kerro mitaan. Ero on vain siina etta nollarivi NAYTTAA
    tiedolta.
    """
    arvot = [last_season.get(k) for k in _LUKUKENTAT]
    loydetyt = [v for v in arvot if v is not None]
    if not loydetyt:
        return True
    return all(float(v) == 0.0 for v in loydetyt)


def selittaako(row: dict, excluded: bool = False) -> bool:
    """Kertooko viime kauden lohko tasta pelaajasta jotain jota tama kausi ei?

    Kolme haaraa:
      1. Ei lukuja tai kaikki nollia -> EI. (66 rivia 12.9)
      2. Ei mallinakymaa (excluded, tai `data_basis` puuttuu) -> KYLLA:
         viime kausi on ainoa tuotantoluku joka rivilla on.
      3. Muuten vain kun lohko SELITTAA taman kauden arvion: ohut
         PL-otos (`limited_history`/`no_history`) tai minuuttiperusteen
         lippu (`short_season`/`new_club`).
    """
    ls = row.get("last_season")
    if not isinstance(ls, dict) or _kaikki_nollia(ls):
        return False
    if excluded or row.get("data_basis") is None:
        return True
    if row.get("data_basis") in ("limited_history", "no_history"):
        return True
    return row.get("minutes_basis_flag") in ("short_season", "new_club")


def syy(row: dict, excluded: bool = False) -> str | None:
    """Syykoodi sille miksi lohko nakyy, tai None kun se ei nay.

    Portin loydos 5.9 toistuu tassa: merkki tai lohko ilman lukutapaa on
    merkki jolle ei ole selitysta. Lukija saa tietaa MIKSI han katsoo viime
    kauden lukuja taman kauden kortilla.
    """
    if not selittaako(row, excluded):
        return None
    if excluded or row.get("data_basis") is None:
        return SYY_EI_PROJEKTIOTA
    if row.get("minutes_basis_flag") == "new_club":
        return SYY_UUSI_SEURA
    if row.get("minutes_basis_flag") == "short_season":
        return SYY_LYHYT_KAUSI
    return SYY_OHUT_OTOS


def attach(players: list[dict], excluded_rows: list[dict] | None = None) -> dict:
    """Kirjoita `last_season_show` + `last_season_reason` riveille.

    Palauttaa jakauman meta-lohkoon, jotta muutos nakyy artefaktin omassa
    kirjanpidossa eika vain koodissa.
    """
    laskuri: dict[str, int] = {}
    for rivit, on_excluded in ((players, False), (excluded_rows or [], True)):
        for row in rivit:
            nayta = selittaako(row, on_excluded)
            row["last_season_show"] = nayta
            koodi = syy(row, on_excluded)
            if koodi:
                row["last_season_reason"] = koodi
            else:
                row.pop("last_season_reason", None)
            avain = koodi or "hidden"
            laskuri[avain] = laskuri.get(avain, 0) + 1
    return laskuri
