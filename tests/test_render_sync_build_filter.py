"""render.yaml -> live Render -silta (27.9.2026).

`tests/test_render_build_filter.py` mittaa TIEDOSTOA. Se oli vihrea koko
syyskuun, kun live-palvelun buildFilter oli `None` ja 980 bottikommittia
deployasi (build-minuutit loppuivat 27.9). Nama testit vartioivat siltaa:
suodatin luetaan render.yaml:sta eika kirjoiteta kasin, ajautuma nakyy
molempiin suuntiin, ja --apply koskee VAIN buildFilter-kenttaan.
"""
from __future__ import annotations

import yaml

import scripts.render_sync_build_filter as R

ROOT = R.ROOT


def test_desired_filter_is_render_yaml():
    cfg = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    svc = next(s for s in cfg["services"] if s["name"] == "goaliq-api")
    want = R.desired_filter()
    assert want["ignoredPaths"] == svc["buildFilter"]["ignoredPaths"]
    # Bottien kolme paalahdetta (1.9 mittaus) ovat suodattimessa.
    for g in ("data/**", "fpl/**", "*.html"):
        assert g in want["ignoredPaths"]


def test_drift_both_directions():
    want = {"paths": [], "ignoredPaths": ["data/**", "*.html"]}
    assert R.drift(want, want) == []
    # Jarjestys ei ole ajautumaa.
    assert R.drift({"ignoredPaths": ["*.html", "data/**"]}, want) == []
    # 27.9 tuotannon tila: None.
    ero = R.drift(None, want)
    assert ero and "puuttuu" in ero[0]
    # Toinen suunta: livessa jotain mita render.yaml ei sano.
    ero = R.drift({"ignoredPaths": ["data/**", "*.html", "src/**"]}, want)
    assert ero == ["ignoredPaths: livessa ylimaaraista ['src/**']"]


def test_apply_patches_only_build_filter(monkeypatch, tmp_path):
    want = R.desired_filter()
    tila = {"buildFilter": None, "autoDeploy": "yes", "autoDeployTrigger": "commit",
            "branch": "main", "rootDir": "", "suspended": "not_suspended"}
    kutsut = []

    def fake_req(method, url, body=None):
        kutsut.append((method, body))
        if method == "PATCH":
            tila["buildFilter"] = body["buildFilter"]
        return dict(tila)

    monkeypatch.setattr(R, "_req", fake_req)
    monkeypatch.setattr(R, "ROOT", tmp_path)
    assert R.main(["--apply"]) == 0
    patchit = [b for m, b in kutsut if m == "PATCH"]
    assert patchit == [{"buildFilter": want}]
    # Ennen-kuva tallessa ennen kirjoitusta.
    kuvat = list((tmp_path / "outputs").glob("render-service-before-*.json"))
    assert len(kuvat) == 1 and '"buildFilter": null' in kuvat[0].read_text(encoding="utf-8")


def test_measure_only_never_writes(monkeypatch):
    kutsut = []

    def fake_req(method, url, body=None):
        kutsut.append(method)
        return {"buildFilter": None}

    monkeypatch.setattr(R, "_req", fake_req)
    assert R.main([]) == 1  # ajautunut -> exit 1
    assert kutsut == ["GET"]
