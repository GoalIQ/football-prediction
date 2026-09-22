"""GoalIQ:n identiteetti koneille JA ihmisille yhdesta lahteesta (22.9.2026).

TAUSTA (web-audit 22.9, T7 + brandisekaannus). Hakukoneen AI-yhteenveto
yhdisti GoalIQ:n "GOAL IQ" -nimiseen YouTube-kanavaan joka julkaisee
vedonlyontivinkkeja: haun `goaliq` vastaus alkoi YouTube-kanavan
kuvauksella ja jatkui goaliq.app:n FPL-ominaisuuksilla. Samaan aikaan:

  * `WebSite`-schemaa ei ollut millaan sivulla (Googlen sivustonimen lahde)
  * `Organization.description` oli 1 201 merkin ominaisuuslista, ei
    identiteetti, ja se oli kirjoitettu kolmeen paikkaan kolmella eri
    tekstilla (index.html, fpl.html, predictions.html)
  * `sameAs` puuttui Bluesky ja GitHub
  * erottelu muihin GoalIQ-nimisiin oli vain llms.txt:ssa, eli koneille,
    ei yhdellakaan sivulla jonka ihminen lukee

Tama moduuli on ainoa paikka jossa nama maaritellaan. Kaikki pinnat
(index.html, predictions.html ja faq.html GEN-lohkojen kautta,
build_fpl_page, build_prediction_pages) lukevat taalta.
Portti: `tests/test_site_chrome.py`.

sameAs-LISTA (tarkistettu 22.9.2026, jokainen vastasi ja on meidan):
  Play            title "GoalIQ: FPL Assistant", com.veikkoville.goaliq
  App Store       iTunes lookup id6780047163 -> 1 tulos, sama sovellus
  X @goaliqapp    bio "Free at goaliq.app"
  Bluesky         goaliqapp.bsky.social, bio "Free at goaliq.app"
  Instagram       @goaliqfpl, og:title "GoalIQ: FPL Assistant (@goaliqfpl)"
  TikTok          @goaliqfpl, bio "goaliq.app, iOS & Android"
  GitHub          org GoalIQ, repo GoalIQ/football-prediction
EI mukana:
  Threads @goaliqfpl  crawler-UA:lla 302 -> login, TASMALLEEN kuten keksitty
                      kahva (kontrolli: @zuck = 200). Ei todennettavissa,
                      ei siis sameAsiin. Lisaa kun profiili nakyy julkisesti.
  YouTube             meilla ei ole kanavaa (@goaliqapp vapaa 22.9).

Ei `founder`-tietoa: se on henkilotieto ja vaatii Villen paatoksen.
Ei sijaintia kuvaukseen (copy-saanto).

STDLIB-ONLY.
"""
from __future__ import annotations

import json

BASE = "https://goaliq.app"
ORG_ID = BASE + "/#organization"
WEBSITE_ID = BASE + "/#website"
LOGO = BASE + "/assets/brand/goaliq-appicon-512.png"

NAME = "GoalIQ"
LEGAL_NAME = "Savikurki Digital Oy"
ALTERNATE_NAMES = ["GoalIQ FPL", "GoalIQ: FPL Assistant"]

PLAY_URL = "https://play.google.com/store/apps/details?id=com.veikkoville.goaliq"
APPSTORE_URL = "https://apps.apple.com/app/id6780047163"
X_URL = "https://x.com/goaliqapp"
BLUESKY_URL = "https://bsky.app/profile/goaliqapp.bsky.social"
IG_URL = "https://www.instagram.com/goaliqfpl/"
TIKTOK_URL = "https://www.tiktok.com/@goaliqfpl"
GITHUB_URL = "https://github.com/GoalIQ"

SAME_AS = [PLAY_URL, APPSTORE_URL, X_URL, BLUESKY_URL, IG_URL, TIKTOK_URL,
           GITHUB_URL]

#: Identiteetti, ei ominaisuuslista. Alle 300 merkkia (portti mittaa).
#: Ominaisuudet elavat SoftwareApplication-kuvauksessa ja FAQ:ssa.
ORG_DESCRIPTION = (
    "GoalIQ makes Fantasy Premier League (FPL) tools for the web, iOS and "
    "Android. They run on a football match model whose predictions are "
    "logged before kickoff and graded in public, hits and misses included. "
    "Analytics, not betting."
)

#: schema.org `disambiguatingDescription`: erottaa samannimisista.
ORG_DISAMBIGUATION = (
    "GoalIQ at goaliq.app does not publish betting tips and has no YouTube "
    "channel. It is not affiliated with the GOAL IQ YouTube channel, "
    "goaliq.live or goaliq.uk."
)

# --- ihmisluettava erottelu (FAQ + footer) ---------------------------------

#: FAQ-kysymyksen ankkuri. Footerin linkki osoittaa tahan.
DISAMBIG_ANCHOR = "similar-names"
DISAMBIG_QUESTION = "Is GoalIQ the GOAL IQ YouTube channel?"
DISAMBIG_ANSWER = (
    "No. GoalIQ at goaliq.app has no YouTube channel and does not publish "
    "betting tips. It is not connected to the GOAL IQ YouTube channel, to "
    "goaliq.live or to goaliq.uk, which are separate products with a similar "
    "name. Our own channels are goaliq.app, the GoalIQ: FPL Assistant app on "
    "Google Play and the App Store, X (@goaliqapp), Bluesky "
    "(@goaliqapp.bsky.social), Instagram and TikTok (@goaliqfpl) and GitHub "
    "(GoalIQ)."
)

#: Footerin lyhyt rivi. Sama vaite kuin FAQ:ssa, eri pituus.
FOOTER_DISAMBIG_TEXT = (
    "Official GoalIQ: goaliq.app. We do not publish betting tips and have no "
    "YouTube channel."
)
DISAMBIG_BEGIN = "<!-- GEN:SITE-DISAMBIG-START src/site_identity.py renders this; do not edit by hand -->"
DISAMBIG_END = "<!-- GEN:SITE-DISAMBIG-END -->"
IDENTITY_BEGIN = "<!-- GEN:SITE-IDENTITY-START src/site_identity.py renders this; do not edit by hand -->"
IDENTITY_END = "<!-- GEN:SITE-IDENTITY-END -->"


def footer_disambig_html() -> str:
    """Footerin rivi. Inline-tyyli, koska footereilla ei ole yhteista CSS:aa."""
    return (
        '<p class="gq-disambig" style="margin:12px 0 0;font-size:13px;'
        f'line-height:1.5;">{FOOTER_DISAMBIG_TEXT} '
        f'<a href="/faq#{DISAMBIG_ANCHOR}">Sites with a similar name</a></p>'
    )


# --- schema.org --------------------------------------------------------------

def organization_ld() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": ORG_ID,
        "name": NAME,
        "legalName": LEGAL_NAME,
        "alternateName": list(ALTERNATE_NAMES),
        "url": BASE + "/",
        "logo": LOGO,
        "description": ORG_DESCRIPTION,
        "disambiguatingDescription": ORG_DISAMBIGUATION,
        "sameAs": list(SAME_AS),
    }


def publisher_node() -> dict:
    """Kompakti julkaisijasolmu pitkan hannan sivuille (ottelusivut).

    Sama @id ja sama sameAs kuin taydessa solmussa: pelkka @id-viittaus ei
    resolvoidu sivun sisalla (#121-GEO), joten nimi ja kanavat kulkevat
    mukana."""
    return {
        "@type": "Organization",
        "@id": ORG_ID,
        "name": NAME,
        "url": BASE + "/",
        "sameAs": list(SAME_AS),
    }


def website_ld() -> dict:
    """Googlen sivustonimen ensisijainen lahde. Vain etusivulle."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": WEBSITE_ID,
        "name": NAME,
        "alternateName": list(ALTERNATE_NAMES),
        "url": BASE + "/",
        "inLanguage": "en",
        "publisher": {"@id": ORG_ID},
    }


def ld_script(obj: dict) -> str:
    return ('<script type="application/ld+json">\n'
            + json.dumps(obj, ensure_ascii=False, indent=1)
            + "\n</script>")


def identity_block(with_website: bool) -> str:
    """index.html (+WebSite) ja predictions.html: Organization-lohko."""
    parts = [ld_script(organization_ld())]
    if with_website:
        parts.append(ld_script(website_ld()))
    return "\n".join(parts)


def disambig_faq_entity() -> dict:
    return {
        "@type": "Question",
        "name": DISAMBIG_QUESTION,
        "acceptedAnswer": {"@type": "Answer", "text": DISAMBIG_ANSWER},
    }
