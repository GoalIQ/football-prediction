"""YKSI LUKIJA tyokalujen vapaa/premium-rajalle — ja valmis lause siita.

MITATTU VIKA (18.9.2026, GW5-sahkopostin julkaisutarkistaja tarkistusreittia
kavellessa). `scripts/build_fpl_longtail.py` paistoi sivulle
`goaliq.app/fpl/expected-points` lauseen:

    "This ranking is free and needs no account. The tools built on top of it,
     rate my team, the transfer planner, the captain ranker and your
     watchlist, are part of GoalIQ Premium."

Neljasta nimetysta tyokalusta KAKSI oli vaarin: `rate-my-team` ja `watchlist`
ovat rekisterissa `tier: 'free'`. Vika on konversion kannalta vaarinpain — se
kertoi ilmaiskayttajalle ettei han paase parhaaseen ilmaiseen tyokaluumme,
tasan sille lukijalle jonka pitaisi konvertoitua.

Juurisyy EI ollut tier-muutos jota proosa ei seurannut. `git log -S` naytti
lauseen olleen repon juuricommitissa (0499c2709) ja ettei sita ole koskaan
muokattu; `tools.ts` syntyi vasta 4.9 (33d732944) ja `rate-my-team`in
`tier: 'free'` kirjoitettiin kerran eika muutettu. Lause ei siis vanhentunut —
se ei ole koskaan ollut tosi tassa repossa. Siksi mikaan tier-MUUTOSTA vahtiva
mekanismi ei olisi sita loytanyt. Lahin ohitus oli 29f75134b (4.9 copy-sync),
joka kaveli kasin tasan yhdeksan pintaa; `build_fpl_longtail.py` ei ollut
listalla, koska pintalista oli muistinvarainen eika johdettu.

SAANTO 6a KOHTA 1. Kutsupaikka ei saa nahda raakaa tier-kenttaa eika kirjoittaa
tier-sanaa itse: se antaa tyokalujen slugit ja saa valmiin lauseen. Vaara
luokitus ei silloin ole vain kielletty vaan mahdoton — tuntematon slug kaataa
ajon (`UnknownTool`) ja vaaraan luokkaan pyydetty lause kaataa ajon
(`WrongTier`). Kumpikaan ei tulosta tyhjaa.

KAKSI LUKUA, EI KAHTA TOTUUTTA. Tier tulee `web/pro-spa/src/lib/tools.ts`:sta
ja watchlistin katto `web/pro-spa/src/lib/prefs.ts`:sta. Molemmat parsitaan
lahteesta; generoitua `data/tool_tiers.json`ia EI tehty, koska se olisi toinen
totuus ja vaatisi oman vahdin. `tests/test_spa_tool_registry.py` (4.9) parsii
samaa rekisteria samalla tavalla.

MIKSI KATTO ON LAUSEESSA. Pelkka `tier: 'free'` ei riita watchlistille: "your
watchlist is free" on yhta harhaanjohtava kuin vanha "watchlist is Premium",
koska ilmaisella on 3 pelaajan katto. Sanamuoto on kopioitu pinnalta joka jo
sanoo taman oikein (`llms.txt`: "a watchlist ...; three free, up to 50 on
Premium"). Uutta myyntilupausta ei keksitty.

MITA LUKIJA EI TIEDA. Tier asuu tassa repossa kuudessa paikassa. Tama lukija
kattaa kaksi (SPA-rekisteri + watchlistin katto). Endpointtien osittainen
maskaus (`tests/test_premium_enforcement.py` PARTIAL: /api/fantasy/rate-team
maskaa `suggestions`), `api/premium.py`:n maaralliset katot, mobiilin oma
`TOOL_PREMIUM` ja globaali ilmaisikkuna (`FREE_PREMIUM_UNTIL_DEFAULT`) ovat
taman ulkopuolella. Siksi lauseet eivat lupaa mita tyokalu TEKEE, vain mihin
luokkaan se kuuluu: "rate my team is free and needs no account" pitaa myos
silloin kun `suggestions` on maskattu, koska lause ei lupaa siirtosuosituksia.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "web" / "pro-spa" / "src" / "lib" / "tools.ts"
PREFS_PATH = ROOT / "web" / "pro-spa" / "src" / "lib" / "prefs.ts"

FREE = "free"
PREMIUM = "premium"


class ToolTierError(Exception):
    """Lukijan virheet — kaikki nakyvia, mikaan ei palauta tyhjaa."""


class UnknownTool(ToolTierError):
    """Slug ei ole rekisterissa (esim. tyokalu poistettiin)."""


class WrongTier(ToolTierError):
    """Lausetta pyydettiin luokkaan johon tyokalu ei kuulu."""


# Proosamuoto lauseessa. Tama on COPYA, ei tieria: tason kertoo aina rekisteri.
# Oletus johdetaan rekisterin otsikosta, joten uusi tyokalu saa toimivan
# muodon ilman etta tanne pitaa muistaa lisata rivia.
_PHRASE_OVERRIDES = {
    "rate-my-team": "rate my team",
    "watchlist": "your watchlist",
}

_NUM_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def _array_body(text: str, name: str) -> str:
    """`export const <name> ... = [ ... ]` -sisalto.

    Sulku haetaan VASTA `=`-merkin jalkeen: ensimmainen `[` on tyypissa
    (`Tool[]`), ja siihen tarttuminen palauttaisi tyhjan taulukon — jolloin
    jokainen vaite menisi lapi tyhjana.
    """
    start = text.index("export const " + name)
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
    raise ToolTierError(name + ": sulkeva ] puuttuu")


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
    for quote in ("'", '"'):
        m = re.search(rf"\b{key}:\s*\n?\s*{quote}(.*?){quote}", obj, re.S)
        if m:
            return m.group(1)
    return None


def _int_const(text: str, name: str) -> int | None:
    m = re.search(rf"\b{name}\s*(?::\s*number\s*)?=\s*(\d+)", text)
    return int(m.group(1)) if m else None


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


class ToolTiers:
    """Rekisteri luettuna.

    Tekstit annetaan sisaan, jotta vaihetestit voivat ajaa saman koodin
    SYNTEETTISELLA rekisterilla eivat nykyisella (saanto 6a kohta 3).
    """

    def __init__(self, registry_text: str, prefs_text: str = "") -> None:
        self._tiers: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        for obj in _objects(_array_body(registry_text, "TOOLS")):
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
        self._free_limit = _int_const(prefs_text, "WATCHLIST_FREE_LIMIT")
        self._max = _int_const(prefs_text, "WATCHLIST_MAX")

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

    def free_tools(self) -> tuple[str, ...]:
        return tuple(s for s, t in self._tiers.items() if t == FREE)

    def premium_tools(self) -> tuple[str, ...]:
        return tuple(s for s, t in self._tiers.items() if t == PREMIUM)

    # -- proosa ------------------------------------------------------------
    def phrase(self, slug: str) -> str:
        self.tier(slug)  # tuntematon slug kaatuu tassa, ei hiljene
        if slug in _PHRASE_OVERRIDES:
            return _PHRASE_OVERRIDES[slug]
        return "the " + self._titles[slug].lower()

    def caveat(self, slug: str) -> str | None:
        """Ilmaisen tason raja silloin kun pelkka `free` olisi harhaanjohtava."""
        if slug != "watchlist":
            return None
        if self._free_limit is None or self._max is None:
            return None
        low = _NUM_WORDS.get(self._free_limit, str(self._free_limit))
        return low + " free, up to " + str(self._max) + " on Premium"

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
        """Lause joka nimeaa VAIN premium-tyokalut premiumiksi."""
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


def load(registry_path: Path | None = None, prefs_path: Path | None = None) -> ToolTiers:
    global _CACHE
    if registry_path is None and prefs_path is None and _CACHE is not None:
        return _CACHE
    reg = registry_path or REGISTRY_PATH
    pre = prefs_path or PREFS_PATH
    if not reg.exists():
        raise ToolTierError("tyokalurekisteria ei ole: " + str(reg))
    tiers = ToolTiers(
        reg.read_text(encoding="utf-8"),
        pre.read_text(encoding="utf-8") if pre.exists() else "",
    )
    if registry_path is None and prefs_path is None:
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
