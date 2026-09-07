"""#55 career-endpoint-testit: summary-matematiikka, kesävälitilan dedup,
esikausi-degradaatio (EI blank/virhe), teaser-poisjättö, endpoint-smoke.

Hermeettinen: FPL-API (rt._fetch_fpl) ja rate_team mockataan — ei verkkoa.
"""
from __future__ import annotations

import pathlib

import pytest

import src.models.fpl_career as fc
import src.models.fpl_rate_team as rt

ENTRY_ROOT = {
    "id": 424242, "player_first_name": "Ville", "player_last_name": "Test",
    "name": "Test XI", "joined_time": "2023-07-21T10:00:00Z",
}

PAST = [
    {"season_name": "2023/24", "total_points": 2001, "rank": 500000},
    {"season_name": "2024/25", "total_points": 2210, "rank": 120000},
    {"season_name": "2025/26", "total_points": 1381, "rank": 11775271},
]

# Kesävälitila: 25/26 on SEKÄ currentissa (38 GW) ETTÄ pastissa.
CURRENT_FULL = [
    {"event": g, "points": 30 + (g % 7), "total_points": 0,
     "overall_rank": 1_000_000 - g * 1000,
     "event_transfers_cost": 4 if g in (10, 20) else 0,
     "points_on_bench": 2}
    for g in range(1, 39)
]
CURRENT_FULL[-1]["total_points"] = 1381  # matchaa past[-1] → finished-dedup

CHIPS = [{"name": "wildcard", "time": "x", "event": 12},
         {"name": "bboost", "time": "x", "event": 30}]

FAKE_TEASER_RATING = {
    "meta": {"gw": 1, "rating_method": "vs_optimal_budget_team"},
    "rating": {"team_xp_gw": 52.2, "team_xp_horizon": 304.3,
               "percentile": 89.4},
}


# 🔴 Portin 15. kierros: `career` suodattaa kesken olevat kierrokset
# (fail-closed). Ilman bootstrapia yksikaan kierros ei ole todistetusti
# lopullinen, joten oletusfikstuuri sanoo ne valmiiksi - muuten jokainen
# vanha testi mittaisi tyhjaa kautta.
BOOTSTRAP_KAIKKI_VALMIIT = {
    "events": [{"id": g, "finished": True, "data_checked": True}
               for g in range(1, 39)]
}


def _mock_fpl(monkeypatch, root=ENTRY_ROOT, past=PAST, current=CURRENT_FULL,
              chips=CHIPS, bootstrap=BOOTSTRAP_KAIKKI_VALMIIT, teaser="ok"):
    def fake_fetch(path):
        if path == "/entry/424242/":
            return root
        if path == "/entry/424242/history/":
            return {"past": past, "current": current, "chips": chips}
        if path == "/bootstrap-static/":
            if bootstrap is None:
                raise rt.RateTeamError(503, "no bootstrap in this test")
            return bootstrap
        raise rt.RateTeamError(404, "Not found on the FPL API.")

    monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
    if teaser == "ok":
        monkeypatch.setattr(rt, "rate_team",
                            lambda entry=None, **kw: FAKE_TEASER_RATING)
    else:
        def boom(entry=None, **kw):
            raise rt.RateTeamError(404, "no picks")
        monkeypatch.setattr(rt, "rate_team", boom)
    rt._FPL_CACHE.clear()


# ---------------------------------------------------------------------------
# Kesävälitila: finished current == past[-1] → EI tuplalaskentaa
# ---------------------------------------------------------------------------

def test_summer_dedup_and_summary(monkeypatch):
    _mock_fpl(monkeypatch)
    out = fc.career(424242)
    assert out["manager"]["name"] == "Ville Test"
    assert out["manager"]["team_name"] == "Test XI"
    assert out["summary"]["since"] == 2023
    assert len(out["past_seasons"]) == 3
    # Dedup: 25/26 on pastissa → all_time = pelkkä past-summa, seasons = 3
    assert out["summary"]["all_time_points"] == 2001 + 2210 + 1381
    assert out["summary"]["seasons_played"] == 3
    assert out["summary"]["best_season"]["season"] == "2024/25"
    assert out["summary"]["best_rank"] == 120000
    lat = out["latest_season"]
    assert lat["available"] and lat["finished"]
    assert lat["season"] == "2025/26"
    assert lat["total_points"] == 1381
    assert lat["total_hits"] == 8
    assert lat["bench_points"] == 76
    # 🔴 Portin 14. kierros: valinta ja luku NETOSTA. `career.html` renderoi
    # `best_gw`n samalle riville `total_points`in kanssa, ja jalkimmainen on
    # netto - sama rivi naytti kaksi eri yksikkoa ilmaisella julkisella
    # jakokortilla. Fikstuurissa GW10 ja GW20 maksavat 4: GW10:n brutto on
    # 33 mutta netto 29, joten se on huonoin kierros vasta netolla
    # (brutolla huonoin olisi 30).
    assert lat["best_gw"]["points_net"] == 36
    assert lat["worst_gw"]["points_net"] == 29
    assert lat["worst_gw"]["gw"] == 10, "valinta tehdaan netosta"
    # Brutto kulkee yha mukana, jotta hitti on selitettavissa.
    assert lat["worst_gw"]["points"] == 33
    assert [c["gw"] for c in lat["chips_used"]] == [12, 30]
    assert len(lat["gws"]) == 38


def test_in_progress_season_counts_once(monkeypatch):
    # Kesken kauden: current EI matchaa pastia → lasketaan mukaan kerran.
    cur = CURRENT_FULL[:10]
    cur = [dict(g) for g in cur]
    cur[-1]["total_points"] = 333
    cur[-1]["overall_rank"] = 250000
    _mock_fpl(monkeypatch, current=cur)
    out = fc.career(424242)
    lat = out["latest_season"]
    assert lat["available"] and not lat["finished"] and lat["season"] is None
    assert out["summary"]["all_time_points"] == 2001 + 2210 + 1381 + 333
    assert out["summary"]["seasons_played"] == 4
    assert out["summary"]["best_rank"] == 120000  # 250k ei ohita


# ---------------------------------------------------------------------------
# Esikausi-degradaatio: current tyhjä → past + summary silti, EI virhettä
# ---------------------------------------------------------------------------

def test_preseason_graceful_empty_current(monkeypatch):
    boot = {"events": [
        {"id": 1, "is_next": True, "deadline_time": "2026-08-21T17:15:00Z"}]}
    _mock_fpl(monkeypatch, current=[], chips=[], bootstrap=boot, teaser="fail")
    out = fc.career(424242)
    assert len(out["past_seasons"]) == 3
    assert out["summary"]["all_time_points"] == 2001 + 2210 + 1381
    lat = out["latest_season"]
    assert lat["available"] is False
    assert "2026-08-21" in lat["note"] and "GW1" in lat["note"]
    # Teaser failaa → jätetään POIS, ei placeholderia
    assert "model_teaser" not in out


def test_preseason_note_survives_bootstrap_failure(monkeypatch):
    _mock_fpl(monkeypatch, current=[], chips=[], bootstrap=None, teaser="fail")
    out = fc.career(424242)  # bootstrap 503 EI kaada vastausta
    assert out["latest_season"]["available"] is False
    assert out["latest_season"]["note"]


def test_brand_new_entry_no_history(monkeypatch):
    _mock_fpl(monkeypatch, past=[], current=[], chips=[], teaser="fail")
    out = fc.career(424242)
    assert out["past_seasons"] == []
    assert out["summary"]["seasons_played"] == 0
    assert out["summary"]["all_time_points"] == 0
    assert out["summary"]["best_season"] is None
    assert out["summary"]["since"] == 2023  # joined_time-fallback
    assert out["latest_season"]["available"] is False


# ---------------------------------------------------------------------------
# Teaser + virhepolut
# ---------------------------------------------------------------------------

def test_model_teaser_present_when_squad_importable(monkeypatch):
    _mock_fpl(monkeypatch)
    out = fc.career(424242)
    t = out["model_teaser"]
    assert t["team_xp_gw"] == 52.2 and t["percentile"] == 89.4
    assert t["rating_method"] == "vs_optimal_budget_team"  # #50, EI random


def test_unknown_entry_404(monkeypatch):
    _mock_fpl(monkeypatch)
    with pytest.raises(fc.RateTeamError) as e:
        fc.career(999999)
    assert e.value.status_code == 404
    assert "999999" in e.value.detail


# ---------------------------------------------------------------------------
# Endpoint-smoke (TestClient)
# ---------------------------------------------------------------------------

def test_endpoint_career(client, monkeypatch):
    _mock_fpl(monkeypatch)
    r = client.get("/api/fantasy/career?entry=424242")
    assert r.status_code == 200
    b = r.json()
    assert b["manager"]["name"] == "Ville Test"
    assert b["summary"]["seasons_played"] == 3
    assert r.headers["cache-control"] == "no-store"


def test_endpoint_career_requires_entry(client):
    r = client.get("/api/fantasy/career")
    assert r.status_code == 422  # FastAPI: pakollinen query-param puuttuu


def test_endpoint_career_unknown_entry(client, monkeypatch):
    _mock_fpl(monkeypatch)
    r = client.get("/api/fantasy/career?entry=999999")
    assert r.status_code == 404


def test_kesken_oleva_kierros_ei_paady_kortille_lopullisena(monkeypatch):
    """🔴 Portin 15. kierros: JULKINEN JAKOKORTTI JULKAISI PROVISIONAALISEN
    KIERROKSEN LOPULLISENA.

    `_latest_season`in `finished` koskee KAUTTA, ei kierrosta, eika tama
    moduuli tuonut `fpl_gw_finality`a lainkaan. Mitattu tuotannosta 7.9
    (entry 116920, GW3 finished=False, data_checked=False): kortti sanoi
    "Best overall rank 659,556" ja "This season 207 pts" GW3:n
    provisionaalisesta rivista, samalla kun SAMAN TUOTTEEN Season target
    -rivi sanoi "After GW2: 2,090,418 overall". Kerroin 3,2, ja `207`
    liikkuu kun bonukset laskeutuvat.
    """
    kesken = {"events": [{"id": g, "finished": True, "data_checked": True}
                         for g in range(1, 38)]
              + [{"id": 38, "finished": False, "data_checked": False}]}
    _mock_fpl(monkeypatch, bootstrap=kesken)
    out = fc.career(424242)

    assert out["summary"]["provisional_gws_excluded"] == [38]
    # GW38:n pisteet eivat ole kausisummassa.
    lat = out["latest_season"]
    assert all(g["gw"] != 38 for g in lat["gws"])
    # Eika sen sijoitus best/avg-luvuissa.
    assert lat["best_gw"]["gw"] != 38 and lat["worst_gw"]["gw"] != 38

    # NEGATIIVINEN KONTROLLI: kun kierros on valmis, se on mukana.
    _mock_fpl(monkeypatch, bootstrap=BOOTSTRAP_KAIKKI_VALMIIT)
    valmis = fc.career(424242)
    assert valmis["summary"]["provisional_gws_excluded"] == []
    assert any(g["gw"] == 38 for g in valmis["latest_season"]["gws"])


def test_ilman_bootstrapia_ei_julkaista_yhtaan_kierrosta(monkeypatch):
    """FAIL-CLOSED: jos emme saa bootstrapia, emme voi todistaa yhtaan
    kierrosta lopulliseksi. Mieluummin puuttuva luku kuin vaara kuvassa.

    🔴 Portin 16. kierros: TAMA TESTI MITTASI VAIN DIAGNOSTIIKKAKENTTAA.
    Se assertoi `provisional_gws_excluded`in eika katsonut mita LUKIJA nakee
    - ja lukija sai lauseen *"The new FPL season has not started yet"*
    vaikka hanella oli 38 kierrosta pelattuna, seka `all_time_points`in
    josta koko kuluva kausi oli pudonnut hiljaa.
    """
    _mock_fpl(monkeypatch, bootstrap=None)
    out = fc.career(424242)
    lat = out["latest_season"]
    assert out["summary"]["provisional_gws_excluded"], (
        "ilman finality-tietoa kierrokset on merkittava pois")

    # Ja se mita lukija NAKEE. 🔴 Portin 17. kierros: 16. kierros antoi tahan
    # lauseen *"GW38 is under way"*, joka on VAITE kierroksen tilasta. Emme
    # saaneet bootstrapia, joten emme tiedä sitä - kierros saattoi olla
    # gradattu viikkoja sitten. Nyt: emme sano kierroksesta mitaan.
    assert lat["season_state"] == "unconfirmed", lat.get("season_state")
    assert "has not started" not in (lat.get("note") or ""), lat["note"]
    assert "under way" not in (lat.get("note") or ""), lat["note"]
    assert "not answering" in (lat.get("note") or ""), lat["note"]

    # Kausi on silti PELATTU: laskuri ei saa pudottaa sita.
    _mock_fpl(monkeypatch, bootstrap=BOOTSTRAP_KAIKKI_VALMIIT)
    valmis = fc.career(424242)
    assert out["summary"]["seasons_played"] == valmis["summary"]["seasons_played"], (
        "kausi katosi laskurista kun bootstrap puuttui")

    # Tama fikstuuri on kesavalitila (38 GW:ta, jo past-listassa), joten
    # uran summa on sama kummin pain. Kesken oleva kausi: ks. alla.
    assert out["summary"]["all_time_points"] == valmis["summary"]["all_time_points"]


def test_vahvistamaton_kausi_ei_kartuta_uran_summaa(monkeypatch):
    """🔴 Portin 17. kierros: `all_time_points` LASKI GRADAAMATTOMIA PISTEITA.

    16. kierros luki `kausi_summa`n SUODATTAMATTOMASTA listasta, jotta kausi
    ei katoaisi laskurista. Sivuvaikutus: kun yhtaan kierrosta ei ollut
    vahvistettu, uran summa sisalsi gradaamattomat pisteet samalla kun
    kortin viereinen solu sanoi *"Not final yet"*. Sama kuva, kaksi
    vastausta.

    Nyt: kausi lasketaan pelatuksi (`seasons_played` +1) mutta sen panos
    pisteisiin on 0, ja `all_time_provisional` kertoo sen pinnalle.
    """
    kesken = [dict(CURRENT_FULL[0], event=1, total_points=60)]
    gw1_kesken = {"events": [{"id": 1, "finished": False, "data_checked": False}]}
    gw1_valmis = {"events": [{"id": 1, "finished": True, "data_checked": True}]}
    vain_menneet = sum(x["total_points"] for x in PAST)

    _mock_fpl(monkeypatch, current=kesken, bootstrap=gw1_kesken)
    out = fc.career(424242)
    assert out["summary"]["all_time_points"] == vain_menneet, (
        "gradaamattomat pisteet paatyivat uran summaan")
    assert out["summary"]["all_time_provisional"] is True
    assert out["summary"]["seasons_played"] == len(PAST) + 1, (
        "kausi katosi laskurista - se on pelattu vaikka pisteet ovat kesken")

    # NEGATIIVINEN KONTROLLI: sama kausi gradattuna. Jos tama ei eroa, testi
    # olisi vihrea siksi etta panos on aina 0.
    _mock_fpl(monkeypatch, current=kesken, bootstrap=gw1_valmis)
    ok = fc.career(424242)
    assert ok["summary"]["all_time_points"] == vain_menneet + 60
    assert ok["summary"]["all_time_provisional"] is False


def test_esikausi_ja_kesken_oleva_kausi_ovat_eri_lauseet(monkeypatch):
    """`available=False` tarkoitti kahta eri asiaa: "kausi ei ole alkanut"
    ja "kausi on alkanut mutta mitaan ei ole viela gradattu". Kortti sanoi
    molemmissa *"New season · Starts GW1"*."""
    # 🔴 PORTIN 18. KIERROS (B2): aito esikausi vaatii etta KAUSI ei ole
    # alkanut - ei vain etta kayttajan lista on tyhja. Tama fikstuuri kaytti
    # ennen bootstrapia jossa kaikki kierrokset olivat valmiita, eli se
    # vaitti esikautta keskella kautta.
    esikausi_boot = {"events": [
        {"id": 1, "finished": False, "data_checked": False, "is_next": True,
         "deadline_time": "2026-08-14T17:30:00Z"}]}
    _mock_fpl(monkeypatch, current=[], bootstrap=esikausi_boot)
    esikausi = fc.career(424242)["latest_season"]
    assert esikausi["season_state"] == "not_started"
    assert "has not started" in esikausi["note"]
    assert "GW1 deadline is 2026-08-14" in esikausi["note"], esikausi["note"]

    # Kesken kautta liittynyt manageri: `current` on tyhja, mutta KAUSI on
    # alkanut. Mitattu tuotannosta 7.9 (entryt 10462380 ja 10542666): kortti
    # sanoi naille *"The new FPL season has not started yet"* kun GW3 oli
    # pelattavana. Vaite on kaudesta, ja se oli vaara.
    kesken_boot = {"events": [
        {"id": 1, "finished": True, "data_checked": True},
        {"id": 2, "finished": True, "data_checked": True},
        {"id": 3, "finished": False, "data_checked": False, "is_current": True},
        {"id": 4, "finished": False, "data_checked": False, "is_next": True,
         "deadline_time": "2026-09-12T17:30:00Z"}]}
    _mock_fpl(monkeypatch, current=[], bootstrap=kesken_boot)
    liittyja = fc.career(424242)["latest_season"]
    assert liittyja["season_state"] == "no_gameweeks_yet", liittyja
    assert "has not started" not in liittyja["note"], liittyja["note"]
    assert "No scored gameweeks yet" in liittyja["note"], liittyja["note"]

    # Kausi kaynnissa, GW1 kesken.
    gw1_kesken = {"events": [{"id": 1, "finished": False, "data_checked": False}]}
    _mock_fpl(monkeypatch, current=[CURRENT_FULL[0]], bootstrap=gw1_kesken)
    kesken = fc.career(424242)["latest_season"]
    assert kesken["season_state"] == "no_final_gw_yet"
    assert "has not started" not in kesken["note"], kesken["note"]
    assert kesken["provisional_gws"] == [1]


def test_career_kortti_renderoi_neton():
    """🔴 Portin 16. kierros: `career.html:558` oli VARTIOIMATON, ja mutaatio
    (`points_net` -> `points`) lapaisi 3 213 testia.

    RAJOITE, sanottuna auki: tama on merkkijonotesti, koska `career.html` on
    selainpuolen JS jota pytest ei aja. Arvopuoli on katettu erikseen
    (`test_summer_dedup_and_summary` mittaa etta `best_gw.points_net` on
    oikein ja etta VALINTA tehdaan netosta). Tama testi vartioi vain sita
    etta kortti lukee oikeaa kenttaa - ja negatiivinen kontrolli antaa sille
    hampaat.
    """
    html = (pathlib.Path(__file__).resolve().parents[1] / "career.html").read_text(
        encoding="utf-8")
    assert "lat.best_gw.points_net" in html, (
        "kortti lukee bruttoa; `total_points` sen vieressa on netto")
    # Negatiivinen kontrolli: paljas brutto ilman netto-haaraa ei kelpaa.
    import re
    for m in re.finditer(r"best GW: ' \+ ([^;]+?) \+ ' pts'", html):
        assert "points_net" in m.group(1), m.group(1)

    # Ja se mita kortti sanoo kun kierros on jatetty pois.
    assert "still being scored" in html, (
        "kortti ei kerro miksi luku eroaa lukijan omasta FPL-sivusta")
    assert "Not final yet" in html, (
        "kausi kaynnissa ilman gradattua kierrosta nayttaisi 'Starts GW1'")


def test_chipit_pysahtyvat_samaan_kierrokseen_kuin_luvut(monkeypatch):
    """M7: chip-suodatin oli vartioimaton ja mutaatio lapaisi koko sarjan.

    Vastaus ei saa sanoa "wildcard GW3" samalla kun luvut pysahtyvat
    GW2:een: silloin sama nakyma vastaa kahdesta eri kierroksesta ja lukija
    paattelee etta GW3 on mukana pisteissa. Sama yksi lukija (`final_gws`)
    molemmille.
    """
    current = [dict(CURRENT_FULL[i], event=i + 1, total_points=(i + 1) * 60)
               for i in range(3)]
    chips = [{"name": "wildcard", "time": "x", "event": 2},
             {"name": "3xc", "time": "x", "event": 3}]
    events = {"events": [
        {"id": 1, "finished": True, "data_checked": True},
        {"id": 2, "finished": True, "data_checked": True},
        {"id": 3, "finished": True, "data_checked": False},  # kesken
    ]}
    _mock_fpl(monkeypatch, current=current, chips=chips, bootstrap=events)
    lat = fc.career(424242)["latest_season"]
    gws = [c["gw"] for c in lat["chips_used"]]
    assert gws == [2], f"kesken olevan kierroksen chip paatyi vastaukseen: {gws}"

    # NEGATIIVINEN KONTROLLI: kun GW3 on gradattu, chip ON mukana - muuten
    # testi olisi vihrea siksi etta chip-lista on aina lyhyt.
    kaikki = {"events": [dict(e, data_checked=True) for e in events["events"]]}
    _mock_fpl(monkeypatch, current=current, chips=chips, bootstrap=kaikki)
    lat2 = fc.career(424242)["latest_season"]
    assert [c["gw"] for c in lat2["chips_used"]] == [2, 3]


def test_osittain_vahvistettu_kausi_merkitaan_myos_vajaaksi(monkeypatch):
    """🔴 PORTIN 18. KIERROS (B1). Lippu oli `not available`, eli se laukesi
    vain siina harvinaisessa tilassa jossa yhtaan kierrosta ei ole
    vahvistettu. Tavallinen tila on "osa pudotettu", ja siina summa oli vajaa
    mutta label paljas.

    Mitattu tuotannosta 7.9 (entry 116920): kortti nayttti 149 pisteella
    labelilla *"All-time points"* kun lukijan oma FPL-sivu sanoi 221.
    """
    current = [dict(CURRENT_FULL[i], event=i + 1, total_points=(i + 1) * 60)
               for i in range(3)]
    boot = {"events": [
        {"id": 1, "finished": True, "data_checked": True},
        {"id": 2, "finished": True, "data_checked": True},
        {"id": 3, "finished": True, "data_checked": False}]}  # kesken
    _mock_fpl(monkeypatch, current=current, bootstrap=boot)
    out = fc.career(424242)
    lat, sm = out["latest_season"], out["summary"]
    assert lat["available"] is True, "GW1-2 on vahvistettu, kauden pitaa nakya"
    assert sm["provisional_gws_excluded"] == [3]
    assert sm["all_time_provisional"] is True, (
        "vajaa summa merkittiin taydelliseksi")
    assert sm["all_time_through_gw"] == 2
    assert sm["all_time_points"] == sum(x["total_points"] for x in PAST) + 120

    # NEGATIIVINEN KONTROLLI: kun kaikki kolme on vahvistettu, lippu on False
    # ja luku on suurempi. Ilman tata testi voisi olla vihrea siksi etta
    # lippu on aina True.
    kaikki = {"events": [dict(e, data_checked=True) for e in boot["events"]]}
    _mock_fpl(monkeypatch, current=current, bootstrap=kaikki)
    ok = fc.career(424242)["summary"]
    assert ok["all_time_provisional"] is False
    assert ok["all_time_through_gw"] == 3
    assert ok["all_time_points"] == sum(x["total_points"] for x in PAST) + 180


def test_jokainen_saatavuustila_kantaa_kaannosavaimen():
    """🔴 Portin 18. kierros (lisaloydos): `latest_season.note` renderoitiin
    mobiilissa RAAKANA, ja se on vain englanniksi - es/pt-lukija sai
    englanninkielisen lauseen keskelle kaannettya nakymaa.

    Invariantti mitataan JOKAISESTA haarasta, ei siita jonka satun ajamaan
    (saanto 6a kohta 3). Uusi haara ilman avainta kaataa taman.
    """
    tapaukset = [
        ([], [], [3], False, None),                       # unconfirmed
        # Bootstrap alhaalla JA kayttajalla ei yhtaan kierrosta: emme tieda
        # onko kausi alkanut, joten emme saa sanoa etta se ei ole.
        ([], [], None, False, None),                      # unconfirmed
        ([], [], [3], True, None),                        # no_final_gw_yet
        ([], [], None, True,                              # not_started
         [{"id": 1, "finished": False, "is_next": True,
           "deadline_time": "2026-08-14T17:30:00Z"}]),
        # Kesken kausi = seka valmiita etta valmistumattomia kierroksia.
        # (Pelkka "kaikki valmiina" on KESAN tila, ei kesken oleva kausi.)
        ([], [], None, True,                              # no_gameweeks_yet
         [{"id": 1, "finished": True, "data_checked": True},
          {"id": 2, "finished": False, "data_checked": False}]),
    ]
    nahdyt = set()
    for current, past, pudotettu, vahv, events in tapaukset:
        out = fc._latest_season(current, past, pudotettu, vahv, events)
        tila = out["season_state"]
        nahdyt.add(tila)
        assert out.get("note_key"), f"{tila}: note_key puuttuu"
        assert out["note_key"].startswith("fantasy.career.note."), out["note_key"]
        assert out.get("note"), f"{tila}: englanninkielinen varapolku puuttuu"
        assert isinstance(out.get("note_params"), dict), tila
        # Parametrit tayttavat avaimen: jos avain sanoo gw, se on mukana.
        if "gw" in out["note_key"] or "GW" in out["note"]:
            pass  # deadline-muodot kantavat gw:n, tarkistetaan alla
    assert nahdyt == {"unconfirmed", "no_final_gw_yet", "not_started",
                      "no_gameweeks_yet"}, nahdyt

    # Ja parametrit ovat oikeat siella missa lause nimeaa kierroksen.
    kesken = fc._latest_season([], [], [3], True, None)
    assert kesken["note_params"] == {"gw": "3"}
    assert "GW3" in kesken["note"]

    # 🔴 Portin 21. kierros: kaksi poisjatettya kierrosta nimettiin YHTENA
    # (`max(pudotettu)`), eli lause myonsi yhden kun luku oli kahden verran
    # vajaa. Fikstuuri kantaa nyt kaksi, jotta yhden nimeaminen kaatuu.
    kaksi = fc._latest_season([], [], [3, 4], True, None)
    assert kaksi["note_params"] == {"gw": "3, GW4"}
    assert "GW3, GW4" in kaksi["note"], kaksi["note"]


def test_kesan_kausienvalinen_tila_ei_ole_kesken_oleva_kausi(monkeypatch):
    """🔴 PORTIN 19. KIERROS (F). `kausi_alkanut` palautti True heti kun
    JOKIN event oli `finished`. Kesalla bootstrap kantaa PAATTYNEEN kauden
    eventit (kaikki finished, `is_current` yha GW38:lla) sen jalkeen kun
    entryn `current` on nollattu - ja kortti sanoi silloin *"No scored
    gameweeks yet for this team"*, kun oikea vastaus on etta uusi kausi ei
    ole alkanut. B2 vaarinpain.

    Saanto 6a kohta 3: sama funktio KAIKISSA kauden vaiheissa, ei siina
    jossa vika sattui loytymaan.
    """
    kesa = {"events": [{"id": i, "finished": True, "data_checked": True,
                        "is_current": i == 38} for i in range(1, 39)]}
    esikausi = {"events": [{"id": i, "finished": False, "data_checked": False,
                            "is_next": i == 1,
                            "deadline_time": "2027-08-13T17:30:00Z"}
                           for i in range(1, 39)]}
    kesken = {"events": [{"id": i, "finished": i <= 3, "data_checked": i <= 3,
                          "is_current": i == 4} for i in range(1, 39)]}
    gw1_kaynnissa = {"events": [{"id": i, "finished": False,
                                 "data_checked": False, "is_current": i == 1}
                                for i in range(1, 39)]}

    assert fc.kausi_alkanut(kesa["events"]) is False, "kesa luettiin kaudeksi"
    assert fc.kausi_alkanut(esikausi["events"]) is False
    assert fc.kausi_alkanut(kesken["events"]) is True
    assert fc.kausi_alkanut(gw1_kaynnissa["events"]) is True
    assert fc.kausi_alkanut([]) is False

    # Ja se mita LUKIJA nakee kesalla: ei "tama joukkue ei ole pelannut".
    _mock_fpl(monkeypatch, current=[], bootstrap=kesa)
    lat = fc.career(424242)["latest_season"]
    assert lat["season_state"] == "not_started", lat
    assert "No scored gameweeks yet" not in lat["note"], lat["note"]


def test_vajaa_summa_kantaa_aina_ikkunan(monkeypatch):
    """🔴 PORTIN 19. KIERROS (B1 elaa yha). Kolme pintaa gateasi labelin
    ehdolla `provisional && through_gw`, joten kun yhtaan kierrosta ei ollut
    vahvistettu (`through_gw` None) ne putosivat takaisin PALJAASEEN
    "All-time points" -labeliin - ja silloin puuttui KOKO kausi, ei osa.

    INVARIANTTI: jos lippu on tosi, ikkuna on olemassa (kierros tai kausi).
    Mitataan kaikissa neljassa bootstrap-vaiheessa.
    """
    cur = [dict(CURRENT_FULL[i], event=i + 1, total_points=(i + 1) * 60)
           for i in range(2)]
    vaiheet = {
        "bootstrap alhaalla": None,
        "0 vahvistettua": {"events": [
            {"id": 1, "finished": True, "data_checked": False},
            {"id": 2, "finished": False, "data_checked": False}]},
        "1/2 vahvistettu": {"events": [
            {"id": 1, "finished": True, "data_checked": True},
            {"id": 2, "finished": True, "data_checked": False}]},
        "kaikki vahvistettu": {"events": [
            {"id": 1, "finished": True, "data_checked": True},
            {"id": 2, "finished": True, "data_checked": True},
            {"id": 3, "finished": False, "data_checked": False}]},
    }
    nahty_gw = nahty_kausi = False
    for nimi, boot in vaiheet.items():
        _mock_fpl(monkeypatch, current=cur, bootstrap=boot)
        sm = fc.career(424242)["summary"]
        if not sm["all_time_provisional"]:
            continue
        ikkuna = (sm.get("all_time_through_gw"),
                  sm.get("all_time_through_season"))
        assert any(x is not None for x in ikkuna), (
            f"{nimi}: luku on vajaa mutta ikkunaa ei ole -> pinta nayttaa "
            f"paljaan labelin taydelliselta")
        assert sm["all_time_points"] > 0, nimi
        nahty_gw |= ikkuna[0] is not None
        nahty_kausi |= ikkuna[1] is not None

    # Kontrolli: molemmat ikkunamuodot esiintyivat, eli testi ei ole vihrea
    # siksi etta vain toinen haara ajettiin.
    assert nahty_gw and nahty_kausi, (nahty_gw, nahty_kausi)


def test_ensimmaisen_kauden_manageri_ei_saa_nayttaa_nollaa(monkeypatch):
    """🔴 PORTIN 20. KIERROS. Invariantti "ikkuna on aina olemassa kun lippu
    on tosi" on VAARA yhdessa tilassa: ensimmaisen kauden manageri, jolla ei
    ole yhtaan `past`-kautta eika yhtaan vahvistettua kierrosta. Silloin
    `all_time_points` on 0 ja MOLEMMAT ikkunat None.

    Edellinen invarianttitesti oli vihrea vain koska sen fikstuurilla oli
    past-kausia - se ei mitannut ainoaa tilaa jossa invariantti hajoaa
    (muisti: portin-fikstuuri-kirjoitetaan-korjatusta-tapauksesta).

    Oikea invariantti EI ole "ikkuna on aina olemassa" vaan: **jos ikkunaa ei
    ole, lukua ei nayteta**. Pintojen puoli on omissa testeissaan
    (`test_career_card_render.py`, `lib/careerNoteKeys.test.ts`); tama
    lukitsee sen etta backend kertoo tilan erottuvasti.
    """
    cur = [dict(CURRENT_FULL[i], event=i + 1, total_points=(i + 1) * 60)
           for i in range(2)]
    boot = {"events": [{"id": 1, "finished": True, "data_checked": False},
                       {"id": 2, "finished": False, "data_checked": False}]}
    _mock_fpl(monkeypatch, past=[], current=cur, bootstrap=boot)
    sm = fc.career(424242)["summary"]

    assert sm["all_time_points"] == 0
    assert sm["all_time_provisional"] is True
    assert sm["all_time_through_gw"] is None
    assert sm["all_time_through_season"] is None
    # Kausi on silti PELATTU - laskuri ei saa kadota vaikka pisteet ovat 0.
    assert sm["seasons_played"] == 1

    # NEGATIIVINEN KONTROLLI: sama manageri kun GW1 vahvistetaan. Luku ja
    # ikkuna ilmestyvat, eli 0 oli tilan seuraus eika vakio.
    boot["events"][0]["data_checked"] = True
    _mock_fpl(monkeypatch, past=[], current=cur, bootstrap=boot)
    ok = fc.career(424242)["summary"]
    assert ok["all_time_points"] == 60
    assert ok["all_time_through_gw"] == 1
