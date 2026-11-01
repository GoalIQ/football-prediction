"""EI KERTOIMIA (ulkoasu WP1, Villen paatos 1.11.2026, raportin kohta A4).

GoalIQ ei nayta mitaan mika nayttaa vedonlyontikertoimelta. Ennen 1.11:
  * SPA:n Predict nayttaa Premiumille "Model fair value: 4.01 / 3.44 / 2.17"
    (1 / todennakoisyys, eli desimaalikerroin),
  * `/api/predict` ja `/api/predict-wc` palauttivat `fair_odds_home/draw/away`
    kaikille: maski (PREDICT_MASK) nollasi ne anonyymilta, mutta avaimet
    sailyivat ja lippu pois -tilassa arvot olivat aitoja.

Syy on myynti, ei maku: App Storen ikaraja on 4+, ja desimaalikerroin on
tuotteen ainoa elementti joka voi tuoda takaisin 18+ "simulated gambling"
-luokituksen. 18+ estaa myynnin kymmenessa maassa (AE AF BR GA IQ KR LY MA
MV SA, mitattu 17.10).

Saanto 6a, kolme lukkoa:
  1. Skeema: julkisen API:n OpenAPI-skeemassa ei ole yhtaan kenttaa jonka
     nimessa on "odds". Koskee KAIKKIA endpointteja, ei vain ennustetta.
  2. Vastaus: kumpikin ennuste-endpoint, jokaisella kutsujalla (anonyymi lippu
     pois / lippu paalla, Premium, admin) -> ei kerroinavainta, ei
     kerroinsanastoa merkkijonoissa eika lukua joka on 1 / p (1X2). Viimeinen
     erottelee: kerroin uudella nimella (`model_price_home`) jaisi kiinni.
  3. SPA:n lahde: "fair value" / fair_odds / odds / bookmaker ei palaa
     web/pro-spa:n lahteeseen. Poikkeus vain listalla perustelun kanssa.

Mobiili (goaliq-app) EI ole tassa: se on eri repo, ja sen PredictScreen
vahtii kenttaa `prediction.fair_odds_home != null`:lla, eli puuttuva avain
piilottaa osion eika kaada nakymaa. Mobiilin kuollut koodi ja i18n-rivit
poistetaan omassa OTA-paketissa (WP4).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.test_predict_mask import (  # noqa: F401 - pm_client-fixture kayttoon
    ADMIN,
    ENDPOINTS,
    _as_premium,
    _mask_on,
    _post,
    pm_client,
)

ROOT = Path(__file__).resolve().parents[1]

#: Avain joka nimeaa kertoimen tai sen kiertonimen.
KERROINAVAIN = re.compile(r"odds|fair|implied|decimal|bookmaker", re.I)

#: Sanasto joka lukee vedonlyontikertoimelta. Sama lista API:n merkkijonoille
#: ja SPA:n lahteelle.
KERROINSANAT = re.compile(
    r"fair[\s_-]*(?:value|odds)|fair(?:Odds|Value)|\bodds\b|bookmaker|"
    r"decimal[\s_-]*(?:odds|value)",
    re.I,
)


def _avaimet(o, polku=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{polku}/{k}", k
            yield from _avaimet(v, f"{polku}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _avaimet(v, f"{polku}[{i}]")


def _lehdet(o, polku=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _lehdet(v, f"{polku}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _lehdet(v, f"{polku}[{i}]")
    else:
        yield polku, o


# ---------------------------------------------------------------------------
# 1. Skeema: yksikaan julkinen endpoint ei julista kerroinkenttaa
# ---------------------------------------------------------------------------

#: Skeemapolku -> perustelu. Tyhja 1.11.2026. Uusi rivi vaatii perustelun,
#: ja vanhentunut rivi (polkua ei enaa ole) kaataa testin.
SALLITUT_SKEEMAPOLUT: dict[str, str] = {}


def test_openapi_skeemassa_ei_kerroinkenttaa():
    from api.main import app

    osumat = [p for p, k in _avaimet(app.openapi())
              if "odds" in k.lower() and p not in SALLITUT_SKEEMAPOLUT]
    assert not osumat, (
        "kerroinkentta julkisessa API-skeemassa (ulkoasu WP1: GoalIQ ei nayta "
        f"kertoimia, App Store 4+): {osumat}")


def test_skeeman_poikkeuslista_on_perusteltu_ja_ajan_tasalla():
    from api.main import app

    polut = {p for p, _ in _avaimet(app.openapi())}
    for polku, perustelu in SALLITUT_SKEEMAPOLUT.items():
        assert perustelu.strip(), f"{polku}: poikkeus ilman perustelua"
        assert polku in polut, f"{polku}: vanhentunut poikkeus, poista rivi"


# ---------------------------------------------------------------------------
# 2. Vastaus: ei kerrointa yhdellekaan kutsujalle
# ---------------------------------------------------------------------------

KUTSUJAT = ["anonyymi_lippu_pois", "anonyymi_maski_paalla", "premium", "admin"]


def _vastaus(client, monkeypatch, path, body, kutsuja) -> dict:
    headers: dict = {}
    if kutsuja == "anonyymi_lippu_pois":
        monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    else:
        _mask_on(monkeypatch)
        if kutsuja == "premium":
            headers = _as_premium(monkeypatch)
        elif kutsuja == "admin":
            monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
            headers = {"X-Admin-Token": ADMIN}
    d = _post(client, path, body, headers).json()
    # Erotteleva: maskaamattomilla kutsujilla Premium-luvut ovat aitoja, eli
    # testi mittaa tayden vastauksen eika tyhjaa kuorta.
    if kutsuja == "anonyymi_maski_paalla":
        assert d["meta"]["masked"] is True
    else:
        assert "meta" not in d and d["expected_goals_home"] > 0, kutsuja
    return d


@pytest.mark.parametrize("kutsuja", KUTSUJAT)
@pytest.mark.parametrize("path,body", ENDPOINTS)
def test_ennustevastauksessa_ei_kerroinavainta(pm_client, monkeypatch, path,
                                               body, kutsuja):
    d = _vastaus(pm_client, monkeypatch, path, body, kutsuja)
    osumat = [p for p, k in _avaimet(d) if KERROINAVAIN.search(k)]
    assert not osumat, f"{path} ({kutsuja}): kerroinavain vastauksessa: {osumat}"


@pytest.mark.parametrize("kutsuja", KUTSUJAT)
@pytest.mark.parametrize("path,body", ENDPOINTS)
def test_ennustevastauksen_teksti_ei_puhu_kertoimista(pm_client, monkeypatch,
                                                      path, body, kutsuja):
    """Merkkijonot mukaan lukien `meta.mask`, joka oli ennen 1.11 luvannut
    Premiumin avaavan "fair value"n."""
    d = _vastaus(pm_client, monkeypatch, path, body, kutsuja)
    osumat = [(p, v) for p, v in _lehdet(d)
              if isinstance(v, str) and KERROINSANAT.search(v)]
    assert not osumat, f"{path} ({kutsuja}): kerroinsanasto: {osumat}"


@pytest.mark.parametrize("kutsuja", KUTSUJAT)
@pytest.mark.parametrize("path,body", ENDPOINTS)
def test_ennustevastauksessa_ei_lukua_yksi_per_p(pm_client, monkeypatch, path,
                                                 body, kutsuja):
    """Kerroin uudella nimella: yksikaan liukuluku ei ole 1 / p (2 desim.),
    kun p on vastauksen oma 1X2-todennakoisyys. Kokonaisluvut (maalit, pisteet)
    eivat ole kertoimia, joten ne jatetaan pois vaaran osuman estamiseksi."""
    d = _vastaus(pm_client, monkeypatch, path, body, kutsuja)
    kertoimet = {round(1.0 / max(d[k], 0.001), 2)
                 for k in ("p_home_win", "p_draw", "p_away_win")}
    assert all(c > 1.0 for c in kertoimet), "fikstuurin 1X2 puuttuu"
    osumat = [(p, v) for p, v in _lehdet(d)
              if isinstance(v, float) and not isinstance(v, bool)
              and v in kertoimet]
    assert not osumat, f"{path} ({kutsuja}): 1 / p vastauksessa: {osumat}"


# ---------------------------------------------------------------------------
# 3. SPA:n lahde: kerroinnaytto ei palaa
# ---------------------------------------------------------------------------

SPA = ROOT / "web" / "pro-spa"
SPA_LAHTEET = [SPA / "src", SPA / "scripts"]
SPA_PAATTEET = {".svelte", ".ts", ".js", ".mjs", ".css", ".html", ".json"}

#: Tiedosto (relatiivinen web/pro-spa:han, POSIX) -> perustelu. Tyhja
#: 1.11.2026. Rivi kertoo diffissa miksi sana saa olla lahteessa; ilman
#: perustelua tai ilman osumaa (vanhentunut) testi kaatuu.
SALLITUT_SPA: dict[str, str] = {}


def _spa_tiedostot() -> list[Path]:
    out = []
    for juuri in SPA_LAHTEET:
        out += [p for p in sorted(juuri.rglob("*"))
                if p.is_file() and p.suffix in SPA_PAATTEET]
    return out


def test_spa_lahteessa_ei_kerroinnayttoa():
    tiedostot = _spa_tiedostot()
    # Yksisuuntainen haku on vihrea tyhjalla: vaara polku ei saa lapaista.
    assert len(tiedostot) > 100, f"SPA-lahde puuttuu? {len(tiedostot)} tiedostoa"
    assert SPA / "src" / "lib" / "components" / "Predict.svelte" in tiedostot
    osumat = []
    for p in tiedostot:
        rel = p.relative_to(SPA).as_posix()
        if rel in SALLITUT_SPA:
            continue
        for n, rivi in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if KERROINSANAT.search(rivi):
                osumat.append(f"{rel}:{n}: {rivi.strip()[:120]}")
    assert not osumat, (
        "kerroinnaytto tai -sanasto SPA:n lahteessa (ulkoasu WP1, App Store "
        "4+). Poista se, tai lisaa tiedosto SALLITUT_SPA-listaan perustelun "
        "kanssa:\n  " + "\n  ".join(osumat))


def test_spa_poikkeuslista_on_perusteltu_ja_ajan_tasalla():
    for rel, perustelu in SALLITUT_SPA.items():
        assert perustelu.strip(), f"{rel}: poikkeus ilman perustelua"
        p = SPA / rel
        assert p.is_file(), f"{rel}: tiedostoa ei ole, poista rivi"
        assert KERROINSANAT.search(p.read_text(encoding="utf-8")), (
            f"{rel}: ei enaa osumaa, poista vanhentunut poikkeus")


def test_kerroinsanasto_tunnistaa_poistetun_nayton():
    """Kontrolli: mittari osuu siihen muotoon joka oli tuotannossa ennen
    1.11 (Predict.svelte), eika vain keksittyyn esimerkkiin."""
    poistettu = (
        "Model fair value: {data.fair_odds_home.toFixed(2)} / "
        "{data.fair_odds_draw?.toFixed(2)}. This is 1 divided by the model's "
        "probability, not a bookmaker line.")
    assert KERROINSANAT.search(poistettu)
    assert KERROINAVAIN.search("fair_odds_home")
    # Ja ei osu nykyiseen ennustesanastoon (vaara halytys tappaa portin).
    for ok in ("Win probability", "Most likely scorelines", "Over 2.5 goals",
               "Both teams score", "Model prediction, not betting advice.",
               "favourite", "p_home_win", "expected_goals_home"):
        assert not KERROINSANAT.search(ok), ok
        assert not KERROINAVAIN.search(ok), ok
