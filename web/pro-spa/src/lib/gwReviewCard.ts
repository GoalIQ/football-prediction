/**
 * lib/gwReviewCard.ts — Gameweek review -jakokortin sisalto (yksi lukija,
 * web + mobiili; mobiilin goaliq-app/lib/gwReviewCard.ts on sama tiedosto).
 *
 * 6.9.2026 (Villen tilaus): "saisko tohon this week gameweek reviewii
 * jako-ominaisuuden. toi vois olla aina hyva gw review postaus."
 *
 * Kortti on olemassa oleva LISTAKORTTI (sama renderoija kuin xP-listalla):
 * avaava XI rivi rivilta, deadline-freezen xP keskella ja FPL:n pisteet
 * oikealla. Uutta piirtajaa ei tarvita, ja kortti perii listakortin vahdit
 * (vahintaan 3 rivia, alatunniste lahteineen).
 *
 * REHELLISYYS, sama kuin paneelissa (GwReview.svelte / GwReview.tsx):
 *  - rivit jarjestetaan HUONOIMMASTA kutsusta parhaaseen: mallin huti on
 *    ylimpana, ei piilossa listan hannassa.
 *  - `provisional` ja kattavuus ("12 of 15 compared") menevat alaotsikkoon,
 *    eivat tooltippiin: kuva irtoaa sovelluksesta.
 *  - luvut tulevat endpointilta sellaisinaan. Kapteenin rivi on jo
 *    tuplattu backendissa (projected ja actual kertaa multiplier), joten
 *    kortti merkitsee sen C-badgella eika laske mitaan.
 */

export interface ReviewCardPlayer {
  web_name: string;
  team_short: string;
  pos: string;
  projected: number;
  actual: number;
  diff: number;
  multiplier: number;
  in_xi: boolean;
  is_captain: boolean;
}

export interface ReviewCardInput {
  meta: {
    reviewed_gw: number | null;
    provisional?: boolean;
    players_compared?: number;
  };
  review: {
    projected: number | null;
    actual: number | null;
    diff: number | null;
    players: ReviewCardPlayer[];
  } | null;
}

export interface ReviewCardRow {
  rank: number;
  name: string;
  tag: string;
  team: string;
  badges?: string[];
  mid: string;
  value: string;
}

export interface ReviewCardSpec {
  title: string;
  subtitle: string;
  nameLabel: string;
  midLabel: string;
  valueLabel: string;
  rows: ReviewCardRow[];
  heroFirstRow: boolean;
  footNote: string;
  footNote2: string;
  fileName: string;
}

export const REVIEW_CARD_MIN_ROWS = 3;

const sign = (n: number) => (n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1));

/**
 * 🔴 JULKAISUTARKISTAJAN LOYDOKSET 7.9 (A2-A7) — miksi tama funktio
 * nayttaa talta:
 *
 *  A2  Alatunniste sanoi vakiona "captain doubled". Entry pelasi GW3:n
 *      `3xc`-chipilla ja Haaland oli `multiplier=3`. Kapteenin kerroin
 *      johdetaan nyt kapteenin RIVILTA, ja jos kapteeni ei ole naytetyissa
 *      riveissa (ei pelannut), lausetta ei ole.
 *  A3  "xP locked at the deadline" ei pitanyt paikkaansa: gw3-freeze
 *      `frozen_at 12:16:41Z`, deadline `17:30:00Z` = 5 h 14 min ennen.
 *      Muoto on nyt "frozen before the GW{n} deadline".
 *  A4  "12 of 15 compared" laski `players_compared`ia (kaikki vertailtavat
 *      pickit) samalla kun kortin rivit ovat avaava XI. Kattavuus
 *      lasketaan nyt NAYTETYISTA riveista.
 *  A5  Kortin oma laskutoimitus ei mennyt tasan ("+0.9" kun naytetyt luvut
 *      antavat 0.8), koska erotus tuli pyoristamattomasta luvusta.
 *      Erotus lasketaan nyt NAYTETYISTA luvuista.
 *  A7  "72 scored" ei ole FPL:n kierrospistemaara: siina ei ole autosubeja
 *      eika siirtokuluja. Luku on avaavan XI:n summa, ja niin se myos
 *      sanotaan.
 *
 * Yhteinen nimittaja: kortti irtoaa sovelluksesta, joten sen on vastattava
 * omista luvuistaan ilman viereista nakymaa.
 */
export function gwReviewCardSpec(data: ReviewCardInput): ReviewCardSpec | null {
  const rv = data.review;
  const gw = data.meta.reviewed_gw;
  if (!rv || gw == null) return null;
  // Vain pelanneet (multiplier > 0). Penkin rivi olisi 0.0 -> 0, mika
  // lukisi "malli ennusti nollan ja osui".
  const xi = rv.players.filter((p) => p.in_xi && p.multiplier > 0);
  if (xi.length < REVIEW_CARD_MIN_ROWS) return null;
  const ordered = [...xi].sort(
    (a, b) => a.diff - b.diff || a.web_name.localeCompare(b.web_name)
  );
  const rows: ReviewCardRow[] = ordered.map((p, i) => ({
    rank: i + 1,
    name: p.web_name,
    tag: p.pos,
    team: p.team_short,
    badges: p.is_captain ? [p.multiplier >= 3 ? 'TC' : 'C'] : undefined,
    mid: p.projected.toFixed(1),
    value: String(p.actual),
  }));

  // A5 + A7: summat NAYTETYISTA riveista, ja erotus naytetyista luvuista.
  // Nain kortin oma laskutoimitus menee tasan silla tarkkuudella jolla se
  // on kortilla, eika luku voi olla eri joukosta kuin rivit.
  const actualShown = ordered.reduce((n, p) => n + p.actual, 0);
  const projShownText = ordered
    .reduce((n, p) => n + p.projected, 0)
    .toFixed(1);
  const diffShown = actualShown - Number(projShownText);

  const parts: string[] = [];
  parts.push(
    `starting XI ${actualShown} pts against ${projShownText} xP ` +
      `(${sign(diffShown)})`
  );
  // A4: kattavuus koskee sita joukkoa jonka rivit nayttavat.
  const starters = rv.players.filter((p) => p.in_xi).length;
  if (starters > rows.length) {
    parts.push(`${rows.length} of ${starters} starters shown`);
  }
  if (data.meta.provisional) parts.push('provisional, gameweek still open');
  parts.push('worst call first');

  // A2: kapteenin kerroin luetaan kapteenin omalta rivilta.
  const captain = ordered.find((p) => p.is_captain);
  const captainNote =
    captain == null
      ? ''
      : captain.multiplier >= 3
        ? ', captain tripled'
        : captain.multiplier >= 2
          ? ', captain doubled'
          : '';

  return {
    title: `GW${gw} REVIEW`,
    subtitle: parts.join(', '),
    nameLabel: 'PLAYER',
    midLabel: 'XP',
    valueLabel: 'PTS',
    rows,
    // A6: rivi 1 on mallin PAHIN kutsu, joten karkikorostus on pois.
    heroFirstRow: false,
    // A3: freeze on ennen deadlinea, ei deadlinella.
    footNote: `xP frozen before the GW${gw} deadline, points from FPL${captainNote}`,
    footNote2: 'not betting advice',
    fileName: `goaliq_gw${gw}_review.png`,
  };
}
