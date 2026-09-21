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

KANONINEN PROVENIENSSI KAUDELLA 2026/27 = `frozen_squad` (`CANONICAL_SOURCE`,
Villen paatos 21.9.2026, kumoaa 12.9:n `entry`-paatoksen). Julkinen track
record, Season race, tuloskortti ja recap mittaavat MALLIN JAADYTETTYA rivia
FPL:n live-pisteilla, eivat entrya 116920. Syy: 18.9 Ville ajoi GW5:n
jaadytetyn rivin yli (De Cuyper XI:iin Bobby Thomasin tilalle), ja entry-sarja
mittasi silloin mallin ja Villen yhdistelmaa vaikka copy sanoi "the model's
squad". Entry saa poiketa; ero kirjataan riville (`entry_diverged`).

(4) YKSI JULKINEN LUKIJA. Pinnat lukevat mallin kierrospisteet VAIN
`load_public_model_series()`:lla. Se palauttaa jaadytetyn sarjan, ja
entry-rivin ainoastaan kierrokselle jonka freeze on rakenteellisesti
epakelpo (`freeze_invalid`) JA jolle on kirjattu Villen poikkeuspaatos
(`data/model_squad_exceptions/gw{N}.json`) - rivi kantaa silloin
`row_basis: "entry_fallback"` ja syyn. Portti:
tests/test_model_series_reader_discipline.py (raaka luku kummastakin
sarjatiedostosta pinnan koodissa kaataa testin).

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

# 🔴 KANONINEN PROVENIENSSI. Villen paatos 21.9.2026, toteutettu rakenteena:
# julkinen sarja on JAADYTETYN rivin sarja. Jos tama joskus vaihtuu, vaihda
# vakio JA kirjoita syy tahan - lukija, kirjoittajat ja testit lukevat tata
# yhta kohtaa.
#
# Historia: 12.9.2026 paatos oli `entry` ("GW1-GW4 on gradattu entrysta;
# gw4.json on runko jota malli ei voi saavuttaa"). GW4:n osalta se paatos
# elaa yha poikkeuspaatoksena `model_squad_exceptions/gw4.json`, jota
# julkinen lukija kunnioittaa (`row_basis: entry_fallback`).
CANONICAL_SOURCE = SOURCE_FROZEN
CANONICAL_DECISION = (
    "Villen paatos 21.9.2026: mallin julkinen kierrossarja on JAADYTETTY rivi "
    "FPL:n live-pisteilla (autosubit ja kapteeni/vara FPL:n saannoin, ei "
    "chippeja: malli ei pelaa chippeja v0:ssa, chip_evaluation.decision = "
    "not_played). Entry 116920 saa poiketa, ja ero kirjataan riville. "
    "Kierros jonka freeze on rakenteellisesti epakelpo (squad_rebuilt) luetaan "
    "entrysta VAIN jos sille on kirjattu Villen poikkeuspaatos.")

ENTRY_SCORES_PATH = config.DATA_DIR / "model_squad_gw_scores.json"
FROZEN_SCORES_PATH = config.DATA_DIR / "model_squad_frozen_gw_scores.json"
SERIES_PATHS = {SOURCE_ENTRY: ENTRY_SCORES_PATH, SOURCE_FROZEN: FROZEN_SCORES_PATH}
FROZEN_DIR = config.DATA_DIR / "model_squad_frozen"
EXCEPTIONS_DIR = config.DATA_DIR / "model_squad_exceptions"

# Rivin perusta julkisessa sarjassa. `frozen` = jaadytetty rivi FPL:n
# pisteilla. `entry_fallback` = kirjattu poikkeus (ks. `freeze_invalid`).
ROW_BASIS_FROZEN = "frozen"
ROW_BASIS_ENTRY_FALLBACK = "entry_fallback"

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
#
# 🔴 TAMA TUPLE ON VARTIJA, JA SEN OLEMASSAOLO MITATAAN (loydos 18.9.2026).
# Ennen: `FROZEN_FINGERPRINT = ()` poisti seka vartijan etta sita vartioivan
# testin, koska testi oli parametrisoitu taman tuplen yli ja tyhja
# parametrisointi on pytestille SKIP eika FAIL (mitattu: 31 passed,
# 2 skipped, exit 0). Nyt tuplea vartioivat KAKSI ei-parametrisoitua testia
# jotka ajavat molemmat graderit ja vertaavat tuplen TODELLISIIN riveihin:
#   tests/test_model_squad_scores_provenance.py
#     ::test_freeze_rivi_jolta_source_putosi_ei_lue_entryksi
#     ::test_sormenjalkivartija_on_olemassa_ja_erottaa_graderit
# Tuple on tasan freeze-rivin kentat miinus entry-rivin kentat; jos jompaan
# kumpaan graderiin lisataan kentta, jalkimmainen testi kaatuu ja kirjoittaja
# joutuu paattamaan onko uusi kentta sormenjalki vai ei. `xi_ids` (fpl_autosub
# .score_gw) loytyi juuri siten: se oli freeze-only mutta puuttui tuplesta.
FROZEN_FINGERPRINT = ("provenance", "points_before_captain", "captain_reason",
                      "frozen_at", "xi_ids",
                      # 21.9.2026: jaadytetty graderi kirjaa hitin lahteen ja
                      # entryn eron riville (Villen paatos "mallin rivi").
                      "transfer_cost_source", "entry_diverged", "entry_diff")


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


# ---------------------------------------------------------------------------
# JULKINEN MALLISARJA (Villen paatos 21.9.2026: "mallin rivi")
# ---------------------------------------------------------------------------

EXCEPTION_KEYS = ("gw", "reason", "decided_by", "decided_at")


def valid_exception(d, gw: int) -> tuple[dict | None, str | None]:
    """(poikkeus, virhe). Sama saanto kuin verify-vahdilla: voimassa vain jos
    kaikki kentat ovat epatyhjia ja gw on tasmalleen tama kierros. Vajaa
    poikkeus on virhe, ei vapaakortti."""
    if not isinstance(d, dict):
        return None, f"GW{gw}: poikkeus ei ole objekti"
    puuttuu = [k for k in EXCEPTION_KEYS if not str(d.get(k) or "").strip()]
    if puuttuu:
        return None, f"GW{gw}: poikkeuksen kentat puuttuvat: {', '.join(puuttuu)}"
    try:
        if int(d.get("gw")) != int(gw):
            return None, f"GW{gw}: poikkeuksen gw={d.get('gw')}"
    except (TypeError, ValueError):
        return None, f"GW{gw}: poikkeuksen gw ei ole luku"
    return d, None


def freeze_invalid(frozen: dict, *, earlier_exists: bool) -> str | None:
    """Syy jos jaadytetty runko EI ole mallin saavutettavissa oleva rivi.

    `squad_rebuilt: true` (tai uudempi `squad_source: "free_optimum"`)
    tarkoittaa etta freeze putosi vapaaseen optimiin eika jatkanut ketjua:
    mitattu gw4.json 12.9 - 8/15 vaihtui samalla kun meta sanoo transfers [].
    Kauden ENSIMMAINEN freeze on vapaa optimi luonnostaan (ei edellista
    runkoa), joten se ei ole epakelpo - siksi `earlier_exists`.
    """
    meta = (frozen or {}).get("meta") or {}
    if not earlier_exists:
        return None
    if meta.get("squad_source") == "free_optimum" or meta.get("squad_rebuilt") is True:
        return (f"GW{meta.get('gw')}: freeze putosi vapaaseen optimiin "
                f"(squad_rebuilt={meta.get('squad_rebuilt')!r}, "
                f"squad_source={meta.get('squad_source')!r}), eli runko ei "
                f"jatka mallin ketjua")
    return None


def _frozen_public_row(r: dict, freeze: dict | None) -> tuple[dict | None, str | None]:
    gw = int(r["gw"])
    kustannus = r.get("transfer_cost")
    lahde = r.get("transfer_cost_source")
    if kustannus is None:
        # 21.9 ENNEN gradatut freeze-rivit (GW3) eivat kanna kustannusta.
        # Hyvaksytaan vain jos freezen oma meta sanoo nolla hittia; muuten
        # rivi jaa pois eika siita arvata lukua.
        hitit = ((freeze or {}).get("meta") or {}).get("hits")
        if hitit in (0, None) and freeze is not None:
            kustannus, lahde = 0, "freeze_hits_zero_legacy"
        else:
            return None, (f"GW{gw}: rivilta puuttuu transfer_cost ja freezen "
                          f"hits={hitit!r}; lukua ei arvata")
    return {
        "gw": gw,
        "points": int(r.get("points") or 0),
        "transfer_cost": int(kustannus),
        "transfer_cost_source": lahde,
        "active_chip": None,
        "provisional": False,
        "fpl_average": r.get("fpl_average"),
        "captain_id": r.get("captain_id"),
        "captain_reason": r.get("captain_reason"),
        "captain_points_added": r.get("captain_points_added"),
        "bench_points": r.get("bench_points"),
        "autosubs": r.get("autosubs") or [],
        "graded_at": r.get("graded_at"),
        "source": SOURCE_FROZEN,
        "row_basis": ROW_BASIS_FROZEN,
        # None = eroa ei mitattu (ennen 21.9 gradattu rivi); True/False mitattu.
        "entry_diverged": r.get("entry_diverged"),
        "entry_diff": r.get("entry_diff"),
    }, None


def public_model_series(frozen_doc: dict, entry_doc: dict,
                        freezes: dict[int, dict],
                        exceptions: dict[int, dict]) -> dict:
    """Puhdas ydin: julkinen mallisarja yhdesta paikasta.

    Jaadytetty sarja on runko. Entry-rivi otetaan VAIN kierrokselle jonka
    freeze on `freeze_invalid` JA jolle on kelvollinen poikkeuspaatos -
    silloin rivi sanoo sen itse (`row_basis`, `fallback_reason`). Mikaan muu
    polku ei tuo entry-lukua sarjaan, joten Villen yliajo ei voi siirtya
    mallin lukuun.
    """
    validate_gw_scores(frozen_doc, source=SOURCE_FROZEN)
    validate_gw_scores(entry_doc, source=SOURCE_ENTRY)
    rows: dict[int, dict] = {}
    missing: dict[int, str] = {}
    for r in frozen_doc.get("gameweeks") or []:
        gw = int(r["gw"])
        row, syy = _frozen_public_row(r, freezes.get(gw))
        if row is None:
            missing[gw] = syy
        else:
            rows[gw] = row
    entry_rows = {int(r["gw"]): r for r in entry_doc.get("gameweeks") or []}
    fallback = []
    ensimmainen = min(freezes) if freezes else None
    for gw in sorted(freezes):
        if gw in rows:
            continue
        syy = freeze_invalid(freezes[gw],
                             earlier_exists=(ensimmainen is not None
                                             and gw > ensimmainen))
        if syy is None:
            continue            # kelvollinen freeze, ei viela gradattu
        if gw in exceptions:
            exc, virhe = valid_exception(exceptions.get(gw), gw)
        else:
            exc, virhe = None, None
        if virhe:
            missing[gw] = virhe
            continue
        if exc is None:
            missing[gw] = f"{syy}; poikkeuspaatosta ei ole kirjattu"
            continue
        e = entry_rows.get(gw)
        if e is None:
            missing[gw] = f"{syy}; entry-rivia ei ole viela gradattu"
            continue
        rows[gw] = {
            "gw": gw,
            "points": int(e.get("points") or 0),
            "transfer_cost": int(e.get("transfer_cost") or 0),
            "transfer_cost_source": "entry",
            "active_chip": e.get("active_chip"),
            "provisional": bool(e.get("provisional")),
            "fpl_average": e.get("fpl_average"),
            "captain_id": e.get("captain_id"),
            "captain_reason": None,
            "captain_points_added": e.get("captain_points_added"),
            "bench_points": e.get("bench_points"),
            "autosubs": e.get("autosubs") or [],
            "graded_at": e.get("graded_at"),
            "source": SOURCE_ENTRY,
            "row_basis": ROW_BASIS_ENTRY_FALLBACK,
            "fallback_reason": str(exc["reason"]),
            "fallback_decided": f"{exc['decided_by']} {exc['decided_at']}",
            "entry_diverged": False,
            "entry_diff": None,
        }
        fallback.append(gw)
    return {
        "meta": {
            "series_source": CANONICAL_SOURCE,
            "decision": CANONICAL_DECISION,
            "fallback_gws": fallback,
            "missing_gws": {str(k): v for k, v in sorted(missing.items())},
            # Entry EI ole mallin rivin tarkistusreitti taman sarjan
            # riveille. Rivin `entry_diverged is False` kertoo milloin se on.
            "entry_id": None,
        },
        "gameweeks": [rows[g] for g in sorted(rows)],
    }


def _read_dir(d) -> dict[int, dict]:
    import re
    out: dict[int, dict] = {}
    if not Path(d).exists():
        return out
    for p in sorted(Path(d).glob("gw*.json")):
        m = re.fullmatch(r"gw(\d+)\.json", p.name)
        if not m:
            continue
        try:
            out[int(m.group(1))] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SarjaVirhe(f"{p.name}: ei luettavissa ({e!r})") from e
    return out


def load_public_model_series(*, frozen_path=None, entry_path=None,
                             frozen_dir=None, exceptions_dir=None) -> dict:
    """AINOA lukija jolla pinta saa lukea mallin kierrospisteet.

    Kaatuu `SarjaVirhe`en jos jokin lahde on rikki - pinta paattaa itse onko
    se "ei saatavilla" (fail-closed), eika lukija palauta osittaista sarjaa.
    Parametrit ovat testeja varten; tuotanto kayttaa oletuspolkuja.
    """
    fp = Path(frozen_path or FROZEN_SCORES_PATH)
    ep = Path(entry_path or ENTRY_SCORES_PATH)
    frozen_doc = load_gw_scores(fp, source=SOURCE_FROZEN)
    entry_doc = load_gw_scores(ep, source=SOURCE_ENTRY)
    return public_model_series(frozen_doc, entry_doc,
                               _read_dir(frozen_dir or FROZEN_DIR),
                               _read_dir(exceptions_dir or EXCEPTIONS_DIR))


def provisional_hint_gws() -> list[int]:
    """Entry-graderin `meta.provisional_gws`, VAIN epavarmuuden lisaamiseen.

    `fpl_gw_finality.provisional_gws` lukee lopullisuuden FPL:n `events`ista;
    tama lista saa ainoastaan lisata kierroksia provisionaalisiksi, ei
    poistaa (A1, 7.9). Se ei ole mallin pistesarja, mutta se on sama
    tiedosto, joten sekin luetaan taalta eika pinnan omalla json-luvulla.
    Rikkinainen tai puuttuva tiedosto = tyhja vihje (FPL on paalahde).
    """
    try:
        doc = load_gw_scores(ENTRY_SCORES_PATH, source=SOURCE_ENTRY)
    except SarjaVirhe:
        return []
    raaka = (doc.get("meta") or {}).get("provisional_gws") or []
    out = []
    for g in raaka:
        try:
            out.append(int(g))
        except (TypeError, ValueError):
            continue
    return out
