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


# ---------------------------------------------------------------------------
# 30.8: ALASIVUJEN LUKUVAHTI + LOHKON RAJA
#
# Kaksi vikaa samassa portissa, molemmat "lapaisee liian helposti" -luokkaa:
#
# 1. Lukuvahti luki vain fpl.html:aa. Alasivun ankkuriin (#gw-xp) osoittava
#    rivi ohitettiin aanettomasti, eli uusi ilmaispinta sai luvata luvun jota
#    mikaan ei tarkistanut.
# 2. Lohkon LOPPU oli "seuraava h2 JOLLA ON id". Alasivulla muilla h2:illa ei
#    ole id:ta, joten #gw-xp-lohko nieli koko loppusivun: 12 496 merkkia ja
#    387 lukua. Vahti olisi hyvaksynyt kaytannossa minka tahansa luvun.
#
# 🔴 Ja korjaus tuotti kolmannen: `re.compile(r"<h2\b")` kirjoitettiin niin
#    etta `\b` muuttui BACKSPACE-merkiksi, jolloin regex ei osunut koskaan ja
#    lohko jai yha koko sivuksi. Sama vika kuin 30.8 vaiteportissa. Siksi
#    alla on testi joka mittaa ETTA RAJA OIKEASTI RAJAA, ei vain etta funktio
#    palauttaa jotain (muisti: kontrolli-lapaisi-tyhjana, fail-open-nielaisee-
#    mutaatiotestin).
# ---------------------------------------------------------------------------
import scripts.check_llms_txt_sync as g

_SUB_HTML = (
    '<html><body>'
    '<h2 id="gw-xp">Gameweek 3 expected points, top 20</h2>'
    '<p>At most 3 players per club.</p>'
    '<h2>Top 100 by expected points (of 515 players)</h2>'
    '<p>Ranked by total xP. 100 rows.</p>'
    '</body></html>'
)


def test_lohko_paattyy_seuraavaan_h2een_jolla_ei_ole_idta():
    b = g.block_text(_SUB_HTML, "gw-xp")
    assert "top 20" in b
    assert "Top 100" not in b, "lohko nieli seuraavan osion"


def test_lohkon_raja_ei_ole_inertti_regex():
    """Suora mittaus siita etta rajaus TOIMII, ei etta se on olemassa.

    Jos `H2_ANY_RE` on inertti (esim. backspace-merkki), tama kaatuu.
    """
    assert g.H2_ANY_RE.search('<h2 id="x">')
    assert g.H2_ANY_RE.search("<h2>")
    assert not g.H2_ANY_RE.search("<h20>"), "raja osuu vaaraan tagiin"
    assert not g.H2_ANY_RE.search("<h3>")


def test_alasivun_lukuvahti_nappaa_kattamattoman_luvun(monkeypatch):
    monkeypatch.setattr(g, "sub_page_html", lambda p: _SUB_HTML)
    llms = ("- [x](https://goaliq.app/fpl/expected-points#gw-xp): the top 100 "
            "for the next gameweek.")
    bad = g.unsupported_numbers_subpages(llms)
    assert [n for _, n, _ in bad] == ["100"]


def test_alasivun_lukuvahti_paastaa_katetun_luvun_lapi(monkeypatch):
    # Negatiivinen kontrolli: ilman tata vahti voisi kaatua aina.
    monkeypatch.setattr(g, "sub_page_html", lambda p: _SUB_HTML)
    llms = ("- [x](https://goaliq.app/fpl/expected-points#gw-xp): the top 20, "
            "at most 3 per club.")
    assert g.unsupported_numbers_subpages(llms) == []


def test_puuttuva_alasivu_ei_lapaise_hiljaa(monkeypatch):
    # Tarkistamaton vaite ei saa nayttaa tarkistetulta.
    monkeypatch.setattr(g, "sub_page_html", lambda p: "")
    llms = "- [x](https://goaliq.app/fpl/expected-points#gw-xp): the top 20."
    assert len(g.unsupported_numbers_subpages(llms)) == 1


def test_puuttuva_ankkuri_alasivulla_nostetaan(monkeypatch):
    monkeypatch.setattr(g, "sub_page_html", lambda p: _SUB_HTML)
    llms = "- [x](https://goaliq.app/fpl/expected-points#ei-ole): the top 20."
    bad = g.unsupported_numbers_subpages(llms)
    assert len(bad) == 1 and "ei ole lohkoa" in bad[0][2]


def test_paasivun_syvalinkkia_ei_kasitella_alasivuna():
    # `/fpl#anchor` kuuluu vanhalle vahdille; jos SUB_LINK_RE nappaisi senkin,
    # sama rivi tarkistettaisiin kahdesti ja vaarasta tiedostosta.
    assert g.sub_lines_by_page("- [x](https://goaliq.app/fpl#gw-calls): 20 rows.") == {}


def test_tuotannon_llms_ja_alasivut_ovat_synkassa():
    """Elava mittaus: sama tarkistus jonka CI ajaa, mutta testina."""
    llms = g.LLMS.read_text(encoding="utf-8")
    assert g.unsupported_numbers_subpages(llms) == []
