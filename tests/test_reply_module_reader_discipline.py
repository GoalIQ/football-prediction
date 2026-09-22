"""Reply-moduulin lukijakuri (saanto 6a.2).

`data/reply_modules/` luetaan VAIN `src/marketing/reply_module.load_reply_module`in
kautta, koska vain se tarkistaa deadlinen, regeneroinnin ja FPL-statuksen.
Tiedosto joka avaa moduulin itse ohittaa kaikki kolme, ja julkaisee luvun
joka oli totta eilen. Uusi lukija ei paase listalle vahingossa: testi kaatuu
ja kirjoittaja joutuu perustelemaan valinnan tassa.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED = {
    "src/marketing/reply_module.py":
        "Lukija itse (`load_reply_module`) ja sen polkuapuri `module_path`.",
    "scripts/build_reply_module.py":
        "Kirjoittaja: luo moduulin `rm.module_path`illa, ei lue sita.",
}

PATTERN = re.compile(r"reply_modules|module_path\s*\(")


def test_reply_module_is_read_only_through_the_reader():
    hits = {}
    for base in ("api", "scripts", "src"):
        for f in sorted((ROOT / base).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                s = line.strip()
                if s.startswith("#"):
                    continue
                if PATTERN.search(line):
                    hits.setdefault(rel, []).append(i)
    uusia = {f: ls for f, ls in hits.items() if f not in ALLOWED}
    assert not uusia, (
        "Nama tiedostot lukevat reply-moduulia ohi lukijan. Kayta "
        "`load_reply_module(gw, keys=...)` tai lisaa tiedosto ALLOWED-listalle "
        f"perustelun kanssa: {uusia}")
    for f, why in ALLOWED.items():
        assert why.strip(), f


def test_reply_cards_get_their_numbers_from_the_reader(monkeypatch):
    """Kutsupaikka, ei funktio: kortin CLI-polku kulkee lukijan kautta, ja
    lukijan kieltaytyminen kaataa kortin (ei hiljaista vanhaa kuvaa)."""
    import argparse

    import pytest

    import scripts.gen_share_card as g
    from src.marketing import reply_module as rm

    calls = []

    def refuse(gw, **kw):
        calls.append((gw, kw))
        raise rm.ReplyModuleRefused("GW6 deadline passed")
    monkeypatch.setattr(rm, "load_reply_module", refuse)
    for card, extra in (("reply-cs", {}), ("reply-xp", {}),
                        ("captain-compare", {"players": "a-ars,b-mun"}),
                        ("model-vs-template", {})):
        a = argparse.Namespace(gw=6, top=5, players=extra.get("players"))
        with pytest.raises(SystemExit, match="kieltaytyi"):
            g.BUILDERS[card](a)
    assert len(calls) == 4
