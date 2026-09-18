"""Vaihetestit vapaa/premium-lauseelle: invariantti mitataan JOKA VAIHEESSA.

MITATTU VIKA (18.9.2026). `scripts/build_fpl_longtail.py` paistoi sivulle
`/fpl/expected-points` lauseen joka niputti nelja tyokalua premiumiksi;
kaksi niista (`rate-my-team`, `watchlist`) on rekisterissa `tier: 'free'`.
Vika oli KONVERSION KANNALTA VAARINPAIN: se kertoi ilmaiskayttajalle ettei
han paase parhaaseen ilmaiseen tyokaluumme.

Saanto 6a kohta 3: testi joka ajetaan vain NYKYISELLA rekisterilla on vihrea
siihen asti kun se lakkaa olemasta tosi. Siksi jokainen tapaus alla ajaa
saman koodin SYNTEETTISELLA rekisterilla, myos sellaisella jossa tier on eri
kuin tanaan. Juurisyy on nimenomaan se ettei rekisterin ja proosan valilla
ollut mitaan sidosta — proosa ei liikkuisi vaikka tier vaihtuisi.

Tapaukset:
  (a) tyokalu on free   -> lause ei sano sita premiumiksi
  (b) tyokalu on premium-> lause ei sano sita ilmaiseksi
  (c) tier VAIHTUU free -> premium: sama kutsu tuottaa eri lauseen
  (d) tier vaihtuu premium -> free: sama
  (e) sekalista         -> lause jakaa luokat eika niputa
  (f) tyokalu poistetaan-> lukija kaatuu nakyvasti, ei tulosta tyhjaa
  (g) uusi tyokalu      -> mikaan olemassa oleva lause ei ala valehdella,
                           eika uutta voi nimeta ennen kuin sille on
                           kirjoitettu sanamuoto JA kattopaatos
  (h) lahteen editointi -> kommentoitu tier-rivi, prefiksinimi ja puuttuva
                           kattovakio kaatavat ajon eivatka hiljene
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tool_tiers import (  # noqa: E402
    MissingCap,
    MissingCopy,
    ToolTierError,
    ToolTiers,
    UnknownTool,
    WrongTier,
)

PREFS = "export const WATCHLIST_FREE_LIMIT = 3;\nexport const WATCHLIST_MAX = 50;\n"

# Neljan tyokalun slugit ovat samat kuin oikeassa rekisterissa, jotta
# tapaukset osuvat juuri siihen lauseeseen joka 18.9 oli vaarin.
_QUAD = ["rate-my-team", "watchlist", "transfer-planner", "captain-ranker"]


def _registry(entries: list[tuple[str, str, str]]) -> str:
    """Synteettinen `tools.ts`. Muoto on rekisterin muoto, ei kopio sen
    sisallosta: tier annetaan tapauskohtaisesti."""
    body = ",\n".join(
        "\t{\n"
        f"\t\tslug: '{slug}',\n"
        "\t\tgroup: 'team',\n"
        f"\t\ttitle: '{title}',\n"
        "\t\tquestion: 'Testikysymys?',\n"
        f"\t\ttier: '{tier}',\n"
        f"\t\tanchor: 'a-{slug}'\n"
        "\t}"
        for slug, title, tier in entries
    )
    return "export const TOOLS: Tool[] = [\n" + body + "\n];\n"


_TODAY = [
    ("rate-my-team", "Rate my team", "free"),
    ("watchlist", "Watchlist", "free"),
    ("transfer-planner", "Transfer planner", "premium"),
    ("captain-ranker", "Captain ranker", "premium"),
]


def _reader(entries) -> ToolTiers:
    return ToolTiers(_registry(entries), PREFS)


def _swap(entries, slug: str, tier: str):
    return [(s, t, tier if s == slug else tr) for s, t, tr in entries]


_PREMIUM_CLAIM = "part of GoalIQ Premium"


def _osat(sentence: str) -> tuple[list[str], list[str]]:
    """Lause pilkottuna vaitteisiin: (ilmaiset, premiumit).

    EI pilkota "ensimmainen virke on free, toinen premium" -oletuksella. Se
    oletus meni lapi mutaatiolla joka palautti yhden kovakoodatun virkkeen:
    virke 2 oli tyhja, ja free-tarkistus lapaisi tyhjaa vasten. Luokittelu
    tehdaan siita mita virke VAITTAA.
    """
    lauseet = [s.strip() for s in sentence.split(".") if s.strip()]
    premium = [x for x in lauseet if x.endswith(_PREMIUM_CLAIM)]
    free = [x for x in lauseet if x not in premium and " free" in x]
    return free, premium


# --------------------------------------------------------------------------
# (a) ja (b): luokka pitaa molempiin suuntiin
# --------------------------------------------------------------------------


@pytest.mark.parametrize("slug", ["rate-my-team", "watchlist"])
def test_a_free_tyokalua_ei_sanota_premiumiksi(slug: str) -> None:
    r = _reader(_TODAY)
    sentence = r.tier_sentence(_QUAD)
    phrase = r.phrase(slug).lower()
    free, premium = _osat(sentence)
    assert not any(phrase in x.lower() for x in premium), (
        f"{slug} on rekisterissa free mutta lause sanoo sita premiumiksi: {sentence}"
    )
    assert any(phrase in x.lower() for x in free), (
        f"{slug} on rekisterissa free mutta ei nay ilmaisessa vaitteessa: {sentence}"
    )
    # Ja suora kielto: premium-lauseen pyytaminen free-tyokalulle kaatuu.
    with pytest.raises(WrongTier):
        r.premium_sentence([slug])


@pytest.mark.parametrize("slug", ["transfer-planner", "captain-ranker"])
def test_b_premium_tyokalua_ei_sanota_ilmaiseksi(slug: str) -> None:
    r = _reader(_TODAY)
    sentence = r.tier_sentence(_QUAD)
    phrase = r.phrase(slug).lower()
    free, premium = _osat(sentence)
    assert not any(phrase in x.lower() for x in free), (
        f"{slug} on rekisterissa premium mutta lause sanoo sita ilmaiseksi: {sentence}"
    )
    assert any(phrase in x.lower() for x in premium), sentence
    with pytest.raises(WrongTier):
        r.free_sentence([slug])


# --------------------------------------------------------------------------
# (c) ja (d): TIER VAIHTUU, lause seuraa ilman etta proosaa kosketaan
# --------------------------------------------------------------------------


def test_c_tier_vaihtuu_free_premiumiksi_lause_muuttuu() -> None:
    """Tama on juurisyy. 18.9 mikaan ei sitonut proosaa rekisteriin, joten
    tier olisi voinut vaihtua eika lause olisi liikkunut lainkaan."""
    ennen = _reader(_TODAY).tier_sentence(_QUAD)
    jalkeen = _reader(_swap(_TODAY, "rate-my-team", "premium")).tier_sentence(_QUAD)
    assert ennen != jalkeen, "tier vaihtui mutta lause pysyi samana"
    e_free, e_prem = _osat(ennen)
    j_free, j_prem = _osat(jalkeen)
    assert any("rate my team" in x.lower() for x in e_free), ennen
    assert not any("rate my team" in x.lower() for x in e_prem), ennen
    assert any("rate my team" in x.lower() for x in j_prem), jalkeen
    assert not any("rate my team" in x.lower() for x in j_free), jalkeen


def test_d_tier_vaihtuu_premiumista_ilmaiseksi_lause_muuttuu() -> None:
    ennen = _reader(_TODAY).tier_sentence(_QUAD)
    jalkeen = _reader(_swap(_TODAY, "captain-ranker", "free")).tier_sentence(_QUAD)
    assert ennen != jalkeen, "tier vaihtui mutta lause pysyi samana"
    e_free, e_prem = _osat(ennen)
    j_free, j_prem = _osat(jalkeen)
    assert any("the captain ranker" in x.lower() for x in e_prem), ennen
    assert any("the captain ranker" in x.lower() for x in j_free), jalkeen
    assert not any("the captain ranker" in x.lower() for x in j_prem), jalkeen


def test_d2_kaikki_free_ei_jata_premium_lausetta_roikkumaan() -> None:
    entries = [(s, t, "free") for s, t, _ in _TODAY]
    sentence = _reader(entries).tier_sentence(_QUAD)
    assert "Premium" not in sentence.replace("on Premium", ""), sentence


# --------------------------------------------------------------------------
# (e) sekalista jaetaan, ei niputeta
# --------------------------------------------------------------------------


def test_e_sekalista_jakautuu_kahteen_lauseeseen() -> None:
    sentence = _reader(_TODAY).tier_sentence(_QUAD)
    free, premium = _osat(sentence)
    assert len(free) == 1 and len(premium) == 1, (
        "sekalista ei jakautunut kahteen erilliseen vaitteeseen: " + sentence
    )
    for nimi in ("rate my team", "your watchlist"):
        assert nimi in free[0].lower(), sentence
        assert nimi not in premium[0].lower(), sentence
    for nimi in ("the transfer planner", "the captain ranker"):
        assert nimi in premium[0].lower(), sentence
        assert nimi not in free[0].lower(), sentence


def test_e2_watchlistin_katto_on_lauseessa() -> None:
    """`tier: 'free'` yksin olisi harhaanjohtava: ilmaisella on katto.
    Luku tulee prefs.ts:sta, ei kasin kirjoitettuna."""
    sentence = _reader(_TODAY).tier_sentence(_QUAD)
    assert "three free, up to 50 on Premium" in sentence, sentence
    muu = ToolTiers(
        _registry(_TODAY),
        "export const WATCHLIST_FREE_LIMIT = 5;\nexport const WATCHLIST_MAX = 80;\n",
    ).tier_sentence(_QUAD)
    assert "five free, up to 80 on Premium" in muu, muu


# --------------------------------------------------------------------------
# (f) poistettu tyokalu kaataa nakyvasti
# --------------------------------------------------------------------------


def test_f_poistettu_tyokalu_kaataa_eika_tulosta_tyhjaa() -> None:
    ilman = [e for e in _TODAY if e[0] != "watchlist"]
    r = _reader(ilman)
    with pytest.raises(UnknownTool) as exc:
        r.tier_sentence(_QUAD)
    assert "watchlist" in str(exc.value)


def test_f2_tyhja_rekisteri_kaataa() -> None:
    with pytest.raises(Exception):
        ToolTiers("export const TOOLS: Tool[] = [\n];\n", PREFS)


# --------------------------------------------------------------------------
# (g) uusi tyokalu ei saa muuttaa olemassa olevia lauseita valheeksi
# --------------------------------------------------------------------------


@pytest.mark.parametrize("uusi_tier", ["free", "premium"])
def test_g_uusi_tyokalu_ei_muuta_vanhaa_lausetta(uusi_tier: str) -> None:
    ennen = _reader(_TODAY).tier_sentence(_QUAD)
    laajennettu = _TODAY + [("chip-timing", "Chip timing", uusi_tier)]
    jalkeen = _reader(laajennettu).tier_sentence(_QUAD)
    assert ennen == jalkeen, "uusi rekisteririvi muutti lausetta jota ei pyydetty"
    assert "chip timing" not in jalkeen.lower()
    # ...ja rekisterin oma luku seuraa heti, ilman etta proosaa on olemassa.
    assert _reader(laajennettu).tier("chip-timing") == uusi_tier


@pytest.mark.parametrize("uusi_tier", ["free", "premium"])
def test_g2_uutta_tyokalua_ei_voi_nimeta_ilman_kirjoitettua_proosaa(
    uusi_tier: str,
) -> None:
    """🔴 KIERROS 2. Aiemmin proosa johdettiin rekisterin otsikosta
    ("the " + title.lower()). Se lupasi toimivan muodon jota ei ollut:
    23 slugista 15 tuotti julkaisukelvotonta englantia ("The value is free
    and needs no account.", "The player xp is part of GoalIQ Premium.").
    Oletus on poistettu: uusi tyokalu KAATAA lauseen kunnes joku kirjoittaa
    seka sanamuodon etta kattopaatoksen, ja molemmat jaavat diffiin.
    """
    laajennettu = _TODAY + [("chip-timing", "Chip timing", uusi_tier)]
    r = _reader(laajennettu)
    with pytest.raises(MissingCopy) as exc:
        r.tier_sentence(_QUAD + ["chip-timing"])
    assert "chip-timing" in str(exc.value)
    # Kaatuminen ei saa olla "tuntematon slug": rekisteri TUNTEE sen.
    assert r.tier("chip-timing") == uusi_tier


# --------------------------------------------------------------------------
# (h) LAHTEEN EDITOINTI. Nama nelja reittia palauttivat kierroksella 1
# hiljaa vaaran tai tyhjan. Jokainen on mitattu; nyt jokainen kaataa ajon.
# --------------------------------------------------------------------------

_KOMMENTOITU = "\n".join([
    "export const TOOLS: Tool[] = [",
    "\t{",
    "\t\tslug: 'rate-my-team',",
    "\t\tgroup: 'team',",
    "\t\ttitle: 'Rate my team',",
    "\t\tquestion: 'Testikysymys?',",
    # 🔴 Tasan tama rivi: vanha arvo jatetaan nakyviin kommenttiin.
    "\t\t// tier: 'premium' aiemmin",
    "\t\ttier: 'free',",
    "\t\tanchor: 'a-rate'",
    "\t}",
    "];",
    "",
])


def test_h1_kommentoitu_tier_rivi_ei_ole_arvo() -> None:
    """🔴 Mitattu: `// tier: 'premium' aiemmin` OIKEAN `tier: 'free'`:n
    ylapuolella -> lukija palautti premium, ilman poikkeusta. Tama on tasan
    se editointitapa jolla tier-muutos tehdaan: vanha rivi kommentoidaan."""
    r = ToolTiers(_KOMMENTOITU, PREFS)
    assert r.tier("rate-my-team") == "free", (
        "kommentoitu vanha tier-rivi luettiin arvoksi"
    )


def test_h1b_kaksi_oikeaa_tier_kenttaa_kaataa() -> None:
    """Erotteleva kontrolli h1:lle. Jos kommentin poisto olisi toteutettu
    niin etta lukija vain ottaa ENSIMMAISEN osuman, tama menisi lapi: kaksi
    OIKEAA tier-kenttaa on epaselva lahde, ei asia jonka lukija saa valita.
    """
    kaksi = _KOMMENTOITU.replace(
        "\t\t// tier: 'premium' aiemmin", "\t\ttier: 'premium',"
    )
    with pytest.raises(ToolTierError):
        ToolTiers(kaksi, PREFS)


def test_h1c_kommentti_ei_niela_oikeaa_kenttaa() -> None:
    """Positiivinen kontrolli: kommenttien poisto ei saa syoda rivin loppua.
    Naiivi regex katkaisisi `title`-rivin URL-merkkijonon kaksoiskauttaviivan
    kohdalta ja rekisteri jaisi vajaaksi."""
    url_rivi = _KOMMENTOITU.replace(
        "\t\ttitle: 'Rate my team',",
        "\t\ttitle: 'Rate my team', // ks. https://goaliq.app/fpl",
    )
    r = ToolTiers(url_rivi, PREFS)
    assert r.title("rate-my-team") == "Rate my team"
    assert r.tier("rate-my-team") == "free"


def test_h2_prefiksinimi_ei_kelpaa_rekisteriksi() -> None:
    """🔴 Mitattu: `text.index('export const TOOLS')` osui `TOOLSET_META`:an,
    ja lukija luki hiljaa vaaran taulukon."""
    meta = "\n".join([
        "export const TOOLSET_META: Meta[] = [",
        "\t{ slug: 'ei-tama', group: 'x', title: 'Ei tama',",
        "\t  question: 'q', tier: 'premium', anchor: 'a' }",
        "];",
        "",
    ])
    r = ToolTiers(meta + _registry(_TODAY), PREFS)
    assert "ei-tama" not in r.slugs(), "lukija luki TOOLSET_META:n TOOLSina"
    assert r.tier("rate-my-team") == "free"


def test_h3_kaksi_samannimista_taulukkoa_kaataa() -> None:
    with pytest.raises(ToolTierError):
        ToolTiers(_registry(_TODAY) + _registry(_TODAY), PREFS)


def test_h4_puuttuva_kattovakio_on_virhe_ei_none() -> None:
    """🔴 Mitattu: jos `prefs.ts` siirtyy tai vakiot nimetaan uudelleen,
    `caveat()` palautti hiljaa Nonen ja lause olisi sanonut watchlistista
    vain "free" — yhta harhaanjohtava kuin se lause joka 18.9 korjattiin."""
    r = ToolTiers(_registry(_TODAY), "")
    with pytest.raises(MissingCap) as exc:
        r.tier_sentence(_QUAD)
    assert "WATCHLIST_FREE_LIMIT" in str(exc.value)
    vain_alaraja = ToolTiers(
        _registry(_TODAY), "export const WATCHLIST_FREE_LIMIT = 3;"
    )
    with pytest.raises(MissingCap):
        vain_alaraja.tier_sentence(_QUAD)
    vain_ylaraja = ToolTiers(_registry(_TODAY), "export const WATCHLIST_MAX = 50;")
    with pytest.raises(MissingCap):
        vain_ylaraja.tier_sentence(_QUAD)


def test_h5_katto_seuraa_lahdetta_myos_uudella_arvolla() -> None:
    """Positiivinen kontrolli h4:lle: kaatuminen ei saa olla ainoa reitti.
    Kun vakio on olemassa, luku tulee LAHTEESTA eika koodista."""
    muut = "\n".join([
        "export const WATCHLIST_FREE_LIMIT = 7;",
        "export const WATCHLIST_MAX = 99;",
        "",
    ])
    r = ToolTiers(_registry(_TODAY), muut)
    assert "seven free, up to 99 on Premium" in r.tier_sentence(_QUAD)


def test_h6_katto_lukee_oikean_vakion_ei_prefiksia() -> None:
    """`WATCHLIST_MAX` ei saa lukea `WATCHLIST_MAX_ROWS`ia eika toisin pain."""
    harha = "\n".join([
        "export const WATCHLIST_FREE_LIMIT = 3;",
        "export const WATCHLIST_MAX_ROWS = 999;",
        "export const WATCHLIST_MAX = 50;",
        "",
    ])
    r = ToolTiers(_registry(_TODAY), harha)
    assert "three free, up to 50 on Premium" in r.tier_sentence(_QUAD)
