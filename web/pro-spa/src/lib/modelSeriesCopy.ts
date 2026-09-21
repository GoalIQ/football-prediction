/* Mallisarjan ja entry-sarjan julkinen teksti SPA:ssa, YHDESSA paikassa.
 *
 * 🔴 LUONNOS 21.9.2026, kierros 2 (julkaisutarkistajan korjaukset + Villen
 * GW4-paatos). Season race ja tuloskortti nayttavat MALLIN jaadytetyn rivin,
 * ja FPL-entry 116920 naytetaan erikseen omalla nimellaan. Jokainen
 * merkkijono tassa tiedostossa on julkista tekstia, ja se kulkee
 * julkaisutarkistajan + Villen GO:n kautta ENNEN mergea. Mobiilin vastineet:
 * goaliq-app lib/i18n/en.ts `fantasy.race.series.*` (sama sisalto).
 *
 * Payload kantaa koodit ja luvut (`unscored_gws[]`, `reseeded_gws[]`,
 * `cost_unverified_gws`, `model_route`), ja teksti elaa vain taalla. Luvut
 * tulevat AINA payloadista: jos payload ei kanna lukua, lause jaa ilman sita
 * eika mitaan lukua keksita.
 */

function gwList(gws: number[]): string {
	return 'GW' + gws.join(', GW');
}

function signed(n: number): string {
	return n > 0 ? `+${n}` : String(n);
}

export const MODEL_SERIES_COPY = {
	/** `unscored_gws[]`, koodi `no_valid_frozen_squad`. Luku ja keskiarvo vain
	 *  jos payload kantaa ne (`would_have_scored`, `fpl_average`). */
	unscoredNoValidFreeze: (gw: number, points: number | null, avg: number | null) =>
		`GW${gw}: not scored. That week's freeze rebuilt the squad from scratch by mistake instead of carrying on from the week before, so it isn't the model's line.` +
		(points != null && avg != null
			? ` Scored as frozen it would have had ${points}, against an average of ${avg}.`
			: ''),
	/** `reseeded_gws[]`: mallin ketju alkoi entryn rungosta. Wildcard-muoto
	 *  VAIN kun payload sanoo entryn pelanneen wildcardin lahdekierroksella. */
	reseeded: (gw: number, fromGw: number, entryChip: string | null) =>
		entryChip === 'wildcard'
			? `GW${gw}: the model's line restarted from our FPL entry's squad after we played a wildcard there in GW${fromGw}.`
			: `GW${gw}: the model's line restarted from our FPL entry's squad.`,
	/** Rivit joiden mallin hitti-kustannusta ei voitu todentaa. */
	costUnverified: (gws: number[]) =>
		`${gwList(gws)}: the model's transfer cost couldn't be checked against FPL's rules, so its points there are before hits.`,
	costUnverifiedBadge: 'before hits',
	/** Mallin vs keskiarvo. Saanto 6a (21.9): teksti sanoo "hits deducted",
	 *  joten lukija palauttaa sen VAIN kun payload itse sanoo
	 *  `hits_deducted === true`. Bruttoluku (vanha backend, puuttuva lippu tai
	 *  false) -> null, eika lausetta piirreta lainkaan. */
	modelVsAverage: (
		v: { diff: number; gameweeks: number; hits_deducted?: boolean } | null | undefined
	): string | null =>
		v && v.hits_deducted === true && v.gameweeks > 0
			? `Model vs the FPL average: ${signed(v.diff)} over ${v.gameweeks} gameweek${v.gameweeks === 1 ? '' : 's'}, hits deducted`
			: null,
	entryTitle: 'Our FPL entry (model + our own calls)',
	entryNote: (id: number) =>
		`Entry ${id} on the official FPL site. It starts from the model's squad, but the chip calls and the occasional lineup change are ours, so it's scored apart from the model. It's the team in the Beat the Model mini-league table.`,
	entryTotal: (points: number, diff: number, n: number) =>
		`${points} points over ${n} gameweek${n === 1 ? '' : 's'}, ${signed(diff)} vs the FPL average`,
	/** Tuloskortin mallisolun avain: reitti on jaadytetty rivi, ei entry. */
	cardModelKey: (gw: number) => `Model · frozen GW${gw}`,
	cardModelLinkTitle: "The model's scored gameweeks in the public repository",
	/** Jakokortin lahdelause kun mallisolu on kortilla. */
	cardSourceNote: 'model squad and score: github.com/GoalIQ/football-prediction'
} as const;
