"""Kertamaksuinen kausipassi 2026/27: YKSI lahde paattymishetkelle ja YKSI lukija
sille, onko oikeus voimassa (Villen paatos 1.11.2026, ulkoasuohjelma WP6).

Passi on 25 EUR:n kertamaksu, voimassa kauden 2026/27 loppuun (GW38:n deadline
30.5.2027 13:30 UTC, oikeus paivan loppuun UTC) eika uusiudu.

🔴 MIKSI TAMA MODUULI ON OLEMASSA (CLAUDE.md 6a). Tilauksen oikeus puretaan
webhookilla (`customer.subscription.deleted`, RevenueCatin `EXPIRATION`).
Kertamaksusta ei synny yhtaan webhookia paattymishetkella. Jos passi vain
asettaisi `profiles.is_premium = true`, ostajasta tulisi PYSYVA premium, koska
mikaan ei koskaan kaantaisi lippua takaisin (sama ansa jonka 14.8 arvio loysi
ilmaisikkunasta, ks. `api/premium.py`). Siksi:

  1. Paattymishetki kirjoitetaan TANNE kerran (`SEASON_PASS_END`). Webhook
     kirjoittaa sen kantaan tasta, eika yksikaan lukija luota kannan arvoon
     yksin: kiintean paattymisen lahde (`FIXED_END`) ratkaisee.
  2. Lukijat kysyvat taalta (`profile_premium`, `web_row_active`), eivat
     raa'asta lipusta. `tests/test_season_pass_reader_discipline.py` kaataa
     buildin, jos api/:hin ilmestyy premium-tilan haku joka ei kulje taman
     kautta eika ole poikkeuslistalla perusteluineen.
  3. Invariantti mitataan synteettisilla hetkilla ennen paattymista, tasan
     paattymishetkella ja sen jalkeen (`tests/test_season_pass.py`), ei vain
     tanaan, jolloin se on aina tosi.

Seuraava passi (2027/28) lisataan `FIXED_END`iin, ei lukijoihin.
"""
from __future__ import annotations

from datetime import datetime, timezone

#: Passin tunniste. Sama merkkijono kolmessa roolissa: `profiles.premium_source`,
#: `web_subscriptions.plan` (kun kannan CHECK sallii sen, migraatio
#: `supabase/migrations/20261101120000_season_pass_2026_27.sql`) ja Stripe
#: Checkoutin `metadata.plan`.
SEASON_PASS_ID = "season_pass_2026_27"

#: Paattymishetki. Oikeus on voimassa kun `now < SEASON_PASS_END`; tasan talla
#: hetkella ja sen jalkeen ei. GW38:n deadline on samana paivana 13:30 UTC.
SEASON_PASS_END = datetime(2027, 5, 30, 23, 59, 59, tzinfo=timezone.utc)

#: Kantaan kirjoitettava muoto (sama kuin muut webhookin aikaleimat,
#: `datetime.isoformat()` -> "+00:00"). Johdettu, ei kirjoitettu uudelleen.
SEASON_PASS_END_ISO = SEASON_PASS_END.isoformat()

#: Kiintean paattymishetken oikeudet: tunniste -> hetki. Tunniste on joko
#: `premium_source` tai `web_subscriptions.plan`.
FIXED_END: dict[str, datetime] = {SEASON_PASS_ID: SEASON_PASS_END}

#: Lahteet joiden oikeus on avoin (ei kiinteaa loppua) ja jonka omistaa joku
#: muu kuin passi. Passin osto EI leimaa naiden paalle, ettei se lyhentaisi
#: comp-Premiumia tai kaupan tilausta 30.5.2027:aan.
OPEN_ENDED_SOURCES = frozenset({"comp", "revenuecat"})


def _utcnow() -> datetime:
    """Kello yhdessa paikassa, jotta testit voivat ajaa lukijat synteettisilla
    hetkilla (6a kohta 3) koskematta vakioon."""
    return datetime.now(timezone.utc)


def fixed_end(source) -> datetime | None:
    """Kiintea paattymishetki tunnisteelle, tai None (avoin oikeus)."""
    if not isinstance(source, str):
        return None
    return FIXED_END.get(source.strip())


def fixed_end_passed(source, now: datetime | None = None) -> bool:
    """True kun tunnisteella on kiintea loppu ja se on jo ohitettu."""
    end = fixed_end(source)
    return end is not None and (now or _utcnow()) >= end


def profile_premium(is_premium, premium_source, now: datetime | None = None) -> bool:
    """`profiles`-rivin premium-tila NYT.

    Raaka `is_premium` on webhookin viimeinen kirjoitus. Passille se jaa
    todeksi paattymisen yli (webhookia ei tule), joten kiintean lopun lahde
    ohittaa sen. Muut lahteet (stripe_web, revenuecat, comp, None) eivat
    muutu: niiden purku on webhookin tehtava kuten ennenkin.
    """
    return bool(is_premium) and not fixed_end_passed(premium_source, now)


def parse_ts(value) -> datetime | None:
    """ISO-aikaleima -> aware datetime. ValueError nousee kutsujalle."""
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def web_row_active(row: dict, now: datetime | None = None) -> bool:
    """`web_subscriptions`-rivin voimassaolo NYT.

    Sama semantiikka kuin ennen tata moduulia (status `active`, ja
    `current_period_end` NULL tai tulevaisuudessa; jasentamaton aikaleima ->
    voimassa, eli premiumin sailyttamisen suuntaan), mutta kiintean lopun
    `plan` ratkaisee ensin. Rivi jolta `status` puuttuu (kysely suodatti sen
    jo `status=eq.active`), kasitellaan aktiivisena.
    """
    if not isinstance(row, dict):
        return False
    status = row.get("status", "active")
    if status != "active":
        return False
    hetki = now or _utcnow()
    if fixed_end_passed(row.get("plan"), hetki):
        return False
    end = row.get("current_period_end")
    if end is None:
        return True
    try:
        return parse_ts(end) > hetki
    except (ValueError, TypeError):
        return True


def web_row_needs_expiry(row: dict, now: datetime | None = None) -> bool:
    """Pitaako rivi merkita `expired`iksi (lukijan korjaava kirjoitus).

    Vain KERTAOSTON rivi (`stripe_subscription_id` puuttuu): tilauksen rivi
    paivittyy Stripen omalla webhookilla, ja sen uusinta voi saapua minuutteja
    jakson vaihteen jalkeen. Kertaostolle webhookia ei tule koskaan, joten
    ilman tata rivi olisi `active` ikuisesti ja SPA (joka lukee rivin
    suoraan Supabasesta `status=active`-ehdolla) nayttaisi Premiumia.
    """
    if not isinstance(row, dict) or row.get("status", "active") != "active":
        return False
    if row.get("stripe_subscription_id"):
        return False
    return not web_row_active(row, now)


def profile_needs_expiry(is_premium, premium_source,
                         now: datetime | None = None) -> bool:
    """Onko `profiles.is_premium` jaanyt todeksi kiintean lopun yli.

    Sovellus lukee raa'an lipun suoraan Supabasesta (goaliq-app
    lib/AuthContext.tsx), joten API:n lukija korjaa sen kun se nakee taman.
    """
    return bool(is_premium) and fixed_end_passed(premium_source, now)


def crossed_fixed_end(t0: float, t1: float) -> bool:
    """Osuuko jokin kiintea loppu valille (t0, t1] (epoch-sekunteina).

    `api/premium.py`:n 5 min valimuisti kayttaa tata: ennen loppua
    tallennettu True ei saa palvella loppuhetken jalkeen.
    """
    return any(t0 < end.timestamp() <= t1 for end in FIXED_END.values())
