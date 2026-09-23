/**
 * UCL-valintalistat synteettisilla vaiheilla (saanto 6a kohta 3). Mobiilin
 * lib/uclPicks.test.ts ajaa samat tapaukset samalla lukijalla.
 *   - ennen deadlinea            deadline_gameweek = 2, rivit MD2-MD4
 *   - deadline mennyt (refresh myohassa) -> ei kapteenilistaa
 *   - rivien jarjestys ei ole MD-jarjestys (gameweeks[0] != deadline-MD)
 *   - sarjavaihe ohi (available=false), maskattu, thin data
 */
import { describe, expect, it } from 'vitest';
import {
	UCL_CAPTAIN_TOP,
	UCL_DIFF_MAX_OWNED,
	UCL_LIST_TOP,
	captainMatchday,
	matchdayXp,
	uclPicks,
	type UclPickPlayer
} from './uclPicks';

let seq = 0;
function pl(over: Partial<UclPickPlayer> & { md2?: number; md3?: number } = {}): UclPickPlayer {
	const { md2 = 5, md3 = 4, ...rest } = over;
	return {
		id: ++seq,
		pos: 'MID',
		price: 8,
		owned_pct: 20,
		status: 'a',
		data_basis: 'domestic_league',
		xp_horizon_total: md2 + md3,
		gameweeks: [
			{ gw: 2, xp: md2 },
			{ gw: 3, xp: md3 }
		],
		...rest
	};
}
const META = { available: true, masked: false, deadline_gameweek: 2, deadline_passed: false };

describe('captainMatchday', () => {
	it('ennen deadlinea -> deadline-MD', () => expect(captainMatchday(META)).toBe(2));
	it('mennyt deadline -> null (lukittua kierrosta ei esiteta tulevana)', () =>
		expect(captainMatchday({ ...META, deadline_passed: true })).toBeNull());
	it('puuttuva tai rikki deadline -> null', () => {
		expect(captainMatchday({ ...META, deadline_gameweek: null })).toBeNull();
		expect(captainMatchday({ ...META, deadline_gameweek: 0 })).toBeNull();
		expect(captainMatchday(null)).toBeNull();
	});
});

describe('uclPicks captain', () => {
	it('jarjestaa deadline-MD:n xP:n mukaan, ei summan', () => {
		const a = pl({ md2: 3, md3: 20 });
		const b = pl({ md2: 7, md3: 0.5 });
		const r = uclPicks([a, b], META, 'captain');
		expect(r.state).toBe('rows');
		if (r.state !== 'rows') return;
		expect(r.rows.map((x) => x.player.id)).toEqual([b.id, a.id]);
		expect(r.md).toBe(2);
	});
	it('hakee rivin gw-numerolla vaikka gameweeks-jarjestys on eri', () => {
		const p = pl();
		p.gameweeks = [
			{ gw: 3, xp: 9 },
			{ gw: 2, xp: 1 }
		];
		expect(matchdayXp(p, 2)).toBe(1);
		const r = uclPicks([p], META, 'captain');
		expect(r.state === 'rows' && r.rows[0].score).toBe(1);
	});
	it('deadline-MD puuttuu rivilta -> rivi ei tule listalle', () => {
		const p = pl();
		p.gameweeks = [{ gw: 3, xp: 9 }];
		const r = uclPicks([p], META, 'captain');
		expect(r.state === 'rows' && r.rows.length).toBe(0);
	});
	it('mennyt deadline -> no_matchday', () => {
		expect(uclPicks([pl()], { ...META, deadline_passed: true }, 'captain').state).toBe('no_matchday');
	});
	it('top 10', () => {
		const many = Array.from({ length: 30 }, (_, i) => pl({ md2: i + 1 }));
		const r = uclPicks(many, META, 'captain');
		expect(r.state === 'rows' && r.rows.length).toBe(UCL_CAPTAIN_TOP);
	});
});

describe('uclPicks value', () => {
	it('xP-summa / hinta, vain status a', () => {
		const cheap = pl({ price: 4, md2: 4, md3: 4 }); // 2.0
		const dear = pl({ price: 10, md2: 8, md3: 8 }); // 1.6
		const hurt = pl({ price: 4, md2: 6, md3: 6, status: 'i' });
		const r = uclPicks([dear, cheap, hurt], META, 'value');
		expect(r.state === 'rows' && r.rows.map((x) => x.player.id)).toEqual([cheap.id, dear.id]);
		expect(r.state === 'rows' && r.rows[0].score).toBeCloseTo(2.0);
	});
	it('toimii myos mennyt deadline -tilassa (summa on eri kysymys kuin kapteeni)', () => {
		expect(uclPicks([pl()], { ...META, deadline_passed: true }, 'value').state).toBe('rows');
	});
	it('top 20 ja positio', () => {
		const many = Array.from({ length: 40 }, (_, i) => pl({ pos: i % 2 ? 'DEF' : 'MID' }));
		const r = uclPicks(many, META, 'value', { pos: 'DEF' });
		expect(r.state === 'rows' && r.rows.length).toBe(UCL_LIST_TOP);
		expect(r.state === 'rows' && r.rows.every((x) => x.player.pos === 'DEF')).toBe(true);
	});
});

describe('uclPicks differentials', () => {
	it(`omistus <= ${UCL_DIFF_MAX_OWNED} %, jarjestys summalla`, () => {
		const low = pl({ owned_pct: UCL_DIFF_MAX_OWNED, md2: 5, md3: 5 });
		const lower = pl({ owned_pct: 0, md2: 9, md3: 9 });
		const high = pl({ owned_pct: UCL_DIFF_MAX_OWNED + 1, md2: 20, md3: 20 });
		const r = uclPicks([low, high, lower], META, 'differentials');
		expect(r.state === 'rows' && r.rows.map((x) => x.player.id)).toEqual([lower.id, low.id]);
	});
});

describe('thin data', () => {
	it('piilossa oletuksena, luku kertoo montako nousisi listalle, kytkin tuo ne', () => {
		const thin = pl({ data_basis: 'uefa_matches', md2: 9 });
		const none = pl({ data_basis: 'no_history', md2: 8 });
		const ok = pl({ md2: 5 });
		const r = uclPicks([thin, none, ok], META, 'captain');
		expect(r.state === 'rows' && r.rows.map((x) => x.player.id)).toEqual([ok.id]);
		expect(r.state === 'rows' && r.hiddenThin).toBe(2);
		const all = uclPicks([thin, none, ok], META, 'captain', { includeThin: true });
		expect(all.state === 'rows' && all.rows.map((x) => x.player.id)).toEqual([thin.id, none.id, ok.id]);
		expect(all.state === 'rows' && all.hiddenThin).toBe(0);
	});
	it('piilotettu luku on 0 kun thin-rivi ei nousisi listalle', () => {
		const thin = pl({ data_basis: 'uefa_matches', owned_pct: 50 });
		const r = uclPicks([thin, pl({ owned_pct: 1 })], META, 'differentials');
		expect(r.state === 'rows' && r.hiddenThin).toBe(0);
	});
});

describe('tilat', () => {
	it('maskattu -> locked (kymmenikosta laskettu lista olisi vaara vastaus)', () => {
		for (const v of ['captain', 'value', 'differentials'] as const) {
			expect(uclPicks([pl()], { ...META, masked: true }, v).state).toBe('locked');
		}
	});
	it('sarjavaihe ohi tai tyhja -> unavailable', () => {
		expect(uclPicks([pl()], { ...META, available: false }, 'value').state).toBe('unavailable');
		expect(uclPicks([], META, 'value').state).toBe('unavailable');
		expect(uclPicks(null, META, 'value').state).toBe('unavailable');
	});
});

describe('kutsupaikka', () => {
	it('/ucl lukee listat uclPicksin kautta eika laske itse', async () => {
		const { readFileSync } = await import('node:fs');
		const { fileURLToPath } = await import('node:url');
		const src = readFileSync(fileURLToPath(new URL('../routes/ucl/+page.svelte', import.meta.url)), 'utf8');
		expect(src).toMatch(/uclPicks\(/);
		expect(src).not.toMatch(/owned_pct\s*<=/);
		expect(src).not.toMatch(/xp_horizon_total\s*\/\s*\w*\.?price/);
	});
});
