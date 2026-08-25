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
    assert r["text"].startswith("The model"), r["text"]


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
