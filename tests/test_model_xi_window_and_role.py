"""Portti: `/fpl/model-xi` kertoo ikkunansa ja sen ettei se ole entryn joukkue.

🔴 VILLEN LOYDOS 4.9.2026. Sivu naytti "310.8 Projected points, XI" ja
"39.2 xP" kertomatta etta luvut ovat KUUDEN kierroksen (GW3-GW8) summia. Sana
`horizon` esiintyi sivulla nelja kertaa ja **kaikki nelja olivat meta-, og-,
twitter- ja JSON-LD-kuvauksissa**, eli vain hakukoneelle ja linkkiesikatselulle.
Nakyvassa tekstissa ei ollut ikkunaa lainkaan. `116920` esiintyi sivulla
0 kertaa.

Samaan aikaan liikkeella oli kaksi muuta "mallin XI:ta":
  * 3.9 postattu kortti: "Best XI for GW3 alone", 67,6 pistetta, YKSI kierros
  * entry 116920: se runko jota oikeasti pelataan, siirtosaannoilla rajattu

Mitattu paallekkaisyys 15:sta: sivu-kortti **8**, sivu-entry **7**,
kortti-entry **6**. Kolme eri joukkuetta, kolme eri kysymysta, ja vain kortti
kertoi omansa.

Testi ajaa OIKEAN renderointipolun (`render_model_xi`) fikstuurilla, ei greppaa
lahdekoodia: portti joka mittaa eri koodipolkua kuin tuotanto on naennainen
(muisti: `portti-voi-mitata-eri-koodipolkua`).
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_fpl_longtail import render_model_xi

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 4, 13, 0, tzinfo=timezone.utc)


def _player(i: int, pos: str, price: float, xp: float, gws: list[int]) -> dict:
    return {
        "id": i,
        "web_name": "P%d" % i,
        "pos": pos,
        "price": price,
        # >= 5 seuraa: 3/seura-katto tekee 15:n mahdottomaksi kahdella.
        "team_short": "T%02d" % (i % 12),
        "team": "Team",
        "xmins": 85.0,
        "p_start": 0.9,
        "_nailed": True,
        "xp_horizon_total": xp,
        "xp_per_gw": xp / max(len(gws), 1),
        "gameweeks": [{"gw": g, "xp": xp / max(len(gws), 1)} for g in gws],
    }


def _xp(gws: list[int]) -> dict:
    """Riittavan iso pooli jotta optimoija saa laillisen 15:n."""
    players = []
    i = 0
    # runsaasti halpoja ja muutama kallis joka positioon
    for pos, n in (("GKP", 8), ("DEF", 22), ("MID", 22), ("FWD", 14)):
        for k in range(n):
            i += 1
            hinta = 4.0 + (k % 8) * 0.5
            xp = 5.0 + (k % 8) * 4.0
            players.append(_player(i, pos, hinta, xp, gws))
    return {"meta": {"available": True, "horizon_gw": len(gws)},
            "players": players}


def _render(gws: list[int]) -> str:
    html = render_model_xi(_xp(gws), NOW)
    assert html, "renderointi palautti None fikstuurilla jonka pitaisi kelvata"
    return html


def _nakyva(html: str) -> str:
    """Vain se mita lukija nakee: ei <head>, ei script/style, ei attribuutteja.

    Ilman tata portti lapaisisi meta-kuvauksen ansiosta - juuri se oli
    4.9:n vika.
    """
    body = html.split("<body", 1)[-1]
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body)
    return re.sub(r"(?s)<[^>]*>", " ", body)


# --- 1. ikkuna nakyy lukijalle ---------------------------------------------

def test_ikkuna_on_nakyvassa_tekstissa():
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8]))
    assert "GW3-GW8" in nakyva
    assert "6 gameweeks" in nakyva


def test_ikkuna_on_kiinni_luvussa_ei_vain_ledessa():
    """Varoitus kaukana luvusta ei ole varoitus: jokaisen pelaajarivin xP:n
    vieressa on ikkuna."""
    html = _render([3, 4, 5, 6, 7, 8])
    solut = re.findall(r"<span>([\d.]+ xP.*?)</span>", html)
    assert solut, "yhtaan xP-solua ei loytynyt - portti mittaisi tyhjaa"
    ilman = [s for s in solut if "GW3-GW8" not in s]
    assert not ilman, ilman


def test_stat_ruutu_nimeaa_ikkunan():
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8]))
    assert "Projected points, XI, GW3-GW8" in nakyva


def test_ikkuna_johdetaan_datasta_ei_kovakoodata():
    """Kauden lopussa horisontti kutistuu. Kovakoodattu teksti nayttaisi
    hoidetulta (muisti: ehto-ei-vanhene-teksti-vanhenee)."""
    nakyva = _nakyva(_render([35, 36, 37]))
    assert "GW35-GW37" in nakyva
    assert "3 gameweeks" in nakyva
    assert "GW3-GW8" not in nakyva


def test_yksi_kierros_taipuu_yksikkoon():
    nakyva = _nakyva(_render([38]))
    assert "GW38" in nakyva
    assert "1 gameweek" in nakyva
    assert "1 gameweeks" not in nakyva


def test_ilman_kierroksia_sivua_ei_renderoida():
    """xP-luku ilman ikkunaa on se vaara vaihtoehto joka tehdaan
    mahdottomaksi: ennemmin vanha sivu jaa voimaan."""
    data = _xp([3, 4, 5])
    for p in data["players"]:
        p["gameweeks"] = []
    assert render_model_xi(data, NOW) is None


# --- 2. rooli: tama ei ole entryn joukkue -----------------------------------

def test_sivu_erottaa_itsensa_entrysta():
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8]))
    assert "116920" in nakyva
    assert "not the team the model plays" in nakyva


def test_sivu_ei_luettele_kolmatta_tapausta():
    """Portin 4.9 huomio: "A one gameweek best XI is different again" oli
    taydellisyys-tunnusmerkki. Kortti on somessa eika lukijalla ole sita
    edessaan talla sivulla; ihminen nimeaa yhden asian ja lopettaa. Erottelu
    kolmesta tapauksesta jaa llms.txt:aan, jonka lukija on kone eika nae
    muita pintoja."""
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8]))
    assert "one gameweek best XI" not in nakyva
    # ...mutta olennainen erottelu on yha paikallaan
    assert "not the team the model plays" in nakyva


# --- 3. negatiiviset kontrollit --------------------------------------------

def test_negatiivinen_kontrolli_meta_ei_riita():
    """4.9:n vika oli tasan tama: ikkuna oli meta-kuvauksissa muttei sivulla.
    `_nakyva` EI saa nahda <head>:n sisaltoa."""
    html = _render([3, 4, 5, 6, 7, 8])
    head = html.split("<body", 1)[0]
    assert "GW3-GW8" in head, "meta-kuvauksen kuuluu yha kertoa ikkuna"
    nakyva = _nakyva(html)
    assert "og:description" not in nakyva
    assert "<meta" not in nakyva
    # ...ja nakyvan tekstin osuma on siis oikeasti sivulta
    assert nakyva.count("GW3-GW8") >= 2


def test_negatiivinen_kontrolli_pelkka_lede_ei_riita():
    """Mutaatio: jos ikkuna poistetaan pelaajasoluista mutta jatetaan
    ledeen, `test_ikkuna_on_kiinni_luvussa` ON kaadettava."""
    html = _render([3, 4, 5, 6, 7, 8])
    mutatoitu = re.sub(r"<i>GW3-GW8</i>", "", html)
    solut = re.findall(r"<span>([\d.]+ xP.*?)</span>", mutatoitu)
    assert solut
    assert [s for s in solut if "GW3-GW8" not in s], (
        "mutaatio ei muuttanut mitaan - portti ei mittaa pelaajasoluja")


def test_negatiivinen_kontrolli_nakyva_ei_ole_tyhja():
    """Testi joka lukee tyhjaa lapaisee aina."""
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8]))
    assert len(nakyva) > 1500, len(nakyva)
    assert "The Model XI" in nakyva


@pytest.mark.parametrize("gws", [[3], [3, 4], list(range(3, 9)),
                                 [36, 37, 38]])
def test_invariantti_kaikissa_kauden_vaiheissa(gws):
    """Sama invariantti mitataan jokaisessa vaiheessa, ei nykyhetkessa
    (saanto 6a kohta 3)."""
    html = _render(gws)
    nakyva = _nakyva(html)
    odotettu = f"GW{gws[0]}" if len(gws) == 1 else f"GW{gws[0]}-GW{gws[-1]}"
    assert odotettu in nakyva
    solut = re.findall(r"<span>([\d.]+ xP.*?)</span>", html)
    assert solut
    assert all(odotettu in s for s in solut)
    assert "116920" in nakyva


# --- 4. julkaisuportin 4.9 loydokset ----------------------------------------

def test_naulattu_vaite_ei_ole_ehdoton_lupaus():
    """🔴 Portin loydos 4.9: `p_start` PUUTTUI render_model_xi:n poolista,
    joten `_xi_start_risk`in suodatin ei loytanyt koskaan riskipelaajaa ja
    sivu tulosti AINA "Every player in this XI projects as a nailed starter".
    Haara "Not everyone here is nailed" oli inertti kirjoitushetkesta asti.
    """
    data = _xp([3, 4, 5, 6, 7, 8])
    # kalleimmat (= korkein xP) paatyvat XI:hin; laske yksi niista alas
    kohde = max(data["players"], key=lambda p: p["xp_horizon_total"])
    kohde["p_start"] = 0.60
    html = render_model_xi(data, NOW)
    nakyva = _nakyva(html)
    assert "Not everyone here is nailed" in nakyva, (
        "riskihaara ei laukea vaikka XI:ssa on 0,60-pelaaja")
    assert "Every player in this XI projects as a nailed starter" not in nakyva


def test_kontrolli_naulattu_haara_laukeaa_yha():
    """Negatiivisen kontrollin pari: molemmat haarat on saatava laukeamaan,
    muuten testi voisi lapaista koska haara on kaantynyt inertiksi toisin
    pain."""
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8]))
    assert "Every player in this XI projects as a nailed starter" in nakyva


def test_optimaalisuusvaite_kulkee_saman_portin_lapi_kuin_lede():
    """🔴 Portin loydos 4.9: kappale sanoi suoraan "This is a budget optimum",
    vaikka `optimal_xi_proven()` on False. Mitattu samana paivana: entryn
    rungosta johdettu laillinen 15 antoi XI:lle 322,42 xP kun sivu naytti
    310,77 — eli hakumme ei loyda optimia."""
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8]))
    from src.models.fpl_rate_team import optimal_xi_proven
    if optimal_xi_proven():
        assert "the proven optimum XI inside the 100.0m budget" in nakyva
    else:
        assert "the best XI our search found" in nakyva
        assert "This is a budget optimum" not in nakyva
        assert "proven optimum" not in nakyva


def test_entry_nimella_on_reitti():
    """Lihavoitu nimi ilman linkkia ei ole tarkistettavissa
    (muisti: vaite-tarvitsee-reitin)."""
    data = _xp([3, 4, 5, 6, 7, 8])
    data["meta"]["completed_gameweeks"] = [1, 2]
    html = render_model_xi(data, NOW)
    assert 'href="https://fantasy.premierleague.com/entry/116920/event/2"' in html


def test_entry_ilman_pelattua_kierrosta_ei_saa_rikkinaista_linkkia():
    """Kauden alussa pickeja ei ole julkisena: nimi jaa lihavoinniksi eika
    linkiksi joka vie 404:aan."""
    data = _xp([1, 2, 3, 4, 5, 6])
    data["meta"]["completed_gameweeks"] = []
    html = render_model_xi(data, NOW)
    assert "<b>Entry 116920</b>" in html
    assert "/entry/116920/event/" not in html


# --- 5. optimaalisuusvaite on YHDESSA portissa, ei kuudessa polussa ---------

OPTIMISMI = ("highest-scoring", "highest expected", "best possible",
             "budget optimum", "proven optimal", "best 100.0m")


def test_hedgaamaton_vaite_ei_paase_headiin():
    """🔴 Portin loydos 4.9: `title` ja `desc` rakennettiin ENNEN
    `optimal_xi_proven()`-haaraa, joten hedge oli vain nakyvassa copyssa ja
    <head> sanoi hedgaamatta "The highest-scoring XI" / "best 100.0m FPL
    squad" kuudessa kohdassa. Se on Villen saman paivan loydos peilikuvana.
    <head> on julkisempi kuin runko: linkkiesikatselut ja hakukoneet lainaavat
    juuri sita."""
    from src.models.fpl_rate_team import optimal_xi_proven
    html = _render([3, 4, 5, 6, 7, 8])
    head = html.split("<body", 1)[0].lower()
    if optimal_xi_proven():
        return  # todistettu optimi saa sanoa sen
    osumat = [k for k in OPTIMISMI if k in head]
    assert not osumat, (
        "hedgaamaton optimaalisuusvaite <head>:ssa: %s" % osumat)


def test_hedgaamaton_vaite_ei_paase_nakyvaan_copyyn():
    from src.models.fpl_rate_team import optimal_xi_proven
    if optimal_xi_proven():
        return
    nakyva = _nakyva(_render([3, 4, 5, 6, 7, 8])).lower()
    osumat = [k for k in OPTIMISMI if k in nakyva]
    assert not osumat, osumat


def test_kontrolli_sanalista_ei_ole_tyhja():
    """Portin sanalista vanhenee: varmista etta se osuu johonkin kun vaite
    ON sallittu (fikstuurilla haku on todistettu)."""
    html = _render([3, 4, 5, 6, 7, 8])
    from src.models.fpl_rate_team import optimal_xi_proven
    if optimal_xi_proven():
        yhdessa = (html.split("<body", 1)[0] + _nakyva(html)).lower()
        assert any(k in yhdessa for k in OPTIMISMI), (
            "todistetulla optimilla sivun PITAA sanoa se")


def test_llms_txt_ei_kanna_hedgaamatonta_vaitetta():
    """llms.txt on se pinta jota vastausmoottorit lainaavat sanatarkasti,
    eli vaara muotoilu elaa siella pisimpaan ja siteerattuna."""
    rivi = [r for r in (ROOT / "llms.txt").read_text(
        encoding="utf-8").splitlines() if "/fpl/model-xi" in r]
    assert rivi, "llms.txt:sta puuttuu model-xi-rivi"
    teksti = rivi[0].lower()
    for kielletty in ("highest expected-points squad", "this is a budget optimum",
                      "best possible"):
        assert kielletty not in teksti, kielletty
    assert "not the team goaliq plays" in teksti


def test_jakokortti_lukee_optimal_provenin():
    """career.html kirjoitti "% of the best possible budget squad" lukematta
    `optimal_proven`ia, kun SPA luki sen oikein. Sama vaite kahta polkua ja
    vain toinen portin takana."""
    kortti = (ROOT / "career.html").read_text(encoding="utf-8")
    assert "optimal_proven" in kortti, "jakokortti ei lue porttia"
    assert "beats_benchmark" in kortti
    # ...ja teaser valittaa lipun eteenpain, muuten kortti ei voi lukea sita
    teaser = (ROOT / "src" / "models" / "fpl_career.py").read_text(
        encoding="utf-8")
    i = teaser.index("def _model_teaser")
    lohko = teaser[i:i + 2500]
    for kentta in ("optimal_proven", "beats_benchmark", "horizon_gw"):
        assert f'"{kentta}"' in lohko, kentta

