/**
 * lib/seasonObjective.ts — kauden tavoitteen tila (yksi lukija, web + mobiili).
 *
 * 6.9.2026 (Villen havainto): "Season target" -lohko otti tavoitteen vastaan
 * mutta sanoi kaikilla kauden vaiheilla "Rank tracking against your target
 * starts once the season is under way" — myos GW3:n jalkeen, kun rank oli
 * jo tiedossa. Teksti oli kirjoitettu esikaudella ja lipun takana ei ollut
 * mitaan (saanto 6a: ehto ei vanhene, teksti vanhenee).
 *
 * Lahde: rate-teamin `season_rank.overall_rank` ja `rank_change`
 * (FPL:n oma entry-historia, viimeisin PAATTYNYT kierros). Kesken olevan
 * kierroksen sijoitusta ei vaiteta: luku nimetaan kierroksella josta se on.
 *
 * 🔴 JULKAISUTARKISTAJAN LOYDOKSET 7.9 (B2-B5, B7):
 *
 *  B2  "GW3: 242,100 overall" luettiin NYKYHETKEKSI, ja "up 12,000 on last
 *      gameweek" oli kaksitulkintainen (kumpi kierros on "last"?). Muoto on
 *      nyt "After GW3: … up 12,000 places from GW2" — molemmat kierrokset
 *      nimetty.
 *  B3  `rank <= target` luki tavoitteen rajan SISALLE. Rajalla ei olla
 *      sisalla: `rank === target` on oma tila `level`.
 *  B4  🔴 SAMA VIKALUOKKA KERROSTA ALEMPANA. Kun FPL-kutsu kaatui,
 *      `overall_rank` oli `null` ja lukija palautti `pre_season`, eli
 *      "season is under way" -teksti palasi kesken kauden — tasan se vika
 *      jonka korjaamiseksi tama tiedosto kirjoitettiin. Puuttuva luku
 *      TIEDETYLLA kierroksella on nyt oma tila `rank_unavailable`.
 *  B7  es/pt-kaannokset vaittivat vaaraa ja luvut muotoiltiin `en-GB`:lla
 *      myos es/pt-lokaaleissa ("242,100" luetaan espanjaksi 242,1:na).
 *      Muotoilu ottaa lokaalin vastaan.
 *
 * Mobiilin goaliq-app/lib/seasonObjective.ts on sama tiedosto.
 */

export type ObjectiveKind =
  /** ei paattynytta kierrosta -> kausi ei ole viela alkanut */
  | 'pre_season'
  /** kierros tiedossa mutta sijoitusta ei saatu (FPL-kutsu kaatui) */
  | 'rank_unavailable'
  /** sijoitus tavoitteen sisalla (rank < target) */
  | 'inside'
  /** sijoitus tasan tavoitteessa (rank === target) */
  | 'level'
  /** sijoitus tavoitteen ulkopuolella (rank > target) */
  | 'outside';

export interface ObjectiveStatus {
  kind: ObjectiveKind;
  /** Kierros josta sijoitus on. null vain pre_season-tilassa. */
  gw: number | null;
  rank: number | null;
  /** Sijoja tavoitteen ulkopuolella (rank - target), 0 kun sisalla tai tasan. */
  gap: number;
  /** Positiivinen = nousi edellisesta kierroksesta. null = ei vertailua. */
  change: number | null;
  /** Kierros johon `change` vertaa (gw - 1). null kun vertailua ei ole. */
  changeFromGw: number | null;
}

export function objectiveStatus(
  target: number | null | undefined,
  rank: number | null | undefined,
  rankChange: number | null | undefined,
  gw: number | null | undefined
): ObjectiveStatus | null {
  if (target == null || !Number.isFinite(target) || target <= 0) return null;

  const gwOk = gw != null && Number.isFinite(gw) && gw > 0;
  const rankOk = rank != null && Number.isFinite(rank) && rank > 0;

  // B4: kierros tiedossa, luku ei -> EI esikautta. Esikausi on se tila
  // jossa paattynytta kierrosta ei ole lainkaan.
  if (!gwOk) {
    return { kind: 'pre_season', gw: null, rank: null, gap: 0, change: null, changeFromGw: null };
  }
  if (!rankOk) {
    return {
      kind: 'rank_unavailable',
      gw: gw as number,
      rank: null,
      gap: 0,
      change: null,
      changeFromGw: null,
    };
  }

  const change = rankChange != null && Number.isFinite(rankChange) ? rankChange : null;
  const changeFromGw = change != null && (gw as number) > 1 ? (gw as number) - 1 : null;
  const base = {
    gw: gw as number,
    rank: rank as number,
    change: changeFromGw != null ? change : null,
    changeFromGw,
  };
  // B3: raja ei ole sisapuoli.
  if ((rank as number) < target) return { ...base, kind: 'inside', gap: 0 };
  if ((rank as number) === target) return { ...base, kind: 'level', gap: 0 };
  return { ...base, kind: 'outside', gap: (rank as number) - target };
}

/** Englanninkielinen rivi (web; mobiili kaantaa i18n:ssa samoista kentista).
 *
 *  Kierros nimetaan aina, ja muutos nimeaa MOLEMMAT kierrokset: luku on
 *  viimeisimman PAATTYNEEN kierroksen, ei taman hetken.
 *
 *  `locale` on parametri (B7): `toLocaleString('en-GB')` kirjoittaa
 *  "242,100", joka luetaan espanjaksi ja portugaliksi luvuksi 242,1.
 */
export function objectiveLine(s: ObjectiveStatus, locale: string = 'en-GB'): string {
  if (s.kind === 'pre_season') {
    return 'Rank tracking against your target starts once the season is under way.';
  }
  const num = (n: number) => n.toLocaleString(locale);
  if (s.kind === 'rank_unavailable') {
    return `Your overall rank after GW${s.gw} was not available from FPL just now.`;
  }
  const rank = num(s.rank as number);
  const move =
    s.change == null || s.change === 0 || s.changeFromGw == null
      ? ''
      : s.change > 0
        ? `, up ${num(s.change)} places from GW${s.changeFromGw}`
        : `, down ${num(Math.abs(s.change))} places from GW${s.changeFromGw}`;
  if (s.kind === 'inside') return `After GW${s.gw}: ${rank} overall, inside your target${move}`;
  if (s.kind === 'level') return `After GW${s.gw}: ${rank} overall, level with your target${move}`;
  return `After GW${s.gw}: ${rank} overall, ${num(s.gap)} places outside your target${move}`;
}
