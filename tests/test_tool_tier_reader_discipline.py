"""Poikkeuslista jossa on perustelu: tier-vaite kirjoitetaan lukijan kautta.

MITATTU VIKA (18.9.2026). `scripts/build_fpl_longtail.py` nimesi nelja
tyokalua premiumiksi yhdessa lauseessa; kaksi oli rekisterissa `tier: 'free'`.
Lause ei ollut vanhentunut vaan se ei ollut koskaan ollut tosi tassa repossa
(`git log -S` -> vain juuricommit 0499c2709). Lahin ohitus oli 29f75134b
(4.9 copy-sync), joka kaveli kasin tasan yhdeksan pintaa — ja
`build_fpl_longtail.py` ei ollut listalla, koska PINTALISTA OLI
MUISTINVARAINEN EIKA JOHDETTU.

🔴 KIERROS 2 (18.9, adversariaalinen kumoaja). Kierroksen 1 portti oli
vihrea kolmessa tapauksessa joissa sama vaite oli yha sivulla. Kaikki kolme
on mitattu, ja jokainen on nyt fikstuurina alla:

  P1-1  SAMA VAARA VAITE 1500 RIVIA YLEMPANA. `render_club_best`-docstring
        sanoi "Rate-my-team, siirtosuunnittelija ja kapteenirankkeri pysyvat
        premiumina". Portti ei nahnyt sita kahdesta syysta: fraasilista tunsi
        nimen vain valilyontimuodossa (`rate my team`, rivilla luki
        `Rate-my-team`), ja tier-sana oli ERI RIVILLA kuin nimi.
  P1-2  VAPAUTUS OLI TIEDOSTOTASOINEN. Yksi `import src.tool_tiers` vapautti
        tiedoston KAIKISTA tier-vaitteista. Mitattu mutaatio: sama vaite
        sanamuodossa "are GoalIQ Premium tools" -> 25 passed, portti vihrea.
        Nyt vapautus on VAITEKOHTAINEN: teksti on kunnossa vain jos se tulee
        lukijan lausefunktion kutsusta, muuten se on poikkeuslistalla
        PERUSTELUN ja tarkistettavan vaitteen kanssa. Import ei vapauta
        mitaan.
  P1-3  SKANNERI VAATI SAMAN RIVIN. Mitattu mutaatio: sama vaite kolmelle
        riville katkaistuna implisiittisella konkatenaatiolla -> 11 passed,
        portti vihrea. 🔴 Alkuperainen vika oli ITSEKIN katkaistu kolmelle
        riville; se jai kiinni vain koska sattui olemaan yksi rivi jolla oli
        seka nimi etta tier-sana. Portti vartioi nahtya muotoilua, ei
        luokkaa (muisti `portti-kirjoitetaan-nahdylle-muodolle`). Skannaus
        lukee nyt sen tekstin joka paatyy ULOS VIEREKKAIN, ks.
        `tests/_tier_scan.py`.

NELJAS MUOTO jota kumoaja ei nimennyt ja joka meni myos lapi: vaite koostuu
KAHDESTA PAIKASTA — tyokalujen nimet ovat moduulitason vakiossa ja tier-sana
f-stringissa toisaalla. Kumpikaan puolisko ei yksin nayta vaitteelta.
Skanneri sijoittaa moduulitason merkkijonovakiot sisaan, ja fikstuuri
`test_neljas_muoto_*` mittaa sen.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from _tier_scan import claims, norm, tool_phrases  # noqa: E402
from src.tool_tiers import load  # noqa: E402

# 🔴 Kierroksen 1 vapautus oli `READER_IMPORT.search(text)` KOKO TIEDOSTOLLE.
# Se on poistettu, eika tilalle tullut mitaan tiedostotasoista: ainoa
# automaattinen vapautus on se etta vaitteen teksti tulee lukijan
# lausefunktiosta, jolloin sita ei ole lahteessa lainkaan (`_tier_scan`
# nollaa kutsun lahdealueen). Tama rivi jaa tanne siksi etta
# `test_korjattu_tiedosto_*` mittaa yha kutsupaikan importin.
READER_IMPORT = re.compile(
    r"^\s*(from\s+src\.tool_tiers\s+import|import\s+src\.tool_tiers)", re.M
)

# Pintoja skannataan Python-puolelta. `api/` on mukana kierroksesta 2:
# palvelin on se paikka jossa tier oikeasti ratkeaa, ja sen kommentit
# tekevat tier-vaitteita. SPA ja mobiili ovat eri kielet ja omien
# porttiensa takana (SPA: tests/test_spa_tool_registry.py).
SCAN_GLOBS = ("scripts/*.py", "src/**/*.py", "api/*.py")

# Lukija itse ei ole pinta: sen koodi KIRJOITTAA tier-sanat ja sen
# `_COPY`-taulu on niiden lahde. Tama on maaritelma, ei poikkeus, joten se
# ei kuulu ALLOWED-listalle.
READER_FILE = "src/tool_tiers.py"

_MIN_REASON = 40


class Poikkeus:
    """Yhden VAITTEEN poikkeus, ei tiedoston.

    `ote` on se tekstinpatka joka yksiloi vaitteen. Se vertaillaan
    normalisoituna, joten viivat, alaviivat ja rivinvaihdot eivat vaikuta.
    Jos vaitteen sanamuoto muuttuu, ote lakkaa osumasta ja vaite palaa
    porttiin — poikkeus ei siis peri uutta tekstia.

    `premium` ja `free` ovat ne tier-vaitteet jotka ote tekee. Ne
    tarkistetaan rekisterista, joten kirjattu poikkeus voi olla vaara vain
    jos kirjoittaja jattaa vaitteen kirjaamatta, ja silloin diffissa nakyy
    tyhja kentta.
    """

    def __init__(self, ote: str, reason: str, premium=(), free=()) -> None:
        self.ote = norm(ote).strip()
        self.raw_ote = ote
        self.reason = reason
        self.premium = tuple(premium)
        self.free = tuple(free)

    def kattaa(self, vaite) -> bool:
        return bool(self.ote) and self.ote in vaite.text


# --------------------------------------------------------------------------
# POIKKEUSLISTA. Yksi rivi per VAITE. Jokainen on tietoinen valinta.
# --------------------------------------------------------------------------
ALLOWED: dict[str, list[Poikkeus]] = {
    "scripts/build_fpl_longtail.py": [
        Poikkeus(
            ote="CaptainRanker on kokonaan premium",
            reason=(
                "Moduulin docstring ja rivin 706 kommentti kirjaavat 3.8.2026 "
                "kiinni saadun premium-vuodon: best-captain-sivun alkuperainen "
                "perustelu oli vaara premissi. Se on vian historia eika sivulle "
                "paistettavaa copya. Vaite tarkistetaan alla rekisterista."
            ),
            premium=("captain-ranker",),
        ),
        Poikkeus(
            ote='Se EI pida paikkaansa: CaptainRanker',
            reason=(
                "Sama 3.8 kirjattu vuoto, mutta rivin 706 kommenttilohkossa "
                "vaite katkeaa rivinvaihtoon kesken lauseen, joten se on eri "
                "tekstinpatka kuin docstringin. Vaite on sama ja se "
                "tarkistetaan rekisterista."
            ),
            premium=("captain-ranker",),
        ),
        Poikkeus(
            ote="price watch on ilmainen appissa",
            reason=(
                "Moduulin docstring perustelee miksi price-changes-sivu saa "
                "nayttaa koko risers/fallers-listan: sama sisalto on appissa "
                "ilmainen. Perustelu, ei julkista copya."
            ),
            free=("price-watch",),
        ),
        Poikkeus(
            ote="jonka kilpailijat antavat ilmaiseksi",
            reason=(
                "xg-leaders-docstring kirjaa 26.7 tehdyn paatoksen purkaa "
                "maksumuuri hyodykedatan paalta. Historiaa, ei copya."
            ),
        ),
        Poikkeus(
            ote="katsoviin mallin tuotoksiin (xP, captain ranker)",
            reason=(
                "Sama docstring, jatkolause: mihin upsell siirtyi kun leaders "
                "vapautui. Nimeaa tyokalun mutta ei luokittele sita."
            ),
        ),
        Poikkeus(
            ote="transfer planner, chip timing)",
            reason=(
                "UPSELL-vakio on JULKISTA COPYA jokaisen long-tail-sivun "
                "alalaidassa. Se ei ole tier-listaus vaan yksi myyntilause, "
                "eika lukija tuota sita. Kolme nimettya tyokalua tarkistetaan "
                "alla rekisterista; jos jokin niista muuttuu ilmaiseksi, tama "
                "portti kaatuu ennen kuin sivu paistetaan."
            ),
            premium=("captain-ranker", "transfer-planner", "chip-timing"),
        ),
    ],
    "scripts/build_fpl_page.py": [
        Poikkeus(
            ote="captain ranker, chip timing for the best Wildcard",
            reason=(
                "fpl.html:n FAQ-vastaus listaa ilmaisen ja maksullisen puolen "
                "samassa kappaleessa. Se on pitka myyntiteksti eika "
                "tier-listaus, ja sen kaantaminen lukijan lauseiksi on eri tyo "
                "(koko FAQ, ei yksi lause). Molemmat puolet tarkistetaan alla "
                "rekisterista."
            ),
            premium=("captain-ranker", "chip-timing", "edge-mode"),
            free=("rate-my-team", "fit-checker", "price-watch"),
        ),
        Poikkeus(
            ote="clean sheet outlook and price watch tables on the web",
            reason=(
                "Saman FAQ-vastauksen ilmaispuolen loppu: jakokortit "
                "ilmaisista taulukoista. Nimeaa kaksi ilmaista tyokalua, "
                "molemmat tarkistetaan rekisterista."
            ),
            free=("clean-sheets", "price-watch"),
        ),
        # 22.9.2026: poistettu poikkeus "rate my team with a captain pick, a
        # fit checker" (Organization.description). Kuvaus on nyt
        # identiteetti eika ominaisuuslista (src/site_identity.py,
        # web-audit T7), eika siina nimeta yhtaan tyokalua.
        Poikkeus(
            ote="price watch, expected points for the next gameweek (the top 20, web)",
            reason=(
                "Sivun `<meta name=description>`. Sama myyntiteksti "
                "hakutulosta varten; ei sivun proosaa. Vaitteet "
                "tarkistetaan rekisterista."
            ),
            free=("price-watch",),
        ),
        Poikkeus(
            ote="Premium</a> projects clean sheets and expected points for every gameweek",
            reason=(
                "🔴 Tama EI vaita clean-sheets-tyokalua maksulliseksi, ja siksi "
                "`free`-kentta on tahallaan tyhja: lause vertaa YHTA kierrosta "
                "(tama ilmainen sivu, ja rekisterin `clean-sheets` vastaa "
                "kysymykseen 'this week') KOKO IKKUNAAN, joka on Premiumin "
                "puolella. Vaite on horisontista, ei tyokalusta. Jos "
                "clean-sheets joskus muuttuu maksulliseksi, tama lause pysyy "
                "totena eika sen kuulu kaataa porttia."
            ),
        ),
        Poikkeus(
            ote="Open GoalIQ Premium: per-gameweek xP and captain ranker",
            reason=(
                "CTA-napin teksti nimeaa kaksi tyokalua myyntilupauksessa. Se "
                "ei ole tier-listaus vaan linkin otsikko, eika lukija tuota "
                "nappitekstia. Molemmat vaitteet tarkistetaan rekisterista."
            ),
            premium=("captain-ranker", "player-xp"),
        ),
        Poikkeus(
            ote="GoalIQ Premium at pro.goaliq.app adds expected points",
            reason=(
                "Saman FAQ:n toinen vastaus ('Is there a full xP dashboard'). "
                "Nimeaa kaksi tyokalua myyntilupauksessa; molemmat "
                "tarkistetaan rekisterista."
            ),
            premium=("player-xp", "captain-ranker"),
        ),
        Poikkeus(
            ote="is free and needs no account: it names the line",
            reason=(
                "fdr-ruudukon inline-upsell. Lause on sanasta sanaan sama kuin "
                "lukijan free_sentence(['rate-my-team']), mutta se elaa "
                "keskella HTML-ankkuria jonka teksti katkeaa rivinvaihtoon, "
                "joten lukijan kutsu vaatisi linkin pilkkomisen. Molemmat "
                "vaitteet tarkistetaan rekisterista, joten tier-muutos kaataa "
                "taman."
            ),
            free=("rate-my-team",),
            premium=("transfer-chains",),
        ),
    ],
    "scripts/push_dispatch.py": [
        Poikkeus(
            ote="Kolme porttia: premium-tili, pelaaja kayttajan watchlistissa",
            reason=(
                "Sisainen push-jakelun logiikka: 'premium-tili' on tilauslippu "
                "ja 'watchlist' on kayttajan oma lista, ei tyokalun tier. "
                "Mikaan rivi ei paady julkiselle pinnalle."
            ),
        ),
        Poikkeus(
            ote="watchlist` tulevat admin-endpointilta valmiiksi",
            reason=(
                "Sama docstring, jatkolause tietolahteesta. Kertoo mista "
                "kentat tulevat, ei mihin luokkaan tyokalu kuuluu."
            ),
        ),
    ],
    "api/main.py": [
        Poikkeus(
            ote="push-tokenit premium-lipulla ja watchlistilla",
            reason=(
                "Admin-endpointin docstring: `is_premium` on tilauslippu ja "
                "`watchlist` on kayttajan rivit. Ei tyokalun tier-vaite."
            ),
        ),
        Poikkeus(
            ote="premium/watchlist vain niille riveille joilla on tili",
            reason=(
                "Saman endpointin toteutuskommentti liitoksesta. Sisainen, ei "
                "julkista pintaa."
            ),
        ),
        Poikkeus(
            ote="is_premium",
            reason=(
                "Vastauksen kentat `is_premium` ja `watchlist` ovat "
                "kayttajakohtaista dataa push-runnerille, eivat tyokalun "
                "luokkaa. Sisainen rajapinta."
            ),
        ),
        Poikkeus(
            ote="draft rater ja fit checker tarvitsevat kaikki pelaajat",
            reason=(
                "free-draft-poolin perustelu: valitsin tarvitsee koko "
                "pelaajajoukon vaikka teaser on maskattu. Koskee payloadin "
                "kokoa, ei tyokalun tieria."
            ),
        ),
        Poikkeus(
            ote="pooliin lisattiin status + news (ilmainen watchlist tarvitsee",
            reason=(
                "Perustelu sille miksi `status`/`news` on free-poolissa. Tama "
                "on watchlistin SISALTOVAATIMUS eika sen luokka."
            ),
        ),
    ],
    "src/models/fpl_player_stats.py": [
        Poikkeus(
            ote="Next-gameweek and horizon xP are GoalIQ Premium",
            reason=(
                "`MASK_TEXT` on se lause jonka PALVELIN palauttaa "
                "`meta.mask`-kentassa kun player-stats on maskattu, eli se on "
                "julkista tekstia joka nakyy jokaiselle ilmaiskayttajalle "
                "API-vastauksessa. Se ei voi tulla lukijalta: lukijan lause "
                "nimeaa tyokalun, tama nimeaa KENTAT jotka puuttuvat. Vaite "
                "tarkistetaan rekisterista."
            ),
            premium=("player-xp",),
        ),
    ],
    "api/premium.py": [
        Poikkeus(
            ote="ne ovat jo nyt ilmaisia FantasyPlayerCardissa",
            reason=(
                "Maskin perustelu: FPL:n oma saatavuustieto on jo ilmaista "
                "pelaajakortilla, joten sen pitaminen poissa maskatusta "
                "vastauksesta ei suojaisi mitaan. Vaite tarkistetaan "
                "rekisterista."
            ),
            free=("player-card",),
        ),
        Poikkeus(
            ote="ilmainen watchlist ei voi pitaa store-listauksen lupausta",
            reason=(
                "Maskin perustelu: saatavuuslippu jaa free-payloadiin jotta "
                "store-listauksen lupaus pitaa. Koskee kenttia, ei tieria."
            ),
        ),
        Poikkeus(
            ote='myyntisivu sanoo niin ("Rate my team, with a',
            reason=(
                "Maskin perustelu lainaa MYYNTISIVUN lupausta perustellakseen "
                "mihin rate-team-vastaus katkaistaan. Lainaus on se ankkuri "
                "jonka takia maski on juuri siina kohdassa. Vaite tarkistetaan "
                "rekisterista."
            ),
            free=("rate-my-team",),
        ),
    ],
}


# --------------------------------------------------------------------------
# Skannauksen ajurit
# --------------------------------------------------------------------------


def _surfaces() -> dict[str, str]:
    out = {}
    for pattern in SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            rel = path.relative_to(ROOT).as_posix()
            if rel == READER_FILE:
                continue
            out[rel] = path.read_text(encoding="utf-8", errors="replace")
    return out


def _all_claims(surfaces: dict[str, str]) -> list:
    phrases = tool_phrases(load())
    out = []
    for rel, text in surfaces.items():
        out += claims(rel, text, phrases)
    return out


def _undisciplined(
    surfaces: dict[str, str], allowed: dict[str, list[Poikkeus]]
) -> list[str]:
    """Vaitteet joita mikaan poikkeus ei kata."""
    bad = []
    for vaite in _all_claims(surfaces):
        if any(p.kattaa(vaite) for p in allowed.get(vaite.path, ())):
            continue
        bad.append(
            f"{vaite.path}:{vaite.line} {list(vaite.names)} :: {vaite.text[:180]}"
        )
    return bad


# --------------------------------------------------------------------------
# Portit
# --------------------------------------------------------------------------


def test_skanneri_loytaa_edes_jotain() -> None:
    """Kontrolli tyhjaa vastaan: jos hakusanat tai polut rikkoutuvat, koko
    portti menisi lapi hiljaa (muisti: kontrolli-lapaisi-tyhjana)."""
    surfaces = _surfaces()
    assert len(surfaces) > 50, sorted(surfaces)
    assert tool_phrases(load()), "rekisterista ei saatu yhtaan tyokalunimea"
    assert len(_all_claims(surfaces)) > 10, "skanneri ei loytanyt tier-vaitteita"


def test_jokainen_tier_vaite_kulkee_lukijan_kautta() -> None:
    bad = _undisciplined(_surfaces(), ALLOWED)
    assert not bad, (
        "nama vaitteet nimeavat tyokalun tier-yhteydessa ilman "
        "src/tool_tiers.py:n lausefunktiota eivatka ole poikkeuslistalla "
        "perusteluineen:\n  " + "\n  ".join(bad)
    )


def _reason_problems(allowed: dict[str, list[Poikkeus]]) -> list[str]:
    bad = []
    for rel, rivit in allowed.items():
        for p in rivit:
            if len(p.reason.strip()) < _MIN_REASON:
                bad.append(f"{rel}: perustelu puuttuu tai on liian lyhyt")
            elif not (ROOT / rel).exists():
                bad.append(f"{rel}: poikkeus osoittaa tiedostoon jota ei ole")
    return bad


def _claim_problems(allowed: dict[str, list[Poikkeus]]) -> list[str]:
    reader = load()
    bad = []
    for rel, rivit in allowed.items():
        for p in rivit:
            for want, slugs in (("premium", p.premium), ("free", p.free)):
                for slug in slugs:
                    got = reader.tier(slug)
                    if got != want:
                        bad.append(
                            f"{rel}: vaittaa {slug} {want}, rekisteri sanoo {got}"
                        )
    return bad


def test_poikkeuslistalla_on_perustelu() -> None:
    assert _reason_problems(ALLOWED) == []


def test_poikkeuksen_oma_vaite_tarkistetaan_rekisterista() -> None:
    assert _claim_problems(ALLOWED) == []


def test_kuollut_poikkeus_kaataa_portin() -> None:
    """Poikkeus joka ei osu mihinkaan on rotan alku: se jaa listalle
    vapauttamaan tekstia jota ei enaa ole, ja seuraava kirjoittaja lukee
    siita etta tama tiedosto on 'kasitelty'."""
    surfaces = _surfaces()
    phrases = tool_phrases(load())
    kuolleet = []
    for rel, rivit in ALLOWED.items():
        loydetyt = claims(rel, surfaces.get(rel, ""), phrases)
        for p in rivit:
            if not any(p.kattaa(v) for v in loydetyt):
                kuolleet.append(f"{rel}: ote ei osu mihinkaan: {p.raw_ote!r}")
    assert kuolleet == [], kuolleet


def test_korjattu_tiedosto_ei_vapaudu_poikkeuksella() -> None:
    """18.9 korjattu lause tulee lukijalta. Jos joku poistaa kutsun ja
    vaientaa portin poikkeuksella, tama kaatuu."""
    src = (ROOT / "scripts" / "build_fpl_longtail.py").read_text(encoding="utf-8")
    assert READER_IMPORT.search(src), "kutsupaikka ei enaa importtaa lukijaa"
    assert "tier_sentence(" in src, "kutsupaikka ei enaa kutsu lukijaa"
    for p in ALLOWED.get("scripts/build_fpl_longtail.py", []):
        assert "rate my team" not in p.ote, (
            "rate-my-teamin tier-vaite on taas poikkeuslistalla: " + p.raw_ote
        )


# --------------------------------------------------------------------------
# Negatiiviset kontrollit: TASAN ne muodot jotka menivat lapi
# --------------------------------------------------------------------------


def _osuu(lahde: str, tiedosto: str = "scripts/keksitty_sivu.py") -> list[str]:
    return _undisciplined({tiedosto: lahde}, ALLOWED)


def test_p1_2_lukijan_import_ei_vapauta_tiedostoa() -> None:
    """KUMOAJAN MUTAATIO 1 (mitattu kierroksella 1: 25 passed, portti vihrea).

    Tiedosto importtaa lukijan JA kayttaa sita, ja kirjoittaa sen viereen
    saman vaaran vaitteen kasin. Kierroksen 1 portti vapautti koko tiedoston
    importin perusteella.
    """
    lahde = (
        "from src.tool_tiers import tier_sentence\n"
        'OK = tier_sentence(["rate-my-team"])\n'
        'MUT_NOTE = "<p>Rate my team and your watchlist are GoalIQ '
        'Premium tools.</p>"\n'
    )
    bad = _osuu(lahde)
    assert bad and "keksitty_sivu" in bad[0], bad


def test_p1_2_sama_vaite_alkuperaisella_sanamuodolla() -> None:
    """Sama mutaatio silla sanamuodolla jonka kierros 1 sattui nakemaan.
    Molempien on kaaduttava, muuten portti vartioi sanamuotoa."""
    lahde = (
        "from src.tool_tiers import tier_sentence\n"
        'MUT_NOTE = "<p>Rate my team and your watchlist are part of GoalIQ '
        'Premium.</p>"\n'
    )
    assert _osuu(lahde), "portti nakee vain toisen sanamuodon"


def test_p1_3_vaite_katkaistuna_kolmelle_riville() -> None:
    """KUMOAJAN MUTAATIO 2 (mitattu kierroksella 1: 11 passed, portti vihrea).

    Implisiittinen konkatenaatio: yhdellakaan rivilla ei ole seka nimea etta
    tier-sanaa.
    """
    lahde = (
        "HTML = (\n"
        '  "<p>Rate my team and your watchlist are "\n'
        '  "part of GoalIQ Premium.</p>"\n'
        ")\n"
    )
    bad = _osuu(lahde)
    assert bad and "keksitty_sivu" in bad[0], bad
    # ...ja rivijako ei saa olla se mika ratkaisee: sama vaite viidelle
    # riville, nimi ja tier-sana neljan rivin paassa toisistaan.
    levea = (
        "HTML = (\n"
        '  "<p>Rate my team"\n'
        '  ", the transfer planner"\n'
        '  ", and your watchlist"\n'
        '  " are part of GoalIQ Premium.</p>"\n'
        ")\n"
    )
    assert _osuu(levea), "viidelle riville katkaistu vaite meni lapi"


def test_p1_1_nimi_viivoilla_ja_tier_sana_eri_rivilla() -> None:
    """P1-1 sanatarkasti: se docstring joka jai pystyyn 1500 rivia korjatun
    lauseen ylapuolelle."""
    lahde = (
        "def render_club_best(xp, now):\n"
        '    """Seuran paras pelaaja per positio.\n'
        "\n"
        "    VAPAA/PREMIUM-RAJA: tama on seurakohtainen KARKI, ei koko lista.\n"
        "    Rate-my-team, siirtosuunnittelija ja kapteenirankkeri\n"
        "    pysyvat premiumina.\n"
        '    """\n'
        "    return None\n"
    )
    bad = _osuu(lahde)
    assert bad and "keksitty_sivu" in bad[0], bad


@pytest.mark.parametrize(
    "nimi",
    ["Rate my team", "rate-my-team", "rate_my_team", "RateMyTeam", "RATE MY TEAM"],
)
def test_nimen_kirjoitusasu_ei_pelasta(nimi: str) -> None:
    """Normalisointi: viisi kirjoitusasua, sama vaite."""
    lahde = f'NOTE = "<p>{nimi} is part of GoalIQ Premium.</p>"\n'
    assert _osuu(lahde), nimi


def test_neljas_muoto_vaite_koostuu_kahdesta_paikasta() -> None:
    """NELJAS MUOTO (oma loydos, ei kumoajan listalla).

    Nimet ovat moduulitason vakiossa ja tier-sana f-stringissa toisessa
    funktiossa. Kummallakaan puoliskolla ei ole mitaan tier-vaitteelta
    nayttavaa, eika mikaan ikkuna tai konkatenaatio yhdista niita — vain
    vakion sijoitus tekee sen.
    """
    lahde = (
        '_TOOLS = "Rate my team and your watchlist"\n'
        "\n"
        "\n"
        "def johdanto():\n"
        '    return "<p>The xP ranking is open to everyone.</p>"\n'
        "\n"
        "\n"
        "def myyntilause():\n"
        '    return f"<p>{_TOOLS} are part of GoalIQ Premium.</p>"\n'
    )
    bad = _osuu(lahde)
    assert bad and "keksitty_sivu" in bad[0], bad


def test_neljas_muoto_join_listasta() -> None:
    """Sama vaite `" ".join(...)`-listana jonka alkiot ovat omilla
    riveillaan. Ei yhtaan plusmerkkia eika implisiittista konkatenaatiota."""
    lahde = (
        'NOTE = " ".join(\n'
        "    [\n"
        '        "<p>Rate my team",\n'
        '        "and your watchlist",\n'
        '        "are part of GoalIQ Premium.</p>",\n'
        "    ]\n"
        ")\n"
    )
    assert _osuu(lahde), "join-listaan piilotettu vaite meni lapi"


def test_suomenkielinen_tier_sana_loytyy() -> None:
    lahde = (
        "def _doc():\n"
        '    """Watchlist ja rate-my-team pysyvat maksullisina."""\n'
        "    return None\n"
    )
    assert _osuu(lahde), "suomenkielinen tier-sana meni lapi"


def test_html_attribuutti_ei_piilota_vaitetta() -> None:
    lahde = (
        "NOTE = '<span data-tier=\"premium\">Rate my team</span> "
        "is part of GoalIQ Premium.'\n"
    )
    assert _osuu(lahde)


# -- positiiviset kontrollit: portti ei saa kaataa oikeaa tapaa -------------


def test_lukijan_kutsu_ei_ole_vaite() -> None:
    """Slug-lista lukijan kutsussa EI ole tier-vaite: lukija kaataa ajon
    tuntemattomasta slugista ja vaarasta luokasta."""
    lahde = (
        "from src.tool_tiers import tier_sentence\n"
        "HTML = (\n"
        "    '<p class=\"note\">This ranking is free and needs no account. '\n"
        "    + tier_sentence(\n"
        '        ["rate-my-team", "watchlist", "transfer-planner", "captain-ranker"],\n'
        "        free_already_said=True,\n"
        "    )\n"
        '    + "</p>"\n'
        ")\n"
    )
    assert _osuu(lahde) == []


def test_pelkka_maininta_lukijasta_ei_vapauta() -> None:
    """Docstringissa oleva sana 'tool_tiers' ei ole lukijan kaytto."""
    lahde = (
        '"""Tier tulee src/tool_tiers.py:sta."""\n'
        'HTML = "<p>Rate my team and your watchlist are part of '
        'GoalIQ Premium.</p>"\n'
    )
    assert _osuu(lahde)


def test_phrase_ei_vapauta_tier_sanaa() -> None:
    """`phrase()` palauttaa pelkan nimen. Jos kutsupaikka kirjoittaa
    tier-sanan sen viereen, se kirjoittaa luokan itse."""
    lahde = (
        "from src.tool_tiers import load\n"
        'HTML = "<p>" + load().phrase("rate-my-team") + " is part of GoalIQ '
        'Premium.</p>"\n'
    )
    assert _osuu(lahde), "phrase()-kutsu vapautti kasin kirjoitetun tier-sanan"


# -- poikkeuslistan omat kontrollit ----------------------------------------


def test_negatiivinen_kontrolli_perustelu_puuttuu() -> None:
    bad = _reason_problems(
        {"scripts/build_fpl_page.py": [Poikkeus(ote="x", reason="ok")]}
    )
    assert bad and "perustelu" in bad[0], bad


def test_negatiivinen_kontrolli_poikkeus_osoittaa_olemattomaan_tiedostoon() -> None:
    bad = _reason_problems({"scripts/ei_ole.py": [Poikkeus(ote="x", reason="x" * 60)]})
    assert bad and "ei ole" in bad[0], bad


def test_negatiivinen_kontrolli_poikkeuksen_vaite_on_vaara() -> None:
    """Perusteltu poikkeus ei ole aukko: jos se vaittaa ilmaisen tyokalun
    premiumiksi, portti kaatuu — tasan 18.9 loydetty vaite."""
    bad = _claim_problems(
        {
            "scripts/build_fpl_page.py": [
                Poikkeus(ote="x", reason="x" * 60, premium=("rate-my-team",))
            ]
        }
    )
    assert bad and "rate-my-team" in bad[0], bad
    toinen = _claim_problems(
        {
            "scripts/build_fpl_page.py": [
                Poikkeus(ote="x", reason="x" * 60, free=("captain-ranker",))
            ]
        }
    )
    assert toinen and "captain-ranker" in toinen[0], toinen


def test_negatiivinen_kontrolli_poikkeus_ei_kata_naapurivaitetta() -> None:
    """Poikkeus vapauttaa VAITTEEN, ei tiedostoa. Sama tiedosto, kaksi
    vaitetta: vain se jonka ote osuu paasee lapi."""
    lahde = (
        'OK = "<p>Price watch is free and needs no account.</p>"\n'
        "\n"
        'MUT = "<p>Rate my team is part of GoalIQ Premium.</p>"\n'
    )
    allowed = {
        "scripts/keksitty_sivu.py": [
            Poikkeus(
                ote="Price watch is free and needs no account",
                reason="x" * 60,
                free=("price-watch",),
            )
        ]
    }
    bad = _undisciplined({"scripts/keksitty_sivu.py": lahde}, allowed)
    assert bad and all("rate my team" in b.lower() for b in bad), bad
