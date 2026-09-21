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
KAUSI_ID = 90   # 2026/27 (ingest_ucl.py hakee saman)
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

def hae_syote(md: int) -> list[dict]:
    req = urllib.request.Request(f"{FEED}/players/players_{KAUSI_ID}_en_{md}.json",
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
            loo_syote: list[dict] | None = None) -> dict:
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
        for kausi, w in (("2526", X.EDELLINEN_KAUSI_PAINO), ("2627", 1.0)):
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
    tour = _lataa_otteludata_cached(["INT-Champions League"], ["2324", "2425", "2526", "2627"])
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


def tuota(md: int) -> dict:
    from src.models import uefa_prebuilt
    dc, syy = uefa_prebuilt.load(tournament="INT-Champions League",
                                  season_pair=list(config.current_season_pair()),
                                  decay=0.0035)
    if dc is None:
        raise SystemExit(f"CL-malli ei kelpaa ({syy}) - xP:ta ei rakenneta vanhalla mallilla")
    syote = hae_syote(md)
    ok, n, huonot = X.tarkista_saannot(syote)
    if n and ok < n:
        raise SystemExit(f"UEFA muutti pisteytysta: saannot selittavat {ok}/{n} ({huonot})")
    tour = _cl_data()
    u27 = U.lataa(["2627"])
    nimet = joukkuekartta(u27, tour)
    tiimit = {str(p["tId"]) for p in syote}
    puuttuu = sorted(t for t in tiimit if t not in nimet)
    if puuttuu:
        raise SystemExit(f"joukkuekartasta puuttuu {len(puuttuu)} seuraa: {puuttuu}")
    odotus = odotusfunktio(_Taitettu(dc), nimet, lambda n: n in dc.attack)
    ottelut = ottelut_syotteesta(syote, md)
    t = rakenna(md, ennen=None, syote=syote, odotus=odotus, joukkuenimi=nimet,
                ottelut=ottelut, uefa2627=u27, saatavuus_kaytossa=True)
    return {"meta": {"md": md, "pelaajia": len(t["pelaajat"]), "saannot_selittavat": f"{ok}/{n}",
                     "data_basis": dict(collections.Counter(p["data_basis"] for p in t["pelaajat"]))},
            "pelaajat": sorted(t["pelaajat"], key=lambda p: -p["xp"])}


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
    md = args.md or json.loads((config.DATA_DIR / "ucl_fantasy.json").read_text(encoding="utf-8"))["meta"]["matchday"]
    out = tuota(md)
    (args.out or OUT).write_text(json.dumps(out, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"UCL xP MD{md}: {out['meta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
