"""SPL:n uutiskenttä ei tuo em/en dashia julkiseen artefaktiin (16.10.2026).

data/spl_xp_projections.json piti tests.yml:n punaisena 9.10. alkaen: SPL:n kaksikielinen uutinen
sisälsi en dashin. Artefaktiportti (test_public_json_copy) mittaa tuloksen vasta bottiajon jälkeen;
tämä mittaa tuottajan, myös kutsupaikan, ettei siivous jää funktioksi jota kukaan ei kutsu.
"""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.build_spl_xp import clean_news

LAHDE = Path(__file__).resolve().parents[1] / "scripts" / "build_spl_xp.py"


def test_viivat_vaihdetaan_teksti_sailyy():
    raaka = "Back Injury - Expected Return : End of Oct - إصابة في الظهر – العودة المتوقعة: نهاية أكتوبر"
    puhdas = clean_news(raaka)
    assert "–" not in puhdas and "—" not in puhdas
    assert "إصابة في الظهر - العودة" in puhdas
    assert clean_news(None) == ""


def test_artefaktin_news_kulkee_siivouksen_kautta():
    puu = ast.parse(LAHDE.read_text(encoding="utf-8"))
    news_arvot = [v for d in ast.walk(puu) if isinstance(d, ast.Dict)
                  for k, v in zip(d.keys, d.values)
                  if isinstance(k, ast.Constant) and k.value == "news"]
    assert news_arvot, "news-kenttää ei löytynyt"
    for v in news_arvot:
        assert isinstance(v, ast.Call) and getattr(v.func, "id", None) == "clean_news", ast.dump(v)
