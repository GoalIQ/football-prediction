/** Portti: kumppanilinkki (26.9.2026, FPL Demon).
 *
 * (1) URL tulee vain $lib/partners:sta (ref-tagi ei voi unohtua pinnasta),
 * (2) linkki on maksajan xP-listan alla eika lukitussa esikatselussa, joka on
 *     ostohetki (kumppanin ilmaistaso pyorii meidan luvuillamme),
 * (3) klikkaus kirjataan ja linkki avautuu uuteen valilehteen noopenerilla.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { FPL_DEMON, partnerActive } from './partners';

const LIB = fileURLToPath(new URL('.', import.meta.url));
const SRC = join(LIB, '..');
const read = (p: string) => readFileSync(join(LIB, p), 'utf-8');
const strip = (s: string) => s.replace(/<!--[\s\S]*?-->/g, '');

function walk(dir: string): string[] {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		return statSync(p).isDirectory() ? walk(p) : [p];
	});
}

describe('kumppanilinkki', () => {
	it('URL: https, planneri ja Demonin itse antamat seurantatagit (DM 27.9)', () => {
		const u = new URL(FPL_DEMON.url);
		expect(u.protocol).toBe('https:');
		expect(u.hostname).toBe('fpldemon.com');
		expect(u.pathname).toBe('/fpl/planner');
		expect(u.searchParams.get('utm_source')).toBe('goaliq');
		expect(u.searchParams.get('utm_medium')).toBe('social');
		expect(u.searchParams.get('utm_campaign')).toBe('goaliq');
	});

	it('kumppanin domain vain partners.ts:ssa (ei kasin kirjoitettuja URL:eja)', () => {
		const osumat = walk(SRC)
			.filter((p) => /\.(ts|svelte)$/.test(p) && !p.endsWith('.test.ts'))
			.filter((p) => readFileSync(p, 'utf-8').includes('fpldemon.com'))
			.map((p) => p.split(String.fromCharCode(92)).join('/').split('/src/').pop());
		expect(osumat).toEqual(['lib/partners.ts']);
	});

	it('paattyy itsestaan (B4): nakyy ennen activeUntilia, ei sen jalkeen', () => {
		const raja = Date.parse(FPL_DEMON.activeUntil);
		expect(Number.isFinite(raja)).toBe(true);
		expect(partnerActive(FPL_DEMON, raja - 1)).toBe(true);
		expect(partnerActive(FPL_DEMON, raja)).toBe(false);
		expect(partnerActive(FPL_DEMON, Date.parse('2026-09-26T12:00:00Z'))).toBe(true);
		expect(partnerActive({ ...FPL_DEMON, activeUntil: '' }, raja - 1)).toBe(false);
		expect(partnerActive({ ...FPL_DEMON, activeUntil: 'huomenna' }, raja - 1)).toBe(false);
		// Kokeilu on sovittu GW10:n loppuun; pidempi paiva vaatii paatoksen.
		expect(FPL_DEMON.activeUntil <= '2026-11-10').toBe(true);
	});

	it('komponentti: href partnerista, uusi valilehti, noopener, klikkaus kirjataan', () => {
		const src = strip(read('components/PartnerLink.svelte'));
		expect(src).toMatch(/href=\{partner\.url\}/);
		expect(src).toMatch(/target="_blank"/);
		expect(src).toMatch(/rel="noopener"/);
		expect(src).toMatch(/capture\('partner_link_clicked', \{ partner: partner\.id, surface \}\)/);
		expect(src).toMatch(/<span class="tag">Partner<\/span>/);
		// Koko kappale on paattymisehdon sisalla, ei vain osa.
		expect(src.trim()).toMatch(/\{#if partnerActive\(partner\)\}\s*<p class="partner">[\s\S]*<\/p>\s*\{\/if\}/);
	});

	it('sijoitus: maksajan haarassa XpTablen alla, ei lukitussa esikatselussa', () => {
		const th = strip(read('components/ToolsHome.svelte'));
		expect(th.match(/<PartnerLink /g)?.length).toBe(1);
		const premiumAlku = th.indexOf("{#if premium && (show('captain-ranker') || show('fixture-swing') || show('player-xp'))}");
		const lukittuAlku = th.indexOf("{:else if show('captain-ranker') || show('fixture-swing') || show('player-xp')}");
		const xp = th.indexOf('<XpTable data={xp} />');
		const link = th.indexOf('<PartnerLink partner={FPL_DEMON} surface="player_xp" />');
		expect(premiumAlku).toBeGreaterThan(-1);
		expect(xp).toBeGreaterThan(premiumAlku);
		expect(link).toBeGreaterThan(xp);
		expect(link).toBeLessThan(lukittuAlku);
		expect(read('components/LockedToolPreview.svelte')).not.toMatch(/PartnerLink|partners/);
	});
});
