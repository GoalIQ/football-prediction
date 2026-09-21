# -*- coding: utf-8 -*-
"""UEFAn oma ottelurajapinta: CL, EL ja ECL karsintoineen, avaimeton.

MIKSI (21.9.2026, UCL-KATTAVUUS-ILMAISELLA-DATALLA). CL-mallin data tuli
kahdesta lahteesta joista kumpikaan ei nae koko kuvaa:

  football-data.org (CL)   vain sarjavaihe ja pudotuspelit, EI karsintoja,
                           ja ilmaistason kiintio (10/min) on jaettu koko
                           tuotannon kanssa
  openfootball txt (EL/ECL) 2023-26, ei kuluvaa kautta

Tulos 21.9: LASKilla oli mallissa YKSI ottelu, Vikingilla viisi ja Sabahilla
yksitoista - ja Sabah oli julkisessa ennusteessa 46 %:n kotisuosikki Slavia
Prahaa vastaan, koska ohut rating kutistuu CL:n keskitasolle. UEFAn oma
rajapinta (`match.uefa.com/v5/matches`, sama taho jonka Fantasy-syotetta
ingest_ucl.py jo lukee) antaa samoille seuroille 19 (Sabah), 35 (Slovan),
41 (Bodo/Glimt) ottelua kolmelta kaudelta, kuluvan kauden karsinnat mukaan
lukien.

TULOS ON 90 MINUUTIN TULOS (`score.regular`), ei jatkoajan: sama normi kuin
mallin muissa riveissa. Jatkoaika on eri peli (vasyneet joukkueet, eri
riskit), ja sen maalit vaaristaisivat maaliodotusta.

NIMET. Rivissa kulkee UEFAn seura-ID ja kolme nimivaihtoehtoa, koska
UEFAn nimet eivat ole samaa nimiavaruutta kuin kotiliigojen ('LASK' vs
'LASK Linz', 'Lille' vs 'Lille OSC', 'Atleti'). Oikea nimi valitaan fitissa
(`ratkaise_nimet`) kun kotiliigojen ja football-data.orgin nimet ovat
kasilla. Ilman sita sama seura olisi kahtena entiteettina: UEFA-nimi ilman
kotiliigaa ja kotiliigan nimi ilman UEFA-otteluita.

KAUDET. Paattyneet kaudet vendoroidaan repoon (`data/uefa_matches/`) - ne
eivat muutu, eika mallin siltamaara saa riippua siita vastaako UEFA juuri
bake-hetkella. Kuluva kausi haetaan livena ja valimuistitetaan levylle;
jos haku epaonnistuu, luetaan levyn vanha versio ja syy lokitetaan.
"""
from __future__ import annotations

import collections
import json
import time
from pathlib import Path

import pandas as pd
import requests

import config

BASE = "https://match.uefa.com/v5/matches"
# Ilman selaimen nakoista UA:ta UEFA vastaa joskus 403 (muisti
# ucl-syote-aukeaa-curl-ualla); curl-UA toimii mitatusti.
HEADERS = {"User-Agent": "curl/8.4.0", "Accept": "application/json"}

KILPAILUT: dict[str, int] = {
    "INT-Champions League": 1,
    "INT-Europa League": 14,
    "INT-Conference League": 2019,
}
"""Mallin liiganimi -> UEFAn competitionId."""

KARSINTA_LIIGA = "INT-Champions League Qualifying"
"""CL:n karsintarivit omalla nimellaan: ne ovat siltaa ja ratingin dataa,
mutta EIVAT tee seurasta CL-kelpoista (kelpoisuus tulee sarjavaiheesta)."""

VENDOR_DIR = config.DATA_DIR / "uefa_matches"
CACHE_DIR = config.RAW_DATA_DIR / "uefa_matches"
LIVE_TTL_SEC = 6 * 3600

COLUMNS = ["date", "home_team", "away_team", "home_score", "away_score",
           "league", "season", "home_xg", "away_xg", "lahde",
           "vaihe", "home_uefa_id", "away_uefa_id", "home_maa", "away_maa",
           "home_nimet", "away_nimet"]


def kausi_vuodeksi(kausi: str) -> int:
    """'2627' -> 2027 (UEFAn seasonYear on kauden paattymisvuosi)."""
    return 2000 + int(kausi[2:])


def _nimet(t: dict) -> list[str]:
    """Nimivaihtoehdot jarjestyksessa: virallinen, kansainvalinen, nayttonimi."""
    tr = t.get("translations") or {}
    out: list[str] = []
    for n in ((tr.get("displayOfficialName") or {}).get("EN"),
              t.get("internationalName"),
              (tr.get("displayName") or {}).get("EN")):
        if n and n not in out:
            out.append(str(n))
    return out


def rivit(raaka: list[dict], liiga: str, kausi: str) -> pd.DataFrame:
    """Rajapinnan vastaus -> mallin rivit. Vain pelatut, vain 90 min tulos."""
    out = []
    for m in raaka:
        if m.get("status") != "FINISHED":
            continue
        reg = ((m.get("score") or {}).get("regular") or {})
        if reg.get("home") is None or reg.get("away") is None:
            continue
        ko = ((m.get("kickOffTime") or {}).get("dateTime")
              or (m.get("kickOffTime") or {}).get("date") or "")
        if not ko:
            continue
        h, a = m.get("homeTeam") or {}, m.get("awayTeam") or {}
        hn, an = _nimet(h), _nimet(a)
        if not hn or not an:
            continue
        vaihe = m.get("competitionPhase") or ""
        out.append({
            "date": pd.Timestamp(ko[:10]),
            "home_team": hn[0], "away_team": an[0],
            "home_score": int(reg["home"]), "away_score": int(reg["away"]),
            "league": KARSINTA_LIIGA if (liiga == "INT-Champions League"
                                         and vaihe == "QUALIFYING") else liiga,
            "season": kausi, "home_xg": pd.NA, "away_xg": pd.NA,
            "lahde": "uefa", "vaihe": vaihe,
            "home_uefa_id": str(h.get("id")), "away_uefa_id": str(a.get("id")),
            "home_maa": h.get("countryCode") or "", "away_maa": a.get("countryCode") or "",
            "home_nimet": "|".join(hn), "away_nimet": "|".join(an),
        })
    return pd.DataFrame(out, columns=COLUMNS)


def _hae_raaka(comp_id: int, vuosi: int) -> list[dict]:
    """Kaikki kauden ottelut sivuttain. Heittaa verkkovirheessa."""
    kaikki: list[dict] = []
    offset = 0
    while True:
        r = requests.get(BASE, headers=HEADERS, timeout=30, params={
            "competitionId": comp_id, "seasonYear": vuosi,
            "limit": 500, "offset": offset, "order": "ASC"})
        r.raise_for_status()
        sivu = r.json()
        if not isinstance(sivu, list):
            raise ValueError(f"odottamaton vastaus: {type(sivu).__name__}")
        kaikki.extend(sivu)
        if len(sivu) < 500:
            return kaikki
        offset += 500


def _vendor_polku(liiga: str, kausi: str) -> Path:
    return VENDOR_DIR / f"{liiga.replace(' ', '_')}_{kausi}.csv"


def _lue_csv(p: Path) -> pd.DataFrame:
    d = pd.read_csv(p, dtype={"home_uefa_id": str, "away_uefa_id": str,
                              "season": str}, keep_default_na=False,
                    na_values={"home_xg": [""], "away_xg": [""]})
    d["date"] = pd.to_datetime(d["date"])
    return d[COLUMNS]


def lataa_kausi(liiga: str, kausi: str, *, live: bool | None = None) -> pd.DataFrame:
    """Yhden kilpailun yksi kausi.

    Paattynyt kausi: vendoroitu CSV (ei verkkoa). Kuluva kausi: live-haku,
    levyvalimuisti 6 h, vanha levyversio jos haku epaonnistuu.
    """
    comp = KILPAILUT[liiga]
    vp = _vendor_polku(liiga, kausi)
    if live is None:
        live = not vp.exists()
    if not live:
        return _lue_csv(vp) if vp.exists() else pd.DataFrame(columns=COLUMNS)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cp = CACHE_DIR / f"{comp}_{kausi}.json"
    if cp.exists() and (time.time() - cp.stat().st_mtime) < LIVE_TTL_SEC:
        return rivit(json.loads(cp.read_text(encoding="utf-8")), liiga, kausi)
    try:
        raaka = _hae_raaka(comp, kausi_vuodeksi(kausi))
        cp.write_text(json.dumps(raaka), encoding="utf-8")
        return rivit(raaka, liiga, kausi)
    except Exception as e:
        if cp.exists():
            print(f"[uefa_matches] {liiga} {kausi}: live-haku epaonnistui "
                  f"({type(e).__name__}: {e}) -> levyn vanha versio")
            return rivit(json.loads(cp.read_text(encoding="utf-8")), liiga, kausi)
        print(f"[uefa_matches] {liiga} {kausi}: live-haku epaonnistui "
              f"({type(e).__name__}: {e}) eika levylla ole versiota -> tyhja")
        return pd.DataFrame(columns=COLUMNS)


def lataa(kaudet: list[str], liigat: tuple[str, ...] = tuple(KILPAILUT)) -> pd.DataFrame:
    """Kaikki pyydetyt kilpailut ja kaudet yhtena kehyksena."""
    osat = [lataa_kausi(L, k) for L in liigat for k in kaudet]
    osat = [o for o in osat if not o.empty]
    if not osat:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(osat, ignore_index=True)


# ---------------------------------------------------------------------------
# Nimien ratkaisu
# ---------------------------------------------------------------------------

def _tokenit(s: str) -> frozenset[str]:
    from src.models.uefa_joint import canonical_name

    return frozenset(canonical_name(s).split())


def paritus_fd_nimiin(uefa_cl: pd.DataFrame, fd_cl: pd.DataFrame) -> dict[str, str]:
    """UEFA-ID -> football-data.orgin nimi PARITTAMALLA ottelut, ei nimia.

    Sama CL-ottelu on molemmissa lahteissa: sama paiva, sama 90 min tulos.
    Jos paivalla on useampi samalla tuloksella, valitaan se jonka nimien
    tokenit leikkaavat eniten (vaaditaan > 0). Jokainen ottelu antaa aanen
    molemmille seuroille; ID saa nimen jolla on eniten aania.

    Tama on ainoa tapa jolla 'LASK' (UEFA) ja 'LASK Linz' (fd.org),
    'Atleti' ja 'Club Atletico de Madrid' tai 'Lens' ja 'Racing Club de
    Lens' paatyvat samaksi seuraksi ilman kasin yllapidettavaa listaa.
    """
    tarvitaan = {"date", "home_team", "away_team", "home_score", "away_score"}
    if uefa_cl.empty or fd_cl.empty or not tarvitaan <= set(fd_cl.columns):
        return {}
    u = uefa_cl[uefa_cl["vaihe"] != "QUALIFYING"].copy()
    f = fd_cl.dropna(subset=["home_score", "away_score"]).copy()
    u["paiva"] = pd.to_datetime(u["date"]).dt.normalize()
    f["paiva"] = pd.to_datetime(f["date"]).dt.normalize()
    aanet: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    uryh = {k: g for k, g in u.groupby(["paiva", "home_score", "away_score"])}
    for r in f.itertuples(index=False):
        g = uryh.get((r.paiva, int(r.home_score), int(r.away_score)))
        if g is None:
            continue
        fh, fa = _tokenit(r.home_team), _tokenit(r.away_team)
        paras, paras_pisteet, tasan = None, 0, False
        for x in g.itertuples(index=False):
            uh = set().union(*(_tokenit(n) for n in x.home_nimet.split("|")))
            ua = set().union(*(_tokenit(n) for n in x.away_nimet.split("|")))
            p = len(fh & uh) + len(fa & ua)
            if p > paras_pisteet:
                paras, paras_pisteet, tasan = x, p, False
            elif p == paras_pisteet and p > 0:
                tasan = True
        if paras is None or tasan:
            continue
        aanet[paras.home_uefa_id][str(r.home_team)] += 1
        aanet[paras.away_uefa_id][str(r.away_team)] += 1
    return {i: c.most_common(1)[0][0] for i, c in aanet.items()}


def ratkaise_nimet(uefa: pd.DataFrame, fd_cl: pd.DataFrame,
                   kotiliiga_nimet: set[str]) -> tuple[pd.DataFrame, dict]:
    """Aseta home_team/away_team samaan nimiavaruuteen kuin muu data.

    Jarjestys: (1) otteluparitus fd.orgin CL-riveihin, (2) nimivaihtoehto
    jonka kanoninen muoto on kotiliigassa tai fd.orgin CL-datassa,
    (3) sama tokenijoukko eri jarjestyksessa ('LOSC Lille' ~ 'Lille OSC'),
    (4) UEFAn virallinen nimi. Palauttaa myos diagnoosin (mika reitti kullekin).
    """
    from src.models.uefa_joint import canonical_name

    if uefa.empty:
        return uefa, {}
    paritettu = paritus_fd_nimiin(
        uefa[uefa["league"].isin(("INT-Champions League", KARSINTA_LIIGA))], fd_cl)
    tunnetut: dict[str, str] = {}
    for n in list(kotiliiga_nimet) + list(fd_cl.get("home_team", [])) + list(fd_cl.get("away_team", [])):
        tunnetut.setdefault(canonical_name(n), str(n))
    tokeneittain: dict[frozenset, str] = {}
    for c, n in tunnetut.items():
        tokeneittain.setdefault(frozenset(c.split()), n)

    nimi: dict[str, str] = {}
    reitti: dict[str, str] = {}
    for puoli in ("home", "away"):
        for i, vaihtoehdot in zip(uefa[f"{puoli}_uefa_id"], uefa[f"{puoli}_nimet"]):
            if i in nimi:
                continue
            vv = vaihtoehdot.split("|")
            if i in paritettu:
                nimi[i], reitti[i] = paritettu[i], "paritus"
                continue
            for v in vv:
                if canonical_name(v) in tunnetut:
                    nimi[i], reitti[i] = tunnetut[canonical_name(v)], "nimi"
                    break
            else:
                for v in vv:
                    osuma = tokeneittain.get(frozenset(canonical_name(v).split()))
                    if osuma:
                        nimi[i], reitti[i] = osuma, "tokenit"
                        break
                else:
                    nimi[i], reitti[i] = vv[0], "uefa"
    out = uefa.copy()
    out["home_team"] = out["home_uefa_id"].map(nimi)
    out["away_team"] = out["away_uefa_id"].map(nimi)
    return out, reitti


def rakenna_vendor(kaudet: list[str]) -> list[Path]:
    """Kirjoita paattyneet kaudet repoon (scripts/build_uefa_matches.py)."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    kirjoitetut = []
    for liiga in KILPAILUT:
        for k in kaudet:
            d = lataa_kausi(liiga, k, live=True)
            if d.empty:
                raise ValueError(f"{liiga} {k}: tyhja - ei vendoroida tyhjaa")
            p = _vendor_polku(liiga, k)
            d.assign(date=d["date"].dt.strftime("%Y-%m-%d")).to_csv(
                p, index=False, lineterminator="\n")
            kirjoitetut.append(p)
    return kirjoitetut


# ---------------------------------------------------------------------------
# Kokoonpanot (UCL Fantasyn xP:n minuuttimalli seuroille joilla ei ole
# kotiliigan pelaajadataa). Pelaaja-ID:t ovat SAMAA avaruutta kuin UCL
# Fantasyn pelaaja-ID:t (mitattu 21.9: 250079125 molemmissa).
# ---------------------------------------------------------------------------

KOKOONPANO_DIR = config.RAW_DATA_DIR / "uefa_lineups"


def kokoonpano(match_id: str, *, verkko: bool = True) -> dict[str, dict[str, list[str]]] | None:
    """{joukkue_id: {'avaus': [pelaaja_id], 'penkki': [pelaaja_id]}} tai None.

    Paattyneen ottelun kokoonpano ei muutu, joten levyvalimuisti on pysyva.
    Rajapinta ei kerro vaihtoja eika minuutteja - vain avauksen ja penkin."""
    KOKOONPANO_DIR.mkdir(parents=True, exist_ok=True)
    p = KOKOONPANO_DIR / f"{match_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    if not verkko:
        return None
    try:
        r = requests.get(f"{BASE}/{match_id}/lineups", headers=HEADERS, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:
        print(f"[uefa_matches] kokoonpano {match_id}: {type(e).__name__}: {e}")
        return None
    out: dict[str, dict[str, list[str]]] = {}
    for puoli in ("homeTeam", "awayTeam"):
        t = j.get(puoli) or {}
        tid = str((t.get("team") or {}).get("id") or "")
        if not tid:
            continue
        out[tid] = {
            "avaus": [str((x.get("player") or {}).get("id")) for x in t.get("field") or []
                      if (x.get("player") or {}).get("id")],
            "penkki": [str((x.get("player") or {}).get("id")) for x in t.get("bench") or []
                       if (x.get("player") or {}).get("id")],
        }
    if out and all(len(v["avaus"]) == 11 for v in out.values()):
        p.write_text(json.dumps(out), encoding="utf-8")
    return out or None


def raaka_kausi(liiga: str, kausi: str) -> list[dict]:
    """Rajapinnan raakaottelut (ottelu-ID:t, maalintekijat) yhdelle kaudelle.

    Vendoroitu CSV ei sisalla naita kenttia. Paattyneen kauden raakadata ei
    muutu, joten sen levyvalimuisti on pysyva; kuluva kausi kulkee
    `lataa_kausi`n TTL-polun kautta."""
    comp = KILPAILUT[liiga]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cp = CACHE_DIR / f"{comp}_{kausi}.json"
    if not _vendor_polku(liiga, kausi).exists():
        lataa_kausi(liiga, kausi)            # kuluva kausi: TTL + vara
        return json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else []
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))
    try:
        raaka = _hae_raaka(comp, kausi_vuodeksi(kausi))
        cp.write_text(json.dumps(raaka), encoding="utf-8")
        return raaka
    except Exception as e:
        print(f"[uefa_matches] raaka {liiga} {kausi}: {type(e).__name__}: {e}")
        return []
