"""Wildcard-suunnitelma: ajoitus, perustelu ja pitkan aikavalin erillisyys.

🔴 TAMA TIEDOSTO ON OLEMASSA KAHDEN OMAN VIRHEENI TAKIA (25.8.2026).

1. `chip-ev` vertasi eri pituisia ikkunoita ja kutsui maksimia parhaaksi
   kierrokseksi. Villen rivilla luvut olivat 38,00 · 33,55 · 25,71 · 20,22 ·
   15,95 · 10,37 — monotoninen lasku joka nayttaa ajoitussignaalilta mutta on
   ikkunan pituus.
2. Korjasin sen normalisoimalla per kierros, ja ajo valitsi **GW7:n** eli
   myohaisimman. Se on peilikuva samasta viasta: per-kierros-luku ei nae etta
   odottaminen HEITTAA POIS aiemmat kierrokset. Vain ajo naytti sen.

Oikea kehys: yhteinen arviointi-ikkuna, jossa liikkuu vain kytkentahetki.
`test_myohempi_kierros_ei_voita_pelkalla_per_gw_luvulla` lukitsee tuon.
"""
from __future__ import annotations

import pytest

from src.models import fpl_wildcard as wc


# ---------------------------------------------------------------------------
# Apurit
# ---------------------------------------------------------------------------
def _p(pid, xp_per_gw, pos=3, price=50, club=1, gws=(2, 3, 4), **kw):
    """Pelaaja jonka xP on vakio joka kierroksella, ellei `xp_map` anneta."""
    kartta = kw.pop("xp_map", None)
    return {
        "id": pid, "web_name": f"P{pid}", "element_type": pos, "price": price,
        "club": club, "team_short": "AAA",
        "gameweeks": [{"gw": g, "xp": (kartta or {}).get(g, xp_per_gw)}
                      for g in gws],
        **kw,
    }


def _xi_fn(squad, key):
    """Testin XI-valitsin: 11 parasta. Muodostelmasaannot testataan
    `fpl_rate_team`-puolella, tama moduuli ei omista niita."""
    return sorted(squad, key=key, reverse=True)[:11]


def _kutsu(squad, uusi_15, gws=(2, 3, 4), fixtures=None, monkeypatch=None,
           mode="entry"):
    """Ajaa `wildcard_plan` niin etta optimoija palauttaa annetun rungon.

    🔴 Optimoija on `fpl_rate_team`:n vastuulla; tama moduuli vastaa
    AJOITUKSESTA ja PERUSTELUSTA. Siksi runko annetaan, jotta testi mittaa
    tarkalleen sita mita tama tiedosto omistaa.
    """
    monkeypatch.setattr(wc, "_optimi", lambda pool, g: {
        "xi": uusi_15[:11], "bench": uusi_15[11:], "proven": True})
    # club-id -> mallinimi. `_rivisto` jakaa klubit 1..6, ja fixturet kayttavat
    # nimia "A"/"B", joten kartta on oltava tai `long_view` jaa tyhjaksi.
    kartta = {i: nimi for i, nimi in enumerate("ABCDEF", start=1)}
    return wc.wildcard_plan(squad, list(squad) + list(uusi_15), list(gws),
                            fixtures or [], kartta, _xi_fn, mode)


def _rivisto(alku, xp, gws=(2, 3, 4), **kw):
    """15 pelaajaa laillisilla positioilla."""
    pos = [1] * 2 + [2] * 5 + [3] * 5 + [4] * 3
    return [_p(alku + i, xp, pos=pos[i], club=1 + (i % 6), gws=gws, **kw)
            for i in range(15)]


# ---------------------------------------------------------------------------
# 1. Ajoitus
# ---------------------------------------------------------------------------
def test_myohempi_kierros_ei_voita_pelkalla_per_gw_luvulla(monkeypatch):
    """🔴 TAMA ON SE VIRHE JONKA TEIN. Rakennetaan runko joka on hieman
    parempi joka kierroksella mutta SELVASTI parempi viimeisella. Per kierros
    viimeinen ikkuna (1 kierros) nayttaa parhaalta; ajoituspaatoksena se on
    vaara, koska odottaminen heittaa pois kaksi aiempaa kierrosta.
    """
    vanha = _rivisto(1, 1.0)
    # uusi: +1.0 GW2, +1.0 GW3, +5.0 GW4
    uusi = _rivisto(100, 0.0, )
    for p in uusi:
        p["gameweeks"] = [{"gw": 2, "xp": 2.0}, {"gw": 3, "xp": 2.0},
                          {"gw": 4, "xp": 6.0}]
    plan = _kutsu(vanha, uusi, monkeypatch=monkeypatch)

    per_gw = {k["gw"]: k["ev_per_gw"] for k in plan["candidates"]}
    assert per_gw[4] > per_gw[2], "esiehto: per-gw suosisi viimeista"
    assert plan["gw"] == 2, (
        "ajoitus on ratkaistava YHTEISELLA ikkunalla — per-kierros-luku ei nae "
        f"etta odottaminen heittaa pois aiemmat kierrokset (sai GW{plan['gw']})")


def test_kaikki_kandidaatit_kertovat_ikkunansa_pituuden(monkeypatch):
    """Ilman `window_gws`-kenttaa lukija vertaisi eri pituisia summia — se oli
    alkuperainen vika."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 2.0), monkeypatch=monkeypatch)
    pituudet = {k["gw"]: k["window_gws"] for k in plan["candidates"]}
    assert pituudet == {2: 3, 3: 2, 4: 1}


def test_kytkentahetki_vaikuttaa_jokaiseen_riviin(monkeypatch):
    """🔴 MUTAATIO LAPAISI ILMAN TATA. Jos `ev` summattaisiin koko horisontin
    yli kytkentahetkesta riippumatta, JOKAINEN rivi saisi saman luvun ja `max`
    palauttaisi silti GW2:n — oikea vastaus vaarasta syysta, ja rivien luvut
    olisivat vaarin. Kun uusi runko on parempi joka kierroksella, myohempi
    kytkenta kerryttaa AIDOSTI vahemman.
    """
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    evt = [k["ev_total"] for k in plan["candidates"]]
    assert len(set(evt)) == len(evt), (
        f"kytkentahetki ei vaikuta riveihin: {evt}")
    assert evt == sorted(evt, reverse=True), evt


def test_ev_mitataan_oman_optimin_eika_nykyisen_xin_yli(monkeypatch):
    """🔴 Wildcardia ei saa kehua hyodysta jonka saa pelkalla
    penkkijarjestyksella. Vertailukohta on rungon OMA paras XI."""
    vanha = _rivisto(1, 1.0)
    # yksi vanhan pelaaja on eritain hyva -> oma optimi nostaa hanet XI:hin
    vanha[14]["gameweeks"] = [{"gw": g, "xp": 9.0} for g in (2, 3, 4)]
    plan = _kutsu(vanha, _rivisto(100, 1.0), monkeypatch=monkeypatch)
    # 🔴 ASSERT OLI LIIAN LOPSA JA MUTAATIO LAPAISI SEN. "<= 0.01" hyvaksyi
    # myos arvon 0.0, jonka mutaatio (vertaa `rivisto[:11]`:aan) tuottaa. Oikea
    # odotus on SELVASTI negatiivinen: vanhan rungon oma optimi nostaa tahden
    # (9.0) XI:hin, joten uusi tasainen runko HAVIAA sille.
    assert plan["ev_total"] < -1.0, (
        "vanhan rungon oma optimi jai huomiotta -> hyoty yliarvioitui "
        f"(ev_total={plan['ev_total']})")


# ---------------------------------------------------------------------------
# 2. Suositus vs pito
# ---------------------------------------------------------------------------
def test_pieni_hyoty_ei_polta_chippia(monkeypatch):
    """Wildcard on kertakaytto. Alle kynnyksen -> `hold`, ja se sanotaan."""
    plan = _kutsu(_rivisto(1, 3.0), _rivisto(100, 3.1),
                  monkeypatch=monkeypatch)
    assert plan["recommend"] is False
    koodit = [r["code"] for r in plan["reasons"]]
    assert "hold" in koodit and "ev" not in koodit


def test_selva_hyoty_suositellaan(monkeypatch):
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    assert plan["recommend"] is True
    koodit = [r["code"] for r in plan["reasons"]]
    assert "ev" in koodit and "hold" not in koodit


def test_kynnys_on_per_kierros_eika_riipu_horisontin_pituudesta(monkeypatch):
    """🔴 "Onko runko tarpeeksi parempi" ei saa muuttua siita montako kierrosta
    sattuu olemaan jaljella — muuten sama joukkue olisi suositus elokuussa ja
    pito toukokuussa."""
    lyhyt = _kutsu(_rivisto(1, 3.0, gws=(2,)), _rivisto(100, 3.1, gws=(2,)),
                   gws=(2,), monkeypatch=monkeypatch)
    pitka = _kutsu(_rivisto(1, 3.0), _rivisto(100, 3.1),
                   monkeypatch=monkeypatch)
    assert lyhyt["recommend"] == pitka["recommend"] is False


# ---------------------------------------------------------------------------
# 3. Perustelut
# ---------------------------------------------------------------------------
def test_kustannus_sanotaan_ennen_hyotya(monkeypatch):
    """🔴 Paneeli joka avaa omalla voitollaan on mainos. Vaihtuvien maara on
    kustannus ja se tulee ensin."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    koodit = [r["code"] for r in plan["reasons"]]
    assert koodit.index("cost") < koodit.index("ev")


def test_jokainen_perustelu_kantaa_numeron(monkeypatch):
    """Lause ilman lukua on mielipide. Poikkeus: `timing` on menetelmaselite."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    for r in plan["reasons"]:
        if r["code"] == "timing":
            continue
        assert any(ch.isdigit() for ch in r["text"]), r


def test_ajoituslause_kertoo_ettei_malli_hinnoittele_tulevaa(monkeypatch):
    """Malli EI nae tulevaa tietoa, ja se sanotaan aareen — muuten tyokalu
    nayttaisi "loytaneen" parhaan viikon."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    t = next(r["text"] for r in plan["reasons"] if r["code"] == "timing")
    assert "hasn't happened yet" in t and "same" in t


def test_ajoituslause_ei_vaita_ettei_odottaminen_voi_tuottaa(monkeypatch):
    """🔴 LAUSE VALEHTELI, JA JULKAISUPORTTI RAKENSI VASTAESIMERKIN.

    Vanha teksti sanoi EHDOITTA "Waiting can only lose points here". Suositus on
    `max(ev_total)`, joten jos uusi runko on jollain kierroksella nykyista
    HUONOMPI, odottaminen KASVATTAA hyotya. Ajettu vastaesimerkki:

        GW2 ev 33,00 · GW3 ev 66,00 · GW4 ev 33,00  -> valinta GW3

    eli paneeli olisi tulostanut "Play it in GW3", taulukon jossa odottaminen
    tuotti +33, ja niiden viereen lauseen ettei odottaminen voi tuottaa. Sama
    nakyma kumosi itsensa.

    🔴 Ja edellinen testi meni tasta lapi: se tarkisti vain etta merkkijono
    "does not have yet" on mukana. Portti loysi sen, testi ei.
    """
    vanha = _rivisto(1, 0.0, gws=(2, 3, 4))
    for q in vanha:                       # vanha on PAREMPI GW2:lla
        q["gameweeks"] = [{"gw": 2, "xp": 5.0}, {"gw": 3, "xp": 1.0},
                          {"gw": 4, "xp": 1.0}]
    uusi = _rivisto(100, 0.0, gws=(2, 3, 4))
    for q in uusi:
        q["gameweeks"] = [{"gw": 2, "xp": 2.0}, {"gw": 3, "xp": 4.0},
                          {"gw": 4, "xp": 4.0}]
    plan = _kutsu(vanha, uusi, monkeypatch=monkeypatch)

    evt = {k["gw"]: k["ev_total"] for k in plan["candidates"]}
    assert evt[3] > evt[2], "esiehto: odottamisen PITAA tuottaa tassa datassa"
    assert plan["gw"] == 3

    t = next(r["text"] for r in plan["reasons"] if r["code"] == "timing")
    assert "can only lose" not in t, (
        "universaali vaite odottamisesta on epatosi tassa datassa: " + t)
    # ...ja lause kertoo MITA tassa datassa tapahtui. 🔴 "taken together":
    # ehto on SUMMA, ja kierroskohtaiselta kuulostava sanamuoto olisi taas
    # kumottavissa viereisesta taulukosta.
    assert "GW3" in t and "taken together" in t


def test_ajoituslause_ei_vaita_taydellisyytta_kun_kierros_on_tappiollinen(monkeypatch):
    """🔴 KORJASIN B1:N KERRAN JA LOIN SAMAN VIAN UUDESSA MUODOSSA.

    Toinen versio haarautti ehdolla `plan["gw"] == aikaisin` ja sanoi silloin
    "the rebuilt squad is ahead in every round". Ehto EI implikoi sita:
    aikaisin voittaa kun SUFFIKSISUMMAT pysyvat pienempina, ja yksittainen
    kierros saa silti olla tappiollinen.

        deltat   GW2 +33,00 · GW3 -11,00 · GW4 +22,00  -> valinta GW2
        taulukko GW2  44,00 · GW3  11,00 · GW4  22,00

    Myohempi rivi ei voi olla korkeampi ellei jokin kierros ole tappiollinen,
    eli lukija kumoaa vaitteen suoraan viereisesta taulukosta.

    🔴 Ja OMA edellinen testini rakensi `plan["gw"] == 3`, eli ajoi VAIN
    else-haaran. If-haaraa ei testattu negatiivisella deltalla kertaakaan.
    """
    vanha = _rivisto(1, 0.0)
    for q in vanha:
        q["gameweeks"] = [{"gw": 2, "xp": 1.0}, {"gw": 3, "xp": 5.0},
                          {"gw": 4, "xp": 1.0}]
    uusi = _rivisto(100, 0.0)
    for q in uusi:
        q["gameweeks"] = [{"gw": 2, "xp": 4.0}, {"gw": 3, "xp": 4.0},
                          {"gw": 4, "xp": 3.0}]
    plan = _kutsu(vanha, uusi, monkeypatch=monkeypatch)

    evt = {k["gw"]: k["ev_total"] for k in plan["candidates"]}
    assert plan["gw"] == 2, "esiehto: aikaisin voittaa"
    assert evt[4] > evt[3], (
        "esiehto: myohempi rivi on korkeampi, eli jokin kierros on tappiollinen")

    t = next(r["text"] for r in plan["reasons"] if r["code"] == "timing")
    assert "in every round" not in t, (
        "vaite taydellisyydesta on kumottavissa viereisesta taulukosta: " + t)
    assert "even though" in t and "1 of those rounds" in t


def test_ajoituslause_saa_vaittaa_taydellisyytta_kun_se_on_totta(monkeypatch):
    """Vastapari: kun jokainen delta on positiivinen, vahvempi lause on tosi ja
    se saa sanoa niin. Ilman tata korjaus voisi vaientaa lauseen aina."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    t = next(r["text"] for r in plan["reasons"] if r["code"] == "timing")
    assert "ahead in every round of the window" in t


def test_ajoituslause_ei_paaty_koristeelliseen_yhteenvetoon(monkeypatch):
    """🔴 Yhteenvetolause lopussa on AI-tunnusmerkki, ja edellinen virke sanoi
    jo saman. Lause paattyy nyt lukuun."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    t = next(r["text"] for r in plan["reasons"] if r["code"] == "timing")
    assert t.rstrip().endswith("aren't in this number.")
    assert "the one thing" not in t


def test_copy_ei_omista_mallin_rivistoa_lukijalle(monkeypatch):
    """🔴 "your 15" ilman entry-ID:ta on vaite jota lukija ei voi tarkistaa:
    rivisto on silloin MALLIN oma. Mitattu ilmaispinnalta 25.8."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch, mode="model_xi")
    teksti = " ".join(r["text"] for r in plan["reasons"])
    assert "your 15" not in teksti and "your best lineup" not in teksti
    assert "the model's own 15" in teksti


def test_tautologinen_nollatulos_ei_ole_tulos(monkeypatch):
    """🔴 Ilman entrya mallin optimia verrataan mallin omaan optimiin: 0
    muutosta, 0.0 pistetta, "hold". Se ei ole vastaus vaan sama luku kahdesti,
    ja ensikavijan ilmaiskokemus olisi paneeli joka sanoo ettei se muuta
    mitaan. Kerrotaan mika puuttuu."""
    sama = _rivisto(1, 3.0)
    plan = _kutsu(sama, list(sama), monkeypatch=monkeypatch, mode="model_xi")
    assert plan["available"] is False
    assert "team ID" in plan["note"]


def test_varaus_sanotaan_kerran_ei_kolmesti(monkeypatch):
    """🔴 25.8 sama varaus oli KOLMESSA paikassa samassa nakymassa (long_view-
    lause, `long_view.note` ja meta.notes). Toistettu varaus on AI-tunnusmerkki
    ja se laimentaa itseaan."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  fixtures=[_fixture(5, "A", "B")], monkeypatch=monkeypatch)
    t = next(r["text"] for r in plan["reasons"] if r["code"] == "long_view")
    assert "not xP" not in t, "varaus toistui perustelulauseessa"
    assert "note" not in (plan["long_view"] or {}), (
        "long_view kantaa yha oman varauskopionsa")


def test_liputetut_pelaajat_lasketaan_nykyisesta_rungosta(monkeypatch):
    vanha = _rivisto(1, 1.0)
    vanha[0]["chance_next"] = 75
    vanha[1]["chance_next"] = 0
    vanha[2]["chance_next"] = 100          # ei lippu
    plan = _kutsu(vanha, _rivisto(100, 6.0), monkeypatch=monkeypatch)
    t = next(r["text"] for r in plan["reasons"] if r["code"] == "flags")
    assert t.startswith("2 of your current 15")


def test_ulos_ja_sisaan_jarjestetaan_heikoimmasta_ja_vahvimmasta(monkeypatch):
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    assert plan["out"] == sorted(plan["out"], key=lambda r: r["xp_per_gw"])
    assert plan["in"] == sorted(plan["in"], key=lambda r: -r["xp_per_gw"])


# ---------------------------------------------------------------------------
# 4. Pitkan aikavalin nakyma on ERI PERUSTA
# ---------------------------------------------------------------------------
def _fixture(gw, koti, vieras, att_h=3, att_a=3, def_h=3, def_a=3):
    return {"gameweek": gw, "home": koti, "away": vieras,
            "home_model": koti, "away_model": vieras,
            "att_fdr_home": att_h, "att_fdr_away": att_a,
            "def_fdr_home": def_h, "def_fdr_away": def_a}


def test_fixture_data_ei_muuta_xp_lukua(monkeypatch):
    """🔴 KOKO LOHKON PERUSTE. Joukkuetason vaikeus ja pelaajatason xP ovat eri
    suureita; niiden summaaminen tekisi luvusta sellaisen jota kukaan ei voi
    tarkistaa. Fixtureiden lisaaminen ei saa liikuttaa `ev_total`ia lainkaan.
    """
    ilman = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                   monkeypatch=monkeypatch)
    kanssa = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                    fixtures=[_fixture(5, "A", "B"), _fixture(6, "B", "A")],
                    monkeypatch=monkeypatch)
    assert ilman["ev_total"] == kanssa["ev_total"]
    assert kanssa["basis"] == "player_xp"


def test_ev_total_on_tasan_xp_erotus(monkeypatch):
    """🔴 INVARIANSSI EI RIITA. Edellinen testi vertaa kahta ajoa keskenaan,
    joten VAKIOSIIRTYMA lapaisi sen: mutaatio `ev + 5.0` nakyi molemmissa ja
    ero pysyi nollana. Siksi luku lasketaan tassa kasin.

    Vanha 15 x 1.0/GW -> paras XI = 11.0/GW. Uusi 15 x 6.0/GW -> 66.0/GW.
    Kolme kierrosta, kytkenta GW2 -> (66.0 - 11.0) * 3 = 165.0.
    """
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    assert plan["ev_total"] == pytest.approx(165.0), (
        "ev_total ei ole enaa pelkka xP-erotus — onko siihen lisatty jotain "
        "muuta perustaa?")


def test_long_view_kattaa_vain_horisontin_ULKOPUOLISET_kierrokset(monkeypatch):
    """Horisontin sisalla on pelaajatason xP. Sen toistaminen karkeammalla
    joukkuemittarilla olisi sama luku kahdesti eri tarkkuudella."""
    fx = [_fixture(g, "A", "B") for g in (2, 3, 4, 5, 6, 7)]
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0), fixtures=fx,
                  monkeypatch=monkeypatch)
    assert plan["long_view"]["gws"] == [5, 6, 7], plan["long_view"]


def test_ilman_fixtureita_ei_keksita_long_viewta(monkeypatch):
    """Puuttuva data -> lohko puuttuu ja lause jaa pois. Nolla tai arvaus
    olisi vaite jota ei ole mitattu."""
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    assert plan["long_view"] is None
    assert "long_view" not in [r["code"] for r in plan["reasons"]]


def test_team_outlook_laskee_tuplakierroksen_kahdeksi_otteluksi():
    """🔴 Pelkka keskiarvo piilottaisi tuplakierroksen taysin, ja tuplakierros
    on nimenomaan se syy jonka takia chipin ajoitusta katsotaan."""
    fx = [_fixture(8, "A", "B"), _fixture(8, "C", "A")]
    o = wc.team_outlook(fx, {8})
    assert o["A"]["fixtures"] == 2
    assert o["B"]["fixtures"] == 1


def test_team_outlook_ohittaa_rivit_joilta_puuttuu_vaikeus():
    """Puuttuva FDR ei saa muuttua nollaksi: nolla olisi "helpoin mahdollinen"."""
    fx = [{"gameweek": 8, "home_model": "A", "away_model": "B"}]
    assert wc.team_outlook(fx, {8}) == {}


# ---------------------------------------------------------------------------
# 5. Nimikartan aukkovahti
# ---------------------------------------------------------------------------
def test_nimikartta_kattaa_nykyiset_nimet():
    mallinimet = {"Ipswich", "Manchester City", "Manchester United",
                  "Newcastle United", "Nottingham Forest", "Tottenham",
                  "Arsenal"}
    tiimit = [{"name": n} for n in
              ("Ipswich Town", "Man City", "Man Utd", "Newcastle",
               "Nott'm Forest", "Spurs", "Arsenal")]
    assert wc.nimikartta_aukot(tiimit, mallinimet) == []


def test_kartoittamaton_nimi_loytyy():
    """🔴 Ilman tata uuden kauden uudelleennimeaminen pudottaisi joukkueen
    pitkasta nakymasta HILJAA, ja pudonnut pelaaja nayttaisi vain silta ettei
    hanella ole fixture-lukua."""
    aukot = wc.nimikartta_aukot([{"name": "Wrexham AFC"}], {"Arsenal"})
    assert aukot and "Wrexham" in aukot[0]


# ---------------------------------------------------------------------------
# 6. Reunatapaukset
# ---------------------------------------------------------------------------
def test_tyhja_horisontti_ei_kaadu():
    out = wc.wildcard_plan([], [], [], [], {}, _xi_fn)
    assert out["available"] is False and out["note"]


def test_optimoijan_epaonnistuminen_kerrotaan(monkeypatch):
    """Runkoa ei saada -> `available: False` eika puolikas suunnitelma."""
    monkeypatch.setattr(wc, "_optimi", lambda pool, g: None)
    out = wc.wildcard_plan(_rivisto(1, 1.0), _rivisto(1, 1.0), [2, 3],
                           [], {}, _xi_fn)
    assert out["available"] is False


@pytest.mark.parametrize("kentta", ["gw", "ev_total", "ev_per_gw",
                                    "window_gws", "basis", "recommend"])
def test_vastaus_kantaa_paatoskentat(kentta, monkeypatch):
    plan = _kutsu(_rivisto(1, 1.0), _rivisto(100, 6.0),
                  monkeypatch=monkeypatch)
    assert kentta in plan


# ---------------------------------------------------------------------------
# 7. Ilmaispinnan maski
# ---------------------------------------------------------------------------
def test_ilmaispinta_ei_saa_lukua_ilman_sen_ehtoa():
    """🔴 Maski pudotti aluksi `timing`-lauseen, jolloin ilmaispinta nayttti
    EV-luvun ILMAN menetelmavarausta. Varaus joka on eri pinnalla kuin luku ei
    ole kerrottu. Lista tarkistetaan koodista, jotta kuollut avain ei voi
    vaientaa lausetta aanettomasti.
    """
    from api.fantasy_edge import FREE_WILDCARD_REASONS
    assert "timing" in FREE_WILDCARD_REASONS
    assert "ev" in FREE_WILDCARD_REASONS


def test_ilmaislistan_koodit_ovat_oikeasti_olemassa(monkeypatch):
    """Kuollut avain listassa on hiljainen vaientaja: se ei kaada mitaan, se
    vain jattaa lauseen pois. (`window` oli tallainen 25.8.)"""
    from api.fantasy_edge import FREE_WILDCARD_REASONS
    kaikki = set()
    for suosita in (True, False):
        vanha = _rivisto(1, 1.0)
        vanha[0]["chance_next"] = 75      # jotta `flags` syntyy
        plan = _kutsu(vanha, _rivisto(100, 6.0 if suosita else 1.05),
                      fixtures=[_fixture(5, "A", "B")],
                      monkeypatch=monkeypatch)
        kaikki |= {r["code"] for r in plan["reasons"]}
    tuntemattomat = FREE_WILDCARD_REASONS - kaikki
    assert not tuntemattomat, (
        f"ilmaislista viittaa koodeihin joita generaattori ei tuota: "
        f"{sorted(tuntemattomat)}")
