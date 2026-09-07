# -*- coding: utf-8 -*-
"""Portti: kapteenilistan saanto on sama backendissa ja SPA:ssa.

🔴 TAUSTA (7.9.2026, jonorivi GW-TOP20-SUODATIN).

Ilmaispinnan kapteenisivu rajaa ehdokkaat `MAX_CAPTAIN_PER_CLUB = 2`:een
seuraa kohden - katto ei ole FPL:n saanto vaan HAJAUTUSTA: kolme
kapteeniehdokasta samasta joukkueesta on yksi veto, ei kolme.

`web/pro-spa`:n `CaptainRanker` otti top 10:n **ilman kattoa**:

    [...data.players].sort((a, b) => gwXp(b, gw) - gwXp(a, gw)).slice(0, 10)

Mitattu GW4:sta, ja listat EROSIVAT:

    backend (cap 2)   ... 9 Isak (LIV)      10 Virgil (LIV)
    SPA (ei kattoa)   ... 9 Calafiori (ARS) 10 Isak (LIV)

Calafiori on Arsenalin KOLMAS, eli premium-kayttaja naki
kapteeniehdokkaana pelaajan jota oma ilmainen kapteenisivumme ei listannut
lainkaan. Kaksi pintaa, kaksi saantoa, eika kumpikaan kertonut omaansa
(muisti: `kaksi-listaa-kaksi-saantoa`).

Tama portti mittaa kolme asiaa:
  1. vakio on sama molemmissa,
  2. SPA kayttaa sita eika paljasta `slice`a,
  3. katto on KERROTTU lukijalle SPA:n omassa selitteessa.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPA_API = ROOT / "web" / "pro-spa" / "src" / "lib" / "api.ts"
RANKER = (ROOT / "web" / "pro-spa" / "src" / "lib" / "components"
          / "CaptainRanker.svelte")


# 🔴 Ensimmainen versio oli `\.sort\([^)]*gwXp[^)]*\)...` - ja `[^)]*` ei voi
# ylittaa `gwXp(b, nextGw)`:n sulkua, joten regex ei osunut KOSKAAN. Portti
# olisi ollut vihrea vaikka paljas slice palaisi. Negatiivinen kontrolli
# alla loysi sen heti.
PALJAS_SLICE = re.compile(r"\.sort\([\s\S]{0,160}?gwXp[\s\S]{0,160}?\.slice\(")


def _ilman_kommentteja(teksti: str) -> str:
    """Kommentit pois: portti ei saa loytaa omaa selitystaan (7.9: kolme
    porttia teki tasan sen samana paivana)."""
    ulos = re.sub(r"/\*[\s\S]*?\*/", "", teksti)
    return "\n".join(r for r in ulos.splitlines()
                     if not r.strip().startswith("//"))


def test_seurakatto_on_sama_molemmissa():
    from src.models.fpl_gw_xp import MAX_CAPTAIN_PER_CLUB

    lahde = _ilman_kommentteja(SPA_API.read_text(encoding="utf-8"))
    m = re.search(r"MAX_CAPTAIN_PER_CLUB\s*=\s*(\d+)", lahde)
    assert m, "SPA:sta puuttuu MAX_CAPTAIN_PER_CLUB"
    assert int(m.group(1)) == MAX_CAPTAIN_PER_CLUB, (
        f"SPA sanoo {m.group(1)}, backend {MAX_CAPTAIN_PER_CLUB}")


def test_ranker_kayttaa_jaettua_lukijaa_eika_paljasta_slicea():
    lahde = _ilman_kommentteja(RANKER.read_text(encoding="utf-8"))
    assert "captainShortlist(" in lahde, (
        "CaptainRanker ei kayta jaettua lukijaa")
    # Paljas top-N ilman kattoa on tasan se vika joka korjattiin.
    assert not PALJAS_SLICE.search(lahde), (
        "CaptainRanker lajittelee ja leikkaa itse - katto ohitetaan")


def test_katto_on_kerrottu_lukijalle():
    """Suodatin jota ei kerrota on sama kuin ei suodatinta lukijan kannalta:
    han vertaa listaa toiseen lahteeseen ja nakee puuttuvia nimia."""
    lahde = RANKER.read_text(encoding="utf-8")
    # Selite on renderoityvaa tekstia, ei kommentti - siksi tama lukee
    # tiedoston KOMMENTTEINEEN mutta vaatii osuman <p>-lohkosta.
    m = re.search(r"<p class=\"muted\">([\s\S]*?)</p>", lahde)
    assert m, "selitelohkoa ei loytynyt"
    selite = m.group(1)
    assert "per club" in selite, f"katto ei nay lukijalle: {selite[:200]}"
    assert "MAX_CAPTAIN_PER_CLUB" in selite, (
        "luku on kovakoodattu selitteeseen - se ajautuu jos vakio muuttuu")


def test_kontrolli_havaitsin_loytaa_paljaan_slicen():
    """NEGATIIVINEN KONTROLLI: ilman tata portti voisi olla vihrea siksi
    ettei regex osu mihinkaan."""
    paha = ("let top = $derived(\n"
            "  [...data.players].sort((a, b) => gwXp(b, nextGw) - gwXp(a, nextGw)).slice(0, 10)\n"
            ");")
    assert PALJAS_SLICE.search(paha)
    hyva = "let top = $derived(captainShortlist(data.players, nextGw, 10));"
    assert not PALJAS_SLICE.search(hyva)


def test_kontrolli_kommenttien_suodatus_toimii():
    """Portti ei saa loytaa omaa selitystaan lahdekoodin kommentista."""
    vain_kommentti = "// MAX_CAPTAIN_PER_CLUB = 9 selitys\nconst x = 1;\n"
    assert "MAX_CAPTAIN_PER_CLUB" not in _ilman_kommentteja(vain_kommentti)
    lohko = "/* MAX_CAPTAIN_PER_CLUB = 9 */\nconst y = 2;\n"
    assert "MAX_CAPTAIN_PER_CLUB" not in _ilman_kommentteja(lohko)
