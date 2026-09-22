/**
 * Portti: My teamin kentan kokoonpano ja otsikko (TeamPitchManager), pariteetti
 * mobiilin lib/pitchLineup.test.ts:n kanssa (22.9.2026).
 *
 * M1: tulostila asetteli GW5:n pisteet `in_xi`:n eli MALLIN XI:n mukaan.
 * Mitattu FPL:sta, entry 116920 GW5: Gonzalo (569) aloitti ja sai 2 p mutta
 * oli kentalla penkilla, Thomas (173) oli penkilla ja sai 9 p mutta oli
 * kentalla avauksessa, Haaland (C) nakyi 6:na kun FPL nayttaa 12, ja kentan
 * summa oli 41 eika FPL:n 40. Ilmaispinnan otsikko oli "Starting XI".
 * M2: mallin XI (xP-tila) sai saman otsikon "Starting XI".
 *
 * Saanto 6a kohta 3: invariantti ajetaan synteettisilla vaiheilla (ratkennut
 * kierros + entry, Bench Boost, Triple Captain, xP-tila, ei ratkennutta
 * kierrosta, draft ilman entrya), ei vain tassa kauden hetkessa.
 *
 * Muisti "testi kutsuu funktiota, ei kutsupaikkaa": puhtaan funktion testi on
 * vihrea vaikka kentta lakkaisi kutsumasta sita. Siksi lopussa on
 * KUTSUPAIKKA-portti joka lukee TeamPitchManager.svelten, RateTeam.svelten ja
 * SquadHeaderRow.svelten, ja erotteleva fikstuuri joka todistaa etta portti
 * kaatuu kun kutsupaikka palautetaan lukemaan `in_xi`:ta.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { LastFinishedGw, RatedPlayer } from './fantasyTools';
import { settledGwReadable } from './luck';
import {
	modelCaptainFor,
	modelCaptainOf,
	pitchLineup,
	pitchTitle,
	armbandLabel,
	hitLabel,
	settledCardNumbers,
	settledFactor,
	type ModelCaptain,
	type SettledPick,
	type WhatIfPlan
} from './pitchLineup';
import { blankComments, codeLines } from './sourceScan';
import { declaredRange, xpHorizon, type HorizonMeta } from './xpHorizon';

// ---------------------------------------------------------------------------
// Fikstuuri: TUOTANNON vastaus 22.9 (curl "https://api.goaliq.app/api/
// fantasy/rate-team?entry=116920"), ei keksitty. `team.players[].in_xi` =
// mallin XI, `last_finished.players` = FPL:n omat GW5-picksit kertoimineen.
// meta: gw 6, picks_gw 5, horizon_gw 6, horizon_total_from 6,
// horizon_total_gw 6. last_finished: points 40, xp 58.58, points_on_bench 12.
// ---------------------------------------------------------------------------

/** [id, nimi, joukkue, pos, in_xi (malli), is_captain (rate-team)] */
const TEAM: [number, string, string, RatedPlayer['pos'], boolean, boolean][] = [
	[572, 'Tzolakis', 'HUL', 'GKP', true, false],
	[388, 'Guéhi', 'MCI', 'DEF', true, false],
	[8, 'Calafiori', 'ARS', 'DEF', true, false],
	[115, 'De Cuyper', 'BHA', 'DEF', true, false],
	[4, 'Gabriel', 'ARS', 'DEF', true, false],
	[68, 'Tavernier', 'BOU', 'MID', true, false],
	[426, 'B.Fernandes', 'MUN', 'MID', true, false],
	[427, 'Mbeumo', 'MUN', 'MID', true, false],
	[569, 'Gonzalo', 'FUL', 'FWD', false, false],
	[411, 'Haaland', 'MCI', 'FWD', true, true],
	[346, 'Calvert-Lewin', 'LEE', 'FWD', true, false],
	[171, 'Dovin', 'COV', 'GKP', false, false],
	[173, 'Thomas', 'COV', 'DEF', true, false],
	[290, 'Slater', 'HUL', 'MID', false, false],
	[51, 'George Hemmings', 'AVL', 'MID', false, false]
];
const PLAYERS: RatedPlayer[] = TEAM.map(([id, web_name, team_short, pos, in_xi, is_captain]) => ({
	id,
	web_name,
	team_short,
	pos,
	price: 5,
	xp_per_gw: 5,
	xp_horizon_total: 30,
	in_xi,
	is_captain
}));

/** [id, multiplier, C, V, points, xp_frozen] FPL:n pick-jarjestyksessa. */
type PickRow = [number, number, boolean, boolean, number | null, number | null];
const GW5: PickRow[] = [
	[572, 1, false, false, 6, 4.1],
	[388, 1, false, false, 4, 5.49],
	[8, 1, false, false, 1, 4.25],
	[115, 1, false, false, 6, 3.16],
	[4, 1, false, false, 1, 4.82],
	[68, 1, false, false, 2, 4.62],
	[426, 1, false, true, 2, 5.23],
	[427, 1, false, false, 2, 4.64],
	[569, 1, false, false, 2, 4.18],
	[411, 2, true, false, 6, 6.51],
	[346, 1, false, false, 2, 5.07],
	[171, 0, false, false, null, null],
	[173, 0, false, false, 9, 4.09],
	[290, 0, false, false, 2, 3.44],
	[51, 0, false, false, 1, 2.62]
];

function picks(rows: PickRow[]): SettledPick[] {
	const byId = new Map(PLAYERS.map((p) => [p.id, p]));
	return rows.map(([id, multiplier, is_captain, is_vice_captain, points, xp_frozen]) => ({
		id,
		web_name: byId.get(id)?.web_name ?? null,
		team_short: byId.get(id)?.team_short ?? null,
		pos: byId.get(id)?.pos ?? null,
		multiplier,
		is_captain,
		is_vice_captain,
		points,
		xp_frozen
	}));
}

/** FPL:n oma luku samalla saannolla kuin entry_history.points: kerroin mukana. */
function fplPoints(ps: SettledPick[]): number {
	return ps.reduce((s, r) => s + (r.multiplier > 0 ? (r.points ?? 0) * r.multiplier : 0), 0);
}
function fplFrozen(ps: SettledPick[]): number {
	return ps.reduce((s, r) => s + (r.multiplier > 0 ? (r.xp_frozen ?? 0) * r.multiplier : 0), 0);
}

function lf(ps: SettledPick[], over: Partial<LastFinishedGw> = {}): LastFinishedGw {
	return {
		gw: 5,
		players: ps,
		points: fplPoints(ps),
		points_net: fplPoints(ps),
		transfer_cost: 0,
		points_on_bench: ps.reduce((s, r) => s + (r.multiplier === 0 ? (r.points ?? 0) : 0), 0),
		chip: null,
		average_entry_score: 48,
		manager_name: 'GoalIQ App',
		team_name: "GoalIQ's Team",
		overall_rank: 2241907,
		rank_change: -689779,
		biggest_swing: null,
		model_points: null,
		vs_model: null,
		xp: Math.round(fplFrozen(ps) * 100) / 100,
		diff: null,
		complete: true,
		frozen_at: '2026-09-17T12:18:33Z',
		deadline: '2026-09-18T17:30:00Z',
		...over
	};
}

const PROD_LF = lf(picks(GW5));
const META: HorizonMeta = { horizon_gw: 6, horizon_total_from: 6, horizon_total_gw: 6 };
/** Tuotanto 22.9: `captain.pick` = B.Fernandes (426, gw_xp 6.75),
 *  `meta.captain_gw` = 6. Rivin `is_captain` on silti Haalandilla (kayttajan
 *  GW5-kapteeni, backendin effective_captain). */
const PROD_CAPTAIN: ModelCaptain = modelCaptainOf({
	captain: { pick: { id: 426 } },
	meta: { captain_gw: 6 }
});

/** Premiumin what-if-alkutila TASAN kuten TeamPitchManagerin reset-efekti:
 *  XI `in_xi`:sta, kapteeni `is_captain`, vara ei ole. */
function initialPlan(players: RatedPlayer[] = PLAYERS): WhatIfPlan {
	return {
		xiIds: players.filter((p) => p.in_xi).map((p) => p.id),
		captainId: players.find((p) => p.is_captain)?.id ?? null,
		viceId: null
	};
}

interface Cell {
	id: number;
	name: string;
	actual: number;
	xp: number;
	diff: number;
}

/**
 * Mita kentta piirtaa, SAMALLA polulla kuin TeamPitchManager: ehto
 * (`settledGwReadable(premium ? selGw : null, luckGw, luckSameSquad)`) ->
 * toteumakartta -> kokoonpano -> solu kertoimella (`settledOf`) -> otsikko.
 * Kutsupaikkaportti alla varmistaa etta komponentti kayttaa samoja lausekkeita.
 */
function pitchAs(o: {
	premium: boolean;
	/** Valittu kierros. Ilmaispinnalla efekti asettaa sen `defaultGw`:hen. */
	selGw: number | null;
	lastFinished: LastFinishedGw | null;
	picksGw: number | null;
	players?: RatedPlayer[];
	plan?: WhatIfPlan;
	meta?: HorizonMeta | null;
	modelCaptain?: ModelCaptain | null;
}) {
	const players = o.players ?? PLAYERS;
	const lastFinished = o.lastFinished;
	const luckGw = lastFinished?.gw ?? null;
	const luckSameSquad = lastFinished != null && o.picksGw != null && o.picksGw === lastFinished.gw;
	const readable = settledGwReadable(o.premium ? o.selGw : null, luckGw, luckSameSquad);
	const settledView = lastFinished != null && readable;
	const luckById = new Map<number, { points: number | null; xp: number | null }>();
	if (lastFinished && readable)
		for (const r of lastFinished.players) luckById.set(r.id, { points: r.points, xp: r.xp_frozen });
	const lineup = pitchLineup(
		players,
		settledView ? (lastFinished?.players ?? null) : null,
		o.premium ? (o.plan ?? initialPlan(players)) : null,
		modelCaptainFor(o.modelCaptain === undefined ? PROD_CAPTAIN : o.modelCaptain, o.selGw)
	);
	const cell = (p: RatedPlayer): Cell | null => {
		const r = luckById.get(p.id);
		if (!r || typeof r.points !== 'number' || typeof r.xp !== 'number') return null;
		const f = lineup.factor(p.id);
		return { id: p.id, name: p.web_name, actual: r.points * f, xp: r.xp * f, diff: (r.points - r.xp) * f };
	};
	const xiCells = lineup.xi.map(cell).filter((c): c is Cell => c != null);
	const benchCells = lineup.bench.map(cell).filter((c): c is Cell => c != null);
	const horizon = o.meta === undefined ? xpHorizon(META) : xpHorizon(o.meta);
	return {
		lineup,
		xiIds: lineup.xi.map((p) => p.id),
		benchIds: lineup.bench.map((p) => p.id),
		xiCells,
		benchCells,
		points: xiCells.reduce((s, c) => s + c.actual, 0),
		frozen: xiCells.reduce((s, c) => s + c.xp, 0),
		title: pitchTitle(lineup.source, { horizon, settledGw: luckGw, gw: o.selGw }),
		canEdit: o.premium && lineup.source === 'plan'
	};
}

const ids = (rows: PickRow[], pred: (m: number) => boolean) =>
	rows.filter((r) => pred(r[1])).map((r) => r[0]);

// ---------------------------------------------------------------------------
describe('erotteleva fikstuuri: tuotannon vastaus 22.9', () => {
	it('vanha polku (kentta in_xi:sta) antaa 41, FPL ja uusi polku 40', () => {
		const old = pitchLineup(PLAYERS, null, initialPlan(), null);
		const byId = new Map(PROD_LF.players.map((r) => [r.id, r]));
		const oldSum = old.xi.reduce((s, p) => s + (byId.get(p.id)?.points ?? 0), 0);
		expect(oldSum).toBe(41);
		expect(PROD_LF.points).toBe(40);
		expect(pitchAs({ premium: false, selGw: 6, lastFinished: PROD_LF, picksGw: 5 }).points).toBe(40);
		// Ero on juuri mitattu: Thomas (9) avauksessa ja Gonzalo (2) penkilla,
		// Haaland 6 eika 12. 41 = 40 - 2 + 9 - 6.
		expect(old.xi.map((p) => p.id)).toContain(173);
		expect(old.xi.map((p) => p.id)).not.toContain(569);
	});
});

// ---------------------------------------------------------------------------
describe('vaihe: ratkennut kierros + entry (tulostila)', () => {
	const variants = [
		{ name: 'ilmainen (ei GW-valitsinta, picksit GW5:lta)', premium: false, selGw: 6 },
		{ name: 'Premium, tulos-chip GW5 valittuna', premium: true, selGw: 5 }
	];
	for (const v of variants) {
		it(`${v.name}: XI ja penkki FPL:n pickseista, summa = last_finished.points`, () => {
			const r = pitchAs({ premium: v.premium, selGw: v.selGw, lastFinished: PROD_LF, picksGw: 5 });
			expect(r.lineup.source).toBe('settled');
			expect(r.xiIds).toEqual(ids(GW5, (m) => m > 0));
			expect(r.benchIds).toEqual(ids(GW5, (m) => m === 0));
			expect(r.xiIds).toContain(569); // Gonzalo aloitti
			expect(r.benchIds).toContain(173); // Thomas penkilla
			expect(r.points).toBe(40);
			expect(r.points).toBe(PROD_LF.points);
			expect(r.frozen.toFixed(1)).toBe('58.6');
			expect(Math.abs(r.frozen - (PROD_LF.xp as number))).toBeLessThan(0.005);
			const haaland = r.xiCells.find((c) => c.id === 411)!;
			expect(haaland.actual).toBe(12);
			expect(haaland.xp.toFixed(1)).toBe('13.0');
			expect(haaland.diff.toFixed(1)).toBe('-1.0');
			const thomas = r.benchCells.find((c) => c.id === 173)!;
			expect(thomas.actual).toBe(9);
			expect(r.benchCells.reduce((s, c) => s + c.actual, 0)).toBe(PROD_LF.points_on_bench);
			expect(r.lineup.captainId).toBe(411);
			expect(r.lineup.viceId).toBe(426);
			expect(r.title).toBe('Your team · GW5 result');
			expect(r.canEdit).toBe(false);
		});
	}
});

describe('vaihe: Bench Boost', () => {
	it('realistinen (kapteeni 2, muut 1): 15 kentalla, penkki tyhja, summa = FPL', () => {
		const rows = GW5.map(([id, m, c, v, pts, xp]) => [id, m === 0 ? 1 : m, c, v, pts, xp] as PickRow);
		const L = lf(picks(rows), { chip: 'bboost' });
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: L, picksGw: 5 });
		expect(r.lineup.source).toBe('settled');
		expect(r.xiIds).toHaveLength(15);
		expect(r.benchIds).toHaveLength(0);
		expect(r.points).toBe(L.points);
		expect(r.points).toBe(40 + 12);
	});
	it('kirjaimellisesti 15 x multiplier 1: jokainen pelaaja kertoimella 1', () => {
		const rows = GW5.map(([id, , , v, pts, xp]) => [id, 1, false, v, pts, xp] as PickRow);
		const L = lf(picks(rows), { chip: 'bboost' });
		const r = pitchAs({ premium: true, selGw: 5, lastFinished: L, picksGw: 5 });
		expect(r.xiIds).toHaveLength(15);
		expect(r.benchIds).toHaveLength(0);
		expect(r.points).toBe(L.points);
		expect(r.xiCells.find((c) => c.id === 411)!.actual).toBe(6);
		expect(r.lineup.captainId).toBeNull();
	});
});

describe('vaihe: Triple Captain', () => {
	it('multiplier 3: Haaland 18 / 19.53, summa 46 = FPL', () => {
		const rows = GW5.map(([id, m, c, v, pts, xp]) => [id, id === 411 ? 3 : m, c, v, pts, xp] as PickRow);
		const L = lf(picks(rows), { chip: '3xc' });
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: L, picksGw: 5 });
		const h = r.xiCells.find((c) => c.id === 411)!;
		expect(h.actual).toBe(18);
		expect(h.xp.toFixed(2)).toBe('19.53');
		expect(r.points).toBe(46);
		expect(r.points).toBe(L.points);
	});
});

describe('vaihe: xP-tila (ei tulostilaa)', () => {
	it('Premium, GW6-chip: what-if (alkutila mallin XI), ei otsikkoa, muokattava', () => {
		const r = pitchAs({ premium: true, selGw: 6, lastFinished: PROD_LF, picksGw: 5 });
		expect(r.lineup.source).toBe('plan');
		expect(r.xiIds.sort()).toEqual(PLAYERS.filter((p) => p.in_xi).map((p) => p.id).sort());
		expect(r.xiCells).toHaveLength(0); // GW5:n luvut eivat vuoda GW6:een
		expect(r.title).toBeNull();
		expect(r.canEdit).toBe(true);
	});
	it('Premium what-if seuraa muokkausta (vaihto + kapteeni), ei in_xi:ta', () => {
		const plan: WhatIfPlan = {
			xiIds: initialPlan().xiIds.map((id) => (id === 173 ? 290 : id)),
			captainId: 426,
			viceId: 411
		};
		const r = pitchAs({ premium: true, selGw: 6, lastFinished: PROD_LF, picksGw: 5, plan });
		expect(r.xiIds).toContain(290);
		expect(r.xiIds).not.toContain(173);
		expect(r.lineup.captainId).toBe(426);
		expect(r.lineup.viceId).toBe(411);
	});
	it('ilmainen deadlinen jalkeen (picksit GW6, ratkennut GW5): mallin XI ja mallin otsikko', () => {
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: PROD_LF, picksGw: 6 });
		expect(r.lineup.source).toBe('model');
		expect(r.xiIds).toEqual(PLAYERS.filter((p) => p.in_xi).map((p) => p.id));
		expect(r.xiCells).toHaveLength(0);
		expect(r.title).toBe("Model's XI from your 15, picked on GW6-GW11 xP · GW6");
		expect(r.canEdit).toBe(false);
	});
});

describe('mallin XI:n kapteeni: mallin kutsu, ei players[].is_captain', () => {
	it('fikstuuri on erotteleva: is_captain on eri pelaajalla kuin mallin kutsu', () => {
		expect(PLAYERS.find((p) => p.is_captain)?.id).toBe(411);
		expect(PROD_CAPTAIN).toEqual({ id: 426, gw: 6 });
	});
	it('mallin XI (ilmainen, deadlinen jalkeen): C = captain.pick (B.Fernandes), ei Haaland', () => {
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: PROD_LF, picksGw: 6 });
		expect(r.lineup.source).toBe('model');
		expect(r.lineup.captainId).toBe(426);
		expect(r.lineup.captainId).not.toBe(PLAYERS.find((p) => p.is_captain)?.id);
		expect(r.lineup.viceId).toBeNull();
	});
	it('draft ja ei ratkennutta kierrosta: sama saanto', () => {
		for (const picksGw of [null, 5]) {
			const r = pitchAs({ premium: false, selGw: 6, lastFinished: null, picksGw });
			expect(r.lineup.captainId).toBe(426);
		}
	});
	it('kutsun kierros eri kuin kentan (kesken kierroksen kutsu koskee seuraavaa): ei C:ta', () => {
		const r = pitchAs({
			premium: false,
			selGw: 6,
			lastFinished: null,
			picksGw: null,
			modelCaptain: { id: 426, gw: 7 }
		});
		expect(r.lineup.captainId).toBeNull();
	});
	it('kutsu puuttuu (vanha API) tai kierros tuntematon: ei C:ta, ei is_captain-varahaaraa', () => {
		for (const mc of [null, { id: null, gw: 6 }, { id: 426, gw: null }]) {
			const r = pitchAs({ premium: false, selGw: 6, lastFinished: null, picksGw: null, modelCaptain: mc });
			expect(r.lineup.captainId).toBeNull();
		}
		expect(pitchAs({ premium: false, selGw: null, lastFinished: null, picksGw: null }).lineup.captainId).toBeNull();
	});
	it('kutsu joka ei ole mallin XI:ssa: ei C:ta', () => {
		const r = pitchAs({
			premium: false,
			selGw: 6,
			lastFinished: null,
			picksGw: null,
			modelCaptain: { id: 569, gw: 6 } // Gonzalo, mallin penkilla
		});
		expect(r.lineup.captainId).toBeNull();
	});
	it('tulostila: C/V FPL:n pickseista, ei mallin kutsusta', () => {
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: PROD_LF, picksGw: 5 });
		expect(r.lineup.captainId).toBe(411);
		expect(r.lineup.viceId).toBe(426);
	});
	it('modelCaptainOf lukee captain.pick.id:n ja meta.captain_gw:n, ei muuta', () => {
		expect(modelCaptainOf({ captain: { pick: { id: 426 } }, meta: { captain_gw: 6 } })).toEqual({
			id: 426,
			gw: 6
		});
		expect(modelCaptainOf({})).toEqual({ id: null, gw: null });
		expect(modelCaptainOf({ captain: null, meta: null })).toEqual({ id: null, gw: null });
	});
});

describe('vaihe: ei ratkennutta kierrosta (last_finished null)', () => {
	it('ilmainen: mallin XI, mallin otsikko', () => {
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: null, picksGw: 5 });
		expect(r.lineup.source).toBe('model');
		expect(r.title).toBe("Model's XI from your 15, picked on GW6-GW11 xP · GW6");
	});
	it('Premium: what-if, ei tulostilaa', () => {
		const r = pitchAs({ premium: true, selGw: 6, lastFinished: null, picksGw: 5 });
		expect(r.lineup.source).toBe('plan');
	});
	it('picksit ilman yhtaan multiplier > 0 -rivia: ei tyhjaa kenttaa', () => {
		const rows = GW5.map(([id, , c, v, pts, xp]) => [id, 0, c, v, pts, xp] as PickRow);
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: lf(picks(rows)), picksGw: 5 });
		expect(r.lineup.source).toBe('model');
		expect(r.xiIds).toHaveLength(11);
	});
});

describe('vaihe: draft ilman entrya (mode manual, last_finished null, picks_gw null)', () => {
	it('ilmainen: mallin XI, otsikko nimeaa ikkunan', () => {
		const r = pitchAs({ premium: false, selGw: 6, lastFinished: null, picksGw: null });
		expect(r.lineup.source).toBe('model');
		expect(r.title).toBe("Model's XI from your 15, picked on GW6-GW11 xP · GW6");
	});
	it('Premium: what-if', () => {
		expect(pitchAs({ premium: true, selGw: 6, lastFinished: null, picksGw: null }).lineup.source).toBe(
			'plan'
		);
	});
});

describe('Premiumin sovellettu siirto: GW5:n pelaaja ei ole enaa rungossa', () => {
	it('tulostila piirtaa pick-rivin, summa pysyy FPL:n lukuna', () => {
		const roster = PLAYERS.map((p) =>
			p.id === 569 ? { ...p, id: 999, web_name: 'Uusi', in_xi: false } : p
		);
		const r = pitchAs({ premium: true, selGw: 5, lastFinished: PROD_LF, picksGw: 5, players: roster });
		expect(r.xiIds).toContain(569);
		expect(r.xiIds).not.toContain(999);
		expect(r.lineup.xi.find((p) => p.id === 569)?.web_name).toBe('Gonzalo');
		expect(r.points).toBe(40);
	});
});

// ---------------------------------------------------------------------------
describe('otsikko: lahde ja ikkuna (M2)', () => {
	it('mallin lahde ei voi sanoa "Starting XI", FPL:n picksit eivat voi sanoa mallin XI', () => {
		const h = xpHorizon(META);
		for (const gw of [null, 6]) {
			const m = pitchTitle('model', { horizon: h, settledGw: 5, gw })!;
			expect(m.startsWith("Model's XI from your 15")).toBe(true);
			expect(m).not.toMatch(/Starting XI/);
			const s = pitchTitle('settled', { horizon: h, settledGw: 5, gw })!;
			expect(s.startsWith('Your team')).toBe(true);
			expect(s).not.toMatch(/Model/);
			// Tulostila EI ole "Starting XI": multiplier > 0 = automaattivaihtojen
			// jalkeinen XI (FPL entry 11/12 GW5), BB:ssa 15 pelaajaa.
			expect(s).not.toMatch(/Starting/);
		}
		expect(pitchTitle('plan', { horizon: h, settledGw: 5, gw: 6 })).toBeNull();
	});

	/** Horisonttivaiheet (sama metakenttasopimus kuin xpHorizon.test.ts). Otsikon
	 *  ikkuna on SAMA merkkijono kuin otsakerivin sulkeissa (declaredRange). */
	const PHASES: { name: string; meta: HorizonMeta | null; span: string | null; gw: number }[] = [
		{
			name: 'ennen deadlinea (tuotanto 22.9)',
			meta: { horizon_gw: 6, horizon_total_from: 6, horizon_total_gw: 6 },
			span: 'GW6-GW11',
			gw: 6
		},
		{
			name: 'kesken kierroksen (summa alkaa deadline-kierroksesta)',
			meta: { horizon_gw: 6, horizon_total_from: 7, horizon_total_gw: 5, next_gameweek: 6 },
			span: 'GW7-GW11',
			gw: 7
		},
		{
			name: 'vanha API (ei horizon_total_gw:ta): alkua ei julistettu',
			meta: { horizon_gw: 6, next_gameweek: 6 },
			span: null,
			gw: 6
		},
		{
			name: 'ei deadlinea (horizon_total_from puuttuu)',
			meta: { horizon_gw: 6, horizon_total_gw: 6, next_gameweek: 8 },
			span: null,
			gw: 8
		},
		{
			name: 'kausi lopussa (0 kierrosta)',
			meta: { horizon_gw: 0, horizon_total_from: 39, horizon_total_gw: 0 },
			span: null,
			gw: 38
		},
		{ name: 'ei metaa lainkaan', meta: null, span: null, gw: 6 }
	];
	for (const ph of PHASES) {
		it(`${ph.name}: otsikon ikkuna = otsakerivin ikkuna`, () => {
			const h = xpHorizon(ph.meta);
			expect(declaredRange(h)).toBe(ph.span);
			const t = pitchTitle('model', { horizon: h, settledGw: null, gw: ph.gw });
			expect(t).toBe(
				ph.span != null
					? `Model's XI from your 15, picked on ${ph.span} xP · GW${ph.gw}`
					: `Model's XI from your 15 · GW${ph.gw}`
			);
		});
	}

	it('ilman kierrosta (vanha API ilman gameweeks-riveja, selGw null): ei " · GW"-peraa', () => {
		expect(pitchTitle('model', { horizon: xpHorizon(META), settledGw: null, gw: null })).toBe(
			"Model's XI from your 15, picked on GW6-GW11 xP"
		);
	});

	it('copy: ei em dashia, ei kaarevia lainausmerkkeja, ei Pro-sanaa', () => {
		const all = [
			pitchTitle('model', { horizon: xpHorizon(META), settledGw: 5, gw: 6 }),
			pitchTitle('model', { horizon: xpHorizon(null), settledGw: 5, gw: 6 }),
			pitchTitle('settled', { horizon: null, settledGw: 5, gw: 6 }),
			pitchTitle('settled', { horizon: null, settledGw: null, gw: 6 })
		].join('\n');
		// Merkit koodipisteina, jotta tama tiedosto ei itse sisalla niita.
		const banned = new RegExp(
			'[' + [0x2014, 0x2013, 0x2018, 0x2019, 0x201c, 0x201d].map((c) => String.fromCharCode(c)).join('') + ']'
		);
		expect(all).not.toMatch(banned);
		expect(all).not.toMatch(/\bPro\b/);
	});
});

// ---------------------------------------------------------------------------
// KUTSUPAIKKA-portti
// ---------------------------------------------------------------------------
const readRaw = (rel: string) =>
	readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n');

const norm = (s: string) => s.replace(/\s+/g, ' ').trim();

/** `in_xi` saa esiintya TeamPitchManagerin KOODISSA vain naissa riveissa. Uusi
 *  rivi kaataa portin, ja kirjoittaja joutuu perustelemaan sen tahan. */
const IN_XI_ALLOWED: { line: string; reason: string }[] = [
	{
		line: 'xiIds = players.filter((p) => p.in_xi).map((p) => p.id);',
		reason:
			'Premiumin what-if-ALKUTILA (reset-efekti). Se on muokattava suunnitelma eika koskaan tulostilan kokoonpano: tulostila tulee pitchLineupin settled-haarasta.'
	},
	{
		line: 'const base = players.filter((p) => p.in_xi);',
		reason:
			'baselineXp: what-ifin "xP vs your loaded lineup" -vertailukohta on se mita editoriin ladattiin (alkutila). Ei kentan kokoonpano.'
	}
];

/** Ongelmat TeamPitchManagerin lahteessa. Oma funktio, jotta sama saanto
 *  ajetaan alla myos mutatoidulle lahteelle (erotteleva fikstuuri). */
function pitchCallSiteProblems(raw: string): string[] {
	const code = blankComments(raw);
	const flat = norm(code);
	const p: string[] = [];

	// 1. in_xi vain perustelluilla riveilla.
	for (const l of codeLines(raw)) {
		if (!/\bin_xi\b/.test(l.text)) continue;
		if (!IN_XI_ALLOWED.some((a) => a.line === l.text.trim()))
			p.push(`TeamPitchManager.svelte:${l.n}: in_xi ilman perustelua: ${l.text.trim()}`);
	}

	// 2. Tulostilan ehto: sama lukija ja samat argumentit kuin toteumakartalla.
	if (
		!flat.includes(
			'const settledView = $derived( lastFinished != null && settledGwReadable(premium ? selGw : null, luckGw, luckSameSquad) );'
		)
	)
		p.push('settledView ei ole settledGwReadable(premium ? selGw : null, luckGw, luckSameSquad)');

	// 3. Kokoonpano lukijalta: tulostilassa last_finished.players.
	if (
		!flat.includes(
			'const lineup = $derived( pitchLineup( players, settledView ? (lastFinished?.players ?? null) : null, premium ? { xiIds, captainId, viceId } : null, modelCaptainFor(modelCaptain, selGw) ) );'
		)
	)
		p.push(
			'lineup ei ole pitchLineup(players, settledView ? lastFinished.players : null, what-if, modelCaptainFor(modelCaptain, selGw))'
		);
	if (!/modelCaptain\?: ModelCaptain \| null;/.test(flat))
		p.push('modelCaptain-propin tyyppi ei ole ModelCaptain');

	// 4. Kentta ja penkki piirretaan lineupista.
	for (const need of [
		'const xi = $derived(lineup.xi);',
		'const bench = $derived(lineup.bench);',
		'const effCaptain = $derived(lineup.captainId);',
		'const effVice = $derived(lineup.viceId);',
		'POS_ORDER.map((pos) => xi.filter((p) => p.pos === pos))',
		'{#each rows as row, i (i)}',
		'{#each bench as p (p.id)}',
		'const f = lineup.factor(p.id);',
		'return { actual: r.points * f, xp: r.xp * f, diff: (r.points - r.xp) * f };'
	])
		if (!flat.includes(need)) p.push(`puuttuu: ${need}`);

	// 5. Otsikko lahteesta, ei literaalia markupissa.
	if (!flat.includes('pitchTitle(lineup.source, { horizon, settledGw: luckGw, gw: selGw })'))
		p.push('otsikko ei tule pitchTitle(lineup.source, ...):sta');
	if ((flat.match(/\{pitchHeading\}/g) ?? []).length < 2)
		p.push('ilmais- ja Premium-tulostilan otsikko ei renderoi pitchHeadingia');
	if (/>\s*(Starting XI|Your team)\s*</.test(code) || /Model's XI/.test(code))
		p.push('otsikkoliteraali markupissa: otsikon on tultava pitchTitlesta');

	// 6. Tulostilassa ei muokkausta (C/V ja vaihdot muuttaisivat nakymatonta what-ifia).
	if (!flat.includes("const canEdit = $derived(premium && lineup.source === 'plan');"))
		p.push('canEdit ei ole premium && lineup.source === plan');
	if ((flat.match(/disabled=\{!canEdit\}/g) ?? []).length < 2)
		p.push('XI- tai penkkipaita ei ole disabled={!canEdit}');
	if (/disabled=\{!premium\}/.test(flat)) p.push('paita on yha disabled={!premium}');
	if (!/function onPlayerClick\(id: number\) \{ if \(!canEdit\) return;/.test(flat))
		p.push('onPlayerClick ei vaadi canEditia');
	const fIdx = flat.indexOf('{#each FORMATIONS');
	const fGuard = flat.lastIndexOf('{#if canEdit}', fIdx);
	if (fIdx === -1 || fGuard === -1 || flat.lastIndexOf('{/if}', fIdx) > fGuard)
		p.push('muodostelmachipit eivat ole {#if canEdit} -lohkossa');
	const capIdx = flat.indexOf('Make captain');
	const capGuard = flat.lastIndexOf('{#if canEdit}', capIdx);
	if (capIdx === -1 || capGuard === -1 || capGuard < fIdx)
		p.push('Make captain / Make vice eivat ole {#if canEdit} -lohkossa');
	return p;
}

/** RateTeam antaa kentalle SAMAN ikkunan kuin saman slotin otsakeriville.
 *  Pari = kentta ja sita LAHIN edeltava SquadHeaderRow (slot A: data, slot B:
 *  dataB). Pelkka "jossain tiedostossa on xpHorizon(data.meta)" ei riita:
 *  vertailunakyman otsakerivi (eri lohko) tayttaisi sen, vaikka kentan oma
 *  otsakerivi olisi menettanyt ikkunansa (mutaatiotodiste 22.9). */
function rateTeamProblems(raw: string): string[] {
	const code = blankComments(raw);
	const p: string[] = [];
	let header: string | null = null;
	let pitches = 0;
	for (const m of code.matchAll(/<(SquadHeaderRow|TeamPitchManager)\b[\s\S]*?\/>/g)) {
		if (m[1] === 'SquadHeaderRow') {
			header = m[0];
			continue;
		}
		pitches += 1;
		const b = m[0];
		const v = /lastFinished=\{(\w+)\.last_finished/.exec(b)?.[1];
		if (!v) {
			p.push('TeamPitchManager-kutsu ilman lastFinished-propia');
			continue;
		}
		if (!norm(b).includes(`horizon={xpHorizon(${v}.meta)}`))
			p.push(`TeamPitchManager (${v}) ei saa horizon={xpHorizon(${v}.meta)}`);
		if (!norm(b).includes(`modelCaptain={modelCaptainOf(${v})}`))
			p.push(`TeamPitchManager (${v}) ei saa modelCaptain={modelCaptainOf(${v})}`);
		if (header == null) p.push(`TeamPitchManager (${v}): ei edeltavaa SquadHeaderRowta`);
		else if (!norm(header).includes(`horizon={xpHorizon(${v}.meta)}`))
			p.push(`SquadHeaderRow ennen kenttaa (${v}) ei lue samaa xpHorizon(${v}.meta)-ikkunaa`);
		header = null;
	}
	if (pitches < 2) p.push(`TeamPitchManager-kutsuja ${pitches}, odotettiin 2`);
	return p;
}

/** Otsakerivin sulkeiden ikkuna tulee declaredRangesta, ei horizon.rangesta. */
function headerProblems(raw: string): string[] {
	const flat = norm(blankComments(raw));
	const p: string[] = [];
	if (!flat.includes('{#if declaredRange(horizon)}Next {horizon?.count} GW'))
		p.push('SquadHeaderRow: ehto ei ole declaredRange(horizon)');
	if (!flat.includes('<span class="u">({declaredRange(horizon)})</span>'))
		p.push('SquadHeaderRow: sulkeiden ikkuna ei ole declaredRange(horizon)');
	if (/horizon\??\.range\b/.test(flat)) p.push('SquadHeaderRow lukee horizon.rangea suoraan');
	return p;
}

/** Lukija ei lue rungon `is_captain`ia lainkaan: settled-haara lukee pickin
 *  (`r.is_captain`), mallin haara mallin kutsun. */
function readerProblems(raw: string): string[] {
	return codeLines(raw)
		.filter((l) => /\b(?:p|player|x)\.is_captain\b|\.find\(\(\w+\) => \w+\.is_captain\)/.test(l.text) && !/\br\.is_captain\b/.test(l.text))
		.map((l) => `pitchLineup.ts:${l.n}: rungon is_captain: ${l.text.trim()}`);
}

/** Tulostilan solu ei nayta SEURAAVAN kierroksen lukua: otsikko sanoo "GW5
 *  result", joten GW6:n vastustaja tai GW6:n xP penkilla luettaisiin GW5:n
 *  lukuna (sama vikaluokka kuin 3.9 luckById). */
function settledCellProblems(raw: string): string[] {
	const flat = norm(blankComments(raw));
	const p: string[] = [];
	if (!flat.includes('if (resultMode || settledView) return null;'))
		p.push('oppOf: vastustajarivi ei katoa ilmaispinnan tulostilassa (settledView)');
	const b = flat.indexOf('{#each bench as p');
	const bench = b === -1 ? '' : flat.slice(b);
	if (
		!bench.includes(
			`{#if settledView} <span class="pxp" title="Projection frozen before the deadline" >{settledOf(p)?.xp.toFixed(1) ?? 'n/a'}</span > {:else} <span class="pxp">{xpOf(p).toFixed(1)}</span> {/if}`
		)
	)
		p.push('penkki: tulostilan ensimmainen luku ei ole ratkenneen kierroksen freeze');
	return p;
}

const PITCH = () => readRaw('./components/TeamPitchManager.svelte');

describe('KUTSUPAIKKA: TeamPitchManager lukee kokoonpanon lukijalta, ei in_xi:sta', () => {
	it('TeamPitchManager.svelte', () => {
		expect(pitchCallSiteProblems(PITCH())).toEqual([]);
	});
	it('IN_XI_ALLOWED ei vanhene: jokainen poikkeusrivi loytyy koodista sanatarkasti', () => {
		const lines = codeLines(PITCH()).map((l) => l.text.trim());
		for (const a of IN_XI_ALLOWED) expect(lines, a.reason).toContain(a.line);
	});
	it('RateTeam.svelte: kentta ja otsakerivi saavat saman ikkunan', () => {
		expect(rateTeamProblems(readRaw('./components/RateTeam.svelte'))).toEqual([]);
	});
	it('SquadHeaderRow.svelte: sulkeiden ikkuna declaredRangesta', () => {
		expect(headerProblems(readRaw('./components/SquadHeaderRow.svelte'))).toEqual([]);
	});
	it('pitchLineup.ts: lukija ei lue rungon is_captainia', () => {
		expect(readerProblems(readRaw('./pitchLineup.ts'))).toEqual([]);
	});
	it('tulostilan solu ei nayta seuraavan kierroksen vastustajaa eika xP:ta', () => {
		expect(settledCellProblems(PITCH())).toEqual([]);
	});
});

/** Erotteleva fikstuuri: jokainen mutaatio on muoto jolla vika palaisi. Portti
 *  EI saa olla vihrea yhdellekaan. Vaara haara oikeasti onnistuisi: jokainen
 *  mutatoitu lahde on validia Svelte-koodia. */
const MUTATIONS: { name: string; from: string; to: string }[] = [
	{
		name: 'tulostila ei anna pickseja lukijalle (kokoonpano aina in_xi/what-if)',
		from: 'settledView ? (lastFinished?.players ?? null) : null,',
		to: 'null,'
	},
	{
		name: 'kentan XI suoraan in_xi:sta',
		from: 'const xi = $derived(lineup.xi);',
		to: 'const xi = $derived(players.filter((p) => p.in_xi));'
	},
	{
		name: 'penkki suoraan in_xi:sta',
		from: 'const bench = $derived(lineup.bench);',
		to: 'const bench = $derived(players.filter((p) => !p.in_xi));'
	},
	{
		name: 'XI what-if-tilasta (vanha polku)',
		from: 'const xi = $derived(lineup.xi);',
		to: 'const xi = $derived(xiIds.map((id) => byId.get(id)).filter((p): p is RatedPlayer => !!p));'
	},
	{
		name: 'kerroin ohitetaan (Haaland 6)',
		from: 'const f = lineup.factor(p.id);',
		to: 'const f = 1;'
	},
	{
		name: 'kapteeni what-ifista',
		from: 'const effCaptain = $derived(lineup.captainId);',
		to: 'const effCaptain = $derived(captainId);'
	},
	{
		name: 'mallin XI:n kapteeni palaa is_captain-kenttaan',
		from: 'modelCaptainFor(modelCaptain, selGw)',
		to: '(players.find((p) => p.is_captain)?.id ?? null)'
	},
	{
		name: 'mallin kutsu ilman kierrostarkistusta',
		from: 'modelCaptainFor(modelCaptain, selGw)',
		to: '(modelCaptain?.id ?? null)'
	},
	{
		name: 'otsikko aina tulostilan',
		from: 'pitchTitle(lineup.source, { horizon, settledGw: luckGw, gw: selGw })',
		to: "pitchTitle('settled', { horizon, settledGw: luckGw, gw: selGw })"
	},
	{
		name: 'tulostilan ehto eri kuin toteumakartalla',
		from: 'settledGwReadable(premium ? selGw : null, luckGw, luckSameSquad)\n\t);',
		to: 'settledGwReadable(selGw, luckGw, luckSameSquad)\n\t);'
	},
	{
		name: 'muokkaus sallittu tulostilassa',
		from: "const canEdit = $derived(premium && lineup.source === 'plan');",
		to: 'const canEdit = $derived(premium);'
	}
];

describe('erotteleva fikstuuri: portti kaatuu kun kutsupaikka palautetaan', () => {
	for (const m of MUTATIONS) {
		it(m.name, () => {
			const src = PITCH();
			expect(src.includes(m.from), `mutaation lahtomuoto puuttuu: ${m.from}`).toBe(true);
			expect(pitchCallSiteProblems(src.replace(m.from, m.to)).length).toBeGreaterThan(0);
		});
	}
	it('RateTeam: kentta ilman ikkunaa kaataa portin', () => {
		const src = readRaw('./components/RateTeam.svelte');
		const from = 'horizon={xpHorizon(data.meta)}\n\t\tmodelCaptain={modelCaptainOf(data)}';
		expect(src.includes(from)).toBe(true);
		expect(
			rateTeamProblems(src.replace(from, 'modelCaptain={modelCaptainOf(data)}')).length
		).toBeGreaterThan(0);
		expect(
			rateTeamProblems(src.replace(from, 'horizon={xpHorizon(data.meta)}')).length
		).toBeGreaterThan(0);
	});
	it('RateTeam: kentan oman otsakerivin ikkuna pois kaataa portin (vertailun otsakerivi ei kelpaa)', () => {
		const src = readRaw('./components/RateTeam.svelte');
		const from = '\t\thorizon={xpHorizon(data.meta)}\n\t\tgw={data.meta.gw}';
		expect(src.includes(from)).toBe(true);
		expect(rateTeamProblems(src.replace(from, '\t\tgw={data.meta.gw}')).length).toBeGreaterThan(0);
	});
	it('lukija: mallin haaran kapteeni players.find(p => p.is_captain):sta kaataa portin', () => {
		const src = readRaw('./pitchLineup.ts');
		const from =
			'captainId: modelCaptainId != null && xiIds.has(modelCaptainId) ? modelCaptainId : null,';
		expect(src.includes(from)).toBe(true);
		expect(
			readerProblems(src.replace(from, 'captainId: players.find((p) => p.is_captain)?.id ?? null,'))
				.length
		).toBeGreaterThan(0);
	});
	it('tulostilan solu: vanha oppOf-ehto ja penkin GW6-xP kaatavat portin', () => {
		const src = PITCH();
		const opp = 'if (resultMode || settledView) return null;';
		const pxp = `{#if settledView}`;
		expect(src.includes(opp) && src.includes(pxp)).toBe(true);
		expect(settledCellProblems(src.replace(opp, 'if (resultMode) return null;')).length).toBeGreaterThan(0);
		const i = src.indexOf(pxp, src.indexOf('{#each bench as p'));
		const j = src.indexOf('{/if}', i) + '{/if}'.length;
		expect(
			settledCellProblems(src.slice(0, i) + '<span class="pxp">{xpOf(p).toFixed(1)}</span>' + src.slice(j))
				.length
		).toBeGreaterThan(0);
	});
	it('SquadHeaderRow: vanha horizon.range-muoto kaataa portin', () => {
		const src = readRaw('./components/SquadHeaderRow.svelte');
		expect(
			headerProblems(src.replace('({declaredRange(horizon)})', '({horizon?.range})')).length
		).toBeGreaterThan(0);
	});
});

// ---------------------------------------------------------------------------
// JAKOKORTTI (JAKOKORTTI-TULOSTILA-KERROIN, 22.9): kortin solut samalta
// kerroinlukijalta kuin kentta. Sama portti mobiilissa (goaliq-app
// lib/pitchLineup.test.ts).
// ---------------------------------------------------------------------------

/** Kortin XI-solujen pistesumma: sama suodatin kuin luckCardSpecissa. */
const cardSum = (L: LastFinishedGw) =>
	L.players.filter((r) => r.multiplier > 0).reduce((s, r) => s + (settledCardNumbers(r).pts ?? 0), 0);

describe('jakokortti: solut kertoimella, summa = FPL:n luku', () => {
	it('fikstuuri on EROTTELEVA: kertoimeton kortti summautuu 34:aan, ei 40:een', () => {
		const raw = PROD_LF.players.filter((r) => r.multiplier > 0).reduce((s, r) => s + (r.points ?? 0), 0);
		expect(raw).toBe(34);
		expect(PROD_LF.points).toBe(40);
	});
	const vaiheet: [string, LastFinishedGw, number][] = [
		['ratkennut kierros', PROD_LF, 40],
		[
			'Triple Captain',
			lf(picks(GW5.map(([id, m, c, v, pts, xp]) => [id, id === 411 ? 3 : m, c, v, pts, xp] as PickRow)), {
				chip: '3xc'
			}),
			46
		],
		[
			'Bench Boost',
			lf(picks(GW5.map(([id, m, c, v, pts, xp]) => [id, m === 0 ? 1 : m, c, v, pts, xp] as PickRow)), {
				chip: 'bboost'
			}),
			40 + 12
		]
	];
	for (const [vaihe, L, odotus] of vaiheet) {
		it(`vaihe ${vaihe}: XI-solujen summa = FPL (${odotus})`, () => {
			expect(L.points).toBe(odotus);
			expect(cardSum(L)).toBe(L.points);
		});
	}
	it('kapteenin solu 12 / 13.0 / -1.0, penkki omana lukunaan, puuttuva ei ole nolla', () => {
		const h = settledCardNumbers(PROD_LF.players.find((r) => r.id === 411)!);
		expect(h.pts).toBe(12);
		expect(h.xp!.toFixed(1)).toBe('13.0');
		expect(h.diff!.toFixed(1)).toBe('-1.0');
		expect(settledCardNumbers(PROD_LF.players.find((r) => r.id === 173)!).pts).toBe(9);
		expect(settledCardNumbers(PROD_LF.players.find((r) => r.id === 171)!)).toEqual({
			pts: null,
			xp: null,
			diff: null
		});
	});
	it('kortti ja kentta: sama kerroin jokaiselle pickille (yksi lukija)', () => {
		const lineup = pitchLineup(PLAYERS, PROD_LF.players, null, null);
		for (const r of PROD_LF.players) expect(lineup.factor(r.id)).toBe(settledFactor(r));
	});
	it('KUTSUPAIKKA: luckCardSpecin toCard lukee settledCardNumbersia eika laske itse', () => {
		const src = blankComments(readRaw('./components/TeamPitchManager.svelte'));
		const start = src.indexOf('function luckCardSpec()');
		expect(start).toBeGreaterThan(0);
		const a = src.indexOf('const toCard = ', start);
		const b = src.indexOf('const played = ', a);
		expect(a).toBeGreaterThan(start);
		expect(b).toBeGreaterThan(a);
		const body = src.slice(a, b);
		expect(body).toMatch(/settledCardNumbers\(r\)/);
		expect(body).not.toMatch(/r\.points\s*-\s*r\.xp_frozen/);
		expect(body).not.toMatch(/r\.xp_frozen\.toFixed|String\(r\.points\)/);
	});
});

describe('jakokortti: kerroin legendiin, hit alaotsikkoon (julkaisutarkistaja 22.9 k2)', () => {
	const played = (L: LastFinishedGw) => L.players.filter((r) => r.multiplier > 0);
	it('C x2, TC x3, varakapteeni nousi, ei kerrointa', () => {
		expect(armbandLabel(played(PROD_LF))).toBe('C = captain x2');
		const tc = lf(picks(GW5.map(([id, m, c, v, pts, xp]) => [id, id === 411 ? 3 : m, c, v, pts, xp] as PickRow)));
		expect(armbandLabel(played(tc))).toBe('C = captain x3');
		const vice = lf(
			picks(
				GW5.map(([id, m, c, v, pts, xp]) => [id, id === 411 ? 0 : id === 426 ? 2 : m, c, v, pts, xp] as PickRow)
			)
		);
		expect(armbandLabel(played(vice))).toBe('V = vice-captain x2');
		const bb1 = lf(picks(GW5.map(([id, , , v, pts, xp]) => [id, 1, false, v, pts, xp] as PickRow)));
		expect(armbandLabel(played(bb1))).toBeNull();
	});
	it('vaihe hit-viikko: solut brutto 40, otsikko netto 36, ero "-4 hit"', () => {
		const hit = lf(picks(GW5), { transfer_cost: 4, points_net: 36 });
		expect(cardSum(hit)).toBe(40);
		expect(cardSum(hit) - hit.points_net!).toBe(4);
		expect(hitLabel(hit.transfer_cost)).toBe('-4 hit');
		expect(hitLabel(0)).toBeNull();
		expect(hitLabel(null)).toBeNull();
	});
});
