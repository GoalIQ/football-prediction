/**
 * MOBIILI-IA-JATKOT, tulostilan OUT-lippu (1.10.2026). Peili mobiilin
 * `lib/doubtFlag.ts`:sta.
 *
 * Saatavuuslippu on FPL:n `chance_of_playing_next_round`: se koskee AINA
 * deadline-kierrosta (`meta.deadline_gameweek`), ei sita kierrosta jota kentta
 * sattuu nayttamaan. Ilmaispinnalla kentta nayttaa ratkenneen kierroksen
 * tuloksen ("GW5 result") koko suunnitteluikkunan ajan, joten paljas "OUT"
 * GW5:n pisteiden vieressa luettiin GW5:n poissaoloksi, vaikka luku koskee
 * GW6:ta. Sama Premiumissa kun valittuna on muu kuin deadline-kierros.
 *
 * Saanto: lippu nimeaa kierroksensa aina kun nakyva kierros on eri. Piilotus
 * ei kay, koska se veisi OUT-tiedon juuri siirtoja tehdessa.
 */

/** Kierros jonka lippu nimeaa, tai null kun kentta nayttaa samaa kierrosta
 *  jota FPL:n luku koskee (tai jompaakumpaa ei tiedeta: vanha payload). */
export function doubtFlagGw(shownGw: number | null, chanceGw: number | null): number | null {
	if (shownGw == null || chanceGw == null || shownGw === chanceGw) return null;
	return chanceGw;
}

/** Lipun teksti, tai null kun lippua ei nayteta (ei lukua / 100 %). */
export function doubtFlagText(
	chance: number | null | undefined,
	shownGw: number | null,
	chanceGw: number | null
): string | null {
	if (typeof chance !== 'number' || chance >= 100) return null;
	const core = chance === 0 ? 'OUT' : `${chance}%`;
	const gw = doubtFlagGw(shownGw, chanceGw);
	return gw == null ? core : `GW${gw} ${core}`;
}
