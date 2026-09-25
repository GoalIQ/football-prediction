import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

/* RATE-TEAM-FREEHIT-PALAUTUS (25.9.2026). Backend palauttaa Free Hit -joukkueen
   FH:ta edeltavaksi (meta.freehit_reverted_from). Silloin tavallinen selite
   "This is your GW{picks_gw} squad" olisi epatosi: naytetty runko on
   edellisen kierroksen. Portti: FH-haara on olemassa ja tulee ENNEN tavallista
   selitetta samassa if-ketjussa, jolloin molemmat eivat voi renderoitya. */
const src = readFileSync(new URL('./components/RateTeam.svelte', import.meta.url), 'utf-8');

describe('Free Hit -selite', () => {
	it('FH-haara on ennen picks_outdated-selitetta samassa ketjussa', () => {
		const fh = src.indexOf("{#if typeof data.meta.freehit_reverted_from === 'number'}");
		const outdated = src.indexOf('{:else if data.meta.picks_outdated === true');
		expect(fh).toBeGreaterThan(-1);
		expect(outdated).toBeGreaterThan(fh);
		// tavallista selitetta (picks_gw-ehto) ei ole enaa omana {#if}-lohkonaan
		expect(src).not.toMatch(/\{#if data\.meta\.picks_outdated === true && typeof data\.meta\.picks_gw/);
	});

	it('FH-selite ei vaita palautunutta runkoa GW{picks_gw}:n joukkueeksi', () => {
		const fh = src.indexOf("{#if typeof data.meta.freehit_reverted_from === 'number'}");
		const block = src.slice(fh, src.indexOf('{:else if data.meta.picks_outdated', fh));
		expect(block).toContain('Free Hit squad has reverted');
		expect(block).not.toContain('This is your GW{data.meta.picks_gw} squad');
	});
});
