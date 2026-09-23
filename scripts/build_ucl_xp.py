# -*- coding: utf-8 -*-
"""UCL Fantasy xP: build (tuotanto) ja takatesti samalla koodilla.

AJO:
  python -m scripts.build_ucl_xp                 # seuraava kierros -> data/ucl_xp_projections.json
  python -m scripts.build_ucl_xp --takatesti 1   # ennusta MD1 datalla ennen 8.9. ja vertaa toteumaan

Kaava: src/models/ucl_xp.py. Taman skriptin tehtava on koota data ja
yhdistaa lahteet ID:lla tai tarkistetulla nimisaannolla - ei arvata.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

import config
from src.data import understat_players as US
from src.data import uefa_matches as U
from src.models import ucl_xp as X
from src.models.uefa_joint import canonical_name

FEED = "https://gaming.uefa.com/en/uclfantasy/services/feeds"
FEED_HEADERS = {"User-Agent": "curl/8.0", "Accept": "application/json, text/plain, */*",
                "Referer": "https://gaming.uefa.com/en/uclfantasy/create-team"}
KAUSI_ID = 90
"""Syotteen kausi-ID kaudelle 2026/27 (takatestin oletus). Tuotanto lukee
ID:n ingestion artefaktista (`data/ucl_fantasy.json` meta.season_id), jonka
ingest_ucl.py etsii itse joka kaudelle."""
OUT = config.DATA_DIR / "ucl_xp_projections.json"
VAIHTO_PENKILTA = 0.35
"""Osuus penkille merkityista jotka nousevat kentalle. UEFAn kokoonpano
kertoo vain avauksen ja penkin; rakenteellinen arvio, ei sovitettu."""

# Understatin seuranimet jotka eivat osu kanonisella nimella eivatka
# osajoukkona. Mitattu 21.9 CL 26/27:n 21 paasarjaseurasta.
UNDERSTAT_ALIAS = {
    "internazionale milano": "inter",
    "bayern munchen": "bayern munich",
    "rb leipzig": "rasenballsport leipzig",
}


# ---------------------------------------------------------------------------
# Lahteet
# ---------------------------------------------------------------------------

def hae_syote(md: int, kausi_id: int = KAUSI_ID) -> list[dict]:
    req = urllib.request.Request(f"{FEED}/players/players_{kausi_id}_en_{md}.json",
                                 headers=FEED_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))["data"]["value"]["playerList"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("ø", "o").replace("ß", "ss").replace("ł", "l").replace("đ", "d")
    return re.sub(r"[^a-z ]+", " ", s).strip()


def _toks(s: str) -> list[str]:
    return [t for t in _norm(s).split() if t]


# ---------------------------------------------------------------------------
# Joukkuekartta: UCL Fantasyn joukkue-ID -> CL-mallin nimi -> Understat
# ---------------------------------------------------------------------------

def joukkuekartta(uefa2627: pd.DataFrame, fd_cl: pd.DataFrame) -> dict[str, str]:
    """UEFA-ID -> fd.org-nimi otteluparituksella (sama kuin CL-mallin nimet)."""
    return U.paritus_fd_nimiin(uefa2627[uefa2627["league"] == "INT-Champions League"], fd_cl)


def understat_seura(malli_nimi: str, maa: str, us_joukkueet: list[str]) -> str | None:
    c = canonical_name(malli_nimi)
    c = UNDERSTAT_ALIAS.get(c, c)
    kan = {canonical_name(t): t for t in us_joukkueet}
    if c in kan:
        return kan[c]
    ct = set(c.split())
    osumat = [t for k, t in kan.items() if set(k.split()) and (set(k.split()) <= ct or ct <= set(k.split()))]
    return osumat[0] if len(osumat) == 1 else None


# ---------------------------------------------------------------------------
# Pelaajien yhdistaminen Understatiin (seuran sisalla)
# ---------------------------------------------------------------------------

def yhdista_pelaaja(p: dict, ehdokkaat: list[dict]) -> dict | None:
    nimet = [p.get("pFName") or "", p.get("latinName") or "", p.get("pDName") or ""]
    koko = {" ".join(_toks(n)) for n in nimet if n}
    for e in ehdokkaat:
        if " ".join(_toks(e["nimi"])) in koko:
            return e
    # sukunimi + etukirjain, tai yksiselitteinen sukunimi
    pt = _toks(p.get("latinName") or p.get("pFName") or "")
    if not pt:
        return None
    suku, etu = pt[-1], pt[0][:1]
    osu = [e for e in ehdokkaat if _toks(e["nimi"]) and _toks(e["nimi"])[-1] == suku]
    if len(osu) > 1:
        osu = [e for e in osu if _toks(e["nimi"])[0][:1] == etu]
    if len(osu) == 1:
        return osu[0]
    # tokenijoukko: kaikki UEFA-nimen tokenit Understat-nimessa (tai painvastoin)
    pts = set(pt)
    osu = [e for e in ehdokkaat if pts and (pts <= set(_toks(e["nimi"])) or set(_toks(e["nimi"])) <= pts)
           and len(set(_toks(e["nimi"])) & pts) >= 1]
    return osu[0] if len(osu) == 1 else None


# ---------------------------------------------------------------------------
# Paaputki
# ---------------------------------------------------------------------------

def ottelut_syotteesta(syote: list[dict], md: int) -> dict[str, tuple[str, str]]:
    """joukkue_id -> (koti_id, vieras_id) kierrokselle `md` syotteen omasta listasta."""
    out = {}
    for p in syote:
        for x in (p.get("upcomingMatchesList") or []) + (p.get("currentMatchesList") or []):
            if str(x.get("mdId")) != str(md):
                continue
            t, v = str(p["tId"]), str(x["vsTID"])
            out[t] = (t, v) if x.get("tLoc") == "H" else (v, t)
    return out


def rakenna(md: int, *, ennen: str | None, syote: list[dict], odotus, joukkuenimi: dict[str, str],
            ottelut: dict[str, tuple[str, str]],
            uefa2627: pd.DataFrame, saatavuus_kaytossa: bool = True,
            loo_syote: list[dict] | None = None, myohempi_kierros: bool = False) -> dict:
    """Laske xP jokaiselle syotteen pelaajalle kierroksen `md` otteluun.

    `ennen`: takatestin leikkauspaiva (Understat 2026 rajataan joukkueiden
    otteluhistoriaan; pelaajakertymia ei voi rajata -> kirjattu vuotona).
    `odotus(koti_id, vieras_id)` -> ucl_xp.joukkue_odotus-muotoinen dict.
    `loo_syote`: kierroksen toteumasyote pelipaikkavakioille (riistot,
    kaukaa-osuus, torjunnat) - takatestissa oma ottelu jatetaan pois."""
    # --- Understat: kaudet 2025 (paino 0.5) ja 2026 (paino 1) ---
    us = {}
    for maa in US.LIIGAT:
        for v in (2025, 2026):
            d = US.lataa(maa, v)
            if d:
                us[(maa, v)] = d

    # --- UEFA-ottelut 25/26 (paino 0.5) ja 26/27 (paino 1) ennen leikkausta ---
    # Raakadata (ottelu-ID:t, maalintekijat); kokoonpanot ottelu-ID:lla.
    raaka: list[tuple[dict, float]] = []
    for liiga in U.KILPAILUT:
        edellinen, kuluva = config.current_season_pair()
        for kausi, w in ((edellinen, X.EDELLINEN_KAUSI_PAINO), (kuluva, 1.0)):
            for m in U.raaka_kausi(liiga, kausi):
                if m.get("status") != "FINISHED":
                    continue
                if ennen and m["kickOffTime"]["dateTime"][:10] >= ennen:
                    continue
                raaka.append((m, w))
    maalit_uefa: collections.Counter = collections.Counter()
    ottelut_joukkue: dict[str, list[tuple[str, float]]] = collections.defaultdict(list)
    joukkue_maalit: collections.Counter = collections.Counter()
    for m, w in raaka:
        for sc in (m.get("playerEvents") or {}).get("scorers") or []:
            if sc.get("goalType") in ("SCORED", "PENALTY"):
                maalit_uefa[str((sc.get("player") or {}).get("id"))] += w
        h, a_ = str(m["homeTeam"]["id"]), str(m["awayTeam"]["id"])
        reg = (m.get("score") or {}).get("regular") or {}
        ottelut_joukkue[h].append((str(m["id"]), w))
        ottelut_joukkue[a_].append((str(m["id"]), w))
        joukkue_maalit[h] += w * int(reg.get("home") or 0)
        joukkue_maalit[a_] += w * int(reg.get("away") or 0)

    maa_id = {}
    for puoli in ("home", "away"):
        for i, mm in zip(uefa2627[f"{puoli}_uefa_id"], uefa2627[f"{puoli}_maa"]):
            maa_id[str(i)] = mm

    # --- Pelaajakohtaiset kertymat ---
    kertymat = {}
    pos_of = {}
    for p in syote:
        pid, tid = str(p["id"]), str(p["tId"])
        pos = X.SKILL.get(p.get("skill"))
        if pos is None:
            continue
        pos_of[pid] = pos
        maa = maa_id.get(tid, "")
        nimi = joukkuenimi.get(tid)
        acc = {"g": 0.0, "a": 0.0, "min": 0.0, "yc": 0.0, "lahde": "ei_dataa",
               "aloitukset": 0.0, "vaihdot": 0.0, "joukkue_ottelut": 0.0}
        if maa in US.LIIGAT and nimi:
            for v, w in ((2026, 1.0), (2025, X.EDELLINEN_KAUSI_PAINO)):
                d = us.get((maa, v))
                if not d:
                    continue
                jj = US.joukkueet(d, ennen=ennen if v == 2026 else None)
                seura = understat_seura(nimi, maa, list(jj))
                if not seura or not jj[seura]["ottelut"]:
                    continue
                ehd = [e for e in US.pelaajat(d) if e["seura"] == seura]
                e = yhdista_pelaaja(p, ehd)
                acc["joukkue_ottelut"] += w * jj[seura]["ottelut"]
                if not e:
                    continue
                txg = jj[seura]["xg"] / jj[seura]["ottelut"]
                acc["g"] += w * e["xg"] / max(txg, 0.3)
                acc["a"] += w * e["xa"] / max(txg, 0.3)
                acc["min"] += w * e["min"]
                acc["yc"] += w * e["yc"]
                al, va = X.aloitukset_minuuteista(e["min"], e["ottelut"])
                acc["aloitukset"] += w * al
                acc["vaihdot"] += w * va
                acc["lahde"] = "kotiliiga"
        if acc["lahde"] == "ei_dataa" and not (maa in US.LIIGAT):
            om = ottelut_joukkue.get(tid, [])
            ww = sum(w for _, w in om)
            if ww > 0:
                al = pe = 0.0
                for mid, w in om:
                    k = U.kokoonpano(mid)
                    if not k or tid not in k:
                        continue
                    al += w * (pid in k[tid]["avaus"])
                    pe += w * (pid in k[tid]["penkki"])
                tpm = max(joukkue_maalit[tid] / ww, 0.3)
                acc["g"] = maalit_uefa.get(pid, 0.0) / tpm
                acc["aloitukset"] = al
                acc["vaihdot"] = pe * VAIHTO_PENKILTA
                acc["joukkue_ottelut"] = ww
                acc["min"] = al * X.MIN_ALOITUS + pe * VAIHTO_PENKILTA * X.MIN_VAIHTO
                acc["lahde"] = "uefa"
        kertymat[pid] = acc

    # --- Pelipaikan priorit kotiliigapelaajista ---
    prior = {}
    for pos in X.POS:
        g = a = mn = yc = 0.0
        for pid, acc in kertymat.items():
            if pos_of[pid] == pos and acc["lahde"] == "kotiliiga":
                g += acc["g"]; a += acc["a"]; mn += acc["min"]; yc += acc["yc"]
        mn = max(mn, 1.0)
        prior[pos] = {"g90": 90 * g / mn, "a90": 90 * a / mn, "yc90": 90 * yc / mn}

    # --- Pelipaikkavakiot toteumasyotteesta (riistot, kaukaa, torjunnat) ---
    vakiot = pelipaikkavakiot(loo_syote or syote)

    # --- Minuutit: raaka-arvio + saatavuus, sitten joukkueittain tasan 11 aloittajaa ---
    raaka_min: dict[str, tuple[float, float]] = {}
    for p in syote:
        pid = str(p["id"])
        if pid not in kertymat:
            continue
        acc = kertymat[pid]
        status = p.get("pStatus") or ""
        if status == "NIS":
            saat = 0.0
        elif not saatavuus_kaytossa:
            saat = 1.0
        elif myohempi_kierros:
            # Syotteen tila koskee SEURAAVAA kierrosta. Myohemmille oletetaan
            # etta loukkaantunut/pelikieltoinen voi palata (puolikas), epavarma
            # pelaa. Rakenteellinen, ei mitattu.
            saat = {"I": 0.5, "S": 0.5, "D": 1.0}.get(status, 1.0)
        else:
            saat = {"I": 0.0, "S": 0.0, "D": 0.5}.get(status, 1.0)
        if acc["joukkue_ottelut"] > 0 and acc["lahde"] != "ei_dataa":
            p_al = acc["aloitukset"] / acc["joukkue_ottelut"]
            p_va = acc["vaihdot"] / acc["joukkue_ottelut"]
        else:
            p_al, p_va = X.P_ALOITUS_TUNTEMATON, X.P_VAIHTO_TUNTEMATON
        raaka_min[pid] = (p_al * saat, p_va * saat)
    joukkueittain: dict[str, list[str]] = collections.defaultdict(list)
    for p in syote:
        if str(p["id"]) in raaka_min:
            joukkueittain[str(p["tId"])].append(str(p["id"]))
    minuutit_norm: dict[str, dict] = {}
    for tid, pids in joukkueittain.items():
        al = X.tayta({i: raaka_min[i][0] for i in pids}, X.ALOITTAJIA, X.KATTO_ALOITUS)
        va = X.tayta({i: raaka_min[i][1] for i in pids}, X.VAIHTOJA, X.KATTO_VAIHTO)
        for i in pids:
            minuutit_norm[i] = X.minuuttiarvio(al[i], va[i], 1.0)

    # --- Ottelut ja xP ---
    tulos = []
    ottelun_pelaajat: dict[tuple, list] = collections.defaultdict(list)
    for p in syote:
        pid = str(p["id"]); tid = str(p["tId"]); pos = pos_of.get(pid)
        if pos is None or pid not in minuutit_norm:
            continue
        if tid not in ottelut:
            continue
        koti, vieras = ottelut[tid]
        jo = odotus(koti, vieras)
        if jo is None or tid not in jo:
            continue
        acc = kertymat[pid]
        pr = prior[pos]
        m_osuus = X.M_PRIOR_OSUUS * (2.0 if acc["lahde"] == "uefa" else 1.0)
        g90 = X.shrink90(acc["g"], acc["min"], pr["g90"], m_osuus)
        a90 = X.shrink90(acc["a"], acc["min"], pr["a90"], m_osuus) if acc["lahde"] == "kotiliiga"             else pr["a90"]
        yc90 = X.shrink90(acc["yc"], acc["min"], pr["yc90"], 900.0)
        mins = minuutit_norm[pid]
        v = vakiot.get((pos, tid)) or vakiot[pos]
        r = X.xp_pelaajalle(pos, joukkue=jo[tid], minuutit=mins, g90=g90, a90=a90,
                            yc90=yc90, riisto3_90=v["riisto3_90"], kaukaa_osuus=v["kaukaa"],
                            torjunnat_per_paastetty=vakiot["torjunnat_per_xga"], p_mom=0.0)
        rivi = {"id": pid, "nimi": p.get("pDName"), "joukkue": p.get("tName"), "tid": tid,
                "pos": pos, "hinta": p.get("value"), "omistus": p.get("selPer"),
                "status": p.get("pStatus") or "", "data_basis": acc["lahde"], "minuutit": mins,
                "g90": g90, "a90": a90, **r}
        tulos.append(rivi)
        ottelun_pelaajat[(koti, vieras)].append(rivi)

    # ottelun pelaaja: tasan yksi per ottelu
    for rr in ottelun_pelaajat.values():
        painot = {x["id"]: (x["e_maalit"] * X._s(x["pos"], "maali") + x["e_syotot"] * 3
                            + 0.05 * x["minuutit"]["p60"]) for x in rr}
        pm = X.mom_todennakoisyydet(painot)
        for x in rr:
            lisa = pm[x["id"]] * X._s(x["pos"], "mom")
            x["komponentit"]["ottelun_pelaaja"] = lisa
            x["xp"] += lisa
    return {"pelaajat": tulos, "priorit": prior, "vakiot": {k: v for k, v in vakiot.items()
                                                             if isinstance(k, str)}}


def pelipaikkavakiot(syote: list[dict]) -> dict:
    """Riistopisteet/90, kaukaa-maalien osuus ja torjunnat per paastetty
    toteutuneista riveista. Palauttaa myos (pos, tid)-avaimet joissa OMAN
    joukkueen ottelu on jatetty pois (takatestin vuodonesto)."""
    def laske(rivit):
        out = {}
        for pos in X.POS:
            rr = [p for p in rivit if X.SKILL.get(p.get("skill")) == pos and p.get("minsPlyd")]
            mn = sum(p["minsPlyd"] for p in rr) or 1.0
            gs = sum(p.get("gS", 0) for p in rr)
            out[pos] = {"riisto3_90": 90.0 * sum(p.get("bR", 0) // 3 for p in rr) / mn,
                        "kaukaa": (sum(p.get("gOB", 0) for p in rr) / gs) if gs else 0.1}
        gk = [p for p in rivit if p.get("skill") == 1 and p.get("minsPlyd")]
        gc = sum(p.get("gC", 0) for p in gk)
        out["torjunnat_per_xga"] = (sum(p.get("saves", 0) for p in gk) / gc) if gc else 2.5
        return out
    kaikki = laske(syote)
    tulos = dict(kaikki)
    for tid in {str(p["tId"]) for p in syote}:
        muut = laske([p for p in syote if str(p["tId"]) != tid])
        for pos in X.POS:
            tulos[(pos, tid)] = muut[pos]
    return tulos


class _Taitettu:
    """Tuotannon CL-malli (data/uefa_joint_model.json, fd.org-nimet)."""

    def __init__(self, dc):
        self.dc, self.rho = dc, dc.rho

    def expected_goals(self, h, a):
        return self.dc.expected_goals(h, a)

    def _bp_score_matrix(self, *a):
        return self.dc._bp_score_matrix(*a)


class _Yhteis:
    """Takatestin CL-malli: fitattu leikkauspaivaan asti, kanoniset nimet."""

    def __init__(self, m):
        self.m, self.rho = m, m.dc.rho

    def expected_goals(self, h, a):
        return self.m.expected_goals(h, a)

    def _bp_score_matrix(self, *a):
        return self.m.dc._bp_score_matrix(*a)


def odotusfunktio(malli, joukkuenimi: dict[str, str], tuntee):
    def odotus(koti, vieras):
        nh, na = joukkuenimi.get(koti), joukkuenimi.get(vieras)
        if not nh or not na or not tuntee(nh) or not tuntee(na):
            return None
        r = X.joukkue_odotus(malli, nh, na)
        return {koti: r[nh], vieras: r[na]}
    return odotus


def _cl_data():
    from api.main import _lataa_otteludata_cached
    # Sama ikkuna kuin API:n yhteisfitissa: vendoroidut CL-kaudet + kuluva pari.
    from src.data.fd_fallback import VENDORED_SEASONS
    kaudet = sorted({*VENDORED_SEASONS.get("INT-Champions League", ()),
                     *config.current_season_pair()})
    tour = _lataa_otteludata_cached(["INT-Champions League"], kaudet)
    return tour


def takatesti_md1(syote_md1: list[dict]) -> dict:
    """MD1 (8.-10.9.2026) datalla ennen 8.9.: CL-malli fitataan leikkaukseen
    asti samalla polulla kuin tuotanto (maaryhma, UEFA-silta)."""
    from api.main import _lataa_otteludata_cached
    from src.models import uefa_joint as J
    from scipy.stats import spearmanr

    leikkaus = "2026-09-08"
    ennen = lambda d: d[pd.to_datetime(d["date"]) < pd.Timestamp(leikkaus)]
    tour = _cl_data()
    dom = _lataa_otteludata_cached(list(J.SUPPORT_LEAGUES), ["2526", "2627"])
    uefa, _ = U.ratkaise_nimet(U.lataa(["2324", "2425", "2526", "2627"]), tour,
                               set(dom.home_team) | set(dom.away_team))
    u27 = uefa[uefa["season"].astype(str) == "2627"]
    nimet = joukkuekartta(u27, tour)
    df = pd.concat([ennen(dom), ennen(tour), ennen(uefa[uefa["league"].isin(J.BRIDGE_LEAGUES)])],
                   ignore_index=True)
    m = J.fit_uefa_joint(df, tournament_league="INT-Champions League", decay=0.0035,
                         stale_seasons=frozenset({"2324"}), team_groups="maa")
    odotus = odotusfunktio(_Yhteis(m), nimet, lambda n: canonical_name(n) in m.dc.attack)
    md1 = u27[(u27["league"] == "INT-Champions League") & (u27["vaihe"] == "TOURNAMENT")
              & (pd.to_datetime(u27["date"]) <= pd.Timestamp("2026-09-10"))]
    ottelut = {}
    for r in md1.itertuples():
        ottelut[r.home_uefa_id] = ottelut[r.away_uefa_id] = (r.home_uefa_id, r.away_uefa_id)
    t = rakenna(1, ennen=leikkaus, syote=syote_md1, odotus=odotus, joukkuenimi=nimet,
                ottelut=ottelut, uefa2627=u27, saatavuus_kaytossa=True, loo_syote=syote_md1)
    toteuma = {str(p["id"]): p.get("totPts", 0) for p in syote_md1}
    P = t["pelaajat"]
    y = np.array([toteuma[p["id"]] for p in P], float)
    xp = np.array([p["xp"] for p in P], float)
    hinta = np.array([p["hinta"] or 0 for p in P], float)
    tulos = {"pelaajia": len(P), "toteuma": float(y.sum()), "ennuste": float(xp.sum()),
             "mae": float(np.mean(abs(xp - y))), "mae_vakio": float(np.mean(abs(y.mean() - y))),
             "spearman": float(spearmanr(xp, y).correlation),
             "spearman_hinta": float(spearmanr(hinta, y).correlation)}
    for k in (10, 30, 100):
        tulos[f"top{k}"] = float(y[np.argsort(-xp)[:k]].mean())
        tulos[f"top{k}_hinta"] = float(y[np.argsort(-hinta)[:k]].mean())
    return tulos


MIN_KOTILIIGARIVIT = 400
"""Alaraja kotiliigapohjaisille riveille. Jos Understat ei vastaa, lahes
kaikki rivit putoavat UEFA-pohjalle ja artefakti olisi hiljaa huonompi:
silloin ei kirjoiteta mitaan (vanha artefakti jaa, tuoreusvahti sulkee sen)."""

HORISONTTI = 3
"""Montako kierrosta eteenpain (sama idea kuin FPL:n horizon_gw, lyhyempi
koska UCL:n sarjavaiheessa on 8 kierrosta)."""
STATUS = {"": "a", "I": "i", "D": "d", "S": "s", "NIS": "u"}
"""UCL-syotteen tila -> FPL-koodi jota SPA ja mobiili jo lukevat."""
DATA_BASIS = {"kotiliiga": "domestic_league", "uefa": "uefa_matches", "ei_dataa": "no_history"}


def ottelut_kierroksittain(raaka_cl: list[dict]) -> dict[int, dict[str, tuple[str, str]]]:
    """Sarjavaiheen ottelut UEFAn rajapinnasta: {md: {joukkue_id: (koti, vieras)}}."""
    out: dict[int, dict[str, tuple[str, str]]] = collections.defaultdict(dict)
    for m in raaka_cl:
        if ((m.get("round") or {}).get("metaData") or {}).get("type") != "GROUP_STANDINGS":
            continue
        try:
            md = int((m.get("matchday") or {}).get("sequenceNumber"))
        except (TypeError, ValueError):
            continue
        h, a = str(m["homeTeam"]["id"]), str(m["awayTeam"]["id"])
        out[md][h] = out[md][a] = (h, a)
    return out


def joukkuetaso(horisontti: list[int], kierrokset: dict, odotus, syote: list[dict]) -> list[dict]:
    """Joukkueiden nollapeli- ja maaliodotus horisontin kierroksille (23.9, UCL-MENUT).

    Villen valinta 23.9: UCL saa saman rakenteen kuin FPL ja RSL, eli myos
    Teams-nakyman (clean sheet % ja otteluvaikeus kierroksittain). Luvut tulevat
    SAMASTA `odotus`-funktiosta kuin pelaajien nollapeli-komponentti
    (`ucl_xp.xp_pelaajalle`: p60 x joukkue['cs']), joten joukkueen CS% ja sen
    puolustajien xP eivat voi kertoa eri tarinaa.

    Ottelu jota malli ei tunne (odotus -> None) jaa pois eika saa nollaa:
    puuttuva luku ei ole 0 %.
    """
    tiedot = {str(p["tId"]): (p.get("tName"), p.get("cCode")) for p in syote}
    joukkueet: dict[str, dict] = {}
    for k in horisontti:
        for koti, vieras in sorted(set((kierrokset.get(k) or {}).values())):
            o = odotus(koti, vieras)
            if o is None:
                continue
            for puoli, vast in ((koti, vieras), (vieras, koti)):
                nimi, lyhyt = tiedot.get(puoli, (None, None))
                t = joukkueet.setdefault(puoli, {"id": int(puoli), "name": nimi or puoli,
                                                 "short": lyhyt or puoli, "fixtures": []})
                t["fixtures"].append({
                    "gw": k, "opp": tiedot.get(vast, (None, None))[1] or vast,
                    "venue": "H" if puoli == koti else "A",
                    "cs_pct": round(o[puoli]["cs"] * 100, 1),
                    "xg": round(o[puoli]["xg"], 2), "xga": round(o[puoli]["xga"], 2),
                })
    return sorted(joukkueet.values(), key=lambda t: (
        -sum(f["cs_pct"] for f in t["fixtures"]) / max(len(t["fixtures"]), 1), t["short"]))


def seuraava_kierros(ucl_fantasy: dict) -> tuple[int | None, str | None]:
    """Ensimmainen lukitsematon kierros ja sen deadline syotteen artefaktista.
    (None, None) kun kaikki on lukittu: tuota() kirjoittaa silloin suljetun
    artefaktin eika build kaadu (vanha kierros jaisi muuten tarjolle)."""
    for m in sorted(ucl_fantasy.get("matchdays") or [], key=lambda x: x["md"]):
        if not m.get("is_locked"):
            return int(m["md"]), m.get("deadline_utc")
    return None, None


KOMPONENTIT = {
    "esiintyminen": "appearance", "maalit": "goals", "syotot": "assists",
    "nollapeli": "clean_sheet", "paastetyt": "goals_conceded", "torjunnat": "saves",
    "riistot": "recoveries", "kortit": "cards", "ottelun_pelaaja": "player_of_the_match",
}
"""Komponenttien julkiset nimet (API on julkinen pinta, avaimet englanniksi)."""


def suljettu(md: int | None, viimeinen: int | None, syy: str) -> dict:
    """Artefakti kun projektiota ei ole tarjolla (sarjavaihe ohi). Klientit
    nayttavat suljetun tilan tekstin; mitaan vanhaa kierrosta ei tarjoilla."""
    import datetime as _dt
    return {"meta": {"product": "GoalIQ UCL Fantasy - expected points (xP)",
                     "available": False, "reason": syy, "league": "INT-Champions League",
                     "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                     "deadline_gameweek": md, "league_phase_last_md": viimeinen},
            "players": []}


def tuota(md: int, deadline: str | None, kausi_id: int = KAUSI_ID) -> dict:
    import datetime as _dt

    from src.models import uefa_prebuilt

    dc, syy = uefa_prebuilt.load(tournament="INT-Champions League",
                                  season_pair=list(config.current_season_pair()),
                                  decay=0.0035)
    if dc is None:
        raise SystemExit(f"CL-malli ei kelpaa ({syy}) - xP:ta ei rakenneta vanhalla mallilla")
    kuluva = config.current_season_pair()[-1]
    kierrokset = ottelut_kierroksittain(U.raaka_kausi("INT-Champions League", kuluva))
    viimeinen = max(kierrokset) if kierrokset else None
    # SARJAVAIHE OHI (julkaisutarkistaja 21.9): pudotuspeleja ei mallinneta.
    # Kirjoitetaan suljettu artefakti eika jateta vanhaa kierrosta tarjolle.
    if viimeinen is None or md > viimeinen:
        return suljettu(md, viimeinen, "league_phase_over")
    syote = hae_syote(md, kausi_id)
    ok, n, huonot = X.tarkista_saannot(syote)
    if n and ok < n:
        raise SystemExit(f"UEFA muutti pisteytysta: saannot selittavat {ok}/{n} ({huonot})")
    tour = _cl_data()
    u27 = U.lataa([kuluva])
    nimet = joukkuekartta(u27, tour)
    tiimit = {str(p["tId"]) for p in syote}
    puuttuu = sorted(t for t in tiimit if t not in nimet)
    if puuttuu:
        raise SystemExit(f"joukkuekartasta puuttuu {len(puuttuu)} seuraa: {puuttuu}")
    odotus = odotusfunktio(_Taitettu(dc), nimet, lambda n: n in dc.attack)
    if md not in kierrokset:
        raise SystemExit(f"MD{md}: UEFAn otteluohjelmassa ei ole otteluita")
    horisontti = [k for k in range(md, md + HORISONTTI) if k in kierrokset]
    koodi = {str(p["tId"]): p.get("cCode") for p in syote}

    rivit: dict[str, dict] = {}
    for k in horisontti:
        t = rakenna(k, ennen=None, syote=syote, odotus=odotus, joukkuenimi=nimet,
                    ottelut=kierrokset[k], uefa2627=u27, saatavuus_kaytossa=True,
                    myohempi_kierros=(k != md))
        for r in t["pelaajat"]:
            rivi = rivit.setdefault(r["id"], {"r": r, "gws": []})
            koti, vieras = kierrokset[k][r["tid"]]
            vast = vieras if r["tid"] == koti else koti
            rivi["gws"].append({"gw": k, "opponents": [{"opp": koodi.get(vast) or vast,
                                                        "venue": "H" if r["tid"] == koti else "A"}],
                                "xp": round(r["xp"], 2)})
            if k == md:
                rivi["r"] = r
    tila = {str(p["id"]): p for p in syote}
    pelaajat = []
    for pid, v in rivit.items():
        r, p = v["r"], tila[pid]
        tot = round(sum(g["xp"] for g in v["gws"]), 2)
        pelaajat.append({
            "id": int(pid), "web_name": p.get("pDName"), "full_name": p.get("pFName"),
            "team": p.get("tName"), "team_short": p.get("cCode"),
            "pos": "GKP" if r["pos"] == "GK" else r["pos"],
            "price": p.get("value"), "owned_pct": p.get("selPer"),
            "status": STATUS.get(p.get("pStatus") or "", "a"),
            "news": (p.get("trained") or "") if (p.get("pStatus") or "") else "",
            "xmins": round(r["minuutit"]["min"], 1),
            "p_start": round(r["minuutit"]["p_aloitus"], 3),
            "data_basis": DATA_BASIS[r["data_basis"]],
            "xp_per_gw": round(tot / len(v["gws"]), 2) if v["gws"] else 0.0,
            "xp_horizon_total": tot,
            "xp_next": v["gws"][0]["xp"] if v["gws"] else 0.0,
            "xp_components": {KOMPONENTIT[kk]: round(vv, 2) for kk, vv in r["komponentit"].items()},
            "gameweeks": v["gws"],
        })
    pelaajat.sort(key=lambda x: -x["xp_horizon_total"])
    kanta = collections.Counter(p["data_basis"] for p in pelaajat)
    # 🔴 Understat voi olla estetty CI-runnerilta (datakeskus-ASN). Silloin
    # jokainen paasarjapelaaja putoaisi "no_history"-tilaan ja lista nayttaisi
    # tayselta. Mitattu 21.9 paikallisesti: 536 kotiliigariviä.
    if kanta.get("domestic_league", 0) < MIN_KOTILIIGARIVIT:
        raise SystemExit(f"vain {kanta.get('domestic_league', 0)} kotiliigapohjaista riviä "
                         f"(< {MIN_KOTILIIGARIVIT}) - Understat ei vastannut? Ei kirjoiteta.")
    return {
        "meta": {
            "product": "GoalIQ UCL Fantasy - expected points (xP)",
            "available": True,
            "league": "INT-Champions League",
            "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "season": f"20{kuluva[:2]}/{kuluva[2:]}",
            "source": "uefa-ucl-fantasy-feed",
            "deadline_gameweek": md, "next_gameweek": md, "current_gameweek": md,
            "deadline_utc": deadline,
            "league_phase_last_md": viimeinen,
            "horizon_gw": len(horisontti),
            "scoring": ("UEFA Champions League Fantasy rules, derived from the official feed's "
                        f"own points ({ok}/{n} players who played matched exactly)"),
            "team_strength_source": "GoalIQ Champions League model (all 36 clubs on one scale)",
            "attack_basis": ("Share of the club's expected goals and assists per 90 minutes in its "
                             "domestic league (Understat, five major leagues). Clubs outside those "
                             "leagues: goals and starting line-ups in UEFA matches, shrunk harder."),
            "minutes_basis": ("Starts and substitute appearances from the domestic league or UEFA "
                              "line-ups, normalised to 11 starters per club; official feed "
                              "availability applied to the next matchday."),
            "data_basis_counts": dict(kanta),
            "thin_data": "uefa_matches",
        },
        "players": pelaajat,
        "teams": joukkuetaso(horisontti, kierrokset, odotus, syote),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--takatesti", action="store_true", help="MD1-takatesti")
    ap.add_argument("--md", type=int, default=None, help="kierros (oletus: seuraava)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.takatesti:
        tulos = takatesti_md1(hae_syote(1))
        print(json.dumps(tulos, indent=1))
        return 0
    uf = json.loads((config.DATA_DIR / "ucl_fantasy.json").read_text(encoding="utf-8"))
    md, deadline = seuraava_kierros(uf)
    if args.md:
        md = args.md
    kausi_id = int((uf.get("meta") or {}).get("season_id") or KAUSI_ID)
    if md is None:
        out = suljettu(None, None, "league_phase_over")
    else:
        out = tuota(md, deadline, kausi_id)
    (args.out or OUT).write_text(json.dumps(out, ensure_ascii=False, default=float), encoding="utf-8")
    m = out["meta"]
    if not m.get("available"):
        print(f"UCL xP: ei tarjolla ({m.get('reason')}), suljettu artefakti kirjoitettu")
    else:
        print(f"UCL xP MD{md}: {len(out['players'])} pelaajaa, horisontti {m['horizon_gw']}, "
              f"datapohja {m['data_basis_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
