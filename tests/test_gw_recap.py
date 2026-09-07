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

import re as _re
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

def _acc(mae, by_class, pos=None):
    r = {"gw": 1, "mae": mae, "n": 490, "by_class": by_class}
    if pos:
        r["by_pos_stats"] = pos
    return r


def test_nostaa_segmentin_joka_on_iso_suhteessa_maehen():
    """🔴 Portin 24. kierros: fikstuuri kaytti `haul`ia, joka on
    TOTEUMASEGMENTTI eika saa nousta lainkaan. Positio tiedetaan ennen
    kierrosta, joten sen harha on aito loydos."""
    m = headline_miss(_acc(1.76, {}, pos={"FWD": {"n": 19, "mae": 9.41,
                                                  "bias": 9.41}}))
    assert m["segment"] == "pos:FWD"
    assert m["n"] == 19 and m["bias"] == 9.41
    assert m["x_mae"] == round(9.41 / 1.76, 1)
    assert m["direction"] == "under"


def test_negatiivinen_kontrolli_pieni_harha_ei_nouse():
    assert headline_miss(_acc(1.76, {"dnp": {"n": 190, "mae": 1.09, "bias": -1.09}})) is None


def test_negatiivinen_kontrolli_liian_pieni_segmentti_on_kohinaa():
    assert headline_miss(_acc(1.76, {"x": {"n": 5, "mae": 20.0, "bias": 20.0}})) is None


def test_yliarvio_tunnistetaan_suunnaltaan():
    m = headline_miss(_acc(1.0, {}, pos={"DEF": {"n": 50, "mae": 5.0,
                                                 "bias": -5.0}}))
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


# --- Portin 22. kierros: julkisen artefaktin kieliportti --------------------
# Kentat joiden arvo on ENUMEROITU. Uusi arvo ei paase lapi vahingossa: testi
# kaatuu ja kirjoittajan on lisattava se tanne (sama mekanismi kuin
# `test_xp_reader_discipline.py`:n perusteltu poikkeuslista).
ENUMEROIDUT = {
    "direction": {"under", "over"},
    # 🔴 PORTIN 23. KIERROS (B6): enumerointi kattoi VAIN `direction`in, ja
    # heuristiikka ei loytanyt yhtaan realistista suomenkielista arvoa -
    # portti ajoi 19 uskottavalla arvolla ("kesken", "vaara", "voitto",
    # "ennuste", ...) ja sai NOLLA osumaa. Myos `aliarvio`, se sanatarkka
    # arvo joka aiheutti 22. kierroksen loydoksen, meni heuristiikasta lapi;
    # se jai kiinni vain koska `direction` oli enumeroitu.
    #
    # Suljetut joukot kuuluvat siis listalle, ei heuristiikan varaan.
    "call": {"captain_pick", "ceiling", "gamble", "model_captain",
             "projected_xi", "safest"},
    "criterion": {"10+ pts", "3+ pts", "reached p90",
                  "captain return, points doubled",
                  "XI points with the captain doubled, FPL automatic "
                  "substitutions applied from the bench in order"},
}

# Kentat joiden arvo on ulkoista dataa tai vapaata tekstia: pelaajien ja
# joukkueiden nimet, aikaleimat, tunnisteet. Naita ei voi enumeroida eika
# heuristiikka saa huutaa niista (esim. "Jarvenpaa" tai "Nystrom").
ULKOINEN_TEKSTI = {
    "segment", "web_name", "team", "team_short", "name", "season",
    "graded_at", "generated_at", "frozen_at", "deadline", "chip", "source",
    "deadline_utc", "logged_at",
}

# Vapaata proosaa: ei enumeroitavissa, mutta EI myoskaan heuristiikan
# varassa. Naille vaaditaan eksplisiittinen englanti-invariantti: teksti
# alkaa pienella ASCII-kirjaimella ja koostuu ASCII-merkeista. Suomi ei
# kaadu tahan aina, mutta yhdessa heuristiikan kanssa pinta on katettu, ja
# ennen kaikkea: uusi proosakentta ei paase tanne vahingossa.
PROOSA = {"basis"}

# Suomen sijapaatteet joita englanti ei tuota sanan lopussa. Heuristiikka on
# tarkoituksella loysa: se kattaa enumeroimattomat kentat, ja vaarat
# positiivit korjataan lisaamalla kentta jompaankumpaan listaan ylla.
_SIJAPAATE = _re.compile(
    r"\w+(ssa|ssä|sta|stä|lle|lta|ltä|jen|ksi|ttu|tty|van|neet|isuus|"
    r"ista|istä|ille|illa|illä|uksia|uksen|oja|ojen|uja|ujä|ksia|"
    r"ksen|sti|ien|ita|itä)(\b|$)", _re.I)


def suomelta_nayttava(x: str) -> bool:
    """Umlaut TAI suomen sijapaate. Ks. `test_kontrolli_...` alla."""
    return bool(_re.search(r"[äöÄÖ]", x) or _SIJAPAATE.search(x))


def test_julkinen_artefakti_ei_sisalla_suomea():
    """🔴 PORTIN 22. KIERROS: EDELLINEN VERSIO SKANNASI VAARAA TIEDOSTOA.

    20. kierros korjasi yhden suomenkielisen merkkijonon generaattorissa.
    21. kierros korjasi toisen JA kirjoitti portin - joka skannasi
    **generaattorin lahdekoodin**. Portti oli vihrea, ja `data/gw_recap.json`
    sisalsi HEADissa yha `"direction": "aliarvio"`. Julkinen pinta on
    ARTEFAKTI, ei generaattori (muisti:
    generoitu-sivu-verifioi-regeneroimalla).

    Ja kieltolista vaihdettiin SALLITTUUN listaan. Sanalista vanhenee:
    `"tila": "kesken"`, `"syy": "kapteeni vaihtui"`, `"suunta": "vaara"` ja
    kymmenen muuta olisivat menneet lapi. Enumeroitu kentta ei voi saada
    uutta arvoa vahingossa, ja enumeroimattomille jaa heuristiikka.
    """
    import datetime as _dt
    import json
    from pathlib import Path

    from scripts.build_gw_recap import (ACC_PATH, CALLS_PATH, SQUAD_PATH,
                                        _load, build)

    # Artefakti REGENEROIDAAN testissa: levylla oleva tiedosto voi olla
    # vanha, ja juuri se oli vika.
    doc = build(_load(CALLS_PATH), _load(SQUAD_PATH), _load(ACC_PATH),
                _dt.datetime.now(_dt.timezone.utc))

    ongelmat = []

    def kavele(x, polku=""):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ENUMEROIDUT:
                    if isinstance(v, str) and v not in ENUMEROIDUT[k]:
                        ongelmat.append(
                            f"{polku}.{k} = {v!r}, sallitut {ENUMEROIDUT[k]}")
                    continue
                if k in PROOSA:
                    if isinstance(v, str):
                        assert v.isascii(), f"{polku}.{k}: ei-ASCII proosassa"
                        assert not suomelta_nayttava(v), f"{polku}.{k}: {v!r}"
                    continue
                if k in ULKOINEN_TEKSTI:
                    continue
                kavele(v, f"{polku}.{k}")
        elif isinstance(x, list):
            for n, v in enumerate(x):
                kavele(v, f"{polku}[{n}]")
        elif isinstance(x, str) and len(x) > 3:
            if suomelta_nayttava(x):
                ongelmat.append(f"{polku} = {x!r}")

    kavele(doc)
    assert not ongelmat, (
        "julkiseen artefaktiin paatyy suomea tai enumeroimaton arvo:\n  "
        + "\n  ".join(ongelmat))

    # Ja LEVYLLA oleva committattu tiedosto on generaattorin kanssa samaa
    # mielta. Tama kaataa jos artefakti on jaanyt jalkeen - se oli tasan
    # tama vika.
    levy = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "gw_recap.json")
        .read_text(encoding="utf-8"))
    for lohko in (levy.get("gameweeks") or []):
        hm = (lohko.get("headline_miss") or {})
        if isinstance(hm, dict) and "direction" in hm:
            assert hm["direction"] in ENUMEROIDUT["direction"], (
                "committattu artefakti on generaattorin jaljessa: "
                f"direction={hm['direction']!r}")


def test_kontrolli_suomiportti_havaitsee_arvon():
    """NEGATIIVINEN KONTROLLI havaitsimelle: sen on loydettava suomi seka
    umlautista etta sijapaatteesta, ja jatettava englanti rauhaan. Ilman
    tata portti voisi olla vihrea siksi ettei se havaitse mitaan."""
    assert suomelta_nayttava("aliarvio kierroksessa")
    assert suomelta_nayttava("kapteeni vaihtui joukkueelle")
    assert suomelta_nayttava("ei lopullisesti gradattuja kierroksia")
    assert not suomelta_nayttava("the model underestimated")
    assert not suomelta_nayttava("under")
    assert not suomelta_nayttava("no finally graded gameweeks yet")
    assert not suomelta_nayttava("model points before its own transfer hits")


def test_kontrolli_enumeroitu_kentta_ei_paase_uudella_arvolla():
    """Sallittu lista on portin ydin: uusi arvo ei paase lapi vahingossa
    vaan kirjoittajan on lisattava se tanne."""
    assert "aliarvio" not in ENUMEROIDUT["direction"]
    assert ENUMEROIDUT["direction"] == {"under", "over"}

def test_kaikki_artefaktin_merkkijonokentat_on_luokiteltu():
    """🔴 PORTIN 23. KIERROS (B6). Enumerointi kattoi yhden kentan, ja
    heuristiikka ei loytanyt yhtaan realistista suomenkielista arvoa.
    Kolme kenttaa (`call`, `criterion`, `basis`) oli enumeroimatta ja siis
    kaytannossa vartioimatta.

    Tama kaataa jos artefaktiin ilmestyy UUSI merkkijonokentta jota ei ole
    luokiteltu johonkin kolmesta: enumeroitu, ulkoinen teksti tai proosa.
    Uusi kentta ei voi jaada nakymattomaksi.
    """
    import datetime as _dt

    from scripts.build_gw_recap import (ACC_PATH, CALLS_PATH, SQUAD_PATH,
                                        _load, build)
    doc = build(_load(CALLS_PATH), _load(SQUAD_PATH), _load(ACC_PATH),
                _dt.datetime.now(_dt.timezone.utc))

    tunnetut = set(ENUMEROIDUT) | ULKOINEN_TEKSTI | PROOSA
    tuntemattomat = set()

    def kavele(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str) and len(v) > 3 and k not in tunnetut:
                    tuntemattomat.add(k)
                kavele(v)
        elif isinstance(x, list):
            for v in x:
                kavele(v)

    kavele(doc)
    assert not tuntemattomat, (
        "artefaktissa on luokittelemattomia merkkijonokenttia. Lisaa jokainen "
        "ENUMEROIDUT-, ULKOINEN_TEKSTI- tai PROOSA-listaan:\n  "
        + "\n  ".join(sorted(tuntemattomat)))


def test_kontrolli_enumerointi_kaataa_uudesta_arvosta():
    """Sallittu lista on portin ydin: uusi arvo ei paase lapi vahingossa."""
    for kentta, sallitut in ENUMEROIDUT.items():
        assert sallitut, kentta
        assert "aliarvio" not in sallitut
        assert "kesken" not in sallitut


def test_headline_miss_ei_raportoi_toteumasegmenttia():
    """🔴 PORTIN 24. KIERROS (B1). 23. kierroksella suljin toteumasegmentit
    tautologisina - mutta VAIN toisesta lukijasta (`autopilot/edge.py`).
    `headline_miss` ajoi saman silmukan ilman suodatusta, ja
    `data/gw_recap.json` on JULKISESSA repossa. Mitattu 7.9:

        GW1 headline_miss = {"segment": "haul", "bias": 9.41, "mae": 9.41}

    Kentta on nimensa mukaan tarkoitettu postauksen otsikoksi, ja siina luki
    tasmalleen se sormenjalki (`|bias| == mae`) jolla tautologia
    todistettiin. Kaksi lukijaa, kaksi saantoa.
    """
    from scripts.build_gw_recap import headline_miss

    # Sama luku kummassakin lohkossa: vain positio saa nousta.
    rivi = {
        "mae": 1.68,
        "by_class": {"haul": {"n": 33, "mae": 9.22, "bias": 9.22},
                     "dnp": {"n": 190, "mae": 1.09, "bias": -1.09}},
    }
    assert headline_miss(rivi) is None, "toteumasegmentti paatyi otsikoksi"

    # KONTROLLI: positiosegmentti samoilla luvuilla NOUSEE. Ilman tata
    # testi olisi vihrea siksi ettei mikaan nouse.
    rivi["by_pos_stats"] = {"FWD": {"n": 33, "mae": 9.22, "bias": 9.22}}
    hm = headline_miss(rivi)
    assert hm and hm["segment"] == "pos:FWD", hm


def test_toteumalohko_on_lohko_ei_nimilista():
    """Ensimmainen korjaus oli kieltolista arvonimista, jolloin UUSI luokka
    (esim. `cameo`) olisi mennyt lapi aitona loydoksena. `by_class` on
    maaritelmaltaan toteumasegmentointi (muisti: portin-sanalista-vanhenee).
    """
    from scripts.build_gw_recap import headline_miss
    from src.models.xp_accuracy_segments import TOTEUMALOHKOT
    assert TOTEUMALOHKOT == {"by_class"}
    keksitty = {"mae": 1.0,
                "by_class": {"cameo": {"n": 50, "mae": 9.0, "bias": 9.0}}}
    assert headline_miss(keksitty) is None, "uusi luokkanimi meni lapi"


def test_julkaistu_artefakti_ei_kanna_toteumasegmenttia():
    """Ja LEVYLLA oleva committattu tiedosto on generaattorin kanssa samaa
    mielta - se oli tasan tama vika (artefakti oli livena vaarin)."""
    import json
    from pathlib import Path
    from src.models.xp_accuracy_segments import LOHKOT, TOTEUMALOHKOT
    kielletyt = {e for lohko, e in LOHKOT if lohko not in TOTEUMALOHKOT}
    levy = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "gw_recap.json")
        .read_text(encoding="utf-8"))
    for g in levy.get("gameweeks") or []:
        hm = g.get("headline_miss")
        if not isinstance(hm, dict):
            continue
        seg = str(hm.get("segment") or "")
        assert any(seg.startswith(e) for e in kielletyt if e), (
            f"julkaistu artefakti kantaa toteumasegmentin: {seg!r} "
            f"(GW{g.get('gw')})")
