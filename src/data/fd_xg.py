# -*- coding: utf-8 -*-
"""Ottelutason xG football-data.org-riveille Understatista (XG-NELJA-LIIGAA-UNDERSTAT, 28.9.2026).

ONGELMA. xG-painotettu likelihood (config.DIXON_COLES_XG_WEIGHT, 17.8) mitattiin
Understat-koodeilla ("ESP-La Liga" jne.) ja se paransi log-lossia kaikissa
viidessa liigassa. Mutta tuote (appi, SPA, julkinen ennusteloki, CL-yhteisfitti)
kayttaa La Ligalle, Bundesligalle, Serie A:lle ja Ligue 1:lle `-FD`-koodeja,
joiden rivit tulevat football-data.org:sta `home_xg = pd.NA`:lla. Fitin xG-termi
oli siis naille nelja liigalle inertti, ja llms.txt + predictions-FAQ vaittivat
toisin (julkaisutarkistaja 28.9). Koodien vaihtaminen Understat-koodeihin
vaihtaisi joukkuenimet kaikilla pinnoilla ("Real Madrid CF" -> "Real Madrid"),
joten xG tuodaan FD-riveille nimet ennallaan.

MITATTU 28.9 tuotteen polulla (FD-rivit 25/26, tuotannon fit-parametrit,
walk-forward, samat ottelut, xg_weight 0.0 -> 0.5):
    La Liga     0,9934 -> 0,9865  (n 280)
    Bundesliga  1,0189 -> 1,0083  (n 206)
    Serie A     1,0103 -> 1,0046  (n 280)
    Ligue 1     1,0251 -> 1,0107  (n 205)
Liitos: 346/380, 278/306, 350/380, 304/305 ottelua, tulos eri 0 kaikissa.

LIITOS. Joukkuenimet eivat ole samoja ("Stade Rennais FC 1901" / "Rennes"), eika
kasin yllapidetty nimilista pysy nousijoiden mukana. Kartta paatellaan
datasta: saman paivan (+-1) otteluissa FD:n kotijoukkue aanestaa Understatin
kotijoukkuetta ja vieras vierasta. Oikea pari saa aanen joka kierroksella,
vaarat hajoavat. Kartta hyvaksytaan vain yksi-yhteen.

🔴 KORREKTIUS EI NOJAA KARTTAAN: rivi saa xG:n VAIN jos Understatin ottelun
tulos on sama kuin FD:n. Vaara kartta tuottaa siis puuttuvan xG:n (fitti
kayttaa silloin maaleja, kuten ennen), ei vaaraa xG:ta.

FAIL-OPEN: jos Understat ei vastaa, FD-rivit palautetaan muuttumattomina.
Ennuste on silloin sama kuin ennen tata muutosta, ei virhe.
"""
from __future__ import annotations

import collections

import pandas as pd

# FD-koodi -> Understat-koodi. Vain liigat joille Understat antaa xG:n.
UNDERSTAT_FOR_FD: dict[str, str] = {
    "ESP-La Liga-FD": "ESP-La Liga",
    "GER-Bundesliga-FD": "GER-Bundesliga",
    "ITA-Serie A-FD": "ITA-Serie A",
    "FRA-Ligue 1-FD": "FRA-Ligue 1",
}

PAIVA_TOLERANSSI = (0, -1, 1)


def _paiva(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s)
    if getattr(d.dt, "tz", None) is not None:
        d = d.dt.tz_convert(None)
    return d.dt.normalize()


def joukkuekartta(fd: pd.DataFrame, us: pd.DataFrame) -> dict[str, str]:
    """{FD-nimi: Understat-nimi} aanestamalla saman paivan otteluista.

    Pari hyvaksytaan vain jos se on FD-joukkueen yksiselitteinen karki (ei
    tasapelia) JA kukaan muu FD-joukkue ei vaadi samaa Understat-nimea
    useammalla aanella (yksi-yhteen)."""
    if fd.empty or us.empty:
        return {}
    fd_p, us_p = _paiva(fd["date"]), _paiva(us["date"])
    us_paivat = collections.defaultdict(list)
    for d, h, a in zip(us_p, us["home_team"], us["away_team"]):
        us_paivat[d].append((h, a))
    aanet: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for d, h, a in zip(fd_p, fd["home_team"], fd["away_team"]):
        for dd in PAIVA_TOLERANSSI:
            for uh, ua in us_paivat.get(d + pd.Timedelta(days=dd), ()):
                aanet[h][uh] += 1
                aanet[a][ua] += 1
    ehdokas: dict[str, tuple[str, int]] = {}
    for t, c in aanet.items():
        top = c.most_common(2)
        if len(top) == 2 and top[0][1] == top[1][1]:
            continue
        ehdokas[t] = top[0]
    varattu: dict[str, tuple[str, int]] = {}
    for t, (u, n) in ehdokas.items():
        if u not in varattu or n > varattu[u][1]:
            varattu[u] = (t, n)
    kartta = {t: u for u, (t, _n) in varattu.items()}
    return _ankkuroi(kartta, fd_p, fd, us_paivat)


def _ankkuroi(kartta: dict[str, str], fd_p, fd: pd.DataFrame, us_paivat) -> dict[str, str]:
    """Toinen kierros: tuntematon joukkue tunnistetaan tunnetun vastustajan kautta.

    Julkaisutarkistaja 28.9: ensimmainen kierros ei kartoittanut NOUSIJOITA
    kauden alussa (liian vahan aania, tasapeli) -> Bundesliga 26/27 25/36 rivia,
    Elversberg/Paderborn/Schalke kokonaan ilman xG:ta, sama joka elokuu. Kun
    ottelun toinen puoli on kartassa, saman paivan (+-1) Understat-ottelu jossa
    se pelaa SAMALLA puolella kertoo toisen puolen nimen. Hyvaksytaan vain
    yksiselitteinen karki ja vapaa Understat-nimi; tulosvartija (rikasta)
    estaa silti vaaran xG:n."""
    kartta = dict(kartta)
    for _ in range(3):   # ankkuroitu joukkue voi ankkuroida seuraavan
        vapaat = {n for pari in us_paivat.values() for hu in pari for n in hu}
        vapaat -= set(kartta.values())
        aanet: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for d, h, a in zip(fd_p, fd["home_team"], fd["away_team"]):
            for tunnettu, tuntematon, puoli in ((h, a, 0), (a, h, 1)):
                if tunnettu not in kartta or tuntematon in kartta:
                    continue
                for dd in PAIVA_TOLERANSSI:
                    for pari in us_paivat.get(d + pd.Timedelta(days=dd), ()):
                        if pari[puoli] == kartta[tunnettu] and pari[1 - puoli] in vapaat:
                            aanet[tuntematon][pari[1 - puoli]] += 1
        varattu: dict[str, tuple[str, int]] = {}
        for t, c in aanet.items():
            top = c.most_common(2)
            if len(top) == 2 and top[0][1] == top[1][1]:
                continue
            u, n = top[0]
            if u not in varattu or n > varattu[u][1]:
                varattu[u] = (t, n)
        if not varattu:
            break
        for u, (t, _n) in varattu.items():
            kartta[t] = u
    return kartta


def rikasta(fd: pd.DataFrame, us: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """FD-rivit + home_xg/away_xg Understatista. Palauttaa (df, tilasto).

    xG kirjoitetaan vain riville jonka Understat-parin tulos on sama."""
    out = fd.copy()
    # Tavallinen float NaN:lla (ei nullable Float64): fitti laskee numpylla.
    for c in ("home_xg", "away_xg"):
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float) if c in out else float("nan")
    tilasto = {"rivit": len(fd), "ok": 0, "tulos_eri": 0, "ei_paria": 0, "kartta": 0}
    if fd.empty or us.empty or not {"home_xg", "away_xg"} <= set(us.columns):
        return out, tilasto
    kartta = joukkuekartta(fd, us)
    tilasto["kartta"] = len(kartta)
    us_p = _paiva(us["date"])
    avain = {}
    for d, h, a, hs, as_, hx, ax in zip(us_p, us["home_team"], us["away_team"], us["home_score"],
                                        us["away_score"], us["home_xg"], us["away_xg"]):
        avain[(d, h, a)] = (hs, as_, hx, ax)
    fd_p = _paiva(fd["date"])
    hx_col, ax_col = out.columns.get_loc("home_xg"), out.columns.get_loc("away_xg")
    for i, (d, h, a, hs, as_) in enumerate(zip(fd_p, fd["home_team"], fd["away_team"],
                                               fd["home_score"], fd["away_score"])):
        if pd.isna(hs) or pd.isna(as_):
            continue
        uh, ua = kartta.get(h), kartta.get(a)
        pari = None
        if uh is not None and ua is not None:
            for dd in PAIVA_TOLERANSSI:
                pari = avain.get((d + pd.Timedelta(days=dd), uh, ua))
                if pari is not None:
                    break
        if pari is None:
            tilasto["ei_paria"] += 1
            continue
        u_hs, u_as, u_hx, u_ax = pari
        if pd.isna(u_hs) or (int(u_hs), int(u_as)) != (int(hs), int(as_)):
            tilasto["tulos_eri"] += 1
            continue
        if pd.isna(u_hx) or pd.isna(u_ax):
            tilasto["ei_paria"] += 1
            continue
        out.iat[i, hx_col] = float(u_hx)
        out.iat[i, ax_col] = float(u_ax)
        tilasto["ok"] += 1
    return out, tilasto


def rikasta_liiga(liiga: str, fd: pd.DataFrame, kaudet,
                  lataa_understat) -> tuple[pd.DataFrame, dict | None]:
    """Loaderin kutsupaikka. `lataa_understat(understat_koodi, kaudet)` palauttaa
    Understat-rivit (home_score/away_score/home_xg/away_xg). Fail-open.

    Palauttaa (df, tilasto). Tilasto None = liigalla ei ole Understat-paria
    (ei yritetty). Epaonnistuminen EI ole hiljainen: tilastossa on `virhe`,
    loader kirjaa sen `LoaderTulokset.fd_xg`:hen ja /api/debug/load nayttaa sen
    (julkaisutarkistaja 28.9: ilman tata copyn "xG viidessa liigassa" -vaitetta
    ei voinut mitata tuotannosta, koska rikastamaton ja rikastettu data nayttavat
    samalta sarakelistalta)."""
    koodi = UNDERSTAT_FOR_FD.get(liiga)
    if koodi is None or fd.empty:
        return fd, None
    try:
        us = lataa_understat(koodi, list(kaudet))
    except Exception as e:
        print(f"[fd_xg] {liiga}: Understat ei vastannut ({type(e).__name__}: {e}) -> ilman xG:ta")
        return fd, {"rivit": len(fd), "ok": 0, "virhe": f"{type(e).__name__}: {e}"[:300]}
    out, t = rikasta(fd, us)
    print(f"[fd_xg] {liiga}: xG {t['ok']}/{t['rivit']} rivia (tulos eri {t['tulos_eri']}, "
          f"ei paria {t['ei_paria']}, kartta {t['kartta']})")
    return out, t
