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


def public_picks_gw(meta: dict) -> int | None:
    """Viimeisin kierros jonka pickit FPL nayttaa julkisesti, tai None.

    🔴 MITATTU 4.9.2026 (julkaisuportin loydos). Ensimmainen versio luki taman
    `completed_gameweeks`in maksimista, ja se on VAARA lahde:

        completed_gameweeks = kierrokset joiden JOKAINEN ottelu on alkanut
        pickit muuttuvat julkisiksi jo DEADLINE-hetkella

    GW3:lla mitattuna ero on **46,0 tuntia**: deadline pe 4.9 17:30Z, viimeinen
    aloituspotku su 6.9 15:30Z. Nuo 46 tuntia ovat tasan se deadline-viikonloppu
    jolloin "mita malli omistaa talla viikolla" on elava kysymys, ja linkki
    olisi osoittanut edelliseen kierrokseen.

    `deadline_gameweek` on pienin kierros jonka deadline on VIELA edessa
    (build_fpl_phase0: ehto `d > now`), joten se kaantyy tasmalleen
    deadline-hetkella ja `deadline_gameweek - 1` on viimeisin julkinen.

    Kauden lopussa tulevia deadlineja ei ole -> `deadline_gameweek` puuttuu,
    jolloin viimeisin pelattu kierros on oikea vastaus. Ennen kauden
    ensimmaista deadlinea kumpikin on tyhja -> None, ja kutsujan on jatettava
    linkki tekematta eika arvattava numeroa.
    """
    dl = meta.get("deadline_gameweek")
    if isinstance(dl, int) and dl > 1:
        return dl - 1
    done = [g for g in (meta.get("completed_gameweeks") or [])
            if isinstance(g, int)]
    if done:
        return max(done)
    return None


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


# ---------------------------------------------------------------------------
# PROVENIENSSI (5.9.2026, KORTTI-PROVENIENSSI-PORTTI)
#
# Kortti joka sanoo "The model's own FPL squad - entry 116920" lupaa etta
# runko on entryn runko. 4.9 julkaisutarkistaja verifioi jokaisen kortin
# luvun artefaktia vasten ja antoi LAPI - samasta vaarasta artefaktista. Se
# tarkisti etta entry on olemassa, ei etta kortin joukkue on entryn joukkue.
#
# Tama on se yksi lukija. Runko on entryn runko VAIN jos jokin naista pitaa:
#   entry_verified      - verify_model_entry_matches_freeze totesi deadlinen
#                         jalkeen 15/15 + kapteeni ja kirjoitti sen metaan
#   entry_picks         - freeze siemennettiin entryn omista pickeista (reseed)
#   chain_from_verified - ketjun edellinen lenkki on entry_verified, eli malli
#                         jatkaa rungosta jonka entry todistetusti pelasi
# Kaikki muu (free_optimum, ketju verifioimattomasta lenkista, puuttuva
# meta) on None, ja kortin generaattori kaatuu. Juuri GW2->GW3-ketju 4.9 oli
# "chain" verifioimattomasta GW1:sta: se olisi ollut None.
# ---------------------------------------------------------------------------

PROVENANCE_VERIFIED = "entry_verified"
PROVENANCE_ENTRY_PICKS = "entry_picks"
PROVENANCE_CHAIN = "chain_from_verified"


def verified_record(gw: int, entry: int, *, squad_match: bool,
                    captain_match: bool, at: str, common: int) -> dict:
    """Metaan kirjoitettava tosiasia. `match` on True vain kun SEKA 15 ETTA
    kapteeni tasmaavat - kapteeni on kaksinkertainen pistevaikutus."""
    return {
        "gw": int(gw), "entry": int(entry), "at": str(at),
        "squad_match": bool(squad_match), "captain_match": bool(captain_match),
        "common": int(common),
        "match": bool(squad_match and captain_match),
    }


def _is_verified(frozen: dict | None) -> bool:
    meta = (frozen or {}).get("meta") or {}
    ev = meta.get("entry_verified") or {}
    try:
        return (ev.get("match") is True
                and int(ev.get("gw", -1)) == int(meta.get("gw", -2)))
    except (TypeError, ValueError):
        return False


def provenance(frozen: dict, prev: dict | None = None) -> str | None:
    """Puhdas funktio: onko tama runko entryn runko, ja milla perusteella.

    `prev` on `meta.from_gw`:n freeze (kutsuja lataa sen levylta). Ketju
    hyvaksytaan vain jos `prev` on tasmalleen `from_gw` JA verifioitu.
    """
    meta = frozen.get("meta") or {}
    if _is_verified(frozen):
        return PROVENANCE_VERIFIED
    if meta.get("squad_source") == PROVENANCE_ENTRY_PICKS:
        return PROVENANCE_ENTRY_PICKS
    if meta.get("squad_source") == "chain" and prev is not None:
        pm = prev.get("meta") or {}
        try:
            same_link = int(meta.get("from_gw", -1)) == int(pm.get("gw", -2))
        except (TypeError, ValueError):
            same_link = False
        if same_link and _is_verified(prev):
            return PROVENANCE_CHAIN
    return None


class ProvenienssiPuuttuu(RuntimeError):
    """Runko ei ole todistetusti entryn runko. Kortti ei saa vaittaa sita."""


def require_entry_provenance(frozen: dict, frozen_dir) -> str:
    """Kortin generaattorin portti: palauttaa perusteen tai kaatuu.

    Lataa `from_gw`:n freezen `frozen_dir`:sta itse, jotta kutsujan ei
    tarvitse muistaa - unohdettu parametri olisi sama vika uudestaan.
    """
    import json
    from pathlib import Path

    meta = frozen.get("meta") or {}
    prev = None
    fg = meta.get("from_gw")
    if isinstance(fg, int):
        pp = Path(frozen_dir) / f"gw{fg}.json"
        if pp.exists():
            prev = json.loads(pp.read_text(encoding="utf-8"))
    peruste = provenance(frozen, prev)
    if peruste is None:
        raise ProvenienssiPuuttuu(
            f"GW{meta.get('gw')}: runko ei ole todistetusti entry {ENTRY_ID}:n "
            f"runko (squad_source={meta.get('squad_source')!r}, from_gw={fg!r}, "
            f"entry_verified={bool(meta.get('entry_verified'))}, edellinen "
            f"verifioitu={_is_verified(prev)}). Kortti lupaa entryn rungon, "
            "joten sita ei renderoida. Aja verify_model_entry_matches_freeze "
            "deadlinen jalkeen tai siemenna freeze entryn pickeista.")
    return peruste
