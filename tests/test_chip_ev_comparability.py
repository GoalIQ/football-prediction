"""PORTTI: chip-EV:n rivit ovat vertailukelpoisia, ja `best` pysyy perustassaan.

🔴 KOLME MITATTUA VIKAA (Villen rivi 1186244, 25.8.2026).

1. NELJA SARAKETTA, YKSI ERI SUURE. `bb`/`tc`/`fh` ovat YHDEN kierroksen lukuja,
   `wc` on KUMULATIIVINEN suffiksisumma. Rivit nayttivat samalta:
       GW2 wc 38,00 (6 kierrosta) · GW7 wc 10,37 (1 kierros)
   Monotoninen lasku nayttaa ajoitussignaalilta mutta on ikkunan pituus.

2. `best` VERTASI YLI BASIS-RAJAN. BB ja TC valitsivat GW26:n karkealta
   `team_approx_cs_fdr`-rivilta pelaajatason rivien ohi. Karkea approksimaatio
   voitti puolustettavan luvun, ja `basis` kertoi sen vasta jalkikateen.

3. HORISONTIN ULKOPUOLINEN `wc` OLI KEKSITTY. Skaalaus kertoi wc-sarakkeen
   KESKIARVOLLA (23,97) — eri pituisten ikkunoiden summien keskiarvo, joka ei
   ole mikaan suure. Siita johdettu GW8 24,65 nayttti tarkalta.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import api.main as m

client = TestClient(m.app)


def _payload():
    r = client.get("/api/fantasy/chip-ev")
    assert r.status_code == 200
    return r.json()


def _tarkat(d):
    return [w for w in d["windows"] if w["basis"] == "player_xp"]


def _karkeat(d):
    return [w for w in d["windows"] if w["basis"] != "player_xp"]


def test_wildcard_rivi_kertoo_montako_kierrosta_se_kattaa():
    """🔴 Ilman tata kenttaa lukija vertaa 6 kierroksen summaa yhden kierroksen
    lukuun ja lukee erosta ajoitussignaalin jota siina ei ole."""
    rivit = _tarkat(_payload())
    if not rivit:
        return  # esikausi / data puuttuu
    for w in rivit:
        assert w.get("wc_window_gws") is not None, w
    # ...ja pituus kutistuu rivi riviltä, mika on juuri se mika piti kertoa.
    pituudet = [w["wc_window_gws"] for w in rivit]
    assert pituudet == sorted(pituudet, reverse=True), pituudet


def test_yhden_kierroksen_chipeilla_ei_ole_ikkunaa():
    """`bb`/`tc`/`fh` ovat yhden kierroksen lukuja. Ikkunakentta niille olisi
    vaite etta nekin kumuloituvat."""
    d = _payload()
    for w in d["windows"]:
        for chip in ("bb", "tc", "fh"):
            assert f"{chip}_window_gws" not in w, (chip, w)


def test_horisontin_ulkopuolella_wildcardille_ei_anneta_lukua():
    """🔴 Skaalattu kumulatiivinen luku on keksitty, ei epatarkka. `bb`/`tc`/
    `fh` ovat yhden kierroksen lukuja joten niiden skaalaus on dokumentoitu
    approksimaatio; wc:n ei ole."""
    karkeat = _karkeat(_payload())
    if not karkeat:
        return
    for w in karkeat:
        assert w["wc_ev"] is None, w
        # ...mutta muut EIVAT ole tyhjia: hiljainen nollaus olisi eri vika.
        assert w["bb_ev"] is not None and w["tc_ev"] is not None


def test_paras_ikkuna_valitaan_vain_mitatuilta_riveilta():
    """🔴 Karkea joukkue-approksimaatio ei saa voittaa pelaajatason lukua."""
    d = _payload()
    if not _tarkat(d):
        return
    for chip, b in (d.get("best") or {}).items():
        assert b["basis"] == "player_xp", (chip, b)


def test_karkea_arvio_raportoidaan_erikseen_eika_vaieta():
    """Arvio ei katoa — se saa oman nimensa. Vaientaminen olisi eri vika kuin
    sekoittaminen, ja yhta huono."""
    d = _payload()
    if not _karkeat(d):
        return
    est = d.get("best_estimate") or {}
    assert est, "karkea arvio katosi kokonaan"
    for chip, b in est.items():
        assert b["basis"] != "player_xp", (chip, b)
        assert chip != "wc", "wildcardille ei ole karkeaa arviota"


def test_ilmaispinta_ei_saa_kumpaakaan_parasta():
    """🔴 `best_estimate` on sama premium-tieto toisella nimella. Pelkka
    `best`:n tyhjennys jattaisi sen nakyviin."""
    import api.fantasy_edge as fe
    orig = fe.is_premium_request
    fe.is_premium_request = lambda r: False
    try:
        d = client.get("/api/fantasy/chip-ev").json()
    finally:
        fe.is_premium_request = orig
    assert d["meta"].get("masked") is True
    assert d["best"] == {} and d["best_estimate"] == {}


def test_notes_ei_vuoda_koodinimia_kayttajatekstiin():
    """🔴 `basis=player_xp` ja `basis=team_approx_cs_fdr` ovat JSON-arvoja,
    eivat lukijan kielta. Sama vikaluokka kuin kielletty "legal squad"."""
    notes = " ".join(_payload()["meta"]["notes"])
    for koodinimi in ("basis=", "player_xp", "team_approx", "cs_fdr",
                      "wc_ev", "bb_ev", "_window_gws"):
        assert koodinimi not in notes, koodinimi


def test_notes_kertoo_eron_kumulatiivisen_ja_kierroskohtaisen_valilla():
    """Portti omalle selitteelleen: jos tama lause katoaa, sarakkeet nayttavat
    taas samalta suureelta."""
    notes = " ".join(_payload()["meta"]["notes"]).lower()
    assert "one gameweek" in notes and "how many rounds" in notes
