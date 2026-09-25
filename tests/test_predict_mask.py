"""PREDICT-API-MASK (22.9.2026): palvelinmaski /api/predict, /api/predict-wc
ja /api/parlay -endpointeille, `PREDICT_MASK`-lipun takana (oletus pois).

MITATTU 22.9 tuotannosta: kirjautumaton `POST /api/predict` palautti koko
Premium-sisallon (xG, top_scores, O/U 2.5, BTTS, fair value, form_trend,
h2h_summary). Raja oli vain kayttoliittymassa. Seitsemas kerta samaa
vikaluokkaa (captain 15.8, replacements 2.9, value 4.9, rate-team 5.9,
defcon-leaders 17.9, compare 18.9).

Testit lukitsevat neljä asiaa:

  1. **Lippu pois = ei uutta koodipolkua.** Vastaus on tavu tavulta sama kuin
     Premium-vastaus, eika tokenia tai admin-tokenia edes tarkisteta
     (Supabase-kutsu tai viive ei voi syntya).
  2. **Lippu paalla + ei oikeutta = ei yhtaan Premium-arvoa**, ja fikstuuri on
     EROTTELEVA: maskaamattomassa vastauksessa jokaisella Premium-kentalla on
     aito arvo, joten "kentta oli tyhja joka tapauksessa" ei voi lapaista.
  3. **Tyypit sailyvat.** Maskattu runko validoituu samalla mallilla, ja
     jokaisen kentan JSON-tyyppi on sama (vanha klientti kutsuu
     `expected_goals_home.toFixed(2)`).
  4. **Kutsupaikka, ei vain funktio.** Testit ajavat endpointin HTTP:n yli;
     mutaatiot (maskikutsun poisto endpointista) on kirjattu raporttiin
     goaliq-app/cos-reports/cc-reports/2026-09-22-predict-api-mask.md.

Lisaksi accuracy_pipeline: se logaa live-/api/predictin xG:n julkiseen track
recordiin, joten maskattu vastaus ei saa koskaan paatya lokiin.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

HOME, AWAY = "Brazil", "France"
PREDICT_BODY = {"home_team": HOME, "away_team": AWAY,
                "leagues": ["ENG-Premier League"]}
WC_BODY = {"home_team": HOME, "away_team": AWAY}
WC = {"leagues": ["INT-World Cup"], "seasons": ["2018", "2022"]}
PARLAY_BODY = {"legs": [
    {"home_team": "Brazil", "away_team": "France", "pick": "1", **WC},
    {"home_team": "Mexico", "away_team": "South Africa", "pick": "1", **WC},
    {"home_team": "Tunisia", "away_team": "Congo DR", "pick": "X", **WC},
]}
ENDPOINTS = [("/api/predict", PREDICT_BODY), ("/api/predict-wc", WC_BODY)]
ADMIN = "adm-test-" + "0123456789abcdef"


def _synthetic_matches() -> pd.DataFrame:
    """Kolme keskinaista + kummallekin muita otteluita.

    EROTTELEVA fikstuuri: h2h_summary.total_matches = 3 ja kummankin
    form_trend >= 2 ottelua, eli maskaamattomassa vastauksessa nama kentat
    ovat EPATYHJIA. Ilman tata "maskattu = tyhja" -vaite lapaisisi myos
    silloin kun data vain sattui olemaan tyhja.
    """
    rows = [
        ("2022-12-09", "Brazil", "France", 1, 1),
        ("2021-06-01", "France", "Brazil", 2, 0),
        ("2019-03-20", "Brazil", "France", 3, 1),
        ("2023-03-25", "Brazil", "Morocco", 1, 2),
        ("2023-06-17", "Brazil", "Guinea", 4, 1),
        ("2023-09-08", "Bolivia", "Brazil", 1, 5),
        ("2023-03-24", "France", "Netherlands", 4, 0),
        ("2023-06-16", "Gibraltar", "France", 0, 3),
        ("2023-09-07", "France", "Ireland", 2, 0),
    ]
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team",
                                     "home_score", "away_score"])
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture()
def pm_client(monkeypatch):
    """TestClient ilman domestic-fittia ja ilman verkkoa.

    `_saa_malli` palauttaa esirakennetun WC-mallin (oikea DixonColesModel,
    ei fittia), ja otteludata on synteettinen. Luottamuslippu on asetettu
    kotijoukkueelle, jotta ilmaiskentta `data_confidence` on epatyhja ja sen
    SAILYMINEN maskissa on mitattavissa.
    """
    import api.main as m
    import api.premium as prem
    from src.data.international_results import load_wc_model

    df = _synthetic_matches()
    monkeypatch.setattr(m, "_saa_malli", lambda *a, **k: load_wc_model())
    monkeypatch.setattr(m, "_lataa_otteludata_cached",
                        lambda liigat, kaudet: df.copy())
    monkeypatch.setattr(m, "_load_team_confidence", lambda: {
        HOME: {"model_team": HOME, "minutes_churn_pct": 41.0,
               "flag": "high_turnover", "note": "synthetic note"}})
    for name in ("PREDICT_MASK", "PREMIUM_ENFORCE", "ADMIN_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    # Ilmaisikkuna kiinni oletuksena: vaihetta mitataan erikseen alla.
    monkeypatch.setattr(prem, "free_premium_window_active", lambda: False)
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()
    yield TestClient(m.app)
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()


def _mask_on(monkeypatch):
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setenv("PREDICT_MASK", "on")


def _as_premium(monkeypatch) -> dict:
    """Token kulkee koko polun (verify -> profiili) kuten tuotannossa."""
    import api.premium as prem
    monkeypatch.setattr(prem, "_verify_token_user_id", lambda t: "user-1")
    monkeypatch.setattr(prem, "_profile_is_premium", lambda uid: True)
    return {"Authorization": "Bearer premium-ok"}


def _as_logged_in_free(monkeypatch) -> dict:
    import api.premium as prem
    monkeypatch.setattr(prem, "_verify_token_user_id", lambda t: "user-free")
    monkeypatch.setattr(prem, "_profile_is_premium", lambda uid: False)
    monkeypatch.setattr(prem, "_web_subscription_active", lambda uid: False)
    return {"Authorization": "Bearer free-user"}


def _post(client, path, body, headers=None):
    r = client.post(path, json=body, headers=headers or {})
    assert r.status_code == 200, r.text
    return r


def _full(client, monkeypatch, path, body):
    """Maskaamaton vertailukohta: lippu pois."""
    monkeypatch.delenv("PREDICT_MASK", raising=False)
    return _post(client, path, body)


# ---------------------------------------------------------------------------
# 1. Lippu pois: ennallaan, eika uutta koodipolkua
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,body", ENDPOINTS + [("/api/parlay", PARLAY_BODY)])
@pytest.mark.parametrize("enforce", ["on", "off"])
def test_flag_off_never_checks_identity(pm_client, monkeypatch, path, body,
                                        enforce):
    """Lippu pois -> tokenia eika admin-tokenia tarkisteta LAINKAAN.

    Tama on vahvin in-process-todiste siita etta vastaus on ennallaan: maskin
    ainoa uusi koodi on `predict_mask_on()`, ja kun se on False, identiteetin
    tarkistukset (Supabase-kutsu, 5 min cache) eivat edes kaynnisty.
    """
    import api.premium as prem

    def rajahda(*a, **k):
        raise AssertionError("identiteettia tarkistettiin vaikka lippu on pois")

    monkeypatch.setenv("PREMIUM_ENFORCE", enforce)
    monkeypatch.setattr(prem, "is_premium_request", rajahda)
    monkeypatch.setattr(prem, "is_admin_request", rajahda)
    d = _post(pm_client, path, body,
              {"Authorization": "Bearer x", "X-Admin-Token": "y"}).json()
    assert "meta" not in d


@pytest.mark.parametrize("path,body", ENDPOINTS)
def test_flag_off_contract_unchanged(pm_client, monkeypatch, path, body):
    """Lippu pois + anonyymi: tasan PredictionResponsen kentat, ei metaa,
    ja Premium-kentilla aidot arvot (fikstuuri on erotteleva)."""
    from api.main import PredictionResponse
    from api.premium import PREDICTION_PREMIUM_FIELDS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    d = _post(pm_client, path, body).json()
    assert list(d) == list(PredictionResponse.model_fields), (
        "avaimet tai niiden jarjestys muuttui lippu pois -tilassa")
    for key, masked_value in PREDICTION_PREMIUM_FIELDS.items():
        assert d[key] != masked_value, (
            f"{key}: maskaamaton arvo on sama kuin maskattu - fikstuuri ei "
            "erottele, eli maskitesti mittaisi tyhjaa dataa")


def test_flag_off_parlay_contract_unchanged(pm_client, monkeypatch):
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    b = _post(pm_client, "/api/parlay", PARLAY_BODY).json()
    assert set(b) == {"legs", "n_legs", "combined_probability",
                      "assumes_independence", "note", "disclaimer"}
    assert len(b["legs"]) == 3 and b["combined_probability"] > 0


# ---------------------------------------------------------------------------
# 2. Lippu paalla + ei oikeutta: ei yhtaan Premium-arvoa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,body", ENDPOINTS)
@pytest.mark.parametrize("who", ["anonymous", "invalid_token", "logged_in_free"])
def test_mask_on_hides_every_premium_field(pm_client, monkeypatch, path, body,
                                           who):
    """Lippu paalla, ei Premiumia -> jokainen Premium-kentta on maskattu ja
    jokainen ilmaiskentta on TASMALLEEN sama kuin taydessa vastauksessa."""
    from api.premium import PREDICTION_FREE_FIELDS, PREDICTION_PREMIUM_FIELDS

    import api.premium as prem

    full = _full(pm_client, monkeypatch, path, body).json()
    _mask_on(monkeypatch)
    if who == "anonymous":
        headers = {}
    elif who == "invalid_token":
        monkeypatch.setattr(prem, "_verify_token_user_id", lambda t: None)
        headers = {"Authorization": "Bearer ei-kelpaa"}
    else:
        headers = _as_logged_in_free(monkeypatch)
    d = _post(pm_client, path, body, headers).json()

    assert d["meta"]["masked"] is True
    assert d["meta"]["premium_fields"] == list(PREDICTION_PREMIUM_FIELDS)
    leaked = [k for k, v in PREDICTION_PREMIUM_FIELDS.items() if d[k] != v]
    assert not leaked, f"Premium-kentta vuoti ilmaiselle: {leaked}"
    changed = [k for k in PREDICTION_FREE_FIELDS if d[k] != full[k]]
    assert not changed, f"ilmaiskentta muuttui maskissa: {changed}"
    # Ilmaisosuus on oikeasti olemassa (ei tyhja kuori).
    assert d["p_home_win"] > 0 and d["h2h"], "ilmainen ydin puuttuu"
    if path == "/api/predict":
        assert d["data_confidence"], "luottamuslippu katosi maskissa"


@pytest.mark.parametrize("path,body", ENDPOINTS)
def test_masked_body_carries_no_premium_value(pm_client, monkeypatch, path,
                                              body):
    """Toinen, riippumaton vuototarkistus: yksikaan taydesta vastauksesta
    poimittu Premium-luku tai tulos ei esiinny maskatun vastauksen TEKSTISSA.
    Kenttakohtainen vertailu ei nakisi vuotoa uuteen, luokittelemattomaan
    avaimeen (esim. `meta`an kopioitu top_scores)."""
    import re

    full = _full(pm_client, monkeypatch, path, body).json()
    _mask_on(monkeypatch)
    masked = _post(pm_client, path, body).json()
    # Ihmisluettava selite ("over/under 2.5") ei ole data; kaikki muu on.
    masked["meta"].pop("mask")
    text = json.dumps(masked)
    numbers =[full[k] for k in ("expected_goals_home", "expected_goals_away",
                                 "p_over_2_5", "p_under_2_5", "p_btts_yes",
                                 "p_btts_no", "fair_odds_home",
                                 "fair_odds_away")]
    # Numerorajat: 0.531 ei saa osua lukuun 0.5312 tai 10.531.
    found = [n for n in numbers
             if re.search(r"(?<![\d.])" + re.escape(json.dumps(n)) + r"(?!\d)",
                          text)]
    found += [s["score"] for s in full["top_scores"]
              if json.dumps(s["score"]) in text]
    assert not found, f"Premium-arvo maskatussa vastauksessa: {found}"


def test_parlay_mask_on_anonymous(pm_client, monkeypatch):
    from api.premium import FREE_PARLAY_LEGS

    full = _full(pm_client, monkeypatch, "/api/parlay", PARLAY_BODY).json()
    _mask_on(monkeypatch)
    b = _post(pm_client, "/api/parlay", PARLAY_BODY).json()
    assert b["meta"]["masked"] is True
    assert len(b["legs"]) == FREE_PARLAY_LEGS == 0
    assert b["combined_probability"] == 0.0 != full["combined_probability"]
    # Kehys ja pyynnon kaiku sailyvat (ei mallin lukuja).
    for k in ("n_legs", "assumes_independence", "note", "disclaimer"):
        assert b[k] == full[k], k
    assert str(full["combined_probability"]) not in json.dumps(b)


# ---------------------------------------------------------------------------
# 3. Lippu paalla + oikeus: taysi vastaus, tavu tavulta sama
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,body", ENDPOINTS + [("/api/parlay", PARLAY_BODY)])
def test_mask_on_premium_gets_identical_bytes(pm_client, monkeypatch, path,
                                              body):
    full = _full(pm_client, monkeypatch, path, body).content
    _mask_on(monkeypatch)
    got = _post(pm_client, path, body, _as_premium(monkeypatch)).content
    assert got == full, "Premium-kayttaja sai eri vastauksen kuin ennen maskia"


@pytest.mark.parametrize("path,body", ENDPOINTS + [("/api/parlay", PARLAY_BODY)])
def test_admin_token_bypasses_mask(pm_client, monkeypatch, path, body):
    """accuracy_pipeline tunnistautuu X-Admin-Tokenilla (CI, ei Supabase-
    tilia). Vaara token ei ohita."""
    full = _full(pm_client, monkeypatch, path, body).content
    _mask_on(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    ok = _post(pm_client, path, body, {"X-Admin-Token": ADMIN}).content
    assert ok == full
    bad = _post(pm_client, path, body, {"X-Admin-Token": ADMIN + "x"}).json()
    assert bad["meta"]["masked"] is True


@pytest.mark.parametrize("window_open,expect_masked", [(False, True),
                                                       (True, False)])
def test_logged_in_free_user_follows_free_window(pm_client, monkeypatch,
                                                 window_open, expect_masked):
    """Vaihe-invariantti (saanto 6a, mekanismi 3): kirjautunut ilmaiskayttaja
    saa taydet ennusteet ilmaisikkunan aikana ja maskatut sen jalkeen. Sama
    lukija (is_premium_request) kuin fantasy-maskeissa, ei omaa kelloa."""
    import api.premium as prem

    _mask_on(monkeypatch)
    headers = _as_logged_in_free(monkeypatch)
    monkeypatch.setattr(prem, "free_premium_window_active", lambda: window_open)
    d = _post(pm_client, "/api/predict", PREDICT_BODY, headers).json()
    assert (d.get("meta", {}).get("masked") is True) is expect_masked


def test_mask_needs_premium_enforce(pm_client, monkeypatch):
    """Dokumentoitu riippuvuus: PREDICT_MASK=on mutta PREMIUM_ENFORCE=off ->
    is_premium_request palauttaa aina True eika maski laukea. Jos tama
    muuttuu, kaantoehto (raportti) on paivitettava."""
    monkeypatch.setenv("PREDICT_MASK", "on")
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    d = _post(pm_client, "/api/predict", PREDICT_BODY).json()
    assert "meta" not in d


# ---------------------------------------------------------------------------
# 4. Tyypit ja luokittelu
# ---------------------------------------------------------------------------

def _json_type(v) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    return type(v).__name__


@pytest.mark.parametrize("path,body", ENDPOINTS + [("/api/parlay", PARLAY_BODY)])
def test_masked_types_match_unmasked(pm_client, monkeypatch, path, body):
    """Jokaisen kentan JSON-tyyppi on sama maskattuna. null missaan kentassa
    kaataisi mobiilin `.toFixed()`-kutsun (XgStat, Adjust, ShareableCard,
    ParlayScreen), joten tama on klienttien kaatumattomuuden portti."""
    from api.main import ParlayResponse, PredictionResponse

    full = _full(pm_client, monkeypatch, path, body).json()
    _mask_on(monkeypatch)
    d = _post(pm_client, path, body).json()
    meta = d.pop("meta")
    assert meta["masked"] is True
    assert list(d) == list(full), "maski lisasi tai poisti avaimia"
    wrong = {k: (_json_type(full[k]), _json_type(d[k])) for k in full
             if _json_type(full[k]) != _json_type(d[k])}
    assert not wrong, f"tyyppi muuttui maskissa: {wrong}"
    model = ParlayResponse if path == "/api/parlay" else PredictionResponse
    model.model_validate(d)


def test_every_response_field_is_classified():
    """Saanto 6a, mekanismi 2: PredictionResponsen uusi kentta ei voi jaada
    luokittelematta. Ilman tata uusi Premium-kentta vuotaisi maskin ohi
    hiljaa, koska maski koskee vain nimettyja kenttia."""
    from api.main import PredictionResponse
    from api.premium import PREDICTION_FREE_FIELDS, PREDICTION_PREMIUM_FIELDS

    fields = set(PredictionResponse.model_fields)
    premium = set(PREDICTION_PREMIUM_FIELDS)
    assert not (premium & PREDICTION_FREE_FIELDS), "kentta molemmissa luokissa"
    unclassified = fields - premium - PREDICTION_FREE_FIELDS
    assert not unclassified, (
        f"luokittelematon PredictionResponse-kentta: {sorted(unclassified)}. "
        "Lisaa se api.premium.PREDICTION_PREMIUM_FIELDSiin (maskattu arvo) tai "
        "PREDICTION_FREE_FIELDSiin (perustelu kommenttiin).")
    stale = (premium | PREDICTION_FREE_FIELDS) - fields
    assert not stale, f"luokittelu viittaa poistettuun kenttaan: {stale}"


@pytest.mark.parametrize("raw,expected", [
    ("on", True), ("1", True), ("true", True), ("yes", True), ("ON", True),
    (" on ", True), ("off", False), ("", False), ("0", False), ("no", False),
])
def test_flag_values_match_premium_enforce(monkeypatch, raw, expected):
    from api.premium import predict_mask_on, premium_enforce_on

    monkeypatch.setenv("PREDICT_MASK", raw)
    monkeypatch.setenv("PREMIUM_ENFORCE", raw)
    assert predict_mask_on() is expected
    assert premium_enforce_on() is expected


def test_flag_default_is_off(monkeypatch):
    from api.premium import predict_mask_on

    monkeypatch.delenv("PREDICT_MASK", raising=False)
    assert predict_mask_on() is False


# ---------------------------------------------------------------------------
# 5. accuracy_pipeline: maskattu vastaus ei paady julkiseen lokiin
# ---------------------------------------------------------------------------

@pytest.fixture()
def pipeline_via_testclient(pm_client, monkeypatch):
    """Ohjaa putken `requests.post`in in-process-API:in. Kutsupaikka
    (`domestic_prematch_prediction`) ajetaan sellaisenaan: headerit, URL ja
    vastauksen jasennys kulkevat samaa polkua kuin CI:ssa."""
    import requests

    from scripts import accuracy_pipeline as ap

    def fake_post(url, json=None, headers=None, timeout=None):
        path = url.split("://", 1)[-1].split("/", 1)[1]
        return pm_client.post("/" + path, json=json, headers=headers or {})

    monkeypatch.setattr(requests, "post", fake_post)
    return ap


def test_pipeline_logs_real_xg_with_admin_token(pipeline_via_testclient,
                                                monkeypatch, pm_client):
    ap = pipeline_via_testclient
    full = _full(pm_client, monkeypatch, "/api/predict", PREDICT_BODY).json()
    _mask_on(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)   # sama secret palvelimella ja CI:ssa
    row = ap.domestic_prematch_prediction("ENG-Premier League", HOME, AWAY)
    assert row is not None
    assert row["xg_home"] == round(full["expected_goals_home"], 3) > 0
    assert row["most_likely_score"] == full["top_scores"][0]["score"]


def test_pipeline_refuses_masked_response(pipeline_via_testclient,
                                          monkeypatch):
    """Ilman admin-tokenia palvelin maskaa -> putki palauttaa None eika rivia
    jossa xG 0.0 ja tulos None. Tama on se vika joka olisi muuten
    kirjoittanut nollia julkiseen track recordiin hiljaa."""
    ap = pipeline_via_testclient
    _mask_on(monkeypatch)
    row = ap.domestic_prematch_prediction("ENG-Premier League", HOME, AWAY)
    assert row is None, f"maskattu vastaus logattiin: {row}"


def test_pipeline_refresh_keeps_old_row_when_masked(pipeline_via_testclient,
                                                    monkeypatch):
    """Pre-kickoff-refresh ei saa ylikirjoittaa hyvaa rivia nollilla."""
    ap = pipeline_via_testclient
    _mask_on(monkeypatch)
    rivi = {"league": "ENG-Premier League", "home_team": HOME,
            "away_team": AWAY, "xg_home": 1.5, "xg_away": 1.1,
            "most_likely_score": "1-1", "p_home": 0.4, "p_draw": 0.3,
            "p_away": 0.3, "predicted_winner": "home"}
    paivitetyt, ohitetut, _ = ap._apply_refresh(
        [rivi], ap.domestic_prematch_prediction)
    assert (paivitetyt, ohitetut) == (0, 1)
    assert rivi["xg_home"] == 1.5 and rivi["most_likely_score"] == "1-1"


def test_pipeline_headers_follow_env(monkeypatch):
    from scripts import accuracy_pipeline as ap

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert ap._predict_headers() == {}
    monkeypatch.setenv("ADMIN_TOKEN", " " + ADMIN + " ")
    assert ap._predict_headers() == {"X-Admin-Token": ADMIN}


def test_workflow_passes_admin_token_to_pipeline_step():
    """Putken token tulee workflow'sta. Jos env-rivi katoaa run-askeleesta,
    lippu paalla -> jokainen domestic-rivi ohitetaan VAROITUKSELLA ja track
    record jaatyy. Tama punastuu ennen sita."""
    from pathlib import Path

    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows"
          / "accuracy-log.yml").read_text(encoding="utf-8")
    alku = wf.index("- name: Log pre-match + reconcile + recompute aggregate")
    loppu = wf.index("run: python -m scripts.accuracy_pipeline run", alku)
    askel = wf[alku:loppu]
    assert "ADMIN_TOKEN: ${{ secrets.ADMIN_TOKEN }}" in askel


def test_regression_snapshot_flags_masked_prod(pm_client, monkeypatch):
    """scripts/regression_predict.snapshot (myos tests/update_golden.py:n
    tuotantovertailu) kutsuu tuotantoa anonyymina. Maskattu vastaus on
    tyypeiltaan identtinen, joten ilman merkintaa vertailu nayttaisi
    regressiolta. urlopen ohjataan in-process-API:in, jotta oikea `_post`
    (headerit mukaan lukien) on kutsupolulla."""
    import io
    import urllib.request

    from scripts import regression_predict as rp

    def fake_urlopen(req, timeout=None):
        path = "/" + req.full_url.split("://", 1)[-1].split("/", 1)[1]
        headers = {k: v for k, v in req.header_items()}
        r = pm_client.post(path, content=req.data, headers=headers)
        return io.BytesIO(r.content)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(rp, "CASES", [("ENG-Premier League", ["2425", "2526"],
                                       HOME, AWAY)])
    _mask_on(monkeypatch)
    key = f"ENG-Premier League|{HOME}-{AWAY}"
    assert "masked" in rp.snapshot("http://x")[key]["_error"]
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    rec = rp.snapshot("http://x")[key]
    assert "_error" not in rec and rec["expected_goals_home"] > 0


# ---------------------------------------------------------------------------
# 6. Kutsupaikkojen kattavuus (staattinen, ajotestien lisaksi)
# ---------------------------------------------------------------------------

MASKED_ENDPOINTS = {"/api/predict": "predict", "/api/predict-wc": "predict_wc",
                    "/api/parlay": "parlay"}


def test_every_prediction_endpoint_calls_the_mask():
    """Staattinen varmistus ajotestien rinnalla, AST-tasolla.

    🔴 MITATTU 22.9 rakentaessa: ensimmainen versio etsi merkkijonoa
    `predict_mask_applies(request)` rungosta ja oli VIHREA, vaikka
    /api/predict-wc:n runko palautti `return PredictionResponse(...)` ENNEN
    maskiehtoa. Maski oli kuollutta koodia; vain ajotesti nakyi sen.
    Siksi tama tarkistaa RAKENTEEN: maskiehto on rungon ylatasolla, sen
    edella ei ole yhtaan `return`ia, ja haara palauttaa `_masked_json`in.
    """
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).resolve().parents[1] / "api" / "main.py")
                     .read_text(encoding="utf-8"))
    funcs = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call) and dec.args
                        and isinstance(dec.args[0], ast.Constant)):
                    funcs[dec.args[0].value] = node
    for path, name in MASKED_ENDPOINTS.items():
        fn = funcs[path]
        assert fn.name == name, (path, fn.name)
        idx = next((i for i, st in enumerate(fn.body)
                    if isinstance(st, ast.If)
                    and "predict_mask_applies(request)" in ast.unparse(st.test)),
                   None)
        assert idx is not None, f"{path}: maskiehto puuttuu rungon ylatasolta"
        before = [st for st in fn.body[:idx] if isinstance(st, ast.Return)]
        assert not before, (f"{path}: return ennen maskiehtoa rivilla "
                            f"{before[0].lineno} - maski on kuollutta koodia")
        branch = ast.unparse(fn.body[idx])
        assert "return _masked_json(resp, mask_" in branch, path


def test_maski_paalla_on_vartioitu_tuotannossa():
    """25.9 PREDICT_MASK=on (Villen GO). Lipun oletus on pois, joten sen
    katoaminen (vrt. ympariston pyyhkiytyminen 20.9) ei kaada mitaan vaan
    avaa Premium-kentat hiljaa. Kaksi lukkoa: nimi pakollisissa ja tulos
    mitattuna env-health-watchissa. MUTAATIO: poista jompikumpi -> punainen."""
    from pathlib import Path
    import api.main as m
    assert "PREDICT_MASK" in m._PAKOLLISET_ENV
    wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows"
          / "env-health-watch.yml").read_text(encoding="utf-8")
    assert "https://api.goaliq.app/api/predict" in wf
    assert "get('meta',{}).get('masked')" in wf
