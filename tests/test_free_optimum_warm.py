"""THIS-WEEK-LATAUS-HIDAS (26.9.2026): vapaa optimi lammitetaan kaynnistyksessa.

Villen havainto 25.9: "miksi squadin loading kestaa taas ... this weekissa".
Mitattu 26.9: tuotannon ensimmainen rate-team-vastaus deployn jalkeen 4,9 s,
lammin 0,12 s. Kylma aika on `build_optimal_squad` (paikallisesti 3,4 s),
joka laskettiin pyynnon sisalla, koska valimuisti elaa prosessin muistissa ja
Render kaynnistaa prosessin uudelleen jokaisella mainin pushilla (49-90
vuorokaudessa).

Portit (saanto 6a):
  1. Lammitys osuu TASMALLEEN siihen avaimeen jota pyynnot hakevat. Muuten
     lammitys olisi olemassa mutta jokainen deploy olisi silti kylma.
  2. Kukaan kutsuja ei muodosta avainta itse (AST-kavely, poikkeuslista
     perusteluineen).
  3. Rinnakkaiset kutsut laskevat optimin kerran.
  4. Kaynnistys lammittaa Renderissa, ei kaadu virheeseen eika jaa odottamaan
     yli rajan, ja koukku on rekisteroity ENNEN mallien lammitysta.
"""
from __future__ import annotations

import ast
import threading
import time
from pathlib import Path

import pytest

import src.models.fpl_rate_team as rt
from tests.test_fpl_rate_team import _mock_fpl  # noqa: F401 (autouse-fixture)

ROOT = Path(__file__).resolve().parents[1]


def _kielletty_laskenta(*_a, **_k):
    raise AssertionError("vapaa optimi laskettiin pyynnossa lammityksen jalkeen")


# ---------------------------------------------------------------------------
# 1. Lammitys osuu pyynnon avaimeen
# ---------------------------------------------------------------------------

def test_lammitetty_optimi_on_se_jonka_rate_team_hakee(monkeypatch):
    mittaus = rt.warm_free_optimum()
    assert mittaus["key"] == "test-fixture"
    monkeypatch.setattr(rt, "build_optimal_squad", _kielletty_laskenta)
    out = rt.rate_team(entry=424242)
    assert out["rating"]["percentile"] >= 0


def test_lammitetty_optimi_kelpaa_model_squadille_ja_fit_checkerille(client, monkeypatch):
    import src.models.fpl_fit as fit

    rt.warm_free_optimum()
    monkeypatch.setattr(rt, "build_optimal_squad", _kielletty_laskenta)
    r = client.get("/api/fantasy/model-squad")
    assert r.status_code == 200, r.text
    # Fit checkerin lukittu rakennus on oma laskentansa (ei valimuistissa);
    # vertailukohta (vapaa optimi) tulee lammitetysta.
    out = fit.fit_squad([25])
    assert "delta" in out or "xi_xp" in out or out


# ---------------------------------------------------------------------------
# 2. Avain muodostetaan yhdessa paikassa
# ---------------------------------------------------------------------------

# Kutsupaikat jotka saavat valittaa avaimen muuttujana. Jokainen rivi tarvitsee
# perustelun: tyhja perustelu ei vapauta (testi kaatuu alla).
_AVAIN_POIKKEUKSET = {
    ("src/models/fpl_rate_team.py", "optimal_budget_team_xp"): (
        "lapivienti: saa avaimen kutsujalta (rate_team) joka muodostaa sen "
        "free_optimum_keylla"
    ),
    ("scripts/render_projected_xi_card.py", "free_hit_xi"): (
        "offline-kortti, oma prosessi: pooli on YHDEN kierroksen (_xi_pool), "
        "ei API:n horisonttipooli, joten sen ei kuulu jakaa avainta "
        "API:n vertailukohdan kanssa"
    ),
}

_OPTIMIFUNKTIOT = {"free_optimum", "optimal_budget_team_xp"}


def _kutsun_nimi(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _avainkutsut():
    for kansio in ("api", "src", "scripts"):
        for polku in sorted((ROOT / kansio).rglob("*.py")):
            rel = polku.relative_to(ROOT).as_posix()
            puu = ast.parse(polku.read_text(encoding="utf-8"))
            for funktio in ast.walk(puu):
                if not isinstance(funktio, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(funktio):
                    if isinstance(node, ast.Call) and _kutsun_nimi(node) in _OPTIMIFUNKTIOT:
                        yield rel, funktio.name, node


def test_kukaan_kutsuja_ei_muodosta_valimuistiavainta_itse():
    rikkeet = []
    loydetyt = 0
    for rel, funktio, node in _avainkutsut():
        loydetyt += 1
        avain = node.args[1] if len(node.args) > 1 else next(
            (k.value for k in node.keywords if k.arg == "cache_key"), None)
        ok = (isinstance(avain, ast.Call) and _kutsun_nimi(avain) == "free_optimum_key")
        if ok or (rel, funktio) in _AVAIN_POIKKEUKSET:
            continue
        rikkeet.append(f"{rel}:{node.lineno} ({funktio})")
    # Kavely loytaa oikeasti kutsupaikat (ei vihrea tyhjalla).
    assert loydetyt >= 5, loydetyt
    assert not rikkeet, (
        "Vapaan optimin avain muodostettu kutsupaikassa. Kayta "
        "free_optimum_key(xp_data), muuten kaynnistyksen lammitys osuu eri "
        "avaimeen: " + ", ".join(rikkeet))


def test_poikkeuksilla_on_perustelu():
    for kohta, perustelu in _AVAIN_POIKKEUKSET.items():
        assert perustelu.strip(), kohta


# ---------------------------------------------------------------------------
# 3. Yksi laskenta kerrallaan
# ---------------------------------------------------------------------------

def test_rinnakkaiset_kutsut_laskevat_optimin_kerran(monkeypatch):
    oikea = rt.build_optimal_squad
    laskut = []

    def hidas(pool, *a, **k):
        laskut.append(1)
        time.sleep(0.2)
        return oikea(pool, *a, **k)

    monkeypatch.setattr(rt, "build_optimal_squad", hidas)
    xp_data, _b, pool, _by = rt.build_context()
    avain = rt.free_optimum_key(xp_data)
    tulokset = []
    saikeet = [threading.Thread(target=lambda: tulokset.append(rt.free_optimum(pool, avain)))
               for _ in range(4)]
    for s in saikeet:
        s.start()
    for s in saikeet:
        s.join(10)
    assert len(tulokset) == 4
    assert len(laskut) == 1, f"optimi laskettiin {len(laskut)} kertaa"
    assert all(t is tulokset[0] for t in tulokset)


# ---------------------------------------------------------------------------
# 4. Kaynnistyskoukku
# ---------------------------------------------------------------------------

def _koukku():
    import api.main as m
    return m


def test_kaynnistys_lammittaa_renderissa(monkeypatch):
    m = _koukku()
    kutsut = []
    monkeypatch.setattr(rt, "warm_free_optimum", lambda: kutsut.append(1) or {"key": "k"})
    monkeypatch.setenv("RENDER", "true")
    m._warm_free_optimum()
    assert kutsut == [1]


def test_kaynnistys_ei_lammita_ilman_renderia(monkeypatch):
    m = _koukku()
    kutsut = []
    monkeypatch.setattr(rt, "warm_free_optimum", lambda: kutsut.append(1) or {})
    monkeypatch.delenv("RENDER", raising=False)
    m._warm_free_optimum()
    assert kutsut == []


def test_kaynnistys_ei_kaadu_lammityksen_virheeseen(monkeypatch, capsys):
    m = _koukku()

    def kaatuu():
        raise rt.RateTeamError(503, "FPL API is not responding right now.")

    monkeypatch.setattr(rt, "warm_free_optimum", kaatuu)
    monkeypatch.setenv("RENDER", "true")
    m._warm_free_optimum()  # ei nosta
    # Virhe kirjataan lokiin nimelta (Renderin lokista nakyy miksi lammitys
    # jai tekematta), eika se katoa saikeeseen.
    assert "RateTeamError" in capsys.readouterr().out


def test_kaynnistys_ei_odota_yli_rajan(monkeypatch):
    m = _koukku()
    vapauta = threading.Event()
    monkeypatch.setattr(rt, "warm_free_optimum", lambda: vapauta.wait(5) and {})
    monkeypatch.setattr(m, "_OPTIMUM_WARM_WAIT_SEC", 0.1)
    monkeypatch.setenv("RENDER", "true")
    t0 = time.time()
    m._warm_free_optimum()
    vapauta.set()
    assert time.time() - t0 < 2


def test_koukku_on_rekisteroity_ennen_mallien_lammitysta():
    m = _koukku()
    nimet = [getattr(f, "__name__", "") for f in m.app.router.on_startup]
    assert "_warm_free_optimum" in nimet, nimet
    assert "_warmup_default_models" in nimet, nimet
    assert nimet.index("_warm_free_optimum") < nimet.index("_warmup_default_models"), nimet


def test_kylma_optimi_on_mitattavasti_kallis_verrattuna_lampimaan(monkeypatch):
    """Perustelun tarkistus: portti on olemassa koska kylma polku laskee ja
    lammin ei. Jos valimuisti lakkaa toimimasta, lammitys on turha."""
    laskut = []
    oikea = rt.build_optimal_squad
    monkeypatch.setattr(rt, "build_optimal_squad",
                        lambda pool, *a, **k: laskut.append(1) or oikea(pool, *a, **k))
    rt.rate_team(entry=424242)
    rt.rate_team(entry=424242)
    assert len(laskut) == 1
