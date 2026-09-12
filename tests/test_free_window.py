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


# ---------------------------------------------------------------------------
# 4. SPA:n vartioitu teksti ei ole vanheneva vaite
# ---------------------------------------------------------------------------
def test_guarded_svelte_source_is_not_flagged(tmp_path):
    """SPA renderoi lupauksen {#if freePremiumWindowActive()} -ehdolla.

    Portti greppaa raakaa lahdekoodia eika nae ehtoa. Ilman tata rajausta se
    menisi 12.9 punaiseksi tiedostoista jotka ovat kunnossa, ja paivittain
    punainen portti tulee ohitetuksi.
    """
    import scripts.check_free_window as g
    f = tmp_path / "Paywall.svelte"
    f.write_text("{#if freePremiumWindowActive()}\n"
                 "<p>Premium is free until the GW4 deadline on 12 September.</p>\n"
                 "{/if}", encoding="utf-8")
    monkey = g.ROOT
    g.ROOT = tmp_path
    try:
        assert g.hits([f]) == []
        assert g.guarded_files([f]) == ["Paywall.svelte"]
    finally:
        g.ROOT = monkey


def test_negative_control_unguarded_svelte_is_flagged(tmp_path):
    """Kontrolli: ilman vartiota SPA-tiedostokin on vanheneva vaite."""
    import scripts.check_free_window as g
    f = tmp_path / "Loose.svelte"
    f.write_text("<p>Premium is free until the GW4 deadline on 12 September.</p>",
                 encoding="utf-8")
    old = g.ROOT
    g.ROOT = tmp_path
    try:
        assert len(g.hits([f])) == 1
    finally:
        g.ROOT = old


# ---------------------------------------------------------------------------
# 5. --fix siivoaa kasin yllapidetyt pinnat
# ---------------------------------------------------------------------------
def test_strip_claim_removes_only_the_sentence_that_carries_it():
    import scripts.check_free_window as g
    txt = ("GoalIQ is a model tool. Premium is free on the web until the GW4 "
           "deadline on 12 September. Cancel anytime.")
    out, n = g.strip_claim(txt)
    assert n == 1
    assert "free on the web until" not in out
    assert "GoalIQ is a model tool." in out, out
    assert "Cancel anytime." in out, out


def test_strip_claim_leaves_clean_text_untouched():
    """Kontrolli: ilman tata funktio voisi poistaa mita tahansa."""
    import scripts.check_free_window as g
    txt = "Premium is 25 EUR a year. Cancel anytime."
    out, n = g.strip_claim(txt)
    assert n == 0 and out == txt


def test_fix_cleans_static_files_once_the_window_has_closed(tmp_path,
                                                            monkeypatch):
    import scripts.check_free_window as g
    monkeypatch.setattr(g, "is_open", lambda now=None: False)
    f = tmp_path / "faq.html"
    f.write_text("<p>Hello. Premium is free on the web until the GW4 deadline "
                 "on 12 September. Bye.</p>", encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    muutetut = g.fix([f])
    assert muutetut == [("faq.html", 1)], muutetut
    after = f.read_text(encoding="utf-8")
    assert "free on the web until" not in after
    assert "Hello." in after and "Bye." in after


def test_negative_control_fix_does_nothing_while_the_window_is_open(tmp_path,
                                                                   monkeypatch):
    """🔴 Tarkein kontrolli: fix ei saa poistaa voimassa olevaa lupausta."""
    import scripts.check_free_window as g
    monkeypatch.setattr(g, "is_open", lambda now=None: True)
    f = tmp_path / "faq.html"
    alku = "<p>Premium is free on the web until the GW4 deadline on 12 September.</p>"
    f.write_text(alku, encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    assert g.fix([f]) == []
    assert f.read_text(encoding="utf-8") == alku


def test_fix_does_not_touch_guarded_spa_files(tmp_path, monkeypatch):
    import scripts.check_free_window as g
    monkeypatch.setattr(g, "is_open", lambda now=None: False)
    f = tmp_path / "Paywall.svelte"
    alku = ("{#if freePremiumWindowActive()}<p>Premium is free until the GW4 "
            "deadline on 12 September.</p>{/if}")
    f.write_text(alku, encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    assert g.fix([f]) == []
    assert f.read_text(encoding="utf-8") == alku


# ---------------------------------------------------------------------------
# 4. RAJAUSPORTTI: lupaus koskee vain webia (7.9.2026)
#
# Ilmaisikkuna koskee VAIN webia; mobiilissa Premium on kaupan tilaus koko
# ajan. Lupaus ilman "on the web" -rajausta on siis eri vaite kuin lupaus sen
# kanssa, ja se on epatosi puhelimessa lukevalle.
#
# 🔴 Mitattu 7.9: `index.html`in ilmaisikkunabandi - sivun ensimmainen
# elementti navin alla, eli suurimman liikenteen pinta - luki "Premium is
# free until the 12 September deadline" ilman rajausta, kun seitseman muuta
# pintaa sanoivat "on the web".
#
# Vanha portti ei voinut nahda tata: se kysyy "elaako lupaus viela ikkunan
# sulkeuduttua", ei "onko lupaus oikein rajattu". Kaksi eri kysymysta samasta
# vaitteesta (muisti: portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa).
# ---------------------------------------------------------------------------

def test_rajausportti_kaataa_rajaamattoman_lupauksen(tmp_path, monkeypatch):
    import scripts.check_free_window as g
    f = tmp_path / "index.html"
    f.write_text("<strong>Premium is free until the 12 September deadline"
                 "</strong>", encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    monkeypatch.setattr(g, "surfaces", lambda: [f])
    assert g.scope_misses([f])
    assert g.main() == 1


def test_negatiivinen_kontrolli_rajattu_lupaus_lapaisee(tmp_path, monkeypatch):
    """Ilman tata portti voisi kaataa KAIKEN ja nayttaa silti toimivalta."""
    import scripts.check_free_window as g
    f = tmp_path / "index.html"
    f.write_text("<strong>Premium is free on the web until the 12 September "
                 "deadline</strong>", encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    monkeypatch.setattr(g, "surfaces", lambda: [f])
    assert not g.scope_misses([f])


def test_rajaus_hrefissa_ei_kelpaa_rajaukseksi(tmp_path, monkeypatch):
    """🔴 TAMA REIKA OLI PORTIN ENSIMMAISESSA VERSIOSSA, ja se teki siita
    inertin juuri silla sivulla jota varten se kirjoitettiin.

    Bandin CTA on `href="https://pro.goaliq.app/"` 120 merkin paassa
    lupauksesta, joten rajausregex osui URLiin attribuutin sisalla ja portti
    oli vihrea vaikka nakyva teksti ei rajannut mitaan. Mutaatiotesti
    paljasti sen; ilman tata testia se palaisi.
    """
    import scripts.check_free_window as g
    f = tmp_path / "index.html"
    f.write_text(
        '<p><strong>Premium is free until the 12 September deadline</strong>'
        '</p><a href="https://pro.goaliq.app/">Get Premium free</a>',
        encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    monkeypatch.setattr(g, "surfaces", lambda: [f])
    assert g.scope_misses([f]), "href-URL kelpasi rajaukseksi"


def test_meta_descriptionin_rajaus_KELPAA(tmp_path, monkeypatch):
    """Vastapari edelliselle: tagien pyyhkiminen olisi vaihtanut yhden
    vaaran positiivisen toiseen.

    `faq.html`in oma rajaus asuu `<meta name="description" content="...">`
    -attribuutissa, joka NAKYY hakutuloksessa. Jos portti pyyhkisi tagit
    kokonaan, se kaatuisi rivilta joka on oikein - ja paivittain punainen
    portti tulee ohitetuksi (muisti: pysyvasti-punainen-putki-nielee-
    regression).
    """
    import scripts.check_free_window as g
    f = tmp_path / "faq.html"
    f.write_text(
        '<meta name="description" content="Pricing (free on the web until '
        '12 September, then 3.99 EUR/month), cancelling.">', encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    monkeypatch.setattr(g, "surfaces", lambda: [f])
    assert not g.scope_misses([f]), "meta-descriptionin rajaus hylattiin"


def test_rajaus_liian_kaukana_ei_kelpaa(tmp_path, monkeypatch):
    """Varaus kaukana luvusta ei tavoita lukijaa."""
    import scripts.check_free_window as g
    f = tmp_path / "index.html"
    f.write_text("<p>Premium is free until the GW4 deadline.</p>"
                 + "<p>filler.</p>" * 60
                 + "<p>Everything above is on the web.</p>", encoding="utf-8")
    monkeypatch.setattr(g, "ROOT", tmp_path)
    monkeypatch.setattr(g, "surfaces", lambda: [f])
    assert g.scope_misses([f])


def test_repon_omat_pinnat_ovat_rajattuja():
    """Portti oikeaa korpusta vasten, ei vain fikstuureja.

    Tama on se testi joka olisi kaatanut 7.9:n vian.
    """
    import scripts.check_free_window as g
    puuttuu = g.scope_misses()
    assert not puuttuu, "rajaamaton ilmaisikkunalupaus:\n  " + "\n  ".join(
        f"{f}:{ln} {t!r}" for f, ln, t in puuttuu)


# --- 12.9.2026: osittainen GEN-kate paasti hintavaitteen livena lapi -------

def test_heron_hintanootti_on_gen_lohkossa():
    """Villen loydos 12.9 livena, sen JALKEEN kun portti sanoi 0 kohtaa.

    `hero_cta_html` vaihtoi napin oikein 12:30, mutta hintanootti heti sen
    ALLA oli GEN-markkerien ULKOPUOLELLA ja kovakoodattu ("After 12
    September it is EUR3.99..."). Osittainen kate on pahempi kuin ei
    katetta: pinta nayttaa hoidetulta.
    """
    from src.free_window import SURFACE_BLOCKS

    assert ("index.html", "FREE-HERO-PRICE") in SURFACE_BLOCKS
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "GEN:FREE-HERO-PRICE-START" in html
    assert "GEN:FREE-HERO-PRICE-END" in html


def test_hintanootti_molemmissa_tiloissa():
    import datetime as _d

    from src.free_window import hero_price_note_html

    auki = hero_price_note_html(_d.datetime(2026, 9, 10, tzinfo=_d.timezone.utc))
    kiinni = hero_price_note_html(_d.datetime(2026, 9, 13, tzinfo=_d.timezone.utc))
    assert "After" in auki, "auki: paivamaaravaite kuuluu sivulle"
    assert "After" not in kiinni, "kiinni: menneessa muodossa oleva lause pois"
    for tila in (auki, kiinni):
        assert "3.99" in tila and "25" in tila, "hinnat nakyvat molemmissa"


def test_paivamaarahintavaite_on_oma_perheensa():
    """CLAIM_RE ei nae tata: se ei lupaa ilmaista Premiumia. Silti se
    vanhenee samalla hetkella."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cfw", ROOT / "scripts" / "check_free_window.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    vanhentuvat = [
        "After 12 September it is &euro;3.99 a month",
        "After 12 Sept it is EUR25 a year",
        "After the GW4 deadline it is €3.99",
        "Free until 12 Sept</span> then &euro;25 / year",
    ]
    for t in vanhentuvat:
        assert m.DATED_PRICE_RE.search(t), t
        assert not m.CLAIM_RE.search(t) or "Free until 12 Sept" in t, (
            f"kontrolli: {t!r} ei saa loytya PELKASTAAN CLAIM_RE:lla")
    for viaton in ("&euro;3.99 a month, or &euro;25 a year.",
                   "&euro;3.99 / month or &euro;25 / year",
                   "After the match we publish the result"):
        assert not m.DATED_PRICE_RE.search(viaton), viaton
