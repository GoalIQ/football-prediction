"""Portti: UEFA-turnausten treeni-ikkuna, ja miksi juuri nelja kautta.

🔴 MITATTU VIKA (8.9.2026). Mestarien liiga kaytti `current_season_pair()`ia
eli domestic-oletusta kilpailussa jossa KENTASTA VAIHTUU PUOLET JOKA VUOSI.
26/27:n sarjavaiheeseen tuli 18 uutta seuraa 36:sta, eika yhdellakaan ollut
riveja mallissa MD1:n aamuna.

Mitattu tuotannosta, KAKSI ajoa per ikkuna (luvut toistuivat):

    2526+2627            36 joukkuetta   18 puuttuu    6/18 ottelua
    2425+2526+2627       54 joukkuetta   11 puuttuu   10/18
    2324+2425+2526+2627  63 joukkuetta    8 puuttuu   12/18   <- valittu
    2223+...+2627        36 joukkuetta   36 puuttuu    0/18   <- RIKKI

VIIDES KAUSI EI HEIKENNA VAAN ROMAHDUTTAA: 2223 myrkyttaa fitin niin ettei
yksikaan palautettu joukkue ole taman kauden osallistuja. Ylaraja on siis
MITATTU eika makuasia, ja siksi tassa on molemmat rajat.

Ensimmainen mittaus antoi leveimmalle ikkunalle 104 joukkuetta, mutta se EI
TOISTUNUT — sama kutsu palautti hetkea myohemmin 36. Sen varaan oli tarkoitus
rakentaa koko korjaus. Siksi jokainen luku yllä on ajettu kahdesti.
"""
from __future__ import annotations

import datetime

import pytest

import config


def test_ikkuna_on_nelja_kautta_datan_vendoroinnin_jalkeen():
    """🔴 Kaksi peruutusta ja yksi oikea korjaus, kaikki 8.9.2026.

    Levensin ikkunan neljaan ja kolmeen kauteen; molemmat romahtivat deployn
    jalkeen (36 joukkuetta, 0/18 ottelua) ja peruin ne. Villen havainto
    perumisen jalkeen: "nyt ei pysty ollenkaan ennustamaan Aston Villan
    pelia" - oikein, nappi piilossa ei ole ennuste.

    Juurisyy ei ollut ikkunan leveys vaan DATAN SAATAVUUS: vanhemman kauden
    haku oli kolikonheitto ja epaonnistuminen pudotti koko liigan
    varalahteelle. Kun kausi on vendoroitu repoon, ikkuna on deterministinen.
    """
    assert config.UEFA_WINDOW_SEASONS == 4


def test_levennys_ei_saa_palata_ilman_mekanismikorjausta():
    """🔴 TAMAN TIEDOSTON TARKEIN TESTI.

    Levensin ikkunan kahdesti ja perruin sen kahdesti samana paivana. Molemmat
    levennykset nayttivat mittaushetkella paremmilta ja molemmat romahtivat
    deployn jalkeen:

        ikkuna              mittaus A     deployn jalkeen
        2526+2627           36 /  6-18    36 / 6-18   <- vakaa
        2425+2526+2627      54 / 10-18    36 / 0-18   <- ROMAHTI
        2324+2425+2526+2627 63 / 12-18    36 / 0-18   <- ROMAHTI

    Romahdustilassa puuttui myos Club Brugge, joka on KAPEALLA ikkunalla
    mukana: levennys teki tuotteesta mitattavasti huonomman.

    Ehto levennykselle EI ole "mittaa uudelleen" - se on jo tehty kahdesti ja
    petti kahdesti. Ehto on ETTA PUUTTUVA KAUSI EI PUDOTA KOKO LIIGAA
    varalahteelle (OsittainenKausijoukko -> openfootball). Kun se on korjattu,
    tama testi paivitetaan samassa committissa kuin mekanismi.
    """
    # Ehto ei ole luku vaan MEKANISMI: jokaisen ikkunan kauden (paitsi
    # aktiivisen, jossa ei viela ole pelattuja otteluita) on oltava joko
    # luotettavasti haettavissa TAI vendoroitu. Muuten yksi saamaton kausi
    # pudottaa koko liigan varalahteelle ja rosteri kutistuu.
    from src.data.fd_fallback import VENDORED_SEASONS

    ikkuna = config.uefa_season_window(datetime.date(2026, 9, 8))
    vendoroidut = set(VENDORED_SEASONS.get("INT-Champions League", ()))
    aktiivinen = ikkuna[-1]
    for kausi in ikkuna[:-1]:
        assert kausi in vendoroidut, (
            f"Ikkunassa on kausi {kausi} jota ei ole vendoroitu. Jos sen haku "
            "epaonnistuu, OsittainenKausijoukko pudottaa KOKO liigan "
            "openfootballiin ja rosteri kutistuu 54 -> 36 (Aston Villa katoaa). "
            "Vendoroi kausi tai kavenna ikkunaa."
        )
    assert aktiivinen not in vendoroidut, (
        "Aktiivista kautta ei pida vendoroida: se elaa, ja snapshot jaadyttaisi sen."
    )
    # 🔴 Ehto EI ole enaa "ala ota kautta jota tier ei kata". Se oli oikea ehto
    # ennen vendorointia; nyt oikea ehto on "ota vain kausia jotka ovat
    # repossa". `FDORG_FREE_TIER_MEASURED` jaa mittauksen kirjaukseksi: se
    # kertoo MIKSI vendorointi tarvitaan, ei mita ikkunaan saa ottaa.
    m2 = config.FDORG_FREE_TIER_MEASURED
    assert m2["ensimmainen_puuttuva"] in vendoroidut, (
        "Kausi joka mitattiin puuttuvaksi upstreamista on ikkunassa muttei "
        "vendoroituna - se romahduttaa rosterin ensimmaisella kylmalla ajolla."
    )
    m = config.FDORG_FREE_TIER_MEASURED
    # (Vendoroinnin jalkeen tama kausi SAA olla ikkunassa; ks. ylla.)


@pytest.mark.parametrize(
    "paiva,odotettu",
    [
        (datetime.date(2026, 9, 8), ["2324", "2425", "2526", "2627"]),
        (datetime.date(2026, 3, 8), ["2223", "2324", "2425", "2526"]),
        (datetime.date(2027, 9, 8), ["2425", "2526", "2627", "2728"]),
        # Kausiraja: 31.7. kuuluu viela edelliseen kauteen, 1.8. uuteen.
        (datetime.date(2026, 7, 31), ["2223", "2324", "2425", "2526"]),
        (datetime.date(2026, 8, 1), ["2324", "2425", "2526", "2627"]),
    ],
)
def test_vaiheinvariantti_ikkuna_seuraa_kautta(paiva, odotettu):
    """Ikkuna lasketaan aktiivisesta kaudesta, joten se on mitattava MUUSSAKIN
    kuin nykyhetkessa. Testi joka ajetaan vain tassa kauden vaiheessa on
    vihrea siihen asti kun se lakkaa olemasta tosi."""
    assert config.uefa_season_window(paiva) == odotettu


def test_ikkuna_on_yhtenainen_ja_paattyy_aktiiviseen():
    for vuosi in range(2024, 2031):
        p = datetime.date(vuosi, 9, 8)
        w = config.uefa_season_window(p)
        assert w[-1] == config.current_season(p)
        assert len(w) == config.UEFA_WINDOW_SEASONS
        for a, b in zip(w, w[1:]):
            assert a[2:] == b[:2], f"aukko ikkunassa {vuosi}: {a} -> {b}"


def test_warmup_lammittaa_saman_ikkunan_jota_klientti_pyytaa():
    """Jos warmup lammittaa eri ikkunan kuin klientti pyytaa, ensimmainen
    kayttaja maksaa koko fitin odotusaikana — ja mittaamme vaaraa mallia."""
    import api.main as main

    cl = [s for liigat, s in main.WARMUP_LEAGUES if liigat == ("INT-Champions League",)]
    assert cl, "CL puuttuu warmupista"
    assert list(cl[0]) == config.uefa_season_window()


def test_vain_uefa_sai_levean_ikkunan():
    """NEGATIIVINEN KONTROLLI: levennys ei saa vuotaa domestic-liigoihin —
    se muuttaisi kerralla kaikkien niiden julkaistut luvut."""
    import api.main as main

    pari = tuple(config.current_season_pair())
    for liigat, kaudet in main.WARMUP_LEAGUES:
        if any(l.startswith("INT-") for l in liigat):
            continue
        assert tuple(kaudet) == pari, f"{liigat} sai muun kuin domestic-parin: {kaudet}"


# ---------------------------------------------------------------------------
# Palvelinpuolen normalisointi. TAMA on se osa joka korjaa myos ne pinnat
# joita emme voi paivittaa: jo asennetut mobiilibuildit ja pro-SPA.
# ---------------------------------------------------------------------------


def test_uefa_oletusikkuna_normalisoituu_palvelimella():
    """Villen kaverin buildi oli yli 2 kk vanha eika sen runtimeVersion saa
    OTA:aakaan. Klienttikorjaus ei siis tavoita hanta — palvelin tavoittaa."""
    import api.main as main

    pyydetty = tuple(config.current_season_pair())
    saatu = main.normalisoi_kaudet(("INT-Champions League",), pyydetty)
    assert list(saatu) == config.uefa_season_window()


def test_eksplisiittista_kausivalintaa_EI_ylikirjoiteta():
    """🔴 NEGATIIVINEN KONTROLLI, ja tama on tarkeampi kuin laajennus itse.
    Jos mika tahansa kausipyynto laajenisi, backtest joka pinnaa kauden saisi
    hiljaa eri datan kuin pyysi — pahempi vika kuin korjattava."""
    import api.main as main

    for pyydetty in (("2526",), ("2425", "2526"), ("2223", "2324")):
        assert main.normalisoi_kaudet(("INT-Champions League",), pyydetty) == pyydetty


def test_domestic_liiga_ei_laajene_koskaan():
    import api.main as main

    pari = tuple(config.current_season_pair())
    for liiga in ("ENG-Premier League", "ENG-Championship", "BRA-Serie A"):
        assert main.normalisoi_kaudet((liiga,), pari) == pari


def test_maailmancup_ei_hairiinny():
    """WC:lla on omat legacy-avaimensa ('18','22','26') ja esirakennettu malli.
    Ne eivat ole domestic-pari, joten normalisointi ei koske niihin — mutta
    varmistetaan se, koska WC alkaa myos 'INT-'-etuliitteella."""
    import api.main as main

    wc = ("18", "22", "26")
    assert main.normalisoi_kaudet(("INT-World Cup",), wc) == wc


def test_teams_vastaus_kertoo_ikkunan_jota_kaytettiin():
    """Vastauksen `seasons` ei saa vaittaa kahta kautta kun lista tulee
    neljasta. Luetaan lahteesta: endpointin ajaminen vaatisi fitin."""
    import inspect

    import api.main as main

    src = inspect.getsource(main.teams) if hasattr(main, "teams") else ""
    if not src:
        import pathlib

        src = pathlib.Path(main.__file__).read_text(encoding="utf-8")
    assert "seasons = list(normalisoi_kaudet(" in src
