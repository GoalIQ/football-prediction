/**
 * Pelaajan maali- ja syottovauhdin datapohja (`data_basis`) teksteiksi.
 * Yksi lukija PlayerCardille ja XpTablelle (mobiili: goaliq-app
 * lib/dataBasis.ts, samat englanninkieliset tekstit).
 *
 * `data_basis` on maali- ja syottovauhdin otos (fpl_xp.data_basis,
 * M_PRIOR_ATTACK), EI aloitus-tn:n pohja (julkaisutarkistaja 29.9 k1 B1).
 * Minuutit = tama kausi + viime kauden arkisto (builderin XP-SEASON-CARRY),
 * siksi "this season or last".
 *
 * 30.9.2026 (MOBIILI-DATAPOHJA-LABEL, tarkistaja 29.9 k2): XpTablen tagi
 * sanoi "No PL data yet" ja "little Premier League history for this player
 * yet", jotka ovat epatosia pelaajalle jolla on PL-minuutteja vanhemmilta
 * kausilta (Hullin Dowell 905 min 2021/22), ja valitun pelaajan
 * minuuttirivi liitti datapohjan aloitus-tn:n peraan.
 *
 * Tuntematon arvo -> null, ei raakaa arvoa ruudulle.
 */

export const DATA_BASIS_LABEL: Record<string, string> = {
	pl_history: "based on the player's own PL minutes",
	limited_history: 'thin PL sample, the position average carries most of the weight',
	no_history: 'no PL minutes this season or last, position average only'
};

const TAG: Record<string, { label: string; title: string }> = {
	limited_history: {
		label: 'Thin PL sample',
		title:
			"Thin PL sample this season and last, so this player's goal and assist rates lean mostly on the position average."
	},
	no_history: {
		label: 'No recent PL minutes',
		title:
			"No Premier League minutes this season or last, so this player's goal and assist rates are the position average."
	}
};

const own = (o: object, k: unknown): k is string =>
	typeof k === 'string' && Object.prototype.hasOwnProperty.call(o, k);

/** "Goal and assist rates: ..." tunnetulle datapohjalle, muuten null. */
export function basisRatesLine(b: unknown): string | null {
	return own(DATA_BASIS_LABEL, b) ? `Goal and assist rates: ${DATA_BASIS_LABEL[b]}.` : null;
}

/** Listan tagi vain priorinvaraisille riveille (pl_history = ei tagia). */
export function basisTag(b: unknown): { label: string; title: string } | null {
	return own(TAG, b) ? TAG[b] : null;
}
