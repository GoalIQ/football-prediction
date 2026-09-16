"""llms.txt:n esimerkkiottelusivu seuraa SITEMAPIA, ei levya eika kalenteria.

16.9.2026 tests.yml oli punainen 14.9 alkaen, ja saman paivan korjaus piti sen
punaisena: esimerkki luettiin levylta (`predictions/<slug>/*.html`, aakkosissa
ensimmainen = arsenal-vs-aston-villa), mutta `scripts/check_llms_txt_sync.py`
vaatii etta ottelusivuluokasta mainitaan jokin SITEMAPIN polku, ja sitemapissa
on vain 30 paivan ikkuna. Sivu oli olemassa muttei ikkunassa. Sama vikaluokka
kuin "lause ja luku eri lahteesta": kaksi lukijaa, kaksi lahdetta.

Invariantti mitataan vaiheissa (CLAUDE.md 6a (3)): ikkuna liukuu, esimerkki
liukuu mukana, portti pysyy vihreana - ja kontrolli todistaa etta portti
oikeasti punastuisi jos esimerkki jaisi jalkeen.
"""
from __future__ import annotations

import pathlib
import re

import scripts.build_prediction_pages as bp
import scripts.check_llms_txt_sync as g

GEN = "<!-- GEN:LLMS-START -->\n<!-- GEN:LLMS-END -->\n"
HUB = "https://goaliq.app/predictions/premier-league/"
FIXTURE_CLASS = "/predictions/<liiga>/<ottelu>"


def _llms(tmp_path, monkeypatch) -> pathlib.Path:
    f = tmp_path / "llms.txt"
    f.write_text("# GoalIQ\n" + GEN, encoding="utf-8")
    monkeypatch.setattr(bp, "LLMS_TXT", f)
    return f


def _run(f: pathlib.Path, urls: list[str]) -> str:
    bp.update_llms_txt({"PL": 3}, urls)
    return f.read_text(encoding="utf-8")


def test_esimerkki_on_sitemapin_ottelusivu_ja_portti_hyvaksyy(tmp_path, monkeypatch):
    f = _llms(tmp_path, monkeypatch)
    urls = [HUB, HUB + "brentford-vs-chelsea", HUB + "tottenham-vs-aston-villa"]
    txt = _run(f, urls)
    assert ("- Example fixture page live right now: "
            + HUB + "brentford-vs-chelsea") in txt
    assert g.undescribed_classes(txt, urls) == []


def test_levyn_sivu_ikkunan_ulkopuolella_ei_kelpaa(tmp_path, monkeypatch):
    """16.9 nahty muoto: levylla on aakkosissa ensimmainen sivu joka EI ole
    sitemapissa (kickoff yli 30 pv paassa). Sen ei saa paatya esimerkiksi."""
    d = tmp_path / "predictions" / "premier-league"
    d.mkdir(parents=True)
    (d / "arsenal-vs-aston-villa.html").write_text("x", encoding="utf-8")
    (d / "brentford-vs-chelsea.html").write_text("x", encoding="utf-8")
    monkeypatch.setattr(bp, "ROOT", tmp_path)
    f = _llms(tmp_path, monkeypatch)
    urls = [HUB, HUB + "brentford-vs-chelsea"]
    txt = _run(f, urls)
    assert "arsenal-vs-aston-villa" not in txt
    assert g.undescribed_classes(txt, urls) == []


def test_ikkunan_liukuminen_vaihtaa_esimerkin_ja_portti_pysyy_vihreana(tmp_path, monkeypatch):
    """Vaihe A: ikkunassa a. Vaihe B: a pelattu, ikkunassa b.

    Kontrolli ensin: A:n llms.txt B:n sitemapia vasten ON punainen - muuten
    testi ei todistaisi mekanismia (muisti: exit-koodi ei ole todiste).
    """
    f = _llms(tmp_path, monkeypatch)
    a = [HUB, HUB + "brentford-vs-chelsea"]
    b = [HUB, HUB + "liverpool-vs-everton"]
    txt_a = _run(f, a)
    assert g.undescribed_classes(txt_a, a) == []
    puna = g.undescribed_classes(txt_a, b)
    assert [x[0] for x in puna] == [FIXTURE_CLASS], puna
    txt_b = _run(f, b)
    assert "liverpool-vs-everton" in txt_b
    assert "brentford-vs-chelsea" not in txt_b
    assert g.undescribed_classes(txt_b, b) == []


def test_tyhja_ikkuna_ei_kirjoita_esimerkkirivia(tmp_path, monkeypatch):
    f = _llms(tmp_path, monkeypatch)
    txt = _run(f, [HUB])
    assert "Example fixture page" not in txt


def test_hub_ei_kelpaa_esimerkiksi():
    assert bp.example_fixture_url(["PL"], [HUB]) is None


def test_liigajarjestys_maaraa_esimerkin_ei_sitemapin_jarjestys():
    br = "https://goaliq.app/predictions/brasileirao/"
    urls = [br, br + "flamengo-rj-vs-corinthians",
            HUB, HUB + "brentford-vs-chelsea"]
    assert bp.example_fixture_url(["PL", "BSA"], urls) == HUB + "brentford-vs-chelsea"


def test_kutsupaikka_antaa_sitemapin_listan():
    """Funktio voi olla oikein ja kutsupaikka vaara (muisti: testi kutsuu
    funktiota, ei kutsupaikkaa). main() saa antaa update_llms_txt:lle vain
    saman listan joka menee sitemapiin."""
    src = pathlib.Path(bp.__file__).read_text(encoding="utf-8")
    kutsut = re.findall(r"update_llms_txt\(([^\n]*)\)", src)
    kutsut = [k for k in kutsut if not k.startswith("counts")]  # ei def-rivi
    assert kutsut, "main() ei kutsu update_llms_txt:ta"
    for k in kutsut:
        assert "sitemap_entries" in k, k
