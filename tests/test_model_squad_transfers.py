"""Mallin runko peritaan ja siirrot tehdaan FPL:n saannoilla (25.8.2026).

🔴 TAUSTA. `freeze_model_squad_gw.py` kutsui `free_optimum()`:ia ILMAN
viittausta edelliseen runkoon: ei siirtorajaa, ei hit-kustannusta. Mitattu 25.8
GW1 -> GW2: 7 pelaajaa 15:sta olisi vaihtunut. Ihminen saa YHDEN ilmaisen
siirron; seitseman maksaisi -24 pistetta. Malli ei maksanut mitaan.

Ja kayttajalle nakyi samaan aikaan lause "The model's squad is locked before
every deadline and plays no chips." Teknisesti tosi (FPL-chippia ei aktivoida)
mutta se antaa ymmartaa etta malli pelaa samoilla saannoilla kuin lukija. Alusta
rakentaminen on VAHVEMPI kuin wildcard, jonka ihminen saa kerran tai kaksi
kaudessa.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _p(pid, pos=3, price=50, club=1, xp=5.0):
    return {"id": pid, "element_type": pos, "price": price, "club": club,
            "web_name": f"P{pid}", "team_short": "AAA",
            "xp_horizon_total": xp, "gameweeks": [{"gw": 2, "xp": xp / 6}]}


def _freeze(ids, meta=None):
    rivit = [{"id": i, "web_name": f"P{i}", "pos": 3, "price": 50, "club": 1}
             for i in ids]
    return {"meta": meta or {}, "xi": rivit[:11], "bench": rivit[11:]}


# ---------------------------------------------------------------------------
# FT-saldo
# ---------------------------------------------------------------------------
def test_ilman_rullausta_yksi_ilmainen_siirto():
    m = _load()
    assert m._ft_available({}) == 1
    assert m._ft_available({"ft_left": 0}) == 1


def test_kayttamaton_siirto_rullaa_kattoon_asti():
    m = _load()
    assert m._ft_available({"ft_left": 1}) == 2
    # 🔴 Katto: rullaus ei kerry rajatta. Ilman kattoa malli saisi kauden
    # lopussa kaytannossa wildcardin ilmaiseksi.
    assert m._ft_available({"ft_left": 5}) == m.FT_MAX
    assert m.FT_MAX == 2


def test_vanha_freeze_ilman_kenttaa_on_konservatiivinen():
    """Puuttuva `ft_left` -> ei rullausta. Epavarmuudessa malli rajoitetaan
    tiukemmin, koska virhe ei silloin imartele sita."""
    m = _load()
    assert m._ft_available({"gw": 1, "cost": 100.0}) == 1


# ---------------------------------------------------------------------------
# Edellisen freezen loytaminen
# ---------------------------------------------------------------------------
def test_perii_lahimmasta_aiemmasta_eika_oleta_gw_miinus_yksi(tmp_path, monkeypatch):
    """Kierros voi jaada valiin (ajo kaatui, kausitauko). Runko peritaan silti
    viimeisimmasta joka on olemassa."""
    m = _load()
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    (tmp_path / "gw1.json").write_text(json.dumps(_freeze([1])), encoding="utf-8")
    (tmp_path / "gw3.json").write_text(json.dumps(_freeze([2])), encoding="utf-8")
    n, _ = m._prev_freeze(5)
    assert n == 3, "lahin AIEMPI, ei gw-1"


def test_ei_aiempaa_freezea_palauttaa_none(tmp_path, monkeypatch):
    """Kauden ensimmainen kierros: vapaa valinta, kuten ihmisellakin."""
    m = _load()
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    assert m._prev_freeze(1) is None


def test_myohempi_freeze_ei_kelpaa_lahteeksi(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    (tmp_path / "gw7.json").write_text(json.dumps(_freeze([1])), encoding="utf-8")
    assert m._prev_freeze(3) is None, "tulevaa kierrosta ei saa peria"


# ---------------------------------------------------------------------------
# Siirtorajoite
# ---------------------------------------------------------------------------
# 28.8 (PLANNER-FREEZE-DIVERGENCE): freeze kayttaa nyt fpl_transfers.plan_gw:ta,
# ei rate-teamin transfer_suggestionsia omalla hit-saannolla. Saannon testit
# (netto >= 0.5, ilmainen siirto samalla kynnyksella, hold, ft_left) elavat
# tests/test_transfer_engine_parity.py:ssa oikealla laillisella rungolla;
# mockatut versiot poistettiin koska ne mittasivat vanhaa polkua.


#: Laillinen 15: 2 GKP, 5 DEF, 5 MID, 3 FWD, enintaan 3 per seura.
_POS = {1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2,
        8: 3, 9: 3, 10: 3, 11: 3, 12: 3, 13: 4, 14: 4, 15: 4}


def _laillinen_pool(ids):
    return [_p(i, pos=_POS[i], club=((i - 1) % 5) + 1) for i in ids]


def _laillinen_freeze(ids, meta=None):
    rivit = [{"id": i, "web_name": f"P{i}", "pos": _POS[i], "price": 50,
              "club": ((i - 1) % 5) + 1} for i in ids]
    return {"meta": meta or {}, "xi": rivit[:11], "bench": rivit[11:]}


def _bootstrap(ids, *, status="u", news="left the league"):
    return {
        "elements": [{"id": i, "web_name": f"P{i}",
                      "element_type": _POS.get(i, 3),
                      "team": ((i - 1) % 5) + 1, "now_cost": 50,
                      "status": status, "news": news,
                      "selected_by_percent": "0.1",
                      "chance_of_playing_next_round": 0} for i in ids],
        "teams": [{"id": c, "name": f"Team{c}", "short_name": f"T{c}"}
                  for c in range(1, 6)],
    }


def test_pelaaja_poissa_poolista_periytyy_bootstrapista():
    """🔴 12.9.2026: TAMA TESTI OLI ENNEN VIAN SPESIFIKAATIO.

    Vanha versio (`test_pelaaja_poissa_poolista_estaa_perimisen`) vaati etta
    funktio palauttaa `None`, ja dokumentoi kutsujan putoamisen vapaaseen
    optimiin oikeaksi kaytokseksi. Se oli VIHREA 11.9 kun freeze jaadytti
    GW4:n rungon jossa 8/15 vaihtui yhdella ilmaisella siirrolla.

    Oikea invariantti: rungon jasen joka on pudonnut xP-artefaktista mutta on
    yha FPL:n bootstrapissa rakennetaan bootstrapista, ja ketju jatkuu.
    """
    m = _load()
    prev = _laillinen_freeze(list(range(1, 16)), {"budget": 100.0})
    pool = _laillinen_pool(range(1, 15))        # id 15 puuttuu poolista
    out = m._constrained_from_prev(prev, pool, 2, ft=1,
                                   bootstrap=_bootstrap([15]))
    assert out is not None, "ketju ei saa katketa poolista pudonneeseen"
    assert len(out["squad"]) == 15
    assert len(out["transfers"]) <= 2, "peritysta rungosta enintaan katto"


def test_pelaajaa_ei_bootstrapissakaan_on_kieltaytyminen():
    """None tarkoittaa nyt tasan yhta asiaa: jasenta ei ole missaan lahteessa.
    Se EI ole signaali pudota vapaaseen optimiin (ks. main())."""
    m = _load()
    prev = _laillinen_freeze(list(range(1, 16)), {"budget": 100.0})
    pool = _laillinen_pool(range(1, 15))
    assert m._constrained_from_prev(prev, pool, 2, ft=1,
                                    bootstrap=_bootstrap([])) is None


def test_poolista_pudonnut_saa_saman_lipun_kuin_moottorin_placeholder():
    """Sama lippu kuin moottorin omalla placeholderilla — yksi lukija.

    🔴 KORJAUS OMAAN AIEMPAAN PERUSTELUUNI (12.9 ilta, tarkistuksen loydos).
    Kirjoitin ensin etta ilman `no_projection`ia `needs_repair` palauttaisi
    False ja moottori mittaisi korvaamista taydella rimalla. **Se ei pida
    paikkaansa:** vanha `_departed_player` kovakoodasi `"chance_next": 0`,
    ja `needs_repair` palauttaa True myos siita. Mitattu:

        needs_repair(vanha)                      = True
        needs_repair(uusi)                       = True
        needs_repair(uusi ilman no_projectionia) = True

    Delegointi on silti oikea: kaksi kopiota samasta kasitteesta erosivat
    yhdessa kentassa, ja `needs_repair`in ENSIMMAINEN ehto luki juuri sita
    kenttaa. Yksi lukija poistaa mahdollisuuden etta ne erkanevat lisaa —
    mutta se ei ollut GW4:n vian syy. Syy oli `_constrained_from_prev`in
    `None` ja `main()`:n fallback, ja ne vartioi
    `tests/test_freeze_chain_continuity.py`.

    Siksi tama testi vaittaa vain sen mika on tosi: kentat ovat identtiset
    moottorin placeholderin kanssa, ja freezen omat lisakentat ovat mukana.
    """
    from src.models.fpl_transfers import needs_repair, placeholder_player

    m = _load()
    boot = _bootstrap([15], status="a", news="")
    boot["elements"][0]["chance_of_playing_next_round"] = None
    rivi = m._departed_player(15, boot)
    kanta = placeholder_player(15, boot)

    puuttuu = [k for k in kanta if k not in rivi]
    assert not puuttuu, f"placeholderin kentat katosivat: {puuttuu}"
    assert rivi["no_projection"] is True, "sama lippu kuin placeholderilla"
    assert rivi["off_pool"] is True, "freezen oma lisakentta"
    assert needs_repair(rivi) is True


def test_ft_left_kertoo_kayttamattomat():
    m = _load()
    from tests.test_transfer_engine_parity import _legal_squad, _prev_from
    squad = _legal_squad()
    out = m._constrained_from_prev(_prev_from(squad), squad, 2, ft=2)
    assert out["transfers"] == []
    assert out["ft_left"] == 2, "kayttamattomat rullaavat eteenpain"


# ---------------------------------------------------------------------------
# Kuollut penkkipaikka freezen kutsupaikalta (17.9, SIIRTOMOOTTORI-EI-MYY-
# PENKIN-PELAAMATONTA). Reseed GW5:een tuo Dovinin (171, status u) takaisin
# penkille; 12.9 mitattu etta moottori ei myy hanta koskaan (XI-hyoty 0.0000).
# Tama mittaa saman freezen omalta polulta: _constrained_from_prev -> plan_gw.
# ---------------------------------------------------------------------------
def test_ketju_siivoaa_kuolleen_penkkipaikan_vapaalla_siirrolla():
    m = _load()
    prev = _laillinen_freeze(list(range(1, 16)), {"budget": 100.0})
    # Korvaaja samasta seurasta kuin lahtija (15 -> seura 5), jotta klubiraja
    # (3/seura) pitaa vaihdon jalkeen. xP sama kuin muilla -> XI-hyoty 0.
    korvaaja = _p(16, pos=4, club=5)
    pool = _laillinen_pool(range(1, 15)) + [korvaaja]
    out = m._constrained_from_prev(prev, pool, 2, ft=1,
                                   bootstrap=_bootstrap([15]))
    assert out is not None
    assert [(t["out"], t["in"]) for t in out["transfers"]] == [(15, 16)], out["transfers"]
    assert out["transfers"][0]["gain_xp"] == 0.0
    assert out["transfers"][0]["hit"] is False
    # Rakenteinen syy nollahyodylle kulkee freezen riville asti.
    assert out["transfers"][0]["repair"] is True
    assert out["transfers"][0]["repair_reason"].startswith("no_projection:")
    assert out["hits"] == 0 and out["ft_left"] == 0
    assert 15 not in {p["id"] for p in out["squad"]}
    assert out["unplayable_left"] == []


def test_ketju_kertoo_kuolleen_paikan_joka_jai_kun_siirto_meni_xi_parannukseen():
    """GW5:n muoto (mitattu 17.9 oikealla artefaktilla): vapaa siirto menee
    XI-parannukseen (White->Thomas +5.18) ja Dovin jaa penkille. Oikein,
    mutta ei hiljaa: `unplayable_left` kertoo sen freeze-metaan asti."""
    m = _load()
    prev = _laillinen_freeze(list(range(1, 16)), {"budget": 100.0})
    korvaaja = _p(16, pos=4, club=5)                 # kuolleen paikan korvaaja, hyoty 0
    parannus = _p(17, pos=3, club=1, xp=30.0)        # MID club1 -> korvaa id 11
    pool = _laillinen_pool(range(1, 15)) + [korvaaja, parannus]
    yksi = m._constrained_from_prev(prev, pool, 2, ft=1, bootstrap=_bootstrap([15]))
    assert [(t["out"], t["in"]) for t in yksi["transfers"]] == [(11, 17)], yksi["transfers"]
    assert yksi["transfers"][0]["repair"] is False
    assert yksi["unplayable_left"] == [15], "jaanyt pelaamaton on kerrottava"
    kaksi = m._constrained_from_prev(prev, pool, 2, ft=2, bootstrap=_bootstrap([15]))
    assert [(t["out"], t["in"]) for t in kaksi["transfers"]] == [(11, 17), (15, 16)]
    assert kaksi["unplayable_left"] == [] and kaksi["hits"] == 0


def test_NEG_ketju_ei_maksa_hittia_kuolleeseen_paikkaan():
    m = _load()
    prev = _laillinen_freeze(list(range(1, 16)), {"budget": 100.0})
    pool = _laillinen_pool(range(1, 15)) + [_p(16, pos=4, club=5)]
    out = m._constrained_from_prev(prev, pool, 2, ft=0,
                                   bootstrap=_bootstrap([15]))
    assert out is not None and out["transfers"] == [] and out["hits"] == 0
