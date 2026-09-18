"""Poikkeuslista jossa on perustelu: tier-vaite kirjoitetaan lukijan kautta.

MITATTU VIKA (18.9.2026). `scripts/build_fpl_longtail.py` nimesi nelja
tyokalua premiumiksi yhdessa lauseessa; kaksi oli rekisterissa `tier: 'free'`.
Lause ei ollut vanhentunut vaan se ei ollut koskaan ollut tosi tassa repossa
(`git log -S` -> vain juuricommit 0499c2709). Lahin ohitus oli 29f75134b
(4.9 copy-sync), joka kaveli kasin tasan yhdeksan pintaa — ja
`build_fpl_longtail.py` ei ollut listalla, koska PINTALISTA OLI
MUISTINVARAINEN EIKA JOHDETTU.

Tama portti johtaa pintalistan koodista: se etsii jokaisen Python-pinnan
jossa tyokalun nimi ja tier-sana esiintyvat samalla rivilla. Sellainen pinta
joko kayttaa lukijaa (`src.tool_tiers`) tai on poikkeuslistalla PERUSTELUN
kanssa. Uusi tiedosto ei paase listalle vahingossa: testi kaatuu ja
kirjoittaja joutuu kirjoittamaan miksi, ja perustelu jaa nakyviin diffiin.

Poikkeus ei ole aukko: jos poikkeusrivi VAITTAA jotain tierista
(`premium`/`free`-kentat), vaite tarkistetaan rekisterista. Kirjattu
poikkeus voi siis olla vanhentumatta vaara vain jos sen kirjoittaja jattaa
vaitteen kirjaamatta, ja silloin diffissa nakyy tyhja kentta.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tool_tiers import load  # noqa: E402

# 🔴 Ensimmainen versio hyvaksyi pinnan jos siina esiintyi merkkijono
# "tool_tiers" missa tahansa. Kutsupaikan mutaatio (import pois, kovakoodattu
# lause takaisin) MENI SILLOIN LAPI, koska tiedoston docstringiin jai maininta
# lukijasta. Vapautuksen antaa vain oikea import, ei puhe lukijasta.
READER_IMPORT = re.compile(r"^\s*(from\s+src\.tool_tiers\s+import|import\s+src\.tool_tiers)", re.M)

# Sanat jotka tekevat rivista tier-vaitteen. Suomi mukana: 18.9 loydetyn
# vian PERUSTELU oli suomenkielisessa docstringissa samassa tiedostossa.
TIER_WORDS = re.compile(
    r"goaliq premium|part of premium|is free|are free|premiumina|ilmaiseksi"
    r"|premium-|on premium",
    re.I,
)

# Pintoja skannataan Python-puolelta: SPA ja mobiili ovat eri kielet ja
# omien porttiensa takana (SPA: tests/test_spa_tool_registry.py).
SCAN_GLOBS = ("scripts/*.py", "src/**/*.py")

# Lukija itse ei ole pinta: sen docstring lainaa 18.9 vaaraa lausetta
# todisteena, ja sen koodi kirjoittaa tier-sanat. Tama ei ole poikkeus vaan
# maaritelma, joten se ei kuulu ALLOWED-listalle.
READER_FILE = "src/tool_tiers.py"


class Poikkeus:
    """Poikkeuslistan rivi. `reason` on pakollinen ja se on proosaa."""

    def __init__(self, reason: str, premium=(), free=()) -> None:
        self.reason = reason
        self.premium = tuple(premium)
        self.free = tuple(free)


# --------------------------------------------------------------------------
# POIKKEUSLISTA. Jokainen rivi on tietoinen valinta, ei unohdus.
# --------------------------------------------------------------------------
ALLOWED: dict[str, Poikkeus] = {
    "scripts/build_fpl_page.py": Poikkeus(
        reason=(
            "CTA-napin teksti 'Open GoalIQ Premium: per-gameweek xP and captain "
            "ranker' nimeaa yhden tyokalun myyntilupauksessa. Se ei ole "
            "tier-listaus vaan linkin otsikko, eika lukija tuota nappitekstia. "
            "Vaite tarkistetaan alla rekisterista."
        ),
        premium=("captain-ranker",),
    ),
    "scripts/push_dispatch.py": Poikkeus(
        reason=(
            "Sisainen push-jakelun logiikka: 'premium-tili' on tilauslippu ja "
            "'watchlist' on kayttajan oma lista, ei tyokalun tier-vaite. "
            "Mikaan rivi ei paady julkiselle pinnalle."
        ),
    ),
    "src/models/fpl_fit.py": Poikkeus(
        reason=(
            "Moduulin docstringin 'premium-trio' tarkoittaa kayttajan lukitsemia "
            "kalliita pelaajia, ei tilaustasoa. Ei julkista copya."
        ),
    ),
}

_MIN_REASON = 40


def _phrases() -> list[str]:
    """Erottelevat tyokalunimet rekisterista.

    Yksisanaiset otsikot ('Value', 'Table', 'Stats') osuisivat tuhansiin
    riveihin joilla ei ole mitaan tekemista tierin kanssa, joten skannaus
    nojaa monisanaisiin nimiin. 'watchlist' on mukana erikseen: se oli
    toinen 18.9 vaarin luokitelluista.
    """
    reader = load()
    names = []
    for slug in reader.slugs():
        title = reader.phrase(slug).removeprefix("the ")
        if len(title.split()) > 1:
            names.append(title.lower())
    names.append("watchlist")
    return sorted(set(names))


def _tier_lines(text: str, phrases: list[str]) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if TIER_WORDS.search(low) and any(p in low for p in phrases):
            hits.append((i, line.strip()))
    return hits


def _surfaces() -> dict[str, str]:
    out = {}
    for pattern in SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            out[path.relative_to(ROOT).as_posix()] = path.read_text(
                encoding="utf-8", errors="replace"
            )
    return out


def _undisciplined(surfaces: dict[str, str], allowed: dict[str, Poikkeus]) -> list[str]:
    phrases = _phrases()
    bad = []
    for rel, text in surfaces.items():
        if rel == READER_FILE:
            continue
        hits = _tier_lines(text, phrases)
        if not hits:
            continue
        if READER_IMPORT.search(text):
            continue
        if rel in allowed:
            continue
        rivit = ", ".join(str(i) for i, _ in hits)
        bad.append(f"{rel}:{rivit}")
    return bad


# --------------------------------------------------------------------------
# Portit
# --------------------------------------------------------------------------


def test_skanneri_loytaa_edes_jotain() -> None:
    """Kontrolli tyhjaa vastaan: jos hakusanat tai polut rikkoutuvat, koko
    portti menisi lapi hiljaa (muisti: kontrolli-lapaisi-tyhjana)."""
    surfaces = _surfaces()
    assert len(surfaces) > 50, surfaces.keys()
    assert _phrases(), "rekisterista ei saatu yhtaan tyokalunimea"
    osumia = sum(len(_tier_lines(t, _phrases())) for t in surfaces.values())
    assert osumia > 0, "skanneri ei loytanyt yhtaan tier-rivia mistaan"


def test_jokainen_tier_vaite_kulkee_lukijan_kautta() -> None:
    bad = _undisciplined(_surfaces(), ALLOWED)
    assert not bad, (
        "nama pinnat nimeavat tyokalun tier-yhteydessa ilman src/tool_tiers.py:n "
        "lukijaa eivatka ole poikkeuslistalla perusteluineen: " + "; ".join(bad)
    )


def _reason_problems(allowed: dict[str, Poikkeus]) -> list[str]:
    bad = []
    for rel, p in allowed.items():
        if len(p.reason.strip()) < _MIN_REASON:
            bad.append(f"{rel}: perustelu puuttuu tai on liian lyhyt")
        elif not (ROOT / rel).exists():
            bad.append(f"{rel}: poikkeus osoittaa tiedostoon jota ei ole")
    return bad


def _claim_problems(allowed: dict[str, Poikkeus]) -> list[str]:
    reader = load()
    bad = []
    for rel, p in allowed.items():
        for want, slugs in (("premium", p.premium), ("free", p.free)):
            for slug in slugs:
                got = reader.tier(slug)
                if got != want:
                    bad.append(f"{rel}: vaittaa {slug} {want}, rekisteri sanoo {got}")
    return bad


def test_poikkeuslistalla_on_perustelu() -> None:
    assert _reason_problems(ALLOWED) == []


def test_poikkeuksen_oma_vaite_tarkistetaan_rekisterista() -> None:
    assert _claim_problems(ALLOWED) == []


def test_korjattu_tiedosto_ei_ole_poikkeuslistalla() -> None:
    """18.9 korjattu pinta kaytti lukijaa. Jos joku myohemmin poistaa kutsun
    ja vaientaa portin poikkeuksella, tama kaatuu."""
    assert "scripts/build_fpl_longtail.py" not in ALLOWED
    src = (ROOT / "scripts" / "build_fpl_longtail.py").read_text(encoding="utf-8")
    assert READER_IMPORT.search(src), "kutsupaikka ei enaa importtaa lukijaa"


# --------------------------------------------------------------------------
# Negatiiviset kontrollit: portti kaatuu oikeasta syysta
# --------------------------------------------------------------------------


def test_negatiivinen_kontrolli_uusi_pinta_ilman_lukijaa() -> None:
    keksitty = {
        "scripts/keksitty_sivu.py": (
            'HTML = "<p>Rate my team and your watchlist are part of '
            'GoalIQ Premium.</p>"\n'
        )
    }
    bad = _undisciplined(keksitty, ALLOWED)
    assert bad and "keksitty_sivu" in bad[0], bad


def test_negatiivinen_kontrolli_lukija_vapauttaa_pinnan() -> None:
    keksitty = {
        "scripts/keksitty_sivu.py": (
            "from src.tool_tiers import tier_sentence\n"
            'HTML = "<p>" + tier_sentence(["rate-my-team"]) + "</p>"\n'
            "# rate my team is free\n"
        )
    }
    assert _undisciplined(keksitty, ALLOWED) == []


def test_negatiivinen_kontrolli_pelkka_maininta_ei_vapauta() -> None:
    """Docstringissa oleva sana 'tool_tiers' ei ole lukijan kaytto."""
    keksitty = {
        "scripts/keksitty_sivu.py": (
            '"""Tier tulee src/tool_tiers.py:sta."""\n'
            'HTML = "<p>Rate my team and your watchlist are part of '
            'GoalIQ Premium.</p>"\n'
        )
    }
    bad = _undisciplined(keksitty, ALLOWED)
    assert bad and "keksitty_sivu" in bad[0], bad


def test_negatiivinen_kontrolli_perustelu_puuttuu() -> None:
    bad = _reason_problems({"scripts/build_fpl_page.py": Poikkeus(reason="ok")})
    assert bad and "perustelu" in bad[0], bad


def test_negatiivinen_kontrolli_poikkeus_osoittaa_olemattomaan_tiedostoon() -> None:
    bad = _reason_problems({"scripts/ei_ole.py": Poikkeus(reason="x" * 60)})
    assert bad and "ei ole" in bad[0], bad


def test_negatiivinen_kontrolli_poikkeuksen_vaite_on_vaara() -> None:
    """Perusteltu poikkeus ei ole aukko: jos se vaittaa ilmaisen tyokalun
    premiumiksi, portti kaatuu — tasan 18.9 loydetty vaite."""
    bad = _claim_problems(
        {"scripts/build_fpl_page.py": Poikkeus(reason="x" * 60, premium=("rate-my-team",))}
    )
    assert bad and "rate-my-team" in bad[0], bad
    toinen = _claim_problems(
        {"scripts/build_fpl_page.py": Poikkeus(reason="x" * 60, free=("captain-ranker",))}
    )
    assert toinen and "captain-ranker" in toinen[0], toinen
