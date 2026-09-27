# -*- coding: utf-8 -*-
"""POSTATTU-KORTTI-EI-OLE-TALLESSA (27.9.2026): jokainen gen_share_card-ajo
kirjoittaa kuvan viereen sivutiedoston (sha256 + argumentit + rivit).

Mitattu 12.9: outputs/ on gitignoressa ja jokainen ajo kirjoittaa saman
tiedostonimen yli -> 9.9 postattu GW4-kortti oli kadonnut, eika postattua
kuvaa voinut todentaa. Portti ajaa main():n KAIKKI kolme paluupolkua
(reply-kortti, gw-outlook, tavallinen lista), koska sivutiedosto joka
puuttuu yhdelta polulta on sama aukko kuin ennen.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gen_share_card as g  # noqa: E402


def _png(path: Path, color=(10, 20, 30)) -> Path:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path, "PNG")
    return path


def test_sivutiedosto_kantaa_kuvan_tiivisteen_ja_rivit(tmp_path):
    png = _png(tmp_path / "kortti.png")
    spec = {"title": "GW6 XP", "rows": [{"rank": 1, "name": "Haaland", "value": "8.4"}],
            "generated_at": "2026-09-27T10:00:00Z"}
    side = g.write_sidecar(png, spec, ["xp", "--top", "10"])
    assert side.name == "kortti.png.json"
    d = json.loads(side.read_text(encoding="utf-8"))
    assert d["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
    assert d["rows"][0]["name"] == "Haaland"
    assert d["card"] == "xp" and d["argv"] == ["xp", "--top", "10"]
    assert d["source_generated_at"] == "2026-09-27T10:00:00Z"
    # Negatiivinen kontrolli: eri kuva -> eri tiiviste (ei vakioarvoa).
    png2 = _png(tmp_path / "toinen.png", color=(200, 0, 0))
    d2 = json.loads(g.write_sidecar(png2, spec, ["xp"]).read_text(encoding="utf-8"))
    assert d2["sha256"] != d["sha256"]


@pytest.mark.parametrize("polku", ["reply", "gw_outlook", "lista"])
def test_jokainen_main_polku_kirjoittaa_sivutiedoston(tmp_path, monkeypatch, polku):
    out = tmp_path / f"{polku}.png"
    if polku == "reply":
        spec = {"kind": "reply_list", "title": "R", "rows": [], "file": "r.png"}
        monkeypatch.setitem(g.REPLY_RENDERERS, "reply_list", lambda sp, o: _png(Path(o)))
    elif polku == "gw_outlook":
        spec = {"kind": "gw_outlook", "title": "O", "gw": 6, "fixtures": [1, 2], "file": "o.png"}
        monkeypatch.setattr(g, "render_gw_outlook", lambda sp, o: _png(Path(o)))
    else:
        spec = {"title": "L", "rows": [{"rank": 1}], "file": "l.png"}
        monkeypatch.setattr(g, "render", lambda sp, o: _png(Path(o)))
    monkeypatch.setitem(g.BUILDERS, "xp", lambda args: spec)
    monkeypatch.setattr(sys, "argv", ["gen_share_card.py", "xp", "--out", str(out)])
    assert g.main() == 0
    side = out.with_name(out.name + ".json")
    assert side.exists(), f"{polku}: sivutiedosto puuttuu"
    d = json.loads(side.read_text(encoding="utf-8"))
    assert d["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
