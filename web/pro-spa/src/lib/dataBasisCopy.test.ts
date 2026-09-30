/**
 * Portti MOBIILI-DATAPOHJA-LABEL-vikaluokalle: PlayerCard.svelte korjasi
 * no_history-sanamuodon 29.9 mutta XpTable.svelte piti oman kopionsa
 * ("No PL data yet" / "No Premier League data for this player yet"), joka
 * on epatosi pelaajille joilla ON PL-minuutteja vanhemmilta kausilta (esim.
 * Hullin Dowell 905 min 2021/22, carry_prev_season kattaa vain edellisen
 * kauden). Tama testi kaataa ajon jos joku palauttaa kummankaan tekstin
 * absoluuttiseksi "no data" -vaitteeksi ilman "this season or last"
 * -rajausta, tai jos "yet" hiipii takaisin no_history-tekstiin.
 */
import { describe, expect, it } from 'vitest';
import { DATA_BASIS_LABEL, DATA_BASIS_TAG, DATA_BASIS_TOOLTIP } from './dataBasisCopy';

describe('dataBasisCopy: no_history ei väitä nollaa PL-dataa absoluuttisena', () => {
	it('DATA_BASIS_LABEL.no_history rajaa väitteen kuluvaan + viime kauteen', () => {
		expect(DATA_BASIS_LABEL.no_history).toBe(
			'no PL minutes this season or last, position average only'
		);
		expect(DATA_BASIS_LABEL.no_history).toMatch(/this season or last/);
		// Negatiivinen kontrolli: vanha epatosi muoto ei saa esiintyä.
		expect(DATA_BASIS_LABEL.no_history).not.toMatch(/\byet\b/);
		expect(DATA_BASIS_LABEL.no_history.toLowerCase()).not.toContain('no pl data');
	});

	it('DATA_BASIS_TAG.no_history (XpTable-tagi) sama rajaus kuin kortilla', () => {
		expect(DATA_BASIS_TAG.no_history).toBe('No PL minutes this season or last');
		expect(DATA_BASIS_TAG.no_history).not.toMatch(/\byet\b/);
	});

	it('DATA_BASIS_TOOLTIP.no_history (XpTable-hover) sama rajaus', () => {
		expect(DATA_BASIS_TOOLTIP.no_history).toMatch(/this season or last/);
		expect(DATA_BASIS_TOOLTIP.no_history).not.toMatch(/\byet\b/);
	});

	it('limited_history-tekstit ennallaan (ei tässä bugissa, ei saa muuttua vahingossa)', () => {
		expect(DATA_BASIS_LABEL.limited_history).toBe(
			'thin PL sample, the position average carries most of the weight'
		);
		expect(DATA_BASIS_TAG.limited_history).toBe('Limited data');
	});

	it('pl_history: ei tagia eika tooltippia (täysi oma data ei näytä varoitusta)', () => {
		expect((DATA_BASIS_TAG as Record<string, string>).pl_history).toBeUndefined();
		expect((DATA_BASIS_TOOLTIP as Record<string, string>).pl_history).toBeUndefined();
	});
});
