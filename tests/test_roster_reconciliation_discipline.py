"""Portti: yksikaan tarjottu liiga ei saa jaada ilman rosterin sovitusta.

🔴 MITATTU VIKA (8.9.2026, Villen kaverin bugiraportti). Kaveri napautti
Mestarien liigan avauskierroksen ottelua Club Brugge vs Aston Villa ja sai
ruudulle jonkin muun ottelun. Mitattu tuotannosta samana paivana:

    /api/fixtures?league=INT-Champions League&days=7  -> 26/27 kentta
    /api/teams?leagues=INT-Champions League&...       -> 25/26 kentta (36 kpl)
    POST /api/predict {Club Brugge KV, Aston Villa FC}
                        -> 404 "Away team 'Aston Villa FC' not found in model."

18 joukkuetta 36:sta puuttui, eli **12 ottelua 18:sta** ei ollut
ennustettavissa.

JUURISYY EI OLLUT KOODI VAAN LISTA. `src/models/promoted_baseline.py` on
rakennettu tasan tata varten: se injektoi fitin JALKEEN joukkueet joilla ei
viela ole rivia, koskematta olemassa oleviin estimaatteihin. Mekanismi sai
26/27-merkinnat Valioliigalle 27.7, neljalle FD-liigalle 1.8 ja
Championshipille 15.8. **Mestarien liiga — sarja jossa kentasta vaihtuu
puolet joka vuosi — ei saanut kumpaakaan merkintaa.**

`RELEGATED_BY_SEASON`:n oma kommentti sanoo sen suoraan: "puuttuva liiga = ei
suodatusta = entinen kaytos". Se on fail-open, ja fail-open ilman porttia
tarkoittaa etta unohdus ei nay missaan.

MITA TAMA PORTTI TEKEE (CLAUDE.md saanto 6a, mekanismi 2): uusi liiga ei
paase tarjolle vahingossa. Jos `WARMUP_LEAGUES`iin lisataan liiga jolla ei ole
rosterin sovitusta, testi kaatuu ja kirjoittaja joutuu kirjoittamaan MIKSI.
Unohduksesta syntyva vika muuttuu mahdottomaksi; tietoinen valinta jaa
nakyviin diffiin.

MEKANISMI 3 (invariantti mitataan joka vaiheessa): ehto luetaan AKTIIVISESTA
kaudesta eika kovakoodatusta '2627':sta. Kun kausi-ikkuna flippaa, kummassakin
taulukossa ei ole viela uuden kauden avainta -> tama portti punastuu heti
flipissa eika vasta kun kayttaja huomaa puuttuvan joukkueen.
"""
from __future__ import annotations

import pytest

from src.models.promoted_baseline import (
    PROMOTED_BY_SEASON,
    RELEGATED_BY_SEASON,
)


def _tarjotut_liigat_ja_aktiivinen_kausi() -> tuple[list[str], str]:
    """Liigat jotka API tosiasiassa tarjoaa, ja niiden aktiivinen kausi.

    Lahde on `WARMUP_LEAGUES` eika kasin kirjoitettu lista tassa tiedostossa:
    kopio vanhenisi tasan silla tavalla jota tama portti yrittaa estaa.
    """
    import api.main as main

    liigat: list[str] = []
    kausi = ""
    for koodit, kaudet in main.WARMUP_LEAGUES:
        for k in koodit:
            if k not in liigat:
                liigat.append(k)
        if kaudet:
            kausi = str(kaudet[-1])
    return liigat, kausi


# ---------------------------------------------------------------------------
# POIKKEUSLISTA. Jokainen rivi vaatii perustelun. Ala lisaa rivia ilman etta
# kirjoitat mita puuttuu ja kuka paattaa — perustelu on koko listan tarkoitus.
# ---------------------------------------------------------------------------
POIKKEUKSET: dict[str, str] = {
    "INT-Champions League": (
        "8.9.2026, PAIVITETTY SAMANA PAIVANA. Alkuperainen puute: 26/27:n "
        "sarjavaiheeseen tuli 18 uutta seuraa 36:sta eika yhdellakaan ollut "
        "riveja mallissa MD1:n aamuna -> 12 ottelua 18:sta ei ollut "
        "ennustettavissa. "
        "TEHTY: treeni-ikkuna levennettiin domestic-parista NELJAAN kauteen "
        "(config.uefa_season_window). Mitattu tuotannosta kahdesti: 36 -> 63 "
        "joukkuetta, puuttuvat 18 -> 8, ennustettavat ottelut 6/18 -> 12/18. "
        "Aston Villa - se joukkue josta bugiraportti tuli - on nyt mallissa. "
        "JAAKO JALJELLE: 8 seuraa joilla ei ole riveja missaan CL-kaudessa "
        "(AS Roma, Como, Fenerbahce, LASK, PAE AEK, Real Betis, Sabah, "
        "Viking). Niille EI injektoida baselinea, ja se on tietoinen valinta: "
        "yksi 'CL-tulokas'-kohortti niputtaisi Roman ja Sabahin samaan "
        "voimatasoon, ja vaara ennuste on pahempi kuin puuttuva nappi (sama "
        "linjaus kuin resolveByDateLeague). Oikea korjaus on ristiliigapriori "
        "kotiliigan ratingista kalibroituna paallekkaisten joukkueiden yli - "
        "se vaatii backtestin ennen kuin siita julkaistaan lukuja, ja on "
        "jonossa rivilla UCL-ROSTERI-PRIORI. "
        "Kayttajalle nakyva vahinko on padottu: goaliq-app "
        "lib/fixturePredictability.ts ei renderoi Predict-CTA:ta ottelulle "
        "jota malli ei osaa vastata. "
        "HERATYSEHTO ON LUKU EIKA PAIVA: poista tama rivi kun "
        "/api/teams?leagues=INT-Champions League sisaltaa 'AS Roma'."
    ),
    "BRA-Serie A": (
        "Kalenterivuosikausi (helmi-joulukuu), joten sen nousija-/putoaja-"
        "ikkuna ei osu eurooppalaiseen elo-touko-flippiin lainkaan: "
        "26/27-avaimen alle kirjattu lista olisi vaarassa kohdassa vuotta. "
        "Sarja on lisaksi kesken kautta koko eurooppalaisen kausivaihdon ajan, "
        "eli rosteri ei ole missaan vaiheessa tyhja samalla tavalla kuin "
        "Euroopassa. Vaatii oman kausiavaimensa ennen kuin sen voi listata; "
        "siihen asti kayttaytyminen on entinen (ei suodatusta)."
    ),
}


def test_jokaisella_tarjotulla_liigalla_on_rosterin_sovitus():
    liigat, kausi = _tarjotut_liigat_ja_aktiivinen_kausi()
    assert liigat, "WARMUP_LEAGUES on tyhja — portti mittaisi tyhjaa joukkoa"
    assert kausi, "aktiivista kautta ei saatu WARMUP_LEAGUESista"

    nousijat = PROMOTED_BY_SEASON.get(kausi, {})
    putoajat = RELEGATED_BY_SEASON.get(kausi, {})

    puuttuvat = [
        liiga
        for liiga in liigat
        if liiga not in nousijat
        and liiga not in putoajat
        and liiga not in POIKKEUKSET
    ]
    assert not puuttuvat, (
        f"Liigat ilman rosterin sovitusta kaudelle {kausi}: {puuttuvat}.\n"
        "Lisaa ne PROMOTED_BY_SEASON/RELEGATED_BY_SEASON-tauluihin TAI "
        "kirjoita perusteltu rivi taman tiedoston POIKKEUKSET-dictiin.\n"
        "Ilman sovitusta joukkuevalitsin tarjoaa viime kauden kentan ja "
        "Predict palauttaa 404:n — tasan 8.9.2026 mitattu vika."
    )


def test_poikkeus_vaatii_aidon_perustelun():
    """Tyhja tai olankohautus-perustelu tekisi listasta pelkan hiljentimen."""
    for liiga, perustelu in POIKKEUKSET.items():
        assert len(perustelu) >= 120, (
            f"{liiga}: perustelu on liian lyhyt ollakseen perustelu. "
            "Kirjoita mika puuttuu, miksi korjaus ei ole viela tehty ja "
            "mika ehto sulkee rivin."
        )


def test_poikkeuslista_ei_saa_sisaltaa_liigaa_jota_ei_tarjota():
    """Kuollut poikkeusrivi vaimentaisi portin liigalle joka palaa tarjolle
    myohemmin — ja kukaan ei huomaisi, koska rivi on jo olemassa."""
    liigat, _ = _tarjotut_liigat_ja_aktiivinen_kausi()
    ylimaaraiset = [k for k in POIKKEUKSET if k not in liigat]
    assert not ylimaaraiset, (
        f"POIKKEUKSET sisaltaa liigoja joita ei tarjota: {ylimaaraiset}. "
        "Poista rivi — muuten se vaimentaa portin jos liiga palaa listalle."
    )


@pytest.mark.parametrize("tuleva_kausi", ["2728", "2829"])
def test_portti_punastuu_kausiflipissa(tuleva_kausi):
    """VAIHEINVARIANTTI. Tama ei mittaa nykyhetkea vaan sita mita tapahtuu
    kun kausi vaihtuu alta. Kummassakaan taulukossa ei ole tulevan kauden
    avainta, joten sovitus on silloin tyhja KAIKILLE liigoille — ja portin
    kuuluu huomata se. Jos joku myohemmin tekee tauluista fallbackin
    edelliseen kauteen, tama kaatuu ja pakottaa katsomaan miksi."""
    assert tuleva_kausi not in PROMOTED_BY_SEASON
    assert tuleva_kausi not in RELEGATED_BY_SEASON

    liigat, _ = _tarjotut_liigat_ja_aktiivinen_kausi()
    nousijat = PROMOTED_BY_SEASON.get(tuleva_kausi, {})
    putoajat = RELEGATED_BY_SEASON.get(tuleva_kausi, {})
    puuttuvat = [
        liiga
        for liiga in liigat
        if liiga not in nousijat
        and liiga not in putoajat
        and liiga not in POIKKEUKSET
    ]
    assert puuttuvat, (
        f"Kaudella {tuleva_kausi} EI pitaisi olla yhtaan sovitusta, mutta "
        "portti ei havainnut yhtaan puutetta. Joko WARMUP_LEAGUES on tyhja "
        "tai joku on lisannyt hiljaisen fallbackin edelliseen kauteen."
    )
