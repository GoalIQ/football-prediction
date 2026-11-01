/** Portti: paivays ja kellonaika renderoidaan aina en-GB:lla (WP2, 1.11.2026).
 *
 * 🔴 MIKSI. My team naytti englanninkielisessa UI:ssa suomenkielisen
 * paivayksen: "FPL publishes GW10 squads a while after the deadline
 * (pe 6.11. klo 20.30 UTC+2)". RateTeamin apufunktio kutsui
 * `toLocaleString(undefined, ...)`, joka kayttaa SELAIMEN kielta.
 * `lib/gameweek.ts` oli lukinnut saman asian en-GB:hen jo 22.9 (deadline-rivi
 * luki "pe 21.8. klo 20.30"), mutta toinen kopio jai.
 *
 * Mekanismit (CLAUDE.md 6a): (1) yksi muotoilija `formatDeadline`
 * (gameweek.ts) deadlinen kaltaisille ajoille, (2) tama portti kaataa buildin
 * jos mika tahansa lahdetiedosto muotoilee paivan tai luvun ilman
 * eksplisiittista kielta, poikkeuslista perusteluineen (tyhja), (3) muotoilun
 * tulos mitataan usealla hetkella, myos vuoden ja vyohykkeen rajalla.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { formatDeadline } from './gameweek';
import { findInCode } from './sourceScan';

const SRC = resolve(__dirname, '..');

/** Kutsu joka jattaa kielen selaimelle: ilman argumenttia, `undefined`,
 *  tyhja taulukko tai pelkat optiot ensimmaisena argumenttina. */
const LOCALE_LESS =
	/\.toLocale(?:Date|Time)?String\(\s*(?:\)|undefined\b|\[\s*\]|\{)|Intl\.(?:DateTimeFormat|NumberFormat|RelativeTimeFormat)\(\s*(?:\)|undefined\b|\[\s*\]|\{)/;

/** Tiedosto -> perustelu. Uusi rivi vaatii perustelun diffissa. */
const POIKKEUKSET: Record<string, string> = {};

function files(dir: string): string[] {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		if (statSync(p).isDirectory()) return files(p);
		return /\.(svelte|ts)$/.test(n) && !/\.test\.ts$/.test(n) ? [p] : [];
	});
}

function hits(): string[] {
	const out: string[] = [];
	for (const f of files(SRC)) {
		const rel = relative(SRC, f).replace(/\\/g, '/');
		if (rel in POIKKEUKSET) continue;
		for (const l of findInCode(readFileSync(f, 'utf-8'), LOCALE_LESS)) {
			out.push(`${rel}:${l.n}: ${l.text.trim()}`);
		}
	}
	return out;
}

describe('paivays: kieli on aina eksplisiittinen', () => {
	it('mikaan lahdetiedosto ei muotoile paivaa selaimen kielella', () => {
		expect(hits()).toEqual([]);
	});

	it('kuvio osuu vanhaan RateTeamin muotoon (negatiivinen kontrolli)', () => {
		for (const vanha of [
			"return d.toLocaleString(undefined, { weekday: 'short' });",
			"d.toLocaleDateString()",
			"d.toLocaleTimeString({ hour: '2-digit' })",
			'new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })',
			'new Intl.DateTimeFormat()'
		]) {
			expect(findInCode(vanha, LOCALE_LESS), vanha).toHaveLength(1);
		}
		for (const ok of [
			"d.toLocaleString('en-GB', { weekday: 'short' })",
			"n.toLocaleString(locale)",
			"new Intl.DateTimeFormat('en-GB', { timeZoneName: 'short' })"
		]) {
			expect(findInCode(ok, LOCALE_LESS), ok).toHaveLength(0);
		}
	});

	it('poikkeuslistan rivit ovat olemassa ja perusteltuja', () => {
		for (const [rel, why] of Object.entries(POIKKEUKSET)) {
			expect(why.trim().length, rel).toBeGreaterThan(20);
			expect(statSync(join(SRC, rel)).isFile(), rel).toBe(true);
		}
	});
});

describe('formatDeadline: englanninkielinen muoto joka hetkella', () => {
	// Perjantai-ilta, vuodenvaihde ja kesaaika: sama muoto jokaisessa.
	const HETKET = [
		'2026-11-06T18:30:00Z',
		'2026-12-31T23:30:00Z',
		'2027-03-28T00:30:00Z',
		'2027-05-23T15:00:00Z'
	];
	for (const iso of HETKET) {
		it(iso, () => {
			const { when } = formatDeadline(new Date(iso));
			// "Fri 6 Nov, 20:30" - ei "pe 6.11. klo 20.30".
			expect(when).toMatch(/^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2} [A-Z][a-z]{2}, \d{2}:\d{2}$/);
			expect(when).not.toMatch(/klo|\d+\.\d+\./);
		});
	}
});
