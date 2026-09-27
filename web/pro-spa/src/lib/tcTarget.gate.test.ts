/**
 * Portti: TC-TARGET-PLAYER (27.9.2026). Triple Captain -rivi nimeaa kapteenin,
 * kortti sanoo oletuksen (XI:n paras kapteeni, ei nykyinen), ja valitsin
 * nayttaa pelaajan oman parhaan kierroksen.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { TC_ASSUMPTION, tcPickLine, tcRowSuffix } from './tcTarget';

const chipEv = readFileSync(resolve(__dirname, 'components/ChipEv.svelte'), 'utf8');

describe('tcTarget', () => {
	it('rivin loppuosa nimeaa kapteenin ja on tyhja ilman nimea', () => {
		expect(tcRowSuffix({ tc_player: { id: 411, web_name: 'Haaland' } })).toBe(' · Haaland');
		expect(tcRowSuffix({ tc_player: null })).toBe('');
		expect(tcRowSuffix({})).toBe('');
	});

	it('valitsimen rivi: kierros ja luku samasta ehdokkaasta', () => {
		expect(tcPickLine({ web_name: 'Haaland', best_gw: 7, best_xp: 8.38 })).toBe(
			'Haaland: GW7, +8.4 xP est.'
		);
	});

	it('oletus sanotaan: paras kapteeni, ei nykyinen', () => {
		expect(TC_ASSUMPTION).toMatch(/best captain/);
		expect(TC_ASSUMPTION).toMatch(/not the captain you have picked/);
	});

	it('ChipEv kayttaa lukijaa (ei omaa tekstia) ja renderoi valitsimen vain TC-kortissa', () => {
		expect(chipEv).toMatch(/\{TC_ASSUMPTION\}/);
		expect(chipEv).toMatch(/tcPickLine\(tcCand\)/);
		expect(chipEv).toMatch(/tcRowSuffix\(w\)/);
		expect(chipEv).toMatch(/chip\.key === 'tc' && best\.player/);
		// Valitsin on TC-lohkon sisalla, ei jokaisessa chip-kortissa.
		const i = chipEv.indexOf("{#if chip.key === 'tc'}\n");
		expect(i).toBeGreaterThan(-1);
		expect(chipEv.indexOf('<select', i)).toBeGreaterThan(i);
	});
});
