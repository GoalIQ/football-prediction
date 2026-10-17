/**
 * Portti: kumppaniattribuutio tilille + lukitun siirron oma funnel-source (1.10.2026).
 * 17.10.2026: lukitun siirron source korvautui henkilokohtaisten tyokalujen
 * lukolla (PersonalLock, source 'personal_lock' / 'personal_lock_<tool>').
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

	it('OAuth-paluu ajaa adoptoinnin kun kayttaja vaihtuu (GOOGLE-OAUTH-REF-E2E)', () => {
		// Mitattu 3.10 Supabasesta: Google-signup ?ref=TESTREF 2.10 14:50 UTC ->
		// auth.users.raw_user_meta_data.ref = TESTREF. Polku toimii vain jos
		// applySession kutsuu adoptOAuthAccountia; ilman sita updateUser-rivi
		// jaa funktioon eika yllaoleva testi huomaa mitaan.
		const a = src('./auth.svelte.ts');
		expect(a).toMatch(/if \(u && u\.id !== prevId\) \{[^}]*\badoptOAuthAccount\(u\b/);
	});

	/* 17.10.2026 (tyokalut taakse): 1.10:n `decision_transfer_lock` (vain
	   siirtopari lukittu) korvautui koko oman paatoskortin lukolla. Mittari
	   sailyy erotteluvoimaisena: nakyma ja klikkaus kirjataan YHDESSA
	   komponentissa (PersonalLock) tyokalukohtaisella lahteella, eika
	   kutsupaikka kirjaa klikkausta toista kertaa. */
	it('lukittu paatoskortti: oma source seka naytolle etta klikkaukselle', () => {
		const lock = src('./components/PersonalLock.svelte');
		expect(lock).toMatch(/capture\(\s*'paywall_shown',\s*\{ source: PERSONAL_LOCK_SOURCE, tool \}/);
		expect(lock).toMatch(/capture\('upgrade_tapped', \{ source: lockUpgradeSource\(tool\) \}\)/);
		const d = src('./components/DecisionCard.svelte');
		expect(d).toMatch(/<PersonalLock tool="this-week" \{onUpgrade\}/);
		expect(d).not.toMatch(/decision_transfer_lock/);
		// RateTeam ei enaa kirjaa upgrade_tappedia itse (ennen `unlock` +
		// 'fantasy_tools'): ThisWeekille menee pelkka avaaja.
		const r = src('./components/RateTeam.svelte');
		expect(r).not.toMatch(/capture\('upgrade_tapped'/);
		expect(r).toMatch(/<ThisWeek[\s\S]*?\{onUpgrade\}[\s\S]*?\/>/);
	});
});
