# -*- coding: utf-8 -*-
"""YKSI julkinen tarkkuusluku joka pinnalla (ulkoasuohjelma WP2, 1.11.2026).

MITATTU 1.11.2026 samana paivana neljä lukua: landingin hero 52.5 % / 988,
landingin hintapaneeli 51.9 % / 932, SPA 51.9 % / 931, record-sivu
"52 % / 987". Juurisyy:

  (1) KAKSI RAJAUSTA. Hero-chip, ticker ja proof-lause lukivat `all_time`a
      (sisaltaa 56 MM-kisojen ennustetta erillisesta maajoukkuemallista),
      hintapaneeli (ACC-TRUST), /fpl-lauseet, record-sivun summarivi ja SPA
      `by_model.club`ia. Jokainen pinta valitsi itse.
  (2) KAKSI HETKEA. Hub on paistettu kuva kunkin putkiajon artefaktista
      (1.11 klo 00:53 987/931, klo 03:53 988/932); SPA lukee elavaa API:a.
      "52 %" oli raportin oma pyoristys 52.5 %:sta.

KORJAUS (CLAUDE.md 6a, mekanismi 1): `src.models.accuracy.public_headline`
paattaa rajauksen (seuramalli) ja muotoilun (`fmt_pct`, Decimal half-up =
SPA:n fmtPct). Hub-builder kutsuu sita, `/api/accuracy` palauttaa sen
kentassa `headline`, SPA nayttaa `pct_text`:n sellaisenaan. Koko lokin
summa (52.5 % / 988) jaa vain Dataset-JSON-LD:hen nimettyna eri rajauksena.

Tama portti rakentaa sivut OIKEALLA builderilla ja lukee jokaisen
otsikkopinnan luvun generoidusta HTML:sta. Jos kaksi pintaa eroaa, testi
kaatuu ja nimeaa pinnan.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from scripts import build_fpl_page as b
from src.models import accuracy as acc
from src.models.fmt import fmt_pct

ROOT = Path(__file__).resolve().parents[1]

_PCT = re.compile(r"(?<![\d.#&])(\d{1,3}(?:\.\d+)?%)")
_N_COMPLETED = re.compile(r"(?<![\d.])(\d[\d,]*) completed")


def _block(html: str, key: str) -> list[str]:
    return re.findall(rf"<!-- GEN:{key}-START -->(.*?)<!-- GEN:{key}-END -->", html, re.S)


def _pair(text: str) -> tuple[str, int] | None:
    p, n = _PCT.search(text), _N_COMPLETED.search(text)
    if not p or not n:
        return None
    return p.group(1), int(n.group(1).replace(",", ""))


def surface_pairs(index_html: str, predictions_html: str, fpl_html: str) -> dict[str, tuple]:
    """Pinta -> (prosentti, n) jokaiselta otsikkopinnalta jolla luku nakyy."""
    out: dict[str, tuple] = {}
    for name, html in (("index", index_html), ("predictions", predictions_html)):
        for key in ("ACC-CHIP", "ACC-PROOF", "ACC-TRUST", "ACC-TICKER"):
            for i, blk in enumerate(_block(html, key)):
                out[f"{name} {key}#{i}"] = _pair(blk)
    # record-sivun summarivi "All club matches  51.9%  484 of 932"
    m = re.search(r'bycomp-name">All club matches</span><span class="bycomp-pct">([^<]+)</span>'
                  r'<span class="bycomp-n">\d+ of (\d+)</span>', predictions_html)
    out["predictions ACC-RECORD All club matches"] = (m.group(1), int(m.group(2))) if m else None
    # /fpl: track record -lause (FAQ + sivu)
    m = re.search(r"Across the (\d+) completed club matches, it called the result correctly "
                  r"in (\d+(?:\.\d+)?%) of them", fpl_html)
    out["fpl track record sentence"] = (m.group(2), int(m.group(1))) if m else None
    return out


def mismatches(pairs: dict[str, tuple], head: dict) -> list[str]:
    want = (head["pct_text"], head["n"])
    return [f"{k}: {v} != {want}" for k, v in pairs.items() if v != want]


# ---------------------------------------------------------------------------
# Lukija
# ---------------------------------------------------------------------------
def _agg(club=(932, 484, 0.5193), all_time=(988, 519, 0.5253)):
    a = {"updated_at": "2026-11-01T09:52:07+00:00",
         "all_time": {"n": all_time[0], "correct_1x2": all_time[1], "pct_1x2": all_time[2]}}
    if club:
        a["by_model"] = {"club": {"n": club[0], "correct_1x2": club[1], "pct_1x2": club[2]}}
    return a


def test_lukija_valitsee_seuramallin_ja_muotoilee_jaetulla_muotoilijalla():
    h = acc.public_headline(_agg())
    assert h["scope"] == "club"
    assert (h["n"], h["correct"], h["pct_text"]) == (932, 484, "51.9%")
    assert h["label"] == "completed club matches"
    # Tasapiste: sama muotoilija kuin muualla (half-up), ei oma pyoristys.
    h2 = acc.public_headline(_agg(club=(400, 193, 0.4825)))
    assert h2["pct_text"] == fmt_pct(0.4825 * 100)


def test_lukija_vanha_skeema_nimeaa_rajauksen_eika_kutsu_sita_seuramalliksi():
    h = acc.public_headline(_agg(club=None))
    assert h["scope"] == "all"
    assert (h["n"], h["pct_text"]) == (988, "52.5%")
    assert h["label"] == "completed matches, all competitions"


def test_lukija_ilman_gradattuja_on_none():
    assert acc.public_headline(acc.empty_aggregate()) is None
    assert acc.public_headline({}) is None


# ---------------------------------------------------------------------------
# Portti: oikea builder, generoidut sivut, jokainen otsikkopinta
# ---------------------------------------------------------------------------
def _erotteleva_pct(club_pct: float) -> float:
    """Synteettinen all_time, joka ei voi tormata sivun muihin lukuihin.

    2.11.2026: seuramalli 0.5269 + 0.0731 = 0.6000 -> "60%", ja sama
    merkkijono esiintyy predictions-sivulla 55 kertaa ottelun
    todennakoisyytena. Portti oli punainen kaikissa PR:issa (#78, #79)
    ilman yhtaan muutosta copyyn, ja se olisi tormannyt uudelleen aina kun
    seuramallin luku ajautuu tasalukuun. Siirretaan offsettia, kunnes luku
    on desimaalinen eika esiinny committattujen sivujen tekstissa."""
    pohja = "".join((ROOT / f).read_text(encoding="utf-8")
                    for f in ("index.html", "predictions.html", "fpl.html"))
    off = 0.0731
    for _ in range(200):
        cand = round(club_pct + off, 4)
        s = fmt_pct(cand * 100)
        if "." in s and s not in pohja:
            return cand
        off += 0.0007
    raise AssertionError("erottelevaa lukua ei loytynyt 200 yrityksella")


@pytest.fixture
def built(tmp_path, monkeypatch):
    """Aja update_index + update_predictions + render_page kopioille.

    Artefaktia muokataan niin etta `all_time` eroaa seuramallista selvasti:
    vanha koodi (hero luki all_timea) tuottaisi silloin toisen luvun, joten
    portti erottelee eika ole vihrea sattumalta."""
    fpl, agg = b.load_data()
    agg = json.loads(json.dumps(agg))
    club = agg["by_model"]["club"]
    agg["all_time"]["n"] = club["n"] + 77
    agg["all_time"]["pct_1x2"] = _erotteleva_pct(club["pct_1x2"])
    c = b.build_context(fpl, agg)
    xp = b._load_json(b.XP_PATH)
    idx = tmp_path / "index.html"
    pred = tmp_path / "predictions.html"
    shutil.copy(ROOT / "index.html", idx)
    shutil.copy(ROOT / "predictions.html", pred)
    monkeypatch.setattr(b, "INDEX_PATH", idx)
    monkeypatch.setattr(b, "PREDICTIONS_PATH", pred)
    b.update_index(c, xp)
    b.update_predictions(c, b.load_log())
    fpl_html = b.render_page(c, xp)
    return {
        "head": acc.public_headline(agg),
        "agg": agg,
        "index": idx.read_text(encoding="utf-8"),
        "predictions": pred.read_text(encoding="utf-8"),
        "fpl": fpl_html,
    }


def test_jokainen_otsikkopinta_nayttaa_saman_luvun(built):
    pairs = surface_pairs(built["index"], built["predictions"], built["fpl"])
    # Jokainen pinta loytyi (puuttuva pinta ei saa olla hiljaa vihrea).
    assert all(v is not None for v in pairs.values()), pairs
    assert len([k for k in pairs if "TICKER" in k]) == 2
    assert not mismatches(pairs, built["head"]), mismatches(pairs, built["head"])


def test_koko_lokin_summa_vain_nimettyna_dataset_kuvauksessa(built):
    """Eri rajaus saa nakya vain nimettyna (WP2): Dataset kuvaa koko lokin."""
    at = built["agg"]["all_time"]
    all_pct = fmt_pct(at["pct_1x2"] * 100)
    for name in ("index", "predictions", "fpl"):
        html = built[name]
        ld = " ".join(re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S))
        nakyva = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        # 2.11.2026: HTML-kommentti ei ole nakyvaa tekstia. Synteettinen
        # all_time (seuramalli + 7.31 pp) osui 60 %:iin, ja indexin
        # kommentissa lukee "60% of visitors are on a phone" -> vaara
        # punainen kaikissa PR:issa (#78, #79) ilman muutosta copyyn.
        nakyva = re.sub(r"(?s)<!--.*?-->", " ", nakyva)
        # count() eika `not in`: epaonnistuva `not in` saa pytestin laskemaan
        # diffin koko sivusta (1,1 Mt), ja ajo jumittaa minuuteiksi.
        osumat = nakyva.count(all_pct)
        assert osumat == 0, f"{name}: koko lokin {all_pct} nakyvassa tekstissa ({osumat} kertaa)"
        if name != "fpl" or "Dataset" in ld:
            # Julkaisutarkistaja 1.11 (PR #75): rajaus ENNEN lukua, jottei koko
            # lokin luku lue maajoukkuemallin lukuna ("N national-team matches
            # from a separate model: X%" -> X luettiin maajoukkueiden luvuksi).
            extra = at["n"] - built["head"]["n"]
            assert (f"All competitions, including {extra} national-team matches from a "
                    f"separate model: {all_pct} across {at['n']} completed matches.") in ld, name
            assert "also holds" not in ld, name


def test_negatiivinen_kontrolli_vanha_hero_kaatuisi(built):
    """Palauta 1.11:n vika (chip luki all_timea) -> vertailun on kaaduttava."""
    at = built["agg"]["all_time"]
    vanha_chip = (f'<div class="num">{fmt_pct(at["pct_1x2"] * 100)}</div>'
                  f'<div class="lbl">result accuracy across {at["n"]} completed matches, '
                  f"all competitions</div>")
    rikki = re.sub(r"(<!-- GEN:ACC-CHIP-START -->).*?(<!-- GEN:ACC-CHIP-END -->)",
                   lambda m: m.group(1) + vanha_chip + m.group(2), built["index"], flags=re.S)
    virheet = mismatches(surface_pairs(rikki, built["predictions"], built["fpl"]), built["head"])
    assert virheet and all("index ACC-CHIP" in v for v in virheet), virheet


# ---------------------------------------------------------------------------
# Julkaistut tiedostot ja API
# ---------------------------------------------------------------------------
def test_repon_sivut_kantavat_artefaktin_luvun():
    """Committattu index/predictions/fpl samaa lukua kuin committattu
    data/accuracy.json. Bot paistaa sivut samassa ajossa kuin artefaktin."""
    head = acc.public_headline(json.loads((ROOT / "data" / "accuracy.json").read_text(encoding="utf-8")))
    pairs = surface_pairs(*((ROOT / f).read_text(encoding="utf-8")
                            for f in ("index.html", "predictions.html", "fpl.html")))
    assert all(v is not None for v in pairs.values()), pairs
    assert not mismatches(pairs, head), mismatches(pairs, head)


def test_api_palauttaa_saman_lukijan_tuloksen(client):
    r = client.get("/api/accuracy")
    assert r.status_code == 200
    assert r.json()["headline"] == acc.public_headline(acc.load_aggregate())


def test_spa_nayttaa_api_n_valmiin_merkkijonon():
    """SPA ei valitse rajausta eika muotoile prosenttia (Provenance.svelte)."""
    src = (ROOT / "web/pro-spa/src/lib/components/Provenance.svelte").read_text(encoding="utf-8")
    koodi = "\n".join(r.split("//", 1)[0] for r in src.split("</script>")[0].splitlines())
    assert "acc?.headline" in koodi and "h.pct_text" in koodi
    assert "fmtPct" not in koodi and "by_model" not in koodi and "all_time" not in koodi
