"""Julkaise uusimmat generoidut kortit sivustolle VAKIONIMILLA.

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

Aja `fpl-data-refresh`issa korttien generoinnin jalkeen. Exit 0 myos kun
lahdetta ei ole (kauden alussa), jotta tama ei pada refreshia - vanha kuva
jaa silloin voimaan ja tuoreusportti huutaa siita erikseen.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

CARDS_IN = config.PROJECT_ROOT / "outputs" / "cards"
CARDS_OUT = config.PROJECT_ROOT / "assets" / "cards"
LEVEYS = 900
LAATU = 82

# (lahdekuvio, kohdenimi). Kuvio poimii kierrosnumeron, jotta uusin voittaa.
KORTIT = [
    (re.compile(r"goaliq_standouts_gw(\d+)\.png$"), "gameweek-card.webp"),
    (re.compile(r"goaliq_projected_xi_gw(\d+)\.png$"), "projected-xi-card.webp"),
]


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


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("::warning::Pillow puuttuu — kortteja ei julkaistu sivustolle.")
        return 0

    CARDS_OUT.mkdir(parents=True, exist_ok=True)
    tehty = 0
    for kuvio, nimi in KORTIT:
        lahde = uusin(kuvio)
        if lahde is None:
            print(f"::notice::{nimi}: lahdekorttia ei ole, vanha jaa voimaan.")
            continue
        kohde = CARDS_OUT / nimi
        im = Image.open(lahde)
        w, h = im.size
        im = im.resize((LEVEYS, round(h * LEVEYS / w)), Image.LANCZOS)
        im.convert("RGB").save(kohde, "WEBP", quality=LAATU, method=6)
        kb = kohde.stat().st_size / 1024
        print(f"{lahde.name} -> {kohde.relative_to(config.PROJECT_ROOT)} "
              f"({kb:.0f} kB)")
        tehty += 1
    if not tehty:
        print("::warning::Yhtaan korttia ei julkaistu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
