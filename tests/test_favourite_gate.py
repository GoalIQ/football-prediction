# -*- coding: utf-8 -*-
"""SUOSIKKI-VAIN-KUN-ERO-YLITTAA-VIRHEEN (QUEUE, korjattu 10.9.2026).

Villen havainto 8.9: tuotanto nimesi Club Brugge suosikiksi (40,5 %) kun
tasapeli oli 24,0 % ja Aston Villa 35,5 % — ero kärkeen on 5,0 pp, ja mallin
oma mitattu keskipoikkeama Optasta oli 8,2 pp. Rivin oma esimerkki on tässä
suoraan regressiotestinä (test_villen_brugge_esimerkki_on_lahella_kutsu).

Jokaisella positiivisella testillä on negatiivinen kontrolli, ja yksi
mutaatiotesti erottaa oikean (kolmen tuloksen KESKINÄINEN) vertailun
virheellisestä koti-vieras-vertailusta joka jättäisi tasapelin huomiotta.
"""
from src.models.favourite_gate import calibration_error_pp, is_close_call


def _bin(pred, actual, n):
    return {"bin_mid": pred, "predicted": pred, "actual": actual, "n": n}


# ---------------------------------------------------------------------------
# calibration_error_pp: painotettu MAE, ei tasapainotettu keskiarvo
# ---------------------------------------------------------------------------
def test_calibration_error_pp_is_n_weighted_mean_abs_error():
    calibration = [
        _bin(0.20, 0.10, n=90),   # |0.20-0.10| = 0.10, paino 90
        _bin(0.80, 0.90, n=10),   # |0.80-0.90| = 0.10, paino 10
    ]
    # Molempien binien virhe on sama (0.10) joten painotus ei tässä erotu -
    # vaihdetaan toinen binin virhe isommaksi jotta painotus näkyy.
    calibration = [
        _bin(0.20, 0.10, n=90),   # virhe 0.10 pistettä, paino 90
        _bin(0.80, 0.50, n=10),   # virhe 0.30 pistettä, paino 10
    ]
    expected = (0.10 * 90 + 0.30 * 10) / 100 * 100  # = 12.0 pp
    assert calibration_error_pp(calibration) == expected


def test_negative_control_naive_unweighted_mean_gives_a_different_number():
    """Kontrolli: jos joku vaihtaisi painotetun MAE:n suoraksi keskiarvoksi,
    tämä testi erottaisi sen — muuten testi 1 läpäisisi silläkin."""
    calibration = [_bin(0.20, 0.10, n=90), _bin(0.80, 0.50, n=10)]
    naive_mean = (0.10 + 0.30) / 2 * 100  # = 20.0 pp
    assert calibration_error_pp(calibration) != naive_mean
    assert calibration_error_pp(calibration) == 12.0


def test_calibration_error_pp_is_none_without_measured_data():
    assert calibration_error_pp([]) is None
    assert calibration_error_pp(None) is None
    assert calibration_error_pp([_bin(0.5, 0.5, n=0)]) is None


def test_negative_control_missing_data_does_not_suppress_the_surface():
    """Kontrolli: puuttuva mittaus (None) ei saa vaimentaa suosikkia kuten
    0.0 pp:n virhe vaimentaisi jokaisen eron joka ei ole tasan 0. Reitti
    calibration_error_pp([]) -> is_close_call pitää päätyä samaan turvalliseen
    oletukseen kuin error_pp=None suoraan annettuna."""
    assert is_close_call(0.5, 0.3, 0.2, calibration_error_pp([])) is False


# ---------------------------------------------------------------------------
# is_close_call: kolmen tuloksen KESKINÄINEN ero, ei koti-vieras-ero
# ---------------------------------------------------------------------------
def test_villen_brugge_esimerkki_on_lahella_kutsu():
    """Tuotannon oma tapaus 8.9: Brugge 40,5 / tasapeli 24,0 / Villa 35,5,
    mitattu virhe 8,2 pp. Ero kärkeen on 5,0 pp < 8,2 pp -> lähellä kutsu."""
    assert is_close_call(0.405, 0.240, 0.355, error_pp=8.2) is True


def test_negative_control_smaller_measured_error_does_not_trip_close_call():
    """Kontrolli: sama ottelu mutta pienempi mitattu virhe (4.0 pp) ei enää
    ylitä 5,0 pp:n eroa - suosikki saa silloin näkyä normaalisti."""
    assert is_close_call(0.405, 0.240, 0.355, error_pp=4.0) is False


def test_clear_favourite_is_not_a_close_call():
    assert is_close_call(0.70, 0.20, 0.10, error_pp=8.2) is False


def test_mutation_top_two_gap_not_home_away_gap():
    """Mutaatiotesti: jos joku vaihtaisi vertailun 'abs(p_home - p_away)':ksi
    (kuten `named_winner` tekee voittajan NIMEÄMISEEN), tämä tapaus antaisi
    väärän vastauksen. Koti 50 %, tasapeli 45 %, vieras 5 %: koti-vieras-ero
    on 45 pp (näyttäisi selvältä suosikilta), mutta oikea kärkiero on
    koti-tasapeli 5 pp - se ON lähellä kutsu mitatulla 8,2 pp:n virheellä."""
    assert is_close_call(0.50, 0.45, 0.05, error_pp=8.2) is True


def test_negative_control_home_away_gap_alone_would_have_passed_wrongly():
    """Kontrolli todistaa etta edellinen testi mittaa jotain: naiivi
    koti-vieras-ero olisi 45 pp, joka EI ole lähellä 8,2 pp:n virhettä -
    eli naiivi toteutus olisi antanut False:n samassa tilanteessa."""
    naive_gap_pp = abs(0.50 - 0.05) * 100
    assert naive_gap_pp >= 8.2, "kontrolli ei enää erota oikeaa väärästä"


def test_error_pp_none_never_suppresses_the_surface():
    assert is_close_call(0.34, 0.33, 0.33, error_pp=None) is False
