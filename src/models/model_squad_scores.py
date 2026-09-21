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

(4) KAKSI JULKISTA LUKIJAA, EI SEKOITUSTA (Villen paatos 21.9: "molemmat
sarjat, malli ensin"). Pinnat lukevat mallin pisteet VAIN
`load_public_model_series()`:lla (jaadytetty rivi; epakelpo freeze = kierros
pois, `unscored_gws`) ja entryn 116920 pisteet VAIN
`load_public_entry_series()`:lla, omana sarjanaan. Portti:
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
# gw4.json on runko jota malli ei voi saavuttaa"). 21.9 GW4 jaa MALLIN
# sarjasta pois (freeze epakelpo) eika saa entryn lukua korvikkeeksi; entryn
# luvut naytetaan erikseen `load_public_entry_series()`:lla.
CANONICAL_SOURCE = SOURCE_FROZEN
CANONICAL_DECISION = (
    "Villen paatos 21.9.2026: mallin julkinen kierrossarja on JAADYTETTY rivi "
    "FPL:n live-pisteilla (autosubit ja kapteeni/vara FPL:n saannoin, ei "
    "chippeja: malli ei pelaa chippeja v0:ssa, chip_evaluation.decision = "
    "not_played). Entry 116920 saa poiketa, ja ero kirjataan riville. "
    "Kierros jonka freeze on rakenteellisesti epakelpo (squad_rebuilt) jaa "
    "mallisarjasta pois (unscored_gws), EIKA saa entryn lukua. Entryn sarja "
    "naytetaan erikseen omalla nimellaan (miniliigan ratkaiseva sarja).")

ENTRY_SCORES_PATH = config.DATA_DIR / "model_squad_gw_scores.json"
FROZEN_SCORES_PATH = config.DATA_DIR / "model_squad_frozen_gw_scores.json"
SERIES_PATHS = {SOURCE_ENTRY: ENTRY_SCORES_PATH, SOURCE_FROZEN: FROZEN_SCORES_PATH}
FROZEN_DIR = config.DATA_DIR / "model_squad_frozen"

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
# JULKISET SARJAT (Villen paatos 21.9.2026: "molemmat sarjat, malli ensin")
# ---------------------------------------------------------------------------
#
# KAKSI SARJAA, KAKSI LUKIJAA, EI SEKOITUSTA:
#
#   `load_public_model_series()`  MALLIN jaadytetty rivi FPL:n pisteilla.
#                                 Tama on track record, Season racen
#                                 "Model"-luku ja tuloskortin mallisolu.
#   `load_public_entry_series()`  FPL-entry 116920: malli + Villen chip- ja
#                                 kokoonpanopaatokset. Tama ratkaisee Beat
#                                 the Model -miniliigan (FPL:n taulukko), ja
#                                 se naytetaan ERIKSEEN omalla nimellaan.
#
# Mallisarjaan ei tule entry-lukua MILLAAN polulla. Kierros jonka freeze on
# rakenteellisesti epakelpo (gw4.json) jaa sarjasta pois ja kirjataan
# `unscored_gws`iin koodilla - se ei saa entryn lukua korvikkeeksi, koska
# silloin mallin kausisumma sisaltaisi Villen kierroksen.

UNSCORED_NO_VALID_FREEZE = "no_valid_frozen_squad"
#: Pinnan nayttama koodi -> sen merkitys. Teksti renderoidaan pinnassa
#: (julkinen copy kulkee julkaisuportin kautta), payload kantaa vain koodin.
UNSCORED_CODES = frozenset({UNSCORED_NO_VALID_FREEZE})


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


def _frozen_public_row(r: dict, freeze: dict | None) -> dict:
    """Yksi jaadytetyn sarjan rivi julkiseen muotoon.

    Siirtokustannus: graderi kirjaa `transfer_cost`in ja sen lahteen, ja
    `None` tarkoittaa ettei kustannusta voitu todentaa FPL:n saannoilla -
    silloin rivi naytetaan BRUTTONA ja `transfer_cost_verified: False`
    sanoo sen (Villen paatos 21.9). 21.9 ENNEN gradatut rivit (GW3) eivat
    kanna kenttaa: nolla siirtoa freezessa = 0 todennetusti, muuten
    todentamaton. Lukua ei arvata kummassakaan suunnassa.
    """
    gw = int(r["gw"])
    if "transfer_cost" in r:
        kustannus = r.get("transfer_cost")
        lahde = r.get("transfer_cost_source")
    else:
        siirrot = ((freeze or {}).get("meta") or {}).get("transfers")
        if freeze is not None and siirrot is not None and len(siirrot) == 0:
            kustannus, lahde = 0, "no_transfers"
        else:
            kustannus, lahde = None, "unverified"
    return {
        "gw": gw,
        "points": int(r.get("points") or 0),
        "transfer_cost": None if kustannus is None else int(kustannus),
        "transfer_cost_verified": kustannus is not None,
        "transfer_cost_source": lahde,
        # Malli ei pelaa chippeja (freezen meta.chip None, chip_evaluation
        # decision not_played), joten mallisarjassa ei ole chippia.
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
        # None = eroa ei mitattu (ennen 21.9 gradattu rivi); True/False mitattu.
        "entry_diverged": r.get("entry_diverged"),
        "entry_diff": r.get("entry_diff"),
    }


def public_model_series(frozen_doc: dict, freezes: dict[int, dict]) -> dict:
    """Puhdas ydin: mallin julkinen sarja, vain jaadytetysta sarjasta.

    Ottaa vastaan VAIN jaadytetyn sarjan: entry-sarjaa ei edes anneta
    funktiolle, joten entryn luku ei voi paatya mallisarjaan millaan
    haaralla (rakenne, ei ehto).
    """
    validate_gw_scores(frozen_doc, source=SOURCE_FROZEN)
    rows = {}
    for r in frozen_doc.get("gameweeks") or []:
        rows[int(r["gw"])] = _frozen_public_row(r, freezes.get(int(r["gw"])))
    # Graderin diagnostinen luku epakelvolle freezelle (Villen paatos 21.9:
    # "pois summasta, syy JA luku nakyviin"). Luku tulee VAIN tasta listasta;
    # jos sita ei ole viela kirjattu, kentat ovat None eika pinta nayta lukua.
    diag = {int(u["gw"]): u for u in (frozen_doc.get("unscored") or [])
            if isinstance(u, dict) and u.get("gw") is not None}
    ensimmainen = min(freezes) if freezes else None
    unscored = []
    for gw in sorted(freezes):
        if gw in rows:
            continue
        if freeze_invalid(freezes[gw], earlier_exists=(ensimmainen is not None
                                                       and gw > ensimmainen)):
            d = diag.get(gw) or {}
            unscored.append({
                "gw": gw, "code": UNSCORED_NO_VALID_FREEZE,
                "would_have_scored": d.get("would_have_scored"),
                "fpl_average": d.get("fpl_average"),
            })
    # Kierrokset joilla mallin ketju aloitettiin uudelleen entryn rungosta
    # (freezen `squad_source: entry_picks` + `reseed`). Ilman selitysta GW3:n
    # 8/15 vaihtoa GW2:sta nayttaisi piilotetulta wildcardilta paneelissa
    # joka sanoo "no chips". Vain pisteytetyt kierrokset: selitys kuuluu
    # riville joka on nakyvissa.
    reseeded = []
    for gw in sorted(rows):
        meta = (freezes.get(gw) or {}).get("meta") or {}
        if meta.get("squad_source") != "entry_picks":
            continue
        lahde = (meta.get("reseed") or {}).get("source_gw")
        reseeded.append({"gw": gw,
                         "from_gw": int(lahde) if lahde is not None else gw - 1})
    return {
        "meta": {
            "series_source": CANONICAL_SOURCE,
            "decision": CANONICAL_DECISION,
            "unscored_gws": unscored,
            "reseeded_gws": reseeded,
        },
        "gameweeks": [rows[g] for g in sorted(rows)],
    }


def public_entry_series(entry_doc: dict) -> dict:
    """Puhdas ydin: FPL-entryn 116920 sarja omana sarjanaan.

    Tama on "our FPL entry (model + human chip calls)": entryn omat pisteet,
    chipit ja hitit sellaisenaan. Se ratkaisee Beat the Model -miniliigan,
    joten se naytetaan - mutta ERI nimella ja ERI kentassa kuin mallisarja.
    """
    validate_gw_scores(entry_doc, source=SOURCE_ENTRY)
    from src.models.fpl_model_entry import ENTRY_ID
    rows = []
    for r in sorted(entry_doc.get("gameweeks") or [], key=lambda x: int(x["gw"])):
        kustannus = int(r.get("transfer_cost") or 0)
        pisteet = int(r.get("points") or 0)
        rows.append({
            "gw": int(r["gw"]),
            "points": pisteet,
            "points_net": pisteet - kustannus,
            "transfer_cost": kustannus,
            "fpl_average": r.get("fpl_average"),
            "chip": r.get("active_chip"),
            "provisional": bool(r.get("provisional")),
        })
    return {"meta": {"series_source": SOURCE_ENTRY, "entry_id": ENTRY_ID},
            "gameweeks": rows}


#: Julkisen repon pysyva osoite. Jaadytetty rivi on todistettavissa sen
#: git-historiasta (commit ennen deadlinea).
REPO_BLOB = "https://github.com/GoalIQ/football-prediction/blob/main/"


def frozen_route(gw: int) -> dict:
    """Mallin luvun tarkistusreitti: pisteytetyt kierrokset julkisessa repossa.

    Julkaisuportti 21.9: reitti on `model_squad_frozen_gw_scores.json`, EI
    `model_squad_frozen/gw{n}.json` - rungoissa on suomenkielinen
    `meta.reseed.reason` eivatka ne nayta lukua. Pisteytetyssa tiedostossa
    on luku, `xi_ids` ja rungon jaadytyshetki.
    """
    gw = int(gw)
    return {"kind": "frozen_squad", "gw": gw,
            "url": f"{REPO_BLOB}data/model_squad_frozen_gw_scores.json"}


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


def load_public_model_series(*, frozen_path=None, frozen_dir=None) -> dict:
    """AINOA lukija jolla pinta saa lukea MALLIN kierrospisteet.

    Kaatuu `SarjaVirhe`en jos lahde on rikki - pinta paattaa itse onko se
    "ei saatavilla" (fail-closed), eika lukija palauta osittaista sarjaa.
    Parametrit ovat testeja varten; tuotanto kayttaa oletuspolkuja.
    """
    fp = Path(frozen_path or FROZEN_SCORES_PATH)
    frozen_doc = load_gw_scores(fp, source=SOURCE_FROZEN)
    return public_model_series(frozen_doc, _read_dir(frozen_dir or FROZEN_DIR))


def load_public_entry_series(*, entry_path=None) -> dict:
    """AINOA lukija jolla pinta saa lukea FPL-ENTRYN kierrospisteet."""
    ep = Path(entry_path or ENTRY_SCORES_PATH)
    return public_entry_series(load_gw_scores(ep, source=SOURCE_ENTRY))


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
