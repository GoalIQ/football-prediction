# -*- coding: utf-8 -*-
"""Portti: kortti ja sivu nostavat SAMAT joukkueliput samasta lukijasta.

🔴 TAUSTA (julkaisuportin huomio 4.9.2026, korjattu 7.9).
`fpl_xp_projections.json` antaa `team_flag`in kolmella arvolla: `promoted`,
`high_turnover`, tyhja. Long-tail-sivut tunsivat molemmat liput; jakokortti
tarkisti vain `== "promoted"`, joten `high_turnover` ei tuottanut korttiin
mitaan merkkia.

Mitattu 7.9 poolista: **99 `high_turnover` ja 80 `promoted`** - lahes puolet
liputetuista pelaajista oli kortilla merkitsematta. Yksi heista oli Wissa
(Newcastle, 25,2 % viime kauden minuuteista lahtenyt).

Kortti on julkisin pinta, koska kuva irtoaa sovelluksesta.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_kortti_merkitsee_jokaisen_lipun():
    from src.models.team_flag import MERKKI, marker, team_flag
    for lippu in MERKKI:
        p = {"web_name": "X", "team_flag": lippu}
        assert marker(p), f"{lippu} ei tuota merkkia kortille"
        assert team_flag(p) == lippu
    # NEGATIIVINEN KONTROLLI: liputon pelaaja ei saa merkkia, eika
    # tuntematon lippu keksi omaansa.
    assert marker({"web_name": "X"}) == ""
    assert marker({"web_name": "X", "team_flag": ""}) == ""
    assert marker({"web_name": "X", "team_flag": "jokin_uusi_2027"}) == ""


def test_merkit_ovat_erottuvia():
    """Kaksi lippua ei saa jakaa samaa merkkia: alaviite selittaa ne
    erikseen, ja lukija yhdistaa merkin selitteeseen."""
    from src.models.team_flag import MERKKI
    assert len(set(MERKKI.values())) == len(MERKKI), MERKKI


def test_alaviite_selittaa_vain_nakyvat_merkit():
    """10.8: sivun selite kertoi merkista jota sivulla ei ollut yhtaan, ja
    lukija etsi turhaan. Sama saanto kortille."""
    from src.models.team_flag import flags_present
    assert flags_present([{"team_flag": "promoted"}]) == ["promoted"]
    assert flags_present([{"team_flag": "high_turnover"}]) == ["high_turnover"]
    assert flags_present([{"team_flag": "promoted"},
                          {"team_flag": "high_turnover"}]) == [
        "promoted", "high_turnover"]
    assert flags_present([{"web_name": "X"}]) == []
    assert flags_present([]) == []
    assert flags_present(None) == []


def test_kortin_ja_sivun_lippujoukko_on_sama():
    """Sivu (long-tail) ja kortti lukevat saman lippujoukon. Jos toiselle
    lisataan lippu, tama kaatuu - se oli tasan vika joka jai 4.9->7.9."""
    from scripts.build_fpl_longtail import _TFLAG_LABEL
    from src.models.team_flag import MERKKI, SANA
    assert set(_TFLAG_LABEL) == set(MERKKI), (
        "sivu ja kortti tuntevat eri liput")
    assert _TFLAG_LABEL == SANA, "sama lippu, eri sana pinnoilla"


def test_artefaktissa_ei_ole_lippua_jota_pinnat_eivat_tunne():
    """Ylavirta voi lisata uuden lipun; silloin molemmat pinnat ovat
    hiljaa vaarassa. Portti lukee ARTEFAKTIN, ei koodia."""
    p = ROOT / "data" / "fpl_xp_projections.json"
    if not p.exists():
        pytest.skip("projektiota ei ole")
    from src.models.team_flag import MERKKI
    doc = json.loads(p.read_text(encoding="utf-8"))
    nahdyt = {(x.get("team_flag") or "") for x in doc.get("players") or []}
    tuntemattomat = {f for f in nahdyt if f and f not in MERKKI}
    assert not tuntemattomat, (
        f"artefaktissa on lippuja joita pinnat eivat tunne: {tuntemattomat}")
    # KONTROLLI: artefaktissa on OIKEASTI molempia lippuja, joten testi ei
    # ole vihrea tyhjyyden takia.
    assert {"promoted", "high_turnover"} <= nahdyt, nahdyt
