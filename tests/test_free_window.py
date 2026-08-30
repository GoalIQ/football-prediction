# -*- coding: utf-8 -*-
"""Ilmaisikkuna: yksi lahde + portti kasin yllapidetyille pinnoille.

30.8.2026. "Premium is free on the web until the GW4 deadline on 12 September"
oli kovakoodattuna 15 kohtaan 8 tiedostossa, joista vain yksi on generoitu.
12.9.2026 klo 12:30 UTC jokainen niista alkaa vaittaa Premiumin olevan
ilmainen kun se ei ole (muisti: ehto-ei-vanhene-teksti-vanhenee).

Portit tassa:
  1. lause johdetaan aikaleimasta ja KATOAA itsestaan
  2. sivun lohko vaihtaa myos CTA:n ja hintalauseen
  3. kasin yllapidetty pinta joka lupaa ilmaista ikkunan sulkeuduttua KAATAA
Jokaisella negatiivinen kontrolli.
"""
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUKI = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
KIINNI = dt.datetime(2026, 9, 13, tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# 1. Lause katoaa itsestaan
# ---------------------------------------------------------------------------
def test_note_is_present_while_the_window_is_open():
    from src.free_window import note
    out = note(AUKI)
    assert "free on the web until" in out
    assert "12 September" in out


def test_note_is_empty_once_the_window_has_closed():
    """Tyhja on tarkoituksellinen: kutsupaikka upottaa paluuarvon sivulle."""
    from src.free_window import note
    assert note(KIINNI) == ""


def test_boundary_is_the_timestamp_not_the_day():
    from src.free_window import is_open, until
    u = until()
    assert is_open(u - dt.timedelta(seconds=1))
    assert not is_open(u)
    assert not is_open(u + dt.timedelta(seconds=1))


def test_naive_datetime_is_treated_as_utc_not_local():
    """Naiivi aika ei saa siirtaa rajaa kutsujan aikavyohykkeen mukaan."""
    from src.free_window import is_open, until
    u = until()
    assert not is_open(u.replace(tzinfo=None) + dt.timedelta(hours=1))


def test_day_label_is_derived_not_written_twice():
    """Kaksi kirjoitettua paivamaaraa ajautuisi erilleen."""
    from src.free_window import FREE_PREMIUM_UNTIL, day_label
    assert FREE_PREMIUM_UNTIL.startswith("2026-09-12")
    assert day_label() == "12 September"


# ---------------------------------------------------------------------------
# 2. Sivun lohko vaihtuu kokonaan
# ---------------------------------------------------------------------------
def test_page_block_drops_the_promise_and_the_free_cta_when_closed(monkeypatch):
    import src.free_window as fw
    from scripts.build_fpl_page import free_window_block
    monkeypatch.setattr(fw, "is_open", lambda now=None: False)
    monkeypatch.setattr(fw, "note", lambda now=None: "")
    out = free_window_block()
    assert "free on the web until" not in out
    assert "fpl-freewindow" not in out, "ilmais-CTA jai paalle"
    assert "Get Premium<" in out
    assert "After 12 September" not in out, "menneessa muodossa oleva hintalause"


def test_negative_control_open_window_still_shows_everything(monkeypatch):
    """Ilman tata edellinen lapaisisi toteutuksella joka palauttaa aina tyhjan."""
    import src.free_window as fw
    from scripts.build_fpl_page import free_window_block
    monkeypatch.setattr(fw, "is_open", lambda now=None: True)
    out = free_window_block()
    assert "fpl-freewindow" in out
    assert "Get Premium free" in out
    assert "After 12 September" in out


# ---------------------------------------------------------------------------
# 3. Portti kasin yllapidetyille pinnoille
# ---------------------------------------------------------------------------
def test_gate_fails_when_a_surface_still_promises_after_the_window(tmp_path,
                                                                  monkeypatch):
    import scripts.check_free_window as g
    monkeypatch.setattr(g, "is_open", lambda now=None: False)
    f = tmp_path / "faq.html"
    f.write_text("<p>Premium is free on the web until the GW4 deadline.</p>",
                 encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    monkeypatch.setattr(g, "surfaces", lambda: [f])
    assert g.main() == 1


def test_negative_control_gate_passes_when_surfaces_are_clean(tmp_path,
                                                             monkeypatch):
    import scripts.check_free_window as g
    monkeypatch.setattr(g, "is_open", lambda now=None: False)
    f = tmp_path / "faq.html"
    f.write_text("<p>Premium is 25 EUR a year.</p>", encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    monkeypatch.setattr(g, "surfaces", lambda: [f])
    assert g.main() == 0


def test_gate_fails_closed_when_it_finds_no_surfaces(monkeypatch):
    """Tyhja korpus ei ole 'kaikki kunnossa' (muisti: kontrolli-lapasi-tyhjana)."""
    import scripts.check_free_window as g
    monkeypatch.setattr(g, "surfaces", lambda: [])
    assert g.main() == 1


def test_claim_is_recognised_in_several_wordings():
    """Sama vaite on kirjoitettu useassa muodossa eri pinnoille."""
    import scripts.check_free_window as g
    for s in ("free on the web until the GW4 deadline",
              "Premium is free until the GW4 deadline on 12 September",
              "there is nothing to pay for GW1 to GW3"):
        assert g.CLAIM_RE.search(s), s


def test_negative_control_unrelated_free_text_does_not_match():
    """Ilman tata edellinen lapaisisi kuviolla joka osuu sanaan 'free'."""
    import scripts.check_free_window as g
    for s in ("Free, no sign-in", "the free expected points table",
              "Create a free account"):
        assert not g.CLAIM_RE.search(s), s
