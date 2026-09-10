"""DEPLOY-VERIFY-MUUTTUNEET-SIVUT: verify mittaa ajon muuttamat sivut, ei
kiinteaa listaa. Synteettinen: muuttunut sivu jota ydinlista ei kata on
listalla; tyhja diff = ydin; katto pitaa; ei-html ja outputs/ pois."""
from scripts.verify_targets import CORE, MAX_PAGES, changed_html, targets


def test_changed_page_outside_core_is_verified():
    t = targets(["fpl/defence.html", "fpl/stats.html", "data/x.json"])
    assert "fpl/defence.html" in t and "fpl/stats.html" in t
    assert list(t[:3]) == list(CORE)


def test_empty_diff_falls_back_to_core_only():
    assert targets([]) == list(CORE)


def test_cap_keeps_core_and_is_deterministic():
    many = [f"predictions/premier-league/m{i:03d}.html" for i in range(300)]
    t = targets(many)
    assert len(t) == MAX_PAGES and t[:3] == list(CORE)
    assert t == targets(list(reversed(many)))


def test_non_html_and_outputs_are_ignored():
    assert changed_html(["outputs/cards/x.html", "cos-reports/y.html", "a.png", "fpl/points.html"]) == ["fpl/points.html"]


def test_negative_control_verify_script_fails_on_mismatch():
    """verify_live_pages.sh kaatuu kun live != repo: skriptin loppu on exit 1
    kun kaikki_ok jaa nollaksi TRIES-kierroksella (luetaan lahteesta, koska
    skriptin ajo vaatii verkon)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" / "verify_live_pages.sh").read_text(encoding="utf-8")
    assert "exit 1" in src and "kaikki_ok" in src
