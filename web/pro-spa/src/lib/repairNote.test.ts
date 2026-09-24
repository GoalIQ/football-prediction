import { describe, expect, it } from 'vitest';
import { repairNote, repairRow } from './availabilityFlag';

describe('repairRow: backendin repair_reason -> AvailabilityRow', () => {
	it.each([
		['status:u', { status: 'u' }],
		['status:i', { status: 'i' }],
		['status:s', { status: 's' }],
		['status:n', { status: 'n' }],
		['status:d', { status: 'd' }],
		['chance_next:0', { chance_next: 0 }],
		['no_projection:unavailable', { in_projection: false, excluded_reason: 'unavailable' }]
	])('%s', (reason, row) => {
		expect(repairRow(reason)).toEqual(row);
	});

	it.each([null, undefined, '', 'status', 'status:a', 'status:x', 'chance_next:50', 'foo:bar', 'no_projection:'])(
		'tuntematon %s -> null (ei keksittya syyta)',
		(reason) => {
			expect(repairRow(reason as string | null | undefined)).toBeNull();
		}
	);
});

describe('repairNote: plannerin korjausrivi', () => {
	it('Dovin (status u, +0.00): mitattu 18.9 tapaus saa syyn', () => {
		const n = repairNote('Dovin', 'status:u', 0);
		expect(n?.text).toBe('Dovin: left club');
		expect(n?.title).toContain('FPL lists this player as no longer in the league');
		expect(n?.title).toContain('+0.00 xP');
	});

	it('positiivinen hyoty ei vaita +0.00:aa', () => {
		const n = repairNote('Saka', 'status:i', 1.2);
		expect(n?.text).toBe('Saka: out');
		expect(n?.title).toContain('injured');
		expect(n?.title).not.toContain('+0.00');
	});

	it('chance_next:0 ilman statusta', () => {
		const n = repairNote('X', 'chance_next:0', 0);
		expect(n?.text).toBe('X: out');
		expect(n?.title).toContain('0% chance of playing the next round');
	});

	it('no_projection ei saa kynnyslausetta (se koskee below_min_xp:ta)', () => {
		const n = repairNote('Y', 'no_projection:unavailable', 0);
		expect(n?.text).toBe('Y: no xP');
		expect(n?.title).toContain('outside our projection');
		expect(n?.title).not.toContain('under');
	});

	it('status d ilman prosenttia: merkki doubt', () => {
		expect(repairNote('Z', 'status:d', 0)?.text).toBe('Z: doubt');
	});

	it('tuntematon syy -> ei merkkia', () => {
		expect(repairNote('W', 'mystery:1', 0)).toBeNull();
		expect(repairNote('W', null, 0)).toBeNull();
	});
});

// Kutsupaikkaportti (muisti testi-kutsuu-funktiota-ei-kutsupaikkaa): yllä
// olevat testit pysyvat vihreina vaikka planneri lakkaisi kutsumasta
// repairNotea. Tama kaatuu jos rivi palaa pelkkaan "+0.00 xP":hen.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { blankComments } from './sourceScan';

describe('kutsupaikka: TransferPlanner nayttaa korjaussyyn', () => {
	it('siirtorivi kutsuu repairNotea backendin repair_reasonilla', () => {
		const src = blankComments(
			readFileSync(fileURLToPath(new URL('./components/TransferPlanner.svelte', import.meta.url)), 'utf-8')
		);
		expect(src).toMatch(/\{#if t\.repair\}/);
		expect(src).toMatch(/repairNote\(t\.out\.web_name, t\.repair_reason, t\.gain_xp_remaining\)/);
	});
});
