"""Julkaise uusimmat generoidut kortit sivustolle VAKIONIMILLA + sisaltotiiviste.

🔴 MIKSI VAKIONIMI (4.9.2026). Laskeutumissivulla ei ollut yhtaan kuvaa
tuotteesta: 0 kuvaa ja 2 559 sanaa proosaa, jossa kavijaa pyydetaan
kuvittelemaan tyokalut joita myymme. Kortit ovat olleet olemassa koko ajan,
mutta ne kirjoitetaan `outputs/`-kansioon joka on gitignoressa.

Nimi EI saa sisaltaa kierrosnumeroa. `goaliq_standouts_gw3.png` olisi
naennaisesti toiminut ja vanhentunut hiljaa GW4:ssa - sama vikaluokka kuin
"Live model projections · GW1-6" joka oli kovakoodattu GEN-markerien
ulkopuolelle. Sivu osoittaa vakionimeen, ja tama skripti vaihtaa sen alta.

WebP eika PNG: mitattu 4.9, sama kortti on PNG:na 192 kB ja WebP:na 32 kB.
Laskeutumissivu on pakattuna 26 kB, joten kaksi PNG:ta olisi
kuusinkertaistanut sivun painon.

🔴 22.9.2026 (LANDING-KORTIT-GW3-VANHAT): VAKIONIMI PIILOTTI KIERROKSEN.
Etusivu naytti GW3:n kortteja kun kausi oli GW6:ssa (18 vrk). Kaksi
mekanismivikaa:
  1. Tama docstring sanoi "aja fpl-data-refreshissa", mutta yksikaan
     workflow ei ajanut sita. Nyt ajaa: `scripts/refresh_site_cards.py`.
  2. Tuoreusportti luki tiedoston mtimea. CI:n tuoreessa checkoutissa ika on
     aina 0 vrk, joten portti oli CI:ssa sokea (lokaalisti punainen 17 vrk).

🔴 22.9 JULKAISUPORTTI: KIERROS EI RIITA, SISALTO RATKAISEE. Ensimmainen
korjaus vertasi kortin kierrosta dataan. Portti blokkasi sen: 22 vrk:n
maaotteluvalilla GW6:n kortti olisi ollut "ajan tasalla" koko ajan, vaikka
ilmaissivu `/fpl/expected-points` paivittyy 3 h valein ja kortin prosentit
alkavat erota sivun luvuista (tai kortille jaa loukkaantunut pelaaja).
Nyt `cards.json` kantaa kortin NAKYVAN SISALLON tiivisteen
(`card_shot.content_signature`: nimet + pyoristetyt luvut + otsikot, ilman
aikaleimoja), ja kortti renderoidaan kun nykyisen projektion tiiviste on eri.
Portti (`kortin_tila`) vertaa samaa tiivistetta, joten kortti joka ei vastaa
sivun lukuja kaatuu - myos saman kierroksen sisalla.

Julkaisu kieltaytyy lahteesta jonka tiiviste ei vastaa nykyista projektiota:
vanha PNG `outputs/`issa ei voi enaa paatya sivulle tuoreen nimella.
Myos 450 px -variantit (index.html:n srcset) tehdaan tassa; ne tehtiin 5.9
kasin eivatka paivittyneet kuvan mukana.

Exit 0 myos kun lahdetta ei ole (kauden alussa), jotta tama ei pada
refreshia - vanha kuva jaa silloin voimaan ja portti huutaa siita erikseen.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from scripts.card_shot import content_signature
from src.models.fpl_gameweek import actionable_gameweek  # sama lukija kuin renderoijilla

CARDS_IN = config.PROJECT_ROOT / "outputs" / "cards"
CARDS_OUT = config.PROJECT_ROOT / "assets" / "cards"
MANIFEST = CARDS_OUT / "cards.json"
XP_PATH = config.DATA_DIR / "fpl_xp_projections.json"
LEVEYS = 900
# index.html: srcset="...-450.webp 450w, ....webp 900w"
LEVEYS_PIENI = 450
LAATU = 82

# Kuinka kauan kortti saa olla eri kuin nykyinen projektio SEN JALKEEN kun
# renderointia on yritetty ja se kaatui (cards.json: `stale_since`).
# Perustelu ja vaiheittainen mittaus: tests/test_site_card_images.py
# (ARMONAIKA-lohko).
ARMONAIKA = dt.timedelta(hours=24)

# (lahdekuvio, kohdenimi). Kuvio poimii kierrosnumeron, jotta uusin voittaa.
KORTIT = [
    (re.compile(r"goaliq_standouts_gw(\d+)\.png$"), "gameweek-card.webp"),
    (re.compile(r"goaliq_projected_xi_gw(\d+)\.png$"), "projected-xi-card.webp"),
]
NIMET = [nimi for _, nimi in KORTIT]


def pieni_nimi(nimi: str) -> str:
    return nimi[: -len(".webp")] + f"-{LEVEYS_PIENI}.webp"


def uusin(kuvio: re.Pattern) -> Path | None:
    """Suurin kierrosnumero, ei tiedoston aikaleima.

    Aikaleima muuttuu kun tiedosto kopioidaan tai varmuuskopioidaan, ja
    merkkijonolajittelu laittaisi gw10:n ennen gw9:aa.
    """
    paras, paras_gw = None, -1
    if not CARDS_IN.exists():
        return None
    for f in CARDS_IN.iterdir():
        m = kuvio.search(f.name)
        if not m:
            continue
        gw = int(m.group(1))
        if gw > paras_gw:
            paras, paras_gw = f, gw
    return paras


def _kierros(kuvio: re.Pattern, polku: Path) -> int:
    return int(kuvio.search(polku.name).group(1))


def _utc(s) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def sha256(polku: Path) -> str:
    return hashlib.sha256(polku.read_bytes()).hexdigest()


def lue_meta(path: Path | None = None) -> dict:
    # Polku luetaan KUTSUHETKELLA (ei oletusarvona): oletusarvo jaatyisi
    # import-hetkeen, ja testin/ajon polunvaihto ohittaisi sen hiljaa.
    path = path or XP_PATH
    return (json.loads(path.read_text(encoding="utf-8")).get("meta") or {})


def lue_manifesti(path: Path | None = None) -> dict:
    path = path or MANIFEST
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def kirjoita_manifesti(manifesti: dict) -> None:
    # newline="\n": samat tavut Windowsilla ja runnerilla.
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifesti, indent=1, sort_keys=True)
                        + "\n", encoding="utf-8", newline="\n")


def nykyiset_tiivisteet(now: dt.datetime | None = None) -> dict[str, str | None]:
    """YKSI LUKIJA: mita kukin kortti nayttaisi NYT, tiivisteena.

    HTML tulee samasta funktiosta jolla renderoija kuvaisi kortin
    (`current_card_html`, samat syotetiedostot). None = korttia ei voi
    muodostaa nykyisesta datasta (esim. loki eroaa kortista ennen deadlinea);
    silloin sita ei myoskaan voi renderoida.
    """
    from scripts import render_projected_xi_card, render_standouts_card
    lahteet = {"gameweek-card.webp": render_standouts_card,
               "projected-xi-card.webp": render_projected_xi_card}
    out: dict[str, str | None] = {}
    for nimi in NIMET:
        try:
            out[nimi] = content_signature(lahteet[nimi].current_card_html(now))
        except (Exception, SystemExit) as e:  # noqa: BLE001 - None kertoo sen
            print(f"::warning::{nimi}: korttia ei voi muodostaa nykyisesta "
                  f"datasta: {e!r}")
            out[nimi] = None
    return out


def kortin_tila(entry: dict | None, nykyinen: str | None, meta: dict,
                now: dt.datetime) -> tuple[bool, str]:
    """YKSI LUKIJA: saako taman kortin nayttaa sivulla juuri nyt?

    Kortti on ajan tasalla kun sen tiiviste (cards.json) = tiiviste joka
    lasketaan nykyisesta projektiosta samalla funktiolla jolla kortti
    renderoidaan. Poikkeama sallitaan vain ARMONAIKA sen jalkeen kun
    renderointia on YRITETTY ja se kaatui (`stale_since`, jonka
    refresh_site_cards kirjoittaa). Ilman yritysta poikkeama kaatuu heti:
    se tarkoittaa etta joku muutti dataa tai kortin pohjaa renderoimatta.
    """
    if actionable_gameweek(meta) is None:
        return True, ("datassa ei ole tulevaa kierrosta (kauden tauko), "
                      "ei verrattavaa")
    if not entry or not entry.get("signature"):
        return False, ("kortilla ei ole sisaltotiivistetta assets/cards/cards.json:ssa "
                       "(julkaistu ohi publish_cards_to_site:n?)")
    if nykyinen is not None and entry["signature"] == nykyinen:
        return True, f"kortti GW{entry.get('gw')} vastaa nykyista projektiota"
    alkaen = _utc(entry.get("stale_since"))
    mika = ("nykyisesta datasta ei voi muodostaa korttia" if nykyinen is None
            else f"kortin sisalto ({entry['signature']}) != nykyinen projektio "
                 f"({nykyinen})")
    if alkaen is not None and now <= alkaen + ARMONAIKA:
        h = (now - alkaen).total_seconds() / 3600
        return True, (f"{mika}; renderointi kaatui {h:.1f} h sitten, armonaika "
                      f"{ARMONAIKA.total_seconds() / 3600:.0f} h")
    return False, (mika + (f"; renderointi kaatunut {alkaen:%Y-%m-%d %H:%M} UTC alkaen"
                           if alkaen else "; renderointia ei ole yritetty")
                   + ". Aja `python -m scripts.refresh_site_cards` ja committaa "
                     "kortit samaan pushiin.")


def tarvitsee_renderoinnin(manifesti: dict, nykyiset: dict[str, str | None],
                           meta: dict) -> list[str]:
    """Kortit joiden tiiviste != nykyinen. CI:n liipaisin.

    Ei armonaikaa: armonaika on portin toleranssi kaatuneelle yritykselle,
    ei syy odottaa. Tyhja lista = ei renderointia eika tiedostomuutoksia.
    """
    if actionable_gameweek(meta) is None:
        return []
    return [n for n in NIMET
            if nykyiset.get(n) is None
            or (manifesti.get(n) or {}).get("signature") != nykyiset.get(n)]


def merkitse_vanhaksi(nimet: list[str], now: dt.datetime) -> None:
    """Renderointi kaatui: kirjaa ENSIMMAINEN kaatumishetki (ei ylikirjoiteta
    myohemmilla yrityksilla, joten armonaika ei liu'u eika tiedosto muutu
    joka ajossa)."""
    manifesti = lue_manifesti()
    muuttui = False
    for n in nimet:
        e = manifesti.setdefault(n, {})
        if not e.get("stale_since"):
            e["stale_since"] = now.astimezone(dt.timezone.utc).isoformat(
                timespec="seconds")
            muuttui = True
    if muuttui:
        kirjoita_manifesti(manifesti)


def _tallenna(im, kohde: Path, leveys: int) -> None:
    from PIL import Image
    w, h = im.size
    pieni = im.resize((leveys, round(h * leveys / w)), Image.LANCZOS)
    pieni.convert("RGB").save(kohde, "WEBP", quality=LAATU, method=6)


def julkaise(nykyiset: dict[str, str | None], meta: dict,
             now: dt.datetime) -> int:
    """Kirjoita webp + 450-variantti + cards.json-rivi jokaiselle kortille jonka
    uusimman lahteen (PNG + sen HTML) tiiviste = nykyinen. Palauttaa
    julkaistujen maaran."""
    from PIL import Image
    CARDS_OUT.mkdir(parents=True, exist_ok=True)
    manifesti = lue_manifesti()
    tehty = 0
    for kuvio, nimi in KORTIT:
        lahde = uusin(kuvio)
        if lahde is None:
            print(f"::notice::{nimi}: lahdekorttia ei ole, vanha jaa voimaan.")
            continue
        html = lahde.with_suffix(".html")
        tiiviste = (content_signature(html.read_text(encoding="utf-8"))
                    if html.exists() else None)
        if tiiviste is None or tiiviste != nykyiset.get(nimi):
            print(f"::notice::{nimi}: lahde {lahde.name} ei vastaa nykyista "
                  f"projektiota ({tiiviste} != {nykyiset.get(nimi)}) - ei julkaista.")
            continue
        kohde, pieni = CARDS_OUT / nimi, CARDS_OUT / pieni_nimi(nimi)
        im = Image.open(lahde)
        _tallenna(im, kohde, LEVEYS)
        _tallenna(im, pieni, LEVEYS_PIENI)
        manifesti[nimi] = {
            "gw": _kierros(kuvio, lahde),
            "signature": tiiviste,
            "deadline_utc": meta.get("deadline_utc"),
            "projection_generated_at": meta.get("generated_at"),
            "source": lahde.name,
            "published_at": now.astimezone(dt.timezone.utc).isoformat(
                timespec="seconds"),
            "sha256": {nimi: sha256(kohde), pieni.name: sha256(pieni)},
        }
        print(f"{lahde.name} -> assets/cards/{kohde.name} "
              f"({kohde.stat().st_size / 1024:.0f} kB) + {pieni.name} "
              f"({pieni.stat().st_size / 1024:.0f} kB)")
        tehty += 1
    if tehty:
        kirjoita_manifesti(manifesti)
    else:
        print("::warning::Yhtaan korttia ei julkaistu.")
    return tehty


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="tulosta korttien tila (kortin_tila), exit 1 jos jokin on vanha")
    args = ap.parse_args(argv)
    meta = lue_meta()
    now = dt.datetime.now(dt.timezone.utc)
    nykyiset = nykyiset_tiivisteet(now)
    if args.check:
        manifesti = lue_manifesti()
        huono = 0
        for nimi in NIMET:
            ok, syy = kortin_tila(manifesti.get(nimi), nykyiset.get(nimi), meta, now)
            print(f"{'OK   ' if ok else 'VANHA'} {nimi}: {syy}")
            huono += not ok
        return 1 if huono else 0
    try:
        import PIL  # noqa: F401
    except ImportError:
        # 22.9: oli ::warning + exit 0, eli CI:ssa hiljainen no-op: kortteja
        # ei julkaistu ja askel oli vihrea.
        print("::error::Pillow puuttuu - kortteja ei julkaistu sivustolle.")
        return 1
    julkaise(nykyiset, meta, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
