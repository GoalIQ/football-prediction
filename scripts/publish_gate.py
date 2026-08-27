# -*- coding: utf-8 -*-
"""CARD-PUBLISH-NIMIPORTTI (27.8): nimiesto JULKAISUVAIHEESSA, ei renderoinnissa.

Paatos 24.8: korttiin ei lisata estolistaa, koska kortti = sivu on koko
rakenteen peruste (tests/test_share_card_server_rows.py) ja vaientaminen
palauttaisi "kortti nayttaa muuta kuin taulukko" -luokan. Julkaisutarkistaja
osoitti sen puolikkaaksi: kova saanto koskee JULKAISEMISTA. Tama portti ajetaan
ennen kuin kortti tai teksti menee X:aan, Blueskyyn, IG:hen tai DM:aan.

Kaytto:
  python -m scripts.publish_gate --page fpl/xg-leaders.html   # sivun korttispec
  python -m scripts.publish_gate --text "postausteksti ..."
  python -m scripts.publish_gate --file draft.txt
Exit 1 + nimet jos estolistan nimi esiintyy; exit 0 muuten. Lista:
scripts/publish_blocklist.json (nimi + syy + kirjattu pvm), ei kovakoodattu.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKLIST_PATH = ROOT / "scripts" / "publish_blocklist.json"  # data/ on gitignoressa


def load_blocklist(path: Path = BLOCKLIST_PATH) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"publish_gate: estolista puuttuu: {path}")
    d = json.loads(path.read_text(encoding="utf-8"))
    return list(d.get("players") or [])


def card_spec_from_page(html_text: str) -> dict | None:
    m = re.search(r"data-card-spec='(.*?)'>", html_text, re.S)
    if not m:
        return None
    return json.loads(_html.unescape(m.group(1)))


def spec_text(spec: dict) -> str:
    osat = [str(spec.get("title") or ""), str(spec.get("subtitle") or "")]
    for r in spec.get("rows") or []:
        osat.extend(str(v) for v in r.values())
    return "\n".join(osat)


def blocked_names(text: str, blocklist: list[dict]) -> list[dict]:
    """Nimet jotka esiintyvat tekstissa kokonaisina sanoina (ei osasanoina:
    'Thiaw' ei saa osua 'Mathiaw'-tyyppiseen nimeen eika painvastoin)."""
    hits = []
    for entry in blocklist:
        name = entry.get("name") or ""
        if not name:
            continue
        if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I):
            hits.append(entry)
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--page", help="renderoity sivu jonka korttispec tarkistetaan")
    g.add_argument("--text", help="postaus-/DM-teksti")
    g.add_argument("--file", help="tekstitiedosto")
    args = ap.parse_args(argv)
    if args.page:
        spec = card_spec_from_page(Path(args.page).read_text(encoding="utf-8", errors="replace"))
        if spec is None:
            print(f"publish_gate: {args.page}: ei korttispecia")
            return 2
        text = spec_text(spec)
    elif args.text:
        text = args.text
    else:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    hits = blocked_names(text, load_blocklist())
    if hits:
        print("PUBLISH GATE: BLOKATTU")
        for h in hits:
            print(f"  - {h['name']}: {h.get('reason', '')} ({h.get('since', '')})")
        return 1
    print("PUBLISH GATE: OK (0 estolistan nimea)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
