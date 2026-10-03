/**
 * uclSquad (UCL-LAAJENNUS vaiheet 5-7): saannot, paras XI, siirrot, chipit.
 * Synteettinen pooli: invariantit mitataan vaiheilla (maskattu, mennyt
 * deadline, chip-kielletty MD, vanhentunut artefakti), ei nykyhetkella.
 */
import { describe, expect, it } from 'vitest';
import {
	UCL_RULES,
	analyseSquad,
	bestXi,
	chipAdvice,
	horizonMatchdays,
	limitlessXi,
	squadBank,
	suggestTransfers,
	validateSquad,
	withXp,
	type UclSquadPlayer
} from './uclSquad';

const MDS = [2, 3, 4];
let nextId = 1;
function pl(pos: string, team: string, price: number, xp: number | number[], extra: Partial<UclSquadPlayer> = {}): UclSquadPlayer {
	const xs = Array.isArray(xp) ? xp : MDS.map(() => xp);
	return {
		id: nextId++,
		pos,
		team_short: team,
		price,
		status: 'a',
		data_basis: 'domestic_league',
		gameweeks: MDS.map((gw, i) => ({ gw, xp: xs[i] ?? 0 })),
		...extra
	};
}

/** Laillinen 15:n ryhma, arvo 15 * 6 = 90, eri seuroista (3 per seura). */
function squad(): UclSquadPlayer[] {
	const clubs = ['A1', 'A2', 'A3', 'A4', 'A5'];
	const out: UclSquadPlayer[] = [];
	const shape: [string, number][] = [['GKP', 2], ['DEF', 5], ['MID', 5], ['FWD', 3]];
	let k = 0;
	for (const [pos, n] of shape) for (let i = 0; i < n; i++) out.push(pl(pos, clubs[k++ % 5], 6, 3));
	return out;
}

describe('validateSquad', () => {
	it('laillinen ryhma: ei huomautuksia, pankki = 100 - arvo', () => {
		const s = squad();
		const v = validateSquad(s.map((p) => p.id), s);
		expect(v.issues).toEqual([]);
		expect(v.value).toBe(90);
		expect(squadBank(v.players)).toBe(10);
	});

	it('seurakatto 3, pelipaikkakiintiot, koko ja tuntematon id', () => {
		const s = squad();
		const fourth = pl('DEF', s[0].team_short, 4, 1);
		const ids = [...s.slice(0, 14).map((p) => p.id), fourth.id, 999999];
		const v = validateSquad(ids, [...s, fourth]);
		const kinds = v.issues.map((i) => i.kind).sort();
		expect(kinds).toContain('unknown');
		expect(kinds).toContain('position');
		expect(v.issues.some((i) => i.kind === 'club' && i.have === 4)).toBe(true);
	});

	it('budjetti: yli 100 ilman pankkia on virhe, kayttajan pankilla ei (hinnat nousevat MD3:sta)', () => {
		const s = squad().map((p) => ({ ...p, price: 7 }));
		expect(validateSquad(s.map((p) => p.id), s).issues.map((i) => i.kind)).toEqual(['budget']);
		expect(validateSquad(s.map((p) => p.id), s, 0.5).issues).toEqual([]);
	});
});

describe('bestXi', () => {
	it('muodostelma 1 GK / >=3 DEF / >=2 MID / >=1 FWD, kapteeni tuplaa', () => {
		const s = squad();
		// Hyokkaajat ja keskikentta vahvoja, puolustus heikko: minimit silti.
		s.filter((p) => p.pos === 'FWD').forEach((p) => (p.gameweeks = MDS.map((gw) => ({ gw, xp: 9 }))));
		s.filter((p) => p.pos === 'MID').forEach((p) => (p.gameweeks = MDS.map((gw) => ({ gw, xp: 7 }))));
		s.filter((p) => p.pos === 'DEF').forEach((p, i) => (p.gameweeks = MDS.map((gw) => ({ gw, xp: 1 + i * 0.1 }))));
		const xi = bestXi(s, 2);
		const pos = (q: string) => xi.ids.filter((id) => s.find((p) => p.id === id)!.pos === q).length;
		expect(xi.ids.length).toBe(UCL_RULES.xiSize);
		expect(pos('GKP')).toBe(1);
		expect(pos('DEF')).toBe(3);
		expect(pos('MID')).toBe(4);
		expect(pos('FWD')).toBe(3);
		const sum = xi.ids.reduce((t, id) => t + (s.find((p) => p.id === id)!.gameweeks![0].xp), 0);
		expect(xi.points).toBeCloseTo(sum + 9, 6);
	});

	it('puuttuva matchday-rivi = 0 xP (ei ottelua)', () => {
		const s = squad();
		const def = s.find((p) => p.pos === 'DEF')!;
		def.gameweeks = [];
		expect(bestXi(s, 2).ids).not.toContain(def.id);
	});
});

describe('horizonMatchdays', () => {
	it('lukee numerot riveilta, ei sarjavaiheen jalkeisia', () => {
		const p = pl('MID', 'X', 5, 1);
		p.gameweeks = [{ gw: 8, xp: 1 }, { gw: 7, xp: 1 }, { gw: 9, xp: 1 }];
		expect(horizonMatchdays([p])).toEqual([7, 8]);
	});
});

describe('suggestTransfers', () => {
	it('loytaa selvan parannuksen, laskee hitit ilmaisista siirroista', () => {
		const s = squad();
		const star = pl('FWD', 'B1', 7, 8);
		const r = suggestTransfers(s, [...s, star], squadBank(s), 1, MDS);
		expect(r.single?.in).toEqual([star.id]);
		expect(r.single?.hits).toBe(0);
		expect(r.single?.gain).toBeGreaterThan(0);
		const noFree = suggestTransfers(s, [...s, star], squadBank(s), 0, MDS);
		expect(noFree.single?.hits).toBe(1);
		expect(noFree.single?.net).toBeCloseTo(noFree.single!.gain - 4, 6);
	});

	it('pankki: liian kallis ei kelpaa', () => {
		const s = squad();
		const pricey = pl('FWD', 'B1', 6 + squadBank(s) + 0.1, 20);
		expect(suggestTransfers(s, [...s, pricey], squadBank(s), 2, MDS).single).toBeNull();
	});

	it('seurakatto: neljas samasta seurasta ei kelpaa', () => {
		const s = squad(); // 3 per seura; hyokkaajat seuroista A3, A4, A5
		// A1:lla ei ole hyokkaajaa -> A1-hyokkaajan osto nostaisi A1:n neljaan aina.
		const a1 = pl('FWD', 'A1', 5, 20);
		expect(suggestTransfers(s, [...s, a1], squadBank(s), 2, MDS).single).toBeNull();
		// A3:lla on hyokkaaja: laillinen vain kun ulos lahtee juuri se.
		const a3 = pl('FWD', 'A3', 5, 20);
		const r = suggestTransfers(s, [...s, a3], squadBank(s), 2, MDS);
		const a3fwd = s.find((p) => p.pos === 'FWD' && p.team_short === 'A3')!;
		expect(r.single?.out).toEqual([a3fwd.id]);
	});

	it('pari tarkistetaan PARINA: kumpikin yksin mahtuu pankkiin, yhdessa ei', () => {
		const s = squad(); // pankki 10
		const a = pl('FWD', 'B1', 6 + 8, 9); // +8
		const b = pl('MID', 'B2', 6 + 8, 9); // +8, yhteensa +16 > 10
		const r = suggestTransfers(s, [...s, a, b], squadBank(s), 2, MDS);
		expect(r.single).not.toBeNull();
		expect(r.double).toBeNull();
	});

	it('penkille jaava ostos ei ole parannus (pisteet XI:sta, ei pelaajan summasta)', () => {
		const s = squad();
		// Vain varamaalivahdin paikka: GK1 3.0, GK2 3.0 -> uusi GK 2.9 ei aloita.
		const gk = pl('GKP', 'B1', 4, 2.9);
		expect(suggestTransfers(s, [...s, gk], squadBank(s), 2, MDS).single).toBeNull();
	});

	it('thin data ja ei-saatavilla eivat ole ehdotuksia', () => {
		const s = squad();
		const thin = pl('FWD', 'B1', 5, 20, { data_basis: 'uefa_matches' });
		const out = pl('FWD', 'B2', 5, 20, { status: 'i' });
		expect(suggestTransfers(s, [...s, thin, out], squadBank(s), 2, MDS).single).toBeNull();
	});
});

describe('chipAdvice', () => {
	it('MD 1/9/11: chip ei ole pelattavissa', () => {
		const s = squad();
		for (const md of UCL_RULES.chipBlockedMatchdays) {
			expect(chipAdvice(s, s, 10, [md, md + 1])).toEqual({ state: 'blocked', md });
		}
	});

	it('Limitless noudattaa seurakattoa ja ei ole koskaan huonompi kuin oma XI', () => {
		const s = squad();
		const stars = [1, 2, 3, 4, 5].map(() => pl('FWD', 'ZZ', 15, 12));
		const xi = limitlessXi([...s, ...stars], 2);
		const all = [...s, ...stars];
		const zz = xi.ids.filter((id) => all.find((p) => p.id === id)!.team_short === 'ZZ').length;
		expect(zz).toBeLessThanOrEqual(3);
		const adv = chipAdvice(s, all, 10, MDS);
		expect(adv.state).toBe('rows');
		if (adv.state === 'rows') {
			for (const r of adv.limitless) expect(r.gain).toBeGreaterThanOrEqual(-1e-9);
			expect(adv.wildcard.gain).toBeGreaterThanOrEqual(0);
		}
	});
});

describe('analyseSquad: vaiheet (saanto 6a)', () => {
	const s = squad();
	const pool = s.map(({ gameweeks, data_basis, ...p }) => p); // pool ei kanna xP:ta
	const ids = s.map((p) => p.id);
	const meta = { available: true, masked: false, deadline_gameweek: 2, deadline_passed: false };

	it('valmis: XI + horisontti seuraavista MD:ista', () => {
		const a = analyseSquad(ids, pool, s, meta);
		expect(a.state).toBe('ready');
		if (a.state === 'ready') {
			expect(a.md).toBe(2);
			expect(a.mds).toEqual([2, 3, 4]);
		}
	});
	it('maskattu (ilmainen) -> locked, ei lukuja kymmenen karjen pohjalta', () => {
		expect(analyseSquad(ids, pool, s.slice(0, 10), { ...meta, masked: true }).state).toBe('locked');
	});
	it('mennyt deadline -> unavailable', () => {
		expect(analyseSquad(ids, pool, s, { ...meta, deadline_passed: true }).state).toBe('unavailable');
	});
	it('pudotuspelit (MD9+) -> unavailable, ei sarjavaiheen rajoja', () => {
		expect(analyseSquad(ids, pool, s, { ...meta, deadline_gameweek: 9 }).state).toBe('unavailable');
	});
	it('vanhentunut artefakti (xP alkaa myohemmasta MD:sta kuin deadline) -> unavailable', () => {
		const late = s.map((p) => ({ ...p, gameweeks: [{ gw: 3, xp: 1 }] }));
		expect(analyseSquad(ids, pool, late, meta).state).toBe('unavailable');
	});
	it('excluded-pelaaja (poolissa, ei xP-listalla) pysyy joukkueessa 0 xP:lla', () => {
		const a = analyseSquad(ids, pool, s.slice(1), meta);
		expect(a.state).toBe('ready');
		expect(withXp(pool, s.slice(1))[0].gameweeks).toEqual([]);
	});
	it('keskenerainen joukkue -> incomplete huomautuksineen', () => {
		const a = analyseSquad(ids.slice(0, 14), pool, s, meta);
		expect(a.state).toBe('incomplete');
	});
});
