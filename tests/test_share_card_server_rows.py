# -*- coding: utf-8 -*-
"""JAKOKORTTI: rivit tulevat PALVELIMELTA, ei elavasta DOMista.

TAUSTA (24.8). Ensimmainen toteutus luki kortin rivit `table.lb`:n tbodysta.
Julkaisutarkistaja blokkasi sen nelja kierrosta perakkain, ja juurisyy ei
ollut sanamuoto vaan rakenne: jokainen `table.lb` saa `GEN:TABLE-TOOLS`ilta
klikkilajittelun ja suodatinpalkin, joten

  - "TOP 10 BY EXPECTED POINTS" muuttui KAHDELLA klikkauksella kymmeneksi
    kalleimmaksi tai kymmeneksi matalimmaksi,
  - suodattimet piilottavat rivit `display:none`-tyylilla jota
    `querySelectorAll` ei nae, joten kortti kantoi globaalin top-10:n vaikka
    jakaja katsoi DEF-listaa.

Kaksi yritysta korjata LUKIJA (kieltaytymisvahdit, lajittelumerkki) tuotti
kumpikin uusia valheita. Palvelinrivit poistavat koko luokan: kortti on aina
se nakyma jonka linkista tuleva lukija nakee.

Nama testit vartioivat rakennetta, eivat sanamuotoa.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PALVELINKORTTI = ["points", "expected-points", "xg-leaders", "defence"]

# 🔴 KENTTA -> SARAKEOTSIKKO. Pelkka "arvo on jokin rivin soluista" ei riita:
# portti mittasi 24.8 etta `mid` sai arvon rivin xA-solusta ja `value` osui
# soluun jonka arvo sattui olemaan sama. Oikea rivi, VAARA SARAKE - ja
# kortti nayttaisi projektiona luvun joka on jotain muuta. Sarakeotsikko
# luetaan renderoidusta theadista, joten sopimus ei voi ajautua erilleen.
SARAKKEET = {
    "points": {"name": "player", "team": "team", "tag": "pos",
               "mid": "xp", "value": "pts"},
    "expected-points": {"name": "player", "team": "team", "tag": "pos",
                        "mid": "price", "value": "6gw xp"},
    # 25.8: siirretty palvelinriveille. Molemmilla sivuilla on klikkilajittelu
    # ja xg-leadersilla lisaksi viisi suodatinta, joten DOM-lukija olisi
    # kantanut sen nakyman johon jakaja sattui suodattamaan.
    "xg-leaders": {"name": "player", "team": "team", "tag": "pos",
                   "mid": "games", "value": "xg"},
    # 🔴 Defence on JOUKKUElista: ei team- eika pos-saraketta, ja nimisarake
    # on "Team". `name_label="TEAM"` pinnataan erikseen alla.
    "defence": {"name": "team", "mid": "shots", "value": "xgc"},
}

# Otsikon on nimettava sama suure kuin arvosarake. Ilman tata "TOP 10 BY
# EXPECTED POINTS" voi vaihtua muotoon "TOP 10 BY PRICE" kenenkaan
# huomaamatta - portti mittasi senkin lapimenoksi.
OTSIKKO = {
    "points": ("ACTUAL", "PTS"),
    "expected-points": ("EXPECTED POINTS", "xP"),
    "xg-leaders": ("xG PER GAME", "xG/GAME"),
    # 🔴 SUUNTA ON OSA OTSIKKOA. Taulukko on NOUSEVASSA jarjestyksessa
    # (Arsenal 0,91 = paras puolustus), ja ensimmainen ehdotus oli
    # "MOST XG CONCEDED" eli tasan painvastainen kuin data.
    "defence": ("FEWEST xG CONCEDED", "xGC"),
}


def _kortin_spec(nimi: str) -> dict:
    """Palvelimen kirjoittama korttispec sivulta."""
    import html as _html
    m = re.search(r"data-card-spec='([^']*)'", _sivu(nimi))
    assert m, f"{nimi}: sivulla ei ole data-card-speciä"
    return json.loads(_html.unescape(m.group(1).replace("&#39;", "'")))


def _sivu(nimi: str) -> str:
    p = ROOT / "fpl" / f"{nimi}.html"
    if not p.exists():
        pytest.skip(f"{p.name} ei ole rakennettu")
    return p.read_text(encoding="utf-8", errors="replace")


def _spec(h: str) -> dict:
    m = re.search(r"data-card-spec='(.*?)'>", h, re.S)
    assert m, "sivulta puuttuu palvelimen kirjoittama data-card-spec"
    return json.loads(html.unescape(m.group(1)))


def _otsikot(h: str) -> list[str]:
    m = re.search(r"<thead>(.*?)</thead>", h, re.S)
    assert m, "taulukosta puuttuu thead"
    out = []
    for t in re.findall(r"<th[^>]*>(.*?)</th>", m.group(1), re.S):
        t = re.sub(r"<[^>]+>", "", t)
        out.append(t.replace(chr(9662), "").replace(chr(9652), "").strip().lower())
    return out


def _taulukon_rivit(h: str, maara: int = 10) -> list[list[str]]:
    tb = re.search(r"<tbody[^>]*>(.*?)</tbody>", h, re.S)
    assert tb, "taulukosta puuttuu tbody"
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", tb.group(1), re.S)[:maara]:
        out.append([re.sub(r"<[^>]+>", "", c).strip()
                    for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)])
    return out


@pytest.mark.parametrize("sivu", PALVELINKORTTI)
def test_card_rows_match_the_server_rendered_table(sivu):
    """Kortin rivit ovat SAMAT kuin sivun oletusnakyman kymmenen ensimmaista.

    Tama on koko rakenteen peruste: linkista tuleva lukija nakee tasan sen
    mita kuvassa lukee.
    """
    h = _sivu(sivu)
    spec = _spec(h)
    taulukko = _taulukon_rivit(h)
    otsikot = _otsikot(h)
    assert len(spec["rows"]) == len(taulukko) == 10
    for i, (kortti, rivi) in enumerate(zip(spec["rows"], taulukko), start=1):
        assert kortti["rank"] == i, f"rivi {i}: sijaluku ei ole jarjestyksessa"
        # Sarakeindeksia EI oleteta: /fpl/points alkaa nimella,
        # /fpl/expected-points sijaluvulla. Invariantti on etta kortin rivi
        # ja taulukon rivi ovat SAMA rivi samassa jarjestyksessa, ei se
        # missa sarakkeessa nimi sattuu olemaan.
        # 🔴 JOKAINEN NAKYVA KENTTA, ei vain nimi ja arvo. Portin
        # ensimmainen versio jatti `mid`, `team` ja `tag` vartioimatta, ja
        # /fpl/points-kortilla `mid` ON projektio - puolet vaitteesta
        # "PROJECTED VS ACTUAL", ja ainoa luku jota mikaan ei mitannut.
        # 🔴 TASMALLINEN SOLU, EI SUBSTRING. Ensimmainen versio kaytti
        # `arvo in solu`, ja portti mittasi kolme lapimenoa: `mid` sai arvon
        # rivin xG-solusta (vaara SARAKE, oikea rivi), `value='1'` osui
        # soluun '11', ja PTS sai Diff-solun arvon. Substring-osuma on sokea
        # tasan silloin kun luku on oikean nakoinen mutta vaarasta paikasta.
        for kentta, otsikko in SARAKKEET[sivu].items():
            arvo = kortti.get(kentta)
            if not arvo:
                continue
            assert otsikko in otsikot, (
                f"{sivu}: saraketta {otsikko!r} ei ole theadissa {otsikot!r}")
            j = otsikot.index(otsikko)
            assert j < len(rivi), f"rivi {i}: saraketta {j} ei ole"
            # 🔴 TASMALLINEN, EI SUBSTRING. `arvo in rivi[j]` paastaa lapi
            # katkaistun arvon: value '1' osuu soluun '17' ja team 'BH'
            # soluun 'BHA'. Kortti nayttaisi silloin eri luvun kuin
            # taulukko, ja portti sanoisi ne samaksi.
            assert arvo == rivi[j], (
                f"rivi {i}: kortin {kentta}={arvo!r} ei vastaa saraketta "
                f"{otsikko!r} (={rivi[j]!r}) - oikea rivi mutta vaara "
                f"sarake tai eri lahde")


@pytest.mark.parametrize("sivu", PALVELINKORTTI)
def test_card_does_not_read_the_live_dom(sivu):
    """Negatiivinen kontrolli: DOM-lukija ei saa palata takaovesta.

    `querySelectorAll('tbody tr')` kortin JS:ssa on tasan se kuvio joka
    blokattiin. Fallback saa olla olemassa, mutta sen on oltava inertti
    (`function(){return null;}`), koska palvelinspec on aina lasna.
    """
    h = _sivu(sivu)
    assert "data-card-spec" in h
    assert "specFromServer" in h, "kortti ei lue palvelinspecia"
    js = re.search(r"var spec=specFromServer\(\);(.*?)\}\);", h, re.S)
    assert js, "kortin klikkauskasittelijaa ei loydy"
    # 🔴 `"tbody tr" not in ...` OLI SOKEA. Livena oleva /fpl/stats-fallback
    # ei kayta sita vaan `tb.querySelectorAll('tr')`, eli portti olisi
    # paastanyt lapi tasan sen lukijan joka on neljasti todettu
    # valehtelevaksi. Vaaditaan fallbackin INERTTIYS sanatarkasti, ei
    # kielleta yhta kirjoitusasua.
    assert "function(){return null;}" in js.group(1), (
        f"{sivu}: fallback ei ole inertti - kortti voi pudota lukemaan "
        f"elavaa DOMia jos palvelinspec puuttuu")
    assert "querySelector" not in js.group(1), (
        f"{sivu}: kortin klikkauskasittelija koskee DOMiin - lajittelu ja "
        f"suodattimet muuttaisivat kuvan sisallon otsikon muuttumatta")

    # Aukko B: seka JS etta portti ottivat ENSIMMAISEN osuman. Kahdella
    # taulukolla kortti nayttaisi vaaran, ja portti vertaisi vaaraa
    # itseensa. Kaksi taulukkoa on seuraavan migraation paassa.
    assert h.count("data-card-spec='") == 1, (
        f"{sivu}: sivulla on {h.count(chr(39).join(['data-card-spec=', '']))} "
        f"korttispecia - tasan yksi sallitaan, muuten kortti arvaa")


@pytest.mark.parametrize("sivu", PALVELINKORTTI)
def test_card_spec_carries_every_required_field(sivu):
    """Puuttuva kentta ei saa jaada hiljaiseksi: renderoija piirtaisi
    oletuksen, ja oletus on eri vaite kuin tyhja."""
    spec = _spec(_sivu(sivu))
    for k in ("title", "subtitle", "nameLabel", "valueLabel", "rows",
              "fileName", "footNote2"):
        assert spec.get(k), f"{sivu}: korttispecista puuttuu {k}"
    assert spec["fileName"].endswith(".png")
    for r in spec["rows"]:
        for k in ("rank", "name", "value"):
            assert r.get(k) not in (None, ""), f"rivilta puuttuu {k}: {r}"


# ---------------------------------------------------------------------------
# 🔴 VAITTEET, EI VAIN RIVIT
# ---------------------------------------------------------------------------
# Portti mittasi 24.8 etta jokainen kortin TEKSTIVAITE lapaisi vaikka se
# vaihdettaisiin valheeksi: otsikko "TOP 10 BY PRICE", alaotsikko
# "frozen 22 Aug, AFTER deadline", "model MAE 0.4 pts", "GW1 final",
# "the full top 100 is Premium". Rivivahti vartioi rivit, ei sita mita
# kortti niista sanoo. Nama testit sitovat vaitteet SIVUN omiin lukuihin.

def test_points_card_claims_match_the_page():
    """Kortti 1:n jokainen luku ja tilavaite on sivulta tarkistettavissa."""
    h = _sivu("points")
    spec = _spec(h)

    mae = re.search(r"mean absolute error is <strong>([0-9.]+) points", h)
    assert mae, "sivulta puuttuu MAE-lause"
    n = re.search(r"Across the (\d+) players in both the projection", h)
    assert n, "sivulta puuttuu verrattujen maara"
    assert spec["footNote"] == (
        f"model MAE {mae.group(1)} pts across {n.group(1)} compared players"), (
        f"kortin MAE-ankkuri ei vastaa sivun omaa lausetta: "
        f"{spec['footNote']!r}")

    # "before the deadline" on MITATTU relaatio, ei sanamuoto: sivu kertoo
    # molemmat aikaleimat, joten kortti ei saa vaittaa vastakkaista.
    ts = re.search(r"frozen ([0-9T:\-]+) UTC for the GW\d+ deadline "
                   r"([0-9T:\-]+) UTC", h)
    if ts and "before the deadline" in spec["subtitle"]:
        assert ts.group(1) < ts.group(2), (
            "kortti sanoo 'before the deadline' mutta sivun aikaleimat "
            "sanovat muuta")

    gw = re.search(r"GW(\d+)", spec["title"])
    assert gw, "otsikosta puuttuu kierrosnumero"
    # "SO FAR" ja "not final" kulkevat yhdessa: toinen ilman toista on
    # ristiriita samalla kortilla.
    assert ("SO FAR" in spec["title"]) == ("not final" in spec["footNote2"]), (
        f"otsikko ja alaviite eri mielta kierroksen tilasta: "
        f"{spec['title']!r} / {spec['footNote2']!r}")


def test_expected_points_card_claims_match_the_page():
    """Kortti 2:n ikkuna ja ilmaislupaus ovat sivulta tarkistettavissa."""
    h = _sivu("expected-points")
    spec = _spec(h)

    ikkuna = re.search(r"Ranked by total xP over (GW[0-9-]+)", h)
    assert ikkuna, "sivulta puuttuu ikkunalause"
    assert spec["subtitle"].startswith(ikkuna.group(1) + ","), (
        f"kortin ikkuna {spec['subtitle']!r} ei ala sivun ikkunalla "
        f"{ikkuna.group(1)!r}")

    # Ilmaislupaus on tarkistettava: sivun on oikeasti naytettava se maara
    # ilman kirjautumista.
    assert "free on goaliq.app" in spec["footNote"], spec["footNote"]
    luvattu = re.search(r"the full top (\d+) is free", spec["footNote"])
    assert luvattu, f"footNote ei nimea maaraa: {spec['footNote']!r}"
    rivit = len(re.findall(r"<tr>", re.search(
        r"<tbody[^>]*>(.*?)</tbody>", h, re.S).group(1)))
    assert rivit == int(luvattu.group(1)), (
        f"kortti lupaa top {luvattu.group(1)} mutta sivulla on {rivit} rivia")

    # Esikausivaraus on datalipun takana, ei kalenterissa.
    if "pre-season" in spec["subtitle"]:
        assert "pre-season" in spec["footNote2"] or "Rows move" in spec["footNote2"]


@pytest.mark.parametrize("sivu", PALVELINKORTTI)
def test_card_title_names_the_value_column(sivu):
    """Otsikon on nimettava sama suure kuin arvosarake.

    Portti mittasi 24.8 etta "TOP 10 BY EXPECTED POINTS" -> "TOP 10 BY
    PRICE" lapaisi: rivit olivat oikein, mutta kortti vaitti rankkaavansa
    jollain muulla. Otsikko on kortin painavin vaite ja se oli ainoa jota
    mikaan ei mitannut.
    """
    spec = _spec(_sivu(sivu))
    otsikossa, arvossa = OTSIKKO[sivu]
    assert otsikossa in spec["title"], (
        f"{sivu}: otsikko {spec['title']!r} ei nimea arvosaraketta "
        f"({otsikossa!r})")
    assert arvossa.lower() in spec["valueLabel"].lower(), (
        f"{sivu}: valueLabel {spec['valueLabel']!r} ei vastaa otsikkoa")


# ---------------------------------------------------------------------------
# KAUSI JA TUOREUSVAITE (25.8.2026)
# ---------------------------------------------------------------------------
# 🔴 JULKAISUPORTTI LOYSI TAMAN, EIVAT NAMA TESTIT. Kumpikin kortti pudotti
# kausitiedon ja korvasi sen paivamaaralla:
#
#   defence  : lahde on KOKO PAATTYNYT 2025/26 (38 ottelua per joukkue,
#              artefakti jaadytetty 8.8). Kortti sanoi "As of 25 Aug".
#              Sivu mainitsee kauden viidesti, kortti ei kertaakaan.
#   xg-leaders: kymmenesta rivista KUUSI on `basis=2025/26`. Rullaava ikkuna
#              sekoittaa kausia kunnes pelaajalla on 3 ottelua talla kaudella.
#
# "As of {pvm}" ei ollut kopioitu maneeri vaan AKTIIVINEN TUOREUSVAITE, ja se
# oli epatosi kaikilla defencen riveilla ja kuudella xg-kortin kymmenesta.
KAUSIPAKOLLINEN = ["xg-leaders", "defence"]


@pytest.mark.parametrize("sivu", KAUSIPAKOLLINEN)
def test_kortti_nimeaa_kauden(sivu):
    """Kortti jonka data on menneelta kaudelta ON nimettava se kausi. Lukija ei
    nae sivun ymparoivaa tekstia — kortti matkustaa yksin."""
    spec = _kortin_spec(sivu)
    teksti = " ".join(str(spec.get(k) or "")
                      for k in ("title", "subtitle", "footNote", "footNote2"))
    assert re.search(r"20\d\d/\d\d", teksti), (
        f"{sivu}: kortti ei nimea kautta lainkaan — {teksti!r}")


@pytest.mark.parametrize("sivu", KAUSIPAKOLLINEN)
def test_kortti_ei_vaita_tuoreutta_paivamaaralla(sivu):
    """🔴 "As of {pvm}" lukee tuoreutena. Naiden kahden kortin data ei ole
    tuoretta siina merkityksessa, joten paivamaara on vaite eika leima.

    (Points- ja expected-points-korteilla paivamaara ON oikein: niiden luvut
    liikkuvat joka ajossa. Siksi tama portti koskee vain naita kahta.)
    """
    spec = _kortin_spec(sivu)
    teksti = " ".join(str(spec.get(k) or "")
                      for k in ("subtitle", "footNote", "footNote2"))
    assert "As of" not in teksti, (
        f"{sivu}: kortti vaittaa tuoreutta paivamaaralla vaikka data on "
        f"menneelta kaudelta — {teksti!r}")


@pytest.mark.parametrize("sivu", PALVELINKORTTI)
def test_xg_kirjoitetaan_pienella_x(sivu):
    """`xG` on termi jonka kirjoitusasu kantaa merkitysta. `XG` versaali-
    otsikossa lukee silta ettei kirjoittaja tunne sita, ja sisarkortti sailytti
    pienen x:n samassa generaattorissa."""
    spec = _kortin_spec(sivu)
    for kentta in ("title", "subtitle", "valueLabel", "midLabel"):
        arvo = str(spec.get(kentta) or "")
        assert not re.search(r"XG", arvo), (
            f"{sivu}.{kentta}: 'XG' pitaa olla 'xG' — {arvo!r}")
