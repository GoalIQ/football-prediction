"""Portti: UEFAn ottelulahde (src/data/uefa_matches.py) ja maaryhmaprior.

🔴 MIKSI (21.9.2026, UCL-KATTAVUUS-ILMAISELLA-DATALLA). CL-mallissa LASKilla
oli yksi ottelu, Vikingilla viisi ja Sabahilla yksitoista, ja Sabah oli
julkisessa ennusteessa 46 %:n kotisuosikki Slavia Prahaa vastaan. Syy oli
kaksiosainen: (1) CL-karsinnat ja kuluvan kauden EL/ECL puuttuivat datasta,
(2) ohut rating kutistui KOKO datan keskiarvoon, joka on suurliigojen taso.
Korjaus on UEFAn oma rajapinta + maakohtainen kutistuskohde, ja kumpikin voi
kadota hiljaa: fitti onnistuu ja API vastaa 200 joka tapauksessa.

Hermeettinen: verkkoa ei kayteta (live-haku mockataan tai luetaan
vendoroitua CSV:ta).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.data import uefa_matches as U
from src.models.uefa_joint import BRIDGE_LEAGUES, canonical_name, fit_uefa_joint

CL = "INT-Champions League"


def _ottelu(pvm, koti, vieras, hs, vs, *, vaihe="TOURNAMENT", status="FINISHED",
            total=None, maa=("AUT", "SCO"), kid="1", vid="2"):
    def _t(n, m, i):
        nimet = n if isinstance(n, tuple) else (n, n, n)
        return {"id": i, "countryCode": m, "internationalName": nimet[1],
                "translations": {"displayOfficialName": {"EN": nimet[0]},
                                 "displayName": {"EN": nimet[2]}}}
    return {
        "status": status, "competitionPhase": vaihe,
        "kickOffTime": {"dateTime": f"{pvm}T19:00:00Z"},
        "homeTeam": _t(koti, maa[0], kid), "awayTeam": _t(vieras, maa[1], vid),
        "score": {"regular": {"home": hs, "away": vs},
                  "total": {"home": total[0], "away": total[1]} if total else
                  {"home": hs, "away": vs}},
    }


# ---------------------------------------------------------------------------
# 1. Rivit: vain pelatut, 90 min tulos, karsinta omalla nimellaan
# ---------------------------------------------------------------------------


def test_rivit_kayttaa_90_minuutin_tulosta_eika_jatkoaikaa():
    d = U.rivit([_ottelu("2026-08-25", "LASK", "Celtic FC", 1, 1, total=(2, 1),
                         vaihe="QUALIFYING")], CL, "2627")
    assert (d.home_score.iloc[0], d.away_score.iloc[0]) == (1, 1)


def test_cl_karsinta_on_siltaa_ei_turnausta():
    d = U.rivit([_ottelu("2026-08-25", "LASK", "Celtic FC", 4, 1, vaihe="QUALIFYING"),
                 _ottelu("2026-09-08", "AEK Athens FC", "LASK", 1, 0)], CL, "2627")
    assert list(d.league) == [U.KARSINTA_LIIGA, CL]


def test_karsintaliiga_on_siltaliiga():
    """Rivi jonka liiga ei ole silta eika turnaus luetaan KOTILIIGAKSI:
    ilman tata Sabahin kotiliiga olisi 'INT-Champions League Qualifying'."""
    assert U.KARSINTA_LIIGA in BRIDGE_LEAGUES


def test_pelaamaton_ja_keskeytetty_ohitetaan():
    d = U.rivit([_ottelu("2026-10-13", "A", "B", 0, 0, status="UPCOMING"),
                 _ottelu("2025-08-01", "A", "B", 3, 0, status="ABANDONED")], CL, "2627")
    assert d.empty


# ---------------------------------------------------------------------------
# 2. Vendoroitu data: paattyneet kaudet repossa, sama ikkuna kuin CL:lla
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("liiga", list(U.KILPAILUT))
def test_paattyneet_kaudet_on_vendoroitu(liiga):
    from src.data.fd_fallback import VENDORED_SEASONS

    for k in VENDORED_SEASONS[CL]:
        p = U._vendor_polku(liiga, k)
        assert p.exists(), f"vendoroitu kausi puuttuu: {p}"
        d = U.lataa_kausi(liiga, k)
        assert len(d) >= 150, f"{liiga} {k}: vain {len(d)} ottelua"
        assert set(d.season.astype(str)) == {k}


def test_vendoroitu_kausi_ei_kayta_verkkoa(monkeypatch):
    monkeypatch.setattr(U.requests, "get", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("vendoroitu kausi ei saa hakea verkosta")))
    assert not U.lataa_kausi("INT-Europa League", "2526").empty


def test_live_kausi_lukee_levyn_kun_haku_epaonnistuu(monkeypatch, tmp_path):
    import json
    import os

    monkeypatch.setattr(U, "CACHE_DIR", tmp_path)
    vanha = [_ottelu("2026-08-25", "LASK", "Celtic FC", 4, 1, vaihe="QUALIFYING")]
    p = tmp_path / "1_2627.json"
    p.write_text(json.dumps(vanha), encoding="utf-8")
    os.utime(p, (0, 0))  # vanhempi kuin TTL -> yrittaa livea

    def kaatuu(*a, **k):
        raise U.requests.ConnectionError("alhaalla")

    monkeypatch.setattr(U.requests, "get", kaatuu)
    d = U.lataa_kausi(CL, "2627")
    assert len(d) == 1 and d.home_team.iloc[0] == "LASK"


# ---------------------------------------------------------------------------
# 3. Nimet: paritus ottelun perusteella, ei merkkijonon
# ---------------------------------------------------------------------------


def _fd(pvm, koti, vieras, hs, vs):
    return {"date": pd.Timestamp(pvm), "home_team": koti, "away_team": vieras,
            "home_score": hs, "away_score": vs, "league": CL}


def test_paritus_yhdistaa_lask_ja_lask_linz():
    """UEFA sanoo 'LASK', fd.org 'LASK Linz': merkkijono ei yhdista, ottelu yhdistaa."""
    u = U.rivit([_ottelu("2026-09-08", ("AEK Athens FC", "AEK Athens", "AEK"), "LASK",
                         1, 0, maa=("GRE", "AUT"), kid="10", vid="20")], CL, "2627")
    f = pd.DataFrame([_fd("2026-09-08", "PAE AEK", "LASK Linz", 1, 0)])
    assert U.paritus_fd_nimiin(u, f) == {"10": "PAE AEK", "20": "LASK Linz"}


def test_paritus_ei_arvaa_kun_tulos_ja_nimet_ovat_monitulkintaisia():
    u = U.rivit([_ottelu("2026-09-08", "Aaa", "Bbb", 1, 0, kid="1", vid="2"),
                 _ottelu("2026-09-08", "Ccc", "Ddd", 1, 0, kid="3", vid="4")], CL, "2627")
    f = pd.DataFrame([_fd("2026-09-08", "Xxx", "Yyy", 1, 0)])
    assert U.paritus_fd_nimiin(u, f) == {}


def test_nimiratkaisun_jarjestys():
    u = U.rivit([
        _ottelu("2026-09-08", "LASK", ("LOSC Lille", "Lille", "Lille"), 0, 1,
                kid="20", vid="30", maa=("AUT", "FRA")),
        _ottelu("2026-07-01", ("Sabah FC", "Sabah", "Sabah"), "KuPS Kuopio", 1, 0,
                kid="40", vid="50", maa=("AZE", "FIN"), vaihe="QUALIFYING"),
    ], CL, "2627")
    f = pd.DataFrame([_fd("2026-09-08", "LASK Linz", "Lille OSC", 0, 1)])
    out, reitti = U.ratkaise_nimet(u, f, kotiliiga_nimet={"Lille OSC", "Lens"})
    assert reitti["20"] == "paritus" and reitti["30"] == "paritus"
    assert reitti["40"] == "uefa" and out.home_team.iloc[1] == "Sabah FC"


def test_tokenijoukko_yhdistaa_kaannetyn_nimen():
    u = U.rivit([_ottelu("2025-08-01", ("KV Club Brugge", "Brugge", "Brugge"), "Foo",
                         2, 0, kid="30", vid="99", maa=("BEL", "XXX"),
                         vaihe="QUALIFYING")], "INT-Europa League", "2526")
    out, reitti = U.ratkaise_nimet(u, pd.DataFrame(columns=["home_team", "away_team",
                                                            "home_score", "away_score", "date"]),
                                   kotiliiga_nimet={"Club Brugge KV"})
    assert reitti["30"] == "tokenit" and out.home_team.iloc[0] == "Club Brugge KV"


# ---------------------------------------------------------------------------
# 4. Maaryhma: ohut seura kutistuu maansa tasolle, ei suurliigojen tasolle
# ---------------------------------------------------------------------------


def _synteettinen_eurooppa(seed=0):
    """Kotiliiga L (12 seuraa) + kaksi pienta maata ilman kotiliigaa:
    VAHVA (3 seuraa jotka voittavat L:n seuroja) ja HEIKKO (3 seuraa jotka
    haviavat kaikille). Jokaisesta maasta yksi OHUT seura jolla on 1 tasapeli."""
    rng = np.random.default_rng(seed)
    L = [f"L{i}" for i in range(12)]
    rows = []
    d0 = pd.Timestamp("2025-08-01")
    for k in range(2):
        for i, h in enumerate(L):
            for j, a in enumerate(L):
                if h != a:
                    rows.append(dict(date=d0 + pd.Timedelta(days=k * 150 + i + j),
                                     home_team=h, away_team=a,
                                     home_score=int(rng.poisson(1.5)),
                                     away_score=int(rng.poisson(1.1)),
                                     league="LIG", season="2526"))
    def uefa(h, a, hs, as_, mh, ma, pv):
        rows.append(dict(date=d0 + pd.Timedelta(days=pv), home_team=h, away_team=a,
                         home_score=hs, away_score=as_, league="INT-Europa League",
                         season="2526", home_maa=mh, away_maa=ma))
    pv = 0
    for v in ("V1", "V2", "V3"):
        for l in L[:8]:
            pv += 1
            uefa(v, l, 3, 0, "VAH", "LIG", pv)
            uefa(l, v, 0, 2, "LIG", "VAH", pv)
    for w in ("H1", "H2", "H3"):
        for l in L[:8]:
            pv += 1
            uefa(w, l, 0, 3, "HEI", "LIG", pv)
            uefa(l, w, 3, 0, "LIG", "HEI", pv)
    uefa("VOHUT", "HOHUT", 1, 1, "VAH", "HEI", pv + 1)
    df = pd.DataFrame(rows)
    df.loc[df.league == "LIG", "league"] = "ENG-Premier League"
    return df


def _vahvuus(m, seura):
    c = canonical_name(seura)
    return m.dc.attack[c] - m.dc.defence[c]


def test_maaryhma_vie_ohuen_seuran_maansa_tasolle():
    df = _synteettinen_eurooppa()
    ilman = fit_uefa_joint(df, tournament_league=CL, decay=0.0)
    kanssa = fit_uefa_joint(df, tournament_league=CL, decay=0.0, team_groups="maa")
    # Ilman ryhmaa ohuet seurat ovat lahes samalla tasolla (sama 1-1; ero on
    # vain kotiedun asetelmasta).
    assert abs(_vahvuus(ilman, "VOHUT") - _vahvuus(ilman, "HOHUT")) < 0.15
    # Ryhman kanssa vahvan maan ohut seura on selvasti heikon maan ohuen ylapuolella.
    ero = _vahvuus(kanssa, "VOHUT") - _vahvuus(kanssa, "HOHUT")
    assert ero > 0.5, ero
    # Ja kumpikin on lahempana omaa maataan kuin ilman ryhmaa.
    assert _vahvuus(kanssa, "HOHUT") < _vahvuus(ilman, "HOHUT")
    assert _vahvuus(kanssa, "VOHUT") > _vahvuus(ilman, "VOHUT")


def test_kotiliigan_seura_ei_saa_ryhmaa():
    from src.models.uefa_joint import _maaryhmat

    df = _synteettinen_eurooppa()
    d = df.copy()
    d["home_team"] = d["home_team"].map(canonical_name)
    d["away_team"] = d["away_team"].map(canonical_name)
    club_league = {c: "ENG-Premier League" for c in ("l0", "l1")}
    r = _maaryhmat(d, club_league)
    assert "l0" not in r and r["v1"] == "maa:VAH" and r["hohut"] == "maa:HEI"


def test_ryhmaton_fitti_on_bittitarkasti_ennallaan():
    """team_groups=None ei saa muuttaa yhtaan lukua (domestic-polku)."""
    from src.models.dixon_coles import DixonColesModel

    df = _synteettinen_eurooppa()
    a = DixonColesModel(per_team_home_adv=False).fit(df, decay=0.0035, date_col="date")
    b = DixonColesModel(per_team_home_adv=False).fit(df, decay=0.0035, date_col="date",
                                                     team_groups=None)
    assert a.attack == b.attack and a.defence == b.defence
    assert a.home_advantage == b.home_advantage and a.rho == b.rho


def test_vendoroitu_data_ei_ole_gitignoressa():
    """`/data/*` on ignoressa. Ilman poikkeusta vendoroidut kaudet jaisivat
    repon ulkopuolelle ja tuotanto hakisi ne livena - tai ei ollenkaan
    (muisti gitignored-fix-silent-regression)."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for p in sorted(U.VENDOR_DIR.glob("*.csv")):
        r = subprocess.run(["git", "check-ignore", "-q", str(p.relative_to(root))],
                           cwd=root, capture_output=True)
        assert r.returncode == 1, f"{p.name} on gitignoressa"
    assert list(U.VENDOR_DIR.glob("*.csv")), "vendoroituja kausia ei ole"


# ---------------------------------------------------------------------------
# 5. Linkitys kotiliigaan: mallinnetun maan seura ei saa jaada kahdeksi
#    entiteetiksi. Vain repossa oleva data (vendoroidut kotiliigat + UEFA).
# ---------------------------------------------------------------------------

_MAAN_LIIGA = {"POR": "POR-Primeira Liga", "NED": "NED-Eredivisie",
               "GRE": "GRE-Super League", "TUR": "TUR-Super Lig"}
_YLEISET = {"real", "sporting", "sport", "club", "clube", "city", "united",
            "athletic", "atletico", "racing", "pae", "sp", "fc", "sc", "spor",
            "kulubu", "de", "e", "cp", "sfp", "fk", "sk", "as", "ac"}


def _kotinimet(liiga):
    from src.data.fd_fallback import lataa_varasnapshot

    d = lataa_varasnapshot(liiga)
    return set(d["home_team"]) | set(d["away_team"])


def test_mallinnetun_maan_uefa_seura_linkittyy_kotiliigaan():
    """21.9 loytyi 12 seuraa (Sporting CP, Benfica, Braga, PAOK, Olympiakos...)
    jotka olivat mallissa kahtena: UEFA/fd.org-nimi ilman kotiliigaa ja
    kotiliigan nimi ilman eurooppalaisia otteluita. Portti: jos UEFA-seuran
    nimella on kotiliigassa ehdokas jonka kanssa se jakaa tunnistavan
    tokenin, mutta kanoninen muoto ei osu, alias puuttuu."""
    u = U.lataa(["2425", "2526"])
    puuttuvat = []
    for maa, liiga in _MAAN_LIIGA.items():
        koti = {canonical_name(n): n for n in _kotinimet(liiga)}
        sub = pd.concat([
            u.loc[u.home_maa == maa, ["home_uefa_id", "home_nimet"]].set_axis(["id", "nimet"], axis=1),
            u.loc[u.away_maa == maa, ["away_uefa_id", "away_nimet"]].set_axis(["id", "nimet"], axis=1),
        ]).drop_duplicates("id")
        for nimet in sub["nimet"]:
            vv = nimet.split("|")
            if any(canonical_name(v) in koti for v in vv):
                continue
            tokenit = {t for v in vv for t in canonical_name(v).split()
                       if len(t) >= 4 and t not in _YLEISET}
            ehd = [n for c, n in koti.items() if tokenit & set(c.split())]
            if ehd:
                puuttuvat.append(f"{maa}: {vv[0]} ~ {ehd}")
    assert not puuttuvat, "alias puuttuu CLUB_ALIASES:sta:\n" + "\n".join(puuttuvat)


@pytest.mark.parametrize("uefa,koti", [
    ("Sporting Clube de Portugal", "Sp Lisbon"),
    ("Sporting CP", "Sp Lisbon"),
    ("Sport Lisboa e Benfica", "Benfica"),
    ("SC Braga", "Sp Braga"),
    ("Vitória SC", "Guimaraes"),
    ("PAOK FC", "PAOK Saloniki"),
    ("PAE Olympiakos SFP", "Olympiakos Piraeus"),
    ("N.E.C. Nijmegen", "Nijmegen"),
    ("Tottenham Hotspur FC", "Tottenham"),
    ("Real Club Celta", "RC Celta de Vigo"),
    ("Racing Club de Strasbourg Alsace", "RC Strasbourg Alsace"),
])
def test_tunnetut_nimiparit_ovat_sama_seura(uefa, koti):
    """Parit joilla ei ole yhteista tokenia (Sporting ~ 'Sp Lisbon') eika
    niita siksi loyda yllaoleva portti."""
    assert canonical_name(uefa) == canonical_name(koti)
