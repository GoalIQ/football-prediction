"""Kumppanit (26.9.2026). YKSI paikka kumppanin nimelle, linkille, seuranta-
tageille ja paattymispaivalle (saanto 6a): pinta ei kirjoita URL:ia kasin,
joten tagi tai paattyminen ei voi unohtua yhdesta paikasta.

FPL Demon: GoalIQ:n xP-syote (/api/partner/xp) pyorittaa hanen plannerinsa ja
solverinsa, sovittu X DM:ssa 26.9 (kokeilu GW10:n loppuun). Me linkitamme
hanen planneriinsa (ehtojen kohta 4).

SIJOITUS (Villen paatos 27.9): ILMAISEN /fpl/expected-points -sivun top 100
-taulukon alle. Ensimmainen versio (fp `feat/partner-link-demon`) oli vain
maksajan SPA-listan alla, ja sen nakisi 4-5 maksajaa joilla on jo oma
planneri: Demonin utm-seuranta nayttaisi nollaa, vaikka lupasimme "tracked
links both ways". EI lukitussa esikatselussa eika paywallissa: se on
ostohetki, ja linkki tarjoaisi siina ilmaisen vaihtoehdon joka pyorii meidan
luvuillamme.

URL on Demonin itse lahettama (X DM 27.9 klo 6.46), sellaisenaan: hanen
analytiikkansa lukee HANEN tagejaan.

PAATTYMINEN (julkaisutarkistaja B4): lause "run on these projections" on tosi
vain kumppanuuden ajan. `active_until` sammuttaa linkin seuraavassa
rebuildissa; jatko vaatii tietoisen paivamaaramuutoksen diffissa. Jos
kumppanuus loppuu aiemmin, aseta mennyt paiva ja aja refresh.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape

FPL_DEMON: dict[str, str] = {
    "id": "fpldemon",
    "name": "FPL Demon",
    "url": ("https://fpldemon.com/fpl/planner"
            "?utm_source=goaliq&utm_medium=social&utm_campaign=goaliq"),
    # Kokeilu GW10:n loppuun; katsaus ti 10.11. (rutiini trig_015PLmRamWe8S1J9ZBJMvtGP).
    "active_until": "2026-11-10",
    # Versio A (HANDOVER, kumppanilinkkirivi). Vaihdetaan B:hen tai C:hen
    # deployn yhteydessa jos solver ei kayta lukujamme tai horisontti on eri.
    "claim": "{name}'s planner and solver run on these projections.",
    "cta": "Plan your transfers there",
}


def partner_active(p: dict, now: datetime) -> bool:
    """True = linkki saa nakya. Puuttuva tai virheellinen paiva = ei nayteta
    (fail-closed: vanhentunut vaite on pahempi kuin puuttuva linkki)."""
    try:
        until = datetime.fromisoformat(str(p.get("active_until") or ""))
    except ValueError:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now < until


def partner_line_html(p: dict, now: datetime, surface: str) -> str:
    """Kumppanirivi hub-sivulle, tai "" kun kumppanuus ei ole voimassa.

    rel="sponsored": sovittu vastavuoroinen linkki, ei riippumaton suositus
    (hakukoneille sama kuin "Partner:"-merkinta lukijalle). Klikkaus kirjataan
    samalla tapahtumanimella kuin SPA kayttaisi, jotta meidan puolen luku on
    verrattavissa Demonin utm-lukuun.
    """
    if not partner_active(p, now):
        return ""
    pid = escape(p["id"], quote=True)
    surf = escape(surface, quote=True)
    return (
        '<p class="note"><strong>Partner:</strong> '
        f'{escape(p["claim"].format(name=p["name"]), quote=False)} '
        f'<a href="{escape(p["url"], quote=True)}" target="_blank" '
        'rel="noopener sponsored" '
        "onclick=\"window.posthog&amp;&amp;posthog.capture('partner_link_clicked',"
        f"{{partner:'{pid}',surface:'{surf}'}})\">"
        f'{escape(p["cta"], quote=False)}</a>.</p>'
    )
