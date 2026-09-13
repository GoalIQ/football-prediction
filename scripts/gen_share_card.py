# -*- coding: utf-8 -*-
"""GoalIQ-jakokortti komentoriviltä — toistettava versio sivujen napista.

TAUSTA (Villen pyynto 9.8): sivujen "Share as image" tekee kortin siita mita
kayttaja on suodattanut. Omaan postaustahtiin tarvitaan sama kortti ilman
kasityota, jotta se ei ole joka kerta klikkailua.

LAYOUT on TASMALLEEN sama kuin selainkortissa (scripts/share_card_js.py) ja
SPA:ssa (web/pro-spa/src/lib/shareCard.ts): 1080 leveä, ROW_TOP 404, ROW_H 80,
sama paletti ja sama alatunniste. Jos muutat mittoja, muuta KAIKKI kolme --
muuten syntyy nelja erinakoista korttia samasta tuotteesta.

GAMEWEEK-IKKUNA (--from-gw / --to-gw) on mahdollinen VAIN siella missa data on
ottelukohtaista:
    cs        kylla  (data/fpl_cs_fdr.json, fixtures[].gameweek)
    defence   ei     (kauden aggregaatti per joukkue, ei GW-erittelya)
    stats     ei     (FPL:n kausisummat, ei GW-erittelya)
Naille kahdelle GW-ikkuna vaatisi uuden datalahteen; skripti sanoo sen
suoraan sen sijaan etta hyvaksyisi lipun ja jattaisi sen HILJAA huomiotta.

AJO:
    python scripts/gen_share_card.py cs --from-gw 1 --to-gw 6
    python scripts/gen_share_card.py defence
    python scripts/gen_share_card.py stats --sort xgi --top 10
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORT))

from src.models.fpl_club_best import club_best_rows, gap_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_DIR = ROOT / "outputs" / "cards"

# --- Layout: 1:1 share_card_js.py / shareCard.ts ---------------------------
W, MX = 1080, 60
ROW_TOP, ROW_H, FOOT_H = 404, 80, 146
INK, INK2 = (11, 10, 9), (20, 19, 17)
AMBER, CREAM, MUTED = (245, 197, 66), (243, 242, 242), (168, 162, 154)
LINE = (243, 242, 242, 34)
TAG_LINE = (243, 242, 242, 84)

# Fontit tulevat mobiilirepon node_modulesista. Polku johdetaan
# kotihakemistosta ja on ylikirjoitettavissa GOALIQ_APP_DIR:lla: kovakoodattu
# C:-polku ei loydy toiselta koneelta eika CI:sta.
_APP_DIR = Path(os.environ.get("GOALIQ_APP_DIR")
                or Path.home() / "Documents" / "goaliq-app")
_FONT_DIR = _APP_DIR / "node_modules" / "@expo-google-fonts" / "ibm-plex-mono"
FONT_BOLD = _FONT_DIR / "700Bold" / "IBMPlexMono_700Bold.ttf"
FONT_MED = _FONT_DIR / "500Medium" / "IBMPlexMono_500Medium.ttf"
WORDMARK = ROOT / "assets" / "brand" / "goaliq-wordmark-teletext.png"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        # Fontin puuttuminen muuttaisi kortin ilmeen taysin ja hiljaa.
        raise SystemExit(f"Fonttia ei loydy: {path}")
    return ImageFont.truetype(str(path), size)


def _pros(arvo: float) -> str:
    """Prosentti kokonaislukuna, TASAN PUOLIKAS YLOSPAIN.

    🔴 MITATTU 12.9.2026: `f"{v:.0f}%"` kayttaa Pythonin pankkiiripyoristysta
    (round-half-to-even), joten **Aston Villan 24.5 % renderoityi kortille
    "24%"** kun ilmaissivu sanoo 24,5 %. Lukija joka vertaa korttia sivuun
    nakee 24 vs 24,5 ja paattelee etta jompikumpi on vaarin - ja kortti oli se
    joka oli vaarassa suuntaan.
    Muisti: `pyoristyssaanto-eroaa-pythonin-ja-jsn-valilla`.
    """
    from decimal import ROUND_HALF_UP, Decimal
    return f"{Decimal(str(arvo)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)}%"


def _shrink(d, text, px, max_w, min_px, font_path):
    """Kutista teksti mahtumaan - tai KAADA ajo jos se ei mahdu.

    🔴 12.9: aiemmin tama palautti min_px-fontin ja piirsi tekstin kortin
    reunan yli, hiljaa. Mitattu samana aamuna: minuuttilipun selite venytti
    alatunnisteen 1 176 px:iin 960 px:n tilassa ja URL leikkautui kesken
    ("goaliq.app/fpl/expec"), eli KORTIN AINOA TARKISTUSREITTI katosi.
    Koodissa oli jo varoitus tasta ("teksti ei saa hukkua siihen etta joku
    pidentaa sita myohemmin") - mutta varoitus ei ole portti.
    Nyt liian pitka teksti on mahdoton julkaista: ajo kaatuu.
    """
    f = _font(font_path, px)
    while d.textlength(text, font=f) > max_w and px > min_px:
        px -= 2
        f = _font(font_path, px)
    leveys = d.textlength(text, font=f)
    if leveys > max_w:
        raise SystemExit(
            f"gen_share_card: teksti ei mahdu korttiin edes {px}px:lla "
            f"({leveys:.0f} px / {max_w:.0f} px). Lyhenna se: {text}")
    return f


def render(spec: dict, out_path: Path) -> Path:
    rows = spec["rows"]
    # 9.9 (Villen pyynto): xP-kortin rivi saa alarivin (xMins + mista pisteet
    # tulevat). Rivikorkeus tulee spekista, jotta muut kortit eivat muutu.
    row_h = int(spec.get("row_h") or ROW_H)
    h = ROW_TOP + len(rows) * row_h + FOOT_H

    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y),
                      tuple(int(a + (b - a) * t) for a, b in zip(INK, INK2)))
    canvas = grad.resize((W, h)).convert("RGBA")
    d = ImageDraw.Draw(canvas)

    if WORDMARK.exists():
        wm_src = Image.open(WORDMARK).convert("RGBA")
        wm_h = 84
        wm = wm_src.resize(
            (int(wm_src.width * wm_h / wm_src.height), wm_h), Image.LANCZOS)
        canvas.alpha_composite(wm, ((W - wm.width) // 2, 64))
    else:
        f = _font(FONT_BOLD, 56)
        gw_w = d.textlength("GOAL", font=f)
        box, x0 = 76, (W - (gw_w + 14 + 76)) / 2
        d.text((x0, 72), "GOAL", font=f, fill=CREAM)
        d.rectangle([x0 + gw_w + 14, 64, x0 + gw_w + 14 + box, 64 + box],
                    fill=AMBER)
        f2 = _font(FONT_BOLD, 40)
        d.text((x0 + gw_w + 14 + (box - d.textlength("IQ", font=f2)) / 2, 82),
               "IQ", font=f2, fill=INK)
    d.rounded_rectangle([(W - 120) / 2, 176, (W + 120) / 2, 182],
                        radius=3, fill=AMBER)

    f_title = _font(FONT_BOLD, 60)
    title = spec["title"]
    d.text(((W - d.textlength(title, font=f_title)) / 2, 226), title,
           font=f_title, fill=CREAM)
    f_sub = _font(FONT_MED, 22)
    sub = spec["subtitle"]
    d.text(((W - d.textlength(sub, font=f_sub)) / 2, 306), sub,
           font=f_sub, fill=MUTED)

    f_col = _font(FONT_MED, 19)
    fx_right = W - MX - 180
    d.text((MX + 76, ROW_TOP - 34), spec.get("nameLabel", "PLAYER"),
           font=f_col, fill=MUTED)
    if spec.get("midLabel"):
        d.text((fx_right - d.textlength(spec["midLabel"], font=f_col),
                ROW_TOP - 34), spec["midLabel"], font=f_col, fill=MUTED)
    d.text((W - MX - d.textlength(spec["valueLabel"], font=f_col),
            ROW_TOP - 34), spec["valueLabel"], font=f_col, fill=MUTED)

    f_rank = _font(FONT_BOLD, 28)
    f_tag = _font(FONT_BOLD, 17)
    f_team = _font(FONT_MED, 20)
    f_val = _font(FONT_BOLD, 36)

    for i, r in enumerate(rows):
        y = ROW_TOP + i * row_h
        # Alarivillinen rivi: paarivi nousee ylos ja sub piirretaan sen alle.
        sub = r.get("sub")
        cy = y + (row_h / 2 - 12 if sub else row_h / 2)
        first = i == 0
        d.rectangle([MX - 12, y + 4, W - (MX - 12), y + row_h - 4],
                    outline=AMBER if first else LINE, width=2 if first else 1)
        if sub:
            f_sub_row = _shrink(d, sub, 19, W - 2 * MX - 76 - 120, 13, FONT_MED)
            d.text((MX + 76, y + row_h - 34), sub, font=f_sub_row, fill=MUTED)

        rk = str(r["rank"])
        d.text((MX + 34 - d.textlength(rk, font=f_rank), cy - 16), rk,
               font=f_rank, fill=AMBER if first else MUTED)

        x = MX + 76
        f_name = _shrink(d, r["name"], 32, 330, 20, FONT_BOLD)
        d.text((x, cy - f_name.size * 0.62), r["name"], font=f_name, fill=CREAM)
        x += d.textlength(r["name"], font=f_name) + 16

        if r.get("tag"):
            pw = d.textlength(r["tag"], font=f_tag) + 16
            d.rectangle([x, cy - 15, x + pw, cy + 15], outline=TAG_LINE, width=1)
            d.text((x + 8, cy - 10), r["tag"], font=f_tag, fill=CREAM)
            x += pw + 12

        if r.get("team"):
            d.text((x, cy - 10), r["team"], font=f_team, fill=MUTED)
            x += d.textlength(r["team"], font=f_team) + 12

        # Erikoistilannemerkinnat (P = pilkut, FK = vapaapotkut). Selainkortti
        # piirtaa nama jo; ilman niita PIL-versio ei ollut sama kortti, mika
        # nakyi pikselidiffina viikkopostauksen korttia vastaan (9.8).
        for b in (r.get("badges") or []):
            bw = d.textlength(b, font=f_tag) + 14
            d.rectangle([x, cy - 14, x + bw, cy + 14], outline=AMBER, width=1)
            d.text((x + 7, cy - 9), b, font=f_tag, fill=AMBER)
            x += bw + 8

        if r.get("mid"):
            f_mid = _shrink(d, r["mid"], 24, 190, 14, FONT_MED)
            d.text((fx_right - d.textlength(r["mid"], font=f_mid),
                    cy - f_mid.size * 0.55), r["mid"], font=f_mid, fill=MUTED)

        val = r["value"]
        d.text((W - MX - d.textlength(val, font=f_val), cy - 36 * 0.58), val,
               font=f_val, fill=AMBER if first else CREAM)

    # Kahva varaa oikean laidan; alatunnisteen 1. rivi jakaa saman rivin sen
    # kanssa. Ilman kutistusta liian pitka teksti piirtyy kahvan PAALLE --
    # niin kavi 9.8 kun defence-kortin lahdemerkintaan lisattiin puuttuvat
    # seurat. Teksti ei saa hukkua siihen etta joku pidentaa sita myohemmin.
    f_handle = _font(FONT_BOLD, 20)
    handle_w = d.textlength("@goaliqapp", font=f_handle)
    foot_max = W - MX - handle_w - 24 - MX
    f_foot = _shrink(d, spec["footNote"], 20, foot_max, 13, FONT_MED)
    d.text((MX, h - 88), spec["footNote"], font=f_foot, fill=MUTED)
    d.text((W - MX - handle_w, h - 88), "@goaliqapp", font=f_handle, fill=AMBER)
    f_foot2 = _shrink(d, spec["footNote2"], 17, W - 2 * MX, 11, FONT_MED)
    d.text((MX, h - 54), spec["footNote2"], font=f_foot2, fill=MUTED)
    d.rectangle([0, h - 8, W, h], fill=AMBER)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


# ---------------------------------------------------------------------------
# Datarakentajat
# ---------------------------------------------------------------------------
def _xp_payload() -> dict:
    """Taysi xP-projektio korttigeneraattorille.

    🔴 14.8 BUGI: kortit lukivat JULKISTA /api/fantasy/xp-endpointia, joka on
    premium-portin takana MASKATTU top-10-teaseriksi (meta.masked=true, 10
    riviä 507:sta). Kortit siis rakennettiin myyntipinnasta eika omasta
    datasta. `xp`-kortille se sattui olemaan oikein — top 10 on top 10 —
    mutta `value`-kortti ("best xP per million") oli SYSTEMAATTISESTI vaara:
    vastine asuu halvoissa pelaajissa, ja ne on maskattu pois maaritelman
    nojalla. Kortti siis vastasi kysymykseen "kuka kymmenesta kalleimmasta on
    vahiten kallis". Se ehti olla kaytossa 9.8 alkaen.
    Vikaluokka on sama kuin muistiinpanossa "maski katkaisee ilmaispinnan
    hiljaa": tyhja tai typistetty lista ei ole virhe, se on uskottava vastaus.

    Lahde on nyt repon artefakti — sama tiedosto jonka API servaa, ilman
    maskia. Verkkohaku jaa varalle jos ajetaan repon ulkopuolelta, ja
    KUMPIKIN polku kertoo itsestaan aanekkaasti: hiljainen fallback
    maskattuun dataan olisi tasan tama bugi uudelleen.
    """
    import urllib.request

    p = DATA / "fpl_xp_projections.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        n = len(data.get("players") or [])
        print(f"[data] repon artefakti: {n} pelaajaa (maskaamaton)")
        return data
    req = urllib.request.Request(
        "https://api.goaliq.app/api/fantasy/xp",
        headers={"User-Agent": "Mozilla/5.0 goaliq-card-gen"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode("utf-8"))
    n = len(data.get("players") or [])
    if data.get("meta", {}).get("masked"):
        raise SystemExit(
            f"VIRHE: API palautti MASKATUN teaserin ({n} pelaajaa). Kortteja ei "
            f"rakenneta myyntipinnasta — aja tama repossa, jolloin "
            f"data/fpl_xp_projections.json on kaytettavissa.")
    print(f"[data] API: {n} pelaajaa")
    return data


def _load(name: str) -> dict:
    p = DATA / name
    if not p.exists():
        raise SystemExit(f"Datatiedostoa ei loydy: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def card_cs(args) -> dict:
    """Puhtaan pelin todennakoisyys valitulla gameweek-ikkunalla."""
    d = _load("fpl_cs_fdr.json")
    lo, hi = args.from_gw, args.to_gw
    acc: dict[str, list[float]] = {}
    for fx in d.get("fixtures", []):
        gw = fx.get("gameweek")
        if gw is None or not (lo <= int(gw) <= hi):
            continue
        for side in ("home", "away"):
            team = fx.get(side)
            pct = fx.get(f"cs_{side}_pct")
            if team is None or pct is None:
                continue
            acc.setdefault(str(team), []).append(float(pct))
    if not acc:
        raise SystemExit(f"Ei otteluita valilla GW{lo}-{hi}.")

    # KAKSI ERI KYSYMYSTA, ja ne antavat eri jarjestyksen heti kun ikkunassa on
    # tupla- tai blankkiviikkoja:
    #   avg   = "kuinka hyva puolustus on YHDESSA ottelussa" (keskiarvo)
    #   total = "montako puhdasta peliä ikkunasta on odotettavissa" (summa)
    # FPL:ssa jalkimmainen on yleensa se paatos jota ollaan tekemassa, mutta
    # se palkitsee tuplaviikosta -- kumpikin on oikea vastaus eri kysymykseen,
    # joten kortti KERTOO kumpaa se nayttaa eika jata sita arvattavaksi.
    if args.metric == "total":
        ranked = sorted(((t, sum(v) / 100.0, len(v)) for t, v in acc.items()),
                        key=lambda x: x[1], reverse=True)[:args.top]
        value = lambda v: f"{v:.2f}"          # noqa: E731
        vlabel, sub = "xCS", "expected clean sheets in the window"
    else:
        ranked = sorted(((t, sum(v) / len(v), len(v)) for t, v in acc.items()),
                        key=lambda x: x[1], reverse=True)[:args.top]
        # .0f pyoristaa parilliseen (46.5 -> "46"), mika nayttaa lukijasta
        # yhden pienelta virheelta. Puolikkaat ylospain kuten ihminen odottaa.
        value = lambda v: f"{int(v + 0.5)}%"  # noqa: E731
        vlabel, sub = "CS%", "average clean sheet probability per fixture"

    span = f"GW{lo}" if lo == hi else f"GW{lo}-{hi}"
    return {
        "title": f"BEST CLEAN SHEET ODDS {span}",
        "subtitle": sub,
        "nameLabel": "TEAM",
        "midLabel": "FIXTURES",
        "valueLabel": vlabel,
        "footNote": "GoalIQ match model, logged before kickoff",
        "footNote2": "model projections, not betting advice",
        "rows": [{"rank": i + 1, "name": t, "mid": f"{n}", "value": value(v)}
                 for i, (t, v, n) in enumerate(ranked)],
        "file": f"goaliq-cs-{span.lower()}-{args.metric}.png",
    }


def card_defence(args) -> dict:
    """Vahiten xG:ta paastaneet.

    KOLME ASIAA JOTKA KORTIN ON SANOTTAVA, koska se matkustaa yksin ilman
    sivun ymparoivaa tekstia:
      1. Otos on KOKO edellinen kausi (38 ottelua/joukkue), ei alkanut kausi.
      2. xg_pm SISALTAA rangaistuspotkut -- vain vyohykesarakkeet jattavat ne
         pois (build_understat_team_defence.py lisaa xG:n ennen penalty-
         continueta).
      3. Mukana on vain ne joukkueet joilla on kauden data: nousijat puuttuvat
         kokonaan, eli nousija EI VOI nakya listalla. Ilman tata lukija
         paattelee etta nousijoiden puolustus on huono, vaikka se on
         mittaamatta. Sama sokea piste kaatoi /fpl/defence-sivun 8.8.
    Arvot luetaan metasta, jotta kortti ei voi erkaantua datasta.
    """
    d = _load("understat_team_defence_2526.json")
    meta = d.get("meta", {})
    teams = [t for t in d.get("teams", []) if t.get("xg_pm") is not None]
    ranked = sorted(teams, key=lambda t: float(t["xg_pm"]))[:args.top]
    season = meta.get("season", "last season")
    promoted = meta.get("promoted_no_data") or []
    n_have, n_all = len(teams), meta.get("n_current_teams") or len(teams)
    sub = f"{season} full season, per match, penalties included"
    foot = f"{n_have} of {n_all} clubs"
    if promoted:
        foot += f", no data yet: {', '.join(promoted)}"
    # "own xG model" tarkoittaa koodissa UNDERSTATIN omaa mallia
    # (build_understat_shots.py: "Understat runs its own xG model"). Sivulla
    # ymparoiva teksti kantaa sen, mutta kortti matkustaa yksin ja siina se
    # luki kuin malli olisi meidan. Lahde nimetaan, koska luvut EIVAT tasmaa
    # Optan eivatka FotMobin kanssa (mitattu 9.8: mediaani +11.6 % FotMobiin).
    foot2 = ("Understat xG, not Opta · free at goaliq.app, "
             "not betting advice")
    return {
        "title": "FEWEST XG CONCEDED",
        "subtitle": sub,
        "nameLabel": "TEAM",
        "valueLabel": "XGC",
        "footNote": foot,
        "footNote2": foot2,
        "rows": [{"rank": i + 1, "name": str(t["team"]),
                  "value": f"{float(t['xg_pm']):.2f}"}
                 for i, t in enumerate(ranked)],
        "file": "goaliq-defence-xgc.png",
    }


def card_stats(args) -> dict:
    d = _load("fpl_player_stats.json")
    cols = d["meta"]["cols"]
    if args.sort not in cols:
        raise SystemExit(
            f"Tuntematon sarake {args.sort!r}. Vaihtoehdot: {', '.join(cols)}")
    idx = {c: i for i, c in enumerate(cols)}
    k = idx[args.sort]
    rows = [p for p in d["players"]
            if isinstance(p[k], (int, float)) and p[idx["mins"]] >= args.min_mins]
    # Pariteetti sivun napin kanssa: samat suodattimet, ja ne KERROTAAN
    # alaotsikossa. Suodatettu kortti joka ei kerro suodatustaan on
    # harhaanjohtava jaettuna.
    if args.pos:
        want = args.pos.upper()
        rows = [p for p in rows if str(p[idx["pos"]]).upper() == want]
    if args.team:
        want_t = args.team.upper()
        rows = [p for p in rows if str(p[idx["team"]]).upper() == want_t]
    if not rows:
        raise SystemExit("Suodattimet eivat jata yhtaan pelaajaa.")
    n_pool = len(rows)
    rows.sort(key=lambda p: p[k], reverse=True)
    rows = rows[:args.top]
    label = args.sort.upper()
    fmt = (lambda v: str(int(v))) if all(
        float(p[k]).is_integer() for p in rows) else (lambda v: f"{v:.2f}")
    return {
        "title": f"TOP {args.top} BY {label}",
        "subtitle": " · ".join(
            [x for x in (args.pos.upper() if args.pos else "",
                         args.team.upper() if args.team else "",
                         f"{args.min_mins}+ mins" if args.min_mins else "",
                         f"{n_pool} players") if x]),
        "nameLabel": "PLAYER",
        "valueLabel": label,
        "footNote": "free FPL stats at goaliq.app",
        "footNote2": "official FPL API and shot-level data, not betting advice",
        "rows": [{"rank": i + 1, "name": str(p[idx["name"]]),
                  "tag": str(p[idx["pos"]]), "team": str(p[idx["team"]]),
                  "value": fmt(float(p[k]))}
                 for i, p in enumerate(rows)],
        "file": "goaliq-stats-" + "-".join(
            [x for x in (args.sort, (args.pos or "").lower(),
                         (args.team or "").lower()) if x]) + ".png",
    }


def _as_of(data: dict) -> str:
    """'9 Sep' artefaktin generated_at-leimasta. Projektio kirjoitetaan uusiksi
    3 h valein, joten kortti ilman paivaysta ei kerro onko se vanha vai vaara."""
    g = str((data.get("meta") or {}).get("generated_at") or "")[:10]
    kk = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    try:
        return f"{int(g[8:10])} {kk[int(g[5:7]) - 1]}"
    except (ValueError, IndexError):
        return "today"


def card_xp(args) -> dict:
    """Seuraavan gameweekin xP-top: viikkopostauksen kortti.

    Siirretty tanne goaliq-appin outputs/gen_fpl_xp_list.py:sta 9.8, jotta
    samalle layoutille ei jaa kolmatta erillista renderoijaa. Data on sama
    live-endpoint kuin ennen, joten kortti ja webin Captain ranker nayttavat
    samat luvut.
    """
    data = _xp_payload()
    # 10.9 PORTTI k4: kierros ja rivit SAMALTA lukijalta kuin sivun #gw-xp
    # (fpl_gw_xp.free_rows: actionable_gameweek + top_projected + blocklist).
    # Raaka meta-kentta ja alarivin nollapeli olisivat kesken kierroksen
    # eri kierrosta samalla PNG-rivilla (30.8: next=2, vaikutettava=3).
    from scripts.publish_gate import load_blocklist
    from src.models.fpl_gw_xp import free_rows
    gw, free = free_rows(data, load_blocklist())
    if gw is None:
        raise SystemExit("card_xp: kierrosta ei voi paatella metasta.")
    # 9.9 PORTTI blokkasi ajurikategoriat (premium-selite ilman
    # ilmaisreittia). 10.9 XP-AJURIT-ILMAISPINNALLE: sivun rivi kantaa nyt
    # YHDEN todisteen ("on penalties", "51% clean sheet chance", "0.57
    # xGI/90 last season") ja kortti lukee SAMAN funktion
    # (src/models/fpl_why_drivers.card_sub) -> sama teksti. P/FK-badget
    # pysyvat poissa: sama tieto on nyt tekstina, ei kahdesti.
    from src.models.fpl_minutes_flags import flag_symbol, legend_parts
    from src.models.fpl_why_drivers import card_sub, fact_context, fact_text
    ctx = fact_context(data)
    # 9.9 PORTTI: sivu (#gw-xp) jarjestaa top_projected-lukijalla (tasapeli
    # id:lla, korkeintaan MAX_PER_CLUB per seura). Kortti lajitteli itse ja
    # nayttti Joao Pedron ennen Palmeria (molemmat 5.11) kun sivu naytti
    # painvastoin. Yksi lukija molemmille, ei kahta lajittelua.
    rows = []
    for p in free[:args.top]:
        g = next((g for g in (p.get("gameweeks") or []) if g.get("gw") == gw),
                 None)
        if not g:
            continue
        opps = g.get("opponents") or []
        fx = ", ".join(f"{o['opp']} ({o['venue']})" for o in opps) if opps             else "Blank"
        # 9.9 PORTTI: P/FK-badget pois - set piece -tietoa ei ole
        # ilmaissivulla, joten merkki olisi vaite ilman reittia.
        #
        # 🔴 12.9: MINUUTTIPERUSTAN LIPPU TAKAISIN. Sivun #gw-xp merkitsee
        # Isakin rivin `!`:lla (694 min viime kaudella), kortti ei merkinnyt -
        # sama pelaaja, sama sija, kaksi eri lupausta varmuudesta, ja kortti on
        # se joka leviaa ilman sivua ymparillaan. Ehto tulee jaetusta lukijasta
        # eika kortin omasta tulkinnasta (src/models/fpl_minutes_flags).
        sym = flag_symbol(p)
        badges = [sym] if sym else []
        rows.append({"name": p["web_name"], "tag": p["pos"],
                     "team": p["team_short"], "mid": fx,
                     "_xp": float(g.get("xp") or 0.0), "badges": badges,
                     "fact_text": fact_text(p, ctx["team_cs"], ctx["prev_season"]) or None,
                     "sub": card_sub(p, ctx)})
    # Thiaw ei markkinointiin (Villen ohje 10.8, koskee generoituja kortteja).
    # Kortin sisalto on datavetoinen, joten esto on generaattorissa eika
    # postaajan muistissa: fail-closed, Ville paattaa.
    # Nimen varassa (web_name ei ole avain, muisti): riittaa tahan, koska
    # vaara positiivinen kaataa vain kortin eika mitaan julkaista.
    if any(r["name"] == "Thiaw" for r in rows):
        raise SystemExit("card_xp: Thiaw on top-listalla; kortti ei mene ulos "
                         "(Villen ohje 10.8). Kayta --top pienempaa tai odota.")
    if not rows:
        raise SystemExit(f"Ei xP-rivejä GW{gw}:lle.")
    # Selite samasta lukijasta kuin merkki: lippu ilman lukutapaa on merkki
    # jolle ei ole selitysta (sama portin loydos kuin sivulla 5.9).
    # Selite samasta lukijasta kuin merkki: lippu ilman lukutapaa on merkki
    # jolle ei ole selitysta (sama portin loydos kuin sivulla 5.9). Sivun
    # sanamuoto lyhennettyna kortin leveyteen: sama MERKITYS, ei sama pituus -
    # pitka versio kutistuisi 11 px:iin ja jaisi lukematta.
    LYHYT = {"!": "! = short spell or new club last season",
             "?": "? = no Premier League games yet, role comes from price"}
    selite = [LYHYT[s[0]] for s in legend_parts(free[:len(rows)])]
    foot = "xMins = minutes the model expects him to play."
    if selite:
        foot = foot + " " + ". ".join(selite) + "."
    else:
        foot = "xMins = the minutes the model expects him to play. Same row on the page."
    return {
        "title": f"GAMEWEEK {gw} TOP {len(rows)}",
        "subtitle": "expected points, GoalIQ match model",
        "nameLabel": "PLAYER",
        "midLabel": "FIXTURE",
        "valueLabel": "xP",
        "footNote": foot,
        "footNote2": (f"GW{gw} top 20 free, no account: goaliq.app/fpl/expected-points#gw-xp"
                      f"  ·  as of {_as_of(data)}  ·  model projections, not betting advice"),
        "row_h": 104 if any(r.get("sub") for r in rows) else ROW_H,
        # 9.9: sivun GW-osio nayttaa yhden desimaalin (5.5, 5.4). Kortti samalla
        # tarkkuudella, muuten lukija nakee 5.47 vs 5.5 ja pitaa toista vaarana.
        "rows": [dict(r, rank=i + 1, value=f"{r['_xp']:.1f}")
                 for i, r in enumerate(rows)],
        "file": f"goaliq_xp_gw{gw}_top{len(rows)}.png",
    }


def _tier_subtitle(args, n_gw: int, pos_label: str, cap: int) -> str:
    """Alaotsikko kertoo TASMALLEEN sen saannon jolla rivit valittiin.

    Jos saantoa ei kirjoiteta nakyviin, lukija ei voi tietaa miksi joku puuttuu
    - ja juuri se kaatoi ensimmaisen version (Welbeck putosi minuuttilattiaan
    jota kortilla ei lukenut missaan)."""
    yksikko = pos_label.lower()[:-1]
    osat = [f"next {n_gw} GW"]
    if args.max_price:
        osat.append(f"every {yksikko} at {args.max_price:.1f}m or less")
        # Hintakaton kanssa rank-cap on ERI rajaus ja se on sanottava erikseen.
        if args.rank_cap:
            osat.append(f"free top {cap}")
    elif args.rank_cap:
        # 17.8: tama haara sanoi saannon jo itse, ja alla ollut erillinen
        # `if args.rank_cap` lisasi sen TOISEN KERRAN. Kortille renderoityi
        # "every forward in the free top 100, free top 100". Loytyi vasta kun
        # kortti katsottiin kuvana - koodista se ei nay, koska kumpikin haara
        # on erikseen oikein.
        osat.append(f"every {yksikko} in the free top {cap}")
    return ", ".join(osat)


def card_price_tier(args) -> dict:
    """Yhden pelipaikan hinta vs pisteet, VAIN tarkistettavissa olevilla riveilla.

    Villen tilaus 15.8: "joku hintakategorian hyokkaajat tms."

    ALKUPERAINEN KULMA KAATUI MITTAUKSEEN, ja se on syyta lukea ennen kuin
    tata kayttaa uudelleen: alle 5,0 M£:n hyokkaajia on 14, mutta EI YHDELLA
    NIISTA ole projisoitua avauspaikkaa (xmins 34, 19, 19, 19, ...). Luvut
    eivat myoskaan ole projektioita vaan hintaprioria: viidella heista on
    identtinen 7.3 xP6, koska he ovat `no_history`-pelaajia jotka saavat saman
    kovakoodatun 38 %:n aloitustodennakoisyyden. Enemmisto on nousijaseuroista,
    eli "halpaa hyokkaajaa ei ole" olisi kertonut MEIDAN sokeasta pisteesta
    eika pelista.

    TARKISTETTAVUUS ON SISAANRAKENNETTU: `--rank-cap` pudottaa rivit jotka
    eivat mahdu ilmaissivun `/fpl/expected-points` top-100:aan. Ilman sita
    kortti nimeaisi pelaajia joita lukija ei voi tarkistaa mistaan — tasan se
    vika joka blokkasi kaksi tekstia 14.-15.8.
    """
    data = _xp_payload()
    players = data.get("players") or []
    n_gw = len(((players[0] if players else {}).get("gameweeks")) or []) or 6

    ranked = sorted(players, key=lambda p: -float(p.get("xp_horizon_total") or 0))
    cap = args.rank_cap or len(ranked)
    checkable = {p.get("id") or p.get("web_name") for p in ranked[:cap]}

    rows = []
    for p in ranked:
        if args.pos and p.get("pos") != args.pos:
            continue
        if (p.get("id") or p.get("web_name")) not in checkable:
            continue
        price = float(p.get("price") or 0)
        tot = float(p.get("xp_horizon_total") or 0)
        if price <= 0 or tot <= 0:
            continue
        # Hintakatto tekee kortista YHDEN johdonmukaisen kysymyksen.
        # Villen havainto 15.8: "sekava etta tutkii 8 milj hyokkaajia ja sit
        # yhtakkia haaland vain ylempana <- missa asiayhteys? paljon kalliimpi."
        # Han on oikeassa: ilman kattoa kortti sekoitti kaksi eri kysymysta
        # (kuka on paras vs kuka on paras rahoilla) ja rivit 1-2 vastasivat eri
        # kysymykseen kuin rivit 3-9. Katto on myos LUKIJAN tarkistettavissa:
        # hinta on FPL:n omaa julkista dataa.
        if args.max_price and price > args.max_price:
            continue
        # 🔴 EI MINUUTTILATTIAA, ja tama on tietoinen paatos (15.8).
        # Ensimmainen versio suodatti xmins >= 60 "projisoituihin aloittajiin".
        # Julkaisutarkistaja loysi etta se pudotti Welbeckin (CHE, 6.0m, 19.1)
        # jonka xmins on 59 - yhden alle rajan - vaikka kortilla oli Joao Pedro
        # 62:lla. Lukija joka avaa linkin ja suodattaa hyokkaajat nakee rivin
        # jota kortilla ei ole, eika kortti selita miksi. Rajan puolustaminen
        # yhden minuutin tarkkuudella on mahdotonta.
        #
        # Sen sijaan saanto on nyt sellainen jonka lukija voi TARKISTAA sivulta:
        # "jokainen hyokkaaja ilmaisen top 100:n sisalla". xmins nakyy omana
        # sarakkeenaan, joten rotaatioriski on nakyvissa eika piilotettuna.
        # 17.8: `tag` on TYHJA tarkoituksella. Se piirtyy merkkina nimen
        # viereen (ks. rivi ~150), ja aiemmin tassa oli hinta - joka menee
        # samalla `value`ksi oikean reunan PRICE-sarakkeeseen. Kortille
        # renderoityi siis hinta KAHDESTI joka rivilla ("Haaland [15.5m] MCI
        # ... 15.5m"). Muut korttityypit kayttavat `tag`ia pelipaikalle, joten
        # tama oli ainoa jossa sama arvo tuli kahteen kenttaan. Loytyi kuvasta,
        # ei koodista.
        rows.append({"name": p["web_name"], "tag": "", "_price": f"{price:.1f}m",
                     "team": p["team_short"],
                     "mid": f"{tot:.1f} xP · {float(p.get('xmins') or 0):.0f} min",
                     "_v": tot, "badges": []})
    if not rows:
        raise SystemExit("Ei rivejä price-tier-kortille.")
    rows.sort(key=lambda r: r["_v"], reverse=True)
    rows = rows[:args.top]
    pos_label = {"FWD": "FORWARDS", "MID": "MIDFIELDERS",
                 "DEF": "DEFENDERS", "GKP": "GOALKEEPERS"}.get(args.pos, "PLAYERS")
    return {
        "title": f"{pos_label}: PRICE VS POINTS",
        "subtitle": _tier_subtitle(args, n_gw, pos_label, cap),
        "nameLabel": "PLAYER",
        "midLabel": "TOTAL / EXP. MINUTES",
        "valueLabel": "PRICE",
        "footNote": "every row is on goaliq.app/fpl/expected-points, free",
        "footNote2": "model projections, not betting advice",
        "rows": [dict(r, rank=i + 1, value=r["_price"])
                 for i, r in enumerate(rows)],
        "file": f"goaliq_pricetier_{(args.pos or 'all').lower()}_{n_gw}gw.png",
    }


def card_value(args) -> dict:
    """xP per miljoona horisontin yli: hinta-tehokkuuskortti.

    Lisatty 9.8 koska r/FantasyPL-postaus tasta kulmasta oli se joka toimi:
    premiumit ovat parhaita pelaajia ja huonointa vastinetta. Kortti on IG:ta
    ja Blueskyta varten, joissa kuva on formaatti eika liite.

    --min-mins suodattaa avaajiin (oletus 60 xmins): ilman sita listan
    valtaisivat vaihtomiehet, joiden pieni xP jaettuna 4.0 miljoonalla nayttaa
    tehokkuudelta. Sama rajaus kuin postauksessa, jotta luvut tasmaavat.
    """
    data = _xp_payload()
    players = data.get("players") or []
    n_gw = len(((players[0] if players else {}).get("gameweeks")) or []) or 6
    floor = args.min_mins if args.min_mins and args.min_mins < 90 else 60
    rows = []
    for p in players:
        price = float(p.get("price") or 0)
        tot = float(p.get("xp_horizon_total") or 0)
        if price <= 0 or tot <= 0:
            continue
        if float(p.get("xmins") or 0) < floor:
            continue
        rows.append({"name": p["web_name"], "tag": p["pos"],
                     "team": p["team_short"],
                     "mid": f"{price:.1f}m · {tot:.1f} xP",
                     "_v": tot / price, "badges": []})
    if not rows:
        raise SystemExit("Ei rivejä value-kortille.")
    rows.sort(key=lambda r: r["_v"], reverse=True)
    rows = rows[:args.top]
    return {
        "title": f"BEST VALUE, NEXT {n_gw} GW",
        "subtitle": f"expected points per million, {floor}+ min starters",
        "nameLabel": "PLAYER",
        "midLabel": "PRICE / TOTAL",
        "valueLabel": "xP/m",
        "footNote": "logged before kickoff, graded in public",
        "footNote2": "model projections, not betting advice",
        "rows": [dict(r, rank=i + 1, value=f"{r['_v']:.2f}")
                 for i, r in enumerate(rows)],
        "file": f"goaliq_value_{n_gw}gw_top{len(rows)}.png",
    }


def card_club_best(args) -> dict:
    """Jokaisen seuran paras pelaaja YHDESSA positiossa, ennustetuilla pisteilla.

    KULMA (Villen idea 14.8, WGTA_FPL:n talismaani-kortin muoto). Se kortti
    listasi joukkueittain yhden pelaajan VIIME kauden pisteilla ja osuudella
    seuran pisteista. Sama muoto, eri data: meilla luku on ETEENPAIN katsova
    ennuste, ja "osuus" korvautuu erolla saman seuran ja saman position
    kakkoseen. Se on kysymys johon menneet pisteet eivat vastaa: onko tama
    seuran ainoa vaihtoehto talta paikalta vai yksi monesta.

    🔴 KAIKKI 20 SEURAA, EI MINUUTTILATTIAA. Aiempi versio suodatti
    xmins >= 60 ja tuotti hyokkaajakortin jossa oli 10 seuraa 20:sta —
    otsikko olisi luvannut "every club" ja kuva nayttanyt puolet. Lattian
    sijaan seuran paras kelpaa sellaisenaan: xP sisaltaa jo minuutit, joten
    vahan pelaava nousee seuransa karkeen vain jos seuralla ei ole ketaan
    parempaa, ja se on kortin kannalta TOSI vastaus.

    🔴 "?"-MERKKI ON PAKOLLINEN REHELLISYYSLIPPU. Pelaaja jolla ei ole
    Valioliigaminuutteja saa roolinsa hintapriorista eika mallilta. Nousijoiden
    riveilla se on saanto eika poikkeus, ja ilman merkkia kortti esittaisi
    priorin ennusteena. Sama periaate kuin data_basis-kentalla API:ssa.
    """
    pos = (args.pos or "").upper()
    if pos not in ("GKP", "DEF", "MID", "FWD"):
        raise SystemExit(
            "club-best vaatii --pos GKP|DEF|MID|FWD. Kortti on per positio: "
            "20 seuraa x 4 positiota olisi 80 rivia eika luettava kuva.")

    data = _xp_payload()
    players = data.get("players") or []
    n_gw = len(((players[0] if players else {}).get("gameweeks")) or []) or 6

    # 🔴 JAETTU LASKENTA. Alatunniste ohjaa lukijan /fpl/club-best-sivulle
    # todistamaan nama luvut. Jos kortti ja sivu laskisivat ne erikseen, ne
    # voisivat ajautua erilleen ja vaite kaatuisi tasan silla reitilla jolla
    # se piti todistaa. Ks. src/models/fpl_club_best.py.
    src_rows = club_best_rows(players, pos)
    if not src_rows:
        raise SystemExit(f"Ei rivejä positiolle {pos}.")

    rows = []
    for r in src_rows:
        # LUOTTAMUSINDIKAATTORI (Villen saanto 14.8): naytetaan vain kun se
        # kertoo jotain — `high` on oletus eika kaipaa selitysta. Tama kattaa
        # tapauksen jota "?" EI kata: pelaaja jolla on tayi PL-historia mutta
        # epavarmat minuutit (tyoparijako).
        price = f"{r['price']:.1f}m"
        if r["uncertain_minutes"]:
            price += f" · {r['xmins']:.0f} min"
        rows.append({
            "name": r["name"], "tag": r["club"], "team": price,
            "mid": gap_text(r), "_v": r["xp"],
            "badges": ["?"] if r["prior"] else [],
        })

    n_prior = sum(1 for r in rows if r["badges"])
    foot2 = "model projections, not betting advice"
    if n_prior:
        # "price prior" on mallijargonia julkisessa copyssa (vrt. `legal squad`
        # joka vuoti neljalle pinnalle). Sanotaan mita se tarkoittaa.
        foot2 = (f"? = no Premier League games yet, role guessed from price "
                 f"({n_prior} of {len(rows)}) · {foot2}")

    # 🔴 PAIVAYS ON TARKISTETTAVUUTTA, EI KOSMETIIKKAA. Lahdetiedosto
    # paivittyy useita kertoja paivassa (14.8: nelja refresh-committia), joten
    # ilman paivaysta lukija nakee huomenna eri luvut eika kortilla ole mitaan
    # joka selittaisi eron. Paivays luetaan artefaktin omasta leimasta eika
    # ajohetkesta: se kertoo milloin LUVUT syntyivat.
    gen = str(data.get("meta", {}).get("generated_at") or "")
    stamp = ""
    if len(gen) >= 10:
        y, m, dd = gen[:4], gen[5:7], gen[8:10]
        months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        try:
            stamp = f", as of {int(dd)} {months[int(m) - 1]}"
        except (ValueError, IndexError):
            stamp = ""
    # 🔴 25.8: kortti on JULKINEN pinta ja tama kaava valehteli kahdesti.
    # (1) `next_gameweek` osoittaa kesken kierroksen jo lukittuun kierrokseen,
    #     joten kortti olisi sanonut "GW1-6" sen jalkeen kun GW1 pelattiin.
    # (2) `first + n - 1` tuottaa kierroksen jota listalla ei ole heti kun
    #     aloitus ja lista ovat eri mielta ("GW2-7" kun data on GW1-6).
    # Ikkuna johdetaan nyt todellisista kierroksista. Ks. fpl_gameweek.py.
    from src.models.fpl_gameweek import window_label
    _gws = ((players[0] if players else {}).get("gameweeks")) or []
    window = window_label(data.get("meta") or {}, _gws, n_gw)
    return {
        "title": f"BEST {pos} AT EVERY CLUB",
        "subtitle": f"projected points, {window}{stamp}",
        "nameLabel": "PLAYER",
        "midLabel": "GAP TO CLUB'S 2ND",
        "valueLabel": "xP",
        # 🔴 REITTI ON KOLMAS YRITYS, ja kaksi edellista olivat vaarin.
        # (1) "goaliq.app/fpl" — se sivu renderoi listansa MASKATUSTA
        #     top-10-teaserista, eli 17 rivia 20:sta ei olisi tarkistettavissa.
        # (2) raaka JSON goaliq.app/data/... — reitti oli tosi mutta 1,3 MB
        #     JSON puhelimen selaimessa ei ole kenellekaan tarkistus vaan este.
        #     Portti ei nostanut sita koska se testasi vain etta URL vastaa 200.
        # (3) /fpl/club-best — ihmisluettava, ilmainen, ei kirjautumista, ja
        #     TASMALLEEN samat rivit koska laskenta on jaettu moduuli.
        # Huom miksi /fpl/expected-points EI kelpaa: se on `rows[:100]`, ja
        # nousijaseurojen karjet (Belloumi, Tchaouna, Florentino, Smith Rowe)
        # eivat mahdu koko liigan top-100:aan — eli tasan ne rivit joita
        # lukija todennakoisimmin haluaa tarkistaa puuttuisivat.
        "footNote": "every club, free at goaliq.app/fpl/club-best",
        "footNote2": foot2,
        "rows": [dict(r, rank=i + 1, value=f"{r['_v']:.1f}")
                 for i, r in enumerate(rows)],
        "file": f"goaliq_club_best_{pos.lower()}_{n_gw}gw.png",
    }


# ---------------------------------------------------------------------------
# GW-OUTLOOK: kolme saraketta (maalit, nollapelit, ottelut)
# ---------------------------------------------------------------------------
# Villen tilaus 17.8 (Wolfyn ehdotuksesta): jaettava kortti jossa on koko
# kierroksen kuva yhdella silmayksella. Ulkoasu on kolme saraketta, ei
# rivilista, joten `render()` ei kelpaa - se laskee korkeuden riveista ja
# piirtaa yhden rivin per tietue.
#
# 🔴 NUMEROT OVAT MEIDAN MALLISTAMME. Ehdotuksen mukana tullut mallikuva
# sisalsi toisen palvelun luvut, ja ne eroavat meidan luvuistamme
# merkittavasti (NEW 1.41 vs meidan 1.82, BRE 1.54 vs 1.95). Kortti lukee
# data/fpl_cs_fdr.json:ia eika mitaan muuta.
#
# Sana "odds" ei esiinny kortissa: positioimme analytiikaksi emmeka
# vedonlyonniksi, ja otsikko on siksi "clean sheet %".

def _hex_to_rgb(c: str):
    from PIL import ImageColor
    try:
        return ImageColor.getrgb(c)
    except ValueError:
        return (120, 120, 120)


# ---------------------------------------------------------------------------
# PAITAPAIVITYS 2.9: PIL-paita varipallon tilalle. Sama geometria kuin
# team_colors._JERSEY (SVG-polku -> monikulmio), samat kuviot ja hihansuut.
# Kortti on rasteri (PIL), joten polku litistetaan: M/L suoraan, C/Q 8 askelta.
# ---------------------------------------------------------------------------
def _flatten_path(d: str, steps: int = 8) -> list[tuple[float, float]]:
    toks = d.replace(",", " ").split()
    pts: list[tuple[float, float]] = []
    i = 0
    cur = (0.0, 0.0)
    while i < len(toks):
        c = toks[i]
        if c == "M" or c == "L":
            cur = (float(toks[i + 1]), float(toks[i + 2])); pts.append(cur); i += 3
        elif c == "C":
            p1 = (float(toks[i + 1]), float(toks[i + 2]))
            p2 = (float(toks[i + 3]), float(toks[i + 4]))
            p3 = (float(toks[i + 5]), float(toks[i + 6]))
            p0 = cur
            for k in range(1, steps + 1):
                t = k / steps
                x = (1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t*t*p2[0] + t**3*p3[0]
                y = (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t*t*p2[1] + t**3*p3[1]
                pts.append((x, y))
            cur = p3; i += 7
        elif c == "Q":
            p1 = (float(toks[i + 1]), float(toks[i + 2]))
            p2 = (float(toks[i + 3]), float(toks[i + 4]))
            p0 = cur
            for k in range(1, steps + 1):
                t = k / steps
                x = (1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0]
                y = (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]
                pts.append((x, y))
            cur = p2; i += 5
        elif c == "Z":
            i += 1
        else:
            i += 1
    return pts


def _draw_kit_pil(canvas, x: int, y: int, size: int, short: str,
                  outline=(243, 242, 242, 90)) -> None:
    """Piirra joukkueen paita (size x size) kortille kohtaan (x, y)."""
    from PIL import Image, ImageDraw
    from src.models.team_colors import (
        _team_color, _darken, _KIT_BY_SHORT, _kit_layers, _cuff_color,
        _JERSEY, _SLEEVE_L, _SLEEVE_R, _CUFF_L, _CUFF_R, _COLLAR,
    )
    S = 4  # supersample -> siistit viistot reunat
    W = size * S
    sc = W / 100.0
    def P(pts): return [(px * sc, py * sc) for px, py in pts]
    color, _ = _team_color(short)
    pattern, secondary = _KIT_BY_SHORT.get((short or "").upper(), ("solid", None))
    sleeve = secondary if (pattern == "sleeves" and secondary) else _darken(color)
    cuff = _cuff_color(color, pattern, secondary)
    body = P(_flatten_path(_JERSEY))
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon(body, fill=_hex_to_rgb(color))
    layers = _kit_layers(pattern) if secondary else []
    if layers:
        pat = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pat)
        for l in layers:
            if l[0] == "rect":
                pd.rectangle([l[1] * sc, l[2] * sc, (l[1] + l[3]) * sc, (l[2] + l[4]) * sc],
                             fill=_hex_to_rgb(secondary))
            else:
                pd.polygon(P(_flatten_path(l[1])), fill=_hex_to_rgb(secondary))
        mask = Image.new("L", (W, W), 0)
        ImageDraw.Draw(mask).polygon(body, fill=255)
        layer.paste(pat, (0, 0), Image.composite(mask, Image.new("L", (W, W), 0), pat.split()[3]))
        d = ImageDraw.Draw(layer)
    for path_, col in ((_SLEEVE_L, sleeve), (_SLEEVE_R, sleeve), (_CUFF_L, cuff), (_CUFF_R, cuff)):
        d.polygon(P(_flatten_path(path_)), fill=_hex_to_rgb(col))
    collar = P(_flatten_path(_COLLAR))
    d.line(collar, fill=_hex_to_rgb(secondary or sleeve), width=max(1, int(4 * sc)), joint="curve")
    d.line(body + body[:1], fill=outline, width=max(1, int(3 * sc)), joint="curve")
    small = layer.resize((size, size), Image.LANCZOS)
    canvas.paste(small, (x, y), small)


def _rajatasapeli(jarjestetty: list[dict], kentta: str, n: int = 10) -> bool:
    """Pyoristyvatko sijat n ja n+1 samaksi kahden desimaalin luvuksi?

    Jos pyoristyvat, top-n-lista ja sen ulkopuolinen rivi nayttavat kortissa
    identtiselta arvolta mutta saavat eri kohtelun, eika lukija voi tietaa
    miksi. Ei ole virhe leikata listaa, mutta on virhe leikata se NAKYMATTOMAN
    eron kohdalta.
    """
    if len(jarjestetty) <= n:
        return False
    return (f"{jarjestetty[n - 1][kentta]:.2f}"
            == f"{jarjestetty[n][kentta]:.2f}")


def card_gw_outlook(args) -> dict:
    """Kierroksen kuva: projisoidut maalit, nollapeli-% ja ottelut.

    LAHDE ON fpl_projections_phase0.json EIKA fpl_cs_fdr.json (17.8). Ne ovat
    eri mielta, ja ero on iso: MUN 41 % vs 31,2 % ja SUN 36 % vs 26,9 % GW1:ssa.
    cs_fdr EI aja `fpl_context.fixture_adjustments`-kerrosta, joten se antaa
    nousijan sarja-avaukseen kotona raa'an DC-luvun. Tasan sen korjaamiseksi
    tuo moduuli on kirjoitettu — sen docstring nimeaa esimerkkinaan naivin
    "Man Utd 43 % CS @ Hull":n, ja kortissa luki 41 %.

    Kortti on jakopinta: sen luvun on oltava sama jonka lukija nakee
    goaliq.app/fpl:sta. phase0 on se tiedosto jota build_fpl_page.py servaa,
    joten lahde valitaan pinnan mukaan eika kentannimien mukavuuden mukaan
    (kentat ovat samat molemmissa, mika on juuri se syy miksi vaara lahde ei
    kaatanut mitaan vaan tuotti hiljaa vaarat luvut).
    """
    doc = _load("fpl_projections_phase0.json")
    # 🔴 SAMA KIERROSLUKIJA KUIN SIVULLA (12.9.2026). Tassa oli
    # `min(fixtures gameweeks)`, joka on NELJAS saanto samaan kysymykseen
    # (sivu: display_gameweek, siirtosuunnittelu: actionable, chip-EV: oma).
    # Se osuu oikeaan vain niin kauan kuin builderi pudottaa alkaneen
    # kierroksen heti — eli se on riippuvainen toisen komponentin
    # sivuvaikutuksesta, ei saannosta. Kortti on jakopinta ja sivu on sen
    # tarkistusreitti: jos ne eivat lue samaa funktiota, lukija joka klikkaa
    # linkkia nakee eri kierroksen kuin kuvassa.
    from src.models.fpl_gameweek import display_gameweek
    gw = args.gw or display_gameweek(doc.get("meta") or {},
                                     doc.get("fixtures") or []) \
        or min((f["gameweek"] for f in doc["fixtures"]), default=1)
    fx = [f for f in doc["fixtures"] if f["gameweek"] == gw]
    if not fx:
        raise SystemExit(f"GW{gw}: ei otteluita fpl_projections_phase0.json:ssa.")

    # 🔴 LYHENNE TULEE JSONISTA, EI NIMIKARTASTA. Renderoijan `SHORT`-kartan
    # avain oli "Brighton & Hove Albion" mutta JSON sanoo "Brighton", joten
    # kartta ei osunut ja fallback `name[:3]` teki siita "BRI". Mitattu 25.8:
    # 6/20 seurasta putosi fallbackiin ja niista 5 osui oikein SATTUMALTA.
    # FPL-yleisolle Brighton on BHA poikkeuksetta. `home_short`/`away_short`
    # on auktoritatiivinen kentta ja se oli koko ajan payloadissa.
    promoted = set((doc.get("meta", {}).get("context_layer") or {})
                   .get("promoted_teams") or [])
    teams = []
    for f in fx:
        for koti in (True, False):
            nimi = f["home"] if koti else f["away"]
            teams.append({
                "team": nimi,
                "short": f.get("home_short" if koti else "away_short"),
                "xg": f["xg_home"] if koti else f["xg_away"],
                "cs": f["cs_home_pct"] if koti else f["cs_away_pct"],
                # 🔴 Nousijalla ei ole omaa PL-historiaa: sivu merkitsee sen
                # "baseline rating" -tekstilla, ja ilman samaa merkintaa kortti
                # olisi EPAREHELLISEMPI kuin sivu jolle se lukijan lahettaa.
                "promoted": nimi in promoted,
            })

    return {
        "kind": "gw_outlook",
        "gw": gw,
        "goals": sorted(teams, key=lambda t: -t["xg"])[:10],
        "cs": sorted(teams, key=lambda t: -t["cs"])[:10],
        # 🔴 Rajatasapeli: jos sijat 10 ja 11 pyoristyvat SAMAKSI luvuksi,
        # kortti nayttaa toisen karkikympissa ja toisen otteluissa identtisella
        # arvolla, ja on siten ristiriidassa itsensa kanssa. Mitattu 25.8:
        # Brighton 1,301 ja Sunderland 1,300 -> molemmat "1.30". Lippu kertoo
        # renderoijalle etta sarake tarvitsee kolmannen desimaalin.
        "goals_tie": _rajatasapeli(sorted(teams, key=lambda t: -t["xg"]), "xg"),
        "fixtures": sorted(fx, key=lambda f: f.get("kickoff_ms") or 0),
        "promoted": sorted(promoted),
        "generated_at": doc.get("meta", {}).get("generated_at", ""),
        "file": f"goaliq_gw_outlook_gw{gw}.png",
    }


def _promoted_footnote() -> str:
    """Alaviite SAMASTA lahteesta kuin sivun merkinta.

    26.8: alaviite oli kovakoodattu ("baseline rating with no PL history yet")
    ja meni GW2-kortin mukana ulos 25.8. Molemmat puolikkaat olivat silloin jo
    epatosia: GW1 pelattiin 21.-24.8 (= PL-historiaa on) ja artefaktin
    `promoted_baseline_values.applied_to` oli tyhja (= baselinea ei sovelleta).
    Kortti = sivu, joten alaviite luetaan samasta `team_confidence.json`:sta.
    Fail-closed: puuttuva lahde nostaa, ei palaa vanhaan vaitteeseen.
    """
    p = DATA / "team_confidence.json"
    if not p.exists():
        raise SystemExit("kortti: team_confidence.json puuttuu — "
                         "nousija-alaviitetta ei voi johtaa")
    teams = json.loads(p.read_text(encoding="utf-8"))["teams"]
    thin = [t for t in teams
            if t.get("is_promoted") and t.get("basis") == "own_thin_fit"]
    if not thin:
        return "* promoted side, baseline rating with no PL history yet"
    n = min(int(t.get("own_matches") or 0) for t in thin)
    return (f"* promoted side, rating fitted on {n} PL "
            f"{'match' if n == 1 else 'matches'} so far")


#: Julkinen nimi samalle apurille. Kortteja on kolme generaattoria ja
#: kovakoodattu "one PL match" on shipannut jo kerran (25.8), joten
#: alaviite luetaan YHDESTA paikasta (muisti: kuratoitu-lista-jaettuun-moduuliin).
def _turnover_footnote() -> str:
    """Alaviite `high_turnover`-merkille, SAMASTA lahteesta kuin sivu.

    Kynnys luetaan artefaktista eika kovakoodata: `build_team_confidence`
    mittaa sen 51 joukkue-kausivaihdoksesta, ja jos se muuttuu, alaviite
    muuttuu mukana. Fail-closed kuten nousija-alaviite.
    """
    p = DATA / "team_confidence.json"
    if not p.exists():
        raise SystemExit("kortti: team_confidence.json puuttuu - "
                         "vaihtuvuus-alaviitetta ei voi johtaa")
    doc = json.loads(p.read_text(encoding="utf-8"))
    kynnys = doc.get("high_turnover_threshold_pct")
    if kynnys is None:
        return ("† squad turnover above our threshold: a large share of "
                "last season's minutes left the club")
    return (f"† over {float(kynnys):.0f}% of last season's minutes left "
            f"the club")


promoted_footnote = _promoted_footnote
turnover_footnote = _turnover_footnote


def render_gw_outlook(spec: dict, out_path: Path) -> Path:
    """Kolmen sarakkeen kortti. Oma renderoija, koska `render()` on rivilista."""
    from PIL import Image, ImageDraw
    from src.models.team_colors import _team_color

    SHORT = {
        "Arsenal": "ARS", "Aston Villa": "AVL", "Bournemouth": "BOU",
        "Brentford": "BRE", "Brighton & Hove Albion": "BHA", "Chelsea": "CHE",
        "Coventry City": "COV", "Crystal Palace": "CRY", "Everton": "EVE",
        "Fulham": "FUL", "Hull City": "HUL", "Ipswich Town": "IPS",
        "Leeds United": "LEE", "Liverpool": "LIV", "Manchester City": "MCI",
        "Manchester United": "MUN", "Newcastle United": "NEW",
        "Nottingham Forest": "NFO", "Sunderland": "SUN",
        "Tottenham Hotspur": "TOT",
    }

    # Rivin oma `short` voittaa aina; kartta jaa varalle fixture-sarakkeelle
    # jossa rivilla ei ole valmista lyhennetta.
    def sh(name: str, oma: str | None = None) -> str:
        return oma or SHORT.get(name, (name or "?")[:3].upper())

    h = 1010
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y),
                      tuple(int(a + (b - a) * t) for a, b in zip(INK, INK2)))
    canvas = grad.resize((W, h)).convert("RGBA")
    d = ImageDraw.Draw(canvas)

    if WORDMARK.exists():
        wm = Image.open(WORDMARK).convert("RGBA")
        wm_h = 60
        wm = wm.resize((int(wm.width * wm_h / wm.height), wm_h), Image.LANCZOS)
        canvas.alpha_composite(wm, (W - MX - wm.width, 52))

    f_t = _font(FONT_BOLD, 52)
    d.text((MX, 52), "PROJECTED GOALS", font=f_t, fill=CREAM)
    d.text((MX, 108), "& CLEAN SHEET %", font=f_t, fill=CREAM)
    gw_x = MX + d.textlength("& CLEAN SHEET % ", font=f_t)
    d.text((gw_x, 108), f"GW{spec['gw']}", font=f_t, fill=AMBER)

    f_s = _font(FONT_MED, 20)
    # 🔴 PAIVAYS. Projektiot paivittyvat paivittain ja kortti postataan
    # tyypillisesti 1-3 vrk generoinnin jalkeen. Ilman aikaleimaa kortti
    # nayttaa vaaralta sina hetkena kun luvut liikkuvat, eika lukija voi
    # tietaa kummalla on oikeassa.
    _gen = (spec.get("generated_at") or "")[:10]
    _stamp = ""
    if len(_gen) == 10:
        _kk = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        try:
            _stamp = (f"  ·  as of {int(_gen[8:10])} "
                      f"{_kk[int(_gen[5:7]) - 1]}")
        except (ValueError, IndexError):
            _stamp = ""
    d.text((MX, 176), "Dixon-Coles match model" + _stamp, font=f_s, fill=MUTED)

    PANEL_BG = (24, 23, 21)

    def _ring(rgb: tuple) -> tuple:
        """Palloviivan vari: vaalea jos tayttovari sulautuu paneeliin.

        Fulhamin musta (#000) piirtyi paneelin taustaa (24,23,21) vasten
        vakioviivalla (60,58,54) niin etta pallo luki REIKANA eika merkkina.
        Kynnys on luminanssiero eika nimilista, jotta myos tulevat tummat
        asut (esim. uusi nousija) hoituvat ilman etta joku muistaa lisata
        ne kasin.
        """
        lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        bg = 0.2126 * PANEL_BG[0] + 0.7152 * PANEL_BG[1] + 0.0722 * PANEL_BG[2]
        return (150, 146, 138) if abs(lum - bg) < 42 else (60, 58, 54)

    top = 236
    col_w, gap = 288, 26
    # Paneelin korkeus: sisalto + ALAMARGINAALI. Ilman jalkimmaista termia
    # ottelusarakkeen viimeinen rivi ULOTTUI paneelin ulkopuolelle (sen
    # sisalto on 2 rivia a 24 px eika 1 x 40 px kuten kahdessa muussa), ja
    # se luki kuvassa katkaistulta. Sama korkeus kaikkiin kolmeen, jotta ne
    # pysyvat linjassa.
    def _panel_bottom(n: int) -> int:
        return top + 60 + n * 62

    f_hdr = _font(FONT_BOLD, 22)
    f_rank = _font(FONT_MED, 18)
    f_team = _font(FONT_BOLD, 30)
    f_val = _font(FONT_BOLD, 30)

    def column(x: int, title: str, rows: list, fmt) -> None:
        d.rounded_rectangle([x, top, x + col_w, _panel_bottom(len(rows))],
                            radius=14, fill=PANEL_BG)
        d.text((x + 16, top + 12), title, font=f_hdr, fill=AMBER)
        for i, r in enumerate(rows):
            y = top + 52 + i * 62
            d.text((x + 16, y + 14), f"{i + 1:>2}", font=f_rank, fill=MUTED)
            code = sh(r["team"], r.get("short"))
            col, _ = _team_color(code)
            _draw_kit_pil(canvas, x + 44, y + 4, 40, code)
            # Nousija saa tahden: sivu merkitsee sen "baseline rating"
            # -tekstilla, ja ilman samaa merkintaa kortti vaittaisi enemman
            # kuin sivu jolle se lukijan lahettaa.
            if r.get("promoted"):
                code = code + "*"
            d.text((x + 88, y + 8), code, font=f_team, fill=CREAM)
            v = fmt(r)
            d.text((x + col_w - 16 - d.textlength(v, font=f_val), y + 8),
                   v, font=f_val, fill=AMBER)

    # Kolmas desimaali VAIN kun raja on nakymaton (ks. _rajatasapeli).
    _gd = 3 if spec.get("goals_tie") else 2
    column(MX, "PROJECTED GOALS", spec["goals"],
           lambda r: f"{r['xg']:.{_gd}f}")
    column(MX + col_w + gap, "CLEAN SHEET %", spec["cs"], lambda r: _pros(r["cs"]))

    # Kolmas sarake: ottelut. Wolfyn ehdotus 17.8 - ottelut ovat dataa,
    # "top takeaways" olisi mielipidetta.
    fx_x = MX + 2 * (col_w + gap)
    fx_w = W - MX - fx_x
    fxs = spec["fixtures"]
    d.rounded_rectangle([fx_x, top, fx_x + fx_w, _panel_bottom(len(fxs))],
                        radius=14, fill=PANEL_BG)
    d.text((fx_x + 16, top + 12), "FIXTURES", font=f_hdr, fill=AMBER)
    f_fx = _font(FONT_BOLD, 22)
    f_fxs = _font(FONT_MED, 15)
    # 17.8 (Wolfyn ehdotus): projisoidut maalit ottelurivin viereen. Ilman
    # niita tama sarake on ainoa jossa ei ole yhtaan lukua, eli rakennetta
    # ilman tietoa. Vasen sarake vastaa kysymykseen "kuka tekee eniten",
    # tama vastaa kysymykseen "mita tassa ottelussa tapahtuu" - eri
    # kysymyksia, joten toisto on tarkoituksellista eika laiskuutta.
    f_fxn = _font(FONT_BOLD, 20)
    for i, f in enumerate(fxs):
        y = top + 52 + i * 62
        for j, (name, xg, lyh) in enumerate((
                (f["home"], f["xg_home"], f.get("home_short")),
                (f["away"], f["xg_away"], f.get("away_short")))):
            code = sh(name, lyh)
            col, _ = _team_color(code)
            ry = y + 6 + j * 24
            _draw_kit_pil(canvas, fx_x + 10, ry - 2, 24, code)
            # Portti 2.9: nousijatahti myos ottelusarakkeeseen. Ilman sita kortin
            # karkiluku (MCI 41 % v COV) oli ainoa jonka ohut osapuoli jai
            # merkitsematta, kun sivu merkitsee Coventryn omalla rivillaan.
            if name in (spec.get("promoted") or []):
                code = code + "*"
            d.text((fx_x + 38, ry), code, font=f_fx, fill=CREAM)
            v = f"{xg:.2f}"
            d.text((fx_x + 156 - d.textlength(v, font=f_fxn), ry + 1),
                   v, font=f_fxn, fill=AMBER)
        # Paivays OIKEAAN laitaan. Kiintea x+178 jatti paneelin oikeaan
        # reunaan ~65 px tyhjaa kourua samalla kun vasen oli 14 px, ja
        # sarake luki keskeneraiselta vaikka mitaan ei puuttunut.
        ko = (f.get("kickoff") or "").split(",")[0].replace(" 2026", "")
        d.text((fx_x + fx_w - 16 - d.textlength(ko, font=f_fxs), y + 18),
               ko, font=f_fxs, fill=MUTED)

    f_foot = _font(FONT_MED, 19)
    # 🔴 NOUSIJA-ALAVIITE. Ilman tata "COV #3" lukee ansaittuna reittauksena
    # ja on kortin toimintakehotus (osta nousijan puolustaja), vaikka luku on
    # empiirinen nousijabaseline eika mitattu PL-suoritus.
    if spec.get("promoted"):
        foot = _promoted_footnote()
        f_note = _font(FONT_MED, 16)
        # 🔴 MITTAA, ALA OLETA. Ensimmainen johdettu sanamuoto oli 7 merkkia
        # pidempi kuin kovakoodattu ja VALUI ottelupaneelin alle: alaviite
        # luki "...match so fa" renderoidyssa kuvassa. Teksti joka katkeaa
        # keskella varausta on huonompi kuin ei varausta, joten leveys on
        # portti eika tyylikysymys.
        avail = fx_x - MX - 12
        if d.textlength(foot, font=f_note) > avail:
            raise SystemExit(
                f"kortti: nousija-alaviite ei mahdu ({foot!r}, "
                f"{d.textlength(foot, font=f_note):.0f}px > {avail}px)")
        d.text((MX, h - 116), foot, font=f_note, fill=MUTED)
    d.text((MX, h - 84), "every club, both columns, on goaliq.app/fpl, free",
           font=f_foot, fill=MUTED)
    d.text((MX, h - 52), "model projections, not betting advice",
           font=_font(FONT_MED, 16), fill=MUTED)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


def render_gw_outlook_hero(spec: dict, out_path: Path, cs_only: bool = False) -> Path:
    """Hero-versio (9.9.2026, Villen pyynto: "grafiikoiltaan paremmaksi,
    sellaiseksi mika houkuttaisi ja myisi").

    Sama spec ja sama sivupariteettitesti kuin `render_gw_outlook`, eri
    hierarkia: YKSI iso luku (paras nollapelisauma), sen alla top 5 nollapeli
    ja top 5 maalit isommalla rivilla, ottelut tiiviina ruudukkona, ja
    alarivi joka sanoo mista loput 20 loytyvat. Mitattu syy: M76-kortti
    (30 lukua) 1 456 nayttoa vs tekstipostaus 13 - kuva kantaa, mutta 30
    samanarvoista lukua ei anna silmalle paikkaa aloittaa.
    """
    from PIL import Image, ImageDraw
    from src.models.team_colors import _team_color

    h = 1400  # rajataan lopussa sisallon mukaan (crop), ei arvata
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y),
                      tuple(int(a + (b - a) * t) for a, b in zip(INK, INK2)))
    canvas = grad.resize((W, h)).convert("RGBA")
    d = ImageDraw.Draw(canvas)
    PANEL_BG = (24, 23, 21)
    LINE = (48, 46, 42)

    def sh(r: dict) -> str:
        code = r.get("short") or (r.get("team") or "?")[:3].upper()
        return code + ("*" if r.get("promoted") else "")

    # --- otsikko ---
    if WORDMARK.exists():
        wm = Image.open(WORDMARK).convert("RGBA")
        wm_h = 56
        wm = wm.resize((int(wm.width * wm_h / wm.height), wm_h), Image.LANCZOS)
        canvas.alpha_composite(wm, (W - MX - wm.width, 48))
    f_t = _font(FONT_BOLD, 44)
    otsikko = "CLEAN SHEET CHANCES" if cs_only else "CLEAN SHEETS & GOALS"
    d.text((MX, 48), otsikko, font=f_t, fill=CREAM)
    gw_x = MX + d.textlength(otsikko + " ", font=f_t)
    d.text((gw_x, 48), f"GW{spec['gw']}", font=f_t, fill=AMBER)
    _gen = (spec.get("generated_at") or "")[:10]
    _stamp = ""
    if len(_gen) == 10:
        _kk = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        try:
            _stamp = f"  ·  as of {int(_gen[8:10])} {_kk[int(_gen[5:7]) - 1]}"
        except (ValueError, IndexError):
            _stamp = ""
    d.text((MX, 104), "Dixon-Coles match model" + _stamp,
           font=_font(FONT_MED, 19), fill=MUTED)

    # --- hero: paras nollapelisauma ---
    cs = spec["cs"]
    top1 = cs[0]
    vastustaja, venue = "", ""
    for f in spec["fixtures"]:
        if f["home"] == top1["team"]:
            vastustaja, venue = f.get("away_short") or f["away"][:3].upper(), "(H)"
        elif f["away"] == top1["team"]:
            vastustaja, venue = f.get("home_short") or f["home"][:3].upper(), "(A)"
    if vastustaja and (vastustaja.rstrip("*") in (spec.get("promoted") or [])
                       or any(x in vastustaja for x in ())):
        pass
    # nousijatahti vastustajalle samalla saannolla kuin riveilla
    for f in spec["fixtures"]:
        for side, oma in (("home", "away"), ("away", "home")):
            if f[side] == top1["team"] and f[oma] in (spec.get("promoted") or []):
                vastustaja = vastustaja + "*"

    hero_top = 150
    d.rounded_rectangle([MX, hero_top, W - MX, hero_top + 214], radius=18,
                        fill=PANEL_BG)
    d.text((MX + 24, hero_top + 18), "BEST CLEAN SHEET CHANCE", font=_font(FONT_BOLD, 22),
           fill=AMBER)
    code1 = sh(top1)
    _draw_kit_pil(canvas, MX + 24, hero_top + 62, 96, code1.rstrip("*"))
    f_big = _font(FONT_BOLD, 112)
    val = f"{top1['cs']:g}%"
    d.text((MX + 140, hero_top + 44), val, font=f_big, fill=AMBER)
    vx = MX + 140 + d.textlength(val, font=f_big) + 28
    d.text((vx, hero_top + 66), code1, font=_font(FONT_BOLD, 46), fill=CREAM)
    if vastustaja:
        d.text((vx, hero_top + 122), f"v {vastustaja} {venue}",
               font=_font(FONT_MED, 26), fill=MUTED)
    # toiseksi paras oikeaan laitaan: gappi on koko pointti
    if len(cs) > 1:
        nxt = cs[1]
        txt2 = f"next best {sh(nxt)} {nxt['cs']:g}%"
        f2 = _font(FONT_MED, 22)
        d.text((W - MX - 24 - d.textlength(txt2, font=f2), hero_top + 176),
               txt2, font=f2, fill=MUTED)

    # --- kaksi saraketta, top 5 ---
    top = hero_top + 240
    col_w, gap = 388, 24
    n = 5
    row_h = 66
    f_hdr = _font(FONT_BOLD, 22)
    f_rank = _font(FONT_MED, 18)
    f_team = _font(FONT_BOLD, 32)
    f_val = _font(FONT_BOLD, 34)

    def column(x: int, title: str, rows: list, fmt) -> None:
        d.rounded_rectangle([x, top, x + col_w, top + 58 + n * row_h],
                            radius=14, fill=PANEL_BG)
        d.text((x + 18, top + 14), title, font=f_hdr, fill=AMBER)
        for i, r in enumerate(rows[:n]):
            y = top + 54 + i * row_h
            if i:
                d.line([(x + 18, y), (x + col_w - 18, y)], fill=LINE, width=1)
            d.text((x + 18, y + 20), f"{i + 1}", font=f_rank, fill=MUTED)
            code = sh(r)
            _draw_kit_pil(canvas, x + 46, y + 10, 42, code.rstrip("*"))
            d.text((x + 100, y + 12), code, font=f_team, fill=CREAM)
            v = fmt(r)
            d.text((x + col_w - 18 - d.textlength(v, font=f_val), y + 10),
                   v, font=f_val, fill=AMBER)

    _gd = 3 if spec.get("goals_tie") else 2
    if cs_only:
        # 9.9 portti: projisoidut maalit eivat ole millaan ilmaissivulla,
        # joten kortti joka lahettaa lukijan goaliq.app/fpl:aan ei saa
        # nayttaa niita (QUEUE FPL-SIVU-OTTELUIDEN-XG). Nollapeli-% on
        # sivulla rivi rivilta: kaksi saraketta, sijat 1-5 ja 6-10.
        column(MX, "CLEAN SHEET %  ·  1-5", cs[:5], lambda r: f"{r['cs']:g}%")
        rows6 = cs[5:10]
        x2 = MX + col_w + gap
        d.rounded_rectangle([x2, top, x2 + col_w, top + 58 + n * row_h],
                            radius=14, fill=PANEL_BG)
        d.text((x2 + 18, top + 14), "CLEAN SHEET %  ·  6-10", font=f_hdr, fill=AMBER)
        for i, r in enumerate(rows6):
            y = top + 54 + i * row_h
            if i:
                d.line([(x2 + 18, y), (x2 + col_w - 18, y)], fill=LINE, width=1)
            d.text((x2 + 18, y + 20), f"{i + 6}", font=f_rank, fill=MUTED)
            code = sh(r)
            _draw_kit_pil(canvas, x2 + 46, y + 10, 42, code.rstrip("*"))
            d.text((x2 + 100, y + 12), code, font=f_team, fill=CREAM)
            v = f"{r['cs']:g}%"
            d.text((x2 + col_w - 18 - d.textlength(v, font=f_val), y + 10),
                   v, font=f_val, fill=AMBER)
    else:
        column(MX, "CLEAN SHEET %", cs, lambda r: f"{r['cs']:g}%")
        column(MX + col_w + gap, "PROJECTED GOALS", spec["goals"],
               lambda r: f"{r['xg']:.{_gd}f}")

    # --- ottelut tiiviina kahdessa sarakkeessa ---
    fx_top = top + 58 + n * row_h + 22
    fxs = [] if cs_only else spec["fixtures"]
    per_col = (len(fxs) + 1) // 2
    fx_row = 40
    if fxs:
        d.rounded_rectangle([MX, fx_top, W - MX, fx_top + 50 + per_col * fx_row],
                            radius=14, fill=PANEL_BG)
        d.text((MX + 18, fx_top + 12), "FIXTURES · projected goals",
               font=f_hdr, fill=AMBER)
    f_fx = _font(FONT_BOLD, 21)
    f_fxn = _font(FONT_BOLD, 20)
    f_fxs = _font(FONT_MED, 15)
    half = (W - 2 * MX) // 2
    for i, f in enumerate(fxs):
        cx = MX + (i // per_col) * half
        y = fx_top + 48 + (i % per_col) * fx_row
        hs = (f.get("home_short") or f["home"][:3].upper()) + \
            ("*" if f["home"] in (spec.get("promoted") or []) else "")
        as_ = (f.get("away_short") or f["away"][:3].upper()) + \
            ("*" if f["away"] in (spec.get("promoted") or []) else "")
        _draw_kit_pil(canvas, cx + 18, y + 2, 26, hs.rstrip("*"))
        d.text((cx + 50, y + 3), hs, font=f_fx, fill=CREAM)
        v1 = f"{f['xg_home']:.2f}"
        d.text((cx + 138, y + 4), v1, font=f_fxn, fill=AMBER)
        d.text((cx + 198, y + 4), "-", font=f_fxn, fill=MUTED)
        v2 = f"{f['xg_away']:.2f}"
        d.text((cx + 220, y + 4), v2, font=f_fxn, fill=AMBER)
        _draw_kit_pil(canvas, cx + 288, y + 2, 26, as_.rstrip("*"))
        d.text((cx + 320, y + 3), as_, font=f_fx, fill=CREAM)
        # Vain viikonpaiva: koko paivays tormasi vieraspaitaan (mitattu 9.9)
        # ja kierroksen paivat ovat kortin otsikossa jo GW-numerona.
        ko = (f.get("kickoff") or "").split(" ")[0]
        d.text((cx + half - 18 - d.textlength(ko, font=f_fxs), y + 7),
               ko, font=f_fxs, fill=MUTED)

    # --- alarivit: nousijaviite + myyva reitti ---
    y0 = (fx_top + 50 + per_col * fx_row + 18) if fxs else fx_top
    # 9.9 portti: alarivi leikkautui kanvaasin reunaan ("advice" katkesi) koska
    # vain nousija-alaviitteella oli leveysvahti. Jokainen alarivi mitataan;
    # ylivuoto kaataa ajon, ei julkaise katkennutta vastuuvapautta.
    def _rivi(y: int, teksti: str, font, fill) -> None:
        if d.textlength(teksti, font=font) > W - 2 * MX:
            raise SystemExit(
                f"kortti: alarivi ei mahdu ({teksti!r}, "
                f"{d.textlength(teksti, font=font):.0f}px > {W - 2 * MX}px)")
        d.text((MX, y), teksti, font=font, fill=fill)
    if spec.get("promoted") and any(r.get("promoted") for r in
                                    (cs[:10] + ([] if cs_only else spec["goals"]))
                                    ) or (fxs and spec.get("promoted")):
        _rivi(y0, _promoted_footnote(), _font(FONT_MED, 16), MUTED)
        y0 += 26
    _rivi(y0 + 2, "All 20 teams, every gameweek: goaliq.app/fpl  ·  free, no account",
          _font(FONT_BOLD, 21), CREAM)
    _rivi(y0 + 34, "Match predictions logged before kick-off and graded in public.  ·  not betting advice",
          _font(FONT_MED, 15), MUTED)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = canvas.crop((0, 0, W, y0 + 72))
    canvas.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


BUILDERS = {"cs": card_cs, "defence": card_defence, "stats": card_stats,
            "xp": card_xp, "value": card_value, "club-best": card_club_best,
            "price-tier": card_price_tier,
            "gw-outlook": card_gw_outlook}
GW_CAPABLE = {"cs"}


# ---------------------------------------------------------------------------
# POSTATTU-KORTTI-EI-OLE-TALLESSA (12.9.2026)
# ---------------------------------------------------------------------------
# `outputs/` on .gitignoressa ja jokainen ajo kirjoittaa saman tiedostonimen
# yli, joten postatun kortin sisaltoa ei voinut myohemmin todistaa: 9.9
# postattu GW4-kortti (M82) ei ollut enaa olemassa missaan, ja MARKETING_QUEUE
# viittasi commitiin jossa sita ei ollut. Sidecar tallentaa PNG:n vieressa
# sen mita postaus vaitti postanneensa (rivit + sha256), jotta vaite on
# jalkikateen tarkistettavissa riippumatta siita kirjoittaako seuraava ajo
# saman tiedostonimen paalle.
def sidecar_path(png_path: Path) -> Path:
    return png_path.with_suffix(png_path.suffix + ".json")


def write_sidecar(spec: dict, card: str, png_path: Path) -> Path:
    """Kirjoita PNG:n vierelle JSON: rivit + artefaktin generated_at + sha256.

    sha256 lasketaan JUURI KIRJOITETUSTA tiedostosta (ei muistin canvasista),
    jotta sidecar todistaa mita levylla oikeasti on eika mita render() luuli
    kirjoittavansa.
    """
    png_bytes = png_path.read_bytes()
    payload = {
        "card": card,
        # Milloin TAMA sidecar (ja siis kortti) generoitiin.
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(
            timespec="seconds"),
        # Lahdeartefaktin oma generated_at JOS builder sen tunsi (esim.
        # gw-outlook). Tyhja merkkijono != puuttuva kentta: puuttuva kentta
        # nayttaisi vanhalta sidecarilta, tyhja sanoo etta lahde ei kanna sita.
        "source_generated_at": spec.get("generated_at") or "",
        "rows": spec.get("rows", []),
        "sha256": hashlib.sha256(png_bytes).hexdigest(),
    }
    out = sidecar_path(png_path)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return out


def verify_sidecar(png_path: Path) -> None:
    """Kaada kutsuja jos kortista ei voi todistaa mita se vaitti olevansa.

    Kolme tapaa epaonnistua, jokainen oma virheensa: PNG puuttuu, sidecar
    puuttuu, tai sha256 ei tasmaa (tiedosto vaihtui/korruptoitui sidecarin
    kirjoittamisen jalkeen). Tarkoitettu kaytettavaksi POSTATTU-rivin
    portista: rivi jolla on kortti ilman tallennettua kuvaa TAI shaa ei saa
    lapaista hiljaa.
    """
    if not png_path.exists():
        raise FileNotFoundError(f"kortin PNG puuttuu: {png_path}")
    sc = sidecar_path(png_path)
    if not sc.exists():
        raise FileNotFoundError(
            f"kortilla ei ole sidecaria (rivit/sha todistamatta): {sc}")
    payload = json.loads(sc.read_text(encoding="utf-8"))
    actual = hashlib.sha256(png_path.read_bytes()).hexdigest()
    if payload.get("sha256") != actual:
        raise ValueError(
            f"kortin sha256 ei tasmaa sidecariin (tiedosto vaihtunut "
            f"sidecarin kirjoittamisen jalkeen?): {png_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="GoalIQ share card generator")
    ap.add_argument("card", choices=sorted(BUILDERS))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--from-gw", type=int, default=1)
    ap.add_argument("--to-gw", type=int, default=6)
    ap.add_argument("--metric", choices=("avg", "total"), default="avg",
                    help="cs: avg = CS%% per ottelu, total = odotetut puhtaat "
                         "pelit ikkunassa")
    ap.add_argument("--sort", default="pts", help="stats: sarake (esim. xgi)")
    ap.add_argument("--min-mins", type=int, default=400,
                    help="stats: minimiminuutit")
    ap.add_argument("--pos", default=None, help="stats: GKP/DEF/MID/FWD")
    ap.add_argument("--team", default=None, help="stats: joukkuelyhenne (ARS)")
    ap.add_argument("--max-price", type=float, default=None,
                    help="price-tier: hintakatto miljoonissa (esim. 8.0)")
    ap.add_argument("--rank-cap", type=int, default=None,
                    help="price-tier: pudota rivit jotka eivat mahdu ilmaissivun "
                         "top-N:aan (tarkistettavuus). /fpl/expected-points = 100")
    ap.add_argument("--gw", type=int, default=None,
                    help="gw-outlook: kierros (oletus: pienin datassa)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--style", choices=("classic", "hero"), default="classic",
                    help="gw-outlook: hero = yksi iso karkiluku + top 5 (9.9)")
    ap.add_argument("--cs-only", action="store_true",
                    help="gw-outlook hero: vain nollapeli-%% (maalit eivat ole "
                         "ilmaissivulla, portti 9.9)")
    a = ap.parse_args()

    gw_given = any(x.startswith("--from-gw") or x.startswith("--to-gw")
                   for x in sys.argv[1:])
    if gw_given and a.card not in GW_CAPABLE:
        # Hiljaa ohitettu lippu on pahempi kuin virhe: kortin otsikko
        # lupaisi ikkunan jota data ei kanna.
        raise SystemExit(
            f"--from-gw/--to-gw ei ole tuettu kortille {a.card!r}: sen data on "
            f"kauden aggregaatti ilman gameweek-erittelya. GW-ikkuna toimii: "
            f"{', '.join(sorted(GW_CAPABLE))}")

    spec = BUILDERS[a.card](a)
    out = Path(a.out) if a.out else OUT_DIR / spec["file"]
    if spec.get("kind") == "gw_outlook":
        if a.style == "hero":
            if not a.out:
                out = OUT_DIR / spec["file"].replace(
                    ".png", "_hero_cs.png" if a.cs_only else "_hero.png")
            pth = render_gw_outlook_hero(spec, out, cs_only=a.cs_only)
        else:
            pth = render_gw_outlook(spec, out)
        sc = write_sidecar(spec, a.card, pth)
        print("GW%s outlook (%d ottelua) -> %s (sidecar %s)"
              % (spec["gw"], len(spec["fixtures"]), pth, sc))
        return 0
    p = render(spec, out)
    sc = write_sidecar(spec, a.card, p)
    print(f"{spec['title']} ({len(spec['rows'])} rivia) -> {p} (sidecar {sc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
