/**
 * Portti: kumppaniattribuutio tilille + lukitun siirron oma funnel-source (1.10.2026).
 *
 * Mittaus cc-reports/2026-10-01-demon-polku-ja-konversiomittari.md:
 *   - Demonin `utm_source=fpldemon` ei paatynyt tilille lainkaan (vain `?ref=`).
 *   - Lukitun siirron naytosta ei lahtenyt tapahtumaa, klikkaus jakoi sourcen.
 * Funktiotesti ei riita (muisti: testi kutsuu funktiota, ei kutsupaikkaa),
 * joten kutsupaikat luetaan lahteesta.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { beforeEach, describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import {
	attributionData,
	capturePartner,
	partnerFromSearch,
	storedPartner
} from './partnerAttribution';

const src = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8'));

describe('partnerAttribution', () => {
	beforeEach(() => {
		const m = new Map<string, string>();
		(globalThis as { localStorage?: unknown }).localStorage = {
			getItem: (k: string) => m.get(k) ?? null,
			setItem: (k: string, v: string) => void m.set(k, v),
			removeItem: (k: string) => void m.delete(k)
		};
	});

	it('Demonin linkki tunnistetaan, muut utm:t eivat ole kumppaneita', () => {
		expect(partnerFromSearch('?utm_source=fpldemon&utm_medium=partner&utm_content=nav')).toBe(
			'fpldemon'
		);
		expect(partnerFromSearch('?utm_source=FPLDemon&utm_medium=Partner')).toBe('fpldemon');
		expect(partnerFromSearch('?utm_source=twitter&utm_medium=social')).toBeNull();
		expect(partnerFromSearch('?utm_source=fpldemon')).toBeNull();
		expect(partnerFromSearch('?utm_source=<x>&utm_medium=partner')).toBeNull();
	});

	it('ensimmainen kumppani pitaa attribuution', () => {
		expect(capturePartner('?utm_source=fpldemon&utm_medium=partner')).toBe('fpldemon');
		expect(capturePartner('?utm_source=toinen&utm_medium=partner')).toBe('fpldemon');
		expect(storedPartner()).toBe('fpldemon');
	});

	it('attributionData: ref ja partner omissa avaimissaan, olemassa olevaa ei ylikirjoiteta', () => {
		expect(attributionData(null, 'fpldemon')).toEqual({ partner: 'fpldemon' });
		expect(attributionData('ROWAN', 'fpldemon')).toEqual({ ref: 'ROWAN', partner: 'fpldemon' });
		expect(attributionData(null, null)).toBeNull();
		expect(attributionData('ROWAN', 'fpldemon', { ref: 'X', partner: 'y' })).toBeNull();
		// Kumppani EI koskaan paady refiin (ref = provisio).
		expect(attributionData(null, 'fpldemon')?.ref).toBeUndefined();
	});
});

describe('kutsupaikat', () => {
	it('layout poimii kumppanin bootissa', () => {
		expect(src('../routes/+layout.svelte')).toMatch(/capturePartner\(window\.location\.search\)/);
	});

	it('signUp ja OAuth-paluu kirjoittavat kumppanin tilille', () => {
		const a = src('./auth.svelte.ts');
		expect(a).toMatch(/options:\s*\{\s*data:\s*meta\s*\}/);
		expect(a).toMatch(/updateUser\(\{\s*data:\s*meta\s*\}\)/);
		expect((a.match(/attributionData\(/g) ?? []).length).toBe(2);
		// billing.ts (ref/Stripe) ei lue kumppania.
		expect(src('./billing.ts')).not.toMatch(/partner/i);
	});

	it('lukittu siirto: oma source seka naytolle etta klikkaukselle', () => {
		const d = src('./components/DecisionCard.svelte');
		expect(d).toMatch(/LOCK_SOURCE = 'decision_transfer_lock'/);
		expect(d).toMatch(/capture\('paywall_shown', \{ source: LOCK_SOURCE/);
		expect(d).toMatch(/onUpgrade\?\.\(LOCK_SOURCE\)/);
		const r = src('./components/RateTeam.svelte');
		expect(r).toMatch(/capture\('upgrade_tapped', \{ source: typeof source === 'string' \? source : 'fantasy_tools' \}\)/);
	});
});
