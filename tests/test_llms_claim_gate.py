# -*- coding: utf-8 -*-
"""LLMS-SYNC-CLAIM-GATE (30.8.2026): llms.txt:n VAITTEET, ei vain ankkurit.

Ankkuriportti mittaa etta lohko on KUVATTU. Se ei mittaa etta kuvaus on TOSI.
29.8 julkaisutarkistaja loysi llms.txt:n /fpl-osiosta viisi vikaa (liioiteltu
gradauskattavuus, sivun oman varauksen vastainen parafraasi, vanheneva luku
"all 20 teams", "logged and scored" ilman yhtaan gradattua rivia, kielletty
"rather than") ja KAIKKI menivat ankkuriportin lapi vihreana.

Jokaisella vahdilla on negatiivinen kontrolli: portti joka ei voi kaatua ei
mittaa mitaan (muisti: kontrolli-lapasi-tyhjana, gate-substring-osuma-on-sokea).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_llms_txt_sync import (  # noqa: E402
    banned_phrases, banned_phrases_elsewhere, block_text, free_claim_gating,
    llms_lines_by_anchor, unsupported_numbers)

PAGE = (
    '<h2 id="clean-sheets">Clean sheets</h2>'
    '<p>Model clean sheet probability for every team with a fixture.</p>'
    '<h2 id="fixture-difficulty">Fixture difficulty</h2>'
    '<table><caption>Easy fixtures (44% or more) are gold. '
    'Avg CS% is the average across that row.</caption></table>'
    '<h2 id="pro">Premium</h2><p>Sales.</p>'
)


def _llms(fpl_line):
    return ("# GoalIQ\n"
            "- [Clean sheets](https://goaliq.app/fpl#clean-sheets): model "
            "clean sheet probability. Free.\n"
            + fpl_line + "\n")


# ---------------------------------------------------------------------------
# 1. Lohkon rajaus
# ---------------------------------------------------------------------------
def test_block_text_stops_at_the_next_heading():
    blk = block_text(PAGE, "fixture-difficulty")
    assert "44%" in blk
    assert "Sales" not in blk, "lohko vuoti seuraavaan otsikkoon"
    assert "every team with a fixture" not in blk, "lohko vuoti edelliseen"


def test_block_text_unknown_anchor_is_empty():
    assert block_text(PAGE, "ei-ole") == ""


# ---------------------------------------------------------------------------
# 2. Lukuvaitteet
# ---------------------------------------------------------------------------
def test_number_not_on_the_page_is_caught():
    """Tasan se vika joka "all 20 teams" oli: luku jota sivu ei sano."""
    bad = unsupported_numbers(PAGE, _llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): covers all 20 teams."))
    assert [(a, n) for a, n, _ in bad] == [("fixture-difficulty", "20")], bad


def test_negative_control_number_that_is_on_the_page_passes():
    """Kontrolli: ilman tata portti voisi huutaa jokaisesta luvusta."""
    assert unsupported_numbers(PAGE, _llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): easy is 44% or more."
    )) == []


def test_negative_control_small_prose_numbers_are_not_claims():
    """1-9 on proosaa ("1 to 5", "three free"), ei mittaustulos.

    Ilman tata rajausta portti olisi kaynyt punaisena jokaisesta rivista
    eika kukaan olisi lukenut sita.
    """
    assert unsupported_numbers(PAGE, _llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): a 1 to 5 scale."
    )) == []


def test_negative_control_missing_block_is_left_to_the_anchor_gate():
    assert unsupported_numbers(PAGE, _llms(
        "- [X](https://goaliq.app/fpl#ei-ole): 99 things.")) == []


# ---------------------------------------------------------------------------
# 3. Hylatty sanamuoto
# ---------------------------------------------------------------------------
def test_banned_phrase_on_an_fpl_row_blocks():
    out = banned_phrases(_llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): model FDR rather "
        "than the official one."))
    assert out == [("fixture-difficulty", "rather than")], out


def test_negative_control_clean_fpl_row_passes():
    assert banned_phrases(_llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): the model FDR, "
        "not FPL's official one.")) == []


def test_phrase_outside_the_fpl_rows_is_a_note_not_a_block():
    txt = _llms("- [FDR](https://goaliq.app/fpl#fixture-difficulty): clean.")
    txt += "- [WC](https://goaliq.app/world-cup): a recap rather than a forecast.\n"
    assert banned_phrases(txt) == []
    assert [ph for _, ph in banned_phrases_elsewhere(txt)] == ["rather than"]


# ---------------------------------------------------------------------------
# 4. Free-vaite vs premium-gatetus
# ---------------------------------------------------------------------------
def test_free_claim_is_fine_when_the_page_has_no_premium_gating():
    assert free_claim_gating(PAGE, _llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): Free.")) == []


def test_free_claim_fails_if_the_block_becomes_premium_gated():
    """Fail-closed tulevaisuutta varten: jos gatetus ilmestyy, Free on vale."""
    gated = PAGE.replace('<h2 id="fixture-difficulty">',
                         '<div class="is-premium"><h2 id="fixture-difficulty">')
    assert free_claim_gating(gated, _llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): Free.")) == [
        "clean-sheets", "fixture-difficulty"]


def test_negative_control_no_free_claim_no_failure():
    gated = PAGE.replace('<h2 id="fixture-difficulty">',
                         '<div class="is-premium"><h2 id="fixture-difficulty">')
    txt = ("- [FDR](https://goaliq.app/fpl#fixture-difficulty): Premium only.\n")
    assert free_claim_gating(gated, txt) == []


# ---------------------------------------------------------------------------
# 5. Rivien poiminta
# ---------------------------------------------------------------------------
def test_lines_are_grouped_by_anchor():
    got = llms_lines_by_anchor(_llms(
        "- [FDR](https://goaliq.app/fpl#fixture-difficulty): x."))
    assert set(got) == {"clean-sheets", "fixture-difficulty"}


# ---------------------------------------------------------------------------
# 6. Sivuluokkaportti (GEO): uusi sivutyyppi ei saa jaada nakymattomaksi
# ---------------------------------------------------------------------------
# Ankkuriportti kattaa /fpl-sivun lohkot, ei kokonaisia sivuTYYPPEJA. 30.8
# mitattiin etta sitemapissa on 401 URLia ja /faq ei ollut kuvattu lainkaan,
# vaikka se on kuudella kysymyksella ja FAQPage-skeemalla juuri se sivutyyppi
# jota tekoalykoneet siteeraavat.
from scripts.check_llms_txt_sync import (  # noqa: E402
    CLASS_EXEMPT, undescribed_classes, url_class)


def test_url_class_collapses_templated_paths():
    """349 ottelusivua on YKSI luokka, ei 349 vaadittua rivia."""
    assert url_class("/predictions/premier-league/a-vs-b") == "/predictions/<liiga>/<ottelu>"
    assert url_class("/fpl/club/arsenal") == "/fpl/club/<x>"
    assert url_class("/fpl/note/some-slug") == "/fpl/note/<x>"


def test_url_class_keeps_real_pages_separate():
    """Kontrolli: ilman tata kaikki romahtaisi yhdeksi luokaksi ja portti
    olisi aina vihrea."""
    assert url_class("/faq") == "/faq"
    assert url_class("/fpl/points") == "/fpl/points"
    assert url_class("/fpl") == "/fpl"
    assert url_class("/") == "/"


def test_a_page_class_nobody_describes_is_caught():
    """Tasan se vika joka /faq oli."""
    llms = "- [FPL](https://goaliq.app/fpl): tools.\n"
    urls = ["https://goaliq.app/fpl", "https://goaliq.app/faq"]
    out = undescribed_classes(llms, urls)
    assert [(c, n) for c, n, _ in out] == [("/faq", 1)], out


def test_negative_control_described_class_passes():
    """Ilman tata portti huutaisi kaikesta."""
    llms = "- [FPL](https://goaliq.app/fpl)\n- [FAQ](https://goaliq.app/faq)\n"
    urls = ["https://goaliq.app/fpl", "https://goaliq.app/faq"]
    assert undescribed_classes(llms, urls) == []


def test_one_example_covers_a_whole_templated_class():
    """Kuvion kuvaaminen KERRAN riittaa; 349 rivia olisi vaara korjaus."""
    llms = "Club pages: https://goaliq.app/fpl/club/arsenal, /liverpool and so on.\n"
    urls = ["https://goaliq.app/fpl/club/arsenal",
            "https://goaliq.app/fpl/club/liverpool",
            "https://goaliq.app/fpl/club/chelsea"]
    assert undescribed_classes(llms, urls) == []


def test_every_exemption_carries_a_reason():
    """Poikkeus on tietoinen paatos, ei oletus."""
    for luokka, syy in CLASS_EXEMPT.items():
        assert isinstance(syy, str) and len(syy) > 10, luokka
