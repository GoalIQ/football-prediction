"""Poimii auto-PR:n julkisen tekstin julkaisutarkistajalle (18.10.2026, Villen GO: tarkistaja CI:hin).

Kaksi lähdettä, koska kumpikaan ei yksin riitä:
  1. PR-rungon "Julkinen teksti" -osio (agentti listaa siihen jokaisen uuden tai muuttuneen merkkijonon).
  2. Diffin lisätyt rivit käyttäjälle näkyvissä tiedostoissa. Agentti voi unohtaa merkkijonon osiosta;
     diff ei unohda.

Jos osio sanoo "ei muutoksia" eikä diffistä löydy käyttäjälle näkyvää tekstiä, Claudea ei ajeta lainkaan
(tarvitaan=false). Kiintiö kuluu vain silloin, kun tarkistettavaa on.

Käyttö: python julkinen_teksti.py --base origin/main --head <sha> --runko body.md --out /tmp/jt
Kirjoittaa /tmp/jt/syote.md ja tulostaa "tarvitaan=true|false" (GITHUB_OUTPUTiin työnkulussa).
"""
from __future__ import annotations

import argparse
import fnmatch
import html
import re
import subprocess
import sys
from pathlib import Path

NAKYVAT = (
    "*.html", "fpl/*", "predictions/*", "llms.txt",
    "web/pro-spa/src/*.svelte", "web/pro-spa/src/*.ts", "web/pro-spa/static/*",
    "scripts/build_*.py", "src/*.py", "api/*.py",
)
EI_NAKYVAT = ("*.test.ts", "*.spec.ts", "tests/*", "*.gate.test.ts")
MUUT_OSIOT = ("free vai premium", "julkaisu", "mitä ei tehty", "mita ei tehty", "riskit", "miten todennettu",
              "mitä", "miksi")
MAX_RIVEJA = 300
SANA = re.compile(r"[A-Za-zÀ-ÿ']{2,}")
MERKKIJONO = re.compile(r"""(["'`])((?:(?!\1).){12,})\1""")
TAGI = re.compile(r"<[^>]+>")


def osio(runko: str) -> str:
    rivit = runko.splitlines()
    alku = None
    for i, r in enumerate(rivit):
        if "julkinen teksti" in r.lower():
            alku = i
            break
    if alku is None:
        return ""
    # Otsikkorivillä voi olla sisältöä kaksoispisteen jälkeen ("Julkinen teksti: ei muutoksia").
    ensimmainen = rivit[alku].split(":", 1)[1].strip().strip("*_ ") if ":" in rivit[alku] else ""
    out = [ensimmainen] if ensimmainen else []
    for r in rivit[alku + 1:]:
        if _seuraava_osio(r):
            break
        out.append(r)
    return "\n".join(out).strip()


def _seuraava_osio(rivi: str) -> bool:
    """Otsikkorivi ("## Riskit", "**Julkaisu**", "Free vai Premium (ehdotus):"), ei listarivi."""
    s = rivi.strip()
    if not s or s.startswith(("- ", "* ", "> ")):
        return False
    p = s.lstrip("#").strip().strip("*_").strip().split(":", 1)[0].strip().strip("*_").lower()
    return any(p == o or (p.startswith(o + " (") and len(p) < 60) for o in MUUT_OSIOT)


def ei_muutoksia(teksti: str) -> bool:
    t = " ".join(teksti.lower().split()).strip(" .-*")
    return len(t) < 60 and ("ei muutoksia" in t or t in ("ei", "ei ole", "-", "none", "no changes"))


def nakyva(polku: str) -> bool:
    return any(fnmatch.fnmatchcase(polku, k) for k in NAKYVAT) and \
        not any(fnmatch.fnmatchcase(polku, k) for k in EI_NAKYVAT)


def poimi_rivi(polku: str, rivi: str) -> list[str]:
    s = rivi.strip()
    if not s or s.startswith(("//", "#", "*", "/*", "import ", "from ")):
        return []
    if polku.endswith((".html", ".svelte")) or polku.startswith(("fpl/", "predictions/")):
        teksti = " ".join(html.unescape(TAGI.sub(" ", s)).split())
        osat = [teksti] if len(SANA.findall(teksti)) >= 3 else []
        # HTML:n lainausmerkit ovat attribuutteja; vain Sveltessä merkkijono voi olla tekstiä.
        if polku.endswith(".svelte"):
            osat += [m.group(2) for m in MERKKIJONO.finditer(s) if len(SANA.findall(m.group(2))) >= 3]
        return osat
    if polku == "llms.txt":
        return [s] if len(SANA.findall(s)) >= 3 else []
    return [m.group(2) for m in MERKKIJONO.finditer(s) if len(SANA.findall(m.group(2))) >= 3]


def poimi_diffista(diff: str) -> list[tuple[str, str]]:
    out, nahty, polku = [], set(), None
    for rivi in diff.splitlines():
        if rivi.startswith("+++ "):
            nimi = rivi[4:]
            polku = None if nimi == "/dev/null" else (nimi[2:] if nimi.startswith("b/") else nimi)
            if polku and not nakyva(polku):
                polku = None
        elif rivi.startswith("+") and polku:
            for teksti in poimi_rivi(polku, rivi[1:]):
                if teksti not in nahty:
                    nahty.add(teksti)
                    out.append((polku, teksti))
    return out


def rakenna(runko: str, diff: str) -> tuple[bool, str]:
    o = osio(runko)
    poimitut = poimi_diffista(diff)
    tarvitaan = bool(poimitut) or not (o and ei_muutoksia(o))
    osa = ["## PR-rungon Julkinen teksti -osio", "", o or "(osio puuttuu PR-rungosta)", "",
           "## Diffin lisätyt käyttäjälle näkyvät merkkijonot (koneellinen poiminta)", ""]
    for polku, teksti in poimitut[:MAX_RIVEJA]:
        osa.append(f"- `{polku}`: {teksti}")
    if len(poimitut) > MAX_RIVEJA:
        osa.append(f"- ... ja {len(poimitut) - MAX_RIVEJA} muuta (katkaistu)")
    if not poimitut:
        osa.append("(ei poimittavaa)")
    return tarvitaan, "\n".join(osa) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--runko", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    diff = subprocess.run(["git", "diff", "-U0", "--no-renames", f"{a.base}...{a.head}"], check=True,
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    runko = Path(a.runko).read_text(encoding="utf-8") if Path(a.runko).is_file() else ""
    tarvitaan, syote = rakenna(runko, diff)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "syote.md").write_text(syote, encoding="utf-8")
    print(f"tarvitaan={'true' if tarvitaan else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
