"""Vie render.yaml:n buildFilterin LIVE-palveluun ja mittaa ajautuman.

🔴 MIKSI (27.9.2026): Renderin build-minuutit loppuivat 27.9 06:56 UTC, ja
kuusi deployta peraikkain peruuntui ("workspace has run out of build pipeline
minutes"). Syy: `render.yaml`:n buildFilter korjattiin 1.9 (809d2fafb,
"buildFilter vuoti, 924 deployta kuukaudessa 500 min kiintiolla"), mutta
palvelu EI ole blueprint-synkronoitu, joten tiedosto ei koskaan vaikuttanut
mihinkaan. Live-palvelun `buildFilter` oli `None` koko syyskuun: 1 091
deployta 1.-27.9, joista 980 bottien datacommiteista joita suodatin olisi
ohittanut. Portti (tests/test_render_build_filter.py) mittasi TIEDOSTOA,
ei tuotantoa.

Tama skripti on se puuttuva silta: yksi lahde (render.yaml), yksi kirjoittaja
(tama), ja ajautuma mitataan livesta. Kaytto:

    python -m scripts.render_sync_build_filter            # vain mittaus, exit 1 jos ajautunut
    python -m scripts.render_sync_build_filter --apply    # kirjoittaa, mittaa jalkeen

Avain luetaan .env:sta (RENDER_API_KEY), ei CI:hin (muisti: admin-endpoint,
ei service-avainta CI:hin). --apply tallentaa ennen-kuvan (muisti: tuotannon
ohjauspinta, ennen-kuva ensin) ja koskee VAIN buildFilter-kenttaan.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ID = "srv-d7u5fgnlk1mc73ec6rv0"  # goaliq-api
API = f"https://api.render.com/v1/services/{SERVICE_ID}"


def desired_filter(render_yaml: Path = ROOT / "render.yaml") -> dict:
    """render.yaml:n goaliq-api-palvelun buildFilter Renderin API-muodossa."""
    cfg = yaml.safe_load(render_yaml.read_text(encoding="utf-8"))
    svc = next(s for s in cfg["services"] if s.get("name") == "goaliq-api")
    bf = svc.get("buildFilter") or {}
    return {"paths": list(bf.get("paths") or []),
            "ignoredPaths": list(bf.get("ignoredPaths") or [])}


def normalize(bf: dict | None) -> dict:
    bf = bf or {}
    return {"paths": sorted(bf.get("paths") or []),
            "ignoredPaths": sorted(bf.get("ignoredPaths") or [])}


def drift(live: dict | None, want: dict) -> list[str]:
    """Tyhja lista = live vastaa render.yaml:ia. Muuten ihmisluettavat erot."""
    a, b = normalize(live), normalize(want)
    out = []
    for k in ("paths", "ignoredPaths"):
        puuttuu = sorted(set(b[k]) - set(a[k]))
        ylim = sorted(set(a[k]) - set(b[k]))
        if puuttuu:
            out.append(f"{k}: livesta puuttuu {puuttuu}")
        if ylim:
            out.append(f"{k}: livessa ylimaaraista {ylim}")
    return out


def _env_file() -> Path:
    """Worktreessa .env on paatyopuussa (gitignoroitu, ei kopioida)."""
    if (ROOT / ".env").exists():
        return ROOT / ".env"
    import subprocess
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return Path(common).parent / ".env"


def _key() -> str:
    for ln in _env_file().read_text(encoding="utf-8").splitlines():
        if ln.startswith("RENDER_API_KEY="):
            return ln.split("=", 1)[1].strip()
    sys.exit("RENDER_API_KEY puuttuu .env:sta")


def _req(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {_key()}", "Accept": "application/json",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    want = desired_filter()
    before = _req("GET", API)
    ero = drift(before.get("buildFilter"), want)
    print(f"autoDeploy={before.get('autoDeploy')} trigger={before.get('autoDeployTrigger')}")
    if not ero:
        print("OK: live buildFilter == render.yaml")
        return 0
    print("AJAUTUNUT:\n  " + "\n  ".join(ero))
    if not args.apply:
        return 1
    leima = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    kuva = ROOT / "outputs" / f"render-service-before-{leima}.json"
    kuva.parent.mkdir(parents=True, exist_ok=True)
    kuva.write_text(json.dumps(before, indent=2), encoding="utf-8")
    print(f"ennen-kuva: {kuva.relative_to(ROOT)}")
    _req("PATCH", API, {"buildFilter": want})
    after = _req("GET", API)
    ero2 = drift(after.get("buildFilter"), want)
    muut = [k for k in ("autoDeploy", "autoDeployTrigger", "branch", "rootDir", "suspended")
            if before.get(k) != after.get(k)]
    if muut:
        print(f"🔴 MUUT KENTAT MUUTTUIVAT: {muut}")
        return 1
    if ero2:
        print("🔴 PATCHin jalkeen yha ajautunut:\n  " + "\n  ".join(ero2))
        return 1
    print("OK: kirjoitettu ja mitattu, live buildFilter == render.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
