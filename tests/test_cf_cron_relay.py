# -*- coding: utf-8 -*-
"""CF-workerin cron ei voi eriytya siita workflow'sta jota se laukaisee.

🔴 MIKSI TAMA ON OLEMASSA (12.9.2026). `fp-dispatch-relay.yml` ajaa slotilla
`50 * * * *`, ja sen oma kommentti perustelee minuutin: ":50 -> viimeisen
60 min ikkuna kattaa fp-slotit :00, :15, :17, :20, :40, :45." Worker joka
laukaisee relayn EI saa ajaa eri hetkella: silloin relayn lookback ei kata
samoja slotteja, ja korjaus nayttaisi toimivalta samalla kun se laukaisee
relayn hetkella jolta se ei nae mitaan due-slottia.

Kaksi lukua samasta kysymyksesta kahdessa tiedostossa on tasan se vikaluokka
jota vastaan koko autopilot on rakennettu. Tama testi sitoo ne yhteen.

Vartioi myos ettei tokenia vahingossa kirjoiteta konfiguraatioon: secret
kuuluu `wrangler secret put`iin eika mihinkaan tiedostoon.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "cf-worker" / "fp-cron-relay"
WRANGLER = WORKER_DIR / "wrangler.jsonc"
WORKER_SRC = WORKER_DIR / "src" / "index.js"
RELAY = ROOT / ".github" / "workflows" / "fp-dispatch-relay.yml"


def _jsonc(txt: str) -> dict:
    """Riittava JSONC-lukija: poistaa // -kommentit rivin alusta ja lopusta.

    Ei yleiskaytto-parseri — tama tiedosto on meidan, ja jos siihen ilmestyy
    lohkokommentti tai merkkijonon sisainen `//`, testi kaatuu JSON-virheeseen
    eika vaikene (fail-closed).
    """
    rivit = []
    for r in txt.split("\n"):
        i = r.find("//")
        rivit.append(r[:i] if i >= 0 else r)
    return json.loads("\n".join(rivit))


def _relay_cronit() -> list[str]:
    """Relayn cron-rivit YAMLista ilman yaml-riippuvuutta."""
    txt = RELAY.read_text(encoding="utf-8")
    return re.findall(r'^\s*-\s*cron:\s*"([^"]+)"', txt, re.M)


@pytest.mark.skipif(not WRANGLER.exists(), reason="workeria ei ole tassa puussa")
def test_workerin_cron_on_sama_kuin_relayn():
    """🔴 Ydintesti."""
    conf = _jsonc(WRANGLER.read_text(encoding="utf-8"))
    worker = conf.get("triggers", {}).get("crons") or []
    relay = _relay_cronit()
    assert relay, "relayn cron-riveja ei loytynyt — onko tiedosto nimetty uudelleen?"
    assert worker, "workerin triggers.crons on tyhja"
    assert sorted(worker) == sorted(relay), (
        f"worker ajaa slotilla {worker} mutta relay julistaa {relay}. "
        f"Relayn lookback on 60 min ja sen minuutti on perusteltu sen omassa "
        f"kommentissa; eri hetki tarkoittaa etta worker laukaisee relayn "
        f"silloin kun relay ei nae due-slotteja."
    )


@pytest.mark.skipif(not WORKER_SRC.exists(), reason="workeria ei ole tassa puussa")
def test_worker_laukaisee_oikean_workflown_oikeassa_repossa():
    src = WORKER_SRC.read_text(encoding="utf-8")
    # 27.9.2026: relay siirtyi goaliq-appista tahan repoon. Vanha kohde
    # (Veikkoville/goaliq-app) kuluttaisi yksityisen repon Actions-minuutteja.
    assert "repo: 'GoalIQ/football-prediction'" in src
    assert "Veikkoville/goaliq-app'" not in src
    assert "fp-dispatch-relay.yml" in src
    assert RELAY.exists(), "worker laukaisee workflow'ta jota ei ole"
    # Token scopattu GoalIQ/football-prediction: eri secret kuin vanha.
    assert "env.GITHUB_DISPATCH_TOKEN_FP" in src
    assert not re.search(r"env\.GITHUB_DISPATCH_TOKEN(?!_FP)\b", src), "vanha goaliq-app-token"


def _ilman_kommentteja(js: str) -> str:
    """Kommentit pois ennen skannausta.

    🔴 Tama portti vartioi LOGIIKKAA, ei copya, ja siksi kommentit
    poistetaan — toisin kuin `test_chip_vaite_ei_palaa_copyyn.py`:ssa, jossa
    kommentti ON skannausyksikko koska greppaava ihminen ei erota sita
    copysta. Ero on tietoinen: workerin otsikkokommentissa on mittaustaulukko
    (fpl-transfer-watch 32 %, fpl-data-refresh 54 % ...) joka on perustelu
    eika kohdelista, ja se nappasi taman testin ensimmaisella ajolla.
    """
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return "\n".join(r[:r.find("//")] if "//" in r else r
                     for r in js.split("\n"))


@pytest.mark.skipif(not WORKER_SRC.exists(), reason="workeria ei ole tassa puussa")
def test_worker_ei_toista_relayn_logiikkaa():
    """Worker on tarkoituksella tyhma. Jos siihen ilmestyy cron-laskentaa tai
    kohdelistaa, samaan kysymykseen on kaksi lukijaa."""
    src = _ilman_kommentteja(WORKER_SRC.read_text(encoding="utf-8"))
    kiellettyja = [s for s in ("fpl-transfer-watch", "accuracy-log",
                               "fpl-data-refresh", "ucl-refresh",
                               "LOOKBACK", "parse_cron", "count_firings")
                   if s in src]
    assert not kiellettyja, (
        f"worker sisaltaa relayn logiikkaa tai kohdelistaa: {kiellettyja}. "
        f"Relay lukee cronit fp-repon omasta tiedostosta (yksi lukija); "
        f"kopio tassa eriytyisi.")


@pytest.mark.skipif(not WRANGLER.exists(), reason="workeria ei ole tassa puussa")
def test_tokenia_ei_ole_konfiguraatiossa():
    """Secret kuuluu `wrangler secret put`iin. Tama kaatuu jos joku panee sen
    `vars`-lohkoon tai kovakoodaa sen lahteeseen."""
    conf = _jsonc(WRANGLER.read_text(encoding="utf-8"))
    vars_ = conf.get("vars") or {}
    paha = [k for k in vars_ if re.search(r"token|secret|pat|key", k, re.I)]
    assert not paha, f"wrangler.jsonc:n vars-lohkossa on salaisuus: {paha}"
    src = WORKER_SRC.read_text(encoding="utf-8")
    # GitHubin PAT-muodot. Fine-grained: github_pat_..., klassinen: ghp_...
    assert not re.search(r"\b(github_pat_|ghp_|gho_|ghs_)\w", src), (
        "lahteessa nayttaa olevan PAT kovakoodattuna")


@pytest.mark.skipif(not WORKER_SRC.exists(), reason="workeria ei ole tassa puussa")
def test_puuttuva_token_ei_heita():
    """Puuttuva secret on konfiguraatiotila, ei poikkeus. Heitto saisi CF:n
    yrittamaan uudelleen ja tayttaisi lokin samalla rivilla — sama paatos kuin
    relayn omassa PAT-tarkistuksessa (paattaa ajon vihreana + ohje lokiin)."""
    src = WORKER_SRC.read_text(encoding="utf-8")
    i = src.index("async function dispatch")
    runko = src[i:i + 1400]
    assert "if (!token)" in runko, "puuttuvaa tokenia ei tarkisteta"
    assert "throw" not in runko.split("return {")[0], (
        "puuttuva token heittaa poikkeuksen")
    assert "wrangler secret put" in runko, (
        "virheviesti ei kerro miten secret asetetaan")


@pytest.mark.skipif(not WORKER_SRC.exists(), reason="workeria ei ole tassa puussa")
def test_fetch_ei_paljasta_tokenia():
    """`/config` on tarkistuspinta ilman dashboardia. Se ei saa palauttaa
    arvoa, vain booleanin."""
    src = WORKER_SRC.read_text(encoding="utf-8")
    i = src.index("async fetch(")
    runko = src[i:]
    assert "token_set: Boolean(" in runko, "token_set ei ole boolean"
    assert "GITHUB_DISPATCH_TOKEN_FP," not in runko, "token palautetaan arvona"


@pytest.mark.skipif(not WORKER_SRC.exists(), reason="workeria ei ole tassa puussa")
def test_github_kutsussa_on_user_agent():
    """GitHubin API vastaa 403 ilman User-Agentia. Se olisi vika joka nakyisi
    vain workerin lokissa eli ei missaan."""
    src = WORKER_SRC.read_text(encoding="utf-8")
    assert "'User-Agent'" in src or '"User-Agent"' in src
    assert "X-GitHub-Api-Version" in src
    assert "res.status === 204" in src, (
        "onnistumista ei tarkisteta statuksesta; 404 (puuttuva Actions-oikeus) "
        "nayttaisi onnistumiselta")


@pytest.mark.skipif(not WRANGLER.exists(), reason="workeria ei ole tassa puussa")
def test_readme_ei_lupaa_julkista_urlia():
    """🔴 Oma ristiriita, loydetty 12.9 juuri ennen deployta.

    `wrangler.jsonc` sanoo `workers_dev: false` eli julkista URLia EI luoda,
    mutta README kaski verifioida `curl https://fp-cron-relay.<sub>.workers.dev/config`.
    Villen ensimmainen verifiointiaskel olisi kaatunut osoitteeseen jota ei ole,
    ja se nayttaisi siltä etta deploy epaonnistui.

    Portti sitoo ne: jos `workers_dev` on false, README ei saa kaskea curlaamaan
    workers.dev-osoitetta. Jos joku avaa `workers_dev: true`, tama testi
    lakkaa vaatimasta sita — mutta silloin se on tietoinen valinta.
    """
    conf = _jsonc(WRANGLER.read_text(encoding="utf-8"))
    readme = (WORKER_DIR / "README.md").read_text(encoding="utf-8")
    if conf.get("workers_dev") is False:
        ohjeet = [r for r in readme.split(chr(10))
                  if "workers.dev" in r and ("curl" in r or "https://" in r)
                  and not r.lstrip().startswith(("*", ">", "`test_"))]
        # Sallittu: maininta siita ETTEI URLia ole.
        ohjeet = [r for r in ohjeet if "EI julkista" not in r and "ei tarvitse" not in r]
        assert not ohjeet, (
            f"README kaskee curlaamaan workers.dev-osoitetta mutta "
            f"workers_dev on false: {ohjeet}")


@pytest.mark.skipif(not WRANGLER.exists(), reason="workeria ei ole tassa puussa")
def test_readme_kertoo_miten_toteuma_mitataan():
    """Deployn ehto on mittaus. README ei saa jattaa sita auki."""
    readme = (WORKER_DIR / "README.md").read_text(encoding="utf-8")
    assert "cron_realization.py" in readme
    assert "wrangler secret list" in readme, "secretin tarkistus puuttuu"
    assert "workflow_dispatch" in readme, "relayn laukeamisen tarkistus puuttuu"


def test_readme_kaskee_mittaamaan_seuraavan_slotin_ja_triggers_deployn():
    """17.9.2026: cron ei lauennut 111 slottiin vaikka `wrangler deploy` tulosti
    schedulen; `wrangler triggers deploy` korjasi heti. Deployn tuloste ei ole
    todiste triggerista. README:n on kaskettava mittaamaan seuraava slotti ja
    nimettava korjaus, muuten sama viisi paivaa toistuu seuraavalla deployllä."""
    readme = (WORKER_DIR / "README.md").read_text(encoding="utf-8")
    assert "wrangler triggers deploy" in readme, "korjauskomento puuttuu READMEsta"
    assert "wrangler tail fp-cron-relay --format json" in readme, (
        "seuraavan slotin mittaus (tail json irrallisena) puuttuu READMEsta")
    # Vanha vaite 'mittari laskee vain schedule-ajot' oli totta 10.9 ja vaara 11.9
    # alkaen; jos se palaa, worker nayttaa tehottomalta vaarasta syysta.
    assert "laskee **vain `schedule`-ajot**" not in readme, (
        "README vaittaa yha etta mittari laskee vain schedule-ajot (korjattu 11.9)")

