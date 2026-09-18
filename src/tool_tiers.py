"""YKSI LUKIJA tyokalujen vapaa/premium-rajalle — ja valmis lause siita.

MITATTU VIKA (18.9.2026, GW5-sahkopostin julkaisutarkistaja tarkistusreittia
kavellessa). `scripts/build_fpl_longtail.py` paistoi sivulle
`goaliq.app/fpl/expected-points` lauseen joka niputti nelja tyokalua
premiumiksi. Neljasta nimetysta tyokalusta KAKSI oli vaarin: `rate-my-team`
ja `watchlist` ovat rekisterissa `tier: 'free'`. Vika on konversion kannalta
vaarinpain — se kertoi ilmaiskayttajalle ettei han paase parhaaseen
ilmaiseen tyokaluumme, tasan sille lukijalle jonka pitaisi konvertoitua.
(Lauseen sanatarkka muoto on portin fikstuurissa
`tests/test_tool_tier_reader_discipline.py`, ei tassa: kierroksesta 2 alkaen
myos taman tiedoston tier-vaitteet kulkevat saman portin lapi, eika
tiedostolla ole enaa tiedostotasoista vapautusta.)

Juurisyy EI ollut tier-muutos jota proosa ei seurannut. `git log -S` naytti
lauseen olleen repon juuricommitissa (0499c2709) ja ettei sita ole koskaan
muokattu; `tools.ts` syntyi vasta 4.9 (33d732944). Lause ei siis
vanhentunut — se ei ole koskaan ollut tosi tassa repossa. Siksi mikaan
tier-MUUTOSTA vahtiva mekanismi ei olisi sita loytanyt. Lahin ohitus oli
29f75134b (4.9 copy-sync), joka kaveli kasin tasan yhdeksan pintaa;
`build_fpl_longtail.py` ei ollut listalla, koska pintalista oli
muistinvarainen eika johdettu.

SAANTO 6a KOHTA 1. Kutsupaikka ei saa nahda raakaa tier-kenttaa eika
kirjoittaa tier-sanaa itse: se antaa tyokalujen slugit ja saa valmiin
lauseen. Vaara luokitus ei silloin ole vain kielletty vaan mahdoton —
tuntematon slug kaataa ajon (`UnknownTool`) ja vaaraan luokkaan pyydetty
lause kaataa ajon (`WrongTier`). Kumpikaan ei tulosta tyhjaa.

KAKSI LUKUA, EI KAHTA TOTUUTTA. Tier tulee `web/pro-spa/src/lib/tools.ts`:sta
ja katot lahteistaan (`web/pro-spa/src/lib/prefs.ts`, `api/premium.py`).
Kaikki parsitaan lahteesta; generoitua `data/tool_tiers.json`ia EI tehty,
koska se olisi toinen totuus ja vaatisi oman vahdin.
`tests/test_spa_tool_registry.py` (4.9) parsii samaa rekisteria samalla
tavalla.

MIKAAN LUKU EI SAA PUUTTUA HILJAA (18.9, kierros 2 — adversariaalisen
kumoajan mittaamat nelja fail-open-reittia):
  * `_array_body` ankkuroi nimen rivin alkuun ja kaatuu jos osumia on muu
    kuin yksi. Prefiksihaku osui aiemmin mihin tahansa `TOOLS`-alkuiseen
    exportiin (mitattu: `TOOLSET_META` -> lukija luki hiljaa vaaran
    taulukon).
  * JS-kommentit poistetaan ENNEN kenttahakua, ja kaksi osumaa samaan
    kenttaan kaataa ajon. Aiemmin kommenttirivi jossa luki vanha tier
    oikean kentan ylapuolella luettiin arvoksi — ja juuri noin
    tier-muutos editoidaan.
  * Lauseen proosa (`phrase`) ja ilmaisen tason katto (`caveat`) tulevat
    `_COPY`-taulusta. Slugi jolla ei ole merkintaa KAATAA ajon
    (`MissingCopy`); se ei saa oletusmuotoa. Oletus tuotti aiemmin
    julkaisukelvotonta englantia 15/23 slugista, eli lupasi toimivan
    muodon jota ei ollut.
  * Katto luetaan lahteesta ja PUUTTUVA VAKIO ON VIRHE (`MissingCap`).
    Aiemmin `caveat()` palautti hiljaa Nonen jos `prefs.ts` siirtyi tai
    vakiot nimettiin uudelleen, ja lause olisi muuttunut yhta
    harhaanjohtavaksi kuin se jota se korjasi.

MIKSI KATTO ON LAUSEESSA. Pelkka `tier: 'free'` ei riita watchlistille,
koska ilmaisella on kolmen pelaajan katto. Sanamuoto on kopioitu pinnalta
joka jo sanoo taman oikein (`llms.txt`: "a watchlist ...; three free, up to
50 on Premium"). Uutta myyntilupausta ei keksitty.

MITA LUKIJA EI TIEDA. Tier asuu tassa repossa kuudessa paikassa. Tama
lukija kattaa kolme (SPA-rekisteri + watchlistin katto + Value-listan
rivikatto). Endpointtien osittainen maskaus
(`tests/test_premium_enforcement.py` PARTIAL: /api/fantasy/rate-team maskaa
`suggestions`), mobiilin oma `TOOL_PREMIUM` ja globaali ilmaisikkuna
(`FREE_PREMIUM_UNTIL_DEFAULT`) ovat taman ulkopuolella. Siksi lauseet eivat
lupaa mita tyokalu TEKEE, vain mihin luokkaan se kuuluu — ja se mita ne
jattavat lupaamatta on kirjattu `_COPY`-taulun `NoCap`-perusteluihin eika
jatetty muistin varaan.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "web" / "pro-spa" / "src" / "lib" / "tools.ts"
PREFS_PATH = ROOT / "web" / "pro-spa" / "src" / "lib" / "prefs.ts"
PREMIUM_API_PATH = ROOT / "api" / "premium.py"

FREE = "free"
PREMIUM = "premium"

# Kattojen lahteet nimineen. Nimi on se jolla `Cap` viittaa lahteeseen, ja
# se nakyy virheilmoituksessa kun vakio puuttuu.
SOURCE_PATHS = {
    "registry": REGISTRY_PATH,
    "prefs": PREFS_PATH,
    "premium_api": PREMIUM_API_PATH,
}


class ToolTierError(Exception):
    """Lukijan virheet — kaikki nakyvia, mikaan ei palauta tyhjaa."""


class UnknownTool(ToolTierError):
    """Slug ei ole rekisterissa (esim. tyokalu poistettiin)."""


class WrongTier(ToolTierError):
    """Lausetta pyydettiin luokkaan johon tyokalu ei kuulu."""


class MissingCopy(ToolTierError):
    """Slugilla ei ole `_COPY`-merkintaa: proosaa ei arvata."""


class MissingCap(ToolTierError):
    """Katon lahdeluku puuttuu. Lause olisi harhaanjohtava ilman sita."""


# --------------------------------------------------------------------------
# Kattopolitiikka: joko luettu luku tai KIRJATTU paatos olla ilman
# --------------------------------------------------------------------------


class Cap:
    """Ilmaisen tason raja joka luetaan lahteesta.

    `consts` haetaan `source`-tiedostosta. Puuttuva vakio nostaa
    `MissingCap`in: hiljainen None tekisi lauseesta yhta harhaanjohtavan
    kuin se lause joka 18.9 korjattiin.
    """

    def __init__(self, source: str, consts: Sequence[str],
                 render: Callable[..., str]) -> None:
        if source not in SOURCE_PATHS:
            raise ToolTierError("tuntematon kattolahde: " + source)
        self.source = source
        self.consts = tuple(consts)
        self.render = render


class NoCap:
    """Kirjattu paatos: talla tyokalulla ei ole lauseessa kattoa.

    Tama ei ole sama asia kuin "unohtui". Perustelu on pakollinen ja se on
    proosaa, jotta myohempi lukija nakee mita lause EI lupaa.
    """

    MIN_REASON = 40

    def __init__(self, reason: str) -> None:
        if len(reason.strip()) < self.MIN_REASON:
            raise ToolTierError("NoCap ilman perustelua: " + repr(reason))
        self.reason = reason


class ToolCopy:
    """Yhden tyokalun proosa. `phrase` on COPYA, ei tieria."""

    def __init__(self, phrase: str, cap: Cap | NoCap) -> None:
        self.phrase = phrase
        self.cap = cap


_NUM_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def _word(n: int) -> str:
    return _NUM_WORDS.get(n, str(n))


# --------------------------------------------------------------------------
# _COPY — vain ne tyokalut jotka joku lause OIKEASTI nimeaa.
#
# Taulu on tahallaan LYHYT. Oletusmuoto poistettiin (se tuotti
# julkaisukelvotonta englantia), mutta 19 kayttamatonta fraasia ei
# kirjoitettu varastoon: ne olisivat julkista myyntitekstia jota kukaan ei
# ole lukenut eika julkaisutarkistaja nahnyt (saanto 6b). Kun uusi tyokalu
# nimetaan lauseessa, `MissingCopy` kaataa ajon ja kirjoittaja joutuu
# paattamaan SEKA sanamuodon ETTA katon — molemmat jaavat nakyviin diffiin.
# --------------------------------------------------------------------------
_COPY: dict[str, ToolCopy] = {
    "rate-my-team": ToolCopy(
        phrase="rate my team",
        cap=NoCap(
            "Ei kattoa lauseessa. Tyokalu on rekisterissa ilmainen, mutta "
            "/api/fantasy/rate-team maskaa `suggestions`-kentan "
            "(tests/test_premium_enforcement.py PARTIAL). Lause ei lupaa "
            "siirtosuosituksia vaan luokan, joten se pitaa maskauksesta "
            "huolimatta. Kattolauseen lisaaminen olisi UUSI julkinen "
            "myyntilupaus ja kuuluu julkaisutarkistajalle, ei tanne."
        ),
    ),
    "watchlist": ToolCopy(
        phrase="your watchlist",
        cap=Cap(
            source="prefs",
            consts=("WATCHLIST_FREE_LIMIT", "WATCHLIST_MAX"),
            render=lambda low, high: (
                _word(low) + " free, up to " + str(high) + " on Premium"
            ),
        ),
    ),
    "transfer-planner": ToolCopy(
        phrase="the transfer planner",
        cap=NoCap(
            "Maksullinen tyokalu: ilmaista tasoa ei ole, joten ilmaisen "
            "tason kattoa ei ole olemassa. Lause ei lupaa maaria."
        ),
    ),
    "captain-ranker": ToolCopy(
        phrase="the captain ranker",
        cap=NoCap(
            "Maksullinen tyokalu: ilmaista tasoa ei ole, joten ilmaisen "
            "tason kattoa ei ole olemassa. Lause ei lupaa maaria."
        ),
    ),
    "value": ToolCopy(
        phrase="the value ranking",
        cap=Cap(
            source="premium_api",
            consts=("FREE_VALUE_ROWS",),
            render=lambda rows: (
                _word(rows) + " rows free, the full ranking on Premium"
            ),
        ),
    ),
}


# --------------------------------------------------------------------------
# Lahteiden parsinta
# --------------------------------------------------------------------------

_LINE_COMMENT = "//"
_BLOCK_OPEN = "/*"
_BLOCK_CLOSE = "*/"


def strip_js_comments(text: str) -> str:
    """Rivi- ja lohkokommentit pois, merkkijonoja rikkomatta.

    EI regexilla: URL-merkkijono sisaltaa kaksoiskauttaviivan, ja naiivi
    haku sohisi loppurivin — mukaan lukien `title:`- tai `tier:`-kentan jos
    se sattuisi samalle riville.
    """
    out: list[str] = []
    i, n = 0, len(text)
    quote: str | None = None
    quotes = "'\"" + chr(96)
    while i < n:
        ch = text[i]
        if quote is not None:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in quotes:
            quote = ch
            out.append(ch)
            i += 1
            continue
        if text.startswith(_LINE_COMMENT, i):
            j = text.find("\n", i)
            if j == -1:
                break
            out.append("\n")
            i = j + 1
            continue
        if text.startswith(_BLOCK_OPEN, i):
            j = text.find(_BLOCK_CLOSE, i + 2)
            if j == -1:
                break
            out.append(" ")
            i = j + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _array_body(text: str, name: str) -> str:
    """`export const <name> ... = [ ... ]` -sisalto.

    Nimi ankkuroidaan rivin alkuun ja sanarajaan: `text.index(...)` osui
    prefiksina mihin tahansa samalla alkavaan exportiin. Osumia pitaa olla
    tasan yksi — kaksi taulukkoa samalla nimella on epaselva lahde, ei
    asia jonka lukija saa valita puolestasi.

    Sulku haetaan VASTA yhtasuuruusmerkin jalkeen: ensimmainen hakasulku on
    tyypissa, ja siihen tarttuminen palauttaisi tyhjan taulukon — jolloin
    jokainen vaite menisi lapi tyhjana.
    """
    decl = re.compile(r"^export const " + re.escape(name) + r"\b", re.M)
    hits = list(decl.finditer(text))
    if len(hits) != 1:
        raise ToolTierError(
            "export const " + name + ": odotettiin tasan yhta maarittelya, "
            "loytyi " + str(len(hits))
        )
    start = hits[0].start()
    eq = text.index("=", start)
    open_bracket = text.index("[", eq)
    depth = 0
    for i in range(open_bracket, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[open_bracket + 1 : i]
    raise ToolTierError(name + ": sulkeva hakasulku puuttuu")


def _objects(body: str) -> list[str]:
    out: list[str] = []
    depth = 0
    start: int | None = None
    for i, ch in enumerate(body):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                out.append(body[start : i + 1])
                start = None
    return out


def _field(obj: str, key: str) -> str | None:
    """Kentan arvo. Kaksi osumaa kaataa ajon.

    Kommentit on jo poistettu, joten kaksi osumaa tarkoittaa kahta oikeaa
    kenttaa. Aiempi versio palautti ensimmaisen, ja kommentoitu vanha
    tier-rivi oikean kentan ylapuolella luettiin arvoksi.
    """
    found: list[str] = []
    for quote in ("'", '"'):
        pattern = r"\b" + key + r":\s*\n?\s*" + quote + r"(.*?)" + quote
        found.extend(re.findall(pattern, obj, re.S))
    if len(found) > 1:
        raise ToolTierError(
            key + ": " + str(len(found)) + " osumaa samassa objektissa ("
            + ", ".join(repr(f) for f in found)
            + "). Lukija ei valitse puolestasi."
        )
    return found[0] if found else None


def _int_const(text: str, name: str) -> int | None:
    pattern = (
        r"^\s*(?:export\s+const\s+|const\s+)?" + re.escape(name)
        + r"\s*(?::\s*number\s*)?=\s*(\d+)"
    )
    found = re.findall(pattern, text, re.M)
    if len(found) > 1:
        raise ToolTierError(
            name + ": " + str(len(found)) + " maarittelya lahteessa, arvo on epaselva"
        )
    return int(found[0]) if found else None


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


class ToolTiers:
    """Rekisteri luettuna.

    Tekstit annetaan sisaan, jotta vaihetestit voivat ajaa saman koodin
    SYNTEETTISELLA rekisterilla eivat nykyisella (saanto 6a kohta 3).
    """

    def __init__(self, registry_text: str, prefs_text: str = "",
                 premium_api_text: str = "") -> None:
        self._tiers: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        clean = strip_js_comments(registry_text)
        for obj in _objects(_array_body(clean, "TOOLS")):
            slug = _field(obj, "slug")
            tier_value = _field(obj, "tier")
            title = _field(obj, "title")
            if not slug:
                continue
            if tier_value not in (FREE, PREMIUM):
                raise ToolTierError(slug + ": tuntematon tier " + repr(tier_value))
            if not title:
                raise ToolTierError(slug + ": title puuttuu")
            self._tiers[slug] = tier_value
            self._titles[slug] = title
        if not self._tiers:
            raise ToolTierError("TOOLS-rekisteri on tyhja")
        self._source_text = {
            "registry": registry_text,
            "prefs": prefs_text,
            "premium_api": premium_api_text,
        }

    # -- perusluku ---------------------------------------------------------
    def tier(self, slug: str) -> str:
        try:
            return self._tiers[slug]
        except KeyError:
            raise UnknownTool(
                repr(slug) + " ei ole tyokalurekisterissa (" + REGISTRY_PATH.name
                + "). Jos tyokalu poistettiin, poista se myos lauseesta."
            ) from None

    def slugs(self) -> tuple[str, ...]:
        return tuple(self._tiers)

    def title(self, slug: str) -> str:
        self.tier(slug)
        return self._titles[slug]

    def titles(self) -> dict[str, str]:
        """Rekisterin omat nimet. Portin skanneri nojaa NAIHIN eika
        `phrase()`iin: nimi on rekisterin fakta, proosa on copya, ja
        `phrase()` kaatuu tahallaan slugeille joita mikaan lause ei viela
        nimea."""
        return dict(self._titles)

    def free_tools(self) -> tuple[str, ...]:
        return tuple(s for s, t in self._tiers.items() if t == FREE)

    def premium_tools(self) -> tuple[str, ...]:
        return tuple(s for s, t in self._tiers.items() if t == PREMIUM)

    # -- proosa ------------------------------------------------------------
    def _copy(self, slug: str) -> ToolCopy:
        self.tier(slug)  # tuntematon slug kaatuu tassa, ei hiljene
        try:
            return _COPY[slug]
        except KeyError:
            raise MissingCopy(
                repr(slug) + ": tyokalulla ei ole proosamerkintaa "
                "src/tool_tiers.py:n _COPY-taulussa. Lisaa sanamuoto JA "
                "kattopaatos (Cap tai perusteltu NoCap) ennen kuin lause "
                "nimeaa sen. Oletusmuotoa ei ole: se tuotti aiemmin "
                "julkaisukelvotonta englantia."
            ) from None

    def phrase(self, slug: str) -> str:
        return self._copy(slug).phrase

    def caveat(self, slug: str) -> str | None:
        """Ilmaisen tason raja silloin kun pelkka `free` olisi harhaanjohtava.

        Ei enaa kovakoodattua yhden slugin ehtolausetta: paatos luetaan
        `_COPY`-taulusta ja luku sen lahteesta. Puuttuva lahdeluku on
        `MissingCap`, ei None.
        """
        cap = self._copy(slug).cap
        if isinstance(cap, NoCap):
            return None
        text = self._source_text.get(cap.source, "")
        values = []
        for name in cap.consts:
            value = _int_const(text, name)
            if value is None:
                raise MissingCap(
                    slug + ": katon vakio " + name + " puuttuu lahteesta "
                    + str(SOURCE_PATHS[cap.source]) + ". Ilman sita lause "
                    "sanoisi vain 'free' ja olisi harhaanjohtava. Jos raja "
                    "poistui, vaihda merkinta NoCapiksi perusteluineen."
                )
            values.append(value)
        return cap.render(*values)

    def _check(self, slugs: list[str], want: str) -> None:
        wrong = [s for s in slugs if self.tier(s) != want]
        if wrong:
            other = FREE if want == PREMIUM else PREMIUM
            raise WrongTier(
                ", ".join(wrong) + ": rekisteri sanoo " + other
                + ", lause sanoisi " + want
                + ". Kayta tier_sentence():a joka jakaa listan itse."
            )

    def _names(self, slugs: list[str]) -> str:
        parts = []
        for s in slugs:
            text = self.phrase(s)
            cav = self.caveat(s)
            parts.append(text + " (" + cav + ")" if cav else text)
        return _join(parts)

    def free_sentence(self, slugs, *, also: bool = False) -> str:
        """Lause joka nimeaa VAIN ilmaiset tyokalut ilmaisiksi.

        `also=True` kun edeltava virke on jo sanonut "free and needs no
        account" (sivun oma ranking) — silloin toisto olisi kompurointia.
        """
        slugs = list(slugs)
        if not slugs:
            return ""
        self._check(slugs, FREE)
        names = self._names(slugs)
        one = len(slugs) == 1
        verb = "is" if one else "are"
        if also:
            tail = "free as well"
        else:
            tail = "free and needs no account" if one else "free and need no account"
        return names[0].upper() + names[1:] + " " + verb + " " + tail + "."

    def premium_sentence(self, slugs) -> str:
        """Lause joka nimeaa VAIN maksulliset tyokalut maksullisiksi."""
        slugs = list(slugs)
        if not slugs:
            return ""
        self._check(slugs, PREMIUM)
        names = self._names(slugs)
        verb = "is" if len(slugs) == 1 else "are"
        return names[0].upper() + names[1:] + " " + verb + " part of GoalIQ Premium."

    def tier_sentence(self, slugs, *, free_already_said: bool = False) -> str:
        """Sekalainen lista jaettuna oikeisiin luokkiin — ei niputusta.

        Tama on se kutsu jonka sivunrakentaja tekee: se ei tieda kumpaan
        luokkaan mikaan tyokalu kuuluu eika voi arvata vaarin.
        """
        slugs = list(slugs)
        free = [s for s in slugs if self.tier(s) == FREE]
        premium = [s for s in slugs if self.tier(s) == PREMIUM]
        out = [
            self.free_sentence(free, also=free_already_said),
            self.premium_sentence(premium),
        ]
        return " ".join(p for p in out if p)


_CACHE: ToolTiers | None = None


def load(
    registry_path: Path | None = None,
    prefs_path: Path | None = None,
    premium_api_path: Path | None = None,
) -> ToolTiers:
    global _CACHE
    given = (registry_path, prefs_path, premium_api_path)
    if all(p is None for p in given) and _CACHE is not None:
        return _CACHE
    reg = registry_path or REGISTRY_PATH
    pre = prefs_path or PREFS_PATH
    prem = premium_api_path or PREMIUM_API_PATH
    if not reg.exists():
        raise ToolTierError("tyokalurekisteria ei ole: " + str(reg))
    tiers = ToolTiers(
        reg.read_text(encoding="utf-8"),
        pre.read_text(encoding="utf-8") if pre.exists() else "",
        prem.read_text(encoding="utf-8") if prem.exists() else "",
    )
    if all(p is None for p in given):
        _CACHE = tiers
    return tiers


def tier(slug: str) -> str:
    return load().tier(slug)


def free_tools() -> tuple[str, ...]:
    return load().free_tools()


def premium_tools() -> tuple[str, ...]:
    return load().premium_tools()


def free_sentence(slugs, *, also: bool = False) -> str:
    return load().free_sentence(slugs, also=also)


def premium_sentence(slugs) -> str:
    return load().premium_sentence(slugs)


def tier_sentence(slugs, *, free_already_said: bool = False) -> str:
    return load().tier_sentence(slugs, free_already_said=free_already_said)
