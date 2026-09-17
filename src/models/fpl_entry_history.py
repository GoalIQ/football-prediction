"""Entryn julkisesta datasta johdetut tilat (3.9.2026, CHIP-EV-BUDGET;
laajennettu 17.9.2026 FREEZE-BANK-MYYNTIHINTA).

Lahteet, kaikki julkisia ilman kirjautumista:
  `entry/{id}/history/`   -> `current` [{event, event_transfers,
                             event_transfers_cost, bank, value, ...}]
                             ja `chips` [{name, event}]
  `entry/{id}/transfers/` -> [{element_in, element_in_cost, element_out,
                             element_out_cost, event, time}]
  `bootstrap-static/`     -> `elements` [{id, now_cost, cost_change_start, ...}]

Johdetut luvut:

  team_value_tenths(history): kauden viimeisin `value`.
    MITATTU 17.9.2026 KOLMESTA DEADLINESTA (entry 116920, repon omat
    hintasnapshotit 4 min deadlinen jalkeen): `value - bank` on rungon
    NYKYHINTOJEN summa, EI myyntihintojen. GW2 991/991, GW3 993/993,
    GW4 994/994; myyntihintasumma samoilla ostohinnoilla oli 991 kaikissa.
    `value` on siis nayttoluku, ei se raha jolla siirto oikeasti tehdaan.

  bank_tenths(history, gw): FPL:n oma pankki kymmenyksina kierroksen
    deadlinella. Se EI muutu hintaliikkeista, vain siirroista - joten se on
    tosi niin kauan kuin entry ei ole tehnyt siirtoja rivin jalkeen.

  selling_prices(...): jokaisen rungon jasenen MYYNTIHINTA FPL:n saannolla:
    hinnan noustua myyja saa ostohinnan + puolet voitosta alaspain
    pyoristettyna (4.5 -> 4.6 myy 4.5; 4.6 -> 4.9 myy 4.7); laskeneesta
    nykyhinnan. Ostohinta on `element_in_cost` siirtolistalta, tai kauden
    alkuhinta (`now_cost - cost_change_start`) jos pelaaja on ollut
    rungossa GW1:sta asti. FPL ei julkaise myyntihintaa julkisesti
    (`picks[]` ei kanna sita; se on vain kirjautuneen `my-team`-vastauksessa),
    joten tama on PAATELMA kahdesta FPL:n omasta luvusta ja pelin saannosta.

  infer_free_transfers(history): vapaiden siirtojen saldo seuraavalle
    kierrokselle. FPL ei julkaise saldoa, mutta se seuraa saannosta:
    kausi alkaa 1 FT:lla, joka kierroksen jalkeen +1, katto 5, tehdyt siirrot
    kuluttavat saldoa (hitit eivat vie miinukselle), ja wildcard/free hit
    -kierroksella siirrot eivat kuluta (saldo sailyy, ei kerry). Tama on
    PAATELMA julkisesta datasta, ei pelin oma luku -> vastaus merkitsee sen
    `ft_source = "inferred_from_history"`.

  entry_state(...): YKSI LUKIJA joka kokoaa ylla olevat yhdeksi tilaksi
    freezea varten. Puuttuva lahde on virhe (`EntryStateError`), ei oletus:
    vaara pankki tai vaara myyntihinta muuttaisi siirtomoottorin vastausta
    hiljaa, ja jaadytys on immutable.
"""
from __future__ import annotations

FT_MAX = 5
# 3.9 PORTTI: alkuarvo oli 1 ja tuotti systemaattisesti yhden liikaa.
# GW1 on rajattomien siirtojen kierros, joten GW2:een tullaan 1 FT:lla, ei
# kahdella. Portti mittasi 450 entrysta: GW2:ssa tr=2 maksoi -4 (n=7), eli
# saldo oli 1; funktio olisi sanonut 2. Silmukka lisaa +1 jokaisen pelatun
# kierroksen jalkeen, joten alkuarvo on 0.
FT_START = 0

#: Chipit joiden kierroksella siirrot eivat kuluta FT-saldoa.
FT_PRESERVING_CHIPS = ("wildcard", "freehit")


class EntryStateError(ValueError):
    """Entryn tilaa ei voitu johtaa julkisesta datasta. Ei sama asia kuin
    oletusarvo: kutsuja ei saa jatkaa arvauksella."""


def team_value_tenths(history: dict | None) -> int | None:
    rows = [r for r in ((history or {}).get("current") or [])
            if isinstance(r.get("value"), int) and r["value"] > 0]
    if not rows:
        return None
    return int(max(rows, key=lambda r: int(r.get("event") or 0))["value"])


def history_row(history: dict | None, gw: int) -> dict | None:
    """Historian rivi kierrokselle `gw`, tai None."""
    for r in (history or {}).get("current") or []:
        if isinstance(r.get("event"), int) and r["event"] == int(gw):
            return r
    return None


def bank_tenths(history: dict | None, gw: int) -> int | None:
    """FPL:n oma `bank` kierroksen `gw` deadlinella, kymmenyksina."""
    row = history_row(history, gw)
    if row is None or not isinstance(row.get("bank"), int):
        return None
    return int(row["bank"])


def value_tenths(history: dict | None, gw: int) -> int | None:
    """FPL:n oma `value` (nykyhinnat + pankki) kierroksen deadlinella."""
    row = history_row(history, gw)
    if row is None or not isinstance(row.get("value"), int):
        return None
    return int(row["value"])


def chip_gws(history: dict | None, names=FT_PRESERVING_CHIPS) -> set[int]:
    return {int(c.get("event")) for c in ((history or {}).get("chips") or [])
            if str(c.get("name")) in names and isinstance(c.get("event"), int)}


def infer_free_transfers(history: dict | None) -> int | None:
    """FT-saldo seuraavalle pelaamattomalle kierrokselle, tai None jos
    historiaa ei ole."""
    rows = sorted((r for r in ((history or {}).get("current") or [])
                   if isinstance(r.get("event"), int)),
                  key=lambda r: r["event"])
    if not rows:
        return None
    chip_gws_ = chip_gws(history)
    ft = FT_START
    for r in rows:
        made = int(r.get("event_transfers") or 0)
        # 6.9 (FPL:n saanto, tarkistettu premierleague.com + FFScout 13.3.2025):
        # wildcard- tai free hit -kierros SAILYTTAA saastetyt siirrot
        # sellaisenaan eika kerryta uutta: "if you had 2 saved free transfers,
        # you will still have 2 the Gameweek after playing the chip".
        # Vanha versio kerrytti +1 myos chip-kierroksella ja antoi entrylle
        # 116920 GW4:lle 3, kun FPL (ja Solio) nayttaa 2.
        if r["event"] in chip_gws_:
            continue
        ft = max(ft - made, 0)
        ft = min(FT_MAX, ft + 1)
    return ft


# ---------------------------------------------------------------------------
# Myyntihinta (17.9.2026, FREEZE-BANK-MYYNTIHINTA)
# ---------------------------------------------------------------------------

def selling_price(purchase_tenths: int, now_tenths: int) -> int:
    """FPL:n saanto: noususta myyja saa puolet voitosta alaspain pyoristettyna
    (kymmenyksissa: kokonaislukujako), laskusta nykyhinnan."""
    purchase = int(purchase_tenths)
    now = int(now_tenths)
    if now > purchase:
        return purchase + (now - purchase) // 2
    return now


def purchase_prices(pick_ids, transfers: list[dict] | None, bootstrap: dict,
                    *, upto_gw: int | None = None,
                    freehit_gws=()) -> dict[int, int]:
    """Ostohinta kymmenyksina jokaiselle `pick_ids`:n pelaajalle.

    Siirrolla tullut: VIIMEISIN `element_in_cost` (ajan mukaan) kierroksilta
    <= `upto_gw`, free hit -kierroksia lukuun ottamatta (FH-runko palautuu
    kierroksen jalkeen ostohintoineen). Muu: kauden alkuhinta bootstrapista,
    `now_cost - cost_change_start` - pelaaja on ollut rungossa GW1:sta asti
    eika hintaa voi olla maksettu muuta kuin alkuhinta.

    Puuttuva lahde on virhe. Kentta `cost_change_start` vaaditaan
    eksplisiittisesti: sen puuttuminen tarkoittaa ettei `bootstrap` ole
    FPL:n bootstrap-static, ja oletus 0 antaisi vaaran ostohinnan hiljaa.
    """
    ids = [int(i) for i in pick_ids]
    fh = {int(g) for g in (freehit_gws or ())}
    viimeisin: dict[int, tuple[tuple, int]] = {}
    for t in transfers or []:
        try:
            pid = int(t["element_in"])
            cost = int(t["element_in_cost"])
            ev = int(t.get("event") or 0)
        except (KeyError, TypeError, ValueError) as e:
            raise EntryStateError(f"siirtorivi ei ole FPL:n muotoa: {t!r} ({e!r})")
        if upto_gw is not None and ev > int(upto_gw):
            continue
        if ev in fh:
            continue
        avain = (ev, str(t.get("time") or ""))
        if pid not in viimeisin or avain > viimeisin[pid][0]:
            viimeisin[pid] = (avain, cost)
    el = {int(e.get("id") or 0): e for e in (bootstrap or {}).get("elements") or []}
    out: dict[int, int] = {}
    puuttuu: list[int] = []
    for pid in ids:
        if pid in viimeisin:
            out[pid] = viimeisin[pid][1]
            continue
        e = el.get(pid)
        if e is None or "now_cost" not in e or "cost_change_start" not in e:
            puuttuu.append(pid)
            continue
        out[pid] = int(e["now_cost"]) - int(e["cost_change_start"])
    if puuttuu:
        raise EntryStateError(
            f"ostohintaa ei voi johtaa pelaajille {puuttuu}: ei siirtolistalla "
            f"eika bootstrapissa (now_cost + cost_change_start)")
    return out


def now_prices(pick_ids, bootstrap: dict) -> dict[int, int]:
    """FPL:n `now_cost` kymmenyksina jokaiselle pelaajalle; puuttuva on virhe."""
    el = {int(e.get("id") or 0): e for e in (bootstrap or {}).get("elements") or []}
    out: dict[int, int] = {}
    puuttuu = []
    for pid in (int(i) for i in pick_ids):
        e = el.get(pid)
        if e is None or not isinstance(e.get("now_cost"), int):
            puuttuu.append(pid)
            continue
        out[pid] = int(e["now_cost"])
    if puuttuu:
        raise EntryStateError(f"now_cost puuttuu bootstrapista pelaajille {puuttuu}")
    return out


def selling_prices(pick_ids, transfers: list[dict] | None, bootstrap: dict,
                   *, upto_gw: int | None = None,
                   freehit_gws=()) -> dict[int, int]:
    osto = purchase_prices(pick_ids, transfers, bootstrap, upto_gw=upto_gw,
                           freehit_gws=freehit_gws)
    nyt = now_prices(pick_ids, bootstrap)
    return {pid: selling_price(osto[pid], nyt[pid]) for pid in osto}


def entry_state(history: dict | None, gw: int, pick_ids,
                transfers: list[dict] | None, bootstrap: dict) -> dict:
    """YKSI LUKIJA entryn rahatilalle kierroksen `gw` rungolle.

    Palauttaa:
      bank_tenths          FPL:n oma pankki (kierroksen rivilta)
      value_tenths         FPL:n oma `value` (nykyhinnat + pankki, naytto)
      purchase             {id: ostohinta}
      selling              {id: myyntihinta}  <- moottorin lahtijan hinta
      now                  {id: nykyhinta}
      selling_value_tenths myyntihintojen summa (se raha joka on OIKEASTI
                           kaytettavissa jos kaikki myydaan, + pankki)

    Jokainen puuttuva palanen on virhe. `transfers` voi olla tyhja lista
    (entry jolla ei ole siirtoja), mutta ei None: None tarkoittaa ettei
    listaa saatu, ja silloin ostohinnat olisivat arvaus.
    """
    ids = [int(i) for i in pick_ids]
    if len(ids) != len(set(ids)):
        raise EntryStateError("rungossa on sama pelaaja kahdesti")
    if transfers is None:
        raise EntryStateError("siirtolistaa ei ole (None) - ostohinnat olisivat arvaus")
    row = history_row(history, gw)
    if row is None:
        raise EntryStateError(f"entryn historiasta puuttuu GW{gw}")
    pankki = bank_tenths(history, gw)
    arvo = value_tenths(history, gw)
    if pankki is None or arvo is None:
        raise EntryStateError(f"GW{gw}:n rivilta puuttuu bank tai value: {row!r}")
    fh = chip_gws(history, names=("freehit",))
    osto = purchase_prices(ids, transfers, bootstrap, upto_gw=gw, freehit_gws=fh)
    nyt = now_prices(ids, bootstrap)
    myynti = {pid: selling_price(osto[pid], nyt[pid]) for pid in ids}
    return {
        "gw": int(gw),
        "bank_tenths": pankki,
        "value_tenths": arvo,
        "purchase": osto,
        "selling": myynti,
        "now": nyt,
        "selling_value_tenths": sum(myynti.values()),
        "bank_source": "fpl_entry_history",
        "selling_source": "fpl_transfers+bootstrap",
    }
