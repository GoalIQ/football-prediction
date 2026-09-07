"""THE MODEL SAYS: johdetut lauseet, ei vapaamuotoisia (25.8.2026).

🔴 Nama merkkijonot ovat JULKISTA ENGLANNINKIELISTA TEKSTIA jotka renderoidaan
kayttajalle, eli niita koskee sama portti kuin sivucopya.
"""
from __future__ import annotations

import re

from src.models import fpl_model_says as MS


def _rev(proj, act, cap=None, worst=None, best=None):
    return {"projected": proj, "actual": act, "captain": cap,
            "worst_call": worst, "best_call": best}


def _p(name, proj, act):
    return {"web_name": name, "projected": proj, "actual": act,
            "diff": round(act - proj, 2)}


# ---------------------------------------------------------------------------
# Jokainen lause kantaa lukunsa
# ---------------------------------------------------------------------------
def test_jokainen_lause_sisaltaa_numeron():
    """🔴 Lukija voi verrata lausetta viereiseen numeroon vain jos luku on
    lauseessa. Lause ilman lukua on tulkinta eika havainto."""
    rivit = MS.review_lines(_rev(55.6, 41, cap=_p("Bruno", 11.4, 4),
                                 worst=_p("Bruno", 11.4, 4),
                                 best=_p("Tav", 3.7, 10)))
    rivit += MS.flag_lines(
        {"availability": [{"web_name": "A", "chance_next": 75}],
         "price": [{"web_name": "B", "direction": "rise",
                    "progress_pct": 68, "eta_days": 2}]}, 2)
    assert rivit
    for r in rivit:
        assert re.search(r"\d", r["text"]), r


def test_alisuoritus_sanotaan_yhta_suoraan_kuin_ylisuoritus():
    ali = MS.review_lines(_rev(55.6, 41))[0]
    yli = MS.review_lines(_rev(41.0, 55))[0]
    assert ali["code"] == "review.total.under"
    assert yli["code"] == "review.total.over"
    assert "short" in ali["text"]
    assert "41" in ali["text"] and "55.6" in ali["text"]


def test_tasapeli_ei_ole_voitto_eika_tappio():
    r = MS.review_lines(_rev(50.0, 50.5))[0]
    assert r["code"] == "review.total.level"


# ---------------------------------------------------------------------------
# Huti ennen osumaa
# ---------------------------------------------------------------------------
def test_mallin_huti_tulee_ennen_mallin_osumaa():
    """🔴 Paneeli joka avaa omalla onnistumisellaan on mainos. Jarjestys on
    tarkoituksellinen."""
    rivit = MS.review_lines(_rev(55.6, 41,
                                 worst=_p("Bruno", 11.4, 4),
                                 best=_p("Tav", 3.7, 10)))
    koodit = [r["code"] for r in rivit]
    assert koodit.index("review.worst") < koodit.index("review.best")


def test_huti_lause_nimeaa_subjektin():
    r = [x for x in MS.review_lines(_rev(50, 40, best=_p("Tav", 3.7, 10)))
         if x["code"] == "review.best"][0]
    assert r["text"].startswith("The model's biggest underestimate"), r["text"]


def test_positiivinen_diff_ei_paady_worst_calliksi():
    """Jos malli ei ollut yliarvioinut ketaan, huti-lausetta ei ole."""
    rivit = MS.review_lines(_rev(50, 60, worst=_p("X", 3.0, 5)))
    assert not any(r["code"] == "review.worst" for r in rivit)


# ---------------------------------------------------------------------------
# Hintamuutos on ennuste, ei tapahtuma
# ---------------------------------------------------------------------------
# 🔴 Varmuutta vaittavat verbit. Lista eika yksi merkkijono: ensimmainen versio
# tarkisti vain "will rise", ja mutaatio joka vaihtoi sen muotoon "will change"
# meni lapi. Portti oli sokea sille luokalle jota se vahtii.
VARMUUSVERBIT = ("will ", "is going to", "guaranteed", "definitely",
                 "certain to", "changes tonight", "rises tonight",
                 "falls tonight")


def test_hintalause_ei_vaita_muutoksen_tapahtuvan():
    """Hintamuutos on ENNUSTE eika tapahtuma, ja `progress_pct` on edistyma
    kynnysta kohti eika varmuus."""
    for eta in (0, 1, 3, None):
        r = MS.flag_lines({"price": [{"web_name": "X", "direction": "rise",
                                      "progress_pct": 68,
                                      "eta_days": eta}]})[0]
        assert "of the way to" in r["text"], r["text"]
        matala = r["text"].lower()
        for v in VARMUUSVERBIT:
            assert v not in matala, (eta, v, r["text"])


AIKASANAT = ("tonight", "today", "within a day", "tomorrow")


def test_aikavaite_esiintyy_vain_kun_data_tukee_sita():
    """🔴 Mutaatio joka liitti "tonight":in KOLMEN PAIVAN etaan meni lapi
    aiemmasta portista. Aikasana on sidottava `eta_days`:iin."""
    for eta, saa_olla in ((0, True), (0.5, True), (1, True),
                          (2, False), (3, False), (None, False)):
        r = MS.flag_lines({"price": [{"web_name": "X", "direction": "rise",
                                      "progress_pct": 68,
                                      "eta_days": eta}]})[0]
        matala = r["text"].lower()
        loytyi = any(a in matala for a in AIKASANAT)
        assert loytyi == saa_olla, (eta, r["text"])


def test_aikavaite_on_ehdollinen():
    """Ajankohta koskee tapahtumaa joka ei ole varma, joten ehto sanotaan."""
    r = MS.flag_lines({"price": [{"web_name": "X", "direction": "rise",
                                  "progress_pct": 68, "eta_days": 0}]})[0]
    assert "if it gets there" in r["text"], r["text"]


def test_mikaan_lause_ei_lupaa_varmuutta():
    """Sama vahti KAIKILLE lauseille, ei vain hintariville."""
    kaikki = (MS.review_lines(_rev(55.6, 41, cap=_p("B", 11.4, 4),
                                   worst=_p("B", 11.4, 4),
                                   best=_p("T", 3.7, 10)))
              + MS.flag_lines({"availability": [{"web_name": "A",
                                                 "chance_next": 75}],
                               "price": [{"web_name": "B", "direction": "fall",
                                          "progress_pct": 90,
                                          "eta_days": 0}]}, 2)
              + MS.plan_lines([{"net_ev_vs_hold": 5.2, "hits_taken": 1},
                               {"net_ev_vs_hold": 1.0, "hits_taken": 0}]))
    for r in kaikki:
        matala = r["text"].lower()
        for v in VARMUUSVERBIT:
            assert v not in matala, (r["code"], v, r["text"])


def test_lippujen_maara_on_listan_pituus_ei_arvio():
    liput = [{"web_name": f"P{i}", "chance_next": 50} for i in range(5)]
    r = MS.flag_lines({"availability": liput}, 3)[0]
    assert "5 flags" in r["text"]
    assert "GW3" in r["text"]
    yksi = MS.flag_lines({"availability": liput[:1]}, 3)[0]
    assert "one flag" in yksi["text"], "yksikkomuoto"


# ---------------------------------------------------------------------------
# Suunnitelmat: haviaja nakyy
# ---------------------------------------------------------------------------
def test_haviaja_saa_oman_lauseensa():
    """🔴 Designin oma saanto 26.7: argumentoi haviavaa vastaan, ala piilota
    sita."""
    rivit = MS.plan_lines([{"net_ev_vs_hold": 5.2, "hits_taken": 0},
                           {"net_ev_vs_hold": 3.0, "hits_taken": 0},
                           {"net_ev_vs_hold": 1.1, "hits_taken": 0}])
    koodit = [r["code"] for r in rivit]
    assert "plans.best" in koodit and "plans.worst" in koodit
    worst = [r for r in rivit if r["code"] == "plans.worst"][0]
    assert "4.1" in worst["text"], worst["text"]
    # 🔴 "of the three" oli kovakoodattu vaikka vartija on len > 1.
    assert "three" not in worst["text"], worst["text"]


def test_hold_on_tulos_eika_puuttuva_suositus():
    rivit = MS.plan_lines([{"net_ev_vs_hold": -1.0, "hits_taken": 0}])
    assert rivit[0]["code"] == "plans.hold"
    assert "No move clears the hold" in rivit[0]["text"]


def test_hit_mainitaan_pisteina():
    r = MS.plan_lines([{"net_ev_vs_hold": 6.0, "hits_taken": 2}])[0]
    assert "8 point hit" in r["text"], r["text"]


def test_tyhja_syote_ei_kaada():
    assert MS.review_lines(None) == []
    assert MS.flag_lines(None) == []
    assert MS.plan_lines(None) == []
    assert MS.plan_lines([{"net_ev_vs_hold": None}]) == []


# ---------------------------------------------------------------------------
# Kovat saannot
# ---------------------------------------------------------------------------
def test_ei_em_dashia_eika_kaarevia_merkkeja():
    kaikki = (MS.review_lines(_rev(55.6, 41, cap=_p("B", 11.4, 4),
                                   worst=_p("B", 11.4, 4),
                                   best=_p("T", 3.7, 10)))
              + MS.flag_lines({"availability": [{"web_name": "A",
                                                 "chance_next": 75}],
                               "price": [{"web_name": "B", "direction": "fall",
                                          "progress_pct": 90,
                                          "eta_days": 0}]}, 2)
              + MS.plan_lines([{"net_ev_vs_hold": 5.2, "hits_taken": 1},
                               {"net_ev_vs_hold": 1.0, "hits_taken": 0}],
                              baseline_xp=158.4))
    for r in kaikki:
        for kielletty in ("—", "–", "‘", "’",
                          "“", "”"):
            assert kielletty not in r["text"], (r["code"], r["text"])


def test_kahdella_suunnitelmalla_ei_vaiteta_kolmea():
    """🔴 Mitattu: `len(kelpo) > 1` paastaa kaksi suunnitelmaa lapi, mutta
    teksti sanoi "The weakest of the three". Superlatiivi jota ei ole
    mitattu."""
    rivit = MS.plan_lines([{"net_ev_vs_hold": 5.0, "hits_taken": 0},
                           {"net_ev_vs_hold": 2.0, "hits_taken": 0}])
    worst = [r for r in rivit if r["code"] == "plans.worst"][0]
    assert "three" not in worst["text"].lower(), worst["text"]
    # `_pts` pudottaa turhat desimaalit: 3.0 -> "3". Testi oletti "3.0" ja oli
    # itse vaarassa, ei koodi.
    # F5 (7.9): luku nayttaa desimaalin, koska PlanChains-paneeli renderoi
    # saman luvun `toFixed(1)`:lla (`PlanChains.svelte:335`). Vanha odotus
    # ("3 points") oli tasan se puoli erosta joka ei tasmannyt paneeliin.
    assert "3.0 points" in worst["text"], worst["text"]


def test_puuttuva_hintasuunta_ohitetaan_ei_arvata():
    """🔴 `else "fall"` julkaisi NOUSEVAN pelaajan laskevana kun `direction`
    puuttui, ja /api/fantasy/price-watch palauttaa risers-riveilla null."""
    assert MS.flag_lines({"price": [{"web_name": "X", "direction": None,
                                     "progress_pct": 68}]}) == []
    assert MS.flag_lines({"price": [{"web_name": "X", "direction": "sideways",
                                     "progress_pct": 68}]}) == []
    ok = MS.flag_lines({"price": [{"web_name": "X", "direction": "fall",
                                   "progress_pct": 68}]})
    assert len(ok) == 1 and "price fall" in ok[0]["text"]


def test_paneeli_ei_selita_omaa_designperiaatettaan():
    """Ainoa lause joka ei kanna lukua vaan kertoo miksi paneeli on tehty
    nain. Se on ilmeisen perustelemista."""
    kaikki = MS.plan_lines([{"net_ev_vs_hold": 5.0, "hits_taken": 0},
                            {"net_ev_vs_hold": 2.0, "hits_taken": 0}])
    for r in kaikki:
        assert "argue with the model" not in r["text"], r["text"]
        assert "top line" not in r["text"], r["text"]


# ---------------------------------------------------------------------------
# PORTIN 4. KIERROS 7.9.2026 (C5, C6, C9, C10). Kolme korjausta elivat vain
# koodissa ilman fikstuuria, ja portti huomautti siita erikseen.
# ---------------------------------------------------------------------------

def _review(proj_raw: float, act: int) -> dict:
    return {"projected": round(proj_raw, 2), "projected_raw": proj_raw,
            "actual": act, "players": []}


def test_d1_pyoristys_on_sama_saanto_kuin_js_tofixed():
    """🔴 C5:n korjaus EI riittanyt: `f"{x:.1f}"` pyoristaa tasatilanteessa
    PARILLISEEN (half-even), JS `toFixed(1)` SUUREMPAAN (half-up). Portin
    brute force 200 000 kierroksella loysi 2 021 eroavaa tapausta (1,0 %),
    ja summausjarjestys ei aiheuttanut yhtaan - vika oli tasan saannossa.

    Fikstuuri on VIKALUOKASTA eika naytteesta: tasatilanne syntyy aina kun
    raaka summa on tasan x.25 tai x.75, ja se on tavallista koska rivien xp
    on pyoristetty kahteen desimaaliin.
    """
    from src.models.fpl_model_says import _shown_1dp
    # Portin mittaama tapaus: raaka 39.25 -> kortti "39.3", vanha lause "39.2".
    assert _shown_1dp(39.25) == 39.3
    assert _shown_1dp(39.35) == 39.4
    # Half-even olisi antanut naissa parillisen; half-up antaa suuremman.
    for x, odotettu in ((0.25, 0.3), (0.75, 0.8), (1.25, 1.3), (2.75, 2.8),
                        (39.25, 39.3), (54.45, 54.5), (71.15, 71.2)):
        assert _shown_1dp(x) == odotettu, (x, _shown_1dp(x), odotettu)
    # Ja lause kayttaa sita.
    t = MS.review_lines(_review(39.25, 55), rows=11)[0]["text"]
    assert "39.3" in t, t
    assert "15.7" in t and "15.8" not in t, t


def test_d4_lause_ei_vaita_avaavaa_yhdettatoista_bench_boostilla():
    """`kuka = "Your eleven" if rows in (None, 11)` oli fail-open chipin
    suhteen: bench boostilla jossa nelja pickkia putoaa `rows == 11` ja lause
    vaittaa avaavaa XI:ta. Sama vika kuin U4 kortilla."""
    bb = MS.review_lines(_review(60.0, 66), rows=11, chip="bboost")[0]["text"]
    assert "eleven" not in bb, bb
    assert "Your 11 counted picks" in bb, bb
    # Ilman chippia 11 riviä on yha avaava XI.
    assert MS.review_lines(_review(60.0, 66), rows=11)[0]["text"].startswith("Your eleven")
    # Muut chipit eivat muuta joukkoa.
    for chip in ("3xc", "freehit", "wildcard", None):
        t = MS.review_lines(_review(60.0, 66), rows=11, chip=chip)[0]["text"]
        assert t.startswith("Your eleven"), (chip, t)


def test_d2_lause_ei_kayta_samaa_sanamuotoa_kuin_kattavuus():
    """`players_compared` (pickit joilla molemmat luvut) ja `rows` (rivit
    joilla multiplier > 0) ovat ERI joukkoja, mutta molemmat renderoityivat
    sanoilla "both numbers" - 14 ja 10 samalla sanamuodolla samalla ruudulla."""
    t = MS.review_lines(_review(50.0, 50), rows=10)[0]["text"]
    assert "both numbers" not in t, t
    assert "Your 10 counted picks" in t, t


def test_r1_so_far_merkitsee_liikkuvan_luvun_ei_jaadytettya():
    """`so far` kiinnittyi PROJEKTIOON, mutta jaadytetty xP on ainoa luku joka
    EI liiku. Kortti merkitsee liikkuvaksi toteuman (`55 live pts`), joten
    kaksi pintaa merkitsi eri luvun kesken olevaksi."""
    t = MS.review_lines(_review(39.25, 55), rows=11, provisional=True)[0]["text"]
    assert "55 so far" in t, t
    assert "39.3 so far" not in t, t


def test_c5_lause_laskee_erotuksen_raaasta_summasta_kuten_klientti():
    """🔴 KAKSOISPYORISTYS. `projected` pyoristettiin kahteen desimaaliin ja
    lause muotoili siita yhteen, samalla kun klientti laskee saman summan
    RAAKANA ja tekee `toFixed(1)`. Brute force 200 000 summalla loysi 1102
    tapausta joissa lause ja viereinen rivi nayttivat eri luvun.

    Tama on yksi niista: raaka 54.4499 -> klientti nayttaa 54.4, joten
    erotuksen on oltava 72 - 54.4 = 17.6, ei 17.5.
    """
    rivit = MS.review_lines(_review(54.4499, 72))
    teksti = rivit[0]["text"]
    assert "54.4" in teksti, teksti
    assert "17.6" in teksti, teksti
    assert "17.5" not in teksti, teksti


def test_c5_negatiivinen_kontrolli_ilman_raakaa_summaa():
    """Vanhat payloadit ilman `projected_raw`ia eivat saa kaataa lausetta."""
    r = {"projected": 71.15, "actual": 72, "players": []}
    rivit = MS.review_lines(r)
    assert rivit and "71.2" in rivit[0]["text"]


def test_c6_lause_ei_vaita_pelaamista_vaan_vertailtavuutta():
    """"Your N who played" oli vaite jota payload ei mittaa: rivi putoaa kun
    JAADYTETTY xP puuttuu, ei siksi etta pelaaja ei pelannut. Ja bench
    boostilla FPL antaa multiplier 1 myos 0 minuutin penkkilaiselle."""
    t10 = MS.review_lines(_review(60.0, 66), rows=10)[0]["text"]
    assert "who played" not in t10, t10
    # D2 (5. kierros): sanamuoto ei saa olla sama kuin kattavuuslauseella,
    # koska joukot ovat eri (rivit vs pickit joilla molemmat luvut).
    assert "Your 10 counted picks" in t10, t10
    assert "both numbers" not in t10, t10
    # 11 riviä on yha luettava muoto.
    t11 = MS.review_lines(_review(60.0, 66), rows=11)[0]["text"]
    assert t11.startswith("Your eleven"), t11
    # Bench boost: 15 riviä ei ole "eleven".
    t15 = MS.review_lines(_review(60.0, 66), rows=15)[0]["text"]
    assert "eleven" not in t15, t15


def test_c10_kesken_oleva_kierros_merkitaan_lauseeseen():
    """Lause kulkee payloadissa itsenaisena ja renderoityy missa tahansa
    `model_says` renderoidaan - myos ilman viereista provisional-varausta.
    Arviota ei saa tehda kesken olevasta luvusta ilman merkintaa."""
    kesken = MS.review_lines(_review(71.15, 72), rows=11, provisional=True)[0]["text"]
    assert "so far" in kesken, kesken
    valmis = MS.review_lines(_review(71.15, 72), rows=11, provisional=False)[0]["text"]
    assert "so far" not in valmis, valmis
    # Merkinta kuuluu kaikkiin kolmeen haaraan, ei vain tasapeliin.
    for proj, act in ((60.0, 80), (80.0, 60)):
        t = MS.review_lines(_review(proj, act), rows=11, provisional=True)[0]["text"]
        assert "so far" in t, t


def test_e1_summa_ei_riipu_jarjestyksesta_eika_eroa_klientista():
    """🔴 E1 (6. kierros): PYORISTYSSAANNON KORJAUS EI RIITTANYT.

    Liukuluvun yhteenlasku ei ole assosiatiivinen, ja kolme pintaa summasi
    samat rivit eri jarjestyksessa. Mitattu tuotannon GW3:sta 7.9: sama
    joukko antoi 71.15 (picks-jarjestys) ja 71.14999999999999
    (diff-jarjestys), eli "71.2" ja "71.1" SAMASSA nakymassa.

    Edellinen testi mittasi vain SAANNON, ei syotetta - ja saanto oli tosi.
    Muisti: portti-voi-mitata-eri-koodipolkua.
    """
    from src.models.fpl_gw_review import build_review

    arvot = [6.11, 4.87, 2.34, 8.05, 3.19, 7.42, 5.68, 9.01, 4.44, 10.02, 10.02]

    def _rakenna(jarjestys):
        picks = {"entry_history": {"points": 58}, "active_chip": None,
                 "picks": [{"element": i + 1, "multiplier": 1,
                            "is_captain": False, "is_vice_captain": False}
                           for i in jarjestys]}
        frozen = {i + 1: arvot[i] for i in range(len(arvot))}
        points = {i + 1: 7 for i in range(len(arvot))}
        info = {i + 1: {"web_name": f"P{i}", "team_short": "ARS", "pos": "MID"}
                for i in range(len(arvot))}
        return build_review(3, picks, frozen, points, info)

    perus = list(range(len(arvot)))
    nouseva = sorted(perus, key=lambda i: arvot[i])
    laskeva = sorted(perus, key=lambda i: -arvot[i])

    tekstit = set()
    for j in (perus, nouseva, laskeva):
        out = _rakenna(j)
        rivi = MS.review_lines(out["review"], rows=len(arvot))[0]["text"]
        tekstit.add(rivi)
    assert len(tekstit) == 1, f"summausjarjestys muuttaa lausetta: {tekstit}"
    # Ja se on sadasosasumman luku, ei liukulukusumman 71.1.
    assert "71.2" in tekstit.pop()


def test_e3_kapteenilause_luetaan_kertoimesta_ei_lipusta():
    """FPL jattaa `is_captain: true` PELAAMATTOMALLE ja siirtaa kertoimen
    varakapteenille. Silloin `_rivi` laski proj = xp * 0 = 0.0 ja act = 0, ja
    lause kuului: "Your captain X returned 0 against a projected 0." """
    from src.models.fpl_gw_review import build_review

    picks = {"entry_history": {"points": 50}, "active_chip": None, "picks": [
        {"element": 1, "multiplier": 0, "is_captain": True, "is_vice_captain": False},
        {"element": 2, "multiplier": 2, "is_captain": False, "is_vice_captain": True},
    ] + [{"element": i, "multiplier": 1, "is_captain": False,
          "is_vice_captain": False} for i in range(3, 16)]}
    frozen = {i: 6.0 for i in range(1, 16)}
    points = {i: 5 for i in range(1, 16)}
    info = {i: {"web_name": f"P{i}", "team_short": "ARS", "pos": "MID"}
            for i in range(1, 16)}
    out = build_review(3, picks, frozen, points, info)

    cap = out["review"]["captain"]
    assert cap is not None and cap["web_name"] == "P2", cap
    assert cap["multiplier"] == 2
    rivi = [r for r in MS.review_lines(out["review"], rows=14)
            if r["code"] == "review.captain"][0]["text"]
    assert "returned 0 against a projected 0" not in rivi, rivi
    assert "P2" in rivi, rivi

    # Kukaan ei saanut kerrointa -> ei kapteenilausetta lainkaan.
    picks2 = dict(picks, picks=[{"element": i, "multiplier": 1,
                                 "is_captain": i == 1, "is_vice_captain": False}
                                for i in range(1, 16)])
    out2 = build_review(3, picks2, frozen, points, info)
    assert out2["review"]["captain"] is None
    assert not [r for r in MS.review_lines(out2["review"], rows=15)
                if r["code"] == "review.captain"]


def test_b1_kapteenilause_nayttaa_raakaluvun_ja_kertoimen():
    """🔴 B1 (7. kierros): lause julkaisi KERROINPAINOTETUT luvut ilman
    kerroinmerkintaa. Mitattu GW3: teksti sanoi "returned 27" kun FPL:n oma
    live-syote sanoo Haalandista 9 - lukija ei loyda 27:aa mistaan. Kortti
    sanoo kertoimen (TC-badge), paneeli ei, ja se on paneelin ainoa
    tekstipinta."""
    from src.models.fpl_model_says import _kapteenilause
    tc = {"web_name": "Haaland", "multiplier": 3, "actual": 27,
          "projected": 23.76, "actual_raw": 9, "projected_raw": 7.92}
    t = _kapteenilause(tc)
    assert "scored 9" in t, t
    assert "tripled to 27" in t, t
    assert "7.9" in t, t

    kaksi = dict(tc, multiplier=2, actual=18, projected=15.84)
    assert "doubled to 18" in _kapteenilause(kaksi)

    # Ilman kerrointa ei kerroinlausetta.
    yksi = dict(tc, multiplier=1, actual=9, projected=7.92)
    t1 = _kapteenilause(yksi)
    assert "tripled" not in t1 and "doubled" not in t1, t1
    assert "scored 9 against a projected 7.9" in t1, t1


def test_b2_pahin_kutsu_valitaan_raakaerolla_ei_kapteeninauhalla():
    """`best_call`/`worst_call` valittiin kerroinpainotetusta erosta, eli
    KAPTEENINAUHA paatti mika oli mallin pahin kutsu. Repon oma saanto
    (`fpl_rate_team.last_finished_block`) sanoo painvastoin."""
    from src.models.fpl_gw_review import build_review

    # Kapteeni: raakaero +1.0 mutta x3 = +3.0. Toinen pelaaja: raaka +2.0.
    picks = {"entry_history": {"points": 40}, "active_chip": "3xc", "picks": [
        {"element": 1, "multiplier": 3, "is_captain": True, "is_vice_captain": False},
        {"element": 2, "multiplier": 1, "is_captain": False, "is_vice_captain": False},
    ] + [{"element": i, "multiplier": 1, "is_captain": False,
          "is_vice_captain": False} for i in range(3, 16)]}
    frozen = {1: 8.0, 2: 4.0, **{i: 5.0 for i in range(3, 16)}}
    points = {1: 9, 2: 6, **{i: 5 for i in range(3, 16)}}
    info = {i: {"web_name": f"P{i}", "team_short": "ARS", "pos": "MID"}
            for i in range(1, 16)}
    out = build_review(3, picks, frozen, points, info)

    paras = out["review"]["best_call"]
    assert paras["web_name"] == "P2", (
        f"kapteeninauha valitsi parhaan: {paras['web_name']} "
        f"(raaka +1.0 x3 = +3.0 vs P2 raaka +2.0)")
    # Ja lause nayttaa kertoimettomat luvut.
    rivi = [r for r in MS.review_lines(out["review"], rows=15)
            if r["code"] == "review.best"][0]["text"]
    assert "4.0" in rivi and "6" in rivi, rivi


def test_f5_projektio_nayttaa_aina_desimaalin():
    """`_pts` pudotti desimaalin kun luku oli lahella kokonaista, ja
    viereinen rivi ei: "71.0 projected +1.0" ja alla "projected 71 ... by 1".
    Mitattu 10,0 % kaikista kierrostotaaleista."""
    from src.models.fpl_model_says import _pts
    assert _pts(71.0) == "71.0"
    assert _pts(1.0) == "1.0"
    # Toteutuneet pisteet ovat kokonaislukuja ja pysyvat sellaisina.
    assert _pts(72) == "72"
    assert _pts(0) == "0"
    t = MS.review_lines(_review(71.0, 72), rows=11)[0]["text"]
    assert "71.0" in t and "by 1.0" in t, t


def _kapteeni_paras():
    """Payload jossa PARAS kutsu on kapteeni. Tasan se fikstuuri jota
    `test_b2_...` ei kayttanyt: siella parhaalla oli multiplier 1, joten
    raaka ja kerroinpainotettu olivat sama luku eika testi voinut nahda
    eroa. Muisti: portin-fikstuuri-kirjoitetaan-korjatusta-tapauksesta."""
    from src.models.fpl_gw_review import build_review
    picks = {"entry_history": {"points": 40}, "active_chip": "3xc", "picks": [
        {"element": 1, "multiplier": 3, "is_captain": True, "is_vice_captain": False},
    ] + [{"element": i, "multiplier": 1, "is_captain": False,
          "is_vice_captain": False} for i in range(2, 16)]}
    frozen = {1: 7.92, **{i: 5.0 for i in range(2, 16)}}
    points = {1: 9, **{i: 5 for i in range(2, 16)}}
    info = {i: {"web_name": f"P{i}", "team_short": "ARS", "pos": "MID"}
            for i in range(1, 16)}
    return build_review(3, picks, frozen, points, info)


def test_review_best_nayttaa_kertoimettomat_luvut_myos_kun_paras_on_kapteeni():
    """🔴 Portin 8. kierros: `review.best` luki yha kerroinpainotettuja
    lukuja samalla kun `review.worst` luki raakoja - B2 oli korjattu yhta
    riviä myohemmin. Kapteenin ollessa paras kutsu kaksi perakkaista
    lausetta antoi saman pelaajan kahdella lukuparilla, eika "23.8
    projected" ole missaan FPL:ssa."""
    out = _kapteeni_paras()
    assert out["review"]["best_call"]["web_name"] == "P1"
    rivit = {r["code"]: r["text"] for r in MS.review_lines(out["review"], rows=15)}
    best = rivit["review.best"]
    assert "7.9 projected" in best, best
    assert "9 scored" in best, best
    # Kerroinpainotetut luvut EIVAT saa esiintya lauseessa.
    assert "23.8" not in best and "27" not in best, best
    # Ja kapteenilause kertoo kertoimen erikseen.
    assert "tripled to 27" in rivit["review.captain"], rivit["review.captain"]


def test_payloadin_players_jarjestys_on_sama_saanto_kuin_kortilla():
    """Payloadin `players` oli KOLMAS jarjestyssaanto (kerroinpainotettu)
    samalla kun kortti ja best/worst-valinta kayttavat raakaeroa. Julkinen
    API-jarjestys luetaan jarjestysvaitteena."""
    out = _kapteeni_paras()
    rivit = out["review"]["players"]
    raa = [r["diff_raw"] for r in rivit]
    assert raa == sorted(raa, reverse=True), raa
    # Kapteeni ei nouse karkeen kerroinpainotuksen ansiosta: raaka +1.08.
    assert rivit[0]["web_name"] == "P1", "raakaero +1.08 on suurin, mutta"


def test_9_kierros_vartija_lukee_samaa_kenttaa_kuin_teksti():
    """🔴 Vartija luki KERROINPAINOTETTUA (`diff`) kun teksti luki raakaa
    (`_raw`), ja paneeli kaytti `diff_raw`ia - kaksi saantoa samasta
    vaitteesta. Mitattu: mult 3, xp 7.9967, pts 8 -> diff +0.01 mutta
    diff_raw 0.0, eli malli julkaisi superlatiivin jonka molemmat luvut ovat
    samat samalla kun paneeli oli vaiti."""
    from src.models.fpl_gw_review import build_review
    picks = {"entry_history": {"points": 40, "event_transfers_cost": 4},
             "active_chip": "3xc", "picks": [
        {"element": 1, "multiplier": 3, "is_captain": True, "is_vice_captain": False},
    ] + [{"element": i, "multiplier": 1, "is_captain": False,
          "is_vice_captain": False} for i in range(2, 16)]}
    frozen = {1: 7.9967, **{i: 5.0 for i in range(2, 16)}}
    points = {1: 8, **{i: 5 for i in range(2, 16)}}
    info = {i: {"web_name": f"P{i}", "team_short": "A", "pos": "MID"}
            for i in range(1, 16)}
    out = build_review(3, picks, frozen, points, info)

    bc = out["review"]["best_call"]
    assert bc["diff"] > 0 and bc["diff_raw"] == 0.0, (bc["diff"], bc["diff_raw"])
    koodit = [r["code"] for r in MS.review_lines(out["review"], rows=15)]
    assert "review.best" not in koodit, (
        "superlatiivi julkaistiin vaikka raakaero on 0")

    # B3: siirtorangaistus on payloadissa, jotta FPL:n luku on selitettavissa.
    assert out["meta"]["transfer_cost"] == 4
