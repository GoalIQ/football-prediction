# -*- coding: utf-8 -*-
"""Portit UCL-kauden vaihelukijalle.

🔴 SAANTO 6a KOHTA 3: invariantti mitataan JOKA VAIHEESSA, ei
nykyhetkessa. Talla hetkella kaikki 1 162 pelaajaa ovat
`matchdays_played == 0`, joten testi joka ajaa vain tuotantodatalla on
vihrea siihen asti kun se lakkaa olemasta tosi - eli MD1:n jalkeen 8.9.
Nama ajavat samat funktiot synteettisilla vaiheilla.
"""
from __future__ import annotations

import datetime as dt

from src.models import ucl_phase as up

NYT = dt.datetime(2026, 9, 7, 15, 0, tzinfo=dt.timezone.utc)


def _doc(pelattu: int, deadlinet: list[str]) -> dict:
    return {
        "matchdays": [{"md": i + 1, "deadline_utc": d, "is_locked": False}
                      for i, d in enumerate(deadlinet)],
        "players": [{"name": "X", "matchdays_played": pelattu,
                     "prev_season_points": 121, "points": 14}
                    if pelattu else
                    {"name": "X", "matchdays_played": 0,
                     "prev_season_points": 121}],
    }


TULEVA = "2026-09-08T18:45:00+00:00"
MYOHEMPI = "2027-01-27T18:45:00+00:00"
MENNYT = "2026-09-01T18:45:00+00:00"


def test_esikausi_kun_yhtaan_kierrosta_ei_ole_pelattu():
    assert up.vaihe(_doc(0, [TULEVA, MYOHEMPI]), NYT) == up.ESIKAUSI


def test_kesken_kun_kierroksia_on_pelattu_ja_deadlineja_jaljella():
    assert up.vaihe(_doc(2, [MENNYT, MYOHEMPI]), NYT) == up.KESKEN


def test_ohi_kun_viimeinen_deadline_on_mennyt():
    """Paattyneella kaudella 'next deadline' -copy on VALHE, ei tyhja.
    Siksi OHI on oma vaiheensa eika `KESKEN` ilman deadlinea."""
    assert up.vaihe(_doc(8, [MENNYT]), NYT) == up.OHI


def test_kentta_ja_otsikko_tulevat_SAMASTA_kutsusta():
    """🔴 KOKO MODUULIN SYY. Jos pinta hakisi kentan ja otsikon erikseen,
    ne ajautuisivat erilleen ja luvun vieressa olisi vaara vuosiluku
    (muisti: lause-ja-luku-eri-lahteesta)."""
    kentta, otsikko = up.pistekentta(_doc(0, [TULEVA]), NYT)
    assert kentta == "prev_season_points"
    assert "last season" in otsikko.lower(), otsikko

    kentta, otsikko = up.pistekentta(_doc(2, [MENNYT, MYOHEMPI]), NYT)
    assert kentta == "points"
    assert "last season" not in otsikko.lower(), otsikko


def test_otsikko_seuraa_kenttaa_myos_kauden_lopussa():
    """KONTROLLI kolmannessa vaiheessa: ilman tata pari voisi olla oikein
    kahdessa vaiheessa ja vaarin siina johon kausi paatyy."""
    kentta, otsikko = up.pistekentta(_doc(8, [MENNYT]), NYT)
    assert kentta == "points" and "last season" not in otsikko.lower()


def test_arvo_ei_kaadu_puuttuvaan_kenttaan():
    """Esikaudella `points`-kenttaa EI OLE olemassa. `p["points"]`
    nostaisi KeyErrorin ja `p.get("points")` palauttaisi Nonen, joka
    kaataa lajittelun."""
    p = _doc(0, [TULEVA])["players"][0]
    assert up.arvo(p, "points") == 0
    assert up.arvo(p, "prev_season_points") == 121


def test_seuraava_kierros_on_ensimmainen_tuleva():
    k = up.seuraava_kierros(_doc(0, [MENNYT, TULEVA, MYOHEMPI]), NYT)
    assert k and k["deadline_utc"] == TULEVA


def test_seuraava_kierros_on_none_kun_kausi_on_ohi():
    assert up.seuraava_kierros(_doc(8, [MENNYT]), NYT) is None


def test_vaihe_ei_ole_sidottu_kalenteriin():
    """NEGATIIVINEN KONTROLLI: sama paivamaara, eri data -> eri vaihe.
    Jos vaihe olisi kovakoodattu kauden alkupaivaan, tama menisi lapi
    vaarin."""
    assert up.vaihe(_doc(0, [TULEVA]), NYT) != up.vaihe(
        _doc(3, [MENNYT, MYOHEMPI]), NYT)


def test_tuotantoartefakti_kulkee_saman_lukijan_lapi():
    """Ja lopuksi oikea data: mika tahansa vaihe, mutta pari on ehjä."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "data" / "ucl_fantasy.json"
    if not p.exists():
        return
    doc = json.loads(p.read_text(encoding="utf-8"))
    kentta, otsikko = up.pistekentta(doc)
    assert up.vaihe(doc) in (up.ESIKAUSI, up.KESKEN, up.OHI)
    if kentta == "prev_season_points":
        assert "last season" in otsikko.lower()
        assert all("points" not in pl for pl in doc["players"]), (
            "artefaktissa on `points`-kentta vaikka vaihe on esikausi")


# --- 11.9.2026: teamPlayed nollattu kierroksen vaihtuessa ------------------

def _doc_md2_lukittu() -> dict:
    """Syotteen tila 11.9 klo 13Z: MD1 pelattu ja lukittu, syote MD2:ssa,
    `teamPlayed == 0` KAIKILLA, mutta luvut ovat jo taman kauden."""
    return {
        "matchdays": [
            {"md": 1, "deadline_utc": MENNYT, "is_locked": True},
            {"md": 2, "deadline_utc": MYOHEMPI, "is_locked": False},
        ],
        "players": [{"name": "E. Haaland", "matchdays_played": 0,
                     "prev_season_points": 0, "points": 12}],
    }


def test_kesken_kun_kierros_on_lukittu_vaikka_teamPlayed_on_nollattu():
    """🔴 11.9: pelkka `matchdays_played` palautti ESIKAUDEN kesken kauden,
    ja sarake olisi sanonut "Pts (last season)" Haalandin 12:lle."""
    doc = _doc_md2_lukittu()
    assert up.kausi_alkanut(doc) is True
    assert up.vaihe(doc, NYT) == up.KESKEN
    assert up.pistekentta(doc, NYT) == ("points", "Pts")


def test_kausi_alkanut_raw_lukee_kumman_tahansa_signaalin():
    """Kumpikin signaali yksin riittaa, ja kumpikaan ei palaa takaisin."""
    lukittu = [{"md": 1, "is_locked": True}]
    avoin = [{"md": 1, "is_locked": False}]
    assert up.kausi_alkanut_raw(lukittu, [0, 0]) is True
    assert up.kausi_alkanut_raw(avoin, [0, 1]) is True
    assert up.kausi_alkanut_raw(avoin, [0, 0]) is False
    assert up.kausi_alkanut_raw([], []) is False
    # Ei kaadu puuttuviin/None-arvoihin (syote voi jattaa kentan pois).
    assert up.kausi_alkanut_raw([{"md": 1}], [None, ""]) is False


def test_esikausi_kontrolli_ei_lukittua_eika_pelattua():
    """KONTROLLI samalle lukijalle: ilman kumpaakaan signaalia esikausi."""
    doc = _doc(0, [TULEVA, MYOHEMPI])
    assert up.kausi_alkanut(doc) is False
    assert up.vaihe(doc, NYT) == up.ESIKAUSI
