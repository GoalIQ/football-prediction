"""Yksi lukija kysymykselle "onko tama runko entryn runko?" (4.9.2026).

TAUSTA. Ville pysaytti 4.9 julkaisuun menossa olleen kortin katsomalla sita:
otsikko lupasi *"The model's own FPL squad, GW3 - entry 116920 - public on
fantasy.premierleague.com"*, mutta seitseman nimea yhdestatoista oli eri kuin
entryn oikeat pickit. Juurisyy ei ollut kortissa vaan ketjussa:
`freeze_model_squad_gw.py` perii rungon EDELLISESTA FREEZESTA
(`_prev_freeze`), ei koskaan FPL:sta. Ketju lahti GW1:n optimoijan rungosta ja
erosi entrysta lopullisesti kun entry pelasi wildcardin GW2:ssa. Mitattu 4.9:
gw2.json vs entry 116920 GW2-pickit = 7/15 yhteista.

Kukaan ei huutanut, koska jokainen lenkki oli sisaisesti johdonmukainen ja
jokainen portti verifioi luvut SAMASTA vaarasta artefaktista.

Tama moduuli on se yksi lukija. Vertailu on puhdas funktio (ei verkkoa, ei
levya), jotta se voidaan ajaa fikstuureilla jokaisessa kauden vaiheessa; haku
on erikseen ja FAIL-CLOSED: jos entryn rivia ei saada, vastaus ei ole "ei
eroa" vaan "ei tiedeta", ja kutsuja kaatuu.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import requests

FPL_BASE = "https://fantasy.premierleague.com/api"
FPL_HEADERS = {"User-Agent": "Mozilla/5.0 (GoalIQ model-entry check)"}

# Entry EI ole kovakoodattu vaan ymparistosta - sama arvo kuin
# scripts/verify_model_entry_matches_freeze.py:ssa.
ENTRY_ID = int(os.environ.get("FPL_MODEL_ENTRY_ID", "116920"))


def squad_ids(frozen: dict) -> set[int]:
    """Jaadytetyn rungon 15 pelaajaa. XI + penkki, ei kumpaakaan yksin:
    kattorike tai vieras nimi voi olla kokonaan penkilla."""
    rows = list(frozen.get("xi") or []) + list(frozen.get("bench") or [])
    return {int(p["id"]) for p in rows if p.get("id") is not None}


def picks_ids(picks: list[dict]) -> set[int]:
    """FPL:n `entry/<id>/event/<gw>/picks` -> pelaajajoukko."""
    return {int(p["element"]) for p in picks or [] if p.get("element") is not None}


def squad_names(frozen: dict) -> dict[int, str]:
    rows = list(frozen.get("xi") or []) + list(frozen.get("bench") or [])
    return {int(p["id"]): str(p.get("web_name") or p["id"]) for p in rows
            if p.get("id") is not None}


@dataclass(frozen=True)
class Ero:
    """Rungon ja entryn ero. `sama` on ainoa hyvaksytty tila."""

    puuttuu: frozenset[int] = field(default_factory=frozenset)   # rungossa, ei entryssa
    ylimaaraiset: frozenset[int] = field(default_factory=frozenset)  # entryssa, ei rungossa

    @property
    def sama(self) -> bool:
        return not self.puuttuu and not self.ylimaaraiset

    @property
    def yhteisia(self) -> int:
        return 15 - len(self.puuttuu)

    def kuvaus(self, nimet: dict[int, str] | None = None) -> str:
        nimet = nimet or {}
        osat = []
        if self.puuttuu:
            osat.append("rungossa mutta EI entryssa: " + ", ".join(
                "%s (%d)" % (nimet.get(i, i), i) for i in sorted(self.puuttuu)))
        if self.ylimaaraiset:
            osat.append("entryssa mutta EI rungossa: " + ", ".join(
                str(i) for i in sorted(self.ylimaaraiset)))
        return " | ".join(osat) or "ei eroa"


def vertaa(runko_ids: set[int], entry_ids: set[int]) -> Ero:
    """Puhdas vertailu. Ei tietoa siita MIKSI ne eroavat - se on kutsujan asia."""
    return Ero(puuttuu=frozenset(runko_ids - entry_ids),
               ylimaaraiset=frozenset(entry_ids - runko_ids))


def latest_played_gw(events: list[dict]) -> int | None:
    """Suurin kierros jonka deadline on mennyt JA joka on paattynyt.

    `finished` yksin ei riita kauden alussa (kaikki ovat False) eika
    `is_previous` ole luotettava kesken kierroksen. Ilman pelattua kierrosta
    entrylla ei ole julkisia pickseja lainkaan -> None, ja kutsuja paattaa
    mita se tarkoittaa (kauden ensimmainen freeze ei voi verrata mihinkaan).
    """
    pelatut = [int(e["id"]) for e in events or []
               if e.get("finished") and e.get("id") is not None]
    return max(pelatut) if pelatut else None


class EntryHakuVirhe(RuntimeError):
    """Entryn rivia EI saatu. Ei sama asia kuin "ei eroa"."""


def fetch_picks(entry: int, gw: int, *, timeout: int = 30) -> list[dict]:
    """FPL:n pickit. Kaikki virheet -> poikkeus (FAIL-CLOSED).

    404 on erikseen mainittu, koska se on odotettavissa ennen kierroksen
    deadlinea (FPL piilottaa pickit deadlineen asti) - mutta se ei silti
    tarkoita etta rivit tasmaavat.
    """
    url = "%s/entry/%d/event/%d/picks/" % (FPL_BASE, entry, gw)
    try:
        r = requests.get(url, headers=FPL_HEADERS, timeout=timeout)
    except Exception as e:  # verkko alhaalla, DNS, timeout
        raise EntryHakuVirhe("verkkovirhe %s: %r" % (url, e)) from e
    if r.status_code == 404:
        raise EntryHakuVirhe(
            "404 %s - entrylla ei ole GW%d-rivia (kierrosta ei ole pelattu "
            "tai entry-id on vaara)" % (url, gw))
    if r.status_code != 200:
        raise EntryHakuVirhe("HTTP %s %s" % (r.status_code, url))
    try:
        return r.json().get("picks") or []
    except Exception as e:
        raise EntryHakuVirhe("JSON-virhe %s: %r" % (url, e)) from e
