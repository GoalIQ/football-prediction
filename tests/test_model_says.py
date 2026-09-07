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
    assert "3 points" in worst["text"], worst["text"]


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
    assert "The 10 picks with both numbers" in t10, t10
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
