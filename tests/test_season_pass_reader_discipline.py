"""Lukijakuri (CLAUDE.md 6a kohdat 1-2): Premium-tila luetaan `src.season_pass`in
kautta, ei raa'asta lipusta.

Miksi: kausipassi (ulkoasu WP6) paattyy 2027-05-30T23:59:59Z ilman webhookia.
`profiles.is_premium` ja `web_subscriptions.status = 'active'` jaavat silloin
todeksi. Jokainen pinta joka lukee ne suoraan antaisi vanhentuneelle passille
Premiumin (tai laskisi sen Premiumiksi raportissa, tai lahettaisi sille
Premium-pushit). Yksi lukija ei voi palauttaa vaaraa; tama portti estaa uuden
ohituksen syntymasta unohduksesta.

Mekanismi: jokainen api/:n ja src/:n funktio joka tekee Supabase-REST-haun
(`requests.get`) `web_subscriptions`-tauluun tai `profiles`-tauluun
`is_premium`-kentalla, joko
  (a) kutsuu `season_pass.`-lukijaa samassa funktiossa, tai
  (b) on POIKKEUKSET-listalla perustelun kanssa.
Lista tarkistetaan molempiin suuntiin: vanhentunut rivi (funktio poistunut tai
ei enaa lue Premium-tilaa) kaataa testin, jottei lista lahoa.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKANNATTAVAT = ("api", "src")
LUKIJAMODUULI = Path("src") / "season_pass.py"

#: (polku, funktio) -> perustelu. Uusi rivi vaatii perustelun joka kertoo miksi
#: raaka luku on oikein JUURI tassa, ei vain etta se on.
POIKKEUKSET: dict[tuple[str, str], str] = {
    ("api/main.py", "_get_web_subscription"):
        "Geneerinen rivihaku kirjoituspaatokseen (user_id tilaus-ID:lla tai "
        "asiakas-ID:lla, select=*). Ei vastaa kysymykseen 'onko Premium'; "
        "kutsupaikka joka tarvitsee voimassaolon kysyy sen "
        "season_pass.web_row_active-lukijalta (esim. _fulfil_season_pass).",
    ("api/main.py", "_get_profile_premium_state"):
        "Kirjoituspaatos: kumpi lahde omistaa oikeuden (no-clobber passin "
        "ostossa ja hyvityksessa). Tarvitsee nimenomaan RAA'AN lipun ja "
        "lahteen, koska kirjoitus kohdistuu kannan tilaan eika kayttajan "
        "oikeuteen nyt.",
    ("api/main.py", "_paid_user_ids"):
        "Luojakohortin raportti mittaa MAKSANEITA (myos entisia) eika oikeutta "
        "nyt: web_subscriptions-rivi ilman status-ehtoa ja is_premium-lippu. "
        "Vanhentunut passi on edelleen maksanut asiakas, joten raaka luku on "
        "oikea mittari tassa.",
}


def _funktiot(puu: ast.AST):
    for solmu in ast.walk(puu):
        if isinstance(solmu, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield solmu


def _merkkijonot(funktio: ast.AST) -> str:
    """Funktion merkkijonoliteraalit (myos f-stringien osat) ilman docstringia."""
    doc = None
    runko = getattr(funktio, "body", [])
    if runko and isinstance(runko[0], ast.Expr) and isinstance(
            getattr(runko[0], "value", None), ast.Constant) and isinstance(runko[0].value.value, str):
        doc = runko[0].value
    osat = []
    for s in ast.walk(funktio):
        if s is doc:
            continue
        if isinstance(s, ast.Constant) and isinstance(s.value, str):
            osat.append(s.value)
    return "\n".join(osat)


def _tekee_get_haun(funktio: ast.AST) -> bool:
    for s in ast.walk(funktio):
        if (isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
                and s.func.attr == "get" and isinstance(s.func.value, ast.Name)
                and s.func.value.id == "requests"):
            return True
    return False


def _lukee_premium_tilaa(funktio: ast.AST) -> bool:
    if not _tekee_get_haun(funktio):
        return False
    teksti = _merkkijonot(funktio)
    if "/rest/v1/web_subscriptions" in teksti:
        return True
    return "/rest/v1/profiles" in teksti and "is_premium" in teksti


def _kayttaa_lukijaa(funktio: ast.AST) -> bool:
    for s in ast.walk(funktio):
        if (isinstance(s, ast.Attribute) and isinstance(s.value, ast.Name)
                and s.value.id == "season_pass"):
            return True
    return False


def _premium_lukijat(lahde: str) -> dict[str, bool]:
    """funktion nimi -> kayttaako se season_pass-lukijaa, Premium-lukijoille."""
    puu = ast.parse(lahde)
    return {f.name: _kayttaa_lukijaa(f) for f in _funktiot(puu) if _lukee_premium_tilaa(f)}


def _kaikki_lukijat() -> dict[tuple[str, str], bool]:
    ulos: dict[tuple[str, str], bool] = {}
    for hakemisto in SKANNATTAVAT:
        for polku in sorted((ROOT / hakemisto).rglob("*.py")):
            suht = polku.relative_to(ROOT)
            if suht == LUKIJAMODUULI:
                continue
            avain = suht.as_posix()
            for nimi, ok in _premium_lukijat(polku.read_text(encoding="utf-8")).items():
                ulos[(avain, nimi)] = ok
    return ulos


def test_jokainen_premium_lukija_kulkee_season_passin_kautta():
    lukijat = _kaikki_lukijat()
    rikkojat = sorted(k for k, ok in lukijat.items() if not ok and k not in POIKKEUKSET)
    assert not rikkojat, (
        "Nama funktiot lukevat Premium-tilan Supabasesta ohi src.season_pass-"
        "lukijan. Kausipassin lippu jaa todeksi 30.5.2027 yli (webhookia ei "
        "tule), joten raaka luku antaa vanhentuneelle passille Premiumin. "
        "Kayta season_pass.profile_premium / web_row_active, tai lisaa rivi "
        f"POIKKEUKSET-listaan perustelun kanssa: {rikkojat}")


def test_poikkeuslista_ei_lahoa():
    lukijat = _kaikki_lukijat()
    vanhat = sorted(k for k in POIKKEUKSET if k not in lukijat)
    assert not vanhat, (
        "POIKKEUKSET-rivi jonka funktio ei enaa lue Premium-tilaa (tai on "
        f"poistunut). Poista rivi: {vanhat}")
    turhat = sorted(k for k in POIKKEUKSET if lukijat.get(k))
    assert not turhat, (
        "Funktio kayttaa nyt season_pass-lukijaa, joten poikkeusta ei tarvita. "
        f"Poista rivi: {turhat}")
    for k, perustelu in POIKKEUKSET.items():
        assert len(perustelu.strip()) >= 40, f"{k}: perustelu puuttuu tai on liian lyhyt"


def test_tunnetut_lukijat_on_kytketty():
    """Positiivinen kontrolli: skanneri loytaa ne lukijat jotka tiedetaan
    olevan olemassa. Jos tama hajoaa, skanneri on sokea eika ensimmainen testi
    todista mitaan."""
    lukijat = _kaikki_lukijat()
    for k in [("api/premium.py", "_profile_is_premium"),
              ("api/premium.py", "_web_subscription_active"),
              ("api/main.py", "_web_subscription_active"),
              ("api/main.py", "_premium_breakdown"),
              ("api/main.py", "push_targets")]:
        assert lukijat.get(k) is True, f"{k} ei loytynyt kytkettyna lukijana"


def test_skanneri_tunnistaa_raa_an_lukijan():
    """Negatiivinen kontrolli synteettisella lahteella: sama haku ilman
    lukijaa liputetaan, lukijan kanssa ei. Molemmat tauluhaut ja muuttujaan
    koottu URL (kuten api/main.py:n _web_subscription_active)."""
    raaka = '''
import requests
def a(uid):
    """Docstringin /rest/v1/web_subscriptions ei laske."""
    url = f"{U}/rest/v1/web_subscriptions?user_id=eq.{uid}&status=eq.active"
    return bool(requests.get(url).json())
def b(uid):
    rows = requests.get(f"{U}/rest/v1/profiles?id=eq.{uid}&select=is_premium").json()
    return bool(rows[0].get("is_premium"))
def c(uid):
    rows = requests.get(f"{U}/rest/v1/profiles?id=eq.{uid}&select=is_premium,premium_source").json()
    return season_pass.profile_premium(rows[0]["is_premium"], rows[0]["premium_source"])
def d(uid):
    return requests.get(f"{U}/rest/v1/profiles?id=eq.{uid}&select=fpl_entry_id").json()
def e(uid):
    """/rest/v1/web_subscriptions vain docstringissa"""
    return requests.get(U).json()
'''
    tulos = _premium_lukijat(raaka)
    assert tulos == {"a": False, "b": False, "c": True}
