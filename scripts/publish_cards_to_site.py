"""Julkaise uusimmat generoidut kortit sivustolle VAKIONIMILLA + kierrosmerkinta.

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
Siksi kortin kierros kirjoitetaan nyt `assets/cards/cards.json`:iin samalla
kun kuva julkaistaan, ja portti (`kortin_tila`) vertaa sita samaan lukijaan
jolla renderoijat nimeavat kortin (`actionable_gameweek`). Aikaleimaa ei
lueta mistaan.

Julkaisu kieltaytyy kortista jonka kierros on eri kuin datan actionable GW:
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
from src.models.fpl_gameweek import actionable_gameweek  # sama lukija kuin renderoijilla

CARDS_IN = config.PROJECT_ROOT / "outputs" / "cards"
CARDS_OUT = config.PROJECT_ROOT / "assets" / "cards"
MANIFEST = CARDS_OUT / "cards.json"
XP_PATH = config.DATA_DIR / "fpl_xp_projections.json"
LEVEYS = 900
# index.html: srcset="...-450.webp 450w, ....webp 900w"
LEVEYS_PIENI = 450
LAATU = 82

# Kuinka kauan edellisen kierroksen kortti saa olla sivulla kun data on jo
# kaantynyt seuraavaan. Perustelu ja vaiheittainen mittaus:
# tests/test_site_card_images.py (ARMONAIKA-lohko).
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


def lue_meta(path: Path = XP_PATH) -> dict:
    return (json.loads(path.read_text(encoding="utf-8")).get("meta") or {})


def lue_manifesti(path: Path = MANIFEST) -> dict:
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def kortin_tila(entry: dict | None, meta: dict,
                now: dt.datetime) -> tuple[bool, str]:
    """YKSI LUKIJA: saako taman kortin nayttaa sivulla juuri nyt?

    Vertaa kortin kierrosta (cards.json) samaan lukijaan jolla renderoijat
    nimeavat kortin (`actionable_gameweek`). Sallittu:
      * kortti = actionable GW
      * kortti = actionable - 1, enintaan ARMONAIKA kortin oman deadlinen
        jalkeen (refresh-ajon viive + yksi uusintayritys)
    Ei sallittu: kaikki muu, myos kortti joka on datan EDELLA (kortti ja sivu
    eri datasta) ja puuttuva merkinta (kuva vaihdettu ohi julkaisun).

    Datan oma tuoreus ei ole taman portin asia: jos refresh on kuollut,
    kortti on yhta tuore kuin data, ja sen vahtivat datan omat portit.
    """
    act = actionable_gameweek(meta)
    if act is None:
        return True, ("datassa ei ole tulevaa kierrosta (kauden tauko), "
                      "ei verrattavaa")
    if not entry or not isinstance(entry.get("gw"), int):
        return False, ("kortilla ei ole kierrosmerkintaa assets/cards/cards.json:ssa "
                       "(julkaistu ohi publish_cards_to_site:n?)")
    gw = entry["gw"]
    if gw == act:
        return True, f"kortti GW{gw} = actionable GW{act}"
    if gw > act:
        return False, (f"kortti GW{gw} on datan edella (actionable GW{act}): "
                       "kortti ja sivu ovat eri datasta")
    dl = _utc(entry.get("deadline_utc"))
    if gw == act - 1 and dl is not None and now <= dl + ARMONAIKA:
        h = (now - dl).total_seconds() / 3600
        return True, (f"kortti GW{gw}, actionable GW{act}: GW{gw}:n deadline "
                      f"meni {h:.1f} h sitten, armonaika "
                      f"{ARMONAIKA.total_seconds() / 3600:.0f} h")
    return False, (f"kortti GW{gw}, actionable GW{act}"
                   + (f", GW{gw}:n deadline {dl:%Y-%m-%d %H:%M} UTC" if dl else "")
                   + ". Aja `python -m scripts.refresh_site_cards` tai "
                     "tarkista fpl-data-refreshin 'Render landing page cards' -askel.")


def tarvitsee_renderoinnin(manifesti: dict, meta: dict) -> list[str]:
    """Kortit joiden kierros != actionable GW. CI:n liipaisin.

    Ei armonaikaa: armonaika on portin toleranssi viiveelle, ei syy odottaa.
    Tyhja lista = ei renderointia eika committia (ei churnia joka ajossa).
    """
    act = actionable_gameweek(meta)
    if act is None:
        return []
    return [n for n in NIMET
            if (manifesti.get(n) or {}).get("gw") != act]


def _tallenna(im, kohde: Path, leveys: int) -> None:
    from PIL import Image
    w, h = im.size
    pieni = im.resize((leveys, round(h * leveys / w)), Image.LANCZOS)
    pieni.convert("RGB").save(kohde, "WEBP", quality=LAATU, method=6)


def julkaise(meta: dict, now: dt.datetime) -> int:
    """Kirjoita webp + 450-variantti + cards.json-rivi jokaiselle kortille jonka
    uusin lahde on actionable GW:lta. Palauttaa julkaistujen maaran."""
    from PIL import Image
    act = actionable_gameweek(meta)
    CARDS_OUT.mkdir(parents=True, exist_ok=True)
    manifesti = lue_manifesti()
    tehty = 0
    for kuvio, nimi in KORTIT:
        lahde = uusin(kuvio)
        if lahde is None:
            print(f"::notice::{nimi}: lahdekorttia ei ole, vanha jaa voimaan.")
            continue
        gw = _kierros(kuvio, lahde)
        if gw != act:
            print(f"::notice::{nimi}: uusin lahde {lahde.name} on GW{gw}, data "
                  f"on GW{act} - ei julkaista eri kierroksen korttia.")
            continue
        kohde, pieni = CARDS_OUT / nimi, CARDS_OUT / pieni_nimi(nimi)
        im = Image.open(lahde)
        _tallenna(im, kohde, LEVEYS)
        _tallenna(im, pieni, LEVEYS_PIENI)
        manifesti[nimi] = {
            "gw": gw,
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
        # newline="\n": samat tavut Windowsilla ja runnerilla.
        MANIFEST.write_text(json.dumps(manifesti, indent=1, sort_keys=True)
                            + "\n", encoding="utf-8", newline="\n")
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
    if args.check:
        manifesti = lue_manifesti()
        huono = 0
        for nimi in NIMET:
            ok, syy = kortin_tila(manifesti.get(nimi), meta, now)
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
    julkaise(meta, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
