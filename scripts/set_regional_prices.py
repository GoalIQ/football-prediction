#!/usr/bin/env python
"""Asettaa `STRIPE_REGIONAL_PRICES`:n Renderiin yhdesta hinta-ID:sta.

MIKSI TAMA ON SKRIPTI EIKA KASITYOTA (20.9.2026): muuttuja on JSON jonka
kasin kirjoittaminen on juuri se kohta jossa typo menee lapi huomaamatta.
Vaara tunniste ei nay virheena meille vaan epaonnistuneena ostoksena TASAN
niilla markkinoilla joita varten aluehinta rakennettiin. Skripti validoi
muodon, tulostaa tuloksen ja vaatii `--apply`:n ennen kuin koskee Renderiin.

MAALISTA on mitattu, ei arvattu. `paywall_shown` 90 vrk (PostHog, 20.9):
Nigeria 54, Angola 49, Kenya 47, Ghana 44, Ethiopia 34, Ivory Coast 31,
Brazil 21, India 21, Bangladesh 20 - yhteensa yli puolet kaikista
maksumuurin nahneista, kun UK on 106, US 83 ja Suomi 57.

🔴 MUUTTUJA KIRJOITETAAN KOKONAAN YLI. Siksi KAIKKI planit annetaan samalla
ajolla: aiempi versio otti yhden planin kerrallaan, ja toinen ajo olisi
pyyhkinyt ensimmaisen hiljaa. Se on juuri se virhe jota tama skripti on
olemassa estamaan.

AJO:
    python scripts/set_regional_prices.py --season price_A --monthly price_B
    python scripts/set_regional_prices.py --season price_A --apply
    python scripts/set_regional_prices.py --clear --apply       # poistaa

Poisto palauttaa listahinnan kaikille maille: `resolve_price` putoaa
oletukseen kun muuttujaa ei ole. Peruminen on siis yksi komento.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ID = "srv-d7u5fgnlk1mc73ec6rv0"          # goaliq-api
VAR = "STRIPE_REGIONAL_PRICES"

#: Mitatut hintaherkat markkinat. Lisaa maa vain mittauksen perusteella.
MARKKINAT = ("NG", "AO", "KE", "GH", "ET", "CI", "BR", "IN", "BD")


def _tarkista(price_id: str) -> str:
    if not isinstance(price_id, str) or not price_id.startswith("price_"):
        raise SystemExit(
            f"VIRHE: {price_id!r} ei ole Stripe-hinta. Odotettu 'price_...'. "
            "Tuotetunniste (prod_...) tai nimi EI kelpaa - resolve_price "
            "hylkaisi sen ja kaikki maksaisivat listahinnan.")
    return price_id


def kartta(season: str | None = None, monthly: str | None = None) -> dict:
    """{"season": {"NG": id, ...}, "monthly": {...}} - resolve_pricen muoto.

    Molemmat planit samassa kutsussa, koska muuttuja kirjoitetaan yli.
    Puuttuva plan jaa pois kartasta = se maksaa listahinnan.
    """
    ulos: dict = {}
    for nimi, pid in (("season", season), ("monthly", monthly)):
        if pid:
            ulos[nimi] = {maa: _tarkista(pid) for maa in MARKKINAT}
    if not ulos:
        raise SystemExit("VIRHE: anna ainakin --season tai --monthly")
    return ulos


def _env_key() -> str:
    for rivi in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        if rivi.startswith("RENDER_API_KEY="):
            return rivi.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("VIRHE: RENDER_API_KEY puuttuu .env:sta")


def aseta(arvo: str) -> None:
    key = _env_key()
    body = json.dumps([{"key": VAR, "value": arvo}]).encode()
    r = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE_ID}/env-vars",
        data=body, method="PUT",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Accept": "application/json"})
    try:
        urllib.request.urlopen(r, timeout=30).read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Render ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}")
    print(f"{VAR} asetettu. Render deployaa muutoksen automaattisesti.")
    print("Verifiointi: tee osto VPN:lla listatusta maasta, tai katso "
          "Stripe-tilauksen metadata.price_tier (pitaa olla maakoodi).")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", help="Stripe-hinta vuositilaukselle, price_...")
    ap.add_argument("--monthly", help="Stripe-hinta kuukausitilaukselle, price_...")
    ap.add_argument("--clear", action="store_true", help="tyhjenna (= listahinta kaikille)")
    ap.add_argument("--apply", action="store_true", help="kirjoita Renderiin")
    a = ap.parse_args()

    arvo = "" if a.clear else json.dumps(kartta(a.season, a.monthly),
                                         separators=(",", ":"))
    if a.clear:
        print("Tyhjennetaan: kaikki maat palaavat listahintaan.")
    else:
        print(f"{VAR}={arvo}")
        planit = [n for n, v in (("season", a.season), ("monthly", a.monthly)) if v]
        print(f"  {len(MARKKINAT)} maata, planit: {', '.join(planit)}")
        if "monthly" not in planit:
            print("  HUOM: kuukausi jaa listahintaan (3,99/kk = 47,88/v), eli "
                  "se on aluemaassa moninkertainen vuosihintaan nahden.")
    if not a.apply:
        print("\n(kuivaharjoitus - lisaa --apply jos tama on oikein)")
        return 0
    aseta(arvo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
