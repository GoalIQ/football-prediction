// $lib/defconBasis.gate.test.ts - DefCon-oletus kauden vaiheesta (2.10.2026).
// Sama lukija ja samat vaiheet kuin goaliq-app lib/defconBasis.test.ts.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { defconDefaultBasis } from './defconBasis';

describe('defconDefaultBasis', () => {
	it('esikausi ja vajaa ikkuna: koko kausi', () => {
		expect(defconDefaultBasis({ is_prev_season_basis: true, season_finished_gws: 0 }, 5)).toBe('season');
		expect(defconDefaultBasis({ is_prev_season_basis: false, season_finished_gws: 4 }, 5)).toBe('season');
		expect(defconDefaultBasis(null, 5)).toBe('season');
	});
	it('ikkuna taynna: kuluva kausi (NEG: 2.10 GW6 nayttaa 2025/26)', () => {
		expect(defconDefaultBasis({ is_prev_season_basis: false, season_finished_gws: 5 }, 5)).toBe('recent');
	});
	it('kutsupaikka: Leaders kysyy lukijalta ja kayttajan valinta lukitsee', () => {
		const src = readFileSync(new URL('./components/Leaders.svelte', import.meta.url), 'utf8');
		expect(src).toMatch(/defconDefaultBasis\(x\.meta, dcWindow\)/);
		expect(src).toMatch(/dcBasisTouched = true/);
	});
});
