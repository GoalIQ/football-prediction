/**
 * Pelaajarivin tunnistus klikkauksesta (22.9.2026, A3 2.3). Erillaan
 * `playerSheet.svelte.ts`:sta, koska tama on puhdas DOM-funktio jota portti
 * (`ia.gate.test.ts`) ajaa ilman Svelte-kaantajaa.
 */

/** Elementit joiden klikkaus on oma toimintonsa eika rivin avaus. */
const INTERACTIVE = 'a,button,input,select,textarea,summary,label,[role="button"]';

/** Pelaajan id klikatusta kohdasta, tai null kun klikkaus ei kuulu
 *  pelaajariville tai osui rivin omaan kontrolliin (jakonappi, laajennus). */
export function playerIdFromEvent(target: EventTarget | null): number | null {
	const el = target as Element | null;
	if (!el || typeof el.closest !== 'function') return null;
	if (el.closest(INTERACTIVE)) return null;
	const row = el.closest('[data-player-id]');
	if (!row) return null;
	const id = Number(row.getAttribute('data-player-id'));
	return Number.isInteger(id) && id > 0 ? id : null;
}
