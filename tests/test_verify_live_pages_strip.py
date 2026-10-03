"""verify_live_pages.sh riisuu Cloudflaren injektoimat lisaykset ennen md5-vertailua.

3.10.2026: CF Pages Web Analytics (kytketty 2.10) lisaa beaconin jokaisen
sivun </body>:n eteen. Riisunta tunsi vain challenge-skriptin, joten live !=
repo oli tosi joka sivulla ja viisi sivuja kirjoittavaa workflow'ta oli
punaisena ~15 h (fpl-data-refresh, accuracy-log, ...). Vanha testi luki
skriptin lahdetta; tama AJAA skriptin file://-URLia vasten, joten se mittaa
mekanismin eika merkkijonoa.

Erotteleva pari: sama beacon + oikea sisaltoero EI saa lapaista (riisunta ei
saa piilottaa deploy-vikaa), ja ilman beaconin riisuntaa positiivinen tapaus
kaatuu (todistettu mutaatiolla 3.10).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_live_pages.sh"
SITE_DEPLOY = ROOT / ".github" / "site-repo" / "deploy.yml"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(not BASH or not shutil.which("curl") or not shutil.which("md5sum"),
                                reason="bash, curl tai md5sum puuttuu")

REPO_HTML = (
    "<!DOCTYPE html>\n<html><body>\n<p>GW6</p>\n"
    '<script defer src="/ref-bridge.js"></script>\n\n</body>\n</html>\n'
)
# Muoto kopioitu goaliq.app/fpl.html:sta 3.10 (token vaihdettu).
BEACON = ("<!-- Cloudflare Pages Analytics --><script defer src='https://static.cloudflareinsights.com/"
          "beacon.min.js' data-cf-beacon='{\"token\": \"" + "0" * 32 + "\"}'></script>"
          "<!-- Cloudflare Pages Analytics -->")
CHALLENGE = ("<script>(function(){function c(){var b=a.contentDocument||a.contentWindow.document;"
             "if(b){var d=b.createElement('script');d.innerHTML=\"window.__CF$cv$params={r:'abc123'}\";"
             "b.getElementsByTagName('head')[0].appendChild(d)}}})();</script>")


def run_verify(tmp_path: Path, live_html: str) -> subprocess.CompletedProcess:
    repo = tmp_path / "repo"
    live = tmp_path / "live"
    repo.mkdir()
    live.mkdir()
    (repo / "fpl.html").write_text(REPO_HTML, encoding="utf-8", newline="\n")
    (live / "fpl.html").write_text(live_html, encoding="utf-8", newline="\n")
    env = {k: v for k, v in os.environ.items() if k != "GH_TOKEN"}
    env.update(LIVE_BASE=live.as_uri(), VERIFY_TRIES="1", VERIFY_SLEEP="0")
    return subprocess.run([BASH, str(SCRIPT), "fpl.html"], cwd=repo, env=env,
                          capture_output=True, text=True, timeout=60)


def inject(html: str, payload: str) -> str:
    return html.replace("\n</body>", "\n" + payload + "</body>", 1)


def test_identical_page_passes(tmp_path):
    r = run_verify(tmp_path, REPO_HTML)
    assert r.returncode == 0 and "OK (yritys 1)" in r.stdout, r.stdout + r.stderr


def test_cf_analytics_beacon_is_stripped(tmp_path):
    r = run_verify(tmp_path, inject(REPO_HTML, BEACON))
    assert r.returncode == 0 and "OK (yritys 1)" in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize("order", ["challenge-first", "beacon-first"])
def test_beacon_and_challenge_on_same_line(tmp_path, order):
    payload = CHALLENGE + BEACON if order == "challenge-first" else BEACON + CHALLENGE
    r = run_verify(tmp_path, inject(REPO_HTML, payload))
    assert r.returncode == 0 and "OK (yritys 1)" in r.stdout, r.stdout + r.stderr


def test_real_difference_still_fails_with_beacon(tmp_path):
    """Negatiivinen kontrolli: riisunta ei saa piilottaa vanhaa deployta."""
    stale = inject(REPO_HTML.replace("GW6", "GW5"), BEACON)
    r = run_verify(tmp_path, stale)
    assert r.returncode != 0 and "OK (yritys" not in r.stdout, r.stdout + r.stderr


def test_site_repo_deploy_strips_beacon_first():
    """Site-repon deploy.yml (SITE-REPO-SPLIT) kayttaa samaa beacon-riisuntaa,
    ja se ajetaan ennen challenge-riisuntaa."""
    sh = SCRIPT.read_text(encoding="utf-8")
    yml = SITE_DEPLOY.read_text(encoding="utf-8")
    expr = re.search(r"^BEACON_STRIP='([^']+)'", sh, re.M).group(1)
    assert f"BEACON='{expr}'" in yml
    assert 'sed -e "$BEACON" -e "$STRIP"' in yml
