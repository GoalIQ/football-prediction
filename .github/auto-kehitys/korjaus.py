"""Korjauskierros: julkaisutarkistuksen blokkaama auto-PR palaa agentille (19.10.2026, ylläpitäjän päätös).

Ennen tätä BLOKATTU-verdikti jäi odottamaan ihmistä. Koska avoimia auto-PR:iä saa olla enintään kaksi, kaksi
blokattua PR:ää pysäytti koko kehityksen (19.10: recap-PR blokattiin mekaanisista syistä, kuten kolme desimaalia
muistiossa ja kaksi sivulla). Nyt auto-kehityksen ajo korjaa ensin vanhimman blokatun PR:n samalla haaralla ja
tekee uuden rivin vasta, kun korjattavaa ei ole. Kierroksia on enintään KIERROKSIA; sen jälkeen PR saa labelin
TARVITSEE_IHMISEN, eikä sitä enää korjata automaattisesti.

Luottamusraja (repo on julkinen, kuka tahansa voi kommentoida): agentti saa vain
  * CI-julkaisutarkistajan oman verdiktin (kirjoittaja github-actions, alkaa "Julkaisutarkistus (CI"), ja
  * ylläpitäjän kommentit (kirjautumisnimi YLLAPITAJAN_LOGINIT tai authorAssociation OWNER/MEMBER, ei botti).
Muiden kommentit eivät päädy agentille lainkaan.

Miksi kirjautumisnimi (21.10.2026): ylläpitäjän jäsenyys orgissa on yksityinen, eikä CI:n GITHUB_TOKEN näe
sitä, joten authorAssociation ei ollut OWNER/MEMBER. PR #6:n molemmat korjauskierrokset saivat 0 ylläpitäjän
kommenttia, vaikka niitä oli kolme, ja agentti toimi pelkän verdiktin varassa. Kirjautumisnimi on yksilöllinen
eikä riipu näkyvyydestä.

  valitse  avoimet PR:t (gh pr list --json number,headRefName,labels) -> korjattava ja merkittävät
  ohjeet   PR:n kommentit ja runko (gh pr view --json comments,body) -> /tmp/korjaus/*.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BLOKATTU = "julkaisutarkistus-blokattu"
TARVITSEE_IHMISEN = "tarvitsee-ihmisen"
VETO = "ei-automaattikorjausta"
KIERROKSIA = 2
KORJATTU = re.compile(r"^korjattu-(\d+)$")
HAARA = re.compile(r"^auto/[a-z0-9][a-z0-9._-]{0,80}$")  # sama kuin auto-kehitys.yml:n julkaisussa
VERDIKTIN_KIRJOITTAJA = "github-actions"
VERDIKTIN_ALKU = "Julkaisutarkistus (CI"
KORJAUKSEN_ALKU = "Korjauskierros "  # auto-kehitys.yml julkaise kirjoittaa tämän pushin jälkeen
EI_VERDIKTIA = 3
YLLAPITAJA = {"OWNER", "MEMBER"}
YLLAPITAJAN_LOGINIT = {"Veikkoville"}
YLLAPITAJAN_KOMMENTTEJA = 5
KOMMENTIN_PITUUS = 3000


def _labelit(pr: dict) -> set[str]:
    return {(l.get("name") if isinstance(l, dict) else str(l)) for l in pr.get("labels") or []}


def tehdyt_kierrokset(labelit: set[str]) -> int:
    return max((int(m.group(1)) for m in (KORJATTU.match(l) for l in labelit) if m), default=0)


def valitse(prt: list[dict]) -> dict:
    """Vanhin blokattu auto-PR, jolla on kierroksia jäljellä. Loppuun korjatut merkitään ihmiselle."""
    korjattava, merkitse = None, []
    for pr in sorted(prt, key=lambda p: int(p["number"])):
        # Vain tämän repon omat auto/-haarat: forkin PR voi nimetä haaransa samoin.
        if pr.get("isCrossRepository") is not False or not HAARA.match(str(pr.get("headRefName", ""))):
            continue
        labelit = _labelit(pr)
        if BLOKATTU not in labelit or TARVITSEE_IHMISEN in labelit or VETO in labelit:
            continue
        tehty = tehdyt_kierrokset(labelit)
        if tehty >= KIERROKSIA:
            merkitse.append(int(pr["number"]))
        elif korjattava is None:
            korjattava = {"pr": int(pr["number"]), "haara": pr["headRefName"], "kierros": tehty + 1}
    return {"korjattava": korjattava, "merkitse": merkitse}


def _on_botti(kommentti: dict) -> bool:
    login = str((kommentti.get("author") or {}).get("login", ""))
    return login.endswith("[bot]") or login == VERDIKTIN_KIRJOITTAJA


def poimi_ohjeet(doc: dict) -> dict:
    kommentit = sorted(doc.get("comments") or [], key=lambda k: str(k.get("createdAt", "")))
    verdiktit = [k for k in kommentit
                 if str((k.get("author") or {}).get("login", "")) == VERDIKTIN_KIRJOITTAJA
                 and str(k.get("body", "")).startswith(VERDIKTIN_ALKU)]
    pushit = [k for k in kommentit
              if str((k.get("author") or {}).get("login", "")) == VERDIKTIN_KIRJOITTAJA
              and str(k.get("body", "")).startswith(KORJAUKSEN_ALKU)]
    verdikti = verdiktit[-1] if verdiktit else None
    if verdikti and pushit and str(verdikti.get("createdAt", "")) < str(pushit[-1].get("createdAt", "")):
        verdikti = None  # edellinen korjaus on uudempi kuin verdikti: tuoretta verdiktiä ei ole
    yllapitaja = [k for k in kommentit
                  if (str((k.get("author") or {}).get("login", "")) in YLLAPITAJAN_LOGINIT
                      or str(k.get("authorAssociation", "")).upper() in YLLAPITAJA)
                  and not _on_botti(k)]
    return {
        "verdikti": str(verdikti["body"]) if verdikti else None,
        "yllapitaja": [str(k.get("body", ""))[:KOMMENTIN_PITUUS] for k in yllapitaja[-YLLAPITAJAN_KOMMENTTEJA:]],
        "runko": str(doc.get("body") or ""),
    }


def kirjoita_ohjeet(ohjeet: dict, kansio: Path) -> None:
    kansio.mkdir(parents=True, exist_ok=True)
    (kansio / "verdikti.md").write_text(ohjeet["verdikti"] or "", encoding="utf-8")
    yp = "\n\n---\n\n".join(ohjeet["yllapitaja"]) or "(ei ylläpitäjän kommentteja)"
    (kansio / "yllapitaja.md").write_text(yp + "\n", encoding="utf-8")
    (kansio / "pr-body-nyt.md").write_text(ohjeet["runko"], encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="komento", required=True)
    v = sub.add_parser("valitse")
    v.add_argument("--prt", required=True)
    v.add_argument("--out", required=True)
    o = sub.add_parser("ohjeet")
    o.add_argument("--kommentit", required=True)
    o.add_argument("--kansio", required=True)
    a = ap.parse_args(argv)
    if a.komento == "valitse":
        tulos = valitse(json.loads(Path(a.prt).read_text(encoding="utf-8")))
        Path(a.out).write_text(json.dumps(tulos, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(tulos, ensure_ascii=False))
        return 0
    ohjeet = poimi_ohjeet(json.loads(Path(a.kommentit).read_text(encoding="utf-8")))
    if not ohjeet["verdikti"]:
        # Blokattu label ilman tuoretta verdiktiä (tarkistus kaatui tai ei ole vielä ajettu korjauksen jälkeen):
        # korjattavaa ei ole. Työnkulku tekee silloin uuden rivin, jos se on sallittu.
        print("::notice::Korjattavalla PR:llä ei ole tuoretta julkaisutarkistuksen verdiktiä")
        return EI_VERDIKTIA
    kirjoita_ohjeet(ohjeet, Path(a.kansio))
    print(f"Verdikti {len(ohjeet['verdikti'])} merkkiä, ylläpitäjän kommentteja {len(ohjeet['yllapitaja'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
