/**
 * Portti: Fixtures -> Predict esitayttaa ottelun kaikilla reiteilla (22.9.2026).
 *
 * Vika (Ville 22.9, mitattu tuotannossa selaimella): alapalkki -> Matches
 * (/matches, ryhmasivu) -> ottelun "Predict" -> /matches/predict
 * (tyokalusivu). Reitti vaihtui, ToolsHome rakentui uudelleen ja sen
 * `$state`issa ollut ottelu katosi: valinnat tyhjina, ei ennustetta. Myos
 * liigan vaihto Fixturesissa (La Liga) katosi samasta syysta.
 *
 * Saanto 6a: ottelu kulkee URL:ssa, yksi lukija `predictPrefillFrom`, ja
 * KUTSUPAIKKA on lukittu: ToolsHome ei saa pitaa ottelua omassa tilassaan.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import { PREDICT_PATH, predictHref, predictPrefillFrom } from './predictLink';

const read = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')).replace(
		/\r\n/g,
		'\n'
	);

describe('predictLink: ottelu URL:ssa', () => {
	it('edestakaisin: liiga, kotijoukkue ja vieras sailyvat myos erikoismerkeilla', () => {
		for (const [l, h, a] of [
			['ENG-Premier League', 'Arsenal', 'Leeds United'],
			['ESP-La Liga-FD', 'Málaga', 'Espanyol'],
			['ENG-Premier League', 'Brighton & Hove Albion', "Nott'm Forest"]
		]) {
			const href = predictHref(l, h, a);
			expect(href.startsWith(`${PREDICT_PATH}?`)).toBe(true);
			const q = new URL(href, 'https://pro.goaliq.app').searchParams;
			expect(predictPrefillFrom(q)).toEqual({ league: l, home: h, away: a });
		}
	});

	it('puuttuva tai tyhja kentta -> ei esitayttoa (ei arvata)', () => {
		for (const s of ['', 'league=ENG-Premier%20League&home=Arsenal', 'league=&home=a&away=b', 'home=a&away=b']) {
			expect(predictPrefillFrom(new URLSearchParams(s))).toBeNull();
		}
	});
});

describe('KUTSUPAIKKA: ToolsHome ei pida ottelua omassa tilassaan', () => {
	const src = read('./components/ToolsHome.svelte');

	it('goPredict navigoi predictHrefilla ja esitaytto luetaan URL:sta', () => {
		expect(src).toMatch(/void goto\(predictHref\(lg, h, a\)\)/);
		expect(src).toMatch(/const predictPrefill = \$derived\(predictPrefillFrom\(page\.url\.searchParams\)\)/);
		expect(src).toMatch(/<Predict\b[^>]*prefill=\{predictPrefill\}/);
	});

	it('NEG: ottelu ei ole komponentin $statessa eika navigointi ole paljas polku', () => {
		expect(src).not.toMatch(/predictPrefill = \$state/);
		expect(src).not.toMatch(/goto\(['"]\/matches\/predict['"]\)/);
	});

	it('molemmat reittisivut valittavat queryn ohjauksessa (muuten ottelu katoaisi taas)', () => {
		for (const f of ['../routes/[group]/+page.svelte', '../routes/[group]/[tool]/+page.svelte']) {
			expect(read(f)).toMatch(/goto\(`\$\{target \?\? '\/'\}\$\{page\.url\.search\}/);
		}
	});
});
