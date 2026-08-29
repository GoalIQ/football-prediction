# -*- coding: utf-8 -*-
"""EO-BY-TIER-osion portit (29.8.2026) - scripts/build_fpl_page.eo_by_tier_html.

Kolme asiaa joita skriptin docstring vaatii ja joita sivu ei saa rikkoa:
  1. n nakyy JOKAISEN tason otsikossa (otos ei taso). Mutaatio: jos
     renderoija pudottaa n:n, test_n_nakyy_jokaisen_tason_otsikossa kaatuu.
  2. Kehallinen payload (meta.circular) EI renderoidy. Negatiivinen kontrolli:
     sama payload circular=False renderoituu, joten testi mittaa lippua eika
     tyhjaa dataa (vrt. muisti kontrolli-lapaisi-tyhjana).
  3. Tyhja tai puuttuva data -> ei osiota, ei otsikkoa ilman sisaltoa.
Lisaksi copy-portti: ei em dashia, ei odds/solver-sanastoa, ei estolistan
nimia nostettuna copyyn, ja mobiilissa nakyvat vain pelaaja + 1. taso +
overall.
"""
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_fpl_page as b  # noqa: E402
from scripts import publish_gate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _player(pid, name, team, eo, cap=0.0, overall=10.0):
    return {"id": pid, "web_name": name, "team": team, "pos": "MID",
            "price": 7.0, "overall_pct": overall,
            "tiers": {k: {"owned_pct": eo, "eo_pct": eo + i, "captain_pct": cap}
                      for i, k in enumerate(("top1k", "top10k", "top100k"))}}


def _eo_payload(circular=False, n=(200, 150, 120)):
    return {
        "meta": {
            "picks_gameweek": 2, "rank_after_gw": 1, "circular": circular,
            "generated_at": "2026-08-29T07:19:40+00:00",
            "metric": "EO = mean multiplier x 100 (bench 0, playing 1, captain 2, "
                      "triple captain 3), taken straight from the official picks payload.",
            "sample": {"top1k": {"n_sampled": n[0]},
                       "top10k": {"n_sampled": n[1]},
                       "top100k": {"n_sampled": n[2]}},
            "caveat": "sample, not tier",
        },
        "players": [_player(i, f"Player{i}", "TST", 100.0 - i, cap=5.0 if i < 3 else 0.0)
                    for i in range(20)],
    }


def _mgr_payload(circular=False, n=180):
    # Viisi rivia per lista, kuten oikeassa datassa: renderoija lupaa
    # "Five per direction" vain taysille listoille, joten yhden rivin
    # fixture mittaisi vaaraa haaraa.
    row = [{"id": 1, "web_name": "Mover", "team": "TST", "pos": "FWD",
            "price": 8.0, "count": 40, "pct": 22.2, "overall_pct": 9.0}] + [
        {"id": 10 + i, "web_name": f"Mover{i}", "team": "TST", "pos": "FWD",
         "price": 8.0, "count": 30 - i, "pct": 16.0 - i, "overall_pct": 9.0}
        for i in range(4)]
    return {
        "meta": {"gameweek": 2, "rank_after_gw": 1, "circular": circular},
        "tiers": {k: {"n_sampled": n, "hold_pct": 40.0, "took_hit_pct": 10.0,
                      "transfers_per_manager": 0.9, "chips": {"none": 170, "wildcard": 2, "freehit": 1}, "transfers_in": row,
                      "transfers_out": row, "captains": row}
                  for k in ("top1k", "top10k", "top100k")},
    }


def _visible(html_text: str) -> str:
    out = re.sub(r"<!--.*?-->", " ", html_text, flags=re.DOTALL)
    return re.sub(r"<[^>]+>", " ", out)


def _main_table_ths(html_text: str) -> list[str]:
    tbl = html_text.split('<div class="scroll"><table>')[1]
    return re.findall(r"<th(?:\s[^>]*)?>", tbl.split("</thead>")[0])


# ---------------------------------------------------------------------------
def test_osio_renderoityy_datasta():
    html = b.eo_by_tier_html(_eo_payload(), None)
    assert 'id="eo-by-tier"' in html
    assert "Player0 (TST)" in html and "Player14 (TST)" in html
    assert "Player15 (TST)" not in html, "top 15, ei enempaa"
    assert "EO = mean multiplier x 100" in html, "metric-teksti payloadista"
    assert "Gameweek 2 squads" in html and "after Gameweek 1" in html
    assert "Owned overall" in html


def test_n_nakyy_jokaisen_tason_otsikossa():
    html = b.eo_by_tier_html(_eo_payload(n=(200, 150, 120)), None)
    for label, n in (("top 1k", 200), ("top 10k", 150), ("top 100k", 120)):
        # Paataulukko JA kapteenitaulukko: molemmissa n otsikossa.
        assert html.count(f"{label}, n={n}") >= 2, f"{label}: n puuttuu otsikosta"
        assert not re.search(rf"<th[^>]*>[^<]*{re.escape(label)}(?!, n=)", html), \
            f"{label}: otsikko ilman n:aa"


def test_taso_ilman_n_ei_renderoidu():
    p = _eo_payload()
    del p["meta"]["sample"]["top10k"]["n_sampled"]
    html = b.eo_by_tier_html(p, None)
    assert 'id="eo-by-tier"' in html
    assert "top 10k" not in html, "prosentti ilman n:aa on puolikas luku"
    assert "top 1k, n=200" in html and "top 100k, n=120" in html
    # Koko sample puuttuu -> ei osiota lainkaan.
    p2 = _eo_payload()
    p2["meta"]["sample"] = {}
    assert b.eo_by_tier_html(p2, None) == ""


def test_tyhja_tai_puuttuva_data_ei_osiota():
    assert b.eo_by_tier_html(None, None) == ""
    assert b.eo_by_tier_html({}, None) == ""
    p = _eo_payload()
    p["players"] = []
    assert b.eo_by_tier_html(p, None) == ""
    p = _eo_payload()
    del p["meta"]["picks_gameweek"]
    assert b.eo_by_tier_html(p, None) == "", "ilman kierrosta ei voi sanoa mita mitattiin"


def test_kehallinen_payload_ei_renderoidu():
    # Negatiivinen kontrolli ensin: sama payload lipulla False renderoituu.
    ok = b.eo_by_tier_html(_eo_payload(circular=False), _mgr_payload())
    assert 'id="eo-by-tier"' in ok and 'id="elite-transfers"' in ok
    assert b.eo_by_tier_html(_eo_payload(circular=True), _mgr_payload()) == ""
    # Managers-payload kehallinen, EO ei: EO-osio jaa, siirtolohko putoaa.
    part = b.eo_by_tier_html(_eo_payload(), _mgr_payload(circular=True))
    assert 'id="eo-by-tier"' in part and 'id="elite-transfers"' not in part


def test_managers_lohko_n_ja_sisalto():
    html = b.eo_by_tier_html(_eo_payload(), _mgr_payload(n=180))
    assert 'id="elite-transfers"' in html
    assert html.count("n=180") == 3, "n JOKAISEN tason otsikossa managers-lohkossa"
    assert "Moved in: Mover (TST) 22.2%" in html
    assert "Moved out: Mover (TST) 22.2%" in html
    assert "40.0% made no transfer and 10.0% took a points hit." in html
    assert "transfers per manager" not in html, "wildcard vaaristaa keskiarvon"
    # Ilman managers-dataa ei lohkoa eika otsikkoa.
    assert 'id="elite-transfers"' not in b.eo_by_tier_html(_eo_payload(), None)


# --- Julkaisuportin 29.8 loydokset: yksi testi per loydos, jotta korjaus ei
# katoa seuraavassa muokkauksessa (portti B2-B6). --------------------------
def test_chipit_eivat_ole_samassa_virkkeessa_prosenttien_kanssa():
    """B4: 'X played a wildcard' luettiin prosentiksi.

    hold/hit ovat prosentteja, chipit lukumaaria 200:sta. Samassa virkkeessa
    '5 played a wildcard' luettiin 5 %:ksi (oikea 2,5 %) ja '15 played triple
    captain' (7,5 %) naytti pienemmalta kuin '7.0% took a points hit'.
    """
    html = b.eo_by_tier_html(_eo_payload(), _mgr_payload(n=180))
    assert "played a wildcard" not in html, "lukumaara ilman jakajaa"
    assert "Chips used, out of 180: wildcard 2, free hit 1." in html
    # Jakaja on saman tason n, ei EO-taulukon n.
    assert "out of 200" not in html.split('id="elite-transfers"')[1]


def test_kapteenit_vain_yhdessa_paikassa():
    """B5: kapteenitaulukko ja siirtolohko antoivat eri top-5:n.

    Aito tasapeli (kaksi pelaajaa samalla countilla) katkaistiin eri
    jarjestyksessa kahdessa tiedostossa, joten sivu naytti kaksi eri
    viidetta kapteenia samasta otoksesta. Kapteenit tulevat nyt vain
    taulukosta; siirtolohkossa ei ole omaa kapteenilistaa.
    """
    html = b.eo_by_tier_html(_eo_payload(), _mgr_payload())
    assert "Captain:" not in html, "siirtolohkon rinnakkainen kapteenilista"
    assert html.count("<caption>Share of each sample that captained") == 1


def test_sijoitustason_varaus_on_luvun_vieressa_joka_kierroksella():
    """B3: 'top 1k' on kierroksen tulos, ei taito. Varaus on introssa
    lukujen vieressa eika alaviitteessa, ja se renderoityy rank_gw:n
    arvosta riippumatta (ei haaraa joka voisi kadota kausivaihdossa)."""
    for rank_gw, picks_gw in ((1, 2), (7, 8), (19, 20)):
        p = _eo_payload()
        p["meta"]["rank_after_gw"] = rank_gw
        p["meta"]["picks_gameweek"] = picks_gw
        html = b.eo_by_tier_html(p, None)
        intro = html.split("</p>")[0]
        assert "Chip points count towards rank" in intro, (
            rank_gw, "varaus ei introssa")
        assert f"who led after Gameweek {rank_gw}, not who is best" in intro


def test_ei_mittaamattomia_eika_portin_poistamia_vaitteita():
    """B2 ja B6: mittaamaton vaite ja negatiivinen parallelismi pois."""
    html = b.eo_by_tier_html(_eo_payload(), _mgr_payload())
    for kielletty in (
            "never touched",              # B2: ei artefaktia lepaavista tileista
            "who scored, not who the top ranks chose",  # B6
            "no Gameweek 1 version",      # vastaus kysymattomaan kysymykseen
            "because holding is a choice",
            # Kierros 3: top10k:n ulos-listalla on kahdeksan pelaajaa tasan
            # 2.0 %:ssa ja sivu nayttaa niista kolme. "Five most common" on
            # vaite jonka linkitetty JSON kumoaa; katkaisu kerrotaan aaneen.
            "Five most common in each direction",
            # Metric luettelee kertoimet jo sulkulausekkeessa.
            "A captain counts double"):
        assert kielletty not in html, kielletty
    assert "Five per direction; where moves tie, the list cuts at five." in html


def test_viiden_lupaus_katoaa_kun_lista_on_lyhyempi():
    """Kierros 4, huomio 2: "Five per direction" on tosi vain jos listoissa
    ON viisi rivia. Ohut data (chip-viikko, osittainen ajo) tulostaisi
    vahemman, jolloin lause lupaisi enemman kuin sivu nayttaa.

    Positiivinen kontrolli ensin: taysi payload SAA lauseen. Sitten sama
    payload kolmella rivilla -> lause katoaa mutta lohko jaa.
    """
    lause = "Five per direction"
    assert lause in b.eo_by_tier_html(_eo_payload(), _mgr_payload())
    ohut = _mgr_payload()
    rivit = [{"id": i, "web_name": f"M{i}", "team": "TST", "pos": "FWD",
              "price": 8.0, "count": 6 - i, "pct": 3.0 - i} for i in range(3)]
    ohut["tiers"]["top10k"]["transfers_out"] = rivit
    html = b.eo_by_tier_html(_eo_payload(), ohut)
    assert 'id="elite-transfers"' in html, "lohko jaa, vain lupaus katoaa"
    assert lause not in html
    assert "M0 (TST) 3.0%" in html


def test_managers_lahdeviite_kantaa_oman_ajopaivan():
    m = _mgr_payload()
    m["meta"]["generated_at"] = "2026-08-29T11:11:00+00:00"
    html = b.eo_by_tier_html(_eo_payload(), m)
    assert ("data/fpl_elite_managers.json</a> in the public repository, "
            "generated 2026-08-29.") in html
    # Ilman paivaa lause paattyy silti pisteeseen, ei roikkuvaan pilkkuun.
    # Tarkastus rajataan siirtolohkoon: EO-taulukon oma lahdeviite kantaa
    # aina oman paivansa, joten koko sivun greppays osuisi siihen (vrt.
    # muisti: substring-osuma on sokea).
    m2 = _mgr_payload()
    m2["meta"].pop("generated_at", None)
    lohko = b.eo_by_tier_html(_eo_payload(), m2).split('id="elite-transfers"')[1]
    assert "data/fpl_elite_managers.json</a> in the public repository." in lohko
    assert "generated" not in lohko


def test_mobiilissa_nakyy_pelaaja_taso1_overall():
    html = b.eo_by_tier_html(_eo_payload(), None)
    ths = _main_table_ths(html)
    visible = [t for t in ths if "m-hide" not in t]
    hidden = [t for t in ths if "m-hide" in t]
    assert len(visible) == 3, visible
    assert len(hidden) == 2, hidden
    # Rivien solut noudattavat samaa jakoa kuin otsikot.
    first_row = re.search(r"<tbody><tr>(.*?)</tr>", html).group(1)
    assert first_row.count("m-hide") == 2


def test_copy_style_portti():
    html = b.eo_by_tier_html(_eo_payload(), _mgr_payload())
    text = _visible(html)
    assert "—" not in text, "em dash"
    low = text.lower()
    for word in ("odds", "solver", "optimis", "betting"):
        assert word not in low, word
    assert not re.search(r"\bPro\b", text), "Pro-sanaa ei copyssa"
    bl = publish_gate.load_blocklist()
    assert publish_gate.blocked_names(text, bl) == []


def test_oikea_data_ei_kehallinen_ja_n_mukana():
    """Repoon committoitu payload on se jonka sivu nayttaa: lippu pois ja
    n joka tasolla. Jos tiedosto puuttuu (esim. clean checkout ilman ajoa),
    sivu jaa ilman osiota, mika on sallittu tila."""
    path = ROOT / "data" / "fpl_elite_ownership.json"
    if not path.exists():
        return
    eo = json.loads(path.read_text(encoding="utf-8"))
    assert eo["meta"]["circular"] is False
    assert eo["meta"]["picks_gameweek"] > eo["meta"]["rank_after_gw"]
    html = b.eo_by_tier_html(eo, None)
    assert 'id="eo-by-tier"' in html
    for key, s in eo["meta"]["sample"].items():
        assert f"{b.EO_TIER_LABELS[key]}, n={s['n_sampled']}" in html
    mpath = ROOT / "data" / "fpl_elite_managers.json"
    if mpath.exists():
        mgr = json.loads(mpath.read_text(encoding="utf-8"))
        assert mgr["meta"]["circular"] is False
        html2 = b.eo_by_tier_html(eo, mgr)
        assert 'id="elite-transfers"' in html2
        for key, t in mgr["tiers"].items():
            if t["n_sampled"]:
                assert f"{b.EO_TIER_LABELS[key]}, n={t['n_sampled']}</h4>" in html2


def test_render_page_kytkenta_lukee_polut():
    """render_page kutsuu osiota EO_PATH/ELITE_MGR_PATH:sta, ei kovakoodattua."""
    src = (ROOT / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    assert "eo_by_tier_html(_load_json(EO_PATH), _load_json(ELITE_MGR_PATH))" in src
    assert "{eo_by_tier}" in src
    assert copy.deepcopy(b.EO_TIER_LABELS) == {
        "top1k": "top 1k", "top10k": "top 10k", "top100k": "top 100k"}
