"""#152: fpl.html CS-solujen predict-linkit (mobiilin solu-tap-pariteetti).

Ei verkkoa, ei buildia — vain linkkilogiikka + slug-driftin vartija.
"""
from __future__ import annotations

from scripts.build_fpl_page import _pred_slug, predict_cell_href
from scripts.build_prediction_pages import _slug as pages_slug


def test_pred_slug_matches_prediction_pages_slug():
    # Ottelusivujen tiedostonimet syntyvät build_prediction_pages._slug:lla —
    # linkin pitää osua täsmälleen samaan slugiin tai solut 404:aavat.
    # 5.8.2026: molemmat osoittavat nyt samaan scripts.slugs.slug-funktioon,
    # joten tämä on identiteettitarkistus — driftin vartiointi siirtyi
    # test_slug_output_is_pinned:iin, joka pinnaa TULOKSEN eikä vertaa
    # kahta funktiota keskenään.
    for name in ("Manchester United", "Nottingham Forest", "Brighton & Hove Albion",
                 "São Paulo", "Wolverhampton Wanderers", "Coventry"):
        assert _pred_slug(name) == pages_slug(name)


def test_slug_output_is_pinned():
    """#229-SEO: slug-kaavan TULOS on julkinen URL-pinta, ei toteutusyksityiskohta.

    Nämä ovat livenä olevia URL-polkuja. Jos tämä testi hajoaa, sivujen
    osoitteet ovat muuttumassa ja se on 301-päätös, ei refaktorointi.
    """
    cases = {
        # F2: diakriitit translitteroituvat, eivät katoa väliviivaksi
        "São Paulo": "sao-paulo",
        "Club Atlético de Madrid": "club-atletico-de-madrid",
        "Málaga CF": "malaga-cf",
        "FC Bayern München": "fc-bayern-munchen",
        "Real Betis Balompié": "real-betis-balompie",
        # NFKD ei hoida näitä -> esikäännöksen regressiovahti
        "Preußen Münster": "preussen-munster",
        "Łódź": "lodz",
        "Køge": "koge",
        # F1: näyttönimikartan tuottamat muodot
        "Bayern Munich": "bayern-munich",
        "Atletico Madrid": "atletico-madrid",
        "Inter": "inter",
        # ASCII-nimet EIVÄT saa liikkua (PL + BSA ovat indeksissä)
        "Manchester United": "manchester-united",
        "Brighton & Hove Albion": "brighton-hove-albion",
        "Atletico-MG": "atletico-mg",
    }
    for raw, expected in cases.items():
        assert pages_slug(raw) == expected, raw


def test_display_names_cover_the_four_long_name_leagues():
    """Hiljainen puolikas kattavuus on tässä talossa tunnettu vikaluokka.

    22.8: joukko kasvoi neljästä kuuteen kun Eredivisie ja Primeira Liga
    saivat sivut (SEO-LEAGUES-ELC-PPL-DED). Testi pitää edelleen listan
    KIINTEÄNÄ eikä salli hiljaista kasvua: uusi liiga on lisättävä tähän
    tietoisesti, ja PL/BSA-poissulku tarkistetaan erikseen alla. ELC jäi
    ulkopuolelle koska sen lokinimet ovat jo hakumuodossa.
    """
    from scripts.build_prediction_pages import DISPLAY_NAMES, DISPLAY_NAME_COMPS

    assert DISPLAY_NAME_COMPS == {"PD", "SA", "BL1", "FL1", "DED", "PPL"}
    # PL ja BSA ovat rakenteellisesti ulkopuolella — ei sattumalta siksi että
    # niiden nimet eivät satu olemaan kartassa.
    for pl_or_bsa in ("Arsenal", "Coventry", "Sao Paulo", "Atletico-MG"):
        assert pl_or_bsa not in DISPLAY_NAMES
    # Kartta ei saa tuottaa törmäystä (kaksi joukkuetta samaan slugiin).
    slugs = [pages_slug(v) for v in DISPLAY_NAMES.values()]
    assert len(slugs) == len(set(slugs))
    # Eikä yhtään feedin pitkän nimen jäännöstä.
    for value in DISPLAY_NAMES.values():
        assert not any(t in value for t in ("Calcio", "Balompié", "de Fútbol",
                                            "1907", "1913", "1909", "1901"))


def test_predict_cell_href_falls_back_to_hub(tmp_path):
    # Ottelusivua ei ole generoitu → hub (on aina olemassa).
    assert predict_cell_href("Arsenal", "Coventry", "H", root=tmp_path) == "/predictions"


def test_predict_cell_href_uses_match_page_when_generated(tmp_path):
    """LEVYLTA .html, LINKKIIN PAATTEETON (muutettu 7.9.2026).

    Cloudflare Pages ohjaa `.html`-URLit 308:lla paatteettomaan muotoon, joka
    on myos ottelusivun oma `rel=canonical`. Mitattu 7.9: `/fpl`-sivulla oli
    66 ottelulinkkia, ja jokainen niista maksoi yhden ylimaaraisen hypyn
    kohteeseen joka on tasan sama sivu.

    Olemassaolo tarkistetaan yha `.html`:lla, koska tiedosto on levylla siina
    muodossa. Vain LINKKI on paatteeton - jos molemmat muutettaisiin, ehto ei
    osuisi mihinkaan ja jokainen solu putoaisi hubiin.
    """
    d = tmp_path / "predictions" / "premier-league"
    d.mkdir(parents=True)
    (d / "arsenal-vs-coventry.html").write_text("x", encoding="utf-8")
    assert (predict_cell_href("Arsenal", "Coventry", "H", root=tmp_path)
            == "/predictions/premier-league/arsenal-vs-coventry")
    # Vieraspeli kääntää koti/vieras-järjestyksen → eri sivu, jota ei ole → hub.
    assert predict_cell_href("Arsenal", "Coventry", "A", root=tmp_path) == "/predictions"
    # NEGATIIVINEN KONTROLLI: levyn tarkistus lukee yha .html-tiedostoa, joten
    # ilman tiedostoa solu EI saa linkittaa ottelusivuun.
    assert (predict_cell_href("Chelsea", "Coventry", "H", root=tmp_path)
            == "/predictions")
