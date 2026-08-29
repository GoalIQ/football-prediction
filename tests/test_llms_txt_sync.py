"""Portti: /fpl-sivun sisaltolohkot on kuvattava llms.txt:ssa.

Loydos 29.8.2026: llms.txt kuvasi /fpl-sivua yha lauseella "clean sheet
probability and fixture difficulty" vaikka sivulla oli gw-calls-loki (28.8),
EO-by-tier ja xP-tarkkuuslohko (29.8). llms.txt on tunnettu copy-sync-sokea
piste: se ei nayta sivulta, joten pintakierros ei kay sita lapi.

Jokaisella vaitteella on negatiivinen kontrolli. Erikseen varmistetaan ettei
kontrolli lapaise tyhjana: jos ankkuriregex hajoaa, `page_anchors` palauttaa
tyhjan joukon ja portti muuttuisi triviaaliksi passiksi kaikilla syotteilla.
Siksi alla mitataan myos ETTA oikealta sivulta loytyy ankkureita.
"""

from __future__ import annotations

import pytest

from scripts.check_llms_txt_sync import (
    EXEMPT,
    LLMS,
    PAGE,
    llms_anchors,
    missing_anchors,
    page_anchors,
    stale_anchors,
)

HTML = '<section id="gw-calls"><h3>x</h3></section><section id="faq"></section>'


def test_kuvaamaton_lohko_loytyy():
    llms = "- [FPL](https://goaliq.app/fpl): yleiskuvaus.\n"
    assert missing_anchors(HTML, llms) == ["gw-calls"]


def test_kuvattu_lohko_lapaisee():
    llms = "- [Calls](https://goaliq.app/fpl#gw-calls): loki.\n"
    assert missing_anchors(HTML, llms) == []


def test_exempt_lohkoa_ei_vaadita():
    # #faq on EXEMPT-listalla, joten sita ei vaadita vaikka llms.txt ei mainitse.
    llms = "- [Calls](https://goaliq.app/fpl#gw-calls): loki.\n"
    assert "faq" not in missing_anchors(HTML, llms)


def test_exempt_ei_saa_niella_sisaltolohkoja():
    # Portin voi "korjata" exemptaamalla lohkon. Nama kolme eivat saa paatya sinne:
    # ne ovat juuri ne joita 29.8 puuttui.
    for anchor in ("gw-calls", "xp-accuracy", "eo-by-tier"):
        assert anchor not in EXEMPT


def test_vanhentunut_syvalinkki_loytyy():
    # Toinen suunta: lohko poistetaan sivulta, llms.txt jaa lupaamaan sita.
    llms = "- [Poistettu](https://goaliq.app/fpl#wildcard-lab): lohko.\n"
    assert stale_anchors(HTML, llms) == ["wildcard-lab"]


def test_kontrolli_ei_lapaise_tyhjana():
    # Jos regex hajoaa, kaikki testit ylla menisivat lapi tyhjilla joukoilla.
    html = PAGE.read_text(encoding="utf-8")
    anchors = page_anchors(html)
    assert len(anchors) >= 10, f"fpl.html:sta loytyi vain {len(anchors)} ankkuria"
    assert "gw-calls" in anchors


def test_oikea_repo_on_synkassa():
    html = PAGE.read_text(encoding="utf-8")
    llms = LLMS.read_text(encoding="utf-8")
    assert llms_anchors(llms), "llms.txt:ssa ei ole yhtaan /fpl-syvalinkkia"
    assert missing_anchors(html, llms) == []
    assert stale_anchors(html, llms) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
