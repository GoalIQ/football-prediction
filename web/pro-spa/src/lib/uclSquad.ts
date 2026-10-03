/**
 * UCL Fantasy -oma joukkue: validointi, paras XI, siirrot ja chipit
 * (UCL-LAAJENNUS-FPL-TYYLIIN vaiheet 5-7, 3.10.2026).
 *
 * YKSI LUKIJA: /ucl#my-team ei laske mitaan itse, ja mobiilin
 * `lib/uclSquad.ts` on taman sanatarkka kopio (sama testisarja).
 * Spec: goaliq-app/cos-reports/ucl-laajennus-spec.md (vaiheet 5-7).
 *
 * Joukkue syotetaan kasin `pool`-listasta. Sita EI haeta UEFAlta: UEFAn
 * kayttoehdot 6.2 kieltavat skriptikeruun (Villen paatos 3.10).
 *
 * Mika voi vaihtua alla (saanto 6a) ja miten lukija torjuu sen:
 *   - matchday: horisontti luetaan xP-rivien `gameweeks`-numeroista
 *     (`horizonMatchdays`), ei oleteta "seuraavat kolme". Mennyt deadline
 *     -> ei analyysia, koska lukittua kierrosta ei esiteta tulevana.
 *   - tilaus: maskattu vastaus on vain kymmenen karki, joten siita laskettu
 *     paras XI tai siirto olisi vaara vastaus -> `locked`.
 *   - sarjan vaihe: seurakatto ja budjetti ovat sarjavaiheen arvoja; MD9+
 *     (pudotuspelit) -> `unavailable` eika vaaria rajoja.
 *   - hinta: hinnat muuttuvat MD3:sta alkaen, joten pankki on kayttajan
 *     syote kun joukkueen arvo ylittaa budjetin.
 */

/** UEFAn saantoartikkeli "UEFA Champions League Fantasy Football rules
 *  2026/27" (last updated 1.6.2026), luettu 3.10. Sarjavaiheen arvot. */
export const UCL_RULES = {
	squadSize: 15,
	quota: { GKP: 2, DEF: 5, MID: 5, FWD: 3 } as Record<UclSquadPos, number>,
	budget: 100,
	clubMax: 3,
	xiMin: { GKP: 1, DEF: 3, MID: 2, FWD: 1 } as Record<UclSquadPos, number>,
	xiMax: { GKP: 1, DEF: 5, MID: 5, FWD: 3 } as Record<UclSquadPos, number>,
	xiSize: 11,
	freePerMatchday: 2,
	freeMax: 3,
	hit: 4,
	chipBlockedMatchdays: [1, 9, 11] as readonly number[],
	leaguePhaseLastMatchday: 8
} as const;

export type UclSquadPos = 'GKP' | 'DEF' | 'MID' | 'FWD';
export const UCL_SQUAD_POSITIONS: readonly UclSquadPos[] = ['GKP', 'DEF', 'MID', 'FWD'];

/** Rivi `pool`-listasta (ilmainen) tai xP-listasta (Premium). */
export interface UclSquadPlayer {
	id: number;
	pos: string;
	price: number;
	team_short: string;
	web_name?: string;
	status?: string;
	data_basis?: string;
	gameweeks?: { gw: number; xp: number }[];
}

export type UclSquadIssue =
	| { kind: 'size'; have: number }
	| { kind: 'position'; pos: UclSquadPos; have: number; need: number }
	| { kind: 'club'; club: string; have: number }
	| { kind: 'budget'; value: number }
	| { kind: 'unknown'; ids: number[] };

const round1 = (x: number) => Math.round(x * 10) / 10;

export function squadValue(players: readonly UclSquadPlayer[]): number {
	return round1(players.reduce((s, p) => s + (Number.isFinite(p.price) ? p.price : 0), 0));
}

/** Pankki: kayttajan syote voittaa; muuten budjetti - arvo (ei negatiivinen). */
export function squadBank(players: readonly UclSquadPlayer[], bank?: number | null): number {
	if (typeof bank === 'number' && Number.isFinite(bank) && bank >= 0) return round1(bank);
	return Math.max(0, round1(UCL_RULES.budget - squadValue(players)));
}

/**
 * Tarkistaa joukkueen. `ids` on kayttajan valinta, `pool` kaikki pelaajat.
 * Budjettivirhe vain kun arvo ylittaa budjetin EIKA kayttaja ole antanut
 * pankkia: MD3:sta alkaen nousseet hinnat voivat laillisesti ylittaa sen.
 */
export function validateSquad(
	ids: readonly number[],
	pool: readonly UclSquadPlayer[],
	bank?: number | null
): { players: UclSquadPlayer[]; issues: UclSquadIssue[]; value: number } {
	const byId = new Map(pool.map((p) => [p.id, p]));
	const unique = [...new Set(ids)];
	const players = unique.map((id) => byId.get(id)).filter((p): p is UclSquadPlayer => !!p);
	const issues: UclSquadIssue[] = [];
	const missing = unique.filter((id) => !byId.has(id));
	if (missing.length) issues.push({ kind: 'unknown', ids: missing });
	if (players.length !== UCL_RULES.squadSize) issues.push({ kind: 'size', have: players.length });
	for (const pos of UCL_SQUAD_POSITIONS) {
		const have = players.filter((p) => p.pos === pos).length;
		if (have !== UCL_RULES.quota[pos]) issues.push({ kind: 'position', pos, have, need: UCL_RULES.quota[pos] });
	}
	const clubs = new Map<string, number>();
	for (const p of players) clubs.set(p.team_short, (clubs.get(p.team_short) ?? 0) + 1);
	for (const [club, have] of clubs) if (have > UCL_RULES.clubMax) issues.push({ kind: 'club', club, have });
	const value = squadValue(players);
	const bankGiven = typeof bank === 'number' && Number.isFinite(bank) && bank >= 0;
	if (!bankGiven && value > UCL_RULES.budget + 1e-9) issues.push({ kind: 'budget', value });
	return { players, issues, value };
}

/** Pelaajan xP annetulla matchdaylla; puuttuva rivi = ei ottelua = 0. */
export function playerXp(p: UclSquadPlayer, md: number): number {
	const g = (p.gameweeks ?? []).find((x) => x.gw === md);
	return g && Number.isFinite(g.xp) ? g.xp : 0;
}

export interface UclXi {
	ids: number[];
	captain: number | null;
	/** XI:n summa + kapteenin tuplaus. */
	points: number;
}

/**
 * Paras XI yhdelle matchdaylle: ensin minimit (1/3/2/1) parhaista, sitten
 * loput nelja paikkaa parhaista jaljella olevista kenttapelaajista. Ahne on
 * tassa optimaalinen, koska 15:n ryhman jakauma (5/5/3) ei voi ylittaa XI:n
 * ylarajoja. Kapteeni = XI:n korkein xP.
 */
export function bestXi(players: readonly UclSquadPlayer[], md: number): UclXi {
	const byXp = (a: UclSquadPlayer, b: UclSquadPlayer) => playerXp(b, md) - playerXp(a, md) || a.id - b.id;
	const chosen: UclSquadPlayer[] = [];
	for (const pos of UCL_SQUAD_POSITIONS) {
		chosen.push(...players.filter((p) => p.pos === pos).sort(byXp).slice(0, UCL_RULES.xiMin[pos]));
	}
	const rest = players
		.filter((p) => p.pos !== 'GKP' && !chosen.includes(p))
		.sort(byXp)
		.slice(0, Math.max(0, UCL_RULES.xiSize - chosen.length));
	chosen.push(...rest);
	const cap = [...chosen].sort(byXp)[0] ?? null;
	const sum = chosen.reduce((s, p) => s + playerXp(p, md), 0);
	return {
		ids: chosen.map((p) => p.id),
		captain: cap ? cap.id : null,
		points: sum + (cap ? playerXp(cap, md) : 0)
	};
}

/** Horisontin pisteet: parhaan XI:n pisteet jokaiselta matchdaylta. */
export function squadPoints(players: readonly UclSquadPlayer[], mds: readonly number[]): number {
	return mds.reduce((s, md) => s + bestXi(players, md).points, 0);
}

/** Matchdayt joille xP on olemassa, nousevasti, vain sarjavaiheesta. */
export function horizonMatchdays(players: readonly UclSquadPlayer[]): number[] {
	const s = new Set<number>();
	for (const p of players) for (const g of p.gameweeks ?? []) if (Number.isInteger(g.gw)) s.add(g.gw);
	return [...s].filter((md) => md <= UCL_RULES.leaguePhaseLastMatchday).sort((a, b) => a - b);
}

/** Ehdotuksiin kelpaa: saatavilla (status a) eika thin data -rivi
 *  (MD1-takatestissa UEFA-pohjaiset yliennustettiin 15-40 %). */
export function suggestable(p: UclSquadPlayer): boolean {
	return (p.status ?? 'a') === 'a' && p.data_basis !== 'uefa_matches' && p.data_basis !== 'no_history';
}

export interface UclMove {
	out: number[];
	in: number[];
	gain: number;
	hits: number;
	net: number;
}

function clubCounts(players: readonly UclSquadPlayer[]): Map<string, number> {
	const m = new Map<string, number>();
	for (const p of players) m.set(p.team_short, (m.get(p.team_short) ?? 0) + 1);
	return m;
}

function swapOk(
	squad: readonly UclSquadPlayer[],
	outs: readonly UclSquadPlayer[],
	ins: readonly UclSquadPlayer[],
	bank: number,
	budgetless = false
): boolean {
	const ids = new Set(squad.map((p) => p.id));
	if (ins.some((p) => ids.has(p.id)) || new Set(ins.map((p) => p.id)).size !== ins.length) return false;
	if (!budgetless) {
		const spend = ins.reduce((s, p) => s + p.price, 0) - outs.reduce((s, p) => s + p.price, 0);
		if (spend > bank + 1e-9) return false;
	}
	const outIds = new Set(outs.map((p) => p.id));
	const after = [...squad.filter((p) => !outIds.has(p.id)), ...ins];
	for (const n of clubCounts(after).values()) if (n > UCL_RULES.clubMax) return false;
	return true;
}

function replaced(squad: readonly UclSquadPlayer[], outs: readonly UclSquadPlayer[], ins: readonly UclSquadPlayer[]) {
	const outIds = new Set(outs.map((p) => p.id));
	return [...squad.filter((p) => !outIds.has(p.id)), ...ins];
}

/** Wildcard-haun ehdokasraja per pelipaikka (toistuva haku; copy: "best squad we can find"). */
const WILDCARD_CANDIDATES_PER_POS = 40;
const PAIR_CANDIDATES_PER_OUT = 12;
/** Parin on oltava vahintaan nain paljon parempi kuin paras yksittainen siirto. */
export const PAIR_MIN_EXTRA = 0.1;

function candidatesByPos(
	all: readonly UclSquadPlayer[],
	squad: readonly UclSquadPlayer[],
	mds: readonly number[],
	cap?: number
) {
	const inSquad = new Set(squad.map((p) => p.id));
	const total = (p: UclSquadPlayer) => mds.reduce((s, md) => s + playerXp(p, md), 0);
	const out = new Map<string, UclSquadPlayer[]>();
	for (const pos of UCL_SQUAD_POSITIONS) {
		out.set(
			pos,
			all
				.filter((p) => p.pos === pos && !inSquad.has(p.id) && suggestable(p))
				.sort((a, b) => total(b) - total(a) || a.id - b.id)
				.slice(0, cap ?? Infinity)
		);
	}
	return out;
}

/**
 * Paras yksi siirto ja paras kahden siirron pari horisontin pisteilla
 * (parhaan XI:n summa, ei pelaajan oma summa: penkkiin jaava ostos ei
 * nosta pisteita). Hitit: siirrot yli ilmaisten * 4.
 *
 * Yksittainen siirto kay KAIKKI ehdokkaat joihin pankki riittaa, koska
 * nakyma lupaa "No transfer within your bank adds expected points".
 * 3.10 hold-copy-portti: aiempi raja (40 parasta xP:n mukaan) olisi
 * pienella pankilla jattanyt kaikki varalliset ehdokkaat pois ja tehnyt
 * lauseesta vaaran. Pari ja Wildcard ovat rajattuja hakuja (copy ei lupaa
 * niista kattavuutta).
 */
export function suggestTransfers(
	squad: readonly UclSquadPlayer[],
	all: readonly UclSquadPlayer[],
	bank: number,
	freeTransfers: number,
	mds: readonly number[],
	opts: { pairs?: boolean; cap?: number } = {}
): { single: UclMove | null; double: UclMove | null } {
	const base = squadPoints(squad, mds);
	const cands = candidatesByPos(all, squad, mds, opts.cap);
	const free = Math.max(0, Math.min(UCL_RULES.freeMax, Math.floor(freeTransfers)));
	const move = (outs: UclSquadPlayer[], ins: UclSquadPlayer[], pts: number): UclMove => {
		const hits = Math.max(0, outs.length - free);
		const gain = pts - base;
		return { out: outs.map((p) => p.id), in: ins.map((p) => p.id), gain, hits, net: gain - hits * UCL_RULES.hit };
	};
	let single: UclMove | null = null;
	const perOut = new Map<number, { p: UclSquadPlayer; pts: number }[]>();
	for (const o of squad) {
		const list: { p: UclSquadPlayer; pts: number }[] = [];
		for (const c of cands.get(o.pos) ?? []) {
			if (!swapOk(squad, [o], [c], bank)) continue;
			const pts = squadPoints(replaced(squad, [o], [c]), mds);
			list.push({ p: c, pts });
			if (!single || pts - base > single.gain + 1e-9) single = move([o], [c], pts);
		}
		perOut.set(o.id, list.sort((a, b) => b.pts - a.pts).slice(0, PAIR_CANDIDATES_PER_OUT));
	}
	// Pari: jokainen ulos-pari, kummallekin sen parhaat ehdokkaat. Pankki ja
	// seurakatto tarkistetaan PARINA (yksittain laillinen pari voi ylittaa).
	let double: UclMove | null = null;
	for (let i = 0; opts.pairs !== false && i < squad.length; i++) {
		for (let j = i + 1; j < squad.length; j++) {
			const a = squad[i];
			const b = squad[j];
			for (const ca of perOut.get(a.id) ?? []) {
				for (const cb of perOut.get(b.id) ?? []) {
					if (ca.p.id === cb.p.id || !swapOk(squad, [a, b], [ca.p, cb.p], bank)) continue;
					const pts = squadPoints(replaced(squad, [a, b], [ca.p, cb.p]), mds);
					if (!double || pts - base > double.gain + 1e-9) double = move([a, b], [ca.p, cb.p], pts);
				}
			}
		}
	}
	if (single && single.gain <= 1e-9) single = null;
	if (double && double.gain <= 1e-9) double = null;
	// Pari vain kun toinen siirto tuo jotain: muuten ehdotus "kaksi siirtoa,
	// sama hyoty" kuluttaisi siirron tyhjaan (mitattu 3.10 oikealla datalla:
	// Kane -> Mbappe +0.5 ja pari Kane+Valle -> Mbappe+Natan, sama +0.5).
	if (double && single && double.gain <= single.gain + PAIR_MIN_EXTRA) double = null;
	return { single, double };
}

/** Paras XI koko poolista ilman budjettia (Limitless), seurakatto voimassa. */
export function limitlessXi(all: readonly UclSquadPlayer[], md: number): UclXi {
	const pool = all.filter(suggestable).sort((a, b) => playerXp(b, md) - playerXp(a, md) || a.id - b.id);
	const chosen: UclSquadPlayer[] = [];
	const clubs = new Map<string, number>();
	const count = (pos: string) => chosen.filter((p) => p.pos === pos).length;
	const take = (p: UclSquadPlayer) => {
		chosen.push(p);
		clubs.set(p.team_short, (clubs.get(p.team_short) ?? 0) + 1);
	};
	const clubFree = (p: UclSquadPlayer) => (clubs.get(p.team_short) ?? 0) < UCL_RULES.clubMax;
	for (const pos of UCL_SQUAD_POSITIONS) {
		for (const p of pool) {
			if (count(pos) >= UCL_RULES.xiMin[pos]) break;
			if (p.pos === pos && clubFree(p)) take(p);
		}
	}
	for (const p of pool) {
		if (chosen.length >= UCL_RULES.xiSize) break;
		if (chosen.includes(p) || !clubFree(p)) continue;
		const pos = p.pos as UclSquadPos;
		if (count(pos) >= UCL_RULES.xiMax[pos]) continue;
		take(p);
	}
	const cap = [...chosen].sort((a, b) => playerXp(b, md) - playerXp(a, md))[0] ?? null;
	const sum = chosen.reduce((s, p) => s + playerXp(p, md), 0);
	return { ids: chosen.map((p) => p.id), captain: cap ? cap.id : null, points: sum + (cap ? playerXp(cap, md) : 0) };
}

/** Wildcard: toistetaan parasta yksittaista siirtoa kunnes mikaan ei paranna.
 *  Paikallinen optimi, ei taattu globaali; horisontti on vain xP:n MD:t. */
export function wildcardSquad(
	squad: readonly UclSquadPlayer[],
	all: readonly UclSquadPlayer[],
	bank: number,
	mds: readonly number[],
	maxRounds = 30
): { players: UclSquadPlayer[]; gain: number } {
	let cur = [...squad];
	let curBank = bank;
	const base = squadPoints(squad, mds);
	for (let r = 0; r < maxRounds; r++) {
		const { single } = suggestTransfers(cur, all, curBank, UCL_RULES.freeMax, mds, {
			pairs: false,
			cap: WILDCARD_CANDIDATES_PER_POS
		});
		if (!single || single.gain < 0.05) break;
		const o = cur.find((p) => p.id === single.out[0])!;
		const i = all.find((p) => p.id === single.in[0])!;
		cur = replaced(cur, [o], [i]);
		curBank = round1(curBank + o.price - i.price);
	}
	return { players: cur, gain: squadPoints(cur, mds) - base };
}

export type UclChipAdvice =
	| {
			state: 'rows';
			limitless: { md: number; gain: number; blocked: boolean }[];
			wildcard: { md: number; gain: number; blocked: boolean };
	  }
	| { state: 'blocked'; md: number };

/** Chip-arvio horisontille. Deadline-MD:lla 1/9/11 kaikilla on jo rajattomat
 *  siirrot, joten chipia ei voi pelata eika siita lasketa arvoa. */
export function chipAdvice(
	squad: readonly UclSquadPlayer[],
	all: readonly UclSquadPlayer[],
	bank: number,
	mds: readonly number[]
): UclChipAdvice {
	const blocked = (md: number) => UCL_RULES.chipBlockedMatchdays.includes(md);
	const now = mds[0];
	if (now === undefined || blocked(now)) return { state: 'blocked', md: now ?? 0 };
	const limitless = mds.map((md) => ({
		md,
		blocked: blocked(md),
		gain: blocked(md) ? 0 : limitlessXi(all, md).points - bestXi(squad, md).points
	}));
	const wc = wildcardSquad(squad, all, bank, mds);
	return { state: 'rows', limitless, wildcard: { md: now, gain: wc.gain, blocked: false } };
}

export type UclSquadAnalysis =
	| { state: 'locked' }
	| { state: 'unavailable' }
	| { state: 'incomplete'; issues: UclSquadIssue[] }
	| {
			state: 'ready';
			md: number;
			mds: number[];
			players: UclSquadPlayer[];
			bank: number;
			xi: UclXi;
			horizonPoints: number;
	  };

/**
 * xP-listan rivit poolin jarjestyksessa: joukkue tarkistetaan poolia
 * vastaan (kaikki pelaajat), ja pelaaja jota ei ole xP-listalla (excluded)
 * saa tyhjat gameweeks = 0 xP eika katoa joukkueesta.
 */
export function withXp(
	pool: readonly UclSquadPlayer[],
	xpPlayers: readonly UclSquadPlayer[]
): UclSquadPlayer[] {
	const xp = new Map(xpPlayers.map((p) => [p.id, p]));
	return pool.map((p) => xp.get(p.id) ?? { ...p, gameweeks: [] });
}

/**
 * Sivun ainoa sisaankaynti analyysiin. `pool` = kaikki pelaajat (ilmainen),
 * `xpPlayers` = taysi xP-lista (Premium), `meta` = vastauksen meta.
 * Maskattu tai mennyt deadline ei tuota lukuja.
 */
export function analyseSquad(
	ids: readonly number[],
	pool: readonly UclSquadPlayer[] | null | undefined,
	xpPlayers: readonly UclSquadPlayer[] | null | undefined,
	meta: { available?: boolean; masked?: boolean; deadline_gameweek?: number | null; deadline_passed?: boolean } | null | undefined,
	bank?: number | null
): UclSquadAnalysis {
	if (!meta || meta.available === false || !pool || !xpPlayers) return { state: 'unavailable' };
	if (meta.masked) return { state: 'locked' };
	const md = meta.deadline_gameweek;
	if (meta.deadline_passed || typeof md !== 'number' || md < 1 || md > UCL_RULES.leaguePhaseLastMatchday) {
		return { state: 'unavailable' };
	}
	const all = withXp(pool, xpPlayers);
	const v = validateSquad(ids, all, bank);
	if (v.issues.length) return { state: 'incomplete', issues: v.issues };
	const mds = horizonMatchdays(xpPlayers).filter((m) => m >= md);
	if (!mds.length || mds[0] !== md) return { state: 'unavailable' };
	return {
		state: 'ready',
		md,
		mds,
		players: v.players,
		bank: squadBank(v.players, bank),
		xi: bestXi(v.players, md),
		horizonPoints: squadPoints(v.players, mds)
	};
}
