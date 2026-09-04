"""Portti: seuranvaihdon aiheuttama seurakaton ylitys ei saa estaa freezea.

🔴 MITATTU VIKA (4.9.2026). GW3:n mallin joukkuetta ei voitu jaadyttaa:

    VIRHE: optimoija palautti LAITTOMAN rungon - ei jaadyteta:
      - yli 3/seura: {15: 4}

Syy ei ollut optimoijassa. GW2:n jaadytetyssa rungossa oli **kolme Cityn
pelaajaa** (Guehi, Haaland, Anderson, kaikki `club: 15` jo freezen hetkella)
ja lisaksi Ndiaye Evertonissa (`club: 9`). **Ndiaye siirtyi Cityyn** GW2:n ja
GW3:n valilla, jolloin peritty runko oli nelja pelaajaa samasta seurasta ilman
etta yhtaan siirtoa tehtiin (`changes: null`).

KORJATTU 4.9 (mitattu bootstrapista gw1- ja gw2-freezen `club`-kenttia
vasten): vain YKSI pelaaja vaihtoi seuraa, ei kolme. Ensimmainen kirjaus
sanoi "kolme heista siirtyi" — se oli paattely, ei mittaus, ja se paatyi
seka taman testin etta `inherited_club_excess`in perusteluun.

Villen paatos 4.9 (vaihtoehto a): peritty ylitys sallitaan, kuten FPL:ssa —
seuranvaihdon takia syntynytta ylitysta ei pureta takautuvasti, mutta samasta
seurasta ei saa OSTAA lisaa. Vaihtoehto b (pakotettu siirto) hylattiin, koska
se olisi tehnyt mallin puolesta siirron jota se ei valinnut ja vaaristanyt
kausivertailun.

Tama toistuu jokaisessa siirtoikkunassa, joten portti ajaa synteettiset
tilanteet eika nojaa siihen mika kauden vaihe nyt on (saanto 6a kohta 3).
"""
from __future__ import annotations

import pytest

from scripts.freeze_model_squad_gw import inherited_club_excess, validate_squad

QUOTA = {1: 2, 2: 5, 3: 5, 4: 3}


def _squad(clubs: list[int]) -> list[dict]:
    """15 pelaajaa oikealla positiojakaumalla, seurat annettuna."""
    assert len(clubs) == 15
    pos = [1] * 2 + [2] * 5 + [3] * 5 + [4] * 3
    return [
        {"id": i + 1, "club": clubs[i], "element_type": pos[i], "price": 45}
        for i in range(15)
    ]


def _prev(squad: list[dict], ids: list[int]) -> dict:
    return {"xi": [p for p in squad if p["id"] in ids[:11]],
            "bench": [p for p in squad if p["id"] in ids[11:]]}


def _split(squad: list[dict]) -> tuple[list[dict], list[dict]]:
    return squad[:11], squad[11:]


# --------------------------------------------------------------------------
# Vaiheet: sama runko, eri alkupera
# --------------------------------------------------------------------------


def test_peritty_ylitys_sallitaan() -> None:
    """Kaikki nelja samasta seurasta olivat jo edellisessa rungossa."""
    clubs = [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6]
    clubs[0] = 2  # neljas seuran 2 pelaaja: tuli seuranvaihdon mukana
    squad = _squad(clubs)
    prev = _prev(squad, [p["id"] for p in squad])
    xi, bench = _split(squad)
    assert inherited_club_excess(squad, prev) == {2: 4}
    assert validate_squad(xi, bench, prev=prev) == []


def test_ostettu_ylitys_kaataa() -> None:
    """Sama runko, mutta yksi neljasta on UUSI -> ylitys on oma vika."""
    clubs = [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6]
    clubs[0] = 2
    squad = _squad(clubs)
    # edellinen runko ilman yhta seuran 2 pelaajaa -> han on ostettu nyt
    ids = [p["id"] for p in squad if p["id"] != 1]
    prev = {"xi": [p for p in squad if p["id"] in ids[:11]],
            "bench": [p for p in squad if p["id"] in ids[11:]]}
    xi, bench = _split(squad)
    assert inherited_club_excess(squad, prev) == {}
    ongelmat = validate_squad(xi, bench, prev=prev)
    assert any("yli 3/seura" in o for o in ongelmat), ongelmat


def test_ilman_edellista_runkoa_katto_on_ehdoton() -> None:
    """Kauden ensimmainen freeze: mitaan ei peritty, joten katto patee."""
    clubs = [2, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6]
    xi, bench = _split(_squad(clubs))
    ongelmat = validate_squad(xi, bench, prev=None)
    assert any("yli 3/seura" in o for o in ongelmat), ongelmat


def test_laillinen_runko_menee_lapi_kummallakin_tavalla() -> None:
    """Negatiivinen kontrolli toiseen suuntaan: suodatus ei saa paastaa
    lapi mita tahansa, mutta ei myoskaan kaataa laillista runkoa."""
    clubs = [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6]
    squad = _squad(clubs)
    xi, bench = _split(squad)
    prev = _prev(squad, [p["id"] for p in squad])
    assert validate_squad(xi, bench, prev=prev) == []
    assert validate_squad(xi, bench, prev=None) == []


def test_muut_saannot_patevat_yha_peritylle_rungolle() -> None:
    """Peritty ylitys ei saa avata muita portteja: positiojakauma ja koko
    tarkistetaan kuten ennen."""
    clubs = [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6]
    squad = _squad(clubs)
    squad[0]["element_type"] = 3  # rikotaan kiintio
    xi, bench = _split(squad)
    prev = _prev(squad, [p["id"] for p in squad])
    ongelmat = validate_squad(xi, bench, prev=prev)
    assert any("positiojakauma" in o for o in ongelmat), ongelmat


@pytest.mark.parametrize("n_uusia", [1, 2, 3])
def test_osittain_peritty_ylitys_kaataa(n_uusia: int) -> None:
    """Jos yksikin ylityksen tekija on uusi, ylitys ei ole peritty.

    Tama on se raja jossa saanto voisi vuotaa: 'melkein peritty' ei ole
    peritty, ja ostoa ei saa piilottaa seuranvaihdon taakse.
    """
    clubs = [2, 2, 2, 2] + [1, 1, 3, 3, 3, 4, 4, 4, 5, 5, 6]
    squad = _squad(clubs)
    uudet = {p["id"] for p in squad[:n_uusia]}
    jaljella = [p for p in squad if p["id"] not in uudet]
    prev = {"xi": jaljella[:11], "bench": jaljella[11:]}
    xi, bench = _split(squad)
    assert inherited_club_excess(squad, prev) == {}
    assert any("yli 3/seura" in o for o in validate_squad(xi, bench, prev=prev))
