/**
 * Pelaajakortti mista tahansa rivista (22.9.2026, UX-uudistus A3 2.3).
 *
 * 🔴 ENNEN: pelaajakortti oli oma tyokalunsa (/players/player-card), johon
 * paasi vain kirjoittamalla nimen hakuun. Listassa nakynyt pelaaja piti
 * kirjoittaa uudelleen toisella sivulla. A2 saanto 16: "pelaajan tiedot
 * bottom sheetiin listan paalle, ei uuteen nakymaan".
 *
 * SAANTO 6a KOHTA 1 (yksi lukija): rivit EIVAT avaa korttia itse. Rivi
 * kantaa vain `data-player-id`-attribuutin, ja yksi delegoitu kasittelija
 * (`playerRowClick`) paneelin tasolla paattaa avaamisesta. Uusi lista saa
 * kortin lisaamalla attribuutin; portti `ia.gate.test.ts` kaataa jos
 * Players-ryhman lista jattaa sen pois.
 */

export const playerSheet = $state({
	/** Avoinna olevan kortin pelaaja, null = kiinni. */
	id: null as number | null,
	/** Mista kortti avattiin (analytiikka). */
	source: ''
});

export function openPlayer(id: number, source: string): void {
	if (!Number.isInteger(id) || id <= 0) return;
	playerSheet.id = id;
	playerSheet.source = source;
}

export function closePlayer(): void {
	playerSheet.id = null;
}

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

/** Delegoitu kasittelija paneelille: `onclick={(e) => playerRowClick(e, 'players')}`. */
export function playerRowClick(e: Event, source: string): void {
	const id = playerIdFromEvent(e.target);
	if (id != null) openPlayer(id, source);
}
