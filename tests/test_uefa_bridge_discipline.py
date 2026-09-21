"""Portti: EL/ECL-silta ja GRE/TUR-tukiliigat eivat voi kadota hiljaa.

🔴 MIKSI (10.9.2026, UCL-KATTAVUUS-ILMAISELLA-DATALLA, Villen GO). Pelkasta
CL:sta Eredivisie sai 8 siltaottelua, Kreikka ja Turkki 0, eli niiden seurat
jaivat ilman nappia vaikka kotiliigan data oli olemassa. Korjaus on kolmessa
paikassa, ja jokainen niista voi kadota erikseen ilman etta mikaan muu
testi punastuu:

    1. src/models/uefa_joint.py  BRIDGE_LEAGUES + SUPPORT_LEAGUES
    2. api/main.py               _fit_uefa_yhteismalli lataa siltaliigat
    3. data/fd_fallback/         vendoroitu snapshot (Renderin levy on efemeeri)

Jos yksi katoaa, siltamaara putoaa takaisin 8/0/0:aan ja kalibroituvien
liigojen joukko kutistuu - mutta fitti onnistuu ja API vastaa 200, joten
vika nakyisi vasta kun kayttaja huomaa napin puuttuvan. Tama tiedosto
mittaa jokaisen kolmen erikseen (CLAUDE.md saanto 6a, mekanismi 2).
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.fd_fallback import (
    VENDORED_LEAGUES,
    VENDORED_SEASONS,
    lataa_varasnapshot,
    polku,
)
from src.models.uefa_joint import (
    BRIDGE_LEAGUES,
    MIN_BRIDGE_MATCHES,
    SUPPORT_LEAGUES,
    canonical_name,
    fit_uefa_joint,
)

CL = "INT-Champions League"
EL = "INT-Europa League"
ECL = "INT-Conference League"


# ---------------------------------------------------------------------------
# 1. Konfiguraatio
# ---------------------------------------------------------------------------


def test_siltaliigat_ovat_el_ja_ecl():
    assert set(BRIDGE_LEAGUES) == {EL, ECL}, BRIDGE_LEAGUES


def test_siltaliiga_ei_ole_tukiliiga():
    """Siltaliiga ei saa olla kotiliiga: EL-rivi tekisi seurasta 'EL-liigan'
    seuran ja sen kotiliiga jaisi lukematta."""
    assert not set(BRIDGE_LEAGUES) & set(SUPPORT_LEAGUES)
    assert CL not in SUPPORT_LEAGUES


def test_kreikka_ja_turkki_ovat_tukiliigoja():
    assert "GRE-Super League" in SUPPORT_LEAGUES
    assert "TUR-Super Lig" in SUPPORT_LEAGUES


# ---------------------------------------------------------------------------
# 2. Snapshot: sama ikkuna kuin CL:lla, tiedosto olemassa, joka kausi kantaa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("liiga", BRIDGE_LEAGUES)
def test_siltaliiga_on_vendoroitu_cl_n_ikkunalla(liiga):
    assert liiga in VENDORED_LEAGUES
    assert VENDORED_SEASONS.get(liiga) == VENDORED_SEASONS[CL], (
        f"{liiga}: siltaikkunan on oltava CL:n ikkuna, muuten silta on vajaa "
        f"osalla kausista ja liigasiirtyma vinoutuu"
    )
    assert polku(liiga).exists(), f"snapshot puuttuu: {polku(liiga)}"
    df = lataa_varasnapshot(liiga)
    assert not df.empty
    for k in VENDORED_SEASONS[liiga]:
        n = int((df["season"].astype(str) == k).sum())
        assert n >= 50, f"{liiga} {k}: vain {n} ottelua snapshotissa"


@pytest.mark.parametrize("liiga", ["GRE-Super League", "TUR-Super Lig"])
def test_tukiliigan_snapshot_on_olemassa(liiga):
    assert liiga in VENDORED_LEAGUES
    assert polku(liiga).exists()
    df = lataa_varasnapshot(liiga)
    assert len(df) >= 100, f"{liiga}: {len(df)} ottelua"


# ---------------------------------------------------------------------------
# 3. Fitti: EL-silta kalibroi liigan jolla ei ole CL-otteluita - ja ilman
#    siltaa se EI kalibroidu (mutaatiokontrolli).
# ---------------------------------------------------------------------------


def _data_jossa_silta_on_vain_el() -> pd.DataFrame:
    rivit = []
    paiva = pd.Timestamp("2026-01-01")

    def lisaa(h, a, hs, as_, liiga, n=1):
        nonlocal paiva
        for _ in range(n):
            paiva = paiva + pd.Timedelta(days=1)
            rivit.append(dict(date=paiva, home_team=h, away_team=a,
                              home_score=hs, away_score=as_, league=liiga,
                              season="2526"))

    PL, TUR = "ENG-Premier League", "TUR-Super Lig"
    pl = [f"Strong {i} FC" for i in range(6)]
    tur = [f"Turk {i} SK" for i in range(6)]
    for joukko, liiga in ((pl, PL), (tur, TUR)):
        for i, h in enumerate(joukko):
            for j, a in enumerate(joukko):
                if i != j:
                    lisaa(h, a, 2, 1, liiga, n=2)
    euro = [f"Euro {i} FC" for i in range(4)]
    # CL: vain PL-seurat pelaavat.
    for t in euro:
        for s in pl[:3]:
            lisaa(s, t, 2, 1, CL, n=3)
            lisaa(t, s, 1, 2, CL, n=3)
    # EL: turkkilaiset pelaavat PL-seuroja vastaan -> silta VAIN EL:sta.
    for s in tur[:4]:
        for p in pl[:4]:
            lisaa(s, p, 1, 2, EL, n=2)
            lisaa(p, s, 2, 0, EL, n=2)
    return pd.DataFrame(rivit)


def test_el_silta_kalibroi_liigan_jolla_ei_ole_cl_otteluita():
    d = _data_jossa_silta_on_vain_el()
    m = fit_uefa_joint(d)
    assert m.bridge_counts.get("TUR-Super Lig", 0) >= MIN_BRIDGE_MATCHES
    assert "TUR-Super Lig" in m.calibrated_leagues()
    assert m.is_eligible("Turk 5 SK"), "seura ilman yhtaan EL/CL-ottelua kelpaa liigansa kautta"
    # Siirtyma ei ole nolla: silta opetti liigojen eron.
    assert m.league_attack.get("TUR-Super Lig", 0.0) != 0.0


def test_ilman_siltaliigoja_sama_data_ei_kalibroi():
    """Mutaatiokontrolli: jos BRIDGE_LEAGUES katoaisi, tasan tama tapahtuisi."""
    d = _data_jossa_silta_on_vain_el()
    m = fit_uefa_joint(d, bridge_leagues=())
    assert m.bridge_counts.get("TUR-Super Lig", 0) < MIN_BRIDGE_MATCHES
    assert "TUR-Super Lig" not in m.calibrated_leagues()
    assert not m.is_eligible("Turk 5 SK")


def test_el_ottelu_ei_tee_seurasta_kelpoista():
    """Silta ei ole kelpoisuus: EL-seura jonka kotiliigaa ei mallinneta jaa
    ilman nappia kuten ennenkin (LASK, Viking, Sabah)."""
    d = _data_jossa_silta_on_vain_el()
    paiva = pd.Timestamp("2026-06-01")
    lisa = []
    for k in range(30):
        paiva = paiva + pd.Timedelta(days=1)
        lisa.append(dict(date=paiva, home_team="Orphan FK", away_team=f"Strong {k % 6} FC",
                         home_score=1, away_score=1, league=EL, season="2526"))
    m = fit_uefa_joint(pd.concat([d, pd.DataFrame(lisa)], ignore_index=True))
    orpo = canonical_name("Orphan FK")
    assert orpo in m.dc.attack, "kontrolli: seura on fitissa"
    assert not m.is_eligible("Orphan FK")
    assert m.club_league.get(orpo) is None, "EL-rivi ei saa antaa kotiliigaa"


def test_alias_yhdistaa_cl_nimen_kotiliigan_nimeen():
    """football-data.org 'PAE AEK' vs football.json 'AEK Athen' - ilman
    aliasta seuralla olisi kaksi entiteettia eika kotiliigan data auttaisi."""
    assert canonical_name("PAE AEK") == canonical_name("AEK Athen")
    assert canonical_name("PSV") == canonical_name("PSV Eindhoven")
    assert canonical_name("Feyenoord Rotterdam") == canonical_name("Feyenoord")
    assert canonical_name("Fenerbahçe SK") == canonical_name("Fenerbahçe")


# ---------------------------------------------------------------------------
# 4. API lataa siltaliigat ja antaa kuluvan kauden nimet
# ---------------------------------------------------------------------------


def test_api_lataa_siltaliigat_ja_nimeaa_seurat_fixtures_muodossa(monkeypatch):
    """Kaksi asiaa samasta ajosta: (a) _fit_uefa_yhteismalli pyytaa
    BRIDGE_LEAGUES-liigat loaderilta ja niiden rivit paatyvat siltaan,
    (b) seura joka kelpaa vain kotiliigansa kautta saa football-data.orgin
    nimen (sama kuin /api/fixtures), ei kotiliigan datan nimea."""
    import api.main as M
    from src.data import football_data_org as fdo
    from src.models import uefa_prebuilt as up

    d = _data_jossa_silta_on_vain_el()
    # Kotiliigassa nimi on 'Turk 5 SK'; fixtures sanoo 'Turk 5 Spor Kulubu SK'.
    d.loc[d.home_team == "Turk 5 SK", "home_team"] = "Turk 5"
    d.loc[d.away_team == "Turk 5 SK", "away_team"] = "Turk 5"
    pyydetyt: list[tuple[str, ...]] = []

    def lataa(liigat, kaudet):
        pyydetyt.append(tuple(liigat))
        return d[d.league.isin(list(liigat))].copy()

    monkeypatch.setattr(M, "_lataa_otteludata_cached", lataa)
    monkeypatch.setattr(up, "load", lambda **kw: (None, "testi"))
    monkeypatch.setattr(fdo, "turnauksen_joukkuenimet",
                        lambda liiga, kaudet: {"Turk 5 SK FC"} if liiga == CL else set())
    monkeypatch.setattr("src.data.fd_fallback.lataa_varasnapshot",
                        lambda liiga, kaudet=None: pd.DataFrame(columns=["home_team", "away_team"]))

    dc = M._fit_uefa_yhteismalli((CL,), ("2526", "2627"), 0.0035, allow_prebuilt=False)

    assert tuple(BRIDGE_LEAGUES) in pyydetyt, pyydetyt
    assert "TUR-Super Lig" in dc.uefa_calibrated_leagues_
    assert "Turk 5 SK FC" in dc.attack, sorted(dc.attack)
    assert "Turk 5" not in dc.attack


def test_api_pyytaa_siltaliigat_vain_turnausikkunalla(monkeypatch):
    """Silta EL/ECL:sta samalla ikkunalla kuin CL - ei kotiliigojen parilla."""
    import api.main as M
    from src.models import uefa_prebuilt as up

    d = _data_jossa_silta_on_vain_el()
    kaudet_per_liigat: dict[tuple[str, ...], tuple[str, ...]] = {}

    def lataa(liigat, kaudet):
        kaudet_per_liigat[tuple(liigat)] = tuple(kaudet)
        return d[d.league.isin(list(liigat))].copy()

    monkeypatch.setattr(M, "_lataa_otteludata_cached", lataa)
    monkeypatch.setattr(up, "load", lambda **kw: (None, "testi"))
    M._fit_uefa_yhteismalli((CL,), ("2526", "2627"), 0.0035, allow_prebuilt=False)
    assert kaudet_per_liigat[tuple(BRIDGE_LEAGUES)] == kaudet_per_liigat[(CL,)]
