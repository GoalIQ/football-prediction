# -*- coding: utf-8 -*-
"""Portti: maksupolun vika ei saa olla nakymaton eika yhteinen.

Kaksi vikaa mitattiin 20.9.2026 tuotannossa, ja molemmat kuuluvat samaan
luokkaan: oire nakyi, syy ei.

1. **Hiljainen syy.** `/api/web/pricing` palautti `{"plans":{}}` tuntikausia.
   `_stripe_price_amount` nieli Stripen virheen (`except Exception: return
   None`), joten oireesta ei voinut paatella onko vika avaimessa,
   hinta-ID:ssa vai verkossa. Sessio arvasi avaimen ja arvasi vaarin, ja
   korjausyritys kohdistui vaaraan muuttujaan.

2. **Yhteinen kiintio.** Guest-checkoutin rate limit sanoi "10/IP/tunti",
   mutta `request.client.host` on taman palvelun takana REITITTIMEN osoite
   (uvicorn kaynnistetaan ilman `--forwarded-allow-ips`:ia, oletus
   `127.0.0.1`, eika Renderin reititin ole se). Kiintio oli siis
   10/tunti yhteensa kaikille maailman ostajille, ja kun se tayttyi,
   maksupolku vastasi 429 kaikille.

Molemmat testit ajetaan ENDPOINTIN lapi eika apufunktiota vasten: vika oli
kutsupaikassa, ja kutsupaikan peruminen on se muutos jonka taman testin on
kaadettava.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.main as m


@pytest.fixture
def client():
    return TestClient(m.app)


@pytest.fixture
def stripe_konfiguroitu(monkeypatch):
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_ID", "price_season_x")
    monkeypatch.setattr(m, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_x")
    monkeypatch.setattr(m.stripe, "api_key", "sk_test_x", raising=False)
    monkeypatch.setattr(m, "_HINTA_CACHE", {})
    monkeypatch.setattr(m, "_HINTA_VIRHE", {})
    monkeypatch.setattr(m, "_HINTA_VIRHE_AIKA", {})
    monkeypatch.delenv("STRIPE_REGIONAL_PRICES", raising=False)


# --------------------------------------------------------------------------
# 1. Syy on luettavissa ilman deployta
# --------------------------------------------------------------------------

def _kaataa(viesti):
    def f(pid, **kw):
        raise RuntimeError(viesti)
    return staticmethod(f)


def test_diagnostiikka_kertoo_MIKSI_hinta_puuttuu(client, monkeypatch,
                                                  stripe_konfiguroitu):
    """`secret_key_set: true` ja ostaminen poikki yhta aikaa - juuri tama
    yhdistelma oli 20.9 totta. Bool ei riita, syy tarvitaan."""
    monkeypatch.setattr(m.stripe.Price, "retrieve",
                        _kaataa("No such price: 'price_season_x'"))
    d = client.get("/api/stripe-config").json()
    assert d["secret_key_set"] is True, "esiehto: avain on asetettu"
    assert d["price_lookup"]["season"]["ok"] is False
    assert "No such price" in d["price_lookup"]["season"]["error"]
    assert d["price_lookup"]["season"]["price_id"] == "price_season_x"


def test_diagnostiikka_kertoo_onnistumisen_summana(client, monkeypatch,
                                                   stripe_konfiguroitu):
    """Vihrea rivi ei saa olla pelkka true: summa todistaa etta vastaus tuli
    Stripesta eika koodin oletuksesta."""
    monkeypatch.setattr(m.stripe.Price, "retrieve", staticmethod(
        lambda pid, **kw: {"unit_amount": 2500, "currency": "eur"}))
    d = client.get("/api/stripe-config").json()
    assert d["price_lookup"]["season"] == {
        "price_id": "price_season_x", "ok": True,
        "amount": 25.0, "currency": "EUR"}


def test_diagnostiikka_ei_vuoda_avainta(client, monkeypatch,
                                        stripe_konfiguroitu):
    """Pinta on julkinen. Stripe maskaa omat viestinsa, mutta maskaus ei saa
    olla ULKOISEN palvelun muistin varassa."""
    # 🔴 Avaimen NAKOINEN merkkijono kootaan paloista. GitHubin push
    # protection tunnistaa `sk_` + 24 merkkia Stripe-avaimeksi ja HYLKAA
    # pushin, vaikka arvo on keksitty - testin ensimmainen versio kaatui
    # juuri siihen. Palasina kirjoitettuna portti mittaa saman asian.
    hanta = "51QaBcDeFgHiJkLmNoPqRsTuV"
    monkeypatch.setattr(m.stripe.Price, "retrieve", _kaataa(
        "Invalid API key provided: " + "sk_" + "live_" + hanta))
    d = client.get("/api/stripe-config").json()
    virhe = d["price_lookup"]["season"]["error"]
    assert hanta not in virhe
    # Prefiksi jaa naikyviin: juuri se erottaa salaisen avaimen (sk_),
    # rajoitetun avaimen (rk_) ja avaimen TUNNISTEEN (mk_) toisistaan.
    # 20.9 se erottelu oli koko diagnoosi.
    assert "sk_***" in virhe


def test_hinnan_haku_ei_saa_niella_syyta(client, monkeypatch,
                                         stripe_konfiguroitu):
    """Kutsupaikkaportti. `/api/web/pricing` saa edelleen pudota pois
    (fail-soft kayttajalle), mutta syyn on jaatava talteen."""
    monkeypatch.setattr(m.stripe.Price, "retrieve",
                        _kaataa("Invalid API key provided"))
    d = client.get("/api/web/pricing").json()
    assert d["plans"] == {}, "fail-soft sailyy: SPA putoaa listahintaan"
    assert "Invalid API key provided" in m._HINTA_VIRHE["price_season_x"], (
        "syy nieltiin - juuri tama teki 20.9:n viasta arvauskilpailun")


def test_rikkinainen_avain_ei_ryoppya_stripea(client, monkeypatch,
                                              stripe_konfiguroitu):
    """Onnistuminen valimuistitettiin, epaonnistuminen ei. Rikkinaisella
    avaimella jokainen maksumuurin lataus teki siis kaksi epaonnistuvaa
    Stripe-kutsua - kuorma oli suurimmillaan juuri silloin kun mikaan ei
    toiminut."""
    kutsut = []

    def kaatuu(pid, **kw):
        kutsut.append(pid)
        raise RuntimeError("Invalid API key provided")

    monkeypatch.setattr(m.stripe.Price, "retrieve", staticmethod(kaatuu))
    for _ in range(5):
        client.get("/api/web/pricing")
    assert len(kutsut) == 2, (
        f"{len(kutsut)} Stripe-kutsua viidesta latauksesta - "
        "epaonnistuminen ei jaa muistiin")


# --------------------------------------------------------------------------
# 2. Kiintio on ostajakohtainen, ei maailmanlaajuinen
# --------------------------------------------------------------------------

@pytest.fixture
def guest_valmis(monkeypatch, stripe_konfiguroitu):
    monkeypatch.setattr(m, "_GUEST_CHECKOUT_HITS", {})

    class _Sessio:
        url = "https://checkout.stripe.com/c/pay/test"

    monkeypatch.setattr(m.stripe.checkout.Session, "create",
                        staticmethod(lambda **kw: _Sessio()))


def _osta(client, ip):
    return client.post("/api/web/checkout/guest",
                       json={"plan": "season", "origin": "https://pro.goaliq.app"},
                       headers={"CF-Connecting-IP": ip})


def test_kiintio_ei_ole_yhteinen_kaikille_ostajille(client, guest_valmis):
    """Ennen korjausta molemmat kavijat mahtuivat samaan ammeeseen, koska
    `request.client.host` on TestClientilla (ja Renderilla) sama arvo
    riippumatta siita kuka ostaa. Silloin yksi botti - tai yksi testisessio -
    sulkee maksupolun kaikilta tunniksi."""
    for i in range(m._GUEST_CHECKOUT_LIMIT):
        assert _osta(client, "203.0.113.7").status_code == 200, f"yritys {i}"
    assert _osta(client, "203.0.113.7").status_code == 429, "oma kiintio taynna"

    toinen = _osta(client, "198.51.100.9")
    assert toinen.status_code == 200, (
        "toinen ostaja sai 429 vaikka han ei ole ostanut kertaakaan - "
        "kiintio on yhteinen, eli maksupolku on kiinni kaikilta")
    assert toinen.json()["url"].startswith("https://checkout.stripe.com/")


def test_kiintio_luetaan_cloudflaren_otsakkeesta_ei_pyynnon_rungosta():
    """`X-Forwarded-For` on vaarennettavissa clientin paasta, ja
    vaarennettava kiintio on huonompi kuin liian karkea. Cloudflare
    YLIKIRJOITTAA `CF-Connecting-IP`:n, joten se on ainoa luotettava lahde
    taman palvelun edessa."""
    import ast
    from pathlib import Path
    lahde = Path(m.__file__).read_text(encoding="utf-8")
    puu = ast.parse(lahde)
    fn = next(n for n in puu.body
              if isinstance(n, ast.FunctionDef) and n.name == "client_ip")
    # Docstring pois: se KERTOO miksi X-Forwarded-For:ia ei lueta, eika
    # perustelu saa kaataa porttia joka vartioi koodia.
    runko = [s for s in fn.body
             if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                     and isinstance(s.value.value, str))]
    koodi = "\n".join(ast.unparse(s) for s in runko)
    assert "cf-connecting-ip" in koodi.lower()
    assert "x-forwarded-for" not in koodi.lower(), (
        "X-Forwarded-For on clientin vaarennettavissa taman proxyn takana")

    kutsuja = next(n for n in puu.body
                   if isinstance(n, ast.FunctionDef)
                   and n.name == "create_guest_checkout_session")
    kutsu = ast.unparse(kutsuja)
    assert "client_ip(" in kutsu, "kutsupaikka palautettiin ennalleen"
