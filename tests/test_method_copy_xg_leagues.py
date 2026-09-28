# -*- coding: utf-8 -*-
"""Menetelmacopyn xG-liigalista = koodin xG-liigat (28.9.2026, saanto 6a).

Sama vika loytyi 28.9 kaksi kertaa kasin: llms.txt ja predictions-FAQ
vaittivat xG-painotusta viidelle liigalle, kun koodissa se toimi vain
Valioliigalle (-FD-liigojen rivit olivat pd.NA:lla). Korjauksen jalkeen copy
oli hetken "vain Premier League", ja XG-NELJA-LIIGAA-UNDERSTAT palautti
neljä liigaa. Copy ja koodi eivat saa enaa ajautua erilleen kumpaankaan
suuntaan: lista luetaan koodista (Understat-liigat + fd_xg.UNDERSTAT_FOR_FD).
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path

from src.data.fd_xg import UNDERSTAT_FOR_FD

ROOT = Path(__file__).resolve().parents[1]
KAIKKI = {"Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Championship",
          "Eredivisie", "Primeira Liga", "Champions League"}


def _koodin_xg_liigat() -> set[str]:
    """Tuotteen liigat joiden ottelut saavat xG:n: Valioliiga (Understat-koodi
    suoraan) + jokainen -FD-liiga jolla on Understat-pari."""
    nimet = {"Premier League"}
    for fd_koodi in UNDERSTAT_FOR_FD:
        nimet.add(re.sub(r"^[A-Z]{3}-|-FD$", "", fd_koodi))
    return nimet


def _lista(lause: str) -> set[str]:
    return {n for n in KAIKKI if re.search(rf"\b{re.escape(n)}\b", lause)}


def test_koodin_lista_on_odotettu():
    assert _koodin_xg_liigat() == {"Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"}


def test_llms_txt_xg_liigat_ovat_koodin():
    rivi = next(r for r in (ROOT / "llms.txt").read_text(encoding="utf-8").splitlines()
                if r.startswith("- Method:"))
    m = re.search(r"per-match xG in the (.+?);", rivi)
    assert m, rivi
    assert _lista(m.group(1)) == _koodin_xg_liigat(), m.group(1)


def test_predictions_faq_xg_liigat_ovat_koodin_molemmissa():
    s = _html.unescape((ROOT / "predictions.html").read_text(encoding="utf-8"))
    osumat = re.findall(r"the xG those matches produced in the (.+?), and on goals alone", s)
    assert len(osumat) == 2, "JSON-LD + nakyva FAQ"
    for o in osumat:
        assert _lista(o) == _koodin_xg_liigat(), o
