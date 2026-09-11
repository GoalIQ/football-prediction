/**
 * PLAYER-PERCENTILES-VS-POSITION (11.9.2026, NextXI-vertailu 10.9).
 *
 * 🔴 YKSI LUKIJA PROSENTTIILILLE (CLAUDE.md 6a mekanismi 1). Prosenttiili on
 * luku jonka VIEREEN kirjoitetaan otoslabel ("vs 116 midfielders"). Jos
 * kumpikin laskettaisiin omalla pinnallaan, label ja luku voisivat ajautua
 * eri joukosta laskettuihin - tasan sama vikaluokka kuin
 * `lause-ja-luku-eri-lahteesta`. Siksi `percentileOf` palauttaa MOLEMMAT
 * samasta kutsusta: prosenttiilin ja sen populaation koon.
 *
 * SAANTO: populaatio on sama positio JA pelattuja minuutteja yli nollan.
 * Pelaamaton pelaaja ei ole kilpailussa, ja hanen nollansa nostaisi jokaisen
 * muun prosenttiilia (muisti: nolla-ei-ole-sama-kuin-ei-tietoa).
 *
 * SAANTO: vain sellaiset tilastot joissa SUUREMPI ON PAREMPI. Paastetyt
 * maalit ja kortit ovat kaanteisia, ja palkki jossa pitka on hyva valehtelisi
 * niista. Ne jatetaan pois kokonaan eika kaanneta, koska kaannetty palkki
 * vaatisi oman selityksensa jokaisen rivin viereen.
 */

/** Rivi jolla on positio ja nimettyja numeroita. Tarkoituksella loysa: sama
 *  lukija palvelee webin `PlayerStatsRow`:ta ja mobiilin omaa tyyppia ilman
 *  etta kumpikaan joutuu kaantamaan aineistoaan valissa. */
export type StatRow = {
	pos?: string | null;
	fpl?: unknown;
};

/** Kentan luku rivilta ilman indeksisignatuurin vaatimusta kutsujalta. */
function field(r: StatRow, key: string): unknown {
	const f = r.fpl;
	if (!f || typeof f !== 'object') return undefined;
	return (f as Record<string, unknown>)[key];
}

export type Percentile = {
	/** 0-100, pyoristetty. Osuus samasta populaatiosta joka jaa TIUKASTI alle. */
	pct: number;
	/** Populaation koko. Sama kutsu antaa luvun ja sen otoksen. */
	n: number;
};

/** Numero tai null. NaN ja aarettomat ovat "ei tietoa", eivat nollia. */
export function num(v: unknown): number | null {
	if (typeof v !== 'number' || !Number.isFinite(v)) return null;
	return v;
}

/** Pelasiko pelaaja lainkaan ikkunassa. */
export function hasPlayed(r: StatRow): boolean {
	return (num(field(r, 'mins')) ?? 0) > 0;
}

/** Populaatio: sama positio, minuutteja yli nollan. */
export function population(rows: StatRow[], pos: string | null | undefined): StatRow[] {
	if (!pos) return [];
	return rows.filter((r) => r.pos === pos && hasPlayed(r));
}

/**
 * Pelaajan prosenttiili yhdesta kentasta omassa positiossaan.
 *
 * Palauttaa null kun arvoa ei ole, populaatio on tyhja tai pelaaja itse ei
 * ole pelannut: kaikissa naissa palkki olisi vaite jota ei voi tehda.
 */
export function percentileOf(
	rows: StatRow[],
	player: StatRow,
	key: string
): Percentile | null {
	const mine = num(field(player, key));
	if (mine === null || !hasPlayed(player)) return null;
	const pop = population(rows, player.pos);
	if (pop.length === 0) return null;
	let below = 0;
	let counted = 0;
	for (const r of pop) {
		const v = num(field(r, key));
		if (v === null) continue;
		counted += 1;
		if (v < mine) below += 1;
	}
	if (counted === 0) return null;
	return { pct: Math.round((below / counted) * 100), n: counted };
}

/** "82nd", "1st", "23rd". Englannin jarjestysluvun paate. */
export function ordinal(n: number): string {
	const t = n % 100;
	if (t >= 11 && t <= 13) return `${n}th`;
	switch (n % 10) {
		case 1:
			return `${n}st`;
		case 2:
			return `${n}nd`;
		case 3:
			return `${n}rd`;
		default:
			return `${n}th`;
	}
}

/** Monikko positiosta, otoslabelia varten. */
export function positionWord(pos: string | null | undefined): string {
	switch (pos) {
		case 'GKP':
			return 'goalkeepers';
		case 'DEF':
			return 'defenders';
		case 'MID':
			return 'midfielders';
		case 'FWD':
			return 'forwards';
		default:
			return 'players';
	}
}

export type StatSpec = { key: string; label: string; digits?: number };

/**
 * Mitka tilastot nayetaan kussakin positiossa. Vain "suurempi on parempi".
 * Kentat ovat `fpl_player_stats.py`:n `_SUM_COLS`-nimia; tassa ei ole yhtaan
 * kenttaa jota vastaus ei kanna.
 */
export const STATS_BY_POS: Record<string, StatSpec[]> = {
	GKP: [
		{ key: 'mins', label: 'Minutes' },
		{ key: 'saves', label: 'Saves' },
		{ key: 'cs', label: 'Clean sheets' },
		{ key: 'bonus', label: 'Bonus points' },
		{ key: 'bps', label: 'Bonus points system' },
		{ key: 'pts', label: 'FPL points' }
	],
	DEF: [
		{ key: 'mins', label: 'Minutes' },
		{ key: 'cs', label: 'Clean sheets' },
		{ key: 'dc', label: 'Defensive contributions' },
		{ key: 'cbi', label: 'Clearances, blocks, interceptions' },
		{ key: 'xgi', label: 'Expected goals and assists', digits: 2 },
		{ key: 'bps', label: 'Bonus points system' },
		{ key: 'pts', label: 'FPL points' }
	],
	MID: [
		{ key: 'mins', label: 'Minutes' },
		{ key: 'xg', label: 'Expected goals', digits: 2 },
		{ key: 'xa', label: 'Expected assists', digits: 2 },
		{ key: 'xgi', label: 'Expected goals and assists', digits: 2 },
		{ key: 'dc', label: 'Defensive contributions' },
		{ key: 'ict', label: 'ICT index', digits: 1 },
		{ key: 'bps', label: 'Bonus points system' },
		{ key: 'pts', label: 'FPL points' }
	],
	FWD: [
		{ key: 'mins', label: 'Minutes' },
		{ key: 'xg', label: 'Expected goals', digits: 2 },
		{ key: 'xa', label: 'Expected assists', digits: 2 },
		{ key: 'xgi', label: 'Expected goals and assists', digits: 2 },
		{ key: 'ict', label: 'ICT index', digits: 1 },
		{ key: 'bps', label: 'Bonus points system' },
		{ key: 'pts', label: 'FPL points' }
	]
};

export function statsFor(pos: string | null | undefined): StatSpec[] {
	return STATS_BY_POS[pos ?? ''] ?? [];
}
