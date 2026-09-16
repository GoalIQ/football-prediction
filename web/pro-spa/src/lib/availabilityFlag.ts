/**
 * YKSI LUKIJA saatavuusmerkille ja sen syylle (16.9).
 *
 * MITATTU VIKA: `PlayerSearch.svelte` palautti sanan `out` kahdesta eri
 * syysta — FPL:n saatavuuslipusta JA siita ettei pelaaja ole projektiossa.
 * Jalkimmainen ei tarkoita samaa: 16.9 tuotannon artefaktissa 178
 * `excluded`-rivista kaksi oli `below_min_xp`, ja niilla FPL-status on `a`
 * (Lewis, MCI, tyhja news) ja `d` (Gruev, 25 %). Hakurivi sanoi heista "out"
 * kun FPL sanoo "available".
 *
 * Toinen puoli samaa vikaa: `out` on KIERROKSETON. FPL:n
 * `chance_of_playing_next_round` koskee vain seuraavaa kierrosta, joten
 * viiden kierroksen listan vieressa paljas "out" vaittaa enemman kuin lahde.
 * Julkaisuportti hylkasi taman samana paivana korttisaatteelta ("out in FPL");
 * hakurivilla sama vaite eli yha, koska portti etsi literaalia eika
 * renderoitya muotoa.
 *
 * Nelja luokkaa, ja jokainen on tosi omassa tapauksessaan:
 *   left     status `u` — pysyvasti pois, ei kierrossidonnainen
 *   out      status `i`/`s`/`n` tai chance 0 — FPL:n oma lippu
 *   doubt    status `d` — FPL:n oma prosentti kun se on tiedossa
 *   no xP    ei projektiota mutta EI lippua — vaittaa vain meidan luvusta
 */
export interface AvailabilityRow {
	status?: string | null;
	chance_next?: number | null;
	in_projection?: boolean;
	excluded_reason?: string | null;
}

export type AvailabilityTone = 'out' | 'warn' | 'muted';

export interface AvailabilityFlag {
	text: string;
	tone: AvailabilityTone;
}

/** Merkki hakuriville, tai `null` kun rivilla ei ole sanottavaa. */
export function availabilityFlag(p: AvailabilityRow): AvailabilityFlag | null {
	const s = p.status ?? 'a';
	if (s === 'u') return { text: 'left club', tone: 'out' };
	if (s === 'i' || s === 's' || s === 'n') return { text: 'out', tone: 'out' };
	if (s === 'd') {
		return {
			text: typeof p.chance_next === 'number' ? `${p.chance_next}%` : 'doubt',
			tone: 'warn'
		};
	}
	if (p.chance_next === 0) return { text: 'out', tone: 'out' };
	// Ei lippua mutta ei projektiotakaan: vaite koskee MEIDAN lukuamme, ei
	// pelaajan tilaa. "out" tassa olisi suoraan epatosi (FPL sanoo `a`).
	if (p.in_projection === false) return { text: 'no xP', tone: 'muted' };
	return null;
}

/**
 * Sama syy taydella lauseella (pelaajakortti). Kynnysluku annetaan
 * artefaktista (`meta.min_xp_total`), ei kirjoiteta kasin — jos
 * build_fpl_xp.py:n raja muuttuu, copy seuraa.
 */
export function noXpReason(
	p: AvailabilityRow,
	opts: { horizon?: number | null; minXp?: number | null } = {}
): string | null {
	const s = p.status ?? 'a';
	if (p.excluded_reason === 'below_min_xp' || (p.in_projection === false && s === 'a')) {
		const raja = typeof opts.minXp === 'number' ? `${opts.minXp} xP` : 'the cutoff';
		return opts.horizon
			? `the model projects this player under ${raja} on the ${opts.horizon}-gameweek horizon`
			: `the model projects this player under ${raja} over the horizon`;
	}
	if (s === 'u') return 'FPL lists this player as no longer in the league';
	if (s === 'i') return 'FPL lists this player as injured';
	if (s === 's') return 'FPL lists this player as suspended';
	if (s === 'n') return 'FPL lists this player as not available';
	if (s === 'd' && typeof p.chance_next === 'number')
		return `FPL gives this player a ${p.chance_next}% chance of playing the next round`;
	if (p.in_projection === false) return 'this player is outside the projection';
	return null;
}
