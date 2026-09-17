# -*- coding: utf-8 -*-
"""Yksi lukija mallin kierrospistesarjoille (KAKSI-GRADERIA-YKSI-TIEDOSTO, 17.9.2026).

TAUSTA, MITATTU 12.9. `data/model_squad_gw_scores.json`:iin kirjoitti KAKSI
skriptia CI:sta:

  * `scripts/grade_model_squad.py`     entry-pohjainen (FPL-entryn oma historia
                                        + picks), `model-squad-grade.yml` cron
                                        `17 */6`, YLIKIRJOITTAA koko tiedoston,
                                        rivit ILMAN source-kenttaa
  * `scripts/grade_model_squad_gw.py`  freeze-pohjainen (jaadytetty runko +
                                        live-pisteet + autosub-saannot),
                                        `fpl-data-refresh.yml` cron `0 */3`,
                                        APPEND-ONLY, `source: frozen_squad`

Sama GW3 olisi entrysta 72 p ja freezesta 63 p. Kumpi ehtii ensin ratkesi
cron-jarjestyksesta, ja sekaprovenienssi on TARTTUVA: entry-graderi ohittaa
rivin jolla ei ole `provisional`-kenttaa (`.get()` -> None -> "jo lopullinen"),
joten kerran sarjaan paassyt freeze-rivi jaisi sinne pysyvasti eika mikaan
huutaisi.

RAKENNE, EI SOPIMUS (CLAUDE.md 6a):

  (1) YKSI LUKIJA. `load_gw_scores(path, source=...)` on ainoa tapa lukea
      sarja, eika se voi palauttaa sekasarjaa: kahta provenienssia samassa
      tiedostossa -> `ProvenienssiRistiriita`. Molemmat kirjoittajat lukevat
      sen kautta ENNEN kirjoitusta ja ajavat tuloksensa `validate_gw_scores`in
      lapi ENNEN kirjoitusta. Kutsupaikkaportti on
      tests/test_model_squad_scores_provenance.py: se ajaa molemmat skriptit
      sekasarjaa vasten ja vaatii kieltaytymisen.

  (2) KAKSI TIEDOSTOA. Entry-sarja on `ENTRY_SCORES_PATH`, freeze-sarja on
      `FROZEN_SCORES_PATH`. Kirjoittaja nimeaa oman provenienssinsa lukijalle,
      ja lukija kieltaytyy antamasta sille toisen provenienssin tiedostoa.
      Sekoitus ei ole "kielletty" vaan mahdoton: vaikka polut osoitettaisiin
      ristiin, lukija kaatuu ennen kuin mitaan kirjoitetaan.

  (3) POIKKEUSLISTA PERUSTELUINEEN. Rivi ilman `source`-kenttaa on legacy ja
      luetaan entryksi (`LEGACY_SOURCELESS`) - mutta vain jos sen muoto on
      entry-graderin muoto. Freeze-graderin sormenjalki (`FROZEN_FINGERPRINT`)
      rivilla jolla ei ole `source`a on ristiriita, ei legacy. Elavan
      tiedoston legacy-rivit on lueteltu testissa perusteluineen; uusi
      source-ton rivi kaataa testin, ja migroitu rivi kaataa sen
      vanhentuneena.

KANONINEN PROVENIENSSI KAUDELLA 2026/27 = `entry` (`CANONICAL_SOURCE`,
Villen paatos 12.9.2026). GW1-GW4 on gradattu entrysta, ja se on sarja jonka
Season race, tuloskortti ja recap lukevat. Freeze-sarja on diagnostiikkaa
(mita jaadytetty runko OLISI tehnyt) omassa tiedostossaan, eika sita lueta
julkiselle pinnalle.

MIGRAATIO (ei ajeta automaattisesti). Levyn GW1-GW4-rivit ovat tuotantodataa.
`stamp_legacy_source(doc)` on puhdas funktio joka lisaa niille
`source: "entry"` ja metaan `series_source: "entry"` muuttamatta mitaan muuta;
sen ajaminen elavaan tiedostoon on Villen GO. Siihen asti lukija hyvaksyy
legacy-rivit yllä olevalla saannolla.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import config

SOURCE_ENTRY = "entry"
SOURCE_FROZEN = "frozen_squad"
SOURCES = frozenset({SOURCE_ENTRY, SOURCE_FROZEN})

# 🔴 KANONINEN PROVENIENSSI. Villen paatos 12.9.2026, toteutettu rakenteena:
# julkinen sarja on entry-sarja. Jos tama joskus vaihtuu, vaihda vakio JA
# kirjoita syy tahan - lukija, kirjoittajat ja testit lukevat tata yhta kohtaa.
CANONICAL_SOURCE = SOURCE_ENTRY
CANONICAL_DECISION = (
    "Villen paatos 12.9.2026: mallin julkinen kierrossarja gradataan FPL-entryn "
    "omista pisteista (grade_model_squad.py). GW1-GW4 on gradattu entrysta. "
    "Jaadytetty gw4.json on runko jota malli ei voi saavuttaa (8/15 vaihtui, "
    "transfers=[]), ja freeze-graderin GW3 olisi 63 p entryn 72 p:n sijaan; "
    "sama sarja ei voi sisaltaa molempia. Freeze-sarja on diagnostiikkaa "
    "omassa tiedostossaan (FROZEN_SCORES_PATH).")

ENTRY_SCORES_PATH = config.DATA_DIR / "model_squad_gw_scores.json"
FROZEN_SCORES_PATH = config.DATA_DIR / "model_squad_frozen_gw_scores.json"
SERIES_PATHS = {SOURCE_ENTRY: ENTRY_SCORES_PATH, SOURCE_FROZEN: FROZEN_SCORES_PATH}

# Rivi ilman source-kenttaa. Perustelu: kentta lisattiin 17.9.2026, ja siihen
# asti AINOA kirjoittaja joka ei kirjoittanut sita oli entry-graderi
# (freeze-graderi on kirjoittanut `source: frozen_squad` 12.9 alkaen,
# fp c1781285f, eika sita ennen koskaan ehtinyt kirjoittaa tahan tiedostoon:
# levyn GW1-GW4 kantavat entry-graderin kentat captain_id/transfer_cost/
# active_chip eivatka yhtaan freeze-graderin kenttaa). Saanto EI ole
# fail-open: source-ton rivi jolla on freeze-sormenjalki on ristiriita.
LEGACY_SOURCELESS = SOURCE_ENTRY

# Kentat joita VAIN freeze-graderi tuottaa (src/models/fpl_autosub.score_gw +
# grade_model_squad_gw.main). Entry-graderin rivilla ei ole yhtakaan naista.
FROZEN_FINGERPRINT = ("provenance", "points_before_captain", "captain_reason",
                      "frozen_at")


class SarjaVirhe(RuntimeError):
    """Sarjaa ei voi lukea luotettavasti. Kirjoittaja ei saa jatkaa."""


class ProvenienssiRistiriita(SarjaVirhe):
    """Sarjassa on kahta provenienssia, tai se ei ole kutsujan sarja."""


def row_source(row: dict) -> str:
    """Yhden rivin provenienssi. Source-ton rivi on legacy-entry vain jos sen
    muoto on entry-graderin muoto."""
    s = row.get("source")
    if s is None:
        vieraat = [k for k in FROZEN_FINGERPRINT if k in row]
        if vieraat:
            raise ProvenienssiRistiriita(
                f"GW{row.get('gw')}: rivilla ei ole source-kenttaa mutta se "
                f"kantaa freeze-graderin kenttia {vieraat}. Legacy-saanto "
                f"(source puuttuu = {LEGACY_SOURCELESS}) ei koske sita.")
        return LEGACY_SOURCELESS
    if s not in SOURCES:
        raise ProvenienssiRistiriita(
            f"GW{row.get('gw')}: tuntematon source {s!r}; sallitut "
            f"{sorted(SOURCES)}.")
    return s


def series_source(doc: dict) -> str | None:
    """Sarjan provenienssi tai None jos sarja on tyhja eika meta sano mitaan.

    Kaatuu jos riveilla on kahta provenienssia, jos meta vaittaa muuta kuin
    rivit, tai jos rivit eivat ole kelvollisia (gw puuttuu / toistuu).
    """
    rows = doc.get("gameweeks")
    if not isinstance(rows, list):
        raise SarjaVirhe("gameweeks puuttuu tai ei ole lista.")
    per_gw: dict[int, str] = {}
    for r in rows:
        if not isinstance(r, dict):
            raise SarjaVirhe(f"rivi ei ole objekti: {r!r}")
        try:
            gw = int(r["gw"])
        except (KeyError, TypeError, ValueError):
            raise SarjaVirhe(f"rivilta puuttuu gw: {r!r}") from None
        if gw in per_gw:
            raise SarjaVirhe(f"GW{gw} esiintyy sarjassa kahdesti.")
        per_gw[gw] = row_source(r)
    sources = set(per_gw.values())
    if len(sources) > 1:
        jako = ", ".join(f"GW{g}={s}" for g, s in sorted(per_gw.items()))
        raise ProvenienssiRistiriita(
            f"sekaprovenienssi: sarjassa on {sorted(sources)} ({jako}). "
            f"Kanoninen sarja on {CANONICAL_SOURCE}; toisen graderin rivit "
            f"kuuluvat omaan tiedostoonsa.")
    meta_src = (doc.get("meta") or {}).get("series_source")
    if meta_src is not None and meta_src not in SOURCES:
        raise ProvenienssiRistiriita(
            f"meta.series_source={meta_src!r} ei ole sallittu provenienssi.")
    if meta_src is not None and sources and meta_src not in sources:
        raise ProvenienssiRistiriita(
            f"meta sanoo series_source={meta_src!r} mutta rivit ovat "
            f"{sorted(sources)}.")
    if sources:
        return next(iter(sources))
    return meta_src


def validate_gw_scores(doc: dict, *, source: str) -> dict:
    """Portti ennen kirjoitusta: doc on yhden provenienssin sarja JA se
    provenienssi on kutsujan oma. Palauttaa docin muuttamatta sita."""
    if source not in SOURCES:
        raise ProvenienssiRistiriita(f"kutsujan source {source!r} ei ole sallittu.")
    found = series_source(doc)
    if found is not None and found != source:
        raise ProvenienssiRistiriita(
            f"sarja on {found!r}-provenienssin sarja, mutta kirjoittaja on "
            f"{source!r}. Kirjoittajan oma tiedosto on "
            f"{SERIES_PATHS[source].name}.")
    return doc


def empty_gw_scores(source: str) -> dict:
    if source not in SOURCES:
        raise ProvenienssiRistiriita(f"source {source!r} ei ole sallittu.")
    return {"meta": {"series_source": source}, "gameweeks": []}


def load_gw_scores(path, *, source: str) -> dict:
    """Ainoa lukija. Puuttuva tiedosto on tyhja sarja kutsujan provenienssilla;
    rikkinainen tiedosto KAATUU (kirjoittaja ei saa kirjoittaa tyhjaa paalle);
    toisen provenienssin tai sekasarja KAATUU.

    Palautettu doc kantaa aina `meta.series_source`-kentan, jotta kirjoittaja
    ei voi kirjoittaa sarjaa joka ei sano provenienssiaan.
    """
    p = Path(path)
    if not p.exists():
        return empty_gw_scores(source)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SarjaVirhe(
            f"{p.name}: sarjaa ei voi lukea ({e!r}); ei kirjoiteta paalle.") from e
    if not isinstance(doc, dict):
        raise SarjaVirhe(f"{p.name}: juuri ei ole objekti.")
    validate_gw_scores(doc, source=source)
    meta = doc.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        doc["meta"] = meta
    meta.setdefault("series_source", source)
    return doc


def sourceless_gws(doc: dict) -> list[int]:
    """Kierrokset joiden rivilla ei ole source-kenttaa (poikkeuslistan mittari)."""
    return sorted(int(r["gw"]) for r in (doc.get("gameweeks") or [])
                  if isinstance(r, dict) and r.get("source") is None)


def stamp_legacy_source(doc: dict) -> dict:
    """Migraatio, puhdas: kopio jossa source-ttomat entry-muotoiset rivit saavat
    `source: entry` ja meta `series_source: entry`. Kaatuu jos joku source-ton
    rivi ei ole entry-muotoinen. EI aja itseaan - elavan tiedoston muutos on GO."""
    out = copy.deepcopy(doc)
    for r in out.get("gameweeks") or []:
        if r.get("source") is None:
            r["source"] = row_source(r)
    validate_gw_scores(out, source=LEGACY_SOURCELESS)
    out.setdefault("meta", {})["series_source"] = LEGACY_SOURCELESS
    return out
