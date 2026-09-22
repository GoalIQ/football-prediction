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
import { playerIdFromEvent } from './playerRow';

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

/** Delegoitu kasittelija paneelille: `onclick={(e) => playerRowClick(e, 'players')}`. */
export function playerRowClick(e: Event, source: string): void {
	const id = playerIdFromEvent(e.target);
	if (id != null) openPlayer(id, source);
}

/**
 * Svelte-action paneelille: `<main use:playerRows={group}>`. Kuuntelija on
 * addEventListener eika onclick-attribuutti, koska paneeli ei itse ole
 * interaktiivinen elementti (a11y): interaktiivisia ovat rivit, ja
 * nappaimistolla kortin saa auki Players-sivun haulla.
 */
export function playerRows(node: HTMLElement, source: string) {
	let src = source;
	const h = (e: Event) => playerRowClick(e, src);
	node.addEventListener('click', h);
	return {
		update(next: string) {
			src = next;
		},
		destroy() {
			node.removeEventListener('click', h);
		}
	};
}
