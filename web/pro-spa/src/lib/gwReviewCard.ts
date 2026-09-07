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
  footNote: string;
  footNote2: string;
  fileName: string;
}

export const REVIEW_CARD_MIN_ROWS = 3;

const sign = (n: number) => (n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1));

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

  const parts: string[] = [];
  if (rv.actual != null && rv.projected != null) {
    const d = rv.diff != null ? ` (${sign(rv.diff)})` : '';
    parts.push(`${rv.actual} scored against ${rv.projected.toFixed(1)} projected${d}`);
  }
  const compared = data.meta.players_compared;
  if (compared != null && compared < 15) parts.push(`${compared} of 15 compared`);
  if (data.meta.provisional) parts.push('provisional, gameweek still open');
  parts.push('worst call first');

  return {
    title: `GW${gw} REVIEW`,
    subtitle: parts.join(', '),
    nameLabel: 'PLAYER',
    midLabel: 'XP',
    valueLabel: 'PTS',
    rows,
    footNote: `xP locked at the GW${gw} deadline, points from FPL, captain doubled`,
    footNote2: 'not betting advice',
    fileName: `goaliq_gw${gw}_review.png`,
  };
}
