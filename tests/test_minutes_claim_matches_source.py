"""Portti: minuuttiharhaa koskeva luku on sidottu MITTAUKSEEN, ei toiseen pintaan.

TAUSTA (12.9.2026, I18N-MINUUTTIVAITE-DRIFT). Vaite "players we projected at
80+ minutes came in about 14 minutes lower than we said" eli SEITSEMALLA
pinnalla: `lib/i18n/{en,es,pt}.ts` kahdella avaimella kussakin, ja pro-SPA:n
`XpTable.svelte`. Jokainen kasin kirjoitettu, eli jokainen voi eriytya.

Jonorivin alkuperainen premissi (web korjasi, mobiili ei) oli VAARIN -- kaikki
sanoivat 14. Uusintamittaus paljasti oikean vian:

    n=132   keskiarvo +13.8 min   MEDIAANI +0.0 min
    39 % osuu viiden minuutin sisaan, 21 % on yli 30 min pielessa

Luku 14 oli siis oikein, mutta LAUSE oli vaara: se luki keskiarvon
TYYPILLISENA tapauksena, ja tyypillinen 80+ pelaaja osuu kohdalleen.
Keskiarvon tekee hanta.

MEKANISMI. Kaksi ehtoa, molemmat LUKUUN sidottuja eivatka sanalistaan
(sanalista vanhenisi ja se on kolmella kielella):

  (1) Jokaisella pinnalla on sama luku kuin artefaktissa. Jos mittaus
      muuttuu, copy on stale ja tama kaatuu.
  (2) Jos keskiarvo ja mediaani eroavat olennaisesti, keskiarvoa EI SAA
      julkaista yksin: pinnan on kannettava myos hannan luku. Tama on
      rakenteellinen ehto, ei sanamuoto -- se pitaa millä tahansa kielella.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LAHDE = ROOT / "data" / "preseason_minutes_bias.json"
SPA = ROOT / "web" / "pro-spa" / "src" / "lib" / "components" / "XpTable.svelte"
APP = ROOT.parent / "goaliq-app" / "lib" / "i18n"
AVAIMET = ("fantasy.xp.minutes_note", "fantasy.xp.method_note")

# Kynnys jonka yli keskiarvo ja mediaani "eroavat olennaisesti".
ERO_KYNNYS_MIN = 5.0


def _mittaus() -> dict:
    assert LAHDE.exists(), (
        f"{LAHDE.relative_to(ROOT)} puuttuu. Aja "
        "scripts/measure_preseason_minutes_bias.py. Artefakti on repossa "
        "(.gitignore-poikkeus), jotta tama testi ei ohita itseaan CI:ssa."
    )
    return json.loads(LAHDE.read_text(encoding="utf-8"))


def _pinnat() -> dict[str, str]:
    """Kaikki seitseman pintaa. Puuttuva pinta kaataa, ei ohita."""
    ulos: dict[str, str] = {}
    if SPA.exists():
        teksti = SPA.read_text(encoding="utf-8")
        # vain nakyva kappale, ei kommentteja
        teksti = re.sub(r"<!--.*?-->", " ", teksti, flags=re.S)
        ulos["pro-spa/XpTable.svelte"] = teksti
    if APP.exists():
        for kieli in ("en", "es", "pt"):
            p = APP / f"{kieli}.ts"
            if not p.exists():
                continue
            s = p.read_text(encoding="utf-8")
            for avain in AVAIMET:
                m = re.search(rf'"{re.escape(avain)}":\s*"([^"]*)"', s)
                assert m, f"{kieli}.ts: avainta {avain} ei loytynyt"
                ulos[f"{kieli}.ts:{avain}"] = m.group(1)
    return ulos


def _vaiteosa(teksti: str) -> str:
    """Se osa jossa minuuttivaite on. Muu copy voi sisaltaa muita lukuja."""
    for ankkuri in ("three summers", "tres veranos", "três verões"):
        i = teksti.find(ankkuri)
        if i != -1:
            return teksti[i:]
    return ""


def test_pintoja_on_seitseman():
    """Ilman tata koko tiedosto voisi olla vihrea nollalla pinnalla."""
    pinnat = _pinnat()
    if not pinnat:
        pytest.skip("kumpikaan repo ei ole mountattu")
    assert len(pinnat) == 7, f"loydetty {len(pinnat)} pintaa: {sorted(pinnat)}"


def test_jokainen_pinta_sanoo_saman_luvun_kuin_mittaus():
    pinnat = _pinnat()
    if not pinnat:
        pytest.skip("kumpikaan repo ei ole mountattu")
    ka = round(_mittaus()["mean"])
    viat = [n for n, t in pinnat.items()
            if not re.search(rf"\b{ka}\b", _vaiteosa(t))]
    assert not viat, (
        f"nama pinnat eivat sano mitattua keskiarvoa ({ka} min): {viat}. "
        "Mittaus: data/preseason_minutes_bias.json "
        "(scripts/measure_preseason_minutes_bias.py)."
    )


def test_keskiarvoa_ei_julkaista_yksin_kun_tyypillinen_eroaa():
    """TAMA on portin ydin.

    Kun keskiarvo ja mediaani eroavat olennaisesti, keskiarvo yksin LUKEE
    tyypillisena tapauksena vaikka se ei ole sellainen. Ehto ei ole
    sanamuoto: pinnan on kannettava myos hannan luku, jolloin lukija nakee
    mista keskiarvo tulee. Pitaa milla tahansa kielella.
    """
    pinnat = _pinnat()
    if not pinnat:
        pytest.skip("kumpikaan repo ei ole mountattu")
    m = _mittaus()
    ero = abs(m["mean"] - m["median"])
    if ero < ERO_KYNNYS_MIN:
        pytest.skip(f"keskiarvo ja mediaani eroavat vain {ero:.1f} min")
    hanta = 30  # measure_preseason_minutes_bias.HANTA_RAJA
    viat = [n for n, t in pinnat.items()
            if not re.search(rf"\b{hanta}\b", _vaiteosa(t))]
    assert not viat, (
        f"keskiarvo {m['mean']:+} ja mediaani {m['median']:+} eroavat "
        f"{ero:.1f} min, joten keskiarvoa ei saa julkaista yksin. Nama "
        f"pinnat eivat kerro hantaa ({hanta} min): {viat}."
    )


def test_kontrolli_vanha_lause_kaatuisi():
    """Fikstuuri on se teksti joka oli livena 12.9 asti."""
    vanha = ("Across the last three summers, players we projected at 80+ "
             "minutes came in about 14 minutes lower than we said, and the "
             "gap closes as 2026/27 results arrive.")
    osa = _vaiteosa(vanha)
    assert re.search(r"\b14\b", osa), "kontrolli: luku loytyy"
    assert not re.search(r"\b30\b", osa), (
        "kontrolli: vanha lause EI kerro hantaa, joten ehdon 3 pitaa kaatua "
        "siihen. Jos tama assertio kaatuu, ehto on fail-open."
    )
