"""/fpl/points: toteutuneet pisteet vs deadlinella JÄÄDYTETTY ennuste.

Sivun koko arvo on siinä, että xP-sarake on se luku joka julkaistiin ENNEN
kierrosta. Elävä xP liikkuu kesken ja jälkeen kierroksen kohti toteumaa
(mitattu 22.8: Gabriel 5.78 -> 5.14), joten elävän vertaaminen toteumaan
näyttäisi mallin tarkempana kuin se oli. Nämä testit vartioivat tasan sitä.

7.9.2026 (FPL-POINTS-GW-ARKISTO): sivu on nyt VAIHETIETOINEN. Sama funktio
ajetaan kolmella synteettisellä kierroksen tilalla, koska invariantti joka
mitataan vain tässä kauden vaiheessa on vihreä siihen asti kun se lakkaa
olemasta tosi (CLAUDE.md 6a(3)):

  kesken               -> pelaamaton EI saa riviä (nolla olisi väite)
  gradattu, oli ottelu -> dnp-rivi, Pts 0, MAE:n ULKOPUOLELLA
  gradattu, ei ottelua -> n/a-rivi (nolla olisi väite ottelusta jota ei ollut)
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

import scripts.build_fpl_longtail as bl


NYT = datetime(2026, 8, 23, 12, 0)

COLS = ["gw", "pts", "g", "a", "dc", "cs", "bps", "bonus", "mins", "xg", "xa"]


def _player_gw(rows: dict[str, list[list]], max_gw: int = 1) -> dict:
    return {"meta": {"cols": COLS, "max_gw": max_gw, "basis_season": "2026/27"},
            "players": rows}


def _rivi(gw=1, pts=6, g=1, a=0, dc=3, cs=1, bps=25, bonus=1, mins=90,
          xg=0.4, xa=0.1):
    return [gw, pts, g, a, dc, cs, bps, bonus, mins, xg, xa]


def _frozen(players: list[dict], gw: int = 1) -> dict:
    return {"meta": {"gw": gw, "deadline": "2026-08-21T17:30:00Z",
                     "frozen_at": "2026-08-20T12:33:43Z"},
            "players": players}


@pytest.fixture
def frozen_stub(monkeypatch):
    """Ohjaa jäädytetyn lumikuvan lukemisen ilman levyä.

    `doc["d"]` = sama lumikuva jokaiselle kierrokselle (vanhat testit).
    `doc[gw]`  = kierroskohtainen lumikuva (arkistotestit).
    """
    doc: dict = {}

    def fake(gw):
        return doc.get(int(gw), doc.get("d"))

    monkeypatch.setattr(bl, "_latest_frozen_gw", fake)
    return doc


@pytest.fixture(autouse=True)
def gradaus_stub(monkeypatch):
    """Gradaustila TESTIN hallinnassa, ei levyn.

    🔴 OLETUS ON "EI GRADATTU". Ilman tätä fixtuuria testit lukisivat oikeaa
    `data/fpl_xp_gw_accuracy.json`:ää, jolloin sama testi mittaisi eri asiaa
    kauden eri vaiheissa: GW1 on tänään gradattu, viime kuussa se ei ollut.
    Sama vikaluokka kuin se jonka arkisto korjaa.
    """
    tila: dict[int, dict] = {}
    monkeypatch.setattr(bl, "_gradatut_kierrokset", lambda: dict(tila))
    return tila


def _gradaus(gw: int, *, n=500, mae=1.5, dnp_n=200) -> dict:
    return {"gw": gw, "graded_at": f"2026-09-0{gw}T12:00:00Z", "n": n,
            "mae": mae, "by_class": {"dnp": {"n": dnp_n, "mae": 1.0,
                                             "bias": -1.0}}}


def _teksti(html: str) -> str:
    """Näkyvä teksti. 🔴 script/style POIS ENSIN: ilman sitä CSS-luokan nimi
    `.dnp` olisi laskettu sivun väitteeksi, ja portti olisi mitannut
    tyylitiedostoa eikä sisältöä."""
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


# ---------------------------------------------------------------------------
# Alkuperäiset invariantit (kesken oleva kierros)
# ---------------------------------------------------------------------------

def test_xp_sarake_tulee_jaadytetysta_lumikuvasta(frozen_stub):
    """Jos xP tulisi muualta, tämä luku ei täsmäisi."""
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Gabriel", "team_short": "ARS", "pos": "DEF",
         "price": 6.1, "xp": 5.78},
    ])
    html = bl.render_points(_player_gw({"1": [_rivi(pts=5)]}), NYT)
    assert html is not None
    assert "5.78" in html          # jäädytetty arvo sellaisenaan
    assert "-0.78" in html         # 5 - 5.78, ei pyöristetty pois
    assert "5.14" not in html      # elävä arvo EI saa esiintyä


def test_ilman_jaadytettya_ennustetta_pudotetaan_mutta_sanotaan_aaneen(frozen_stub):
    """Hiljainen pudotus tekisi taulusta vajaan ilman että kukaan näkee."""
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Mukana", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 3.0},
    ])
    html = bl.render_points(
        _player_gw({"1": [_rivi()], "99": [_rivi(pts=9)]}), NYT)
    assert "Mukana" in html
    t = _teksti(html)
    assert "1 player who did play is also left out" in t


def test_mae_lasketaan_riveista_eika_kovakoodata(frozen_stub):
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "A", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 2.0},
        {"id": 2, "web_name": "B", "team_short": "CHE", "pos": "MID",
         "price": 5.0, "xp": 4.0},
    ])
    # toteumat 6 ja 4 -> virheet 4.0 ja 0.0 -> MAE 2.0
    html = bl.render_points(
        _player_gw({"1": [_rivi(pts=6)], "2": [_rivi(pts=4)]}), NYT)
    t = _teksti(html)
    assert "2.0 points" in t
    assert "too low on 1 of them and too high on 1" in t


def test_defcon_ja_muut_sarakkeet_ovat_mukana(frozen_stub):
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "A", "team_short": "ARS", "pos": "DEF",
         "price": 5.0, "xp": 3.0},
    ])
    html = bl.render_points(_player_gw({"1": [_rivi(dc=7, bps=31)]}), NYT)
    for otsikko in ("DC", "BPS", "xG", "xA", "Bonus" if False else "B"):
        assert f'>{otsikko}<' in html, otsikko
    assert "DefCon" in html      # selitetään lyhenne, ei jätetä arvattavaksi


def test_tyhja_syote_ei_tuota_sivua(frozen_stub):
    frozen_stub["d"] = _frozen([])
    assert bl.render_points(_player_gw({}), NYT) is None
    assert bl.render_points({"meta": {}, "players": {}}, NYT) is None


def test_jarjestys_on_toteutuneet_pisteet_laskevasti(frozen_stub):
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Vahan", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 8.0},
        {"id": 2, "web_name": "Paljon", "team_short": "CHE", "pos": "MID",
         "price": 5.0, "xp": 1.0},
    ])
    html = bl.render_points(
        _player_gw({"1": [_rivi(pts=2)], "2": [_rivi(pts=12)]}), NYT)
    assert html.index("Paljon") < html.index("Vahan")


# ---------------------------------------------------------------------------
# Synteettinen kierros: 20 joukkuetta, jotta "pelasiko joukkue" on pääteltävissä
# ---------------------------------------------------------------------------

def _maailma(gw: int = 1, *, joukkueita: int = 20, per_joukkue: int = 2,
             pelaa: int = 1, ilman_ottelua: int = 0, pts: int = 4,
             xp: float = 3.0):
    """(frozen-lumikuva, player-gw-rivit) hallitulla määrällä joukkueita.

    `ilman_ottelua` ensimmäistä joukkuetta ei pelaa lainkaan -> blank GW
    niiden pelaajille. Muilla joukkueilla `pelaa` pelaajaa saa rivin, loput
    ovat pelaamattomia.
    """
    frozen, rivit = [], {}
    pid = 0
    for t in range(joukkueita):
        lyhenne = f"T{t:02d}"
        for k in range(per_joukkue):
            pid += 1
            frozen.append({"id": pid, "web_name": f"P{pid}",
                           "team_short": lyhenne, "pos": "MID",
                           "price": 5.0, "xp": xp})
            if t >= ilman_ottelua and k < pelaa:
                rivit[str(pid)] = [_rivi(gw=gw, pts=pts)]
    return _frozen(frozen, gw), rivit


# ---------------------------------------------------------------------------
# 🔴 VAIHEINVARIANTTI: sama funktio, kolme kierroksen tilaa
# ---------------------------------------------------------------------------

def test_vaihe_kesken_pelaamaton_ei_saa_rivia(frozen_stub, gradaus_stub):
    """Puuttuva rivi on totuus KESKEN olevalla kierroksella; nolla olisi väite."""
    fro, rivit = _maailma(1)
    frozen_stub["d"] = fro
    html = bl.render_points(_player_gw(rivit), NYT)
    t = _teksti(html)
    assert "P1" in html                      # pelasi
    assert "dnp" not in t                    # pelaamattomasta ei sanota mitään
    assert ">P2<" not in html                # eikä hän ole taulukossa
    assert "has not played yet" in t


def test_vaihe_gradattu_pelaamaton_saa_dnp_rivin_mutta_ei_ole_maessa(
        frozen_stub, gradaus_stub):
    """🔴 MITTAA ARVON, EI MERKKIJONOA.

    Pelanneiden virhe on 4 - 3 = +1.0 kaikilla, pelaamattomien 0 - 3 = -3.0.
    Jos dnp-rivit vuotaisivat MAE:hen, luku olisi 2.0 eikä 1.0 - eli
    mutaatio "sisällytä dnp" kaataa tämän testin.
    """
    fro, rivit = _maailma(1, pts=4, xp=3.0)
    frozen_stub["d"] = fro
    gradaus_stub[1] = _gradaus(1)
    html = bl.render_points(_player_gw(rivit), NYT)
    t = _teksti(html)
    assert ">P2<" in html                    # pelaamaton on taulukossa
    assert "dnp" in t
    assert "1.0 points" in t                 # vain pelanneet
    assert "2.0 points" not in t             # dnp mukana olisi 2.0
    assert "20 of them did not play a minute" in t
    assert "compares only the 20 players who took the pitch" in t


def test_vaihe_blank_gameweek_saa_na_rivin_ei_nollaa(frozen_stub, gradaus_stub):
    """Joukkue jolla ei ollut ottelua: nolla olisi väite ottelusta jota ei
    ollut, joten rivi lukee n/a."""
    fro, rivit = _maailma(1, ilman_ottelua=2)
    frozen_stub["d"] = fro
    gradaus_stub[1] = _gradaus(1)
    html = bl.render_points(_player_gw(rivit), NYT)
    t = _teksti(html)
    # 18 joukkuetta pelasi (parillinen, >= 16) -> pääteltävissä
    assert "n/a" in t
    assert "4 had no fixture in this gameweek" in t
    # blank-joukkueen pelaaja ei saa nollaa
    p1 = re.search(r'<tr class="nodata"><td>P1</td>.*?</tr>', html, re.S)
    assert p1 and "n/a" in p1.group(0) and ">0</strong>" not in p1.group(0)


def test_dnp_paattely_on_fail_closed_kun_otteluita_ei_voi_paatella(
        frozen_stub, gradaus_stub):
    """Liian harva joukkue -> sivu EI väitä dnp:tä kenestäkään.

    Väärä "ei pelannut" olisi julkinen väite pelaajasta, joten epävarmuus
    kaataa koko luokan n/a:ksi eikä arvaa."""
    fro, rivit = _maailma(1, joukkueita=4)
    frozen_stub["d"] = fro
    gradaus_stub[1] = _gradaus(1)
    t = _teksti(bl.render_points(_player_gw(rivit), NYT))
    assert "dnp" not in t
    assert "could not be derived" in t


def test_dnp_paattely_vaatii_parillisen_joukkuemaaran(frozen_stub, gradaus_stub):
    """Ottelussa on kaksi joukkuetta. Pariton määrä = jokin puuttuu."""
    fro, rivit = _maailma(1, joukkueita=20, ilman_ottelua=3)   # 17 pelasi
    frozen_stub["d"] = fro
    gradaus_stub[1] = _gradaus(1)
    t = _teksti(bl.render_points(_player_gw(rivit), NYT))
    assert "dnp" not in t
    assert "could not be derived" in t


@pytest.mark.parametrize("gradattuja", [0, 1, 3])
def test_arkiston_olemassaolo_ei_riipu_gradauksesta(frozen_stub, gradaus_stub,
                                                    gradattuja, tmp_path,
                                                    monkeypatch):
    """🔴 SAMA FUNKTIO KOLMELLA SYNTEETTISELLÄ KIERROSLUVULLA.

    Arkistosivun OLEMASSAOLO on sidottu freezeen + pelattuun riviin, ei
    gradaukseen: kierros on FPL:ssä `finished` (ja sovellus näyttää sen
    tuloskortin) noin vuorokauden ennen gradausta, ja siinä ikkunassa kortin
    lupaama reitti palauttaisi 404. Gradaus ohjaa vain SISÄLTÖÄ.
    """
    for g in (1, 2, 3):
        (tmp_path / f"gw{g}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bl, "XP_FROZEN_DIR", tmp_path)
    rivit: dict[str, list[list]] = {}
    for g in (1, 2, 3):
        fro, osa = _maailma(g)
        frozen_stub[g] = fro
        for pid, rs in osa.items():
            rivit.setdefault(pid, []).extend(rs)
    for g in range(1, gradattuja + 1):
        gradaus_stub[g] = _gradaus(g)
    doc = _player_gw(rivit, max_gw=3)

    assert bl._arkistoitavat_kierrokset(doc) == [1, 2, 3]
    for g in (1, 2, 3):
        html = bl.render_points(doc, NYT, g, archive=True)
        assert html is not None, f"gw{g}: arkistosivua ei syntynyt"
        assert f'href="https://goaliq.app/fpl/points/gw{g}"' in html \
            or f'"https://goaliq.app/fpl/points/gw{g}"' in html
        t = _teksti(html)
        if g <= gradattuja:
            assert "dnp" in t, f"gw{g} on gradattu, dnp-rivien pitäisi näkyä"
            assert "Graded" in t
        else:
            assert "dnp" not in t, f"gw{g} ei ole gradattu, ei saa väittää dnp"
            assert "has not played yet" in t


def test_nauha_linkittaa_jokaiseen_arkistoituun_kierrokseen(frozen_stub,
                                                           gradaus_stub,
                                                           tmp_path, monkeypatch):
    """Jo jaetun kortin lukijan ainoa reitti omaan kierrokseensa."""
    for g in (1, 2, 3):
        (tmp_path / f"gw{g}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bl, "XP_FROZEN_DIR", tmp_path)
    rivit: dict[str, list[list]] = {}
    for g in (1, 2, 3):
        fro, osa = _maailma(g)
        frozen_stub[g] = fro
        for pid, rs in osa.items():
            rivit.setdefault(pid, []).extend(rs)
    doc = _player_gw(rivit, max_gw=3)
    live = bl.render_points(doc, NYT)
    for g in (1, 2, 3):
        assert f'href="/fpl/points/gw{g}"' in live, f"nauhasta puuttuu gw{g}"
    arkisto = bl.render_points(doc, NYT, 2, archive=True)
    assert 'href="/fpl/points"' in arkisto      # paluu uusimpaan
    assert 'href="/fpl/points/gw2"' not in arkisto   # ei linkkiä itseensä
    assert 'href="/fpl/points/gw1"' in arkisto


# ---------------------------------------------------------------------------
# 🔴 MAE-LÄHDEPORTTI: toinen luku LUETAAN, ei lasketa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mae", [9.99, 8.88])
def test_kaikkien_yli_laskettu_mae_luetaan_gradaustiedostosta(
        frozen_stub, gradaus_stub, mae):
    """Sama luku on jo /fpl:n tarkkuustaulukossa. Jos tämä sivu laskisi sen
    itse, kaksi julkista lukua samasta asiasta voisi eriytyä hiljaa.

    Testi vaihtaa LÄHTEEN arvoa ja vaatii että sivun luku seuraa: laskettu
    luku ei voisi seurata."""
    fro, rivit = _maailma(1)
    frozen_stub["d"] = fro
    gradaus_stub[1] = _gradaus(1, n=511, mae=mae, dnp_n=204)
    t = _teksti(bl.render_points(_player_gw(rivit), NYT))
    assert f"{mae:.2f} points" in t
    assert "Counting all 511 frozen players" in t
    assert "including the 204 who never got on the pitch" in t
    assert "fpl_xp_gw_accuracy.json" in t


def test_kesken_olevalla_kierroksella_ei_ole_toista_maeta(frozen_stub,
                                                          gradaus_stub):
    """Gradaamattomalta kierrokselta ei ole lukua luettavaksi, eikä sitä
    keksitä."""
    fro, rivit = _maailma(1)
    frozen_stub["d"] = fro
    t = _teksti(bl.render_points(_player_gw(rivit), NYT))
    assert "Counting all" not in t


# ---------------------------------------------------------------------------
# 🔴 TUPLAKIERROS
# ---------------------------------------------------------------------------

def test_tuplakierroksen_molemmat_ottelut_lasketaan_yhteen(frozen_stub):
    """`build_fpl_player_gw.py` ei aggregoi otteluita: DGW:ssä pelaajalla on
    kaksi riviä samalla `round`-arvolla. Ensimmäisen rivin ottaminen
    hukkaisi toisen ottelun pisteet HILJAA, ja arkistosivu on immutable."""
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Tupla", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 4.0},
    ])
    doc = _player_gw({"1": [_rivi(gw=1, pts=6, g=1, mins=90),
                            _rivi(gw=1, pts=9, g=2, mins=85)]})
    html = bl.render_points(doc, NYT)
    rivi = re.search(r"<tr><td>Tupla</td>.*?</tr>", html, re.S).group(0)
    assert ">15<" in rivi, f"pisteitä ei summattu: {rivi}"
    assert "+11.00" in rivi                      # 15 - 4.0
    assert ">175<" in rivi                       # minuutit summattu
    assert bl._gw_summa(doc["players"]["1"], {c: i for i, c in enumerate(COLS)},
                        1)["g"] == 3


def test_gw_summa_ei_sekoita_kierroksia(frozen_stub):
    ci = {c: i for i, c in enumerate(COLS)}
    gws = [_rivi(gw=1, pts=5), _rivi(gw=2, pts=7), _rivi(gw=2, pts=3)]
    assert bl._gw_summa(gws, ci, 1)["pts"] == 5
    assert bl._gw_summa(gws, ci, 2)["pts"] == 10
    assert bl._gw_summa(gws, ci, 3) is None


# ---------------------------------------------------------------------------
# Kierros tulee parametrista, ei metasta
# ---------------------------------------------------------------------------

def test_kierros_tulee_parametrista_eika_max_gwsta(frozen_stub):
    frozen_stub[2] = _frozen([
        {"id": 1, "web_name": "Kakkonen", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 3.0}], 2)
    frozen_stub[3] = _frozen([
        {"id": 1, "web_name": "Kolmonen", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 3.0}], 3)
    doc = _player_gw({"1": [_rivi(gw=2, pts=8), _rivi(gw=3, pts=2)]}, max_gw=3)
    kakkonen = bl.render_points(doc, NYT, 2)
    assert "Kakkonen" in kakkonen and ">8<" in kakkonen
    assert "GW2" in kakkonen and "GW3: PROJECTED" not in kakkonen
    kolmonen = bl.render_points(doc, NYT)          # max_gw
    assert "Kolmonen" in kolmonen and ">2<" in kolmonen


def test_arkistosivun_canonical_ja_leima(frozen_stub, gradaus_stub, tmp_path,
                                         monkeypatch):
    """Immutable sivu ei kanna ajohetkeä: `Updated <tänään>` on harhaanjohtava
    eikä mikään sivulla ole päivittynyt (ja se tuottaisi tyhjän diffin joka
    ajolta x 38 sivua)."""
    (tmp_path / "gw1.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bl, "XP_FROZEN_DIR", tmp_path)
    fro, rivit = _maailma(1)
    frozen_stub["d"] = fro
    gradaus_stub[1] = _gradaus(1)
    html = bl.render_points(_player_gw(rivit), NYT, 1, archive=True)
    assert '<link rel="canonical" href="https://goaliq.app/fpl/points/gw1"' in html
    t = _teksti(html)
    assert "Graded 2026-09-01" in t
    assert "Updated 23 Aug 2026" not in t
