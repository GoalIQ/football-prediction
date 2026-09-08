"""Portti: UEFA-yhteisfitti laajentaa kattavuutta MUTTA ei paasta lapi
seuraa jonka sarjatasoa ei voi kalibroida.

Taustaketju 8.9.2026, kolme Villen havaintoa perakkain:
  1. "champpari ei anna mun ennustaa esim aston villan pelia" -> kattavuus
  2. "Porto 48% city 27%?? Markkina antaa reilusti toistepain" -> realismi
  3. "et keksi mitaan lukuja vaan kaikki pohjautuu malliin" -> menetelma

Yhteisfitti vastaa kaikkiin kolmeen: kotiliigojen ottelut antavat seuralle
ratingin, turnausottelut estimoivat liigan voimakkuussiirtyman, eika mitaan
arvata. Mutta se avaa myos uuden tavan olla vaarassa - liiga jolla ei ole
turnausotteluita saa siirtyman nolla, eli sita kohdellaan CL:n vahvuisena.
Se on tasan Porton tapaus, ja se on taman tiedoston tarkein testi.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.uefa_joint import (
    MIN_BRIDGE_MATCHES,
    canonical_name,
    fit_uefa_joint,
)

CL = "INT-Champions League"
PL = "ENG-Premier League"
HEIKKO = "POR-Primeira Liga"


# ---------------------------------------------------------------------------
# Nimien kanonisointi. Ilman tata koko yhteisfitti on turha.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b",
    [
        ("Aston Villa FC", "Aston Villa"),
        ("Manchester United FC", "Manchester United"),
        ("FC Porto", "Porto"),
        ("Real Betis Balompié", "Real Betis Balompie"),
        ("FC Bayern München", "Bayern Munchen"),
    ],
)
def test_kanonisointi_yhdistaa_saman_seuran(a, b):
    """Mitattu 8.9: ilman kanonisointia CL-osallistujista loytyi kotiliigoista
    25/36, sen kanssa 28/36. Aston Villa ja Manchester United puuttuivat
    vaikka molemmilla on 38 Valioliiga-ottelua - PL-malli kayttaa Understatin
    lyhytnimia, CL football-data.orgin taysnimia."""
    assert canonical_name(a) == canonical_name(b)


def test_kanonisointi_ei_yhdista_eri_seuroja():
    """NEGATIIVINEN KONTROLLI. Liian ahne normalisointi sulauttaisi eri
    seurat yhdeksi ja tuottaisi ennusteen joukkueelle jota ei ole."""
    eri = ["Manchester United FC", "Manchester City FC", "Real Madrid CF",
           "Atletico Madrid", "Inter", "AC Milan"]
    kanoniset = [canonical_name(x) for x in eri]
    assert len(set(kanoniset)) == len(eri), kanoniset


# ---------------------------------------------------------------------------
# Synteettinen data: vahva liiga (paljon siltaotteluita) + heikko liiga (ei
# yhtaan). Naiden EI kuulu kayttaytya samoin.
# ---------------------------------------------------------------------------


def _synteettinen() -> pd.DataFrame:
    rivit = []
    paiva = pd.Timestamp("2026-01-01")

    def lisaa(h, a, hs, as_, liiga, n=1):
        nonlocal paiva
        for _ in range(n):
            paiva = paiva + pd.Timedelta(days=1)
            rivit.append(dict(date=paiva, home_team=h, away_team=a,
                              home_score=hs, away_score=as_, league=liiga))

    vahvat = [f"Strong {i} FC" for i in range(6)]
    for i, h in enumerate(vahvat):
        for j, a in enumerate(vahvat):
            if i != j:
                lisaa(h, a, 2, 1, PL, n=3)
    # Heikko liiga: yksi dominoiva seura, EI yhtaan turnausottelua.
    heikot = [f"Weak {i} FC" for i in range(5)]
    for a in heikot[1:]:
        lisaa(heikot[0], a, 4, 0, HEIKKO, n=6)
        lisaa(a, heikot[0], 0, 3, HEIKKO, n=6)
    for i, h in enumerate(heikot[1:], 1):
        for j, a in enumerate(heikot[1:], 1):
            if i != j:
                lisaa(h, a, 1, 1, HEIKKO, n=3)
    # Siltaottelut: VAIN vahvan liigan seurat pelaavat turnauksessa.
    turnaus = [f"Euro {i} FC" for i in range(4)]
    for t in turnaus:
        for s in vahvat[:3]:
            lisaa(s, t, 2, 1, CL, n=3)
            lisaa(t, s, 1, 2, CL, n=3)
    return pd.DataFrame(rivit)


@pytest.fixture(scope="module")
def malli():
    return fit_uefa_joint(_synteettinen())


def test_kotiliigan_seura_paasee_mukaan_ilman_turnausotteluita(malli):
    """Tama on koko ominaisuuden tarkoitus: Aston Villalla on 38 PL-ottelua
    muttei yhtaan CL-ottelua taman kauden ikkunassa."""
    assert malli.is_eligible("Strong 4 FC")
    assert "strong 4" in [canonical_name(c) for c in malli.eligible_clubs()]


def test_kalibroimattoman_liigan_seura_EI_paase(malli):
    """🔴 TAMAN TIEDOSTON TARKEIN TESTI (Villen "Porto 48% city 27%").

    Heikon liigan dominoija nayttaa fitissa erinomaiselta, koska se voittaa
    heikkoja vastustajia. Ilman siltaotteluita mikaan ei kerro mallille etta
    sarjataso on matala, joten sen siirtyma on nolla ja se paasisi CL:aan
    aliarvioidulla vastuksella. Tuotannossa se oli FC Porto: att +0,316,
    def -0,478, parempi puolustus kuin Manchester Cityllä."""
    assert malli.bridge_counts.get(HEIKKO, 0) == 0
    assert HEIKKO not in malli.calibrated_leagues()
    assert not malli.is_eligible("Weak 0 FC")
    with pytest.raises(ValueError):
        malli.outcome_probabilities("Weak 0 FC", "Strong 0 FC")


def test_kalibroituva_liiga_ylittaa_kynnyksen(malli):
    assert malli.bridge_counts.get(PL, 0) >= MIN_BRIDGE_MATCHES
    assert PL in malli.calibrated_leagues()


def test_turnausseura_paasee_omilla_otteluillaan(malli):
    """Seura jolla EI ole kotiliigaa mallissa (esim. Tsekin liiga) mutta on
    turnausotteluita: rating on jo oikealta tasolta, joten se kelpaa."""
    assert malli.is_eligible("Euro 0 FC")


def test_heikon_liigan_siirtyma_ei_ole_nolla_jos_silta_on_olemassa():
    """Kun heikko liiga SAA turnausotteluita, siirtyman kuuluu olla
    negatiivinen - eli mallin pitaa oppia sarjatason ero datasta eika
    parametrista."""
    d = _synteettinen()
    rivit = []
    paiva = pd.Timestamp("2027-01-01")
    for k in range(30):
        paiva = paiva + pd.Timedelta(days=1)
        rivit.append(dict(date=paiva, home_team="Weak 0 FC", away_team=f"Euro {k%4} FC",
                          home_score=0, away_score=3, league=CL))
    m = fit_uefa_joint(pd.concat([d, pd.DataFrame(rivit)], ignore_index=True))
    assert m.bridge_counts.get(HEIKKO, 0) >= MIN_BRIDGE_MATCHES
    assert m.league_attack.get(HEIKKO, 0.0) < m.league_attack.get(PL, 0.0), (
        "heikon liigan hyokkayssiirtyman pitaa jaada vahvan alle"
    )


def test_todennakoisyydet_summautuvat_ykkoseen(malli):
    p = malli.outcome_probabilities("Strong 0 FC", "Strong 1 FC")
    assert abs(sum(p) - 1.0) < 1e-6
    assert all(0.0 < x < 1.0 for x in p)


def test_kotietu_nakyy(malli):
    """Sama pari molemmin pain: kotijoukkueen voitto-todennakoisyys ei saa
    olla pienempi kotona kuin vieraissa."""
    koti = malli.outcome_probabilities("Strong 0 FC", "Strong 1 FC")
    vieras = malli.outcome_probabilities("Strong 1 FC", "Strong 0 FC")
    assert koti[0] > vieras[2]


def test_kelpoisuus_on_pakko_tarkistaa_ennen_ennustetta(malli):
    """Epakelpo seura ei saa livahtaa ennusteeseen hiljaa: funktio heittaa
    eika palauta 'jotain'. Hiljainen lapipaasy oli se mekanismi joka tuotti
    Porto-luvun."""
    with pytest.raises(ValueError, match="ei kelpaa"):
        malli.outcome_probabilities("Strong 0 FC", "Weak 0 FC")
