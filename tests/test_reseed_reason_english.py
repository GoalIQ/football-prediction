# -*- coding: utf-8 -*-
"""Portti: reseed-syy on julkista tekstia, joten se kirjoitetaan englanniksi.

TAUSTA (julkaisuportti 21.9.2026). `data/model_squad_reseed/gw{n}.json`:n
`reason` kopioituu freezeen (`data/model_squad_frozen/gw{n}.json`
`meta.reseed.reason`, freeze_model_squad_gw.RESEED_KEYS), ja jaadytetyn
rungon jakokortti ohjaa lukijan juuri siihen tiedostoon julkisessa
repossa. GW3:n ja GW5:n syyt ovat suomeksi.

MITA TEHTIIN JA MITA EI: vanhoja jaadytettyja artefakteja EI kirjoiteta
uudelleen (freeze on immutable, ja koko mallisarjan vaite lepaa sen
git-historian varassa). Siksi GW3 ja GW5 ovat poikkeuslistalla
perusteluineen (saanto 6a kohta 2), ja portti estaa UUDEN suomenkielisen
syyn: sekä paatostiedoston etta sen freezeen kopioidun kentan.

Kieli tunnistetaan karkeasti: a/o-umlautit tai suomen funktiosanat
kokonaisina sanoina. Portti on tarkoituksella konservatiivinen (ei
sijapaatteita: "Villa" ja "Hull" ovat seurojen nimia). Erotteleva kontrolli
todistaa etta nykyiset suomenkieliset syyt tunnistetaan.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEED_DIR = ROOT / "data" / "model_squad_reseed"
FROZEN_DIR = ROOT / "data" / "model_squad_frozen"

#: gw -> miksi suomenkielinen syy saa jaada. Lista ei saa kasvaa: uusi
#: reseed kirjoitetaan englanniksi.
LEGACY_SUOMI: dict[int, str] = {
    3: ("Jaadytetty 4.9.2026 ennen tata porttia; syy on kopioitu "
        "immutableen gw3.json-freezeen, jota ei kirjoiteta uudelleen."),
    5: ("Jaadytetty 17.9.2026 ennen tata porttia; syy on kopioitu "
        "immutableen gw5.json-freezeen, jota ei kirjoiteta uudelleen."),
}

_SUOMEN_SANAT = {"ja", "eika", "eikä", "joten", "etta", "että", "koska",
                 "jolloin", "kun", "mutta", "tai", "ovat", "oli", "sita",
                 "sitä", "siita", "siitä", "ei"}


def suomea(teksti: str) -> bool:
    if re.search(r"[äöåÄÖÅ]", teksti or ""):
        return True
    sanat = set(re.findall(r"[a-zåäö]+", (teksti or "").lower()))
    return bool(sanat & _SUOMEN_SANAT)


def _gw(p: Path) -> int | None:
    m = re.fullmatch(r"gw(\d+)\.json", p.name)
    return int(m.group(1)) if m else None


def suomenkieliset_syyt(reseed_dir: Path, frozen_dir: Path) -> list[str]:
    """Paatostiedostot ja freezet joiden reseed-syy on suomea, poikkeuksia
    lukuun ottamatta."""
    out = []
    for p in sorted(reseed_dir.glob("gw*.json")):
        gw = _gw(p)
        if gw is None or gw in LEGACY_SUOMI:
            continue
        syy = json.loads(p.read_text(encoding="utf-8")).get("reason", "")
        if suomea(syy):
            out.append(f"{p.name}: reason")
    for p in sorted(frozen_dir.glob("gw*.json")):
        gw = _gw(p)
        if gw is None or gw in LEGACY_SUOMI:
            continue
        reseed = (json.loads(p.read_text(encoding="utf-8")).get("meta") or {}
                  ).get("reseed") or {}
        if suomea(reseed.get("reason", "")):
            out.append(f"{p.name}: meta.reseed.reason")
    return out


def test_uusi_reseed_syy_on_englanniksi():
    loydot = suomenkieliset_syyt(RESEED_DIR, FROZEN_DIR)
    assert not loydot, (
        f"Suomenkielinen reseed-syy julkisessa repossa: {loydot}. Syy "
        "kopioituu jaadytettyyn runkoon, johon jakokortti ohjaa lukijan. "
        "Kirjoita reason englanniksi ennen freezea.")


def test_poikkeuslista_ei_vanhene():
    """Jokainen poikkeus osoittaa olemassa olevaan, yha suomenkieliseen
    syyhyn; muuten se poistetaan listalta."""
    for gw, miksi in LEGACY_SUOMI.items():
        assert len(miksi) > 30
        p = RESEED_DIR / f"gw{gw}.json"
        assert p.exists(), f"poikkeus GW{gw} osoittaa tiedostoon jota ei ole"
        syy = json.loads(p.read_text(encoding="utf-8")).get("reason", "")
        assert suomea(syy), (
            f"GW{gw}:n syy ei ole enaa suomea - poista se poikkeuslistalta")


def test_erotteleva_kontrolli(tmp_path):
    """Tunnistin nakee nykyiset suomenkieliset syyt ja paastaa englannin
    (myos seuran nimet) lapi; uusi suomenkielinen tiedosto kaataa portin."""
    for gw in LEGACY_SUOMI:
        syy = json.loads((RESEED_DIR / f"gw{gw}.json").read_text(
            encoding="utf-8"))["reason"]
        assert suomea(syy)
    assert not suomea("The chain broke in GW4, so the model restarts from "
                      "the entry's GW4 picks. Aston Villa and Hull are clubs.")
    r, f = tmp_path / "reseed", tmp_path / "frozen"
    r.mkdir()
    f.mkdir()
    (r / "gw9.json").write_text(json.dumps(
        {"gw": 9, "reason": "Ketju katkesi, joten aloitetaan alusta."}),
        encoding="utf-8")
    (f / "gw9.json").write_text(json.dumps(
        {"meta": {"reseed": {"reason": "Restarted from the entry's picks."}}}),
        encoding="utf-8")
    assert suomenkieliset_syyt(r, f) == ["gw9.json: reason"]
