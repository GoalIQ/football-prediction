# -*- coding: utf-8 -*-
"""Portti: aluehinnan tila on luettavissa, ja sen voi verifioida Suomesta.

🔴 MITATTU 21.9.2026. Villen kysymys "eiko me sovittu hinnaksi 9 EUR vuosi"
ei ollut vastattavissa, koska aluehinnan tilaa ei voinut lukea MISTAAN:

  1. `/api/web/pricing` Suomesta antaa saman vastauksen riippumatta siita
     onko `STRIPE_REGIONAL_PRICES` asetettu.
  2. `/api/stripe-config` ei kantanut kenttaa.
  3. Maata ei voi teeskennella: Cloudflare ylikirjoittaa `CF-IPCountry`:n
     myos suorassa `goaliq-api.onrender.com`-kutsussa (NG -> vastaus FI).
  4. Env-manifestin skannaus katsoi vain api/:ta, ja muuttuja luetaan
     src/:ssa, joten se ohitti senkin.

`resolve_price` on fail-closed: kadonnut tai rikkinainen muuttuja tekee
hinnasta liian KALLIIN eika kaada mitaan. Ymparisto pyyhkiytyi 20.9 kerran
jo. Taman luokan vika nakyisi vain myynnin puuttumisena.

Kaikki testit kulkevat ENDPOINTIN lapi: vika oli siina ettei kutsupaikka
kertonut mitaan, ja kutsupaikan peruminen on se muutos joka taman on
kaadettava.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import api.main as m


@pytest.fixture
def client():
    return TestClient(m.app)


#: Summa EI ole 9.00 vaan 9.13: kovakoodattu "9 EUR" ei voi lapaista
#: testia. Se todistaa etta luku tulee Stripe-kutsusta.
HINNAT = {
    "price_season_list": {"unit_amount": 2500, "currency": "eur",
                          "recurring": {"interval": "year"}},
    "price_monthly_list": {"unit_amount": 399, "currency": "eur",
                           "recurring": {"interval": "month"}},
    "price_season_ng": {"unit_amount": 913, "currency": "eur",
                        "recurring": {"interval": "year"}},
    "price_monthly_ng": {"unit_amount": 149, "currency": "eur",
                         "recurring": {"interval": "month"}},
}


def _konfiguroi(monkeypatch, kartta, hinnat=None):
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_ID", "price_season_list")
    monkeypatch.setattr(m, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_list")
    monkeypatch.setattr(m.stripe, "api_key", "sk_test_x", raising=False)
    monkeypatch.setattr(m, "_HINTA_CACHE", {})
    monkeypatch.setattr(m, "_HINTA_VIRHE", {})
    monkeypatch.setattr(m, "_HINTA_VIRHE_AIKA", {})
    if kartta is None:
        monkeypatch.delenv("STRIPE_REGIONAL_PRICES", raising=False)
    else:
        monkeypatch.setenv("STRIPE_REGIONAL_PRICES",
                           kartta if isinstance(kartta, str) else json.dumps(kartta))
    taulu = HINNAT if hinnat is None else hinnat

    def hae(pid, **kw):
        if pid not in taulu:
            raise RuntimeError(f"No such price: '{pid}'")
        return taulu[pid]

    monkeypatch.setattr(m.stripe.Price, "retrieve", staticmethod(hae))


OIKEA_KARTTA = {"season": {"NG": "price_season_ng", "KE": "price_season_ng"},
                "monthly": {"NG": "price_monthly_ng"}}


# --------------------------------------------------------------------------
# 1. /api/stripe-config kertoo koko ketjun: env -> kartta -> Stripe
# --------------------------------------------------------------------------

def test_tila_kertoo_maat_hinnat_ja_summat_stripesta(client, monkeypatch):
    _konfiguroi(monkeypatch, OIKEA_KARTTA)
    r = client.get("/api/stripe-config").json()["regional_pricing"]
    assert r["configured"] is True
    assert r["ok"] is True, r["errors"]
    assert r["errors"] == []
    assert r["tiers"]["season"] == {"countries": ["KE", "NG"],
                                    "price_ids": ["price_season_ng"]}
    assert r["tiers"]["monthly"] == {"countries": ["NG"],
                                     "price_ids": ["price_monthly_ng"]}
    assert r["prices"]["price_season_ng"] == {
        "tiers": ["season"], "countries": ["KE", "NG"], "ok": True,
        "amount": 9.13, "currency": "EUR", "interval": "year"}
    assert r["prices"]["price_monthly_ng"]["amount"] == 1.49
    assert r["prices"]["price_monthly_ng"]["interval"] == "month"


def test_puuttuva_muuttuja_nakyy_eika_ole_ok(client, monkeypatch):
    """Tama on 20.9:n pyyhkiytymisen muoto. Ennen 21.9 se oli nakymaton."""
    _konfiguroi(monkeypatch, None)
    r = client.get("/api/stripe-config").json()["regional_pricing"]
    assert r["configured"] is False
    assert r["ok"] is False
    assert r["prices"] == {}


def test_rikkinainen_json_on_nakyva_virhe_ei_hiljainen_tyhja(client, monkeypatch):
    _konfiguroi(monkeypatch, '{"season": {"NG": "price_season_ng"')
    r = client.get("/api/stripe-config").json()["regional_pricing"]
    assert r["configured"] is True, "muuttuja ON asetettu - se on vain rikki"
    assert r["ok"] is False
    assert any("ei ole JSONia" in v for v in r["errors"]), r["errors"]


def test_tuntematon_hinta_id_on_nakyva_virhe(client, monkeypatch):
    """Checkout kaatuisi TASAN niilla markkinoilla joita varten aluehinta
    rakennettiin. Se ei saa nayttaa vihrealta."""
    _konfiguroi(monkeypatch, {"season": {"NG": "price_poistettu"}})
    r = client.get("/api/stripe-config").json()["regional_pricing"]
    assert r["ok"] is False
    assert r["prices"]["price_poistettu"]["ok"] is False
    assert "No such price" in r["prices"]["price_poistettu"]["error"]
    assert any("checkout kaatuu" in v and "NG" in v for v in r["errors"])


def test_kirjoitusvirheet_joita_resolveri_ei_koskaan_lue_nakyvat(client, monkeypatch):
    """Kolme kasin tehtavaa virhetta jotka kaikki putoavat hiljaa listahintaan:
    tier jota checkout ei kysy, pienaakkosmaa jota CF-IPCountry ei anna, ja
    tuotteen tunniste hinnan paikalla."""
    _konfiguroi(monkeypatch, {"annual": {"NG": "price_season_ng"},
                              "season": {"ng": "price_season_ng",
                                         "KE": "prod_UpYw5IUJddKOXm",
                                         "GH": "price_season_ng"}})
    r = client.get("/api/stripe-config").json()["regional_pricing"]
    virheet = " | ".join(r["errors"])
    assert "annual" in virheet
    assert "'ng'" in virheet
    assert "prod_UpYw5IUJddKOXm" in virheet
    assert r["tiers"]["season"]["countries"] == ["GH"], (
        "vain rivi jota checkout oikeasti kayttaa saa nakya voimassa olevana")
    assert r["ok"] is False


def test_vaara_jakso_on_virhe(client, monkeypatch):
    """Kuukausi-ID vuositieriin veloittaisi vaaralla jaksolla ilman virhetta."""
    _konfiguroi(monkeypatch, {"season": {"NG": "price_monthly_ng"}})
    r = client.get("/api/stripe-config").json()["regional_pricing"]
    assert r["ok"] is False
    assert r["prices"]["price_monthly_ng"]["ok"] is False
    assert any("month" in v and "year" in v for v in r["errors"])


def test_kuvaus_kayttaa_checkoutin_omaa_resolveria(monkeypatch):
    """Yksi lukija (6a kohta 1): jos kuvaus jasentaisi kartan itse, se voisi
    vaittaa rivia voimassa olevaksi jota resolve_price ei kayta."""
    import src.regional_pricing as rp
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES", json.dumps(OIKEA_KARTTA))
    kutsut = []
    alkup = rp.resolve_price

    def vakoja(plan, country, default):
        kutsut.append((plan, country))
        return alkup(plan, country, default)

    monkeypatch.setattr(rp, "resolve_price", vakoja)
    rp.kuvaa_aluehinnat()
    assert sorted(kutsut) == [("monthly", "NG"), ("season", "KE"),
                              ("season", "NG")]


# --------------------------------------------------------------------------
# 2. Admin-esikatselu: aluehinnan paasta-paahan-verifiointi Suomesta
# --------------------------------------------------------------------------

TOKEN = "admin-testi-token"


def test_admin_esikatselu_ajaa_saman_polun_toisella_maalla(client, monkeypatch):
    _konfiguroi(monkeypatch, OIKEA_KARTTA)
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    r = client.get("/api/web/pricing?as_country=NG",
                   headers={"X-Admin-Token": TOKEN, "CF-IPCountry": "FI"})
    d = r.json()
    assert d["country"] == "NG"
    assert d["preview"] is True
    assert d["plans"]["season"] == {"amount": 9.13, "currency": "EUR", "tier": "NG"}
    assert d["plans"]["monthly"]["tier"] == "NG"
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("otsakkeet", [
    {},
    {"X-Admin-Token": "vaara"},
], ids=["ei-tokenia", "vaara-token"])
def test_esikatselu_ohitetaan_ilman_oikeaa_tokenia(client, monkeypatch, otsakkeet):
    """Fail-closed: parametri ohitetaan hiljaa. Ei 403:a, koska julkinen
    endpoint ei saa kertoa onko admin-tila olemassa."""
    _konfiguroi(monkeypatch, OIKEA_KARTTA)
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    r = client.get("/api/web/pricing?as_country=NG",
                   headers={**otsakkeet, "CF-IPCountry": "FI"})
    assert r.status_code == 200
    d = r.json()
    assert d["country"] == "FI"
    assert "preview" not in d
    assert d["plans"]["season"]["tier"] == "default"
    assert d["plans"]["season"]["amount"] == 25.0


def test_esikatselu_pois_kun_admin_token_puuttuu_ymparistosta(client, monkeypatch):
    _konfiguroi(monkeypatch, OIKEA_KARTTA)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    d = client.get("/api/web/pricing?as_country=NG",
                   headers={"X-Admin-Token": ""}).json()
    assert "preview" not in d
    assert d["plans"]["season"]["tier"] == "default"


def test_checkout_ei_koskaan_lue_esikatselua(client, monkeypatch):
    """Esikatselu vaikuttaa VAIN hinnan nayttamiseen. Vaikka admin-token on
    oikea, checkout veloittaa CF-IPCountry-maan hinnan."""
    _konfiguroi(monkeypatch, OIKEA_KARTTA)
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setattr(m, "_GUEST_CHECKOUT_HITS", {})
    luotu: dict = {}

    class _Sessio:
        url = "https://checkout.stripe.com/c/pay/test"

    def luo(**kw):
        luotu.update(kw)
        return _Sessio()

    monkeypatch.setattr(m.stripe.checkout.Session, "create", staticmethod(luo))
    r = client.post("/api/web/checkout/guest?as_country=NG",
                    json={"plan": "season", "origin": "https://pro.goaliq.app"},
                    headers={"X-Admin-Token": TOKEN, "CF-IPCountry": "FI",
                             "CF-Connecting-IP": "203.0.113.5"})
    assert r.status_code == 200
    assert luotu["line_items"] == [{"price": "price_season_list", "quantity": 1}]
    assert luotu["metadata"]["price_tier"] == "default"


def test_vain_web_pricing_tuntee_esikatselun():
    """Rakenteellinen portti edelliselle: yksikaan muu reitti api/main.py:ssa
    ei viittaa `as_country`in tai `is_admin_request`iin. Uusi checkout-polku
    ei voi alkaa lukea sita vahingossa."""
    import ast
    from pathlib import Path
    lahde = Path(m.__file__).read_text(encoding="utf-8")
    vaarat = []
    for n in ast.parse(lahde).body:
        if isinstance(n, ast.FunctionDef) and n.name != "web_pricing":
            koodi = ast.unparse(n)
            if "as_country" in koodi or "is_admin_request" in koodi:
                vaarat.append(n.name)
    assert not vaarat, f"esikatselu vuotaa muualle: {vaarat}"
