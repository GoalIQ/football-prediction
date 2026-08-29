"""Portit vahdille joka vertaa FPL-tilin rivia jaadytettyyn runkoon.

Vahdin koko arvo on siina etta se KAATUU kun rivit eroavat. Siksi jokaiselle
vihrealle haaralle on negatiivinen kontrolli: testi joka osoittaa etta sama
koodipolku palauttaa 1 kun sen kuuluu.

Tausta: entryn rivi valittiin kasin 23.7, ENNEN 13.8:n P0-korjausta joka
muutti mallin XI:n. Mikaan ei huomannut eroa, koska mikaan ei katsonut.
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from scripts import verify_model_entry_matches_freeze as w


def _frozen(gw: int, deadline: _dt.datetime, ids: list[int],
            captain: int) -> dict:
    xi = [{"id": i, "web_name": f"P{i}", "team_short": "XXX", "pos": 3,
           "club": "X", "price": 50, "xp": 1.0} for i in ids[:11]]
    bench = [{"id": i, "web_name": f"P{i}", "team_short": "XXX", "pos": 3,
              "club": "X", "price": 40, "xp": 0.5} for i in ids[11:]]
    return {
        "meta": {"gw": gw, "deadline": deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "frozen_at": "2026-08-20T12:00:00Z"},
        "captain": captain, "vice_captain": ids[1],
        "xi": xi, "bench": bench,
    }


@pytest.fixture
def frozen_dir(tmp_path, monkeypatch):
    d = tmp_path / "model_squad_frozen"
    d.mkdir()
    monkeypatch.setattr(w, "FROZEN_DIR", d)
    e = tmp_path / "model_squad_exceptions"
    e.mkdir()
    monkeypatch.setattr(w, "EXCEPTIONS_DIR", e)
    return d


def _write(d, gw, deadline, ids, captain=101):
    (d / f"gw{gw}.json").write_text(
        json.dumps(_frozen(gw, deadline, ids, captain)), encoding="utf-8")


IDS = list(range(101, 116))          # 15 pelaajaa
# HUOM: GW1:n oikea deadline (21.8.2026) on TULEVAISUUDESSA kun tama
# kirjoitettiin, joten sita ei voi kayttaa "mennyt deadline" -tapauksena.
# Ensimmainen versio kaytti sita ja kolme testia ajoi hiljaa vaaraan
# haaraan — ne olisivat menneet vihreiksi vasta 21.8 ja vaarin perustein.
PAST = _dt.datetime(2020, 8, 21, 17, 30, tzinfo=_dt.timezone.utc)
FUTURE = _dt.datetime(2099, 1, 1, 12, 0, tzinfo=_dt.timezone.utc)


def test_no_freeze_is_not_an_error(frozen_dir, monkeypatch):
    """Ennen kauden ensimmaista freezea hakemisto on tyhja. Se EI ole vika."""
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 0


def test_before_deadline_prints_squad_and_passes(frozen_dir, monkeypatch, capsys):
    """Rivin syottaminen on kasityota, joten puuttuva syotto ei ole viela
    virhe — mutta tuloste on annettava syotettavassa muodossa."""
    _write(frozen_dir, 1, FUTURE, IDS)
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 0
    out = capsys.readouterr().out
    assert "KAPTEENI" in out
    assert "PENKKI" in out
    assert "P101" in out


def test_after_deadline_match_passes(frozen_dir, monkeypatch):
    _write(frozen_dir, 1, PAST, IDS)
    monkeypatch.setattr(w, "fetch_picks", lambda e, g: (
        [{"element": i, "is_captain": i == 101} for i in IDS], "200"))
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 0


def test_after_deadline_mismatch_fails(frozen_dir, monkeypatch, capsys):
    """NEGATIIVINEN KONTROLLI. Tama on koko vahdin olemassaolon syy: yksi
    vaara pelaaja tilillä = julkinen vaite osoittaa joukkueeseen jota malli
    ei valinnut."""
    _write(frozen_dir, 1, PAST, IDS)
    wrong = IDS[:-1] + [999]
    monkeypatch.setattr(w, "fetch_picks", lambda e, g: (
        [{"element": i, "is_captain": i == 101} for i in wrong], "200"))
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 1
    out = capsys.readouterr().out
    assert "EI VASTAA" in out
    assert "P115" in out       # jaadytetyssa mutta ei tilillä
    assert "999" in out        # tilillä mutta ei jaadytetyssa


def test_captain_difference_alone_fails(frozen_dir, monkeypatch, capsys):
    """15/15 voi tasmata ja rivi olla silti vaara: kapteeni on
    kaksinkertainen pistevaikutus."""
    _write(frozen_dir, 1, PAST, IDS, captain=101)
    monkeypatch.setattr(w, "fetch_picks", lambda e, g: (
        [{"element": i, "is_captain": i == 102} for i in IDS], "200"))
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 1
    assert "KAPTEENI eroaa" in capsys.readouterr().out


def test_missing_picks_after_deadline_fails(frozen_dir, monkeypatch):
    """404 ENNEN deadlinea on normaali; deadlinen JALKEEN se tarkoittaa
    ettei tilia ole pelattu — ja silloin koko kausikisa on tyhja."""
    _write(frozen_dir, 1, PAST, IDS)
    monkeypatch.setattr(w, "fetch_picks", lambda e, g: (None, "404"))
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 1


def test_latest_frozen_sorts_numerically(frozen_dir):
    """gw10 > gw9. Merkkijonolajittelu antaisi gw9:n ja vahti vertaisi
    vaaraa kierrosta koko loppukauden."""
    for gw in (2, 9, 10):
        _write(frozen_dir, gw, PAST, IDS)
    assert w.latest_frozen().name == "gw10.json"


# ---------------------------------------------------------------- kirjattu poikkeus (29.8)
# GW2: Ville pelasi wildcardin korjatulla mallilla, freeze oli vanhan mallin
# kanta. Vahti kaatui oikein mutta padotti commit-askeleen -> data jaassa
# 3 ajoa. Poikkeustiedosto muuttaa eron varoitukseksi VAIN silla kierroksella
# ja VAIN kun syy on kirjattu; se ei ole vapaakortti.

def _write_exception(d, gw, reason="Ville pelasi wildcardin korjatulla mallilla",
                     decided_by="Ville", decided_at="2026-08-28"):
    # d = frozen_dir; poikkeus menee sen RINNALLE (EXCEPTIONS_DIR), ei sisaan.
    (w.EXCEPTIONS_DIR / f"gw{gw}.json").write_text(json.dumps({
        "gw": gw, "reason": reason, "decided_by": decided_by,
        "decided_at": decided_at}), encoding="utf-8")


def _mismatch(monkeypatch):
    wrong = IDS[:-1] + [999]
    monkeypatch.setattr(w, "fetch_picks", lambda e, g: (
        [{"element": i, "is_captain": i == 101} for i in wrong], "200"))
    monkeypatch.setattr("sys.argv", ["x"])


def test_recorded_exception_turns_mismatch_into_warning(frozen_dir, monkeypatch, capsys):
    _write(frozen_dir, 1, PAST, IDS)
    _write_exception(frozen_dir, 1)
    _mismatch(monkeypatch)
    assert w.main() == 0
    out = capsys.readouterr().out
    assert "::warning::" in out and "KIRJATTU POIKKEUS" in out
    assert "::error::" not in out
    assert "P115" in out and "999" in out     # ero nakyy silti lokissa


def test_exception_for_another_gw_does_not_apply(frozen_dir, monkeypatch, capsys):
    """NEGATIIVINEN KONTROLLI: GW2:n poikkeus ei vaienna GW1:n eroa."""
    _write(frozen_dir, 1, PAST, IDS)
    _write_exception(frozen_dir, 2)
    _mismatch(monkeypatch)
    assert w.main() == 1
    assert "EI VASTAA" in capsys.readouterr().out


@pytest.mark.parametrize("bad", [
    {"reason": ""},                    # syy puuttuu
    {"decided_by": " "},               # paattaja puuttuu
    {"gw": 2},                         # vaara kierros tiedoston sisalla
])
def test_broken_exception_is_an_error_not_a_free_pass(frozen_dir, monkeypatch, capsys, bad):
    _write(frozen_dir, 1, PAST, IDS)
    d = {"gw": 1, "reason": "x", "decided_by": "Ville", "decided_at": "2026-08-28"}
    d.update(bad)
    (w.EXCEPTIONS_DIR / "gw1.json").write_text(json.dumps(d), encoding="utf-8")
    _mismatch(monkeypatch)
    assert w.main() == 1
    assert "Poikkeustiedosto on rikki" in capsys.readouterr().out


def test_exception_covers_captain_only_difference(frozen_dir, monkeypatch, capsys):
    _write(frozen_dir, 1, PAST, IDS, captain=101)
    _write_exception(frozen_dir, 1)
    monkeypatch.setattr(w, "fetch_picks", lambda e, g: (
        [{"element": i, "is_captain": i == 102} for i in IDS], "200"))
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 0
    assert "KAPTEENI eroaa" in capsys.readouterr().out


def test_stale_exception_is_flagged_when_squads_match(frozen_dir, monkeypatch, capsys):
    _write(frozen_dir, 1, PAST, IDS)
    _write_exception(frozen_dir, 1)
    monkeypatch.setattr(w, "fetch_picks", lambda e, g: (
        [{"element": i, "is_captain": i == 101} for i in IDS], "200"))
    monkeypatch.setattr("sys.argv", ["x"])
    assert w.main() == 0
    assert "vanhentunut" in capsys.readouterr().out


def test_live_gw2_exception_file_is_valid():
    """Repon oikea poikkeus (GW2, 29.8) lapaisee saman validoinnin kuin testit."""
    if not (w.EXCEPTIONS_DIR / "gw2.json").exists():
        pytest.skip("model_squad_exceptions/gw2.json poistettu (GW3 jalkeen ok)")
    d, err = w.load_exception(2)
    assert err is None, err
    assert d["decided_by"] == "Ville"


def test_frozen_dir_holds_only_freezes():
    """Graderit ja freeze lukevat freeze-kansion glob("gw*.json"):lla ja
    olettavat jokaisen tiedoston olevan runko (meta.gw). 29.8 07:06
    gw2.exception.json siella kaatoi grade_model_squad_gw:n (int(None)) ja
    padotti commit-askeleen — sama vikaluokka jota poikkeus yritti korjata."""
    import re
    if not w.FROZEN_DIR.exists():
        pytest.skip("ei freezeja viela")
    bad = [p.name for p in w.FROZEN_DIR.iterdir()
           if not re.fullmatch(r"gw\d+\.json", p.name)]
    assert not bad, f"freeze-kansiossa muuta kuin gw{{N}}.json: {bad}"


def test_exception_in_frozen_dir_is_not_read(frozen_dir, monkeypatch, capsys):
    """NEGATIIVINEN KONTROLLI: vanhaan paikkaan (freeze-kansio) kirjoitettu
    poikkeus EI vaienna eroa — se olisi taas graderien tiella."""
    _write(frozen_dir, 1, PAST, IDS)
    (frozen_dir / "gw1.exception.json").write_text(json.dumps({
        "gw": 1, "reason": "x", "decided_by": "Ville", "decided_at": "2026-08-28"}),
        encoding="utf-8")
    _mismatch(monkeypatch)
    assert w.main() == 1


# ---------------------------------------------------------------- workflow-rakenne
# Vahti ei tuota dataa. Jos se saa padota commit-askeleen, yksi entryn ero
# jaadyttaa projektiot, price watchin ja freezet (mitattu 28.-29.8: 3 ajoa).
# Sama vikaluokka kuin stats-gate 21.8 ja player-gw 14.8: fail-safe jaatyy
# alavirtaan.

WORKFLOW = w.config.PROJECT_ROOT / ".github" / "workflows" / "fpl-data-refresh.yml"
# Askeleet jotka eivat saa padota commit-askelta: vahti (ei tuota dataa) ja
# graderit (kirjoittavat omaa lokiaan; jos gradaus kaatuu, projektiot, price
# watch ja freezet on silti pushattava). 29.8 07:06: grade_model_squad_gw
# kaatui ja kaikki sen jalkeinen skipattiin — toinen jaatyminen samana aamuna.
WATCH_STEPS = {
    "Verify FPL entry matches the frozen squad": "verify_entry",
    "Grade finished frozen gameweeks (xP vs actual)": "grade_xp",
    "Grade finished model squad gameweeks": "grade_squad",
    "Grade logged gameweek calls": "grade_calls",
}


def _refresh_steps():
    import yaml
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return doc["jobs"]["build-and-commit"]["steps"]


def test_watch_steps_cannot_block_the_commit():
    steps = _refresh_steps()
    by_name = {s.get("name"): s for s in steps}
    health = by_name["Step health (fail loud, data jo pushattu)"]["run"]
    for name, step_id in WATCH_STEPS.items():
        st = by_name[name]
        assert st.get("continue-on-error") is True, f"{name}: continue-on-error puuttuu"
        assert st.get("id") == step_id, f"{name}: id {step_id} puuttuu"
        assert f"steps.{step_id}.outcome" in health, (
            f"{name}: ei Step healthissa -> punainen ei enaa nay missaan")


def test_watch_steps_run_before_the_commit():
    """Jos vahti siirtyy commitin jalkeen, edellinen testi on tyhja."""
    names = [s.get("name") for s in _refresh_steps()]
    commit = next(i for i, n in enumerate(names) if n and n.startswith("Commit + push"))
    for name in WATCH_STEPS:
        assert names.index(name) < commit
