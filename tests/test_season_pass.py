"""Kertamaksuinen kausipassi 2026/27 (ulkoasu WP6, Villen paatos 1.11.2026).

Passi on 25 EUR:n kertamaksu, voimassa 2027-05-30T23:59:59Z asti, ei uusiudu.
Kertamaksusta ei tule paattymiswebhookia, joten oikeuden paattyminen on
LUKIJOIDEN vastuulla (`src.season_pass`). Siksi tama tiedosto mittaa saman
invariantin kolmessa vaiheessa (CLAUDE.md 6a kohta 3): sekuntia ennen loppua,
tasan loppuhetkella ja sen jalkeen. Testi joka ajettaisiin vain tanaan olisi
vihrea aina, koska tanaan passi on aina voimassa.

Lisaksi: kytkin pois (STRIPE_PRICE_SEASON_PASS_2026_27 tyhja) = tasan entinen
kaytos checkoutissa, webhookissa ja hinnoissa. Koodin voi siksi mergeta ennen
kuin Ville luo hinnan Stripeen.

Ei verkkoa: Supabase-REST ja Stripe mockataan (kuten test_web_checkout.py ja
test_stripe_web_webhook.py).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
import stripe

from src import season_pass as sp

PASS = sp.SEASON_PASS_ID
END = sp.SEASON_PASS_END
END_ISO = sp.SEASON_PASS_END_ISO

#: Synteettiset vaiheet. TODAY on ohjelman aloituspaiva (passi voimassa).
TODAY = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
BEFORE = END - timedelta(seconds=1)
AT = END
AFTER = END + timedelta(seconds=1)
LATER = datetime(2027, 8, 1, tzinfo=timezone.utc)

VOIMASSA = [TODAY, BEFORE]
PAATTYNYT = [AT, AFTER, LATER]


def _pass_row(**kw) -> dict:
    row = {"user_id": "u1", "plan": PASS, "status": "active",
           "current_period_end": END_ISO, "stripe_customer_id": "cus_1",
           "stripe_subscription_id": None}
    row.update(kw)
    return row


# ---------------------------------------------------------------------------
# 1. Vakio ja yksi lahde
# ---------------------------------------------------------------------------


def test_paattymishetki_on_paatetty_hetki():
    assert END == datetime(2027, 5, 30, 23, 59, 59, tzinfo=timezone.utc)
    # Kantaan kirjoitettava muoto johdetaan vakiosta, ei kirjoiteta uudelleen.
    assert END_ISO == "2027-05-30T23:59:59+00:00"
    assert sp.FIXED_END[PASS] is END
    # Avoimet oikeudet joita passin osto ei saa lyhentaa.
    assert sp.OPEN_ENDED_SOURCES == {"comp", "revenuecat"}


# ---------------------------------------------------------------------------
# 2. Profiilin lukija vaiheittain
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("now", VOIMASSA)
def test_passin_profiili_voimassa_ennen_loppua(now):
    assert sp.profile_premium(True, PASS, now) is True
    assert sp.profile_needs_expiry(True, PASS, now) is False


@pytest.mark.parametrize("now", PAATTYNYT)
def test_passin_profiili_paattyy_tasan_loppuhetkella_ja_jalkeen(now):
    # Lippu on jaanyt paalle (webhookia ei tule), lukija ei silti anna sita.
    assert sp.profile_premium(True, PASS, now) is False
    assert sp.profile_needs_expiry(True, PASS, now) is True


@pytest.mark.parametrize("source", ["stripe_web", "revenuecat", "comp", None, ""])
@pytest.mark.parametrize("now", VOIMASSA + PAATTYNYT)
def test_muut_lahteet_eivat_muutu_missaan_vaiheessa(source, now):
    # Vuosi- ja kuukausitilaus, kaupan tilaus ja comp: purku on webhookin
    # tehtava kuten ennen. Passin loppu ei saa koskea niihin.
    assert sp.profile_premium(True, source, now) is True
    assert sp.profile_premium(False, source, now) is False
    assert sp.profile_needs_expiry(True, source, now) is False


def test_lukija_kayttaa_moduulin_kelloa_kun_hetkea_ei_anneta(monkeypatch):
    monkeypatch.setattr(sp, "_utcnow", lambda: BEFORE)
    assert sp.profile_premium(True, PASS) is True
    assert sp.web_row_active(_pass_row()) is True
    monkeypatch.setattr(sp, "_utcnow", lambda: AT)
    assert sp.profile_premium(True, PASS) is False
    assert sp.web_row_active(_pass_row()) is False
    assert sp.web_row_needs_expiry(_pass_row()) is True


# ---------------------------------------------------------------------------
# 3. web_subscriptions-rivin lukija vaiheittain
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("now", VOIMASSA)
def test_passin_rivi_voimassa_ennen_loppua(now):
    assert sp.web_row_active(_pass_row(), now) is True
    assert sp.web_row_needs_expiry(_pass_row(), now) is False


@pytest.mark.parametrize("now", PAATTYNYT)
def test_passin_rivi_paattyy_vaikka_kanta_sanoisi_muuta(now):
    # Kiintean lopun plan ratkaisee ENSIN: vaikka current_period_end olisi
    # vaarin (tai NULL), passi ei jatku 30.5.2027 yli.
    assert sp.web_row_active(_pass_row(), now) is False
    assert sp.web_row_active(_pass_row(current_period_end=None), now) is False
    assert sp.web_row_active(
        _pass_row(current_period_end="2030-01-01T00:00:00+00:00"), now) is False
    assert sp.web_row_needs_expiry(_pass_row(), now) is True


@pytest.mark.parametrize("now", PAATTYNYT)
def test_varapolun_season_rivi_paattyy_samaan_hetkeen(now):
    # Migraatio ajamatta -> rivi kirjoitetaan plan=season, loppu = passin loppu.
    rivi = _pass_row(plan="season")
    assert sp.web_row_active(rivi, now) is False
    assert sp.web_row_needs_expiry(rivi, now) is True


@pytest.mark.parametrize("now", VOIMASSA + PAATTYNYT)
def test_tilausrivit_eivat_muutu(now):
    vuosi = {"plan": "season", "status": "active",
             "current_period_end": "2027-11-01T00:00:00+00:00",
             "stripe_subscription_id": "sub_1"}
    kuukausi_null = {"plan": "monthly", "status": "active",
                     "current_period_end": None, "stripe_subscription_id": "sub_2"}
    assert sp.web_row_active(vuosi, now) is True
    assert sp.web_row_active(kuukausi_null, now) is True
    # Tilausrivia ei koskaan merkita lukijassa expired-tilaan: sen tila kulkee
    # Stripen webhookilla (uusinta voi saapua minuutteja jakson vaihteen jalkeen).
    vanha = {**vuosi, "current_period_end": "2026-01-01T00:00:00+00:00"}
    assert sp.web_row_active(vanha, now) is False
    assert sp.web_row_needs_expiry(vanha, now) is False


def test_rivin_reunatapaukset():
    assert sp.web_row_active(_pass_row(status="cancelled"), TODAY) is False
    assert sp.web_row_active(_pass_row(status="expired"), TODAY) is False
    # Kysely suodatti jo status=eq.active -> puuttuva status = aktiivinen.
    rivi = _pass_row()
    del rivi["status"]
    assert sp.web_row_active(rivi, TODAY) is True
    # Jasentamaton aikaleima -> voimassa (premiumin sailyttamisen suuntaan),
    # kuten ennen moduulia.
    assert sp.web_row_active({"plan": "season", "status": "active",
                              "current_period_end": "ei-paiva"}, TODAY) is True
    assert sp.web_row_active(None, TODAY) is False
    assert sp.web_row_needs_expiry(_pass_row(status="cancelled"), AFTER) is False


def test_valimuistin_rajanylitys():
    e = END.timestamp()
    assert sp.crossed_fixed_end(e - 10, e) is True       # loppuhetki kuuluu valiin
    assert sp.crossed_fixed_end(e - 10, e + 10) is True
    assert sp.crossed_fixed_end(e - 10, e - 1) is False
    assert sp.crossed_fixed_end(e, e + 10) is False      # tallennettu jo lopun jalkeen


# ---------------------------------------------------------------------------
# 4. API:n Premium-lukija (api/premium.py) vaiheittain + korjaava kirjoitus
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = json.dumps(data)

    def json(self):
        return self._data


@pytest.fixture
def premium_rest(monkeypatch):
    """Supabase-REST api/premium.py:lle: GET palauttaa annetut rivit, PATCH
    kirjataan."""
    import api.premium as p
    monkeypatch.setenv("SUPABASE_URL", "https://sb.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    tila = {"profiles": [], "web_subscriptions": [], "patches": [], "gets": []}

    def fake_get(url, headers=None, timeout=None):
        tila["gets"].append(url)
        if "/rest/v1/profiles" in url:
            return _Resp(tila["profiles"])
        if "/rest/v1/web_subscriptions" in url:
            return _Resp(tila["web_subscriptions"])
        raise AssertionError(f"odottamaton GET {url}")

    def fake_patch(url, json=None, headers=None, timeout=None):
        tila["patches"].append((url, json))
        return _Resp(None, 204)

    monkeypatch.setattr(p.requests, "get", fake_get)
    monkeypatch.setattr(p.requests, "patch", fake_patch)
    return tila


@pytest.mark.parametrize("now", VOIMASSA)
def test_api_profiililukija_passi_voimassa(premium_rest, monkeypatch, now):
    import api.premium as p
    monkeypatch.setattr(sp, "_utcnow", lambda: now)
    premium_rest["profiles"] = [{"is_premium": True, "premium_source": PASS}]
    assert p._profile_is_premium("u1") is True
    assert premium_rest["patches"] == []          # ei korjaavaa kirjoitusta ennen loppua
    # Lahde luetaan SAMASSA haussa: ilman sita passia ei voi tunnistaa.
    assert "premium_source" in premium_rest["gets"][0]


@pytest.mark.parametrize("now", PAATTYNYT)
def test_api_profiililukija_passi_paattynyt_ja_korjaa_lipun(premium_rest, monkeypatch, now):
    import api.premium as p
    monkeypatch.setattr(sp, "_utcnow", lambda: now)
    premium_rest["profiles"] = [{"is_premium": True, "premium_source": PASS}]
    assert p._profile_is_premium("u1") is False
    # Sovellus lukee lipun suoraan Supabasesta -> API korjaa sen, vain alaspain
    # ja vain riviin jonka oikeuden passi yha omistaa.
    assert len(premium_rest["patches"]) == 1
    url, body = premium_rest["patches"][0]
    assert "profiles?id=eq.u1" in url
    assert f"premium_source=eq.{PASS}" in url
    assert body["is_premium"] is False


@pytest.mark.parametrize("source", ["stripe_web", "revenuecat", "comp", None])
@pytest.mark.parametrize("now", [TODAY, AFTER])
def test_api_profiililukija_muut_lahteet_ennallaan(premium_rest, monkeypatch, source, now):
    import api.premium as p
    monkeypatch.setattr(sp, "_utcnow", lambda: now)
    premium_rest["profiles"] = [{"is_premium": True, "premium_source": source}]
    assert p._profile_is_premium("u1") is True
    assert premium_rest["patches"] == []
    premium_rest["profiles"] = [{"is_premium": False, "premium_source": source}]
    assert p._profile_is_premium("u1") is False


def test_api_profiililukija_tyhja_tai_outo_vastaus(premium_rest):
    import api.premium as p
    premium_rest["profiles"] = []
    assert p._profile_is_premium("u1") is False
    premium_rest["profiles"] = {"message": "virhe"}
    assert p._profile_is_premium("u1") is False


@pytest.mark.parametrize("now", VOIMASSA)
def test_api_web_rivilukija_passi_voimassa(premium_rest, monkeypatch, now):
    import api.premium as p
    monkeypatch.setattr(sp, "_utcnow", lambda: now)
    premium_rest["web_subscriptions"] = [_pass_row()]
    assert p._web_subscription_active("u1") is True
    assert premium_rest["patches"] == []


@pytest.mark.parametrize("now", PAATTYNYT)
def test_api_web_rivilukija_passi_paattynyt_ja_merkitsee_expired(premium_rest, monkeypatch, now):
    import api.premium as p
    monkeypatch.setattr(sp, "_utcnow", lambda: now)
    premium_rest["web_subscriptions"] = [_pass_row()]
    assert p._web_subscription_active("u1") is False
    # SPA lukee rivin suoraan status=active-ehdolla -> rivi expired-tilaan.
    # Suodatin pitaa tilausrivit ulkona.
    assert len(premium_rest["patches"]) == 1
    url, body = premium_rest["patches"][0]
    assert "stripe_subscription_id=is.null" in url
    assert body == {"status": "expired"}


@pytest.mark.parametrize("now", [TODAY, AFTER])
def test_api_web_rivilukija_tilaus_ennallaan(premium_rest, monkeypatch, now):
    import api.premium as p
    monkeypatch.setattr(sp, "_utcnow", lambda: now)
    premium_rest["web_subscriptions"] = [
        {"plan": "season", "current_period_end": "2027-11-01T00:00:00+00:00",
         "stripe_subscription_id": "sub_1"}]
    assert p._web_subscription_active("u1") is True
    assert premium_rest["patches"] == []


def test_api_valimuisti_ei_palvele_loppuhetken_yli(monkeypatch):
    """Ennen loppua tallennettu True ei saa palvella loppuhetken jalkeen,
    vaikka TTL (5 min) olisi viela voimassa."""
    import api.premium as p
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setattr(p, "free_premium_window_active", lambda *a, **k: False)
    monkeypatch.setattr(p, "_verify_token_user_id", lambda token: "u1")
    monkeypatch.setattr(p, "_PREMIUM_CACHE", {})
    kello = {"t": END.timestamp() - 60}
    monkeypatch.setattr(p.time, "time", lambda: kello["t"])
    haut = []

    def profiili(uid):
        haut.append(kello["t"])
        return sp.profile_premium(True, PASS,
                                  datetime.fromtimestamp(kello["t"], timezone.utc))

    monkeypatch.setattr(p, "_profile_is_premium", profiili)
    monkeypatch.setattr(p, "_web_subscription_active", lambda uid: False)

    class Req:
        headers = {"authorization": "Bearer tokeni"}

    assert p.is_premium_request(Req()) is True
    kello["t"] = END.timestamp() - 30                    # TTL voimassa, sama puoli
    assert p.is_premium_request(Req()) is True
    assert len(haut) == 1                                # valimuisti palveli
    kello["t"] = END.timestamp() + 1                     # TTL yha voimassa, raja ylitetty
    assert p.is_premium_request(Req()) is False
    assert len(haut) == 2


# ---------------------------------------------------------------------------
# 5. Checkout: kytkin pois = entinen, kytkin paalla = kertamaksu
# ---------------------------------------------------------------------------


def _configure_checkout(monkeypatch, *, passi: str):
    import api.main as m
    monkeypatch.setattr(stripe, "api_key", "sk_test_x")
    monkeypatch.setattr(m, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_ID", "price_season_test")
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_PASS_2026_27", passi)
    monkeypatch.setattr(m, "_GUEST_CHECKOUT_HITS", {})
    monkeypatch.setattr(m, "_auto_promo_discount", lambda: None)
    monkeypatch.setattr(
        m, "_get_supabase_user",
        lambda token: {"id": "user-123", "email": "test@example.com"}
        if token == "valid" else None)
    created: dict = {}

    def fake_create(**kwargs):
        created.clear()
        created.update(kwargs)
        return type("S", (), {"url": "https://checkout.stripe.com/test"})()

    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_create))
    return created


def _checkout(client, plan="season", guest=False, country=None):
    headers = {} if guest else {"Authorization": "Bearer valid"}
    if country:
        headers["CF-IPCountry"] = country
    path = "/api/web/checkout/guest" if guest else "/api/web/checkout"
    return client.post(path, json={"plan": plan, "origin": "https://pro.goaliq.app"},
                       headers=headers)


def test_checkout_kytkin_pois_on_tasan_entinen(client, monkeypatch):
    created = _configure_checkout(monkeypatch, passi="")
    r = _checkout(client)
    assert r.status_code == 200
    assert created["mode"] == "subscription"
    assert created["line_items"] == [{"price": "price_season_test", "quantity": 1}]
    assert created["subscription_data"] == {"metadata": {"price_tier": "default",
                                                         "plan": "season"}}
    assert created["metadata"] == {"user_id": "user-123", "plan": "season",
                                   "source": "pro-web", "price_tier": "default"}
    assert "payment_intent_data" not in created
    assert "customer_creation" not in created
    # Guest-polku samoin.
    r = _checkout(client, guest=True)
    assert r.status_code == 200
    assert created["mode"] == "subscription"
    assert created["metadata"]["plan"] == "season"


def test_checkout_kytkin_pois_hinta_puuttuu_on_yha_500(client, monkeypatch):
    import api.main as m
    _configure_checkout(monkeypatch, passi="")
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_ID", "")
    r = _checkout(client)
    assert r.status_code == 500
    assert "STRIPE_PRICE_SEASON_ID" in r.json()["detail"]


def test_checkout_kytkin_paalla_kausi_on_kertamaksu(client, monkeypatch):
    created = _configure_checkout(monkeypatch, passi="price_pass_test")
    r = _checkout(client)
    assert r.status_code == 200, r.text
    assert created["mode"] == "payment"
    assert created["line_items"] == [{"price": "price_pass_test", "quantity": 1}]
    assert "subscription_data" not in created           # kaataisi mode=paymentin
    assert created["customer_creation"] == "always"     # hyvityksen kohdistus
    meta = {"user_id": "user-123", "plan": PASS, "source": "pro-web",
            "price_tier": "default"}
    assert created["metadata"] == meta
    assert created["payment_intent_data"] == {"metadata": meta}
    # A7: maksutavat (lompakot) tulevat dashboardista, ei koodin listasta.
    assert "payment_method_types" not in created
    assert created["client_reference_id"] == "user-123"


def test_checkout_kytkin_paalla_ei_aluehintaa(client, monkeypatch):
    # Aluekartan season-hinnat ovat tilaushintoja; mode=payment kaatuisi niihin.
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES", json.dumps(
        {"season": {"US": "price_season_us"}, "monthly": {"US": "price_monthly_us"}}))
    created = _configure_checkout(monkeypatch, passi="price_pass_test")
    r = _checkout(client, country="US")
    assert r.status_code == 200, r.text
    assert created["line_items"] == [{"price": "price_pass_test", "quantity": 1}]
    assert created["metadata"]["price_tier"] == "default"


def test_checkout_kytkin_paalla_kuukausi_ennallaan(client, monkeypatch):
    created = _configure_checkout(monkeypatch, passi="price_pass_test")
    r = _checkout(client, plan="monthly")
    assert r.status_code == 200
    assert created["mode"] == "subscription"
    assert created["line_items"] == [{"price": "price_monthly_test", "quantity": 1}]
    assert created["metadata"]["plan"] == "monthly"


def test_guest_checkout_kytkin_paalla_on_kertamaksu(client, monkeypatch):
    created = _configure_checkout(monkeypatch, passi="price_pass_test")
    r = _checkout(client, guest=True)
    assert r.status_code == 200, r.text
    assert created["mode"] == "payment"
    assert created["line_items"] == [{"price": "price_pass_test", "quantity": 1}]
    assert created["metadata"] == {"plan": PASS, "source": "pro-web-guest",
                                   "price_tier": "default"}
    assert created["payment_intent_data"]["metadata"] == created["metadata"]
    assert "customer_email" not in created
    assert "client_reference_id" not in created
    assert "guest=1" in created["success_url"]


# ---------------------------------------------------------------------------
# 6. Webhook: oikeus kiintealla lopulla, hyvitys purkaa
# ---------------------------------------------------------------------------


SECRET = "whsec_test"


def _signed(payload: dict) -> tuple[bytes, str]:
    payload = {"id": "evt_test", "object": "event", "api_version": "2024-06-20",
               "created": int(time.time()), **payload}
    payload["data"]["object"].setdefault("object", "checkout.session")
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, f"t={ts},v1={sig}"


@pytest.fixture
def hook(monkeypatch):
    """Webhookin kirjoitukset jarjestyksessa yhteen lokiin."""
    import api.main as m
    monkeypatch.setattr(m, "STRIPE_WEB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_PASS_2026_27", "price_pass_test")
    st = {"log": [], "web_row": None, "profile": {}, "upsert_ok": True,
          "stamp_ok": True, "provisioned": "guest-uid"}

    def upsert(fields, match=None):
        st["log"].append(("upsert", dict(fields), match))
        if match is None and fields.get("plan") == PASS and not st["upsert_ok"]:
            return False
        return True

    def get_row(field, value):
        st["log"].append(("get_row", field, value))
        r = st["web_row"]
        return r(field, value) if callable(r) else r

    def stamp(uid, source):
        st["log"].append(("stamp", uid, source))
        return st["stamp_ok"]

    def update(uid, fields):
        st["log"].append(("update", uid, dict(fields)))
        return True

    monkeypatch.setattr(m, "_upsert_web_subscription", upsert)
    monkeypatch.setattr(m, "_get_web_subscription", get_row)
    monkeypatch.setattr(m, "_stamp_premium_source", stamp)
    monkeypatch.setattr(m, "_update_profile", update)
    monkeypatch.setattr(m, "_get_profile_premium_state", lambda uid: st["profile"])
    monkeypatch.setattr(m, "_send_magic_link",
                        lambda email, *a, **k: st["log"].append(("magic", email)) or True)
    monkeypatch.setattr(m, "_provision_supabase_user",
                        lambda email: st["log"].append(("provision", email)) or st["provisioned"])
    monkeypatch.setattr(m, "_affiliate_code_from_session", lambda obj: None)
    return st


def _post(client, event_type, obj):
    body, sig = _signed({"type": event_type, "data": {"object": obj}})
    return client.post("/api/webhook/stripe-web", content=body,
                       headers={"stripe-signature": sig})


def _pass_session(**kw) -> dict:
    obj = {"mode": "payment", "client_reference_id": "user-123",
           "metadata": {"user_id": "user-123", "plan": PASS, "source": "pro-web"},
           "customer": "cus_x", "subscription": None, "payment_status": "paid",
           "payment_intent": "pi_1"}
    obj.update(kw)
    return obj


def _ops(st, kind):
    return [e for e in st["log"] if e[0] == kind]


def test_webhook_passi_avaa_oikeuden_kiintealla_lopulla(client, hook):
    r = _post(client, "checkout.session.completed", _pass_session())
    assert r.status_code == 200
    upserts = _ops(hook, "upsert")
    assert len(upserts) == 1
    rivi = upserts[0][1]
    assert rivi["plan"] == PASS
    assert rivi["status"] == "active"
    assert rivi["current_period_end"] == END_ISO
    assert rivi["stripe_subscription_id"] is None
    assert rivi["stripe_customer_id"] == "cus_x"
    # Lahde ENNEN lippua: leima tekee paattymisesta mahdollisen.
    kinds = [e[0] for e in hook["log"] if e[0] in ("stamp", "update")]
    assert kinds == ["stamp", "update"]
    assert _ops(hook, "stamp")[0][1:] == ("user-123", PASS)
    pf = _ops(hook, "update")[0][2]
    assert pf["is_premium"] is True
    # Ei uusiudu -> sovelluksen tilikortti ei saa sanoa "Renews on".
    assert pf["subscription_cancel_at_period_end"] is True
    assert pf["subscription_current_period_end"] == END_ISO


def test_webhook_passi_viivastetty_maksu_odottaa_vahvistusta(client, hook):
    r = _post(client, "checkout.session.completed", _pass_session(payment_status="unpaid"))
    assert r.status_code == 200
    assert _ops(hook, "upsert") == [] and _ops(hook, "update") == []
    r = _post(client, "checkout.session.async_payment_succeeded", _pass_session())
    assert r.status_code == 200
    assert _ops(hook, "upsert")[0][1]["current_period_end"] == END_ISO
    assert _ops(hook, "update")[0][2]["is_premium"] is True


def test_webhook_async_succeeded_tilaukselle_ohitetaan_kuten_ennen(client, hook):
    obj = {"mode": "subscription", "client_reference_id": "user-123",
           "metadata": {"plan": "season"}, "subscription": "sub_1",
           "payment_status": "paid"}
    r = _post(client, "checkout.session.async_payment_succeeded", obj)
    assert r.status_code == 200
    assert hook["log"] == []


def test_webhook_passi_ei_lyhenna_avointa_oikeutta(client, hook):
    hook["profile"] = {"is_premium": True, "premium_source": "comp"}
    r = _post(client, "checkout.session.completed", _pass_session())
    assert r.status_code == 200
    assert len(_ops(hook, "upsert")) == 1          # web-rivi kirjataan
    assert _ops(hook, "stamp") == [] and _ops(hook, "update") == []


def test_webhook_passi_ei_korvaa_aktiivista_tilausrivia(client, hook):
    hook["web_row"] = {"user_id": "user-123", "plan": "monthly", "status": "active",
                       "current_period_end": "2027-12-01T00:00:00+00:00",
                       "stripe_subscription_id": "sub_live"}
    r = _post(client, "checkout.session.completed", _pass_session())
    assert r.status_code == 200
    assert _ops(hook, "upsert") == []
    assert _ops(hook, "update") == []


def test_webhook_passi_ilman_migraatiota_ei_anna_pysyvaa_premiumia(client, hook):
    hook["upsert_ok"] = False
    hook["stamp_ok"] = False
    r = _post(client, "checkout.session.completed", _pass_session())
    assert r.status_code == 200
    upserts = _ops(hook, "upsert")
    # Toinen yritys plan=season, loppu silti passin loppu -> vanhenee itsestaan.
    assert [u[1]["plan"] for u in upserts] == [PASS, "season"]
    assert upserts[1][1]["current_period_end"] == END_ISO
    # Leima epaonnistui -> lippua EI avata (muuten se jaisi paalle ikuisesti).
    assert _ops(hook, "update") == []


def test_webhook_payment_link_ilman_metadataa_provisioi_tilin(client, hook):
    obj = {"mode": "payment", "metadata": {}, "customer": "cus_g",
           "customer_details": {"email": "ostaja@example.com"},
           "payment_status": "paid", "payment_intent": "pi_g"}
    r = _post(client, "checkout.session.completed", obj)
    assert r.status_code == 200
    assert _ops(hook, "provision") == [("provision", "ostaja@example.com")]
    assert _ops(hook, "upsert")[0][1]["user_id"] == "guest-uid"
    assert _ops(hook, "upsert")[0][1]["current_period_end"] == END_ISO
    # Kirjautumislinkki viimeisena, kun oikeus on jo auki.
    assert hook["log"][-1] == ("magic", "ostaja@example.com")


def test_webhook_kytkin_pois_kertaosto_kulkee_entista_polkua(client, hook, monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_PASS_2026_27", "")
    obj = {"mode": "payment", "client_reference_id": "user-123",
           "metadata": {"plan": "season"}, "customer": "cus_x",
           "subscription": None, "payment_status": "paid"}
    r = _post(client, "checkout.session.completed", obj)
    assert r.status_code == 200
    rivi = _ops(hook, "upsert")[0][1]
    assert rivi["plan"] == "season"
    assert rivi["current_period_end"].endswith("06-30T23:59:59+00:00")
    assert _ops(hook, "stamp")[0][2] == "stripe_web"


def _charge(**kw) -> dict:
    obj = {"object": "charge", "id": "ch_1", "refunded": True, "amount": 2500,
           "amount_refunded": 2500, "customer": "cus_x",
           "metadata": {"user_id": "user-123", "plan": PASS}}
    obj.update(kw)
    return obj


def test_hyvitys_purkaa_passin(client, hook):
    hook["web_row"] = _pass_row(user_id="user-123")
    hook["profile"] = {"is_premium": True, "premium_source": PASS}
    r = _post(client, "charge.refunded", _charge())
    assert r.status_code == 200
    assert ("upsert", {"status": "cancelled"}, {"user_id": "user-123"}) in hook["log"]
    pf = _ops(hook, "update")[0][2]
    assert pf["is_premium"] is False
    assert pf["subscription_current_period_end"] is None


def test_hyvitys_guest_ostolle_loytyy_asiakkaasta(client, hook):
    hook["web_row"] = lambda f, v: (_pass_row(user_id="guest-uid")
                                    if (f, v) == ("stripe_customer_id", "cus_x") else None)
    hook["profile"] = {"is_premium": True, "premium_source": PASS}
    r = _post(client, "charge.refunded", _charge(metadata={"plan": PASS}))
    assert r.status_code == 200
    assert ("upsert", {"status": "cancelled"}, {"user_id": "guest-uid"}) in hook["log"]
    assert _ops(hook, "update")[0][2]["is_premium"] is False


def test_osittainen_hyvitys_ei_pura(client, hook):
    hook["web_row"] = _pass_row(user_id="user-123")
    hook["profile"] = {"is_premium": True, "premium_source": PASS}
    r = _post(client, "charge.refunded", _charge(refunded=False, amount_refunded=500))
    assert r.status_code == 200
    assert _ops(hook, "upsert") == [] and _ops(hook, "update") == []


def test_hyvitys_ei_koske_muun_lahteen_oikeuteen(client, hook):
    hook["web_row"] = _pass_row(user_id="user-123")
    hook["profile"] = {"is_premium": True, "premium_source": "revenuecat"}
    r = _post(client, "charge.refunded", _charge())
    assert r.status_code == 200
    assert ("upsert", {"status": "cancelled"}, {"user_id": "user-123"}) in hook["log"]
    assert _ops(hook, "update") == []


def test_tilauksen_laskun_hyvitys_ei_muuta_mitaan(client, hook):
    hook["web_row"] = {"user_id": "user-123", "plan": "season", "status": "active",
                       "current_period_end": "2027-11-01T00:00:00+00:00",
                       "stripe_subscription_id": "sub_1"}
    r = _post(client, "charge.refunded", _charge(metadata={}))
    assert r.status_code == 200
    assert _ops(hook, "upsert") == [] and _ops(hook, "update") == []


def test_hyvitys_profiilihaun_virhe_on_500_jotta_stripe_yrittaa_uudelleen(client, hook):
    hook["web_row"] = _pass_row(user_id="user-123")
    hook["profile"] = None
    r = _post(client, "charge.refunded", _charge())
    assert r.status_code == 500


# ---------------------------------------------------------------------------
# 7. Hinta ja diagnostiikka: sama kytkin kuin checkoutissa
# ---------------------------------------------------------------------------


def _configure_prices(monkeypatch, *, passi: str, pass_recurring=None):
    import api.main as m
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_ID", "price_season_list")
    monkeypatch.setattr(m, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_list")
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_PASS_2026_27", passi)
    monkeypatch.setattr(m.stripe, "api_key", "sk_test_x", raising=False)
    monkeypatch.setattr(m, "_HINTA_CACHE", {})
    monkeypatch.setattr(m, "_HINTA_VIRHE", {})
    monkeypatch.setattr(m, "_HINTA_VIRHE_AIKA", {})
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES", json.dumps(
        {"season": {"US": "price_season_us"}, "monthly": {"US": "price_monthly_us"}}))
    hinnat = {
        "price_season_list": {"unit_amount": 2500, "currency": "eur",
                              "recurring": {"interval": "year"}},
        "price_monthly_list": {"unit_amount": 399, "currency": "eur",
                               "recurring": {"interval": "month"}},
        "price_season_us": {"unit_amount": 900, "currency": "eur",
                            "recurring": {"interval": "year"}},
        "price_monthly_us": {"unit_amount": 149, "currency": "eur",
                             "recurring": {"interval": "month"}},
        "price_pass": {"unit_amount": 2500, "currency": "eur",
                       "recurring": pass_recurring},
    }
    monkeypatch.setattr(m.stripe.Price, "retrieve",
                        staticmethod(lambda pid, **kw: hinnat[pid]))


def test_hinta_kytkin_pois_tasan_entinen(client, monkeypatch):
    _configure_prices(monkeypatch, passi="")
    d = client.get("/api/web/pricing").json()
    assert d["plans"]["season"] == {"amount": 25.0, "currency": "EUR", "tier": "default"}
    d = client.get("/api/web/pricing", headers={"CF-IPCountry": "US"}).json()
    assert d["plans"]["season"]["amount"] == 9.0
    assert "season_pass" not in client.get("/api/stripe-config").json()["price_lookup"]


def test_hinta_kytkin_paalla_kertarmaksu_ja_loppupaiva(client, monkeypatch):
    _configure_prices(monkeypatch, passi="price_pass")
    for headers in ({}, {"CF-IPCountry": "US"}):
        d = client.get("/api/web/pricing", headers=headers).json()
        assert d["plans"]["season"] == {"amount": 25.0, "currency": "EUR",
                                        "tier": "default", "billing": "one_time",
                                        "access_until": END_ISO}
    # Kuukausi ennallaan (ja aluehinta sille yha voimassa).
    d = client.get("/api/web/pricing", headers={"CF-IPCountry": "US"}).json()
    assert d["plans"]["monthly"]["amount"] == 1.49
    assert "billing" not in d["plans"]["monthly"]
    sp_tila = client.get("/api/stripe-config").json()["price_lookup"]["season_pass"]
    assert sp_tila["ok"] is True and sp_tila["one_time"] is True
    assert sp_tila["access_until"] == END_ISO


def test_diagnostiikka_havaitsee_toistuvan_hinnan(client, monkeypatch):
    # Toistuva hinta mode=payment-sessiossa kaataisi jokaisen oston.
    _configure_prices(monkeypatch, passi="price_pass", pass_recurring={"interval": "year"})
    sp_tila = client.get("/api/stripe-config").json()["price_lookup"]["season_pass"]
    assert sp_tila["ok"] is False
    assert sp_tila["one_time"] is False
    assert "toistuva" in sp_tila["error"]
