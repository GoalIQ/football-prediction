"""Kumppanit (26.9.2026). YKSI paikka kumppanin nimelle, linkille, seuranta-
tageille ja paattymispaivalle (saanto 6a): pinta ei kirjoita URL:ia kasin,
joten tagi tai paattyminen ei voi unohtua yhdesta paikasta.

FPL Demon: GoalIQ:n xP-syote (/api/partner/xp) pyorittaa hanen plannerinsa ja
solverinsa, sovittu X DM:ssa 26.9 (kokeilu GW10:n loppuun). Me linkitamme
hanen planneriinsa (ehtojen kohta 4).

SIJOITUS (Villen paatos 27.9): ILMAINEN /fpl/expected-points -sivu, GW-top 20
-taulukon alle (#gw-xp). Kierroskohtainen taulukko on se luku jonka hanen
plannerinsa nayttaa, ja koko top 100 jaa linkin ja sivun lopun UPSELL/CTA:n
valiin. Ensimmainen hub-versio oli top 100:n alla, ja julkaisutarkistaja mittasi
27.9 (390x844): linkki ja ostonappi samassa puhelinruudussa 424 px:n paassa,
valissa sivun maksullisuuslause (upsell-kappale). Ensimmainen versio kaikkiaan (fp `feat/partner-link-demon`) oli vain
maksajan SPA-listan alla, ja sen nakisi 4-5 maksajaa joilla on jo oma
planneri: Demonin utm-seuranta nayttaisi nollaa, vaikka lupasimme "tracked
links both ways". EI lukitussa esikatselussa eika paywallissa: se on
ostohetki, ja linkki tarjoaisi siina ilmaisen vaihtoehdon joka pyorii meidan
luvuillamme.

KORTTI JA TOINEN PINTA (Villen paatos 28.9): 12 px harmaa alaviiterivi ei
nakynyt, kun Demon antaa meille logopillerin plannerinsa kentan ylla ja
yläpalkin valilehden. Nyt sama kortti kahdella ilmaisella pinnalla:
/fpl/expected-points GW-taulukon alaviitteiden jalkeen ja /fpl-paasivulla
heti heron jalkeen (meidan oma Premium-nappi ensin). Ei navigaatioon: se veisi
kavijan pois jokaiselta sivulta, myos ostohetkelta.

ETUSIVU (Villen paatos 28.9 "tasapainotetaan nakyvyydessa"): Demon antaa meille
ylapalkin valilehden joka sivulla ja logopillerin plannerinsa ensimmaiselle
ruudulle; meilla kortti oli 1.2-3.4 ruutua alaspain. Etusivun heron oikea
sarake on meidan xP-taulukkomme, eli sama luku jota hanen plannerinsa kayttaa:
kortti tarkkuussirun ja nostetun muistion valiin. Tyopoydalla ensimmaisella
ruudulla, puhelimella meidan omien heronappien JALKEEN (ne ovat DOM-jarjestyksessa
ennen oikeaa saraketta). EI Pro-SPA:han: siella sen nakisivat lahinna maksajat,
ja lukittu esikatselu on ostohetki (Villen paatos 27.9).
Etusivun muuttujat ovat --panel ja --font-mono; CSS lukee ne varalla.

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
    # Julkaisutarkistaja 27.9: EI "these projections" (rivin lahella on
    # horisonttisumma, jota hanen plannerissaan ei ole missaan muodossa) eika
    # "and solver" (lukija ei voi tarkistaa ilman Team ID:ta). "five" on
    # syotteen horisontti: portti sitoo sen api/partner_feed.PARTNER_XP_HORIZONiin.
    "claim": "{name}'s planner uses our xP for the next five gameweeks.",
    "cta": "Plan your transfers there",
    # Demonin oma logo (X DM 28.9, alkuperainen 916 px JPG tallessa
    # Documents/goaliq-kumppanit/). Hanen plannerissaan meilla on logopilleri
    # kentan ylla, joten tekstinimi yksin ei ollut vastavuoroinen.
    "logo": "/assets/partners/fpldemon-logo.webp",
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


# Pinnat joilla kortti saa nakya. Uusi pinta vaatii rivin tahan JA portin
# (tests/test_partner_link.py mittaa jokaisen renderoidylta sivulta).
SURFACES = ("hub_expected_points", "hub_fpl", "hub_index")

# Hanen punaisensa, ei meidan amberimme: meidan omat ostonapit ovat amberia,
# joten kumppanin nappi ei saa nayttaa meidan CTA:lta. Kontrasti
# #FF4D57 vs --paper #1F1D1A = 5.2:1 (WCAG AA 4.5).
PARTNER_CARD_CSS = """
.partner-card{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;
gap:12px 20px;margin:22px 0;padding:14px 18px;max-width:760px;
background:var(--paper,var(--panel,#1F1D1A));border:1px solid var(--line-strong,rgba(243,242,242,.4));
border-left:4px solid #FF4D57;}
.partner-card .partner-logo{flex:none;display:block;width:44px;height:44px;border-radius:8px;}
.partner-card .partner-text{flex:1 1 200px;min-width:0;}
.partner-card .partner-kicker{display:block;margin-bottom:2px;font-family:var(--mono,var(--font-mono,monospace));
font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint,#8A847A);}
.partner-card p{margin:0;max-width:none;font-size:16px;line-height:1.45;color:var(--cream,#F3F2F2);}
.partner-card .partner-name{color:#FF4D57;font-weight:700;}
.partner-card .partner-btn{flex:none;display:inline-block;min-height:44px;padding:11px 18px;
border:1px solid #FF4D57;color:#FF4D57;font-family:var(--mono,var(--font-mono,monospace));font-size:14px;
font-weight:700;text-decoration:none;white-space:nowrap;}
.partner-card .partner-btn:hover{background:#FF4D57;color:var(--ink,#0B0A09);}
@media (max-width:520px){.partner-card .partner-btn{width:100%;text-align:center;}}
"""


def partner_card_html(p: dict, now: datetime, surface: str) -> str:
    """Kumppanikortti hub-sivulle, tai "" kun kumppanuus ei ole voimassa.

    Kortin CSS on PARTNER_CARD_CSS; sivu joka kutsuu tata liittaa sen omaan
    <style>-lohkoonsa (portti tarkistaa etta molemmat ovat sivulla).

    rel="sponsored": sovittu vastavuoroinen linkki, ei riippumaton suositus
    (hakukoneille sama kuin "Partner"-merkinta lukijalle). Klikkaus kirjataan
    samalla tapahtumanimella kuin SPA kayttaisi, jotta meidan puolen luku on
    verrattavissa Demonin utm-lukuun; `surface` erottaa pinnat.
    """
    if surface not in SURFACES:
        raise ValueError(f"tuntematon kumppanipinta: {surface!r}")
    if not partner_active(p, now):
        return ""
    pid = escape(p["id"], quote=True)
    surf = escape(surface, quote=True)
    name = f'<b class="partner-name">{escape(p["name"], quote=False)}</b>'
    claim = escape(p["claim"], quote=False).replace("{name}", name)
    # alt="": nimi on heti vieressa tekstina, ruudunlukija lukisi sen muuten
    # kahdesti. width/height varaavat tilan ennen latausta (ei layout-hyppya).
    logo = (f'<img class="partner-logo" src="{escape(p["logo"], quote=True)}" '
            'width="44" height="44" alt="" loading="lazy" decoding="async">'
            if p.get("logo") else "")
    return (
        f'<aside class="partner-card" aria-label="Partner: {escape(p["name"], quote=True)}">'
        f'{logo}<div class="partner-text"><span class="partner-kicker">Partner</span>'
        f"<p>{claim}</p></div>"
        f'<a class="partner-btn" href="{escape(p["url"], quote=True)}" target="_blank" '
        'rel="noopener sponsored" '
        "onclick=\"window.posthog&amp;&amp;posthog.capture('partner_link_clicked',"
        f"{{partner:'{pid}',surface:'{surf}'}})\">"
        f'{escape(p["cta"], quote=False)} &rarr;</a></aside>'
    )
