"""Backlogin mittarisilmukka ja rivin valinta (18.10.2026, Villen GO).

Ennen tätä jokaisella backlog-rivillä oli "Mittari: ... · tarkistus <pvm>", mutta mikään ei lukenut
sitä takaisin: tuote muuttui automaattisesti, mutta kukaan ei tiennyt, kehittyikö se. Tämä tiedosto
tekee kolme asiaa deterministisesti, jotta ne eivät ole kielimallin muistin tai laskupään varassa:

  eraantyneet  tehdyt rivit, joiden tarkistuspäivä on mennyt eikä Tulos-riviä ole (aallonharja mittaa)
  tarkista     aallonharjan haara: jokainen erääntynyt mittari sai Tulos-rivin, eikä olemassa olevien
               rivien Pisteet-, Mittari- tai Tulos-rivejä muutettu
  valitse      auto-kehityksen seuraava rivi: lukitut ensin, sitten suurin piste. Piste lasketaan
               komponenteista (rivin "= N" ei ole lähde), ja siihen tulee näyttötermi: jos saman lähteen
               (aallonharja, agentin ehdotus, ylläpitäjä) kaksi viimeistä mitattua tulosta kolmesta
               epäonnistui, -1; jos kaksi onnistui, +1. Näin rivityyppi, joka ei liikuta mittaria, putoaa.
  kooste       onnistumiset lähteittäin aallonharjan raporttiin

Piste = 2 x arvo + kiire + 2 x myynti + uutuus - työ (S 0, M 1, L 2) + näyttö (docs/TUOTEPERIAATTEET.md).
Tulos-rivin muoto rivin alla: "      Tulos <vvvv-kk-pp>: ✅|❌|➖ <yksi rivi>" (➖ = ei mitattavissa, syy).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RIVI_ALKU = re.compile(r"^- \[([ xX])\] (.*)$")
OSIO = re.compile(r"^## ")
PISTEET = re.compile(r"^\s+Pisteet:(.*)$")
MITTARI = re.compile(r"^\s+Mittari:(.*)$")
TULOS = re.compile(r"^\s+Tulos (\d{4}-\d{2}-\d{2}): (✅|❌|➖) (\S.*)$")
TULOS_LOYSA = re.compile(r"^\s+Tulos\b")
TARKISTUS = re.compile(r"tarkistus (\d{4}-\d{2}-\d{2})")
KOMPONENTIT = {
    "arvo": re.compile(r"arvo (\d)/3"),
    "kiire": re.compile(r"kiire (\d)/3"),
    "myynti": re.compile(r"myynti (\d)/3"),
    "uutuus": re.compile(r"uutuus (\d)/2"),
}
TYO = re.compile(r"ty[öo] ([SML])\b")
TYON_HINTA = {"S": 0, "M": 1, "L": 2}
OTSIKON_PITUUS = 120


@dataclass
class Rivi:
    nro: int
    tehty: bool
    otsikko: str
    teksti: list[str] = field(default_factory=list)
    pisteet: str | None = None
    mittari: str | None = None
    tulokset: list[tuple[str, str, str]] = field(default_factory=list)
    tulos_virheet: list[str] = field(default_factory=list)
    kysymys: bool = False

    @property
    def avain(self) -> str:
        return self.otsikko[:OTSIKON_PITUUS]

    @property
    def lukittu(self) -> bool:
        return bool(self.pisteet and "(lukittu)" in self.pisteet)

    @property
    def tarkistus(self) -> str | None:
        m = TARKISTUS.search(self.mittari or "")
        return m.group(1) if m else None

    @property
    def lahde(self) -> str:
        koko = " ".join([self.otsikko] + self.teksti).lower()
        if "(aallonharja" in koko:
            return "aallonharja"
        if "agentin ehdotus" in koko:
            return "agentti"
        if "ylläpitäjä" in koko or "yllapitaja" in koko:
            return "yllapitaja"
        return "muu"

    def komponentit(self) -> dict[str, int | str] | None:
        if not self.pisteet:
            return None
        out: dict[str, int | str] = {}
        for nimi, kuvio in KOMPONENTIT.items():
            m = kuvio.search(self.pisteet)
            if not m:
                return None
            out[nimi] = int(m.group(1))
        m = TYO.search(self.pisteet)
        if not m:
            return None
        out["tyo"] = m.group(1)
        return out


def jasenna(teksti: str) -> list[Rivi]:
    """Lukee rivit otsikosta "## Avoimet" alkaen (myös "## Tehdyt"). Signaalit-lohko ei ole rivejä."""
    rivit: list[Rivi] = []
    nykyinen: Rivi | None = None
    mukana = False
    for nro, raaka in enumerate(teksti.splitlines(), start=1):
        if OSIO.match(raaka):
            mukana = raaka.strip() in ("## Avoimet", "## Tehdyt")
            nykyinen = None
            continue
        if not mukana:
            continue
        m = RIVI_ALKU.match(raaka)
        if m:
            nykyinen = Rivi(nro=nro, tehty=m.group(1) in "xX", otsikko=m.group(2).strip())
            rivit.append(nykyinen)
            continue
        if nykyinen is None or not raaka.strip():
            continue
        if PISTEET.match(raaka):
            nykyinen.pisteet = raaka.strip()
        elif MITTARI.match(raaka):
            nykyinen.mittari = raaka.strip()
        elif TULOS_LOYSA.match(raaka):
            t = TULOS.match(raaka)
            if t:
                nykyinen.tulokset.append((t.group(1), t.group(2), t.group(3).strip()))
            else:
                nykyinen.tulos_virheet.append(raaka.strip())
        else:
            if "⚠️ EHDOTUS/KYSYMYS" in raaka:
                nykyinen.kysymys = True
            nykyinen.teksti.append(raaka.strip())
    return rivit


def eraantyneet(rivit: list[Rivi], pvm: str) -> list[Rivi]:
    return [r for r in rivit if r.tehty and r.tarkistus and r.tarkistus <= pvm and not r.tulokset]


def naytto(rivit: list[Rivi]) -> dict[str, int]:
    """Lähteen kolme viimeisintä mitattua tulosta (➖ ei lasketa): 2+ ❌ -> -1, 2+ ✅ -> +1."""
    mitatut: dict[str, list[tuple[str, str]]] = {}
    for r in rivit:
        for pvm, merkki, _ in r.tulokset:
            if merkki in ("✅", "❌"):
                mitatut.setdefault(r.lahde, []).append((pvm, merkki))
    out = {}
    for lahde, lista in mitatut.items():
        viimeiset = [m for _, m in sorted(lista)[-3:]]
        if viimeiset.count("❌") >= 2:
            out[lahde] = -1
        elif viimeiset.count("✅") >= 2:
            out[lahde] = 1
        else:
            out[lahde] = 0
    return out


def piste(r: Rivi, naytot: dict[str, int]) -> tuple[int, str] | None:
    k = r.komponentit()
    if k is None:
        return None
    n = naytot.get(r.lahde, 0)
    arvo = 2 * k["arvo"] + k["kiire"] + 2 * k["myynti"] + k["uutuus"] - TYON_HINTA[k["tyo"]] + n
    erittely = (f"2x{k['arvo']} + {k['kiire']} + 2x{k['myynti']} + {k['uutuus']} - {TYON_HINTA[k['tyo']]}"
                f" + näyttö {n:+d} ({r.lahde}) = {arvo}")
    return arvo, erittely


def valitse(rivit: list[Rivi], varatut: list[str], karki: bool) -> dict:
    naytot = naytto(rivit)
    varatut_avaimet = {v.strip()[:OTSIKON_PITUUS] for v in varatut if v.strip()}
    avoimet = [r for r in rivit if not r.tehty]
    ehdokkaat = []
    for r in avoimet:
        if r.avain in varatut_avaimet or r.kysymys:
            continue
        p = piste(r, naytot)
        if p is None:
            continue
        ehdokkaat.append((r, p[0], p[1]))
    lukitut = [e for e in ehdokkaat if e[0].lukittu]
    # Lukitut ylläpitäjän järjestyksessä (listan järjestys), muut pisteen mukaan.
    jarjestys = sorted(ehdokkaat, key=lambda e: (0, e[0].nro, 0) if e[0].lukittu else (1, -e[1], e[0].nro))
    if lukitut:
        valittu, syy = lukitut[0], "lukittu rivi listan järjestyksessä"
    elif karki:
        uudet = [e for e in jarjestys if (e[0].komponentit() or {}).get("uutuus") == 2]
        valittu = uudet[0] if uudet else None
        syy = "kärkivuoro: suurin piste, uutuus 2/2" if uudet else "kärkivuoro: ei uutuus 2 -riviä, ideoi"
    elif jarjestys:
        valittu, syy = jarjestys[0], "suurin piste"
    else:
        valittu, syy = None, "ei valittavia rivejä"

    def kuvaa(e):
        return {"otsikko": e[0].otsikko[:200], "rivi_nro": e[0].nro, "piste": e[1], "erittely": e[2],
                "lukittu": e[0].lukittu}

    return {
        "valittu": kuvaa(valittu) if valittu else None,
        "syy": syy,
        "avoimia": len(avoimet),
        "ehdokkaita": len(ehdokkaat),
        "naytto": naytot,
        "top": [kuvaa(e) for e in jarjestys[:5]],
    }


def tarkista(pohja: list[Rivi], uusi: list[Rivi], pvm: str) -> list[str]:
    virheet = []
    uudet = {r.avain: r for r in uusi}
    for r in uusi:
        for v in r.tulos_virheet:
            virheet.append(f"Tulos-rivi väärässä muodossa ({r.avain[:60]}): {v[:120]}")
    for r in eraantyneet(pohja, pvm):
        u = uudet.get(r.avain)
        if u is None:
            virheet.append(f"erääntynyt rivi katosi: {r.avain[:80]}")
        elif not u.tulokset:
            virheet.append(f"erääntynyt mittari jäi ilman Tulos-riviä: {r.avain[:80]}")
    for r in pohja:
        u = uudet.get(r.avain)
        if u is None:
            continue
        if u.pisteet != r.pisteet or u.mittari != r.mittari:
            virheet.append(f"olemassa olevan rivin Pisteet tai Mittari muuttui: {r.avain[:80]}")
        if u.tulokset[:len(r.tulokset)] != r.tulokset:
            virheet.append(f"olemassa oleva Tulos-rivi muuttui tai poistui: {r.avain[:80]}")
    return virheet


def kooste(rivit: list[Rivi]) -> dict:
    lahteittain: dict[str, dict[str, int]] = {}
    viimeiset = []
    for r in rivit:
        for pvm, merkki, teksti in r.tulokset:
            d = lahteittain.setdefault(r.lahde, {"✅": 0, "❌": 0, "➖": 0})
            d[merkki] += 1
            viimeiset.append((pvm, merkki, r.avain[:80], teksti[:160]))
    viimeiset.sort()
    return {
        "lahteittain": lahteittain,
        "naytto": naytto(rivit),
        "viimeiset": [{"pvm": p, "tulos": m, "rivi": a, "teksti": t} for p, m, a, t in viimeiset[-10:]],
        "avoimia": sum(1 for r in rivit if not r.tehty),
        "tehtyja": sum(1 for r in rivit if r.tehty),
    }


def _kuvaa_eraantynyt(r: Rivi) -> dict:
    return {"otsikko": r.otsikko[:200], "rivi_nro": r.nro, "mittari": r.mittari, "tarkistus": r.tarkistus,
            "lahde": r.lahde}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="komento", required=True)
    for nimi in ("eraantyneet", "valitse", "kooste"):
        s = sub.add_parser(nimi)
        s.add_argument("--backlog", default="docs/AUTO-BACKLOG.md")
        s.add_argument("--pvm", default=_dt.date.today().isoformat())
        s.add_argument("--out")
        if nimi == "valitse":
            s.add_argument("--varatut-tiedosto")
            s.add_argument("--karki", default="false")
    t = sub.add_parser("tarkista")
    t.add_argument("--pohja", required=True)
    t.add_argument("--uusi", required=True)
    t.add_argument("--pvm", default=_dt.date.today().isoformat())
    a = ap.parse_args(argv)

    if a.komento == "tarkista":
        pohja = jasenna(Path(a.pohja).read_text(encoding="utf-8"))
        uusi = jasenna(Path(a.uusi).read_text(encoding="utf-8"))
        virheet = tarkista(pohja, uusi, a.pvm)
        if virheet:
            print(f"MITTARIPORTTI HYLKÄSI ({len(virheet)}):")
            for v in virheet:
                print(f"  - {v}")
            return 1
        print(f"Mittariportti läpi: {len(eraantyneet(pohja, a.pvm))} erääntynyttä mittaria sai tuloksen.")
        return 0

    rivit = jasenna(Path(a.backlog).read_text(encoding="utf-8"))
    if a.komento == "eraantyneet":
        tulos = [_kuvaa_eraantynyt(r) for r in eraantyneet(rivit, a.pvm)]
    elif a.komento == "valitse":
        varatut = []
        if a.varatut_tiedosto and Path(a.varatut_tiedosto).is_file():
            varatut = Path(a.varatut_tiedosto).read_text(encoding="utf-8").splitlines()
        tulos = valitse(rivit, varatut, a.karki == "true")
    else:
        tulos = kooste(rivit)
    teksti = json.dumps(tulos, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(teksti + "\n", encoding="utf-8")
    print(teksti)
    return 0


if __name__ == "__main__":
    sys.exit(main())
