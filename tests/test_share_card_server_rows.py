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
PALVELINKORTTI = ["points", "expected-points", "xg-leaders", "defence",
                  # 27.8 batch 2: team-news (Ruled out -taulukko, arvo = Owned)
                  "team-news", "stats"]
# 27.8 batch 2: sivut joilla kortti ei lue table.lb:ta vaan omaa rivilistaa.
# Kullekin oma lukija joka palauttaa [(nimi, arvo, mid)] sivun NAKYVISTA
# riveista, jotta sama "kortti == sivu" -invariantti patee.
EI_TAULUKKO = ["price-changes", "best-captain"]

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
    # 27.8: `tag2` = rivin kausi. Sekakausilistalla alaotsikko ei kerro
    # kumpi rivi on kumpaa; portti vaatii tagin identtiseksi Season-solun
    # kanssa, jotta kortti ei voi vaittaa eri kautta kuin taulukko.
    "xg-leaders": {"name": "player", "team": "team", "tag": "pos",
                   "tag2": "season", "mid": "games", "value": "xg"},
    # 🔴 Defence on JOUKKUElista: ei team- eika pos-saraketta, ja nimisarake
    # on "Team". `name_label="TEAM"` pinnataan erikseen alla.
    "defence": {"name": "team", "mid": "shots", "value": "xgc"},
    "team-news": {"name": "player", "team": "club", "tag": "pos",
                  "value": "owned"},
    "stats": {"name": "player", "team": "team", "tag": "pos",
              "mid": "mins", "value": "pts"},
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
    "team-news": ("RULED OUT", "OWNED"),
    "stats": ("FPL POINTS", "PTS"),
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
    # 27.8: stats-sivun thead kantaa id:n (<thead id="sth">), sama rakenne.
    m = re.search(r"<thead[^>]*>(.*?)</thead>", h, re.S)
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
        solut = []
        for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S):
            # 27.8: joukkueen luottamuslippu (`<span class="tflag">turnover
            # </span>`) renderoityy joukkuesolun SISAAN. Se on sivun oma
            # varaus eika osa joukkuekoodia, ja kortti kantaa tarkoituksella
            # vain koodin. Ilman tata portti kaatui heti kun CI:n
            # team_confidence liputti Brightonin (BHA -> "BHAturnover").
            # Poistetaan VAIN tama yksi luokka, ei mitaan muuta.
            c = re.sub(r'<span class="tflag">[^<]*</span>', "", c)
            # 29.8: entiteetit puretaan, koska kortin spec on JSONia
            # (`json.loads(html.unescape(...))`) ja taulukko on HTML:aa.
            # GW2:n O'Reilly paljasti eron: kortti kantaa "O'Reilly", solu
            # "O&#x27;Reilly", ja portti sanoi niita eri arvoiksi vaikka ne
            # ovat sama merkkijono eri esityksessa. Purku EI loysenna
            # vertailua: se on yha tasmallinen, ks. negatiivinen kontrolli
            # test_row_gate_still_catches_a_different_name.
            solut.append(html.unescape(re.sub(r"<[^>]+>", "", c)).strip())
        out.append(solut)
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


def test_row_gate_still_catches_a_different_name():
    """NEGATIIVINEN KONTROLLI entiteettipurulle (29.8). Purku saa poistaa
    esityseron, ei aitoa eroa: eri nimi, katkaistu nimi ja eri kirjoitusasu
    kaatavat yha."""
    rivi = _taulukon_rivit(
        "<table><tbody><tr><td>O&#x27;Reilly</td><td>BHA</td></tr></tbody></table>")[0]
    assert rivi[0] == "O'Reilly"          # sama merkkijono, ei entiteetti
    for vaara in ("O'Reilly Jr", "O'Reill", "OReilly", "O`Reilly", "o'reilly"):
        assert vaara != rivi[0], f"{vaara!r} ei saa vastata solua {rivi[0]!r}"


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


# ---------------------------------------------------------------------------
# KAUSIVAITE JOHDETAAN KORTIN OMISTA RIVEISTA (25.8.2026)
# ---------------------------------------------------------------------------
# 🔴 JULKAISUPORTTI LOYSI TAMANKIN. Kausivaite laskettiin `_rivikaudet`ista,
# joka tulee KOKO aineistosta (442 pelaajaa); kortti nayttaa 10. Tanaan joukot
# osuvat yhteen, joten vaite on tosi — SATTUMALTA. Kauden edetessa
# karkikymmenikko tayttyy 2026/27-riveilla kun hanta kantaa 2025/26:n pitkalle
# kevaaseen, ja kortti sanoisi "mixing 2025/26 and 2026/27" kymmenesta rivista
# jotka ovat KAIKKI tata kautta.
#
# 🔴 MERKKIJONOTESTI EI OLISI PURRUT: tuloste on tanaan identtinen kummallakin
# johtamistavalla. Portin on verrattava vaitetta KORTIN OMIEN RIVIEN
# kausiperustaan, ei sen nykyiseen sanamuotoon.


def _kortin_rivien_kaudet() -> set[str] | None:
    """Kortin kymmenen rivin kausiperusta lahdedatasta."""
    import json as _json
    d = ROOT / "data" / "fpl_player_leaders.json"
    if not d.exists():
        return None
    try:
        from src.models.fpl_leaders import rank_xg_leaders
    except Exception:
        return None
    out = rank_xg_leaders(_json.loads(d.read_text(encoding="utf-8")),
                          window=5, top_n=10)
    return {str(r.get("basis") or "") for r in out["players"][:10]} - {""}


def test_xg_kortti_nimeaa_TASAN_omien_riviensa_kaudet():
    """🔴 Ei koko aineiston kausia. Vaite koskee kymmenta rivia, joten se on
    johdettava niista kymmenesta."""
    odotus = _kortin_rivien_kaudet()
    if not odotus:
        pytest.skip("leaders-data ei saatavilla")
    teksti = _kortin_spec("xg-leaders")["subtitle"]
    mainitut = set(re.findall(r"20\d\d/\d\d", teksti))
    assert mainitut == odotus, (
        f"kortti mainitsee {sorted(mainitut)} mutta sen omat rivit ovat "
        f"{sorted(odotus)} — vaite on johdettu vaarasta joukosta")


def test_defence_ei_vaita_each_kun_ottelumaarat_eroavat():
    """🔴 `max()` ei todista sanaa "each". Tanaan kaikilla 17 joukkueella on 38
    ottelua, mutta kesken kauden ajettu artefakti antaisi eri lukuja ja `max`
    vaittaisi silti "each"."""
    import json as _json
    d = ROOT / "data" / "understat_team_defence_2526.json"
    if not d.exists():
        pytest.skip("defence-data ei saatavilla")
    doc = _json.loads(d.read_text(encoding="utf-8"))
    rivit = doc.get("teams") or doc.get("rows") or []
    maarat = {r.get("matches") or 0 for r in rivit}
    teksti = _kortin_spec("defence")["footNote2"]
    if len(maarat) == 1:
        assert "each" in teksti, "kaikilla sama ottelumaara -> 'each' on tosi"
        assert str(next(iter(maarat))) in teksti
    else:
        assert "each" not in teksti, (
            f"ottelumaarat eroavat ({sorted(maarat)}) mutta kortti sanoo "
            f"'each' — {teksti!r}")


# ---------------------------------------------------------------------------
# MEKANISMI SYNTEETTISELLA SYOTTEELLA
# ---------------------------------------------------------------------------
# 🔴 KAKSI EDELLISTA TESTIA OLIVAT SOKEITA, JA MUTAATIO NAYTTI SEN.
# Ne nojaavat tuotantodataan, ja 25.8 koko aineistosta ja karkikymmenikosta
# johdettu kausijoukko ovat IDENTTISET. Mutaatio `rows[:10]` -> `rows` lapaisi
# molemmat. Sama `each`-vahdilla: kaikilla 17 joukkueella on 38 ottelua, joten
# `_dsama = True` lapaisi.
#
# Mekanismi on siksi irrotettu omiksi funktioikseen ja testataan SYNTEETTISELLA
# syotteella jossa joukot AIDOSTI eroavat. Vasta se erottaa oikean johtamisen
# vaarasta.
from scripts.build_fpl_longtail import kortin_kaudet, ottelumaara_lause


def test_kausi_luetaan_vain_karkikymmenikosta():
    """Karki on yhta kautta, hanta toista. Kortti nayttaa karjen."""
    rivit = ([{"basis": "2026/27"}] * 10) + ([{"basis": "2025/26"}] * 400)
    assert kortin_kaudet(rivit) == ["2026/27"], (
        "kausi luettiin hannasta jota kortti ei nayta")


def test_sekakausi_tunnistetaan_kun_karki_on_sekainen():
    """Vastapari: kun karki AIDOSTI sekoittaa kausia, se sanotaan."""
    rivit = ([{"basis": "2026/27"}] * 6 + [{"basis": "2025/26"}] * 4
             + [{"basis": "2024/25"}] * 50)
    assert kortin_kaudet(rivit) == ["2025/26", "2026/27"]


def test_tyhja_basis_ei_muutu_kaudeksi():
    """Puuttuva kausi jaa pois, ei tyhjaksi merkkijonoksi listaan."""
    assert kortin_kaudet([{"basis": ""}, {}, {"basis": None}]) == []


def test_each_sanotaan_vain_kun_kaikilla_sama_ottelumaara():
    assert ottelumaara_lause({38}) == "38 matches each. "


def test_each_ei_sanota_kun_maarat_eroavat():
    """🔴 `max()` olisi sanonut "38 matches each" vaikka yhdella on 12."""
    lause = ottelumaara_lause({38, 37, 12})
    assert "each" not in lause, lause
    assert "at least 12" in lause


def test_ottelumaarasta_ei_synny_lausetta_ilman_dataa():
    assert ottelumaara_lause(set()) == ""
    assert ottelumaara_lause({0}) == ""


# ---------------------------------------------------------------------------
# KYTKENTA: renderoija KAYTTAA johdantaa (25.8.2026)
# ---------------------------------------------------------------------------
# 🔴 EDELLISET TESTIT JATTIVAT TAMAN AUKON, JA JULKAISUPORTTI OSOITTI SEN.
# `kortin_kaudet` voi olla taydellinen ja kortti silti vaara: mikaan testi ei
# vaittanyt etta `render_xg_leaders` KAYTTAA sen tulosta. Mutaatio
# `_korttikaudet = _rivikaudet` olisi mennyt lapi kaikista 34 testista, koska
# tuotantodatalla tulos on sama. Se on tasan se vikaluokka jossa portti mittaa
# eri koodipolkua kuin artefaktin tuottava.
#
# Tama testi ajaa RENDEROIJAN synteettisella syotteella jossa karki ja hanta
# aidosti eroavat, ja lukee kortin subtitlen renderoidysta HTML:sta.
from datetime import datetime


def _pelaaja(pid: int, basis: str, xg: float) -> dict:
    return {
        "id": pid, "code": pid, "web_name": f"P{pid}", "team_short": "AAA",
        "pos": "FWD", "price": 5.0, "owned_pct": 1.0, "basis": basis,
        "games_total": 5,
        # `xgi` on pakollinen: fpl_leaders lukee sen suoraan.
        "recent_games": [{"round": 1, "opp": "BBB", "venue": "H",
                          "minutes": 90, "xg": xg, "xa": 0.0, "xgi": xg,
                          "dc": 0, "cbi": 0, "tkl": 0, "rec": 0}],
    }


def test_renderoija_nimeaa_KARJEN_kauden_kun_hanta_on_eri_kautta():
    """🔴 Karki 10 x 2026/27, hanta 400 x 2025/26. Kortti nayttaa karjen, joten
    sen on nimettava vain sen kausi. Ilman tata testia johdanta voi olla oikea
    ja kutsu vaara."""
    from scripts.build_fpl_longtail import render_xg_leaders
    players = ([_pelaaja(i, "2026/27", 0.90) for i in range(10)]
               + [_pelaaja(1000 + i, "2025/26", 0.10) for i in range(400)])
    html_ = render_xg_leaders(
        {"meta": {"available": True, "basis_season": "2025/26",
                  "target_season": "2026/27"}, "players": players},
        datetime(2026, 8, 25))
    assert html_, "renderoija palautti tyhjan"
    m = re.search(r"data-card-spec='([^']*)'", html_)
    assert m, "renderoidyssa sivussa ei ole korttispekia"
    sub = json.loads(html.unescape(m.group(1).replace("&#39;", "'")))["subtitle"]
    assert "2025/26" not in sub, (
        f"kortti nimeaa hannan kauden vaikka nayttaa karjen rivit: {sub!r}")
    assert "2026/27" in sub, sub


def test_korttirivien_maara_on_yksi_vakio():
    """🔴 `10` oli kirjoitettu VIITEEN paikkaan eivatka ne olleet kytkettyja.
    Jos joku muuttaa kortin nayttamaan 12 rivia, `kortin_kaudet` lukisi yha
    kymmenen ja kortti nimeaisi vaaran joukon kaudet."""
    lahde = (ROOT / "scripts" / "build_fpl_longtail.py").read_text(
        encoding="utf-8")
    assert "CARD_ROWS = 10" in lahde
    assert "rows[:10]" not in lahde, (
        "kortin rivimaara on yha kovakoodattu jossain — kayta CARD_ROWSia")


# ---------------------------------------------------------------------------
# 27.8 batch 2: ei-taulukkosivut. Kortin rivit verrataan sivun omaan
# rivilistaan (.mrow / .stat), samat arvot samassa jarjestyksessa.
# ---------------------------------------------------------------------------

def _price_rows(h: str) -> list[tuple[str, str, str]]:
    """Risers-kortin (.card .mrow) rivit: (nimi, '82%', '£7.5m')."""
    kortti = re.search(r'<div class="card" data-card-spec=[^>]*>(.*?)</div>\s*(?:<h2>|$)', h, re.S)
    assert kortti, "price-changes: risers-korttia (.card + data-card-spec) ei loydy"
    out = []
    for m in re.finditer(r'<div class="mrow"><div><strong>(.*?)</strong><div class="meta">(.*?)</div>', kortti.group(1), re.S):
        nimi = html.unescape(m.group(1))
        meta = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
        hinta = re.search(r"£\d+\.\d+m", meta).group(0)
        pct = re.search(r"(\d+)% of the way", meta).group(1) + "%"
        out.append((nimi, pct, hinta))
    return out


def _captain_rows(h: str) -> list[tuple[str, str, str]]:
    """Kapteenitiilet (.stat-row .stat): (nimi, 'starts 92%' -> '92%', team)."""
    rivi = re.search(r'<div class="stat-row" data-card-spec=[^>]*>(.*?)</div>\s*<p', h, re.S)
    assert rivi, "best-captain: stat-row + data-card-spec ei loydy"
    out = []
    for m in re.finditer(r'<div class="stat"><b>(.*?)</b><span>(.*?)</span></div>', rivi.group(1), re.S):
        nimi = html.unescape(m.group(1)); meta = html.unescape(m.group(2))
        osat = [o.strip() for o in meta.split("·")]
        team = osat[1]
        sm = re.search(r"starts (\d+)%", meta)
        assert sm, f"best-captain: tiilella ei ole Start%-lukua: {meta}"
        out.append((nimi, sm.group(1) + "%", team))
    return out


@pytest.mark.parametrize("sivu", EI_TAULUKKO)
def test_non_table_card_rows_match_the_page(sivu):
    h = _sivu(sivu)
    if "data-card-spec" not in h:
        pytest.skip(f"{sivu}: ei korttia (lista tyhja)")
    spec = _spec(h)
    rivit = _price_rows(h) if sivu == "price-changes" else _captain_rows(h)
    assert len(spec["rows"]) == len(rivit), (len(spec["rows"]), len(rivit))
    for i, (k, (nimi, arvo, kolmas)) in enumerate(zip(spec["rows"], rivit), start=1):
        assert k["rank"] == i
        assert k["name"] == nimi, (k["name"], nimi)
        assert k["value"] == arvo, (k["value"], arvo)
        if sivu == "price-changes":
            assert k["mid"] == kolmas, (k["mid"], kolmas)
        else:
            assert k["team"] == kolmas, (k["team"], kolmas)


@pytest.mark.parametrize("sivu", EI_TAULUKKO)
def test_non_table_card_is_inert_without_server_spec(sivu):
    h = _sivu(sivu)
    if "data-card-spec" not in h:
        pytest.skip(f"{sivu}: ei korttia")
    assert "specFromServer" in h
    js = re.search(r"var spec=specFromServer\(\);(.*?)\}\);", h, re.S)
    assert js and "function(){return null;}" in js.group(1)
    assert h.count("data-card-spec='") == 1
