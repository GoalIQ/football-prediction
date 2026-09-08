"""Portti: vendoroitu varasnapshot pelastaa katkoksessa eika korvaa tuoretta.

🔴 MITATTU KATKOS (8.9.2026). football-data.co.uk oli KOKONAAN alhaalla (503
myos sivun juuresta, `Retry-After: 61`), ja nelja liigaa oli kuollut
tuotannossa: Championship, Eredivisie, Primeira Liga, Brasileirao. Renderin
levy on efemeeri, joten `_hae_csv`:n levycache ei auta kylmakaynnistyksessa.

Mitattu korjauksen jalkeen, oikeassa katkoksessa ja tyhjalla levycachella:
    ENG-Championship   551 ottelua / 30 joukkuetta
    NED-Eredivisie     315 / 21
    POR-Primeira Liga  315 / 20
    BRA-Serie A        557 / 24

TAMAN TIEDOSTON TARKEIN TESTI EI OLE SE ETTA VARA TOIMII, vaan se ettei vara
KOSKAAN korvaa onnistunutta live-hakua. Hiljaa vanhentuvaan dataan
palautuminen on pahempi vika kuin se jota korjataan: se ei nay mistaan.
"""
from __future__ import annotations

import pandas as pd
import pytest

import config
from src.data import fd_fallback
from src.data import footballdata as fd


# ---------------------------------------------------------------------------
# Snapshotin oma kunto. Rikkinainen snapshot olisi vaarallisempi kuin puuttuva.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("liiga", fd_fallback.VENDORED_LEAGUES)
def test_snapshot_on_olemassa_ja_jarkeva(liiga):
    assert fd_fallback.on_saatavilla(liiga), (
        f"{liiga}: varasnapshot puuttuu. Aja scripts/build_fd_fallback.py ja "
        "commitoi — ilman sita liiga kuolee seuraavassa katkoksessa."
    )
    df = fd_fallback.lataa_varasnapshot(liiga)
    assert len(df) >= 250, f"{liiga}: snapshot on epauskottavan pieni ({len(df)})"
    for c in fd_fallback.SNAPSHOT_COLS:
        assert c in df.columns, f"{liiga}: sarake {c} puuttuu"
    # Vain pelatut ottelut: tulokseton rivi tekisi snapshotista aikataulun.
    assert df["home_score"].notna().all()
    assert df["away_score"].notna().all()
    assert df["date"].notna().all()
    joukkueet = set(df["home_team"]) | set(df["away_team"])
    assert len(joukkueet) >= 18, f"{liiga}: vain {len(joukkueet)} joukkuetta"


def test_snapshot_kantaa_lahdeleiman():
    """Varan kaytto pitaa nakya DATASSA eika vain lokissa — muuten kukaan ei
    myohemmin tieda mista luvut tulivat."""
    df = fd_fallback.lataa_varasnapshot("ENG-Championship")
    assert (df["lahde"] == fd_fallback.SOURCE_TAG).all()


def test_skeema_vastaa_live_polkua():
    """Eri muotoinen frame nakyisi vasta kaukana alavirrassa (concat tayttaisi
    NaN:lla tai KeyError). Varmistetaan etta johdetut sarakkeet ovat mukana."""
    df = fd_fallback.lataa_varasnapshot("ENG-Championship")
    for c in fd_fallback.DERIVED_NA_COLS + ("lahde",):
        assert c in df.columns, f"johdettu sarake {c} puuttuu varasnapshotista"


# ---------------------------------------------------------------------------
# Katkos: vara pelastaa.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("liiga", ["ENG-Championship", "NED-Eredivisie", "POR-Primeira Liga"])
def test_katkoksessa_vara_pelastaa(monkeypatch, liiga):
    monkeypatch.setattr(fd, "lataa_mainstream", lambda *a, **k: pd.DataFrame())
    df = fd.lataa(liiga, config.current_season_pair())
    assert not df.empty, f"{liiga}: katkos jatti mallin tyhjaksi vaikka snapshot on"
    assert (df["lahde"] == fd_fallback.SOURCE_TAG).all()


def test_katkoksessa_vara_pelastaa_kalenterivuosiliigan(monkeypatch):
    monkeypatch.setattr(fd, "lataa_new", lambda *a, **k: pd.DataFrame())
    df = fd.lataa("BRA-Serie A", ["2025", "2026"])
    assert not df.empty


# ---------------------------------------------------------------------------
# 🔴 NEGATIIVISET KONTROLLIT. Nama ovat taman tiedoston tarkein osa.
# ---------------------------------------------------------------------------


def test_onnistunut_live_ei_korvaudu_varalla(monkeypatch):
    """Jos vara ajaisi live-datan yli, siirtyisimme hiljaa vanhentuvaan
    dataan — vika joka ei nay mistaan."""
    live = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-09-01"]),
            "home_team": ["LIVE-KOTI"],
            "away_team": ["LIVE-VIERAS"],
            "home_score": [1],
            "away_score": [0],
            "season": ["2627"],
            "league": ["ENG-Championship"],
            "lahde": ["football-data.co.uk"],
        }
    )
    monkeypatch.setattr(fd, "lataa_mainstream", lambda *a, **k: live)
    df = fd.lataa("ENG-Championship", ["2526", "2627"])
    assert set(df["home_team"]) == {"LIVE-KOTI"}
    assert fd_fallback.SOURCE_TAG not in set(df["lahde"])


def test_vain_puuttuva_kausi_taydennetaan(monkeypatch):
    """Osittainen katkos: yksi kausi tulee livena, toinen ei. Onnistunut kausi
    EI saa korvautua, ja puuttuva saa taydentya."""
    live = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-09-01"]),
            "home_team": ["LIVE-KOTI"],
            "away_team": ["LIVE-VIERAS"],
            "home_score": [1],
            "away_score": [0],
            "season": ["2627"],
            "league": ["ENG-Championship"],
            "lahde": ["football-data.co.uk"],
        }
    )

    def vaihteleva(liiga, kausi, force=False):
        return live if kausi == "2627" else pd.DataFrame()

    monkeypatch.setattr(fd, "lataa_mainstream", vaihteleva)
    df = fd.lataa("ENG-Championship", ["2526", "2627"])
    lahteet = set(df["lahde"])
    assert "football-data.co.uk" in lahteet, "live-kausi katosi"
    assert fd_fallback.SOURCE_TAG in lahteet, "puuttuvaa kautta ei taydennetty"
    # Live-kausi 2627 saa tulla VAIN livesta.
    v2627 = df[df["season"].astype(str) == "2627"]
    assert set(v2627["lahde"]) == {"football-data.co.uk"}


def test_liiga_ilman_snapshotia_kayttaytyy_ennallaan(monkeypatch):
    """Vendoroimaton liiga ei saa alkaa lukea vieraan liigan snapshotia."""
    monkeypatch.setattr(fd, "lataa_mainstream", lambda *a, **k: pd.DataFrame())
    df = fd.lataa("SCO-Premiership", ["2526", "2627"])
    assert df.empty


def test_puuttuva_snapshottiedosto_ei_kaada(monkeypatch):
    monkeypatch.setattr(fd_fallback, "polku", lambda liiga: fd_fallback.FALLBACK_DIR / "EI_OLE.csv")
    assert fd_fallback.lataa_varasnapshot("ENG-Championship").empty


# ---------------------------------------------------------------------------
# UEFA: vara ENNEN osittaisuusvahtia. Tama on se korjaus joka teki Aston
# Villan ennustettavaksi.
# ---------------------------------------------------------------------------


def test_cl_vara_estaa_osittaisuusvahdin_ja_lahteenvaihdon(monkeypatch):
    """🔴 8.9 ilta, Villen havainto "nyt ei pysty ollenkaan ennustamaan Aston
    Villan pelia".

    Ilmainen tier + Renderin efemeeri levy tekivat VANHEMMAN kauden hausta
    kolikonheiton. Epaonnistuminen laukaisi `OsittainenKausijoukko`n, loader
    pudotti KOKO liigan openfootballiin ja CL:n rosteri kutistui 54:sta
    36:een - Aston Villa katosi. Ikkunan levennys siis huononsi tuotetta, ja
    se jouduttiin perumaan kerran.

    Repoon vendoroitu kausi tekee ikkunasta deterministisen: kausi joka on
    snapshotissa ei ole epaonnistunut, joten vahti ei laukea eika lahde vaihdu.

    🔴 9.9: TAMA TESTI OLI VIHREA VAIN VILLEN KONEELLA JA PUNAINEN CI:SSA 9
    perakkaista ajoa. Kaksi ymparistoriippuvuutta, molemmat nyt kiinnitetty:

    (1) `lataa()` palauttaa TYHJAN framen heti jos API-avainta ei ole
        (`football_data_org.py`, `if not api_key: return pd.DataFrame()`) -
        kolme rivia ENNEN varasnapshot-haaraa. Lokaalisti avain tulee
        gitignoratusta `.env`:sta, CI:ssa sita ei ole, joten testi ei paassyt
        edes kausisilmukkaan.
    (2) Kaudet 2526/2627 tulivat lokaalisti gitignoratusta levycachesta
        (`data/raw/football-data-org/CL_2025.json`). CI:ssa cachea ei ole,
        joten pelkka avaimen kiinnitys olisi vienyt testin oikeaan API:in:
        hidas, 6,5 s rate-limit-sleep, ja `len(teams)` heiluisi kierroksittain.

    Molemmat stubataan nyt testin sisalla, joten testi mittaa MEKANISMIA -
    ajaako vara ennen osittaisuusvahtia - eika sita onko ajokoneella avain.
    Mutaatiokontrolli: kun `on_saatavilla` pakotetaan False:ksi, tama testi
    nostaa yha `OsittainenKausijoukko`n.
    """
    from src.data import football_data_org as fdo

    # (1) Avain: mika tahansa ei-tyhja arvo riittaa, koska (2) korvaa haun.
    monkeypatch.setattr(fdo, "_api_key", lambda: "TESTIAVAIN")

    # (2) Haku: EI verkkoa, ei levycachea. Vendoroidut kaudet (2425 ja 2526)
    # "epaonnistuvat" niin kuin ilmaisella tierilla oikeastikin -> vain
    # varasnapshot voi pelastaa ne, ja juuri sita tama testi mittaa.
    # Kuluva kausi 2627 EI ole snapshotissa ja onnistuu inline-fikstuurilla:
    # ilman yhtaan onnistunutta kautta osittaisuusvahti ei voisi laueta, eli
    # testi lapaisisi ilman etta mekanismia on koeteltu.
    def _stub_hae_kausi(code, year, key):
        if str(year) < "2026":
            return {"_error": "simuloitu: ilmainen tier ei kata"}
        return {
            "matches": [
                {
                    "utcDate": "2026-09-16T19:00:00Z",
                    "status": "FINISHED",
                    "homeTeam": {"name": "STUB-KOTI"},
                    "awayTeam": {"name": "STUB-VIERAS"},
                    "score": {"fullTime": {"home": 1, "away": 0}},
                }
            ]
        }

    monkeypatch.setattr(fdo, "_hae_kausi", _stub_hae_kausi)

    # 🔴 Kaudet EKSPLISIITTISESTI eika `config.uefa_season_window()`:sta.
    # Tama testi mittaa MEKANISMIA (vara ajaa ennen osittaisuusvahtia), ei
    # sita mika ikkuna on kulloinkin kaytossa. Ensimmainen versio luki
    # ikkunan configista ja hajosi heti kun ikkuna kavennettiin - se olisi
    # ollut vihrea vaarasta syysta ja punainen vaarasta syysta.
    kaudet = ["2425", "2526", "2627"]
    df = fdo.lataa("INT-Champions League", kaudet)
    assert not df.empty
    teams = set(df["home_team"]) | set(df["away_team"])
    assert "Aston Villa FC" in teams, (
        "Aston Villa puuttuu vaikka se PELASI UCL:n 24/25 ja kausi on "
        "vendoroitu. Varasnapshot ei ilmeisesti aja ennen osittaisuusvahtia."
    )
    assert "Club Brugge KV" in teams
    assert len(teams) >= 50, f"rosteri kutistui {len(teams)}:een - lahde vaihtui?"


def test_cl_vara_ei_aja_kun_lahde_vastaa(monkeypatch):
    """NEGATIIVINEN KONTROLLI: vara ei saa korvata onnistunutta hakua.

    🔴 9.9: TAMA KONTROLLI LAPAISI CI:SSA TYHJANA. Se ei kiinnittanyt
    API-avainta, joten CI:ssa `lataa()` palasi ensimmaiselta riviltaan eika
    kausisilmukkaan menty koskaan - `kutsuttu` oli tyhja siksi ETTEI MITAAN
    AJETTU, ei siksi etta vara pysyi poissa. Tiedoston oma docstring sanoo
    taman olevan sen tarkein testi (muisti: kontrolli-lapaisi-tyhjana).

    Nyt haku stubataan onnistuvaksi, joten kontrolli mittaa oikeasti: lahde
    vastasi, siis varaan ei saa koskea. Lisaksi vaaditaan etta haku TAPAHTUI -
    ilman sita sama tyhja lapaisy palaisi ensimmaisesta ymparistomuutoksesta.
    """
    from src.data import fd_fallback
    from src.data import football_data_org as fdo

    haettu = []

    def _stub_hae_kausi(code, year, key):
        haettu.append((code, year))
        return {
            "matches": [
                {
                    "utcDate": "2026-09-16T19:00:00Z",
                    "status": "FINISHED",
                    "homeTeam": {"name": "LIVE-KOTI"},
                    "awayTeam": {"name": "LIVE-VIERAS"},
                    "score": {"fullTime": {"home": 2, "away": 1}},
                }
            ]
        }

    monkeypatch.setattr(fdo, "_api_key", lambda: "TESTIAVAIN")
    monkeypatch.setattr(fdo, "_hae_kausi", _stub_hae_kausi)

    kutsuttu = []
    monkeypatch.setattr(
        fd_fallback, "lataa_varasnapshot",
        lambda liiga, kaudet=None: kutsuttu.append(liiga) or __import__("pandas").DataFrame(),
    )
    df = fdo.lataa("INT-Champions League", ["2526"])
    assert haettu, "hakua ei ajettu - kontrolli olisi lapaissyt tyhjana"
    assert not kutsuttu, "varasnapshot luettiin vaikka lahde vastasi"
    assert set(df["home_team"]) == {"LIVE-KOTI"}, "tulos ei tullut live-polulta"


def test_snapshot_ei_saa_rakentua_itsestaan():
    """🔴 Mitattu 8.9 illalla: rakennusskripti kutsuu `lataa`a, ja kun vara oli
    paalla, Championshipin snapshot kutistui 1103 -> 551 otteluun YHDELLA
    ajolla. Kausi jota ei ollut snapshotissa ei olisi enaa koskaan palannut.
    Rakennuspolku lukee siksi vain primaarilahdetta."""
    import pathlib

    src = pathlib.Path("scripts/build_fd_fallback.py").read_text(encoding="utf-8")
    assert "salli_vara=False" in src
    assert src.count("salli_vara=False") >= 2, (
        "molempien haarojen (co.uk ja football-data.org) on ohitettava vara"
    )
