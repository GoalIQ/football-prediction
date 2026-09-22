"""goaliq.app:n ylapalkki yhdesta lahteesta (22.9.2026, web-audit T5, Villen GO).

TAUSTA. Hubin ylapalkista oli seitseman versiota, ja jokainen eli omassa
tiedostossaan:

  landing            Free FPL tools · Match predictions · Career card · SPL ·
                     UCL · Sign in · Try Premium
  /fpl               Sign in · Open GoalIQ Premium
  FPL-alasivut       All predictions · Try it live      (build_fpl_longtail)
  ottelusivut        All predictions · Try it live      (build_prediction_pages)
  /ucl               FPL tools · Try it live            (build_ucl_page)
  /predictions       Free FPL tools · Career card · Try Premium
  /faq, /privacy     Get the free app
  /career, /creators FPL tools (-> fpl.html, 308-hyppy)
  /spl, /404         ei palkkia lainkaan

Pahin niista: FPL-alasivun palkki vei ottelu-ennusteisiin eika takaisin
/fpl:aan. Kavija joka tuli X-postauksesta /fpl/expected-pointsiin ei
nahnyt palkissa yhtaan tieta muihin FPL-tyokaluihin.

RATKAISU. Tama moduuli on ainoa paikka jossa palkin linkit ja tyyli
maaritellaan. Generaattorit kutsuvat `site_nav_html()`:ia suoraan, ja kasin
yllapidetyt juurisivut saavat saman merkkijonon GEN-lohkoon
`scripts/build_site_chrome.py`:n kautta. Portti
`tests/test_site_chrome.py` vertaa jokaisen sitemap-sivun palkkia taman
funktion tulosteeseen, joten kahdeksas versio ei voi syntya hiljaa.

JARJESTYS: FPL ensin (Villen brief 22.9: positiointi FPL edella, malli
todisteena).

TYYLI: omat luokkanimet (`gqn-*`) ja `nav.gqn`-etuliite, koska sivujen omat
elementtivalitsimet (`nav{...}`, `nav a{...}`, 404:n `a{display:block}`)
osuisivat muuten palkkiin. Jokainen ominaisuus jonka sivun CSS voi asettaa
asetetaan tassa eksplisiittisesti.

STDLIB-ONLY: generaattorit ajetaan GH Actionsissa ilman riippuvuuksia.
"""
from __future__ import annotations

from src.brand import logo_svg

PRO = "https://pro.goaliq.app/"

#: Osiolinkit, FPL ensin. (avain, teksti, href)
SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("fpl", "FPL tools", "/fpl"),
    ("predictions", "Predictions", "/predictions"),
)

#: Tili- ja ostolinkit. Premium-nappi vie hinnastonakymaan (`?tab=premium`),
#: ei pron juureen: juuri avaa tyokalunakyman eika hintoja.
SIGNIN = ("Sign in", PRO, "nav-signin")
PREMIUM = ("Try Premium", PRO + "?tab=premium", "nav")

#: Sallitut `active`-arvot. None = palkki ilman korostettua osiota.
ACTIVE_KEYS: tuple[str | None, ...] = (None,) + tuple(k for k, _, _ in SECTIONS)

BEGIN = "<!-- GEN:SITE-NAV-START src/site_nav.py renders this; do not edit by hand -->"
END = "<!-- GEN:SITE-NAV-END -->"
CSS_BEGIN = "<!-- GEN:SITE-NAV-CSS-START src/site_nav.py renders this; do not edit by hand -->"
CSS_END = "<!-- GEN:SITE-NAV-CSS-END -->"


def site_nav_html(active: str | None = None) -> str:
    """Palkki HTML:na. `active` korostaa osion (aria-current).

    Merkkijono on deterministinen: portti vertaa sivun palkkia tahan
    tulosteeseen sellaisenaan.
    """
    if active not in ACTIVE_KEYS:
        raise ValueError(f"site_nav_html: tuntematon osio {active!r}")
    secs = "".join(
        f'<a class="gqn-sec" href="{href}"'
        + (' aria-current="true"' if key == active else "")
        + f">{label}</a>"
        for key, label, href in SECTIONS
    )
    s_label, s_href, s_cta = SIGNIN
    p_label, p_href, p_cta = PREMIUM
    return (
        '<nav class="gqn" aria-label="GoalIQ">'
        '<div class="gqn-in">'
        f'<a class="gqn-brand" href="/">{logo_svg(26, "gqn-icon")}'
        # Sanamerkki yhtena elementtina: flex-gap erottaisi muuten "Goal" ja
        # "IQ" toisistaan (mitattu 22.9: palkki luki "Goal IQ").
        '<span class="gqn-word">Goal<span>IQ</span></span></a>'
        f'<div class="gqn-main">{secs}</div>'
        '<div class="gqn-acct">'
        f'<a class="gqn-signin" href="{s_href}" data-cta="{s_cta}">{s_label}</a>'
        f'<a class="gqn-cta" href="{p_href}" data-cta="{p_cta}">{p_label}</a>'
        "</div></div></nav>"
    )


# Varit kovakoodattuina eika sivun muuttujista: sivujen `--ink`/`--cream`
# tarkoittavat eri asioita eri sivuilla (faq:n `--cream` on taustavari,
# longtailin tekstivari). Palkki nayttaa samalta joka sivulla vain jos se ei
# peri niita.
SITE_NAV_CSS = (
    "nav.gqn,nav.gqn *{box-sizing:border-box;}"
    "nav.gqn{display:block;position:relative;z-index:40;margin:0;padding:0;"
    "background:#0B0A09;border:0;border-bottom:1px solid rgba(243,242,242,.18);"
    'font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;'
    "font-size:14px;line-height:1.2;text-transform:none;letter-spacing:0;}"
    "nav.gqn .gqn-in{max-width:1100px;margin:0 auto;padding:8px 20px;display:flex;"
    "align-items:center;flex-wrap:nowrap;gap:0 24px;}"
    "nav.gqn a{display:inline-flex;align-items:center;min-height:44px;margin:0;"
    "padding:0;border:0;background:none;color:#F3F2F2;text-decoration:none;"
    "font:inherit;letter-spacing:.01em;text-transform:none;white-space:nowrap;}"
    "nav.gqn a:hover{background:none;color:#F3F2F2;text-decoration:none;}"
    "nav.gqn a:focus-visible{outline:2px solid #2ED6C2;outline-offset:2px;}"
    "nav.gqn a.gqn-brand{font-size:18px;font-weight:700;gap:8px;flex:none;}"
    "nav.gqn .gqn-word{color:#F3F2F2;}"
    "nav.gqn .gqn-word span{color:#F5C542;}"
    "nav.gqn .gqn-icon{display:block;width:26px;height:26px;flex:none;margin:0;}"
    "nav.gqn .gqn-main{display:flex;align-items:center;gap:0 22px;flex:1 1 auto;}"
    "nav.gqn a.gqn-sec{font-weight:600;border-bottom:2px solid transparent;"
    "padding:2px 0 0;}"
    "nav.gqn a.gqn-sec:hover{border-bottom-color:rgba(245,197,66,.55);}"
    "nav.gqn a.gqn-sec[aria-current]{color:#F5C542;border-bottom-color:#F5C542;}"
    "nav.gqn .gqn-acct{display:flex;align-items:center;gap:0 16px;flex:none;"
    "margin-left:auto;}"
    "nav.gqn a.gqn-signin{color:#C9C4BC;font-weight:500;}"
    "nav.gqn a.gqn-signin:hover{color:#F3F2F2;}"
    "nav.gqn a.gqn-cta{min-height:40px;padding:0 14px;border:1px solid #F5C542;"
    "color:#F5C542;font-weight:700;}"
    "nav.gqn a.gqn-cta:hover{background:#F5C542;color:#0B0A09;}"
    # Puhelin: kaksi rivia. Ylarivi = merkki + tili/osto, alarivi = osiot
    # koko leveydelta. Yhdella rivilla 390 px:iin ei mahdu merkki, kaksi
    # osiota ja kaksi tililinkkia ilman etta jokin katkeaa reunaan (pron
    # T2-vika: "My team" -> "My teal").
    "@media (max-width:640px){"
    "nav.gqn .gqn-in{flex-wrap:wrap;padding:4px 16px 0;gap:0 12px;}"
    "nav.gqn .gqn-acct{order:2;gap:0 12px;}"
    "nav.gqn .gqn-main{order:3;flex:1 1 100%;gap:0;"
    "border-top:1px solid rgba(243,242,242,.12);}"
    "nav.gqn a.gqn-sec{flex:1 1 0;justify-content:center;}"
    "nav.gqn a.gqn-brand{font-size:17px;}"
    "nav.gqn a.gqn-cta{padding:0 12px;}"
    "}"
)


def site_nav_style() -> str:
    """`<style>`-elementti palkin tyylille (kasin yllapidettyjen sivujen head)."""
    return f"<style>{SITE_NAV_CSS}</style>"
