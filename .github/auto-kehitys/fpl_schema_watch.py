"""FPL-skeemavahti (16.10.2026): FPL:n sääntö- ja datamuutos on aalto, johon ehtii ensimmäisenä.

DefCon-pisteet tulivat FPL:n dataan kentiksi ennen kuin kukaan rakensi niille työkalua.
Tämä vahti vertaa bootstrap-staticin rakennetta (kentät, chipit, statistiikat,
pistesäännöt ja asetukset) edelliseen tilannekuvaan ja kirjoittaa muutokset
markdowniksi aallonharja-agentille. Vain stdlib, ei kuluja.

Käyttö:
  python fpl_schema_watch.py --snapshot data/fpl_schema_snapshot.json --out /tmp/fpl-schema-diff.md
Exit 0 aina (myös kun FPL ei vastaa): puuttuva mittaus kirjoitetaan tulosteeseen.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
UA = {"User-Agent": "Mozilla/5.0 (GoalIQ schema watch)"}


def _litistetty(obj, etuliite: str = "") -> dict[str, str]:
    """Sisäkkäinen dict -> {'a.b.c': arvo}; skalaarilistat yhdeksi merkkijonoksi."""
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        for k in sorted(obj):
            out.update(_litistetty(obj[k], f"{etuliite}{k}."))
    elif isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            out[etuliite[:-1]] = json.dumps(obj, ensure_ascii=False)
        else:
            out[etuliite[:-1]] = f"<lista {len(obj)}>"
    else:
        out[etuliite[:-1]] = json.dumps(obj, ensure_ascii=False)
    return out


def _kentat(rivit) -> list[str]:
    nimet: set[str] = set()
    for r in rivit or []:
        if isinstance(r, dict):
            nimet.update(r.keys())
    return sorted(nimet)


def tilannekuva(boot: dict) -> dict:
    chipit = []
    for c in boot.get("chips") or []:
        if isinstance(c, dict):
            chipit.append(f"{c.get('name')} gw{c.get('start_event')}-{c.get('stop_event')}")
    return {
        "ylatason_avaimet": sorted(boot.keys()),
        "pelaajan_kentat": _kentat(boot.get("elements")),
        "joukkueen_kentat": _kentat(boot.get("teams")),
        "kierroksen_kentat": _kentat(boot.get("events")),
        "statistiikat": sorted(s.get("name", "") for s in boot.get("element_stats") or [] if isinstance(s, dict)),
        "pelipaikat": sorted(f"{t.get('singular_name_short')} max{t.get('squad_select')}"
                             for t in boot.get("element_types") or [] if isinstance(t, dict)),
        "chipit": sorted(chipit),
        "asetukset": _litistetty(boot.get("game_settings") or {}),
        "pistesaannot": _litistetty((boot.get("game_config") or {}).get("scoring") or {}),
        "saannot": _litistetty((boot.get("game_config") or {}).get("rules") or {}),
    }


def erot(vanha: dict | None, uusi: dict) -> list[str]:
    if not vanha:
        return []
    rivit = []
    for osio in uusi:
        a, b = vanha.get(osio), uusi[osio]
        if isinstance(b, list):
            a = a or []
            lis = [x for x in b if x not in a]
            pois = [x for x in a if x not in b]
            if lis:
                rivit.append(f"- {osio}: uusi {', '.join(lis[:20])}")
            if pois:
                rivit.append(f"- {osio}: poistui {', '.join(pois[:20])}")
        elif isinstance(b, dict):
            a = a or {}
            for k in sorted(set(a) | set(b)):
                if k not in a:
                    rivit.append(f"- {osio}: uusi {k} = {b[k]}")
                elif k not in b:
                    rivit.append(f"- {osio}: poistui {k} (oli {a[k]})")
                elif a[k] != b[k]:
                    rivit.append(f"- {osio}: {k} {a[k]} -> {b[k]}")
    return rivit


def raportti(vanha: dict | None, uusi: dict) -> str:
    if not vanha:
        return "FPL-skeema: ensimmäinen tilannekuva tallennettu, vertailukohtaa ei vielä ole.\n"
    r = erot(vanha, uusi)
    if not r:
        return "FPL-skeema: ei muutoksia edelliseen tilannekuvaan.\n"
    return "FPL-skeema muuttui edellisestä tilannekuvasta:\n" + "\n".join(r) + "\n"


def hae(url: str = URL) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    polku = Path(a.snapshot)
    vanha = json.loads(polku.read_text(encoding="utf-8")) if polku.exists() else None
    try:
        uusi = tilannekuva(hae())
    except Exception as e:  # mittaamatta jäänyt kerrotaan, ajo jatkuu
        teksti = f"FPL-skeema: MITTAAMATTA, FPL ei vastannut ({e!r}).\n"
    else:
        teksti = raportti(vanha, uusi)
        polku.parent.mkdir(parents=True, exist_ok=True)
        polku.write_text(json.dumps(uusi, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    Path(a.out).write_text(teksti, encoding="utf-8")
    print(teksti)
    return 0


if __name__ == "__main__":
    sys.exit(main())
