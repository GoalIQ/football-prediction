"""Vendoroitu varasnapshot football-data.co.uk -liigoille.

🔴 MITATTU KATKOS (8.9.2026). football-data.co.uk oli KOKONAAN alhaalla:

    https://www.football-data.co.uk/mmz4281/2627/E1.csv -> 503
    https://www.football-data.co.uk/englandm.php        -> 503   (sivun juuri)
    Server: nginx   Retry-After: 61

Neljan liigan koko Predict-pinta oli kuollut tuotannossa: Championship,
Eredivisie, Primeira Liga ja Brasileirao ovat ainoat jotka lataavat sielta.
`/api/teams` palautti niille 404:n ja `/api/predict` samoin.

MIKSI LEVYCACHE EI RIITA: `_hae_csv` cachettaa levylle, mutta Renderin levy on
EFEMEERI. Kylmakaynnistys + alhaalla oleva lahde = ei dataa, riippumatta siita
kuinka rehellisesti vastaamme. Ainoa asia joka selviaa kylmakaynnistyksesta on
repoon vendoroitu tiedosto — sama kuvio kuin `data/wc_model.json` (#79) ja
`data/international_results.csv`, jotka on jo vendoroitu tasta samasta syysta.

MITA VENDOROIDAAN: NORMALISOITU tulosdata (paivamaara, joukkueet, maalit,
kausi) — ei upstreamin CSV:aa sellaisenaan. Kertoimet ja muut lisasarakkeet
jaavat pois: malli ei kayta niita, ja snapshot pysyy pienena.

MITEN TAMA EI VOI HILJAA KORVATA TUORETTA DATAA: varasnapshotia luetaan VAIN
kun live-haku palautti tyhjan. Kun lahde on pystyssa, kayttaytyminen on
bittitarkasti entinen — `lataa()` ei edes kutsu tata. Snapshot on lisaksi
merkitty `lahde`-sarakkeeseen, joten sen kaytto nakyy datassa itsessaan.

PAIVITYS: `python scripts/build_fd_fallback.py` (aja kun lahde on pystyssa),
sitten commit. Snapshot vanhenee hitaasti ja hallitusti: vanhentunut snapshot
antaa vanhempia otteluita, ei vaaria otteluita.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import config

FALLBACK_DIR = Path(config.__file__).parent / "data" / "fd_fallback"

# Liigat joille varasnapshot yllapidetaan. Nama ovat ne joita API TARJOAA ja
# jotka lataavat football-data.co.uk:sta — eli ne jotka 8.9 olivat kuolleita.
# Muut football-data.co.uk -liigat eivat ole valitsimessa, joten niille
# snapshot olisi turhaa painolastia.
VENDORED_LEAGUES: tuple[str, ...] = (
    "ENG-Championship",
    "NED-Eredivisie",
    "POR-Primeira Liga",
    "BRA-Serie A",
    # 8.9 ILTA (Villen havainto "nyt ei pysty ollenkaan ennustamaan Aston
    # Villan pelia"): Mestarien liiga tarvitsee saman suojan, mutta ERI
    # SYYSTA. Sen lahde (football-data.org) ei ollut alhaalla — ongelma on
    # ETTA VANHEMPI KAUSI EI LATAUDU LUOTETTAVASTI. Ilmainen tier + Renderin
    # efemeeri levy tarkoittavat etta 24/25 onnistuu joskus ja joskus ei, ja
    # `football_data_org.lataa` heittaa silloin `OsittainenKausijoukko`n ->
    # koko liiga putoaa openfootballiin -> rosteri KUTISTUU 54:sta 36:een.
    #
    # Aston Villa PELASI UCL:n 24/25 (36 joukkuetta, 189 ottelua, QF asti),
    # joten sen voimataso on oikeaa dataa eika priori. Kun kausi on repossa,
    # ikkuna on deterministinen eika kolikonheitto.
    "INT-Champions League",
)

# Kaudet per vendoroitu liiga. UEFA-turnauksille kausi on eksplisiittinen,
# koska ne EIVAT seuraa domestic-ikkunaa.
VENDORED_SEASONS: dict[str, tuple[str, ...]] = {
    # 8.9 ilta, mitattu: kumulatiivinen kattavuus tamanviikon 18 ottelulle
    #   +2526 -> 36 joukkuetta,  6/18 ennustettavaa
    #   +2425 -> 54 joukkuetta, 10/18   (Aston Villa mukaan)
    #   +2324 -> 63 joukkuetta, 12/18   (FC Porto mukaan)
    #   +2223 -> 104 joukkuetta, 12/18  <- EI lisaa yhtaan ottelua
    # 2223 jatetaan siis pois: se toisi 41 joukkuetta joista yksikaan ei pelaa
    # tata kautta, eli pelkkaa painolastia malliin ja valitsimeen.
    "INT-Champions League": ("2324", "2425", "2526"),
}

# Sarakkeet jotka snapshot kantaa. Tama on `_normalisoi`n tuloksen osajoukko;
# lukija taydentaa puuttuvat NA:lla jotta skeema on sama kuin live-polulla.
SNAPSHOT_COLS: tuple[str, ...] = (
    "date", "home_team", "away_team", "home_score", "away_score",
    "season", "league",
)

# Sarakkeet jotka `_normalisoi` lisaa ja joita alavirta voi lukea. Ilman naita
# fallback-frame olisi eri muotoinen kuin live-frame, ja ero nakyisi vasta
# jossain kaukana (concat tayttaisi NaN:lla, tai KeyError).
DERIVED_NA_COLS: tuple[str, ...] = ("home_xg", "away_xg")

SOURCE_TAG = "football-data.co.uk (vendored fallback)"


def _slug(liiga: str) -> str:
    return liiga.replace(" ", "_").replace("-", "_")


def polku(liiga: str) -> Path:
    return FALLBACK_DIR / f"{_slug(liiga)}.csv"


def on_saatavilla(liiga: str) -> bool:
    return liiga in VENDORED_LEAGUES and polku(liiga).exists()


def lataa_varasnapshot(liiga: str, kaudet: list[str] | None = None) -> pd.DataFrame:
    """Vendoroitu data yhdelle liigalle, suodatettuna pyydetyille kausille.

    Palauttaa tyhjan framen jos snapshotia ei ole — kutsuja saa saman tyhjan
    tuloksen kuin ennen, eli tama ei voi muuttaa kayttaytymista huonompaan.
    """
    p = polku(liiga)
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p, encoding="utf-8")
    except Exception as e:  # pragma: no cover - rikkinainen snapshot
        print(f"fd_fallback ({liiga}): snapshot ei aukea: {type(e).__name__}: {e}")
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if kaudet:
        haetut = [str(k) for k in kaudet]
        # Sama joustava match kuin `lataa_new`ssa: kalenterivuosiliigojen
        # kausimerkkijono voi olla '2026' kun pyynto on '26'.
        mask = df["season"].astype(str).apply(
            lambda s: any(k in s or s in k for k in haetut)
        )
        df = df[mask]
    df = df.copy()
    for c in DERIVED_NA_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df["lahde"] = SOURCE_TAG
    return df.reset_index(drop=True)
