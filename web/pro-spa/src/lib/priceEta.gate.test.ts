import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import {
	nextUpdateMoves,
	priceEta,
	priceEtaWord,
	squadPriceMoves,
	type LocalClock
} from './priceEta';

/* PRICE-ETA-ABSOLUUTTINEN-AIKA (26.9.2026). Julkaisutarkistaja blokkasi
   MP-10:n hintarivit: "tonight" johdettiin eta_days-offsetista ilman
   kellonaikaa ja oli vaarin Amerikoissa joka ilta seka buildiviiveessa. Saanto
   6a (3): invariantti mitataan jokaisessa vaiheessa ja vyohykkeessa, ei vain
   siina jossa testaaja sattuu istumaan. */

/** Kiintea UTC-siirtyma minuutteina (26.9 kaikki alla olevat ovat vakioita:
 *  BST +60, EEST +180, BRT -180, CST (Mexico) -360, AEST +600). */
const zone =
	(offsetMin: number): LocalClock =>
	(ms) => {
		const t = new Date(ms + offsetMin * 60_000);
		return { y: t.getUTCFullYear(), m: t.getUTCMonth(), d: t.getUTCDate(), h: t.getUTCHours() };
	};
const LONDON = zone(60);
const HELSINKI = zone(180);
const SAO_PAULO = zone(-180);
const MEXICO = zone(-360);
const SYDNEY = zone(600);
const at = (iso: string) => Date.parse(iso);

const UPD_26 = '2026-09-26T23:00:00Z';
const UPD_27 = '2026-09-27T23:00:00Z';
const UPD_28 = '2026-09-28T23:00:00Z';

describe('priceEta: paivasana lukijan ajassa', () => {
	it('Lontoo 20:00: paivitys keskiyolla -> tonight', () => {
		expect(priceEta(UPD_26, at('2026-09-26T19:00:00Z'), LONDON)?.kind).toBe('tonight');
	});
	it('Helsinki 20:00: paivitys 02:00 -> tonight (ei tomorrow)', () => {
		expect(priceEta(UPD_26, at('2026-09-26T17:00:00Z'), HELSINKI)?.kind).toBe('tonight');
	});
	it('Helsinki 01:00: paivitys tunnin paasta -> yha tonight', () => {
		expect(priceEta(UPD_26, at('2026-09-26T22:00:00Z'), HELSINKI)?.kind).toBe('tonight');
	});
	it('Sao Paulo 21:00 paivityksen jalkeen: uusi build -> tomorrow', () => {
		expect(priceEta(UPD_27, at('2026-09-27T00:00:00Z'), SAO_PAULO)?.kind).toBe('tomorrow');
	});
	it('Sao Paulo 21:00, vanha build (paivitys jo mennyt) -> ei sanaa', () => {
		expect(priceEta(UPD_26, at('2026-09-27T00:00:00Z'), SAO_PAULO)).toBeNull();
	});
	it('Mexico City 10:00: paivitys 17:00 -> today', () => {
		expect(priceEta(UPD_26, at('2026-09-26T16:00:00Z'), MEXICO)?.kind).toBe('today');
	});
	it('Sydney 12:00: seuraava paivitys huomisaamuna -> tomorrow', () => {
		expect(priceEta(UPD_27, at('2026-09-27T02:00:00Z'), SYDNEY)?.kind).toBe('tomorrow');
	});
	it('19:11Z-build katsottuna 23:30Z -> rivi pudotetaan', () => {
		expect(priceEta(UPD_26, at('2026-09-26T23:30:00Z'), LONDON)).toBeNull();
	});
	it('kahden paivan paasta -> in 2 days', () => {
		const e = priceEta(UPD_28, at('2026-09-26T19:00:00Z'), LONDON);
		expect(e).toEqual({ kind: 'days', days: 2 });
		expect(priceEtaWord(e!)).toBe('in 2 days');
		expect(priceEtaWord(e!, true)).toBe('In 2 days');
	});
	it('puuttuva tai roska eta_at -> ei sanaa (fail-closed)', () => {
		for (const bad of [undefined, null, '', 'tonight', 0, '2026-13-99']) {
			expect(priceEta(bad, at('2026-09-26T19:00:00Z'), LONDON)).toBeNull();
		}
	});
});

describe('squadPriceMoves ja nextUpdateMoves', () => {
	const risers = [
		{ id: 1, web_name: 'Saka', status: 'rising_soon', eta_at: UPD_26 },
		{ id: 2, web_name: 'Rogers', status: 'rising_watch', eta_at: UPD_27 },
		{ id: 3, web_name: 'Barry', status: 'rising_soon' },
		{ id: 99, web_name: 'NotMine', status: 'rising_soon', eta_at: UPD_26 }
	];
	const fallers = [{ id: 4, web_name: 'Palmer', status: 'falling_soon', eta_at: UPD_27 }];
	const now = at('2026-09-26T19:00:00Z');

	it('vain ruudun rungon _soon-rivit joilla on tuleva aika', () => {
		const m = squadPriceMoves(new Set([1, 2, 3, 4]), risers, fallers, now, LONDON);
		expect(m.rising.map((r) => r.web_name)).toEqual(['Saka']);
		expect(m.falling.map((r) => [r.web_name, r.eta.kind])).toEqual([['Palmer', 'tomorrow']]);
	});
	it('seuraavan paivityksen rivit ja niiden sana', () => {
		expect(nextUpdateMoves([...risers, ...fallers], now, LONDON)).toEqual({ n: 2, kind: 'tonight' });
		expect(nextUpdateMoves([...risers, ...fallers], at('2026-09-26T16:00:00Z'), MEXICO)).toEqual({
			n: 2,
			kind: 'today'
		});
		// Vanha build klo 00:30 BST: 26.9:n paivitys on mennyt (Saka pois), ja
		// offset 1 -rivi (Rogers) on nyt SEURAAVA paivitys -> tonight.
		expect(nextUpdateMoves(risers, at('2026-09-26T23:30:00Z'), LONDON)).toEqual({ n: 1, kind: 'tonight' });
	});
});

describe('kutsupaikat lukevat paivasanan vain $lib/priceEta:sta', () => {
	const read = (f: string) => readFileSync(new URL(`./components/${f}`, import.meta.url), 'utf-8');
	for (const f of ['SquadNews.svelte', 'PriceWatch.svelte']) {
		it(`${f}: ei eta_days-johdettua paivasanaa`, () => {
			const src = read(f).replace(/<!--[\s\S]*?-->/g, '').replace(/\/\/[^\n]*/g, '');
			expect(src).not.toMatch(/eta_days\s*(===|<=|==|!==)/);
			expect(src).not.toMatch(/return 'tonight'|>\s*Tonight\s*</);
			expect(src).toMatch(/from '\$lib\/priceEta'/);
		});
	}
	it('SquadNews leikkaa listat ruudun runkoon lukijalla', () => {
		expect(read('SquadNews.svelte')).toMatch(/squadPriceMoves\(ids, lists\?\.risers, lists\?\.fallers/);
	});
	it('PriceWatch: sarake, statusluokka ja yhteenveto samasta lukijasta', () => {
		const src = read('PriceWatch.svelte');
		expect(src).toMatch(/\{@const eta = priceEta\(r\.eta_at, Date\.now\(\)\)\}/);
		expect(src).toMatch(/_soon'\) && priceEta\(r\.eta_at, Date\.now\(\)\) == null/);
		expect(src).toMatch(/nextUpdateMoves\(\[\.\.\.o\.rising, \.\.\.o\.falling\]/);
	});
});
