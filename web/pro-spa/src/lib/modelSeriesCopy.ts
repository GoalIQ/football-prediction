/* Mallisarjan ja entry-sarjan julkinen teksti SPA:ssa, YHDESSA paikassa.
 *
 * 🔴 LUONNOS 21.9.2026. Villen paatos "molemmat sarjat, malli ensin":
 * Season race ja tuloskortti nayttavat MALLIN jaadytetyn rivin, ja FPL-entry
 * 116920 (malli + ihmisen chip-paatokset) naytetaan erikseen omalla nimellaan.
 * Jokainen merkkijono tassa tiedostossa on julkista tekstia, ja se kulkee
 * julkaisutarkistajan + Villen GO:n kautta ENNEN mergea. Mobiilin vastineet:
 * goaliq-app lib/i18n/en.ts `fantasy.race.series.*` (sama sisalto).
 *
 * Payload kantaa koodit (`unscored_gws[].code`, `cost_unverified_gws`,
 * `model_route.kind`), ja teksti elaa vain taalla, jotta sama asia ei voi
 * sanoa eri asiaa kahdessa kohdassa.
 */

function gwList(gws: number[]): string {
	return 'GW' + gws.join(', GW');
}

function signed(n: number): string {
	return n > 0 ? `+${n}` : String(n);
}

export const MODEL_SERIES_COPY = {
	/** `unscored_gws[].code === 'no_valid_frozen_squad'` */
	unscoredNoValidFreeze: (gws: number[]) =>
		`${gwList(gws)}: no valid frozen squad, not scored.`,
	/** Rivit joiden mallin hitti-kustannusta ei voitu todentaa. */
	costUnverified: (gws: number[]) =>
		`${gwList(gws)}: the model's transfer cost couldn't be checked against FPL's rules, so its points there are before hits.`,
	costUnverifiedBadge: 'before hits',
	modelVsAverage: (diff: number, n: number) =>
		`Model vs the FPL average: ${signed(diff)} over ${n} gameweek${n === 1 ? '' : 's'}`,
	entryTitle: 'Our FPL entry (model + human chip calls)',
	entryNote: (id: number) =>
		`Entry ${id} on the official FPL site: the model's squad plus our own chip calls. It is the team in the Beat the Model mini-league table, so it is scored here separately from the model.`,
	entryTotal: (points: number, diff: number, n: number) =>
		`${points} points over ${n} gameweek${n === 1 ? '' : 's'}, ${signed(diff)} vs the FPL average`,
	/** Tuloskortin mallisolun avain: reitti on jaadytetty rivi, ei entry. */
	cardModelKey: (gw: number) => `Model · frozen GW${gw}`,
	cardModelLinkTitle: 'The frozen squad file in the public repository'
} as const;
