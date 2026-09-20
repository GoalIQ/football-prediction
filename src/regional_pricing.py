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


def _kartta() -> dict:
    raaka = os.getenv("STRIPE_REGIONAL_PRICES", "").strip()
    if not raaka:
        return {}
    try:
        d = json.loads(raaka)
    except (ValueError, TypeError):
        # Rikkinainen konfiguraatio EI saa kaataa ostoa eika arvata hintaa:
        # se putoaa oletushintaan kuten tuntematon maa.
        return {}
    return d if isinstance(d, dict) else {}


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
    return hinta.strip(), country
