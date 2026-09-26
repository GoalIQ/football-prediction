/** Reaktiivinen kello aikaan sidotuille sanoille ($lib/priceEta).
 *
 * 🔴 MIKSI (26.9.2026, julkaisutarkistaja B2): hintarivin paivasana laskettiin
 * `Date.now()`:lla kerran kun data saapui ($derived ei riipu kellosta). Illalla
 * auki jaanyt valilehti nayttaa aamulla yha "price rise tonight" jo
 * tapahtuneesta paivityksesta. Lukija osaa pudottaa menneen ajan, mutta vain
 * jos se saa oikean hetken.
 *
 * `clock.now` paivittyy kerran minuutissa ja aina kun valilehti tulee
 * nakyviin (taustavalilehden ajastimia kuristetaan). Lukeminen $derivedissa
 * tai templatessa tekee siita riippuvuuden. Palvelimella (prerender) ajastinta
 * ei kaynnisteta.
 */
export const NOW_TICK_MS = 60_000;

let current = $state(Date.now());
let started = false;

function start(): void {
	if (started || typeof window === 'undefined') return;
	started = true;
	setInterval(() => (current = Date.now()), NOW_TICK_MS);
	document.addEventListener('visibilitychange', () => {
		if (!document.hidden) current = Date.now();
	});
}

export const clock = {
	get now(): number {
		start();
		return current;
	}
};
