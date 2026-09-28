# -*- coding: utf-8 -*-
"""XG-NELJA-LIIGAA-UNDERSTAT (28.9.2026): -FD-rivit saavat ottelun xG:n Understatista.

Portti vartioi kolmea asiaa:
1. Korrektius ei nojaa karttaan: rivi saa xG:n VAIN jos Understat-parin tulos
   on sama. Vaara kartta = puuttuva xG, ei vaara xG.
2. Fail-open: Understatin virhe palauttaa FD-rivit muuttumattomina.
3. Kutsupaikka: loaderin FD-haara todella kutsuu rikastusta (muisti:
   testi-kutsuu-funktiota-ei-kutsupaikkaa).
Nimet ovat tuotannon muotoisia (mitattu 28.9: FD 'Stade Rennais FC 1901' vs
Understat 'Rennes' jne.). Kauden vaihe (saanto 6a kohta 3): alkukausi jossa
nousijalla on yksi ottelu ajetaan samalla funktiolla.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data import fd_xg

FD_NIMI = {"Rennes": "Stade Rennais FC 1901", "Marseille": "Olympique de Marseille",
           "Lens": "Racing Club de Lens", "Lyon": "Olympique Lyonnais", "Monaco": "AS Monaco FC",
           "Nice": "OGC Nice"}
US = list(FD_NIMI)


def _kierrokset(n_kierros: int, alku="2025-08-16"):
    """Round-robin-kierrokset kuudelle joukkueelle, kolme ottelua per paiva."""
    rivit = []
    t = US[:]
    for k in range(n_kierros):
        d = pd.Timestamp(alku) + pd.Timedelta(days=7 * k)
        kiinni, loput = t[0], t[1:]
        loput = loput[k % 5:] + loput[:k % 5]
        jarj = [kiinni] + loput
        for i in range(3):
            h, a = jarj[i], jarj[5 - i]
            if k % 2:
                h, a = a, h
            hs, as_ = (k + i) % 3, (k * 2 + i) % 2
            rivit.append({"date": d, "home_team": h, "away_team": a, "home_score": hs,
                          "away_score": as_, "home_xg": 1.0 + 0.1 * i + 0.01 * k,
                          "away_xg": 0.5 + 0.1 * i + 0.01 * k})
    return pd.DataFrame(rivit)


def _fd(us: pd.DataFrame, siirto_paiva=0) -> pd.DataFrame:
    fd = us[["date", "home_team", "away_team", "home_score", "away_score"]].copy()
    fd["home_team"] = fd.home_team.map(FD_NIMI)
    fd["away_team"] = fd.away_team.map(FD_NIMI)
    fd["date"] = fd.date + pd.Timedelta(days=siirto_paiva)
    fd["home_xg"] = pd.NA
    fd["away_xg"] = pd.NA
    fd["league"] = "FRA-Ligue 1-FD"
    return fd


def test_kartta_paatellaan_datasta_ja_on_yksi_yhteen():
    us = _kierrokset(8)
    kartta = fd_xg.joukkuekartta(_fd(us), us)
    assert kartta == {v: k for k, v in FD_NIMI.items()}


def test_rikastus_kirjoittaa_oikean_xgn_jokaiselle_riville():
    us = _kierrokset(8)
    out, t = fd_xg.rikasta(_fd(us, siirto_paiva=1), us)   # FD UTC-paiva +1
    assert t["ok"] == len(us) and t["tulos_eri"] == 0
    assert out.home_xg.tolist() == pytest.approx(us.home_xg.tolist())
    assert out.away_xg.tolist() == pytest.approx(us.away_xg.tolist())
    assert out.home_team.tolist() == _fd(us).home_team.tolist(), "FD-nimet eivat saa muuttua"


def test_eri_tulos_ei_saa_xgta():
    us = _kierrokset(8)
    fd = _fd(us)
    fd.loc[3, "home_score"] = fd.loc[3, "home_score"] + 5
    out, t = fd_xg.rikasta(fd, us)
    assert t["tulos_eri"] == 1
    assert pd.isna(out.loc[3, "home_xg"]) and pd.isna(out.loc[3, "away_xg"])
    assert out.home_xg.notna().sum() == len(us) - 1


def test_puuttuva_understat_ottelu_jaa_ilman_xgta():
    us = _kierrokset(8)
    out, t = fd_xg.rikasta(_fd(us), us.drop(index=5))
    assert t["ei_paria"] == 1 and pd.isna(out.loc[5, "home_xg"])


def test_alkukausi_nousija_yhdella_ottelulla_ei_saa_vaaraa_xgta():
    """Vaihe: kauden alku. Kaikki rikastetut arvot ovat oikean ottelun arvoja,
    vaikka kartta olisi ohut; puuttuva on sallittu, vaara ei."""
    for n in (1, 2, 3):
        us = _kierrokset(n)
        out, _t = fd_xg.rikasta(_fd(us), us)
        mask = out.home_xg.notna()
        assert (out.loc[mask, "home_xg"].values == us.loc[mask, "home_xg"].values).all(), n
        assert (out.loc[mask, "away_xg"].values == us.loc[mask, "away_xg"].values).all(), n


def test_tasapeli_aanissa_ei_tuota_paria():
    fd = pd.DataFrame([{"date": pd.Timestamp("2025-08-16"), "home_team": "A FC",
                        "away_team": "B FC", "home_score": 1, "away_score": 0}])
    us = pd.DataFrame([
        {"date": pd.Timestamp("2025-08-16"), "home_team": "A", "away_team": "B",
         "home_score": 1, "away_score": 0, "home_xg": 1.2, "away_xg": 0.4},
        {"date": pd.Timestamp("2025-08-16"), "home_team": "C", "away_team": "D",
         "home_score": 2, "away_score": 2, "home_xg": 1.0, "away_xg": 1.0}])
    assert fd_xg.joukkuekartta(fd, us) == {}
    out, t = fd_xg.rikasta(fd, us)
    assert pd.isna(out.loc[0, "home_xg"]) and t["ok"] == 0


def test_fail_open_understat_virhe_palauttaa_fd_rivit():
    us = _kierrokset(4)
    fd = _fd(us)

    def kaatuu(koodi, kaudet):
        raise RuntimeError("tls_requests: 403")
    out = fd_xg.rikasta_liiga("FRA-Ligue 1-FD", fd, ["2526"], kaatuu)
    assert out is fd


def test_ei_fd_liiga_ei_kutsu_understatia():
    fd = _fd(_kierrokset(2))

    def ei_saa(koodi, kaudet):
        raise AssertionError("Understatia kutsuttiin liigalle jolla ei ole karttaa")
    assert fd_xg.rikasta_liiga("NED-Eredivisie", fd, ["2526"], ei_saa) is fd


def test_understat_koodi_on_loaderin_understat_liiga():
    from src.data.loader import UNDERSTAT_LEAGUES
    from src.data.football_data_org import COMPETITION_CODES
    for fd_koodi, us_koodi in fd_xg.UNDERSTAT_FOR_FD.items():
        assert fd_koodi in COMPETITION_CODES, fd_koodi
        assert us_koodi in UNDERSTAT_LEAGUES, us_koodi


def test_loaderin_fd_haara_kutsuu_rikastusta(monkeypatch):
    """Kutsupaikka: FD-haara ajaa rikastuksen ennen kuin rivit menevat fittiin."""
    import src.data.loader as L
    us = _kierrokset(6)
    fd = _fd(us)
    fd["league"] = "FRA-Ligue 1-FD"
    monkeypatch.setattr(L, "api_key_kunnossa", lambda: True)
    monkeypatch.setattr(L, "lataa_fdorg", lambda liiga, kaudet: fd.copy())
    monkeypatch.setattr(L, "_understat_rivit", lambda koodi, kaudet: us.copy())
    t = L.lataa_otteludata_yksityiskohtaisesti(["FRA-Ligue 1-FD"], ["2526"])
    assert t.onnistui.get("FRA-Ligue 1-FD") == len(fd)
    assert t.data.home_xg.notna().sum() == len(fd)
    assert set(t.data.home_team) == set(FD_NIMI.values())
