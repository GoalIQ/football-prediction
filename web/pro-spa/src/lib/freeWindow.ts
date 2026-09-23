// SPA-IKKUNAN-PAIVA-KIRJOITETTU-AUKI (23.9.2026): ikkunan loppu kirjoitettiin
// auki 11 merkkijonoon kuudessa komponentissa ("12 September", "GW4
// deadline", "GW1 to GW3"). Seuraavan ikkunan avaaja olisi joutunut
// muistamaan jokaisen, ja unohdus lupaa vaaran paivan. Nyt lukijat johtavat
// tekstin taalta (auth.svelte.ts vie nimet eteenpain), ja portti
// freeWindowDate.gate.test.ts kaataa buildin jos komponentti kirjoittaa
// kuukausipaivan kasin. Tiedostossa ei ole runeja eika Supabasea, jotta
// portti voi tuoda sen.

/** Ikkunan loppu: GW-deadline, UTC. Muut ikkunan tekstit johdetaan tasta. */
export const FREE_PREMIUM_UNTIL = '2026-09-12T12:30:00Z';

/** Kierros jonka deadline on FREE_PREMIUM_UNTIL. */
export const FREE_PREMIUM_UNTIL_GW = 4;

/** "12 September" aikaleimasta, UTC:ssa: katsojan vyohyke ei saa siirtaa
 *  paivaa (UTC+13:ssa 12:30Z on jo 13. paiva, ks. creator/+page.svelte). */
export function windowDayLabel(iso: string): string {
	return new Intl.DateTimeFormat('en-GB', {
		day: 'numeric',
		month: 'long',
		timeZone: 'UTC'
	}).format(new Date(iso));
}

export const FREE_PREMIUM_UNTIL_DAY = windowDayLabel(FREE_PREMIUM_UNTIL);
/** Ikkunan kattamat kierrokset: deadline-kierrosta edeltavat. */
export const FREE_PREMIUM_GWS = `GW1 to GW${FREE_PREMIUM_UNTIL_GW - 1}`;
