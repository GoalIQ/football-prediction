/**
 * lib/seasonObjective.ts — kauden tavoitteen tila (yksi lukija, web + mobiili).
 *
 * 6.9.2026 (Villen havainto): "Season target" -lohko otti tavoitteen vastaan
 * mutta sanoi kaikilla kauden vaiheilla "Rank tracking against your target
 * starts once the season is under way" — myos GW3:n jalkeen, kun rank oli
 * jo tiedossa. Teksti oli kirjoitettu esikaudella ja lipun takana ei ollut
 * mitaan (saanto 6a: ehto ei vanhene, teksti vanhenee).
 *
 * Lahde: rate-teamin `last_finished.overall_rank` ja `rank_change`
 * (FPL:n oma entry-historia, viimeisin PAATTYNYT kierros). Kesken olevan
 * kierroksen sijoitusta ei vaiteta: luku nimetaan kierroksella josta se on.
 *
 * Mobiilin goaliq-app/lib/seasonObjective.ts on sama tiedosto.
 */

export interface ObjectiveStatus {
  /** 'pre_season' = ei rank-dataa; 'inside' = sijoitus tavoitteen sisalla;
   *  'outside' = tavoitteen ulkopuolella. */
  kind: 'pre_season' | 'inside' | 'outside';
  /** Kierros josta sijoitus on. null vain pre_season-tilassa. */
  gw: number | null;
  rank: number | null;
  /** Sijoja tavoitteen ulkopuolella (rank - target), 0 kun sisalla. */
  gap: number;
  /** Positiivinen = nousi edellisesta kierroksesta. null = ei vertailua. */
  change: number | null;
}

export function objectiveStatus(
  target: number | null | undefined,
  rank: number | null | undefined,
  rankChange: number | null | undefined,
  gw: number | null | undefined
): ObjectiveStatus | null {
  if (target == null || !Number.isFinite(target) || target <= 0) return null;
  if (rank == null || !Number.isFinite(rank) || rank <= 0 || gw == null) {
    return { kind: 'pre_season', gw: null, rank: null, gap: 0, change: null };
  }
  const change = rankChange != null && Number.isFinite(rankChange) ? rankChange : null;
  if (rank <= target) return { kind: 'inside', gw, rank, gap: 0, change };
  return { kind: 'outside', gw, rank, gap: rank - target, change };
}

/** Englanninkielinen rivi (web; mobiili kaantaa i18n:ssa samoista kentista).
 *  Kierros nimetaan aina: luku on viimeisimman PAATTYNEEN kierroksen, ei
 *  taman hetken. */
export function objectiveLine(s: ObjectiveStatus): string {
  if (s.kind === 'pre_season') {
    return 'Rank tracking against your target starts once the season is under way.';
  }
  const rank = (s.rank as number).toLocaleString('en-GB');
  const move =
    s.change == null || s.change === 0
      ? ''
      : s.change > 0
        ? `, up ${s.change.toLocaleString('en-GB')} on last gameweek`
        : `, down ${Math.abs(s.change).toLocaleString('en-GB')} on last gameweek`;
  if (s.kind === 'inside') return `GW${s.gw}: ${rank} overall, inside your target${move}`;
  return `GW${s.gw}: ${rank} overall, ${s.gap.toLocaleString('en-GB')} places outside your target${move}`;
}
