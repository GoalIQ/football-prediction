"""Portti: headerista luettu salaisuus verrataan vain `secrets_equal`illa.

Mitattu tuotannossa 28.9: /api/predict + ei-ASCII X-Admin-Token -> 500.
`hmac.compare_digest(str, str)` nostaa TypeErrorin ei-ASCII-merkeilla, ja
Starlette dekoodaa headerit latin-1:na, joten kuka tahansa pystyi
laukaisemaan 500:n. Portti pitaa huolen etta
  (1) admin- ja kumppanireitti vastaavat ei-ASCII-avaimeen 403/401, ei 500,
  (2) oikea avain toimii yha (muuten (1) olisi vihrea rikkinaisella reitilla),
  (3) raakaa compare_digest-kutsua ei ole muualla kuin `secrets_equal`issa.
     Uusi kutsupaikka ei paase lapi vahingossa: se vaatii rivin
     POIKKEUKSET-listaan perusteluineen (CLAUDE.md saanto 6a kohta 2).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from api.premium import secrets_equal

ROOT = Path(__file__).resolve().parents[1]
ADMIN = "adm-test-" + "0123456789abcdef"
PARTNER_KEY = "k" * 30
# Tavut sellaisinaan: Starlette dekoodaa headerin latin-1:na -> 'Ã¤...'.
NON_ASCII = ("ä" + ADMIN).encode("utf-8")

#: Ainoa sallittu kutsupaikka: (tiedosto, funktio).
SALLITTU = ("api/premium.py", "secrets_equal")

#: {(tiedosto, funktio): perustelu}. Tyhja perustelu ei vapauta.
POIKKEUKSET: dict[tuple[str, str], str] = {}


def test_secrets_equal_ei_kaadu_ei_asciiin():
    assert secrets_equal("äö", "äö") is True
    assert secrets_equal("Ã¤" + ADMIN, ADMIN) is False
    assert secrets_equal(ADMIN, ADMIN) is True
    assert secrets_equal(ADMIN + "x", ADMIN) is False


def test_admin_reitti_ei_ascii_on_403(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    ok = client.get("/api/admin/error-counts", headers={"X-Admin-Token": ADMIN})
    assert ok.status_code == 200, ok.text
    bad = client.get("/api/admin/error-counts",
                     headers={"X-Admin-Token": NON_ASCII})
    assert bad.status_code == 403, bad.text


def test_kumppanireitti_ei_ascii_on_401(client, monkeypatch):
    monkeypatch.setenv("PARTNER_XP_KEYS", f"fpldemon:{PARTNER_KEY}")
    ok = client.get("/api/partner/xp", headers={"X-Partner-Key": PARTNER_KEY})
    assert ok.status_code == 200, ok.text
    bad = client.get("/api/partner/xp",
                     headers={"X-Partner-Key": ("ä" + PARTNER_KEY).encode("utf-8")})
    assert bad.status_code == 401, bad.text


def _compare_digest_kutsut() -> list[tuple[str, str, int]]:
    """(tiedosto, sisin funktio, rivi) jokaiselle compare_digest-kutsulle."""
    out = []
    for base in ("api", "src", "scripts"):
        for path in sorted((ROOT / base).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)

            def walk(node, func="<module>"):
                for child in ast.iter_child_nodes(node):
                    name = func
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        name = child.name
                    if isinstance(child, ast.Call):
                        f = child.func
                        attr = (f.attr if isinstance(f, ast.Attribute)
                                else f.id if isinstance(f, ast.Name) else None)
                        if attr == "compare_digest":
                            out.append((rel, func, child.lineno))
                    walk(child, name)

            walk(tree)
    return out


def _vaarat(kutsut, poikkeukset):
    return [(f, fn, line) for f, fn, line in kutsut
            if (f, fn) != SALLITTU and not poikkeukset.get((f, fn), "").strip()]


def test_compare_digest_vain_yhdessa_paikassa():
    kutsut = _compare_digest_kutsut()
    assert any((f, fn) == SALLITTU for f, fn, _ in kutsut), (
        "secrets_equal ei enaa kutsu compare_digestia: portin oletus vanheni")
    vaarat = _vaarat(kutsut, POIKKEUKSET)
    assert not vaarat, (
        "Raaka compare_digest kaatuu ei-ASCII-merkkijonoihin (TypeError -> 500). "
        f"Kayta api.premium.secrets_equalia: {vaarat}")


@pytest.mark.parametrize("perustelu,vapautuu", [("", False), ("   ", False),
                                                ("bytes molemmin puolin", True)])
def test_poikkeus_vaatii_perustelun(perustelu, vapautuu):
    kutsu = [("api/esimerkki.py", "f", 1)]
    assert (not _vaarat(kutsu, {("api/esimerkki.py", "f"): perustelu})) is vapautuu
