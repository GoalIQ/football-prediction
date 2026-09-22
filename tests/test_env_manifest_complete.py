# -*- coding: utf-8 -*-
"""Portti: uusi pakollinen ymparistomuuttuja ei voi jaada vahdin ulkopuolelle.

🔴 20.9.2026: ymparisto pyyhkiytyi ja vika oli nakymaton. Korjaus oli
`_PAKOLLISET_ENV` + `/api/health/env` + ajastettu vahti. Mutta lista joka
yllapidetaan kasin vanhenee: seuraava muuttuja lisataan koodiin eika
listalle, ja silloin vahti on vihrea vaikka tuote on rikki.

Tama testi vaatii, etta JOKAINEN `os.getenv`-nimi api/:ssa JA src/:ssa on
joko pakollisten listalla tai nimetty vapaaehtoiseksi PERUSTELUN kanssa.
Unohdus muuttuu mahdottomaksi, tietoinen valinta jaa diffiin.

🔴 21.9.2026: skannaus kattoi vain api/:n. `STRIPE_REGIONAL_PRICES` luetaan
`src/regional_pricing.py`:ssa, joten se ohitti portin kokonaan - eika sen
tilaa voinut lukea mistaan. Portti joka katsoo yhta hakemistoa vartioi
tapausta, ei luokkaa: API ajaa myos src/:n moduuleja.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import api.main as m

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
SRC = ROOT / "src"

#: Vapaaehtoiset: nimi -> miksi ilman tata parjataan.
VAPAAEHTOISET = {
    "STRIPE_PRICE_ID": "vanha yhden hinnan endpoint; SPA kayttaa "
                       "/api/web/checkoutia eika tata",
    "STRIPE_AUTO_PROMO_CODE": "tyhja = ei esitaytettya alennusta. Se on "
                              "Villen paatos 15.8 (EARLY30 poistettiin), "
                              "eli tyhja on OIKEA tila",
    "WEB_CHECKOUT_ORIGINS": "koodissa on oletuslista joka sisaltaa "
                            "pro.goaliq.appin",
    "FOOTBALL_DATA_API_KEY": "vain taustaskripteille; API ei tarvitse sita "
                             "pyyntopolulla",
    "FPL_MODEL_ENTRY_ID": "oletus on koodissa; vaara arvo nakyisi heti "
                          "mallin omalla sivulla",
    "RENDER_GIT_COMMIT": "Renderin itsensa asettama",
    "PREMIUM_ENFORCE_DEBUG": "vain paikalliseen vianetsintaan",
    "FREE_PREMIUM_UNTIL": "pelkka katkaisin joka voi vain SULKEA ilmaisikkunan "
                          "(api.premium: off/none/0/false); paiva tulee "
                          "src.free_windowista. Tyhja = koodin oletus, mika "
                          "on oikea tila",
    "STRIPE_REGIONAL_PRICES": "ilman sita kaikki maksavat listahinnan "
                              "(resolve_price on fail-closed, mikaan ei "
                              "kaadu). Villen 20.9 paatos on etta aluehinta "
                              "on PAALLA, joten env-health-watch vaatii "
                              "/api/stripe-config regional_pricing.ok=true - "
                              "tulos mitataan Stripesta, ei pelkkaa "
                              "muuttujan olemassaoloa",
    # 22.9.2026 PREDICT-API-MASK. Vapaaehtoinen VAIN niin kauan kuin oikea
    # tila on pois. Kun lippu kaannetaan Renderissa, siirra se
    # api.main._PAKOLLISET_ENViin: muuten ympariston pyyhkiytyminen (20.9)
    # avaisi ennusteiden Premium-kentat anonyymeille eika vahti huomaisi.
    "PREDICT_MASK": "oletus pois on 22.9 OIKEA tila: kolme mobiilin "
                    "Premium-kayttajaa oli viela buildilla joka ei laheta "
                    "tokenia /api/predictiin. Tyhja = ennusteet maskaamatta "
                    "kuten ennen tata muutosta (api.premium.predict_mask_on)",
}


def _on_env_kutsu(n: ast.Call) -> bool:
    """`os.getenv(...)` tai `os.environ.get(...)`."""
    f = n.func
    return isinstance(f, ast.Attribute) and (
        f.attr == "getenv" or (f.attr == "get" and "environ" in ast.unparse(f)))


def _kaareet(puut: list[ast.AST]) -> set[str]:
    """Funktiot jotka lukevat ymparistomuuttujan ENSIMMAISESTA parametristaan.

    🔴 21.9.2026: `api/premium.py` lukee muuttujansa kaareella
    `_env("ADMIN_TOKEN")`, jota skannaus ei tunnistanut. `ADMIN_TOKEN` katosi
    20.9 ympariston pyyhkiytyessa eika palautunut, koska se ei ollut
    listalla eika portti vaatinut paatosta: admin-endpointit (gradaus,
    push-notifikaatiot, autopilotin konversiomittari) vastasivat 403.
    Kaare tunnistetaan RAKENTEESTA eika nimesta, jotta seuraava kaare
    (`_getenv`, `env_str`, ...) ei ohita porttia.
    """
    nimet: set[str] = set()
    for puu in puut:
        for fn in ast.walk(puu):
            if not isinstance(fn, ast.FunctionDef) or not fn.args.args:
                continue
            par = fn.args.args[0].arg
            for c in ast.walk(fn):
                if (isinstance(c, ast.Call) and _on_env_kutsu(c) and c.args
                        and isinstance(c.args[0], ast.Name)
                        and c.args[0].id == par):
                    nimet.add(fn.name)
    return nimet


def _env_nimet() -> set[str]:
    polut = sorted(list(API.rglob("*.py")) + list(SRC.rglob("*.py")))
    puut = [ast.parse(p.read_text(encoding="utf-8")) for p in polut]
    kaareet = _kaareet(puut)
    nimet: set[str] = set()
    for puu in puut:
        for n in ast.walk(puu):
            if not isinstance(n, ast.Call):
                continue
            osuu = _on_env_kutsu(n) or (
                isinstance(n.func, ast.Name) and n.func.id in kaareet)
            if osuu and n.args and isinstance(n.args[0], ast.Constant) \
                    and isinstance(n.args[0].value, str):
                nimet.add(n.args[0].value)
    return {x for x in nimet if re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", x)}


def test_jokainen_env_on_joko_pakollinen_tai_perusteltu():
    tuntemattomat = sorted(
        _env_nimet() - set(m._PAKOLLISET_ENV) - set(VAPAAEHTOISET))
    assert not tuntemattomat, (
        f"ymparistomuuttujia ilman paatosta: {tuntemattomat}. Lisaa ne joko "
        "api.main._PAKOLLISET_ENV:iin (silloin /api/health/env ja ajastettu "
        "vahti seuraavat niita) tai VAPAAEHTOISET-listalle PERUSTELUN "
        "kanssa. 20.9 puuttuva muuttuja antoi Premiumin ilmaiseksi eika "
        "mikaan kertonut siita.")


def test_vapaaehtoisella_on_perustelu():
    for nimi, syy in VAPAAEHTOISET.items():
        assert syy and len(syy) > 15, f"{nimi}: perustelu puuttuu"


def test_pakollisilla_on_seuraus():
    for nimi, syy in m._PAKOLLISET_ENV.items():
        assert syy and len(syy) > 10, f"{nimi}: seuraus kirjoittamatta"


def test_premium_enforce_on_pakollisissa():
    """Tama on se muuttuja joka ei kaada mitaan - se vain lakkaa
    laskuttamasta. Vaarallisin muoto, koska se nayttaa terveelta."""
    assert "PREMIUM_ENFORCE" in m._PAKOLLISET_ENV


def test_vahti_on_kytketty():
    """Endpoint jota kukaan ei kutsu ei ole seurantaa."""
    wf = ROOT / ".github" / "workflows" / "env-health-watch.yml"
    assert wf.exists(), "env-health-watch.yml puuttuu"
    teksti = wf.read_text(encoding="utf-8")
    assert "schedule:" in teksti, "vahti ei ole ajastettu"
    assert "/api/health/env" in teksti
    assert "masked" in teksti, "vahti ei mittaa maskausta tuloksesta"


def test_vahti_mittaa_aluehinnan_tuloksesta():
    """21.9: vapaaehtoinen muuttuja jonka Ville on paattanyt pitaa paalla.
    Olemassaolo ei riita (rikkinainen JSON on olemassa), joten vahdin on
    luettava `regional_pricing.ok`, joka vaatii summat Stripesta."""
    teksti = (ROOT / ".github" / "workflows" / "env-health-watch.yml"
              ).read_text(encoding="utf-8")
    assert "/api/stripe-config" in teksti
    assert "regional_pricing" in teksti
    assert "'ok'" in teksti or '"ok"' in teksti


def test_skannaus_nakee_srcn():
    """Negatiivinen kontrolli: jos skannaus kutistuu takaisin api/:iin,
    tama punastuu eika hiljaa vihrea."""
    assert "STRIPE_REGIONAL_PRICES" in _env_nimet()


def test_kaare_tunnistetaan_rakenteesta():
    """Erotteleva kontrolli: synteettinen kaare jolla on eri nimi kuin
    `_env` loytyy. Ilman tata portti vartioisi vain yhta nimea (muisti:
    portti kirjoitetaan nahdylle muodolle)."""
    lahde = (
        "import os\n"
        "def lue_arvo(avain):\n"
        "    return os.environ.get(avain, '')\n"
        "X = lue_arvo('SYNTEETTINEN_AVAIN')\n")
    assert _kaareet([ast.parse(lahde)]) == {"lue_arvo"}


def test_admin_token_on_vahdin_listalla():
    """ADMIN_TOKEN on pakollinen: sen puuttuminen poistaa admin-endpointit
    kaytosta (gradaus, push-dispatch, cache, autopilotin S12-mittari)."""
    assert "ADMIN_TOKEN" in m._PAKOLLISET_ENV


def test_skannaus_nakee_kaareen_kautta_luetut():
    """Negatiivinen kontrolli kuten test_skannaus_nakee_srcn: jos
    kaaretunnistus putoaa _env_nimet()-funktiosta, tama punastuu. Ilman
    tata ADMIN_TOKENin pysyminen listalla peittaisi regression."""
    assert {"ADMIN_TOKEN", "FREE_PREMIUM_UNTIL"} <= _env_nimet()
