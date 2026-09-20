# -*- coding: utf-8 -*-
"""Portti: uusi pakollinen ymparistomuuttuja ei voi jaada vahdin ulkopuolelle.

🔴 20.9.2026: ymparisto pyyhkiytyi ja vika oli nakymaton. Korjaus oli
`_PAKOLLISET_ENV` + `/api/health/env` + ajastettu vahti. Mutta lista joka
yllapidetaan kasin vanhenee: seuraava muuttuja lisataan koodiin eika
listalle, ja silloin vahti on vihrea vaikka tuote on rikki.

Tama testi vaatii, etta JOKAINEN `os.getenv`-nimi api/:ssa on joko
pakollisten listalla tai nimetty vapaaehtoiseksi PERUSTELUN kanssa.
Unohdus muuttuu mahdottomaksi, tietoinen valinta jaa diffiin.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import api.main as m

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"

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
}


def _env_nimet() -> set[str]:
    nimet: set[str] = set()
    for p in sorted(API.rglob("*.py")):
        puu = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(puu):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            osuu = (isinstance(f, ast.Attribute) and f.attr in ("getenv", "get")
                    and "environ" in ast.unparse(f))
            osuu = osuu or (isinstance(f, ast.Attribute) and f.attr == "getenv")
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
