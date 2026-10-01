/**
 * SHARE-CARD-ULKOASU (1.10.2026). Replacements-jakokortti sai vertailurivin
 * (lahtija), eron lahtijaan ja xP-palkit. Kolme tapaa joilla kuva voisi
 * valehdella, ja portti jokaiselle:
 *
 * 1. Ero ei tasmaa kortin omiin lukuihin. Backendin `xp_gap_vs_target` on
 *    pyoristamattomien summien erotus: 31.03 - 24.27 = 6.76 -> "+6.8", vaikka
 *    kortilla lukee 31.0 ja 24.3. Ero lasketaan NAYTETYISTA luvuista.
 * 2. Palkki on eri mieltä kuin numero. Palkki luetaan samasta merkkijonosta
 *    kuin naytetty arvo, ja jos yksikin arvo ei ole luku (no xP, 14 %, -1.2),
 *    palkkeja ei piirreta lainkaan.
 * 3. Vertailurivin otsake vaittaa saatavuutta. "OUT" luetaan FPL:ssa
 *    loukkaantumislippuna (portti 16.9 hylkasi "out in FPL").
 *
 * Kutsupaikka-osio: funktiotesti pysyy vihreana jos sivu lakkaa kutsumasta
 * funktiota (muisti: testi kutsuu funktiota, ei kutsupaikkaa).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { replacementsCardSpec, shownGap } from './replacementCard';
import { valueBarFractions } from './shareCard';
import { blankComments } from './sourceScan';
import type { ReplacementsResponse } from './fantasyTools';

const lue = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'));

function vastaus(targetXp: number | null, xps: number[], chance: number | null = null): ReplacementsResponse {
	return {
		meta: {
			generated_at: null,
			gws: [6, 7, 8, 9, 10, 11],
			bracket_requested: 2,
			bracket: 2,
			bracket_widened: false,
			price_min: 7.7,
			price_max: 11.7,
			candidates_in_bracket: 20
		},
		target: {
			id: 1,
			web_name: 'Palmer',
			team_short: 'CHE',
			pos: 'MID',
			price: 9.7,
			owned_pct: 25.7,
			xp_window: targetXp,
			p_start: 0.8,
			status: chance != null ? 'd' : 'a',
			chance_next: chance,
			news: ''
		},
		players: xps.map((x, i) => ({
			id: 10 + i,
			web_name: `P${i}`,
			team_short: 'ARS',
			pos: 'MID',
			price: 8,
			owned_pct: 10,
			xp_window: x,
			xp_gap_vs_target: targetXp != null ? x - targetXp : null,
			gameweeks: [],
			p_start: 0.9,
			status: 'a',
			chance_next: null,
			news: '',
			reason: { kind: 'flat', value: 5, text: 'no standout week, 4.0-5.0 xP' }
		}))
	} as unknown as ReplacementsResponse;
}

describe('ero lahtijaan lasketaan naytetyista luvuista', () => {
	it('31.03 vs 24.27 on +6.7 (kortilla 31.0 ja 24.3), ei backendin +6.8', () => {
		expect(shownGap(31.03, 24.27).text).toBe('+6.7');
		expect(shownGap(31.03, 24.27).text).not.toBe('+6.8');
	});
	it('etumerkki, nolla ja negatiivinen', () => {
		expect(shownGap(24.42, 24.27)).toEqual({ text: '+0.1', sign: 1 });
		expect(shownGap(24.3, 24.27)).toEqual({ text: '0.0', sign: 0 });
		expect(shownGap(22.2, 24.27)).toEqual({ text: '-2.1', sign: -1 });
	});
	it('jokaisella satunnaisella parilla ero == naytetty - naytetty', () => {
		let seed = 7;
		const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 45;
		for (let k = 0; k < 2000; k++) {
			const a = rnd();
			const b = rnd();
			const shown = Math.round((Number(a.toFixed(1)) - Number(b.toFixed(1))) * 10) / 10;
			expect(Number(shownGap(a, b).text)).toBeCloseTo(shown, 9);
		}
	});
});

describe('kortin spec', () => {
	it('vertailurivi kantaa lahtijan luvun ja otsake ei vaita saatavuutta', () => {
		const s = replacementsCardSpec(vastaus(24.27, [32.31, 31.03, 27.96]));
		expect(s.hero?.label).toBe('REPLACING');
		expect(s.hero?.label).not.toMatch(/\bOUT\b/i);
		expect(s.hero?.row.value).toBe('24.3');
		expect(s.subtitle).not.toContain('24.3');
		expect(s.valueBars).toBe(true);
	});
	it('jokaisen rivin ero tasmaa kortin omiin lukuihin', () => {
		const s = replacementsCardSpec(vastaus(24.27, [32.31, 31.03, 27.96, 25.47, 24.42]));
		for (const r of s.rows) {
			const d = Number(r.delta!.split(' ')[0]);
			expect(d).toBeCloseTo(Number(r.value) - Number(s.hero!.row.value), 9);
			expect(r.delta).toMatch(/ vs Palmer$/);
			expect(r.deltaUp).toBe(d > 0);
		}
	});
	it('ilman lahtijan projektiota: ei eroja, arvo "no xP", ei palkkeja', () => {
		const s = replacementsCardSpec(vastaus(null, [32.31, 31.03, 27.96], 0));
		expect(s.hero?.row.value).toBe('no xP');
		expect(s.rows.every((r) => r.delta === undefined)).toBe(true);
		expect(
			valueBarFractions([...s.rows.map((r) => r.value), s.hero!.row.value])
		).toBeNull();
	});
	it('FPL:n luku kantaa kierroksen, eika 100 % paady kuvaan', () => {
		expect(replacementsCardSpec(vastaus(24.27, [30, 29, 28], 75)).hero?.row.badges).toEqual([
			'75% to play GW6'
		]);
		expect(replacementsCardSpec(vastaus(24.27, [30, 29, 28], 100)).hero?.row.badges).toBeUndefined();
	});
});

describe('palkki luetaan naytetysta arvosta', () => {
	it('suurin = 1, muut suhteessa', () => {
		expect(valueBarFractions(['32.3', '16.15', '0'])).toEqual([1, 0.5, 0]);
	});
	it('yksikin ei-luku tai etumerkki -> ei palkkeja ollenkaan', () => {
		for (const bad of ['no xP', '14%', '-1.2', '+0.4', '']) {
			expect(valueBarFractions(['32.3', bad, '20.0'])).toBeNull();
		}
	});
});

describe('kutsupaikat', () => {
	it('Replacements-sivu jakaa kortin spec-funktion kautta', () => {
		const src = lue('./components/Replacements.svelte');
		expect(src).toMatch(/shareCard\(replacementsCardSpec\(data\)\)/);
		expect(src).not.toMatch(/WHO REPLACES/);
	});
	it('sivun vs-sarake lukee saman lukijan kuin kortti', () => {
		const src = lue('./components/Replacements.svelte');
		expect(src).toMatch(/shownGap\(p\.xp_window, t\)/);
		expect(src).not.toMatch(/xp_gap_vs_target/);
	});
	it('kortinpiirtaja ei piirra keksittya seuravaria', () => {
		const src = lue('./shareCard.ts');
		expect(src).toMatch(/knownTeamColor\(club\)/);
		const block = src.slice(src.indexOf('const drawRow'), src.indexOf('if (hero) {'));
		expect(block).not.toMatch(/teamColorByShort/);
	});
});
