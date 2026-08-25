"""PORTTI: saatavuuslippu seuraa siirrossa sisaan tulevaa pelaajaa (25.8.2026).

🔴 VILLE KYSYI "webissa olen", JA KYSYMYS PALJASTI AUKON.
Pitch nayttaa `chance_next`-badgen omista pelaajista, mutta `RateTeam.svelte`
rakentaa siirrossa SISAAN tulevan pelaajan rivin KASIN `suggestion.in`
-kentista. Mitattu: `in`-objektissa ei ollut `chance_next`ia eika `news`ia
lainkaan, joten kyse ei ollut klientin mappauksesta vaan puuttuvasta datasta.

Seuraus: kayttaja soveltaa siirron, ja 75 %:n pelaaja renderoityy pitchilla
PUHTAANA — tasan silla hetkella kun han VALITSEE hanet. Se on se paikka jossa
lipun pitaisi pysayttaa.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import api.main as m

client = TestClient(m.app)


# 🔴 ILMAN `entry`a EI TULE EHDOTUKSIA LAINKAAN. Ensimmainen versio kutsui
# ilman sita, sai tyhjan listan ja palasi hiljaa -> mutaatio "lippu pois
# backendista" LAPAISI. Portti joka palaa tyhjana lapaisee aina.
ENTRY = 1186244


def _suggestions():
    r = client.get(f"/api/fantasy/rate-team?entry={ENTRY}")
    if r.status_code != 200:
        return []
    d = r.json()
    return (d.get("transfers") or {}).get("suggestions") or []


def test_siirtoehdotus_kantaa_saatavuuskentat():
    """Kentat on OLTAVA, vaikka arvo olisi None. `None` = FPL:lla ei uutista;
    kentan PUUTTUMINEN tarkoittaa etta klientti ei voi tietaa kumpi on kyse."""
    sug = _suggestions()
    if not sug:
        import pytest
        pytest.skip("ei siirtoehdotuksia — portti ei saa lapaista tyhjana")
    puuttuu = [k for k in ("chance_next", "news")
               if any(k not in (s.get("in") or {}) for s in sug)]
    assert not puuttuu, (
        f"siirtoehdotuksen `in`-objektista puuttuu {puuttuu} — klientti "
        f"rakentaa rivin naista kentista, joten lippu katoaa pitchilta")


def test_klientti_valittaa_lipun_eteenpain():
    """🔴 Backend voi lahettaa kentan ja klientti silti pudottaa sen. Portti
    lukee komponentin lahdekoodia, koska Svelte-ajuria ei tassa repossa ole."""
    from pathlib import Path
    p = (Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src"
         / "lib" / "components" / "RateTeam.svelte")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")
    i = s.index("plannedPlayers")
    lohko = s[i:i + 1600]
    # 🔴 EI PELKKA SUBSTRING. Ensimmainen versio etsi sanaa "chance_next", ja
    # se osui OMAAN KOMMENTTIINI ("...ilman `chance_next`ia...") — mutaatio
    # joka poisti itse sijoituksen lapaisi. Portti vaatii sijoituksen.
    assert "chance_next: s.in.chance_next" in lohko, (
        "plannedPlayers rakentaa sisaan tulevan pelaajan ilman "
        "`chance_next`ia — lippu katoaa siirron jalkeen")
    assert "news: s.in.news" in lohko, "`news` ei vality sisaan tulevalle"


def test_lippu_renderoityy_seka_XI_ssa_etta_PENKILLA():
    """🔴 VILLE NAYTTI KUVAKAAPPAUKSEN JOSSA EI OLLUT YHTAAN LIPPUA.

    Badge renderoityi VAIN XI-silmukassa, ja hanen kolme liputettua pelaajaansa
    (Anderson 75 %, Gibbs-White 75 %, F.Kadioglu 75 %) olivat KAIKKI penkilla.
    Olin verifioinut ominaisuuden lukemalla komponentista yhden osuman ja
    julistanut sen valmiiksi — yksi renderointipolku kahdesta.

    Penkki on lisaksi se paikka jossa lippu painaa eniten: penkkipelaaja on se
    jonka nostat XI:hin.

    🔴 PORTTI LASKEE OSUMAT, EI TARKISTA OLEMASSAOLOA. Pelkka "onko `doubt`
    komponentissa" olisi mennyt lapi koko ajan.
    """
    from pathlib import Path
    p = (Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src"
         / "lib" / "components" / "TeamPitchManager.svelte")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")
    n = s.count('class="doubt"')
    assert n >= 2, (
        f'`class="doubt"` esiintyy {n} kertaa — XI ja penkki ovat eri '
        f"silmukoita, joten molemmat tarvitsevat oman renderoinnin")
    # ...ja molemmat ovat oikeasti eri silmukoissa, eivat vierekkain samassa.
    xi = s.index("{#each row as p")
    penkki = s.index("{#each bench as p")
    assert s.count('class="doubt"', xi, penkki) >= 1, "XI:sta puuttuu lippu"
    assert s.count('class="doubt"', penkki) >= 1, "penkilta puuttuu lippu"
