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
    /** Kaikki pickit (yleensa 15). Kattavuuden NIMITTAJA, ei kovakoodattu. */
    total_picks?: number;
    /** FPL:n `active_chip`. Bench boostilla rivit EIVAT ole avaava XI. */
    chip?: string | null;
    /** Freeze-hetki ja kierroksen deadline ISO-muodossa. Vaite freezen
     *  ajoituksesta tehdaan naista, ei rakenteesta. */
    frozen_at?: string | null;
    deadline?: string | null;
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
 * 🔴 PORTIN KAKSI KIERROSTA (6.9 loydokset A2-A7, 7.9 loydokset U1-U5).
 * Yhteinen nimittaja molemmissa: kortti irtoaa sovelluksesta, joten jokainen
 * sen vaite on JOHDETTAVA payloadista - rakenteellinen oletus on vaite jota
 * kortti ei voi mitata.
 *
 *  U1  "72 pts ... points from FPL" oli tarkistamaton: lukijan oma FPL-sovellus
 *      sanoi GW3:sta 58. Mitattu 7.9: kaikki 10 ottelua olivat
 *      `finished_provisional` mutta EIVAT `finished`, ja live-syotteessa oli 15
 *      kerroinpainotettua bonuspistetta joita `entry_history` ei ollut viela
 *      kirjoittanut (72 - 15 = 57, FPL 58). Ero ei ole virhe vaan ikkuna, ja
 *      kortti sanoo sen nyt itse: kesken olevalla kierroksella luku on
 *      live-syotteesta ja bonus on vahvistamatta.
 *  U2  Paneeli ja kortti antoivat eri erotuksen samasta kierroksesta (+0.9 vs
 *      +0.8) samassa otsikkorivissa. Molemmat lukevat nyt taman funktion.
 *  U3  Kattavuuslause oli KUOLLUT HAARA: backend maarittelee
 *      `in_xi := multiplier > 0`, joten rivit ja "aloittajat" olivat aina sama
 *      joukko. Oikea aukko (`players_compared` 14, pickkeja 15) oli pudonnut
 *      kortilta kokonaan. Nyt kattavuus lasketaan pickeista, ja nimittaja
 *      tulee payloadista.
 *  U4  Bench boostilla jokaisella 15:sta on multiplier > 0 -> "starting XI"
 *      olisi 15 rivin otsikkona vaara. Otsikko johdetaan riveista ja chipista.
 *  U5  Kapteenin kerroin luettiin `is_captain`-lipusta. Jos kapteeni ei
 *      pelannut, FPL siirtaa kertoimen varakapteenille MUTTA lippu jaa
 *      pelaamattomalle -> tuplattu rivi ilman merkintaa ja ilman lausetta.
 *      Kerroin luetaan nyt riveilta (suurin multiplier), eli silta jolla se
 *      oikeasti on.
 */

/** Alaotsikon ja alatunnisteen palaset. Vietu ulos jotta PANEELI voi kayttaa
 *  samaa erotusta kuin kortti (U2): kaksi pintaa samasta kierroksesta ei saa
 *  antaa eri lukua. */
export function reviewTotals(rows: { projected: number; actual: number }[]) {
  const actual = rows.reduce((n, p) => n + p.actual, 0);
  const projectedText = rows.reduce((n, p) => n + p.projected, 0).toFixed(1);
  // Erotus NAYTETYISTA luvuista: pyoristamaton 0.85 nayttaisi "+0.9" vaikka
  // kortilla lukee 71.2 ja 72.
  return { actual, projectedText, diff: actual - Number(projectedText) };
}

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
  const maxMult = ordered.reduce((m, p) => Math.max(m, p.multiplier), 1);
  const rows: ReviewCardRow[] = ordered.map((p, i) => ({
    rank: i + 1,
    name: p.web_name,
    tag: p.pos,
    team: p.team_short,
    // U5: merkinta sille jolla kerroin OIKEASTI on, ei lipulle.
    badges:
      p.multiplier >= 3 ? ['TC'] : p.multiplier >= 2 ? ['C'] : undefined,
    mid: p.projected.toFixed(1),
    value: String(p.actual),
  }));

  const { actual, projectedText, diff } = reviewTotals(ordered);

  // U4: otsikko johdetaan riveista ja chipista, ei oleteta yhdeksitoista.
  const chip = (data.meta.chip || '').toLowerCase();
  const label =
    chip === 'bboost'
      ? `bench boost (all ${rows.length})`
      : rows.length === 11
        ? 'starting XI'
        : `${rows.length} players`;

  const parts: string[] = [];
  parts.push(`${label}: ${actual} pts vs ${projectedText} xP (${sign(diff)})`);

  // U3: kattavuus koskee PICKKEJA ja nimittaja tulee payloadista.
  const compared = data.meta.players_compared;
  const picks = data.meta.total_picks;
  if (compared != null && picks != null && compared < picks) {
    parts.push(`${compared} of ${picks} picks had both numbers`);
  }
  // U1: kesken oleva kierros -> luku on live-syotteesta ja bonus vahvistamatta.
  // Tama on se lause joka selittaa miksi FPL-sovellus voi nayttaa pienempaa.
  if (data.meta.provisional) parts.push('bonus not final, FPL may show less');
  parts.push('worst call first');

  // U5: kerroinlause suurimmasta kertoimesta riveilla.
  const multNote =
    maxMult >= 3 ? ', captain tripled' : maxMult >= 2 ? ', captain doubled' : '';

  // A3 + U-seuranta: freeze-vaite vain kun payload todistaa sen.
  const frozenNote = freezeNote(gw, data.meta.frozen_at, data.meta.deadline);

  return {
    title: `GW${gw} REVIEW`,
    subtitle: parts.join(', '),
    nameLabel: 'PLAYER',
    midLabel: 'XP',
    valueLabel: 'PTS',
    rows,
    // A6: rivi 1 on mallin PAHIN kutsu, joten karkikorostus on pois.
    heroFirstRow: false,
    footNote: `${frozenNote}, points from the FPL live feed${multNote}`,
    footNote2: 'not betting advice',
    fileName: `goaliq_gw${gw}_review.png`,
  };
}

/** Freeze-vaite payloadista. Ilman kumpaakin aikaleimaa kortti sanoo vain
 *  MISTA luku on, ei milloin se lukittiin. */
export function freezeNote(
  gw: number,
  frozenAt: string | null | undefined,
  deadline: string | null | undefined
): string {
  const f = frozenAt ? Date.parse(frozenAt) : NaN;
  const d = deadline ? Date.parse(deadline) : NaN;
  if (Number.isFinite(f) && Number.isFinite(d) && f < d) {
    return `xP frozen before the GW${gw} deadline`;
  }
  return `xP frozen for GW${gw}`;
}
