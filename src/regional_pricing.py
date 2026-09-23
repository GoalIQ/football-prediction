"""YKSI LUKIJA: mika Stripe-hinta annetaan mille maalle.

MITATTU 20.9.2026 (PostHog). `purchase_error` 56 kpl, joista **53 on
kayttajan oma peruutus maksuruudussa** (`user_cancelled=true`) ja vain kolme
aitoa kauppavirhetta. Samaan aikaan `paywall_shown` 90 vrk jakautuu nain:
UK 106, US 83, Suomi 57 — mutta Nigeria 54, Angola 49, Kenya 47, Ghana 44,
Etiopia 34, Norsunluurannikko 31, Brasilia 21, Intia 21, Bangladesh 20.
Yli puolet maksumuurin nahneista on markkinoilla joissa 25 EUR/v on iso raha,
ja peruutus maksuruudussa on silloin odotettu vastaus hintaan, ei mysteeri.

**Stripen Adaptive Pricing ei ratkaise tata.** Se muuntaa VALUUTAN, se ei
sovita ostovoimaa: 25 EUR on Lagosissa yha 25 EUR:n arvoinen, vain nairoissa.
Tama on helppo sekoittaa oletukseksi "meilla on jo paikalliset hinnat".

KAKSI SAANTOA JOTKA TEKEVAT VAARASTA HINNASTA MAHDOTTOMAN (CLAUDE.md 6a):

1. **Maa tulee palvelimelta, ei clientilta.** `CF-IPCountry`-otsake
   (api.goaliq.app on Cloudflaren proxyn takana, muisti
   `api-domain-cloudflare-proxy`). Jos maa luettaisiin pyynnon rungosta tai
   selaimen localesta, kuka tahansa saisi halvimman hinnan ilmoittamalla
   maakseen NG. Tama funktio EI ota maata parametrina kutsupaikan
   valitsemana merkkijonona vaan lukee sen pyynnosta itse.

2. **Tuntematon maa = taysi hinta (fail-closed).** Kartta on eksplisiittinen
   lista. Puuttuva maa, puuttuva konfiguraatio, tyhja otsake tai rikkinainen
   JSON palauttaa oletushinnan. Vika voi siis tehda hinnasta liian KALLIIN
   muttei liian halvan — ja liian kalliin huomaa myynnista, liian halvan ei
   huomaa kukaan ennen kuin tilikaudella on reika.

Konfiguraatio (Render env, EI koodissa — hinta-ID:t ovat tuotantoresurssi):

    STRIPE_REGIONAL_PRICES={"season":{"NG":"price_...","KE":"price_..."},
                            "monthly":{"NG":"price_..."}}

Jos muuttujaa ei ole, kaikki maat saavat oletushinnan ja kayttaytyminen on
tasan sama kuin ennen tata moduulia.
"""
from __future__ import annotations

import json
import os

#: Otsake jonka Cloudflare asettaa. Ei luoteta mihinkaan clientin kenttaan.
COUNTRY_HEADER = "cf-ipcountry"

#: Cloudflare kayttaa naita kun maata ei tiedeta tai pyynto on sisainen.
_EI_MAATA = {"", "XX", "T1", "UNKNOWN"}


def request_country(headers) -> str:
    """Kaksikirjaiminen maakoodi pyynnosta, tai "" jos ei tiedossa.

    `headers` on mika tahansa mappaus jolla on `.get()` (FastAPI/Starlette
    Headers on case-insensitive; dictin kanssa kaytetaan pienta kirjainta).
    """
    try:
        raaka = headers.get(COUNTRY_HEADER) or headers.get(COUNTRY_HEADER.upper()) or ""
    except Exception:                                    # pragma: no cover
        return ""
    maa = str(raaka).strip().upper()
    if maa in _EI_MAATA or len(maa) != 2 or not maa.isalpha():
        return ""
    return maa


# --- Maat joissa EI myyda suoraan verkossa (paatos 23.9.2026) ---------------
#
# UK (ml. Mansaari): verkko-osto suljettu, Premium myydaan sovelluskauppojen
# (App Store, Google Play) kautta. Kavija ohjataan sinne.
#
# LISTA ON KOODISSA EIKA YMPARISTOSSA tarkoituksella: Renderin ymparisto
# pyyhkiytyi 20.9 kerran, ja ymparistomuuttujana tama esto olisi silloin
# kadonnut aanettomasti ja UK-myynti avautunut ilman etta mikaan kertoo.
# Muutos listaan on diffissa nakyva paatos.
#
# FAIL-OPEN PUUTTUVALLE MAALLE (vastakkainen kuin aluehinnassa): tyhja,
# XX- tai T1-otsake EI esta ostoa. Esto koskee vain listalla olevaa maata,
# jotta Cloudflaren otsakkeen puuttuminen ei voi pysayttaa koko verkkomyyntia.
#
# Olemassa olevat tilaukset eivat kulje taman kautta: uusiminen tapahtuu
# Stripessa ilman checkoutia, ja asiakasportaali (/api/customer-portal) on
# eri reitti. Esto koskee vain UUDEN checkout-session luontia.

#: Maat joissa verkko-osto (Stripe Checkout) on suljettu ja osto ohjataan
#: sovelluskauppaan. Arvot ovat CF-IPCountry-muotoa. GB = Iso-Britannia,
#: IM = Mansaari. Kanaalisaaret (JE, GG) eivat ole listalla.
WEB_CHECKOUT_STORE_ONLY = frozenset({"GB", "IM"})

#: Virhekoodi jonka SPA tunnistaa (`web/pro-spa/src/lib/region.ts`).
REGION_STORE_ONLY_ERROR = "region_app_store_only"


def web_checkout_allowed(country: str) -> bool:
    """Saako tasta maasta avata Stripe Checkoutin.

    `country` on `request_country()`n palauttama arvo (kaksi isoa kirjainta
    tai ""). Tuntematon tai puuttuva maa -> True (ks. perustelu ylla).
    """
    return (country or "").strip().upper() not in WEB_CHECKOUT_STORE_ONLY


#: Tierit joita checkout kysyy (`resolve_price(plan, ...)`, plan on
#: WebCheckoutRequestin arvo). Muu avain kartassa on kirjoitusvirhe jota
#: mikaan ei koskaan lue, esim. "annual" - ja sen maat maksavat listahintaa.
TIERIT = ("season", "monthly")


def _jasenna() -> tuple[dict, str | None]:
    """(kartta, virhe). Ainoa paikka joka jasentaa muuttujan.

    Virhe EI kaada ostoa (kartta on silloin tyhja = listahinta), mutta se
    palautetaan jotta `kuvaa_aluehinnat()` voi nayttaa sen. Ennen 21.9
    rikkinainen JSON oli taysin nakymaton: ostaja maksoi 25 EUR eika mikaan
    pinta kertonut miksi.
    """
    raaka = os.getenv("STRIPE_REGIONAL_PRICES", "").strip()
    if not raaka:
        return {}, None
    try:
        d = json.loads(raaka)
    except (ValueError, TypeError) as e:
        # Rikkinainen konfiguraatio EI saa kaataa ostoa eika arvata hintaa:
        # se putoaa oletushintaan kuten tuntematon maa.
        return {}, f"STRIPE_REGIONAL_PRICES ei ole JSONia ({type(e).__name__}: {e})"[:240]
    if not isinstance(d, dict):
        return {}, "STRIPE_REGIONAL_PRICES ei ole JSON-objekti {tier: {maa: price_id}}"
    return d, None


def _kartta() -> dict:
    return _jasenna()[0]


def kuvaa_aluehinnat() -> dict:
    """Mita aluehintakartta TODELLA tekee, luettuna samoilla lukijoilla joita
    checkout kayttaa.

    🔴 MIKSI (21.9.2026). Villen kysymys "eiko me sovittu hinnaksi 9 EUR" ei
    ollut vastattavissa: aluehinnan tilaa ei voinut lukea mistaan. Suomesta
    `/api/web/pricing` antaa saman vastauksen oli muuttuja asetettu tai ei,
    maata ei voi teeskennella (Cloudflare ylikirjoittaa `CF-IPCountry`:n myos
    suorassa origin-kutsussa), ja `resolve_price` on fail-closed eli vika
    tekee hinnasta liian KALLIIN kaatamatta mitaan. Ymparisto pyyhkiytyi
    20.9 kerran jo.

    Kuvaus ei jasenna karttaa omalla logiikallaan: jokainen rivi ajetaan
    `request_country`n ja `resolve_price`n lapi. Jos resolveri muuttuu,
    kuvaus muuttuu sen mukana eika voi vaittaa rivia toimivaksi jota
    checkout ei kayta.
    """
    kartta, virhe = _jasenna()
    virheet: list[str] = [virhe] if virhe else []
    tierit: dict[str, dict[str, str]] = {}
    vartija = "__listahinta__"
    for tier, alue in kartta.items():
        if tier not in TIERIT:
            virheet.append(
                f"tuntematon tier '{tier}' (checkout kysyy vain "
                f"{', '.join(TIERIT)}) - sen maat maksavat listahinnan")
            continue
        if not isinstance(alue, dict):
            virheet.append(f"{tier}: ei ole objekti {{maa: price_id}}")
            continue
        maat: dict[str, str] = {}
        for maa, ilmoitettu in alue.items():
            if request_country({COUNTRY_HEADER: maa}) != maa:
                virheet.append(
                    f"{tier}: maakoodi '{maa}' ei ole muotoa jonka "
                    "CF-IPCountry antaa (kaksi isoa kirjainta) - rivi ei "
                    "osu koskaan")
                continue
            pid, osui = resolve_price(tier, maa, vartija)
            if osui != maa or pid == vartija:
                virheet.append(
                    f"{tier}/{maa}: '{ilmoitettu}' ei kelpaa price-ID:ksi - "
                    "maa maksaa listahinnan")
                continue
            maat[maa] = pid
        tierit[tier] = maat
    return {
        "configured": bool(os.getenv("STRIPE_REGIONAL_PRICES", "").strip()),
        "errors": virheet,
        "tiers": tierit,
    }


def resolve_price(plan: str, country: str, default_price_id: str) -> tuple[str, str]:
    """(price_id, tier). `tier` menee Stripen metadataan mittausta varten.

    tier on "default" tai maakoodi, jolloin toteutunut tuotto on jaettavissa
    hintatasoittain ilman etta se pitaa paatella jalkikateen asiakkaan IP:sta.
    """
    if not country or not default_price_id:
        return default_price_id, "default"
    alue = _kartta().get(plan)
    if not isinstance(alue, dict):
        return default_price_id, "default"
    hinta = alue.get(country)
    if not isinstance(hinta, str) or not hinta.strip():
        return default_price_id, "default"
    hinta = hinta.strip()
    # 20.9: MUOTOTARKISTUS. Kartta taytetaan kasin Renderin
    # ymparistomuuttujaan, ja yleisin virhe on liittaa vaara tunniste:
    # `prod_...` (tuote) tai `price_...`in sijaan nimi. Vaara tunniste ei
    # putoaisi oletushintaan vaan kaataisi Stripe-kutsun, eli ostos
    # epaonnistuisi TASAN niilla markkinoilla joita varten aluehinta
    # rakennettiin. Muoto tarkistetaan siksi ennen kayttoa; tuntematon muoto
    # kasitellaan kuten tuntematon maa.
    if not hinta.startswith("price_"):
        return default_price_id, "default"
    return hinta, country
