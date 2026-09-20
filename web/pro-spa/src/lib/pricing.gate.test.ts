import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/**
 * PORTTI: maksumuurin luku tulee palvelimelta, ja likiarvo ei saa olla eri
 * hinnasta kuin nappi.
 *
 * Runes-tilaa (`$state`) ei voi ajaa taalla ilman Svelte-kaantajaa, joten
 * tama lukee LAHDEKOODIN. Invariantit ovat luettavissa suoraan ja ne ovat
 * juuri ne joita on helppo rikkoa vahingossa myohemmin.
 */
const SRC = fileURLToPath(new URL('./pricing.svelte.ts', import.meta.url));
const PAYWALL = fileURLToPath(new URL('./components/Paywall.svelte', import.meta.url));
const PREVIEW = fileURLToPath(new URL('./components/PremiumPreview.svelte', import.meta.url));

describe('pricing: sivu ja checkout sanovat saman luvun', () => {
	const koodi = readFileSync(SRC, 'utf8');

	it('maata ei paatella selaimesta', () => {
		// Palvelin lukee CF-otsakkeen. Jos SPA arvaisi maan localesta, kavija
		// voisi nahda eri hinnan kuin han maksaa.
		for (const kielletty of ['navigator.language', 'Intl.Locale', 'timeZone']) {
			expect(koodi.includes(kielletty), `${kielletty} maan paattelyyn`).toBe(false);
		}
	});

	it('haku on fail-soft: PLANS jaa voimaan', () => {
		expect(koodi).toContain('catch');
		expect(koodi).toContain('PLANS[key].label');
	});

	it('likiarvo naytetaan vain listahinnalla', () => {
		expect(koodi).toContain('showApprox');
		expect(koodi).toMatch(/showApprox[\s\S]{0,120}planTier\(key\) === 'default'/);
	});

	for (const [nimi, polku] of [['Paywall', PAYWALL], ['PremiumPreview', PREVIEW]] as const) {
		it(`${nimi} kayttaa palvelimen lukua eika PLANS.label-kenttaa`, () => {
			const c = readFileSync(polku, 'utf8');
			expect(c).toContain('planLabel(');
			expect(c).toContain('loadPricing');
			// Kutsupaikkaportti: ilman tata komponentin voi palauttaa
			// kovakoodattuun lappuun ilman etta mikaan huomaa.
			expect(c.includes('plan.label')).toBe(false);
		});
		it(`${nimi} ei nayta likiarvoa aluehinnalla`, () => {
			const c = readFileSync(polku, 'utf8');
			expect(c).toContain('showApprox(');
		});
	}
});
