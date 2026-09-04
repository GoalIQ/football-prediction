"""Portti: jakokortin vertailurivi mahtuu korttiin ja lukee optimal_provenin.

🔴 JULKAISUPORTIN LOYDOS 4.9.2026, kaksi vikaa samalla rivilla.

**(1) Vaite ilman porttia.** `career.html` kirjoitti *"% of the best possible
budget squad"* lukematta `optimal_proven`ia. SPA lukee sen oikein
(`RateTeam.svelte`), joten sama vaite kulki kahta polkua ja vain toinen oli
portin takana. `_model_teaser` ei edes valittanyt lippua eteenpain.

Mitattu entryilla 116920 samana paivana:

    team_xp_horizon_no_captain : 322.42
    optimal_team_xp            : 310.77   <- "best possible budget squad"
    beats_benchmark            : True
    percentile                 : 100.0    <- leikattu min(100, ...)
    optimal_proven             : False

Vertailukohta ei siis ole yalaraja lainkaan: kayttajan oma joukkue voittaa
sen, ja kortti olisi tulostanut "100% of the best possible budget squad".
Tasan se ontto imartelu jota `fpl_rate_team.py:666` varoittaa.

**(2) Korjaus ei mahtunut korttiin.** Ensimmainen korjausyritys oli 55
merkkia. Kortti on 1080 px, rivi alkaa x=100 ja laatikon reuna on 1016, eli
kaytettavissa on 916 px. IBM Plex Mono on monospace 0.6 em -> 40 px:lla
24 px/merkki -> **37 merkkia**. Vanha rivi oli 38 merkkia = 912 px, eli
**nelja pikselia** pelivaraa, eika sita tiennyt kukaan. Uusi teksti olisi
leikannut vaitteen kesken sanan (muisti: jakokortti verifioidaan kuvana).

Tama portti laskee leveyden monospace-metriikasta jokaiselle haaralle ja
ääriarvoille. Se ei korvaa kuvatarkistusta, mutta se kaataa ylivuodon ennen
kuin kukaan generoi korttia.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
CARD = ROOT / "career.html"
CAREER_PY = ROOT / "src" / "models" / "fpl_career.py"

# career.html: W = 1080, PAD = 72, teksti alkaa PAD + 28, laatikko paattyy
# W - PAD + 8. IBM Plex Mono askelleveys 0.6 em; kapein fallback (Consolas)
# 0.55 em, joten 0.6 on konservatiivinen.
W, PAD = 1080, 72
X = PAD + 28
KAYTETTAVISSA = (W - PAD + 8) - X          # 916
EM = 0.6
KOKO = 40
MAX_MERKKIA = int(KAYTETTAVISSA / (EM * KOKO))   # 38 -> kaytannon raja 37


def leveys(teksti: str, koko: int = KOKO) -> float:
    return len(teksti) * EM * koko


# Kortin kolme haaraa, kirjoitettuna auki samoilla saannoilla kuin JS.
def rivi(*, beats: bool, proven: bool | None, pct: float, xp: float | None,
         horizon: int | None) -> str:
    win = ", %d GW" % horizon if horizon else ""
    ref = "our best found XI" if proven is False else "the best possible XI"
    if beats and xp is not None:
        merkki = "+" if xp >= 0 else ""
        return "%s%.1f xP vs %s%s" % (merkki, xp, ref, win)
    return "%.0f%% of %s%s" % (pct, ref, win)


TAPAUKSET = [
    # tavallinen: voittaa vertailukohdan
    dict(beats=True, proven=False, pct=100.0, xp=11.7, horizon=6),
    # ei voita, hakua ei todistettu
    dict(beats=False, proven=False, pct=96.0, xp=None, horizon=6),
    # todistettu optimi
    dict(beats=False, proven=True, pct=88.0, xp=None, horizon=6),
    # aariarvot: kaksinumeroinen horisontti, kolminumeroinen prosentti
    dict(beats=False, proven=True, pct=100.0, xp=None, horizon=38),
    dict(beats=True, proven=False, pct=100.0, xp=123.4, horizon=38),
    # negatiivinen ylijaama (ei pitaisi tapahtua beats=True:lla, mutta
    # merkkijonon on silti mahduttava)
    dict(beats=True, proven=False, pct=100.0, xp=-9.9, horizon=12),
    # horisontti puuttuu
    dict(beats=True, proven=False, pct=100.0, xp=11.7, horizon=None),
]


@pytest.mark.parametrize("tapaus", TAPAUKSET)
def test_rivi_mahtuu_korttiin(tapaus):
    teksti = rivi(**tapaus)
    lev = leveys(teksti)
    assert lev <= KAYTETTAVISSA, (
        "%d merkkia = %.0f px > %d px: %r" % (len(teksti), lev,
                                              KAYTETTAVISSA, teksti))


def test_kontrolli_vanha_ylivuotanut_teksti_kaatuisi():
    """Ilman tata kontrollia testi voisi lapaista koska mittari on rikki."""
    ylivuoto = "Ahead of the strongest squad our search found over 6 GW"
    assert len(ylivuoto) == 55
    assert leveys(ylivuoto) > KAYTETTAVISSA


def test_kontrolli_vanha_rivi_oli_nelja_pikselia_rajalla():
    """Mitattu tosiasia joka selittaa miksi rivilla ei ollut varaa kasvaa."""
    vanha = "100% of the best possible budget squad"
    assert len(vanha) == 38
    assert 0 < KAYTETTAVISSA - leveys(vanha) <= 8


# --- kytkenta: kortti lukee lipun ja teaser valittaa sen -------------------

def test_kortti_lukee_optimal_provenin_ja_beats_benchmarkin():
    kortti = CARD.read_text(encoding="utf-8")
    for kentta in ("optimal_proven", "beats_benchmark", "xp_vs_benchmark",
                   "horizon_gw"):
        assert kentta in kortti, kentta
    assert "best possible budget squad" not in kortti, (
        "hedgaamaton vaite on yha kortissa")


def test_kortti_kayttaa_fittextia_takarajana():
    """Merkkimaara muuttuu datan mukana, joten laskettu raja ei riita yksin."""
    kortti = CARD.read_text(encoding="utf-8")
    i = kortti.index("benchPct")
    lohko = kortti[i:i + 1400]
    assert "fitText(benchPct" in lohko, lohko[-500:]


def test_teaser_valittaa_kentat():
    """Ilman naita kortin `t.optimal_proven === false` on `undefined === false`
    eli False, ja kortti putoaisi hedgaamattomaan haaraan. Fail-open."""
    src = CAREER_PY.read_text(encoding="utf-8")
    i = src.index("def _model_teaser")
    lohko = src[i:i + 3000]
    for kentta in ("optimal_proven", "beats_benchmark", "xp_vs_benchmark",
                   "horizon_gw"):
        assert '"%s"' % kentta in lohko, kentta


def test_ylijaama_lasketaan_kapteenittomasta_sarakkeesta():
    """`optimal_team_xp` on kapteeniton XI-summa. Kapteenillinen luku samassa
    erotuksessa olisi luku vaarasta sarakkeesta (mitattu: 356,7 vs 322,42)."""
    from src.models.fpl_career import _xp_vs_benchmark
    assert _xp_vs_benchmark(
        {"team_xp_horizon_no_captain": 322.42,
         "optimal_team_xp": 310.77}) == 11.7
    # puuttuva kentta -> None, ei arvausta
    assert _xp_vs_benchmark({"optimal_team_xp": 310.77}) is None
    assert _xp_vs_benchmark({"team_xp_horizon_no_captain": 322.42}) is None
    assert _xp_vs_benchmark({}) is None


def test_negatiivinen_kontrolli_kapteenillinen_antaisi_eri_luvun():
    """Mittarin on erotettava sarakkeet, muuten testi lapaisisi vaarallakin."""
    from src.models.fpl_career import _xp_vs_benchmark
    oikein = _xp_vs_benchmark({"team_xp_horizon_no_captain": 322.42,
                               "optimal_team_xp": 310.77})
    vaarin = round(356.7 - 310.77, 1)
    assert oikein != vaarin
