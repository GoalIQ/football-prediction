/**
 * Siirtoparin pelaajan tunniste: nimi + pelipaikka + seura (1.10.2026).
 *
 * Villen havainto: This weekin siirtokortti sanoi "Out Tzolis -> In
 * Tavernier" ja se luettiin maalivahdin vaihdoksi kenttapelaajaan. Tzolis on
 * Arsenalin keskikenttapelaaja (MID), Tzolakis Hullin maalivahti (GKP); pelkka
 * sukunimi ei erota niita. Jos omistaja itse lukee ehdotuksen vaarin,
 * kayttaja lukee myos, ja maalivahti -> keskikentta nayttaa bugilta.
 *
 * YKSI LUKIJA (saanto 6a): jokainen pinta joka nayttaa siirtoparin lukee
 * taman moduulin. Portti `transferLabel.gate.test.ts` kaataa buildin jos
 * komponentti nayttaa `out.web_name`/`in.web_name`-parin importtaamatta
 * tata, ellei se ole poikkeuslistalla perusteluineen.
 *
 * FPL-siirto on aina sama pelipaikka sisaan ja ulos, joten pari kantaa
 * yhden `pos`in. Backend antaa sen joko parin tasolla (rate-team, planner,
 * hold-verdiktin best_checked_move) tai pelaajan tasolla (plan-chains).
 */

export interface TransferSide {
	web_name: string;
	team_short?: string | null;
	pos?: string | null;
}

/** "MID · ARS". Puuttuva osa jaa pois; molempien puuttuessa ''. */
export function transferTag(pos: string | null | undefined, team: string | null | undefined): string {
	return [pos, team].filter((x): x is string => typeof x === 'string' && x !== '').join(' · ');
}

/** "Tzolis (MID, ARS)". Ilman pelipaikkaa ja seuraa pelkka nimi. */
export function transferPlayerText(p: TransferSide, pos?: string | null): string {
	const bits = [pos ?? p.pos, p.team_short].filter(
		(x): x is string => typeof x === 'string' && x !== ''
	);
	return bits.length > 0 ? `${p.web_name} (${bits.join(', ')})` : p.web_name;
}

/** "Tzolis (MID, ARS) to Tavernier (MID, BOU)". `sep` esim. ' → '. */
export function transferPairText(
	out: TransferSide,
	inn: TransferSide,
	pos?: string | null,
	sep = ' to '
): string {
	return `${transferPlayerText(out, pos)}${sep}${transferPlayerText(inn, pos)}`;
}
