"""GW-recap: viikoittaisen postauksen dataselkaranka (31.8.2026).

Villen pyynto: peliviikkoa seuraavana paivana postaus "miten meni", ja ennen
peliviikkoa teemapostaus. Kadenssi ei ole pitanyt koska luvut ovat neljassa
tiedostossa. Tama kokoaa ne.

Nama testit vartioivat kolmea rehellisyyssaantoa, jotka ovat koko syy miksi
track recordin voi julkaista:

  1. gradaamaton EI ole nolla
  2. `met = None` EI ole huti
  3. tappiot ovat mukana juoksevassa rivissa
"""
from __future__ import annotations

import datetime as _dt
import pathlib

from scripts.build_gw_recap import (build, calls_block, headline_miss,
                                    running_record)

NYT = _dt.datetime(2026, 9, 1, 8, 0, tzinfo=_dt.timezone.utc)


def _squad(gw, points, average, provisional=False):
    return {"gw": gw, "points": points, "fpl_average": average,
            "bench_points": 0, "transfer_cost": 0, "active_chip": None,
            "captain_id": 426, "captain_points_added": 2,
            "provisional": provisional, "graded_at": "2026-09-01T07:00:00+00:00"}


def _calls_gw(gw, calls, by_call=None, provisional=False,
              logged="2026-08-28T17:13:07Z", deadline="2026-08-28T17:30:00Z"):
    row = {"gw": gw, "logged_at": logged, "deadline_utc": deadline,
           "calls": calls}
    if by_call is not None:
        row["graded"] = {"graded_at": "2026-09-01T07:00:00Z",
                         "provisional": provisional, "by_call": by_call}
    return row


# --- juokseva rivi ---------------------------------------------------------

def test_tappio_ja_voitto_ovat_samassa_rivissa():
    """Koko syy miksi track record on julkaisukelpoinen."""
    r = running_record([_squad(1, 41, 50), _squad(2, 93, 66)])
    assert r["gameweeks"] == 2
    assert r["total_diff"] == 18
    assert r["beat_average"] == 1 and r["below_average"] == 1
    assert [x["diff"] for x in r["per_gw"]] == [-9, 27]


def test_provisionaalinen_kierros_ei_ole_juoksevassa_rivissa():
    """Kesken oleva luku vaihtuu viela; juokseva summa joka muuttuu
    jalkikateen ei ole track record vaan liikkuva maali."""
    r = running_record([_squad(1, 41, 50), _squad(2, 93, 66, provisional=True)])
    assert r["gameweeks"] == 1 and r["gw_list"] == [1]
    assert r["total_diff"] == -9


def test_negatiivinen_kontrolli_lopullinen_kierros_ON_rivissa():
    """Ilman tata edellinen lapaisisi myos jos KAIKKI suodatetaan pois."""
    r = running_record([_squad(2, 93, 66, provisional=False)])
    assert r["gameweeks"] == 1 and r["total_diff"] == 27


def test_ei_gradattuja_kierroksia_sanotaan_ei_nollata():
    r = running_record([])
    assert r["gameweeks"] == 0 and "no finally graded" in r["note"]
    assert "total_diff" not in r


def test_puuttuva_keskiarvo_ei_lasketa_nollana():
    r = running_record([{"gw": 1, "points": 41, "fpl_average": None}])
    assert r["gameweeks"] == 0


# --- kutsut ----------------------------------------------------------------

def test_osumat_ja_hudit_lasketaan():
    row = _calls_gw(2, [{"call": "a", "web_name": "X"},
                        {"call": "b", "web_name": "Y"},
                        {"call": "c", "web_name": "Z"}],
                    by_call={"a": {"met": True, "points": 12},
                             "b": {"met": False, "points": 2},
                             "c": {"met": True, "points": 9}})
    c = calls_block(row)
    assert c["hits"] == 2 and c["misses"] == 1 and c["ungraded"] == 0


def test_met_none_ei_ole_huti():
    """None = pelaajaa ei loytynyt live-datasta. Sen laskeminen hudiksi
    tekisi track recordista pahemman kuin se on, eli valheellisen."""
    row = _calls_gw(2, [{"call": "a"}, {"call": "b"}],
                    by_call={"a": {"met": True}, "b": {"met": None}})
    c = calls_block(row)
    assert c["hits"] == 1 and c["misses"] == 0 and c["ungraded"] == 1


def test_gradaamaton_kierros_ei_tuota_osumia():
    row = _calls_gw(2, [{"call": "a"}, {"call": "b"}])
    c = calls_block(row)
    assert c["graded"] is False
    assert c["hits"] == 0 and c["misses"] == 0 and c["ungraded"] == 2


def test_kirjattu_ennen_deadlinea_lasketaan_ei_oleteta():
    """Tama on koko julkaistavan vaitteen ydin."""
    assert calls_block(_calls_gw(2, []))["logged_before_deadline"] is True


def test_kirjaus_deadlinen_jalkeen_on_epatosi():
    row = _calls_gw(2, [], logged="2026-08-28T17:45:00Z",
                    deadline="2026-08-28T17:30:00Z")
    assert calls_block(row)["logged_before_deadline"] is False


def test_puuttuva_aikaleima_on_none_ei_true():
    """Ei tietoa != kirjattu ajoissa. Tama vaite menisi julkisuuteen."""
    row = _calls_gw(2, [], logged=None)
    assert calls_block(row)["logged_before_deadline"] is None


def test_rikkinainen_aikaleima_on_none():
    row = _calls_gw(2, [], logged="eilen")
    assert calls_block(row)["logged_before_deadline"] is None


# --- kiinnostavin vaara ----------------------------------------------------

def _acc(mae, by_class):
    return {"gw": 1, "mae": mae, "n": 490, "by_class": by_class}


def test_nostaa_segmentin_joka_on_iso_suhteessa_maehen():
    m = headline_miss(_acc(1.76, {"haul": {"n": 19, "mae": 9.41, "bias": 9.41}}))
    assert m["segment"] == "haul"
    assert m["n"] == 19 and m["bias"] == 9.41
    assert m["x_mae"] == round(9.41 / 1.76, 1)
    assert m["direction"] == "under"


def test_negatiivinen_kontrolli_pieni_harha_ei_nouse():
    assert headline_miss(_acc(1.76, {"dnp": {"n": 190, "mae": 1.09, "bias": -1.09}})) is None


def test_negatiivinen_kontrolli_liian_pieni_segmentti_on_kohinaa():
    assert headline_miss(_acc(1.76, {"x": {"n": 5, "mae": 20.0, "bias": 20.0}})) is None


def test_yliarvio_tunnistetaan_suunnaltaan():
    m = headline_miss(_acc(1.0, {"y": {"n": 50, "mae": 5.0, "bias": -5.0}}))
    assert m["direction"] == "over"


def test_puuttuva_tarkkuusartefakti_ei_kaada():
    assert headline_miss(None) is None
    assert headline_miss({"mae": None}) is None


# --- kooste ----------------------------------------------------------------

def test_puuttuva_lahde_merkitaan_vaillinaiseksi_ei_tyhjaksi():
    doc = build(None, {"gameweeks": [_squad(1, 41, 50)]}, None, NYT)
    assert doc["meta"]["complete"] is False
    assert doc["meta"]["sources"]["gw_calls"] is False
    assert doc["gameweeks"][0]["calls"] is None
    # Luku on silti mukana: vaillinainen ei tarkoita tyhjaa.
    assert doc["gameweeks"][0]["squad"]["diff"] == -9


def test_kaikki_lahteet_paikalla_on_complete():
    doc = build({"gameweeks": [_calls_gw(1, [])]},
                {"gameweeks": [_squad(1, 41, 50)]},
                {"gameweeks": [_acc(1.76, {})]}, NYT)
    assert doc["meta"]["complete"] is True


def test_kierrokset_ovat_jarjestyksessa():
    doc = build(None, {"gameweeks": [_squad(3, 70, 60), _squad(1, 41, 50),
                                     _squad(2, 93, 66)]}, None, NYT)
    assert [g["gw"] for g in doc["gameweeks"]] == [1, 2, 3]


# --- artefakti paasee repoon ----------------------------------------------

def test_gw_recap_ei_ole_gitignoressa():
    """🔴 `/data/*` on ignoroitu ja poikkeukset luetellaan kasin. Ilman
    `!/data/gw_recap.json`-rivia artefakti ei paase repoon, S13 ei nae sita
    raw.githubista, ja koko peliviikkokadenssi on inertti - hiljaa.

    `.gitignore` dokumentoi taman ansan itse: edelliset poikkeukset loytyivat
    vasta ajamalla workflow kasin (muisti: gitignored-fix-silent-regression).
    """
    gi = (pathlib.Path(__file__).resolve().parents[1] / ".gitignore"
          ).read_text(encoding="utf-8")
    rivit = [r.strip() for r in gi.splitlines()]
    assert "!/data/gw_recap.json" in rivit
    # Negatiivinen kontrolli: testi ei saa lapaista pelkalla merkkijonolla
    # kommentissa - poikkeuksen on oltava OMALLA rivillaan.
    assert "/data/*" in rivit


# --- Portin 18. kierros: track record on BRUTTO vs BRUTTO ------------------
# 17. kierros vaihtoi taman nettoon vaaralla premissilla ("FPL:n keskiarvo on
# netto"). Mitattu kahdesti riippumattomasti 7.9.2026, kalibroituna GW1:lla
# jossa hitit eivat voi vaikuttaa: `average_entry_score` on BRUTTO. Vertailu
# on siis brutto vs brutto, ja peruste on kirjoitettu artefaktiin.
#
# Fikstuuri on kirjoitettu VIKALUOKASTA eika korjatusta tapauksesta: hitti on
# 8 p, jolloin brutto ja netto antavat ERI ETUMERKIN. Kumpi tahansa
# suunnanvaihto kaataa testin, ei vain se joka oli viimeksi vaarin.

def _rivi(gw, points, average, cost=0, provisional=False):
    return {"gw": gw, "points": points, "fpl_average": average,
            "transfer_cost": cost, "provisional": provisional}


def test_running_record_vertaa_bruttoa_bruttoon():
    from scripts.build_gw_recap import running_record
    # Brutto 70 vs 66 = +4. Netto olisi 62 vs 66 = -4.
    r = running_record([_rivi(3, 70, 66, cost=8)])
    assert r["total_diff"] == 4, r
    assert r["beat_average"] == 1 and r["below_average"] == 0, r
    # Netto on silti nakyvissa, jotta postauksen kirjoittaja voi kertoa hitin.
    assert r["per_gw"][0]["points_net"] == 62
    assert r["per_gw"][0]["transfer_cost"] == 8
    # Ja peruste sanotaan artefaktissa, ei paatella.
    # Peruste sanotaan artefaktissa - ja se EI saa vaittaa mita FPL:n luku on.
    # 🔴 Portin 20. kierros: myos etuliite "gross vs gross" oli vaite, koska
    # se sanoo MOLEMPIEN puolten olevan bruttoja. Nimeamme vain oman.
    assert "before its own transfer hits" in r["basis"], r.get("basis")
    assert "not established" in r["basis"], r.get("basis")
    for kielletty in ("average_entry_score is gross", "gross vs gross"):
        assert kielletty not in r["basis"], (
            f"todentamaton vaite FPL:n perustasta palasi artefaktiin: {kielletty}")


def test_running_record_kontrolli_ilman_hittia_sama_luku():
    """NEGATIIVINEN KONTROLLI: ilman hittia brutto == netto, joten testi ei
    ole vihrea siksi etta se laskee saman luvun kahdesti."""
    from scripts.build_gw_recap import running_record
    r = running_record([_rivi(3, 70, 66, cost=0)])
    assert r["total_diff"] == 4 and r["beat_average"] == 1, r
    assert r["per_gw"][0]["points_net"] == 70


def test_kierroslohkon_diff_on_sama_brutto():
    """Sama vertailu kahdessa paikassa: juokseva rivi ja kierroslohko eivat
    saa vastata eri yksikossa (muisti: yksi-renderointipolku-kahdesta)."""
    import datetime as _dt
    from scripts.build_gw_recap import build
    doc = build(None, {"gameweeks": [_rivi(3, 70, 66, cost=8)]}, None,
                _dt.datetime(2026, 9, 7, tzinfo=_dt.timezone.utc))
    assert doc["gameweeks"][0]["squad"]["diff"] == 4
    assert doc["gameweeks"][0]["squad"]["points_net"] == 62
    assert doc["running"]["total_diff"] == doc["gameweeks"][0]["squad"]["diff"]


def test_julkinen_artefakti_ei_sisalla_suomea():
    """🔴 Portin 20. kierros korjasi YHDEN suomenkielisen merkkijonon tassa
    tiedostossa ja jatti kaksi. `data/gw_recap.json` on julkisessa repossa.

    Portti skannaa generaattorin merkkijonoliteraalit, ei yhta tunnettua
    sanaa: uusi suomenkielinen kentta kaatuu ilman etta kukaan muistaa
    lisata sita listalle.
    """
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
           / "scripts" / "build_gw_recap.py")
    tree = ast.parse(src.read_text(encoding="utf-8"))
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            if (n.body and isinstance(n.body[0], ast.Expr)
                    and isinstance(getattr(n.body[0], "value", None), ast.Constant)
                    and isinstance(n.body[0].value.value, str)):
                docs.add(id(n.body[0].value))
    # `print`-kutsujen sisalto on CI-lokia eika artefaktia; suomi on siella
    # oikein. Suodatetaan ne pois, jotta portti mittaa sita mika PAATYY
    # tiedostoon eika sita mita ajo tulostaa.
    lokistringit = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "print"):
            for sub in ast.walk(n):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    lokistringit.add(id(sub))

    # Suomen tunnusmerkit joita englannissa ei esiinny sanan sisalla.
    VIHJEET = ("aliarvi", "yliarvi", "kierrok", "ei ole", "vaara", "puuttuu",
               "lopullis", "gradat", "kaytto", "vahvistett", "jaljell")
    osumat = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docs and id(n) not in lokistringit
                and len(n.value) > 3):
            ala = n.value.lower()
            if any(v in ala for v in VIHJEET):
                osumat.append((n.lineno, n.value[:70]))
    assert not osumat, (
        "suomenkielinen merkkijono paatyy julkiseen artefaktiin:\n  "
        + "\n  ".join(f"rivi {ln}: {v!r}" for ln, v in osumat))


def test_kontrolli_suomiportti_havaitsee_artefaktikentan(tmp_path):
    """NEGATIIVINEN KONTROLLI: portin on kaaduttava suomenkieliseen
    ARTEFAKTIKENTTAAN mutta EI `print`-lokiin. Ilman tata portti olisi
    vihrea siksi etta se suodattaa liikaa."""
    import ast
    koe = tmp_path / "koe.py"
    koe.write_text(
        'def f():\n'
        '    print("::warning::ei gradattuja kierroksia")\n'
        '    return {"direction": "aliarvio"}\n', encoding="utf-8")
    tree = ast.parse(koe.read_text(encoding="utf-8"))
    loki = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "print"):
            for sub in ast.walk(n):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    loki.add(id(sub))
    VIHJEET = ("aliarvi", "kierrok")
    osumat = [n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and id(n) not in loki
              and any(v in n.value.lower() for v in VIHJEET)]
    assert osumat == ["aliarvio"], osumat
