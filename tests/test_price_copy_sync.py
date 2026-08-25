"""PORTTI: hintalupaus ja ilmaisikkuna pysyvat synkassa (25.8.2026).

🔴 KAKSI LOYDOSTA JOTKA TAMA PORTTI ESTAA JATKOSSA (copy-sync-auditointi 25.8):

1. `faq.html` (4 hintamainintaa) ja `llms.txt` (1) myivat TAYDELLA HINNALLA
   tuotetta joka on juuri nyt ILMAINEN. Mitattu: molemmissa nolla mainintaa
   ilmaisikkunasta, samalla kun index.html sanoi "Premium is free until the
   12 September deadline" ja pro-spa:n Paywall sanoi aareen etta nyt maksaminen
   on huono kauppa. Lukija joka laskeutuu FAQ:iin nakee hinnan eika kuule
   ikkunasta.

2. `store.config.json` julkaisi ERI TARKKUUSLUVUT kuin livesivut: "140 graded
   matches ... 54.3% ... 80.0%" vastaan livesivun 255 / 50,6 % / 72,5 %. Ja
   sama store-teksti kehotti lukijaa tarkistamaan goaliq.appista. Store-luku
   voi paivittya VAIN submitilla, live-luku paivittyy joka kierros - se ei ole
   epasynkka vaan rakenteellinen varmuus vanhentumisesta.

🔴 EHTO EI VANHENE, TEKSTI VANHENEE. Ikkunateksti on VAARIN kahdella tavalla:
puuttuvana nyt ja jaljella 12.9. jalkeen. Portti vahtii molempia suuntia, jotta
poisto ei jaa yhden ihmisen muistin varaan.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Pinnat joilla hinta esiintyy. 🔴 Lista on portin kattavuus: jos uusi sivu
# alkaa myyda, se on lisattava tanne TAI portti ei nae sita.
HINTAPINNAT = ["index.html", "faq.html", "predictions.html", "fpl.html",
               "llms.txt", "creators.html"]

# Hinnan tunnistimet. Useita muotoja, koska sama luku kirjoitetaan sivuilla
# eri tavoin (&euro;, €, EUR, pilkku vs piste).
HINTA = re.compile(r"3[.,]99\s*(?:&euro;|€|EUR|euros)", re.I)

# Ikkunan tunnistimet.
IKKUNA = re.compile(r"12 September|September 12|GW4 deadline", re.I)


def _window_end() -> dt.datetime:
    """Ikkunan paattymishetki KOODISTA, ei tasta testista.

    Jos testi kovakoodaisi paivan, se voisi olla eri mielta kuin `premium.py`
    ja portti vahtisi vaaraa hetkea.
    """
    s = (ROOT / "api" / "premium.py").read_text(encoding="utf-8")
    m = re.search(r'FREE_PREMIUM_UNTIL_DEFAULT\s*=\s*"([^"]+)"', s)
    assert m, "FREE_PREMIUM_UNTIL_DEFAULT ei loytynyt api/premium.py:sta"
    return dt.datetime.fromisoformat(m.group(1))


def _ikkuna_auki() -> bool:
    return dt.datetime.now(dt.timezone.utc) < _window_end()


def _lue(nimi: str) -> str | None:
    p = ROOT / nimi
    return p.read_text(encoding="utf-8") if p.exists() else None


def test_hintapinta_kertoo_ilmaisikkunasta_kun_se_on_auki():
    """🔴 Sivu joka myy hinnalla mutta ei kerro etta tuote on juuri nyt
    ilmainen, myy vaaraa kauppaa."""
    if not _ikkuna_auki():
        return  # ikkuna kiinni: toinen testi vahtii etta teksti on POISTETTU
    puuttuu = []
    for nimi in HINTAPINNAT:
        s = _lue(nimi)
        if s is None or not HINTA.search(s):
            continue
        if not IKKUNA.search(s):
            puuttuu.append(nimi)
    assert not puuttuu, (
        f"Nama pinnat myyvat hinnalla mutta eivat kerro ilmaisikkunasta: "
        f"{puuttuu}. Ikkuna on auki {_window_end().date()} asti."
    )


def test_ikkunateksti_on_poistettu_kun_ikkuna_on_kiinni():
    """🔴 Toinen suunta, ja se on se joka unohtuu. Poisto oli 25.8 vain
    HTML-kommenttina ("REMOVE the free window after 2026-09-12 12:30 UTC"),
    eli yhden ihmisen muistin varassa."""
    if _ikkuna_auki():
        return
    jaljella = []
    for nimi in HINTAPINNAT:
        s = _lue(nimi)
        if s is not None and IKKUNA.search(s):
            jaljella.append(nimi)
    assert not jaljella, (
        f"Ilmaisikkuna sulkeutui {_window_end().date()} mutta nama pinnat "
        f"lupaavat sita yha: {jaljella}. Poista teksti."
    )


def test_store_listaus_ei_kovakoodaa_tarkkuuslukua():
    """🔴 Store-luku voi paivittya VAIN submitilla, live-luku paivittyy joka
    kierros. Kovakoodattu luku listauksessa ei ole epasynkka vaan
    rakenteellinen VARMUUS vanhentumisesta.

    Mitattu 25.8: listaus sanoi 140 ottelua / 54,3 % / 80,0 %, live 255 /
    50,6 % / 72,5 %, ja sama teksti kehotti tarkistamaan goaliq.appista.
    """
    p = ROOT.parent / "goaliq-app" / "store.config.json"
    if not p.exists():
        return  # mobiilirepo ei ole mountattu
    d = json.loads(p.read_text(encoding="utf-8"))

    def tekstit(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from tekstit(v)
        elif isinstance(o, list):
            for v in o:
                yield from tekstit(v)
        elif isinstance(o, str):
            yield o

    # 🔴 Etsi KUVIO eika tiettya lukua: "54.3%" korjattuna mutta "61.2%"
    # lisattyna olisi sama vika uudessa asussa.
    tarkkuus = re.compile(
        r"\d{2,4}\s+(?:graded|completed)\s+matches"
        r"|\d{1,3}[.,]\d\s*%\s*(?:when|of|correct)"
        r"|(?:correctly|acert\w+|acert\w+)\s+in\s+\d{1,3}[.,]\d\s*%",
        re.I)
    osumat = [t[:120] for t in tekstit(d) if tarkkuus.search(t)]
    assert not osumat, (
        "store.config.json kovakoodaa tarkkuusluvun. Se voi paivittya vain "
        "submitilla, joten se vanhenee varmasti. Kayta muotoa joka ohjaa "
        "lukijan livesivulle ilman lukua.\n" + "\n".join(osumat)
    )


def test_portti_nakee_hinnan_ja_ikkunan_oikeat_muodot():
    """Negatiivinen kontrolli: ilman tata `HINTA`/`IKKUNA` voisivat olla
    rikki ja portti lapaisisi tyhjana."""
    for muoto in ("3.99 &euro;/month", "3,99 €", "3.99 EUR per month",
                  "3.99 euros per month"):
        assert HINTA.search(muoto), muoto
    for muoto in ("until 12 September", "the GW4 deadline on 12 September"):
        assert IKKUNA.search(muoto), muoto
    assert not HINTA.search("25 EUR per year"), "vuosihinta ei ole kuukausi"
    assert not IKKUNA.search("in September we ship"), "pelkka kuukausi ei riita"


def test_hintapintoja_loytyy_oikeasti():
    """Portti joka ei loyda yhtaan hintapintaa lapaisee aina."""
    loytyi = [n for n in HINTAPINNAT
              if (s := _lue(n)) is not None and HINTA.search(s)]
    assert len(loytyi) >= 4, f"vain {loytyi} - onko HINTA-regex rikki?"


# ---------------------------------------------------------------------------
# Applen kentta rajat
# ---------------------------------------------------------------------------
# 🔴 MITATTU REGRESSIO 25.8: korjatessani store-kuvauksen tarkkuuslukua laitoin
# uuden lauseen vanhan VIEREEN enka tilalle. Seuraus oli kaksi: sama vaite
# kahdesti perakkain, ja en-US 4020 / es-ES 4028 merkkia eli YLI Applen 4000
# rajan. Edellinen commit oli tehnyt nimenomaan tyon "kolme kuvausta alle
# rajan" - kumosin sen huomaamatta. Submit olisi kaatunut tai kentta olisi
# katkennut kesken lauseen.
APPLE_RAJAT = {"description": 4000, "keywords": 100,
               "subtitle": 30, "promotionalText": 170}


def test_store_kuvaukset_mahtuvat_applen_rajoihin():
    p = ROOT.parent / "goaliq-app" / "store.config.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    info = ((d.get("apple") or {}).get("info") or {})
    yli = []
    for loc, kentat in info.items():
        for kentta, raja in APPLE_RAJAT.items():
            v = kentat.get(kentta)
            if isinstance(v, str) and len(v) > raja:
                yli.append(f"{loc}.{kentta}: {len(v)}/{raja}")
    assert not yli, (
        "Store-kentta yli Applen rajan (submit kaatuu tai teksti katkeaa): "
        + " | ".join(yli))


def test_store_kuvaus_ei_toista_samaa_vaitetta():
    """🔴 Kaksoiskappale syntyi kun korjaus lisattiin vanhan viereen. Se on
    myos AI-tunnusmerkki: sama asia sanottuna kahdesti hieman eri sanoin."""
    p = ROOT.parent / "goaliq-app" / "store.config.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    info = ((d.get("apple") or {}).get("info") or {})
    tunnisteet = {"en-US": "logged before kick-off",
                  "es-ES": "se registra antes",
                  "pt-BR": "registrada antes"}
    toistot = []
    for loc, avain in tunnisteet.items():
        t = (info.get(loc) or {}).get("description") or ""
        if t.count(avain) > 1:
            toistot.append(f"{loc}: {avain!r} x{t.count(avain)}")
    assert not toistot, ("sama vaite toistuu kuvauksessa: "
                         + " | ".join(toistot))
