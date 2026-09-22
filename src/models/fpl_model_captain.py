"""MALLIN KAPTEENI: yksi lukija kysymykselle "kuka on mallin kapteeni" (22.9.2026).

TAUSTA (julkaisutarkistaja 22.9, web-IA kierros 2). pro.goaliq.app:n This
week -paatoskortti nayttaa kirjautumattomalle "The model's captain, GW{n}" +
"Squad: our FPL entry 116920, GW{picks_gw} picks". Lahde oli
`/api/fantasy/rate-team?entry=116920`, joka lukee FPL:n JULKAISEMAT pickit.
FPL julkaisee kierroksen pickit vasta deadlinella, mutta mallin runko
jaadytetaan noin 29 h ennen deadlinea (`data/model_squad_frozen/gw{N}.json`,
mitattu GW5: freeze 17.9 12:18Z, deadline 18.9 17:30Z). Siina valissa
goaliq.app/fpl nimeaa julkisesti "GW{N} Model squad captain" freezesta
(`gw_calls.model_captain`), ja rate-team nimesi saman otsikon alle kapteenin
EDELLISEN kierroksen rungosta. Jos freezen siirto toi eri kapteenin, kaksi
julkista pintaa nimesi eri pelaajan.

SAANTO (CLAUDE.md 6a kohta 1): tama moduuli on AINOA paikka joka paattaa
kumpi lahde on voimassa, ja sen vastaus kertoo lahteensa.

  - Jos kortin kierrokselle on freeze, kapteeni tulee SIITA, saman
    maaritelman kautta kuin gw_calls-loki (`gw_calls.model_captain_call`).
    `source: "frozen"`.
  - Muuten nykyinen polku: rate-team mallin entrylle, kapteeni rungon
    XI:n korkein GW-xP (sama saanto kuin freezessa). `source: "entry_picks"`
    ja `picks_gw` = FPL:n julkaisemien pickien kierros.

Kortin kierros paatetaan KELLOSTA, ei artefaktista: ensimmainen kierros
jonka FPL:n `deadline_time` on edessa. `meta.deadline_gameweek` tulee
3 h valein ajettavasta artefaktista ja voi laahata tunteja deadlinen
jalkeen. Jos rate-team silti nimeaa kierroksen jolle on freeze (artefakti
laahaa deadlinen jalkeen), kapteeni tulee freezesta: kierros on lukittu,
ja sen kapteeni on se jonka malli lukitsi.

FAIL-CLOSED: jos freeze on olemassa mutta rikki (JSON, kierrosnumero,
kapteeni ei rungossa), vastaus on virhe eika rate-teamin arvaus. Vaara
nimi otsikon "The model's captain" alla on pahempi kuin puuttuva kortti.

REITTI ON VAITE (julkaisutarkistaja 22.9, lahderivi): frozen-kortin rivi
sanoo "logged on goaliq.app/fpl". Se on tosi vain jos SAMAN checkoutin
`fpl.html` nimeaa kutsulokissa saman kapteenin samalle kierrokselle
(`logged_model_captain`). Render deployaa koko repon ja hub-deploy saman
commitin sivun, joten tarkistus mittaa sita sivua jonka lukija avaa.
Muuten 503: freeze voi olla pushattu ilman sivua (`log_gw_calls` on
continue-on-error, build_fpl_page exit 2 = notice), ja 4.9 GW3:n kasin
tehty uudelleenfreeze (fe2043486) muutti rungon ja lokin mutta ei sivua,
jolloin sivu nimesi vanhan kapteenin. Pelkka gw_calls.json-tarkistus ei
olisi nahnyt sita. Jaljelle jaava aukko on hub-deployn kaatuminen pushin
jalkeen: fpl-data-refreshin deploy-verify mittaa sen ja korjaa itse.

ILMAISTA DATAA: kapteeni on jo ilmainen goaliq.app/fpl:ssa ja rate-teamin
ilmaisvastauksessa (`captain.pick` + `captain.alternative`). Tama moduuli ei
kanna siirtoehdotuksia eika muita Premium-kenttia.

Vaiheet mitataan synteettisesti: `tests/test_model_captain_phases.py`.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import re
from pathlib import Path

from src.models import gw_calls
from src.models.fpl_model_entry import ENTRY_ID
from src.models.model_squad_scores import FROZEN_DIR as _FROZEN_DIR

SOURCE_FROZEN = "frozen"
SOURCE_ENTRY_PICKS = "entry_picks"

#: Tarkistusreitit. Freeze: goaliq.app/fpl:n kutsulokin rivi (ihmisluettava,
#: sama kapteeni). Entry: FPL:n oma sivu julkaistuille pickeille.
GW_CALLS_URL = "https://goaliq.app/fpl#gw-calls"
#: Sivu jolle GW_CALLS_URL vie, samasta checkoutista kuin freeze.
#: Testit korvaavat taman.
FPL_PAGE = Path(__file__).resolve().parents[2] / "fpl.html"
_GW_CALLS_ANCHOR = 'id="gw-calls"'
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
FPL_ENTRY_EVENT_URL = "https://fantasy.premierleague.com/entry/{entry}/event/{gw}"

_POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

#: Testit korvaavat taman; tuotanto lukee versioidun hakemiston.
FROZEN_DIR = _FROZEN_DIR


class ModelCaptainError(Exception):
    """Freeze on olemassa mutta sita ei voi lukea luotettavasti."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def next_deadline(events: list[dict], now: _dt.datetime
                  ) -> tuple[int, str] | None:
    """(kierros, deadline_time) ensimmaiselle kierrokselle jonka deadline on
    edessa. None = kauden kaikki deadlinet ovat menneet (tai syote rikki)."""
    best: tuple[int, _dt.datetime, str] | None = None
    for e in events or []:
        gid = e.get("id")
        raw = e.get("deadline_time")
        if not isinstance(gid, int) or isinstance(gid, bool) or not isinstance(raw, str):
            continue
        try:
            t = gw_calls.parse_utc(raw)
        except ValueError:
            continue
        if t > now and (best is None or t < best[1]):
            best = (gid, t, raw)
    return (best[0], best[2]) if best else None


def load_frozen_squad(gw: int, frozen_dir=None) -> dict | None:
    """Kierroksen jaadytetty runko, tai None jos freezea ei ole.

    Olemassa oleva mutta rikkinainen tiedosto -> ModelCaptainError (503):
    ei pudoteta hiljaa entry-polulle, koska se nimeaisi kapteenin jota
    malli ei lukinnut."""
    p = Path(frozen_dir or FROZEN_DIR) / f"gw{int(gw)}.json"
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ModelCaptainError(
            503, f"The model's frozen squad for GW{gw} could not be read.") from e
    meta = doc.get("meta") if isinstance(doc, dict) else None
    if not isinstance(meta, dict) or meta.get("gw") != int(gw):
        raise ModelCaptainError(
            503, f"The model's frozen squad file for GW{gw} names another "
                 "gameweek.")
    return doc


def logged_model_captain(page_html: str | None, gw: int) -> str | None:
    """Sivun kutsulokin "GW{gw} Model squad captain" -rivin pelaajasolu
    ("Haaland (MCI)"), tai None jos rivia ei ole. Lukee vain #gw-calls-
    taulukon, ei muita sivun taulukoita."""
    if not page_html:
        return None
    start = page_html.find(_GW_CALLS_ANCHOR)
    if start < 0:
        return None
    end = page_html.find("</table>", start)
    section = page_html[start:end if end > 0 else None]
    label = gw_calls.CALL_LABELS["model_captain"]
    for row in _ROW_RE.findall(section):
        cells = [_html.unescape(_TAG_RE.sub("", c)).strip()
                 for c in _CELL_RE.findall(row)]
        if len(cells) >= 3 and cells[0] == f"GW{int(gw)}" and cells[1] == label:
            return cells[2]
    return None


def _page_row_name(call: dict) -> str:
    """Sama muoto kuin build_fpl_page.gw_calls_html kirjoittaa."""
    return f"{call.get('web_name') or '?'} ({call.get('team_short') or '?'})"


def _read_page(page_path) -> str | None:
    try:
        return Path(page_path or FPL_PAGE).read_text(encoding="utf-8")
    except OSError:
        return None


def _player(row: dict | None, pid: int, web_name, team_short, pos,
            gw: int, gw_xp) -> dict:
    """Yhteinen pelaajamuoto molemmille lahteille. `opponents` None = ei
    tietoa (pelaaja puuttuu projektiosta); [] = ei ottelua kierroksella."""
    opponents = None
    for g in (row or {}).get("gameweeks") or []:
        if g.get("gw") == gw:
            opponents = list(g.get("opponents") or [])
            break
    if isinstance(pos, int):
        pos = _POS.get(pos, str(pos))
    return {"id": int(pid), "web_name": web_name, "team_short": team_short,
            "pos": pos,
            "gw_xp": (round(float(gw_xp), 2) if gw_xp is not None else None),
            "opponents": opponents}


def _frozen_card(frozen: dict, pool_by_id: dict, xp_meta: dict,
                 deadline: tuple[int, str] | None, page_path=None) -> dict:
    gw = int(frozen["meta"]["gw"])
    call = gw_calls.model_captain_call(frozen, pool_by_id)
    if call is None:
        raise ModelCaptainError(
            503, f"The model's frozen squad for GW{gw} has no captain in it.")
    if logged_model_captain(_read_page(page_path), gw) != _page_row_name(call):
        raise ModelCaptainError(
            503, f"The model's GW{gw} captain is not on goaliq.app/fpl yet.")
    cid = int(call["player_id"])
    fresh = gw_calls.gw_xp_at(pool_by_id.get(cid), gw)
    captain = _player(pool_by_id.get(cid), cid, call["web_name"],
                      call["team_short"], call["pos"], gw, call["value"])
    captain["gw_xp_frozen"] = call.get("frozen_value")
    captain["gw_xp_basis"] = "projection" if fresh is not None else "frozen"

    vice = None
    vrow = gw_calls.frozen_squad_row(frozen, frozen.get("vice_captain"))
    if vrow is not None:
        vid = int(vrow["id"])
        v_fresh = gw_calls.gw_xp_at(pool_by_id.get(vid), gw)
        vice = _player(pool_by_id.get(vid), vid, vrow.get("web_name"),
                       vrow.get("team_short"), vrow.get("pos"), gw,
                       v_fresh if v_fresh is not None else vrow.get("xp"))
    fmeta = frozen.get("meta") or {}
    return {
        "meta": {
            "source": SOURCE_FROZEN,
            "gw": gw,
            "entry_id": ENTRY_ID,
            "picks_gw": None,
            "frozen_at": fmeta.get("frozen_at"),
            "frozen_deadline": fmeta.get("deadline"),
            "deadline_gameweek": deadline[0] if deadline else None,
            "deadline_time": deadline[1] if deadline else None,
            "generated_at": xp_meta.get("generated_at"),
            "route": {"kind": "gw_calls", "gw": gw, "url": GW_CALLS_URL},
        },
        "captain": captain,
        "vice_captain": vice,
        # Lukittu paatos: ei "close call" -vaihtoehtoa. Freezella on
        # varakapteeni, joka on eri asia kuin lahin vaihtoehto.
        "alternative": None,
    }


def _entry_picks_card(payload: dict, deadline: tuple[int, str] | None) -> dict:
    meta = payload.get("meta") or {}
    gw = meta.get("captain_gw")
    rows = {p["id"]: p for p in ((payload.get("team") or {}).get("players") or [])}
    cap_block = payload.get("captain") or {}

    def _from_pick(pick: dict | None) -> dict | None:
        if not pick:
            return None
        row = rows.get(pick["id"])
        return _player(row, pick["id"], pick.get("web_name"),
                       pick.get("team_short"), (row or {}).get("pos"), gw,
                       pick.get("gw_xp"))

    picks_gw = meta.get("picks_gw")
    entry = meta.get("entry") or ENTRY_ID
    return {
        "meta": {
            "source": SOURCE_ENTRY_PICKS,
            "gw": gw,
            "entry_id": entry,
            "picks_gw": picks_gw,
            "frozen_at": None,
            "frozen_deadline": None,
            "deadline_gameweek": deadline[0] if deadline else None,
            "deadline_time": deadline[1] if deadline else None,
            "generated_at": meta.get("generated_at"),
            "route": ({"kind": "fpl_entry", "gw": picks_gw,
                       "url": FPL_ENTRY_EVENT_URL.format(entry=entry, gw=picks_gw)}
                      if isinstance(picks_gw, int) else None),
        },
        "captain": _from_pick(cap_block.get("pick")),
        "vice_captain": None,
        "alternative": _from_pick(cap_block.get("alternative")),
    }


def model_captain(now: _dt.datetime | None = None, *, frozen_dir=None,
                  page_path=None) -> dict:
    """Mallin kapteeni seuraavalle deadlinelle, lahde nimettyna.

    Kutsuu rate-teamia vain kun freezea ei ole. RateTeamError ja
    ModelCaptainError nousevat kutsujalle (endpoint kaantaa ne HTTP:ksi).
    """
    from src.models import fpl_rate_team as rt

    now = now or _now()
    xp_data, bootstrap, _pool, pool_by_id = rt.build_context()
    deadline = next_deadline(bootstrap.get("events") or [], now)
    if deadline is not None:
        frozen = load_frozen_squad(deadline[0], frozen_dir)
        if frozen is not None:
            return _frozen_card(frozen, pool_by_id, xp_data.get("meta") or {},
                                deadline, page_path)

    payload = rt.rate_team(entry=ENTRY_ID)
    cap_gw = (payload.get("meta") or {}).get("captain_gw")
    if isinstance(cap_gw, int) and not isinstance(cap_gw, bool):
        # Artefakti laahaa deadlinen jalkeen: rate-team nimeaa kierroksen
        # joka on jo lukittu. Sen kapteeni on se jonka malli lukitsi.
        frozen = load_frozen_squad(cap_gw, frozen_dir)
        if frozen is not None:
            return _frozen_card(frozen, pool_by_id, xp_data.get("meta") or {},
                                deadline, page_path)
    return _entry_picks_card(payload, deadline)
