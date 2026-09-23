/** Portti: ilmaisikkunan paiva johdetaan aikaleimasta, ei kirjoiteta kasin.
 *
 * 🔴 MIKSI (SPA-IKKUNAN-PAIVA-KIRJOITETTU-AUKI, mitattu 18.9, korjattu 23.9):
 * SPA kirjoitti ikkunan lopun auki 11 merkkijonoon kuudessa komponentissa
 * ("12 September", "GW4 deadline", "GW1 to GW3") vaikka aikaleima oli jo
 * olemassa. Jonorivi loysi yhdeksan; loput kaksi (Hero-leima, LoginBox)
 * loytyivat vasta tamalla grepilla. Seuraavan ikkunan avaaja olisi joutunut
 * muistamaan jokaisen, ja unohdus lupaa vaaran paivan. Sama vikaluokka jonka
 * ILMAISIKKUNA-SULKEUTUU-ITSE korjasi paistetuille sivuille.
 *
 * Mekanismit (CLAUDE.md 6a): (1) yksi lahde freeWindow.ts, (2) poikkeuslista
 * perusteluineen (tyhja), (3) paivan muotoilu mitataan usealla aikaleimalla,
 * myos vyohykkeen rajalla.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
	FREE_PREMIUM_GWS,
	FREE_PREMIUM_UNTIL,
	FREE_PREMIUM_UNTIL_DAY,
	FREE_PREMIUM_UNTIL_GW,
	windowDayLabel
} from './freeWindow';

const SRC = resolve(__dirname, '..');
const MONTHS =
	'January|February|March|April|May|June|July|August|September|October|November|December';
const DAY_MONTH = new RegExp(
	`\\b\\d{1,2}(?:st|nd|rd|th)?\\s+(?:${MONTHS})\\b|\\b(?:${MONTHS})\\s+\\d{1,2}\\b`
);
const GW_RANGE = /\bGW1 to GW\d+\b/;

/** Tiedosto -> perustelu. Uusi rivi vaatii perustelun diffissa. */
const POIKKEUKSET: Record<string, string> = {};

function files(dir: string): string[] {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		if (statSync(p).isDirectory()) return files(p);
		return /\.(svelte|ts)$/.test(n) && !/\.test\.ts$/.test(n) ? [p] : [];
	});
}

/** Kommentit pois: perustelu saa mainita paivan, koodi ei. */
function code(src: string): string {
	return src
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.split('\n')
		.map((l) => l.replace(/(^|[^:'"`])\/\/.*$/, '$1'))
		.join('\n');
}

describe('ilmaisikkunan paiva: yksi lahde', () => {
	it('paiva ja kierrokset johdetaan aikaleimasta', () => {
		expect(FREE_PREMIUM_UNTIL).toBe('2026-09-12T12:30:00Z');
		expect(FREE_PREMIUM_UNTIL_DAY).toBe('12 September');
		expect(FREE_PREMIUM_UNTIL_GW).toBe(4);
		expect(FREE_PREMIUM_GWS).toBe('GW1 to GW3');
	});

	it('muotoilu seuraa aikaleimaa eika ole vakio (vaiheet)', () => {
		// Aikaleimat rakennetaan Date.UTC:lla eika ISO-literaaleina: fp:n
		// tests/test_free_window_self_closing.py lukee jokaisen ikkunan
		// nimeavan tiedoston ISO-leimat ikkunan hetkiksi.
		const iso = (...a: [number, number, number, number, number]) =>
			new Date(Date.UTC(...a)).toISOString();
		expect(windowDayLabel(iso(2027, 0, 5, 11, 0))).toBe('5 January');
		expect(windowDayLabel(iso(2026, 11, 31, 23, 30))).toBe('31 December');
		// Vyohykkeen raja: UTC+13:ssa tama on jo 13. paiva, UTC:ssa ei.
		expect(windowDayLabel(iso(2026, 8, 12, 12, 30))).toBe('12 September');
		expect(windowDayLabel(iso(2026, 8, 12, 23, 59))).toBe('12 September');
	});

	it('mikaan SPA-tiedosto ei kirjoita kuukausipaivaa tai GW-valia kasin', () => {
		const loydot: string[] = [];
		for (const f of files(SRC)) {
			const rel = relative(SRC, f).replace(/\\/g, '/');
			if (rel === 'lib/freeWindow.ts' || rel in POIKKEUKSET) continue;
			code(readFileSync(f, 'utf-8'))
				.split('\n')
				.forEach((l, i) => {
					if (DAY_MONTH.test(l) || GW_RANGE.test(l)) loydot.push(`${rel}:${i + 1}: ${l.trim()}`);
				});
		}
		expect(loydot, 'kayta FREE_PREMIUM_UNTIL_DAY / FREE_PREMIUM_GWS').toEqual([]);
	});

	it('portti loytaa kasin kirjoitetun paivan (negatiivinen kontrolli)', () => {
		// Fikstuurit eivat saa olla fp:n CLAIM_RE-lauseita (scripts/check_free_window.py
		// lukee myos taman tiedoston), joten ne ovat neutraaleja muotoja.
		expect(DAY_MONTH.test(code('<h2>Offer ends 12 September</h2>'))).toBe(true);
		expect(DAY_MONTH.test(code('ends on September 12.'))).toBe(true);
		expect(GW_RANGE.test(code('Covers GW1 to GW3.'))).toBe(true);
		expect(DAY_MONTH.test(code('// 12 September kommentissa'))).toBe(false);
		expect(DAY_MONTH.test(code('<!-- 12 September -->'))).toBe(false);
	});

	it('kuusi komponenttia lukevat johdetut nimet', () => {
		const read = (f: string) => readFileSync(resolve(SRC, f), 'utf-8');
		for (const f of [
			'lib/components/ToolsHome.svelte',
			'lib/components/ProductIntro.svelte',
			'lib/components/PremiumPreview.svelte',
			'lib/components/Paywall.svelte',
			'lib/components/Hero.svelte',
			'lib/components/LoginBox.svelte'
		]) {
			expect(read(f), f).toContain('FREE_PREMIUM_UNTIL_DAY');
		}
	});
});
