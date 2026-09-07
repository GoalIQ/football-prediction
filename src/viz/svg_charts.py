# -*- coding: utf-8 -*-
"""Inline-SVG-kaaviot julkisille sivuille.

Villen kysymys 7.9.2026: "Grafiikoita?". Mitattu vastaus: koko repossa ei
ollut yhtaan kaaviota julkisella sivulla. `src/viz/` on olemassa, mutta se
on Plotlya ja matplotlibia - kuvageneraattoreita muistikirjoihin, ei
mitaan mika paatyy HTML:aan. Jokainen 180+ sivusta on taulukko.

Tama moduuli tuottaa SVG:ta joka menee sivulle sellaisenaan: ei kirjastoa,
ei JS:aa, ei uutta latausoriginia, ei kuvatiedostoa jonka pitaisi pysya
synkassa datan kanssa. Sama syy kuin fonteissa (yksi perhe, ei uutta
originia).

🔴 KAKSI ASIAA JOTKA KAAVIO VOI VALEHDELLA, JA JOTKA ON TEHTY MAHDOTTOMIKSI

**(1) PISTE JOKA EI MAHDU, KATOAA HILJAA.** SVG ei valita jos `cx` on
plottialueen ulkopuolella - se piirtyy reunan taakse tai leikkautuu. Kaavio
nayttaa taydelliselta ja siita puuttuu juuri se havainto joka olisi ollut
kiinnostavin (UCL-datassa: Mbappe 61 % omistuksella on ainoa piste yli
50 %:n). Siksi `_skaalaa` NOSTAA jos arvo on domainin ulkopuolella. Kaavio
joka ei voi naytta kaikkea dataansa ei renderoidy lainkaan.

**(2) PYLVAS JOKA EI ALA NOLLASTA LIIOITTELEE.** Kolme ja neljä nayttavat
kaksinkertaiselta erolta jos akseli alkaa kahdesta. `stacked_bars` laskee
domainin aina nollasta eika ota sita parametrina - vaara vaihtoehto ei ole
tarjolla.

MOBIILI: kaaviolla on kiintea viewBox ja `min-width`, ja kaarija vierittaa
vaakasuunnassa - sama idiomi kuin sivujen taulukoilla. Vaihtoehto olisi
skaalata `width:100%`, jolloin 12 px teksti on 360 px:n puhelimella 7 px
(muisti: headless-chrome-ilman-emulaatiota-nayttaa-ylivuotoa).
"""
from __future__ import annotations

from html import escape

# Sivuston tokenit (scripts/build_fpl_longtail.py :root). Kaavio ei saa
# tuoda omaa paletttiaan - se on juuri se tapa jolla sivustosta tulee
# kokoelma eri nakoisia sivuja.
INK = "#0B0A09"
CREAM = "#F3F2F2"
MUTED = "#A8A29A"
FAINT = "#8A847A"
LINE = "rgba(243,242,242,0.24)"
AMBER = "#F5C542"
TEAL = "#2ED6C2"
CORAL = "#FF8A5C"
PAPER = "#1F1D1A"

MONO = ('IBM Plex Mono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace')

# Positiovarit. Nelja erottuvaa savya tummalla pohjalla; ei punavihreaa
# paria, joten yleisin varisokeuden muoto ei tuhoa erottelua.
POS_VARI = {"GK": AMBER, "DEF": TEAL, "MID": CREAM, "FWD": CORAL}


class KaavioVirhe(ValueError):
    """Kaaviota ei voi piirtaa rehellisesti annetusta datasta."""


def _skaalaa(arvo: float, lo: float, hi: float, pix_lo: float,
             pix_hi: float, akseli: str) -> float:
    """Arvo -> pikseli. NOSTAA jos arvo ei mahdu domainiin.

    🔴 Tama nosto on koko moduulin tarkein rivi. Ilman sita domainin
    ulkopuolinen piste piirtyisi plottialueen ulkopuolelle ja katoaisi
    leikkaukseen, eika mikaan huutaisi.
    """
    if hi <= lo:
        raise KaavioVirhe(f"{akseli}-domain on tyhja tai kaanteinen: {lo}..{hi}")
    if not (lo <= arvo <= hi):
        raise KaavioVirhe(
            f"{akseli}-arvo {arvo} on domainin {lo}..{hi} ulkopuolella - "
            "piste olisi kadonnut leikkaukseen. Laajenna domain tai suodata "
            "data ENNEN piirtoa, alaka anna kaavion pudottaa havaintoa.")
    osuus = (arvo - lo) / (hi - lo)
    return pix_lo + osuus * (pix_hi - pix_lo)


def _nice_ticks(lo: float, hi: float, tavoite: int = 5) -> list[float]:
    """Luettavat tickit valille. Palauttaa aina >= 2 arvoa."""
    if hi <= lo:
        return [lo, lo + 1]
    raaka = (hi - lo) / max(tavoite - 1, 1)
    mag = 10 ** (len(str(int(abs(raaka)))) - 1) if abs(raaka) >= 1 else 0.1
    for kerroin in (1, 2, 2.5, 5, 10, 20, 25, 50, 100):
        askel = mag * kerroin
        if askel >= raaka:
            break
    alku = (int(lo / askel)) * askel
    ulos, x = [], alku
    while x <= hi + askel * 0.001:
        if x >= lo - askel * 0.001:
            ulos.append(round(x, 6))
        x += askel
    return ulos if len(ulos) >= 2 else [lo, hi]


def _num(x: float) -> str:
    """Pikseliarvo ilman turhaa desimaalihantaa."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _teksti(x: float, y: float, s: str, *, vari: str = MUTED, koko: int = 12,
            ankkuri: str = "middle", paino: int = 400) -> str:
    return (f'<text x="{_num(x)}" y="{_num(y)}" fill="{vari}" '
            f'font-family="{MONO}" font-size="{koko}" font-weight="{paino}" '
            f'text-anchor="{ankkuri}">{escape(s)}</text>')


def _kaarija(svg: str, min_leveys: int, otsikko: str) -> str:
    """Vaakavieritys kapealla naytolla, sama idiomi kuin taulukoilla."""
    return (f'<figure class="chart" role="group" aria-label="{escape(otsikko)}">'
            f'<div class="chart-scroll" style="--chart-min:{min_leveys}px">'
            f"{svg}</div></figure>")


def scatter(*, sarjat: list[dict], x_label: str, y_label: str, otsikko: str,
            x_domain: tuple[float, float] | None = None,
            y_domain: tuple[float, float] | None = None,
            x_yksikko: str = "", y_yksikko: str = "",
            leveys: int = 720, korkeus: int = 360) -> str:
    """Hajontakuvio.

    sarjat: [{"nimi": str, "vari": str, "pisteet": [(x, y, "selite"), ...]}]

    Domain lasketaan datasta jos sita ei anneta - silloin piste ei voi
    pudota ulos. Jos domain annetaan, `_skaalaa` nostaa ulkopuolisesta.
    """
    kaikki = [(x, y) for s in sarjat for (x, y, _) in s["pisteet"]]
    if not kaikki:
        raise KaavioVirhe(
            f"'{otsikko}': ei yhtaan pistetta. Tyhja kaavio nayttaa "
            "nollalta, ja nolla on eri asia kuin 'ei tietoa'.")

    if x_domain is None:
        xs = [x for x, _ in kaikki]
        pad = (max(xs) - min(xs)) * 0.06 or 1
        x_domain = (min(xs) - pad, max(xs) + pad)
    if y_domain is None:
        ys = [y for _, y in kaikki]
        # y alkaa nollasta jos data on positiivista: hajontakuviossakin
        # katkaistu akseli liioittelee.
        y_domain = (0 if min(ys) >= 0 else min(ys) * 1.06, max(ys) * 1.08 or 1)

    L, R, T, B = 52, 16, 16, 44
    px0, px1 = L, leveys - R
    py0, py1 = korkeus - B, T

    osat = [f'<svg viewBox="0 0 {leveys} {korkeus}" width="{leveys}" '
            f'height="{korkeus}" role="img" '
            f'aria-label="{escape(otsikko)}" '
            f'style="max-width:100%;height:auto">']
    osat.append(f'<rect width="{leveys}" height="{korkeus}" fill="{PAPER}"/>')

    for t in _nice_ticks(*y_domain):
        if not (y_domain[0] <= t <= y_domain[1]):
            continue
        y = _skaalaa(t, y_domain[0], y_domain[1], py0, py1, "y")
        osat.append(f'<line x1="{px0}" y1="{_num(y)}" x2="{px1}" '
                    f'y2="{_num(y)}" stroke="{LINE}" stroke-width="1"/>')
        osat.append(_teksti(px0 - 8, y + 4, f"{t:g}{y_yksikko}",
                            ankkuri="end", koko=11))

    for t in _nice_ticks(*x_domain):
        if not (x_domain[0] <= t <= x_domain[1]):
            continue
        x = _skaalaa(t, x_domain[0], x_domain[1], px0, px1, "x")
        osat.append(_teksti(x, korkeus - B + 18, f"{t:g}{x_yksikko}", koko=11))

    for s in sarjat:
        vari = s["vari"]
        for (xv, yv, selite) in s["pisteet"]:
            x = _skaalaa(xv, x_domain[0], x_domain[1], px0, px1, "x")
            y = _skaalaa(yv, y_domain[0], y_domain[1], py0, py1, "y")
            osat.append(
                f'<circle cx="{_num(x)}" cy="{_num(y)}" r="4" fill="{vari}" '
                f'fill-opacity="0.78" stroke="{INK}" stroke-width="0.5">'
                f"<title>{escape(selite)}</title></circle>")

    osat.append(_teksti((px0 + px1) / 2, korkeus - 6, x_label, koko=12,
                        vari=FAINT))
    osat.append(f'<text x="12" y="{_num((py0 + py1) / 2)}" fill="{FAINT}" '
                f'font-family="{MONO}" font-size="12" text-anchor="middle" '
                f'transform="rotate(-90 12 {_num((py0 + py1) / 2)})">'
                f"{escape(y_label)}</text>")
    osat.append("</svg>")

    legenda = "".join(
        f'<span class="lg"><i style="background:{s["vari"]}"></i>'
        f'{escape(s["nimi"])}</span>' for s in sarjat)
    return _kaarija("".join(osat), leveys, otsikko) + \
        f'<p class="chart-legend">{legenda}</p>'


def stacked_bars(*, rivit: list[tuple[str, dict]], sarjat: list[tuple[str, str, str]],
                 otsikko: str, x_label: str, leveys: int = 720,
                 pylvas: int = 16, vali: int = 5) -> str:
    """Pinottu vaakapylvaikko.

    rivit:  [(nimi, {avain: luku})]
    sarjat: [(avain, vari, selite)] - piirtojarjestys vasemmalta

    🔴 Domain alkaa AINA nollasta eika sita voi antaa parametrina. Katkaistu
    pylvasakseli on kaavioiden yleisin valhe, eika sita tarvita missaan.
    """
    if not rivit:
        raise KaavioVirhe(f"'{otsikko}': ei yhtaan rivia")
    avaimet = [a for a, _, _ in sarjat]
    summat = [sum(float(arvot.get(a) or 0) for a in avaimet) for _, arvot in rivit]
    hi = max(summat)
    if hi <= 0:
        raise KaavioVirhe(
            f"'{otsikko}': kaikkien rivien summa on 0 - kaavio olisi tyhja "
            "ruudukko joka nayttaa rikkinaiselta, ei nollalta")

    L, R, T, B = 74, 16, 12, 34
    korkeus = T + B + len(rivit) * (pylvas + vali)
    px0, px1 = L, leveys - R

    osat = [f'<svg viewBox="0 0 {leveys} {korkeus}" width="{leveys}" '
            f'height="{korkeus}" role="img" aria-label="{escape(otsikko)}" '
            f'style="max-width:100%;height:auto">']
    osat.append(f'<rect width="{leveys}" height="{korkeus}" fill="{PAPER}"/>')

    for t in _nice_ticks(0, hi):
        if t > hi:
            continue
        x = _skaalaa(t, 0, hi, px0, px1, "x")
        osat.append(f'<line x1="{_num(x)}" y1="{T}" x2="{_num(x)}" '
                    f'y2="{korkeus - B + 4}" stroke="{LINE}" stroke-width="1"/>')
        osat.append(_teksti(x, korkeus - B + 18, f"{t:g}", koko=11))

    for i, (nimi, arvot) in enumerate(rivit):
        y = T + i * (pylvas + vali)
        osat.append(_teksti(L - 8, y + pylvas - 4, nimi, ankkuri="end",
                            koko=11, vari=CREAM))
        kohta = 0.0
        for avain, vari, selite in sarjat:
            v = float(arvot.get(avain) or 0)
            if v <= 0:
                continue
            x_a = _skaalaa(kohta, 0, hi, px0, px1, "x")
            x_b = _skaalaa(kohta + v, 0, hi, px0, px1, "x")
            osat.append(
                f'<rect x="{_num(x_a)}" y="{y}" width="{_num(x_b - x_a)}" '
                f'height="{pylvas}" fill="{vari}" fill-opacity="0.85">'
                f"<title>{escape(nimi)}: {v:g} {escape(selite)}</title></rect>")
            kohta += v

    osat.append(_teksti((px0 + px1) / 2, korkeus - 4, x_label, koko=12,
                        vari=FAINT))
    osat.append("</svg>")

    legenda = "".join(
        f'<span class="lg"><i style="background:{v}"></i>{escape(s)}</span>'
        for _, v, s in sarjat)
    return _kaarija("".join(osat), leveys, otsikko) + \
        f'<p class="chart-legend">{legenda}</p>'


def ranges(*, rivit: list[tuple[str, float, float, str]], otsikko: str,
           x_label: str, x_yksikko: str = "", leveys: int = 720) -> str:
    """Vaihteluvalit janoina. rivit: [(nimi, lo, hi, vari)]."""
    if not rivit:
        raise KaavioVirhe(f"'{otsikko}': ei yhtaan rivia")
    lo = min(a for _, a, _, _ in rivit)
    hi = max(b for _, _, b, _ in rivit)
    if hi <= lo:
        raise KaavioVirhe(f"'{otsikko}': kaikilla riveilla sama arvo {lo}")

    L, R, T, B = 56, 22, 14, 34
    rivi_h = 30
    korkeus = T + B + len(rivit) * rivi_h
    px0, px1 = L, leveys - R

    osat = [f'<svg viewBox="0 0 {leveys} {korkeus}" width="{leveys}" '
            f'height="{korkeus}" role="img" aria-label="{escape(otsikko)}" '
            f'style="max-width:100%;height:auto">']
    osat.append(f'<rect width="{leveys}" height="{korkeus}" fill="{PAPER}"/>')

    for t in _nice_ticks(lo, hi):
        if not (lo <= t <= hi):
            continue
        x = _skaalaa(t, lo, hi, px0, px1, "x")
        osat.append(f'<line x1="{_num(x)}" y1="{T}" x2="{_num(x)}" '
                    f'y2="{korkeus - B + 4}" stroke="{LINE}" stroke-width="1"/>')
        osat.append(_teksti(x, korkeus - B + 18, f"{t:g}{x_yksikko}", koko=11))

    for i, (nimi, a, b, vari) in enumerate(rivit):
        y = T + i * rivi_h + rivi_h / 2
        xa = _skaalaa(a, lo, hi, px0, px1, "x")
        xb = _skaalaa(b, lo, hi, px0, px1, "x")
        osat.append(_teksti(L - 8, y + 4, nimi, ankkuri="end", koko=12,
                            vari=CREAM, paino=600))
        osat.append(
            f'<line x1="{_num(xa)}" y1="{_num(y)}" x2="{_num(xb)}" '
            f'y2="{_num(y)}" stroke="{vari}" stroke-width="6" '
            f'stroke-linecap="round"><title>{escape(nimi)}: '
            f"{a:g}{x_yksikko} - {b:g}{x_yksikko}</title></line>")
        osat.append(_teksti(xb + 10, y + 4, f"{b:g}", ankkuri="start",
                            koko=11, vari=MUTED))

    osat.append(_teksti((px0 + px1) / 2, korkeus - 4, x_label, koko=12,
                        vari=FAINT))
    osat.append("</svg>")
    return _kaarija("".join(osat), leveys, otsikko)


# Kaavioiden CSS. Sivugeneraattori liittaa taman omaan <style>-lohkoonsa.
CHART_CSS = """
.chart{margin:18px 0 6px;}
.chart-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;}
.chart-scroll>svg{min-width:var(--chart-min,720px);display:block;}
.chart-legend{display:flex;flex-wrap:wrap;gap:14px;margin:8px 0 20px;
font-family:var(--mono);font-size:12px;color:var(--muted);}
.chart-legend .lg{display:inline-flex;align-items:center;gap:6px;}
.chart-legend i{width:10px;height:10px;display:inline-block;border-radius:50%;}
"""
