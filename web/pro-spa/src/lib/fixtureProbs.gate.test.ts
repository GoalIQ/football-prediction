/** Portti: Fixtures-rivin 1X2 webissa (ulkoasu WP10 / B3, 2.11.2026).
 *
 * Luku tulee julkisesta ennustelokista, ja rivi yhdistetaan lokiin nimen ja
 * ajan perusteella. Sovelluksessa sama ominaisuus kaatui kahdesti samasta
 * syysta: ensin kilpailukoodi (kaikki rivit ilman lukua, 1.11), sitten
 * nimimuunnos indeksin ja haun valilla (neljalta seuralta katosi palkki, 2.11,
 * goaliq-app b8695417). Taman portin syotteet ovat tuotannosta 2.11.2026
 * (/api/fixtures ja /api/accuracy?include=pending&competition=PL).
 *
 * Mekanismit (CLAUDE.md 6a):
 *   1. yksi lukija `probsFor` (rivi -> luku), indeksi lokin omilla nimilla;
 *   2. poikkeuslista: Fixtures-liiga ilman lokikoodia vaatii perustelun;
 *   3. vaiheinvariantti: sama funktio ennen ottelua, siirretyn ottelun ja
 *      gradauksen jalkeen (rivi poistuu lokin pending-listasta).
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { FIXTURE_LEAGUES } from './leagues';
import {
	buildProbsIndex,
	LOG_COMPETITION,
	logCompetitionFor,
	pctInt,
	probsFor,
	type PendingRow
} from './fixtureProbs';

// /api/fixtures?league=ENG-Premier League&days=30, 2.11.2026 (otos).
const FIXTURES = [
	{ datetime: '2026-11-02T20:00:00Z', home_team: 'Newcastle United FC', home_team_short_name: 'Newcastle', away_team: 'Everton FC', away_team_short_name: 'Everton' },
	{ datetime: '2026-11-07T17:30:00Z', home_team: 'Nottingham Forest FC', home_team_short_name: 'Nottingham', away_team: 'Manchester City FC', away_team_short_name: 'Man City' },
	{ datetime: '2026-11-08T16:30:00Z', home_team: 'Manchester United FC', home_team_short_name: 'Man United', away_team: 'Aston Villa FC', away_team_short_name: 'Aston Villa' },
	{ datetime: '2026-11-08T14:00:00Z', home_team: 'Brighton & Hove Albion FC', home_team_short_name: 'Brighton Hove', away_team: 'Brentford FC', away_team_short_name: 'Brentford' },
	{ datetime: '2026-11-07T15:00:00Z', home_team: 'Arsenal FC', home_team_short_name: 'Arsenal', away_team: 'Hull City AFC', away_team_short_name: 'Hull City' }
];

// /api/accuracy?include=pending&competition=PL, 2.11.2026 (samat ottelut).
const PENDING: PendingRow[] = [
	{ competition: 'PL', home_team: 'Newcastle United', away_team: 'Everton', kickoff: '2026-11-02T20:00:00Z', date: '2026-11-02', p_home: 0.4522, p_draw: 0.2532, p_away: 0.2946, predicted_winner: 'home' },
	{ competition: 'PL', home_team: 'Nottingham Forest', away_team: 'Manchester City', kickoff: '2026-11-07T17:30:00Z', date: '2026-11-07', p_home: 0.1776, p_draw: 0.2561, p_away: 0.5662, predicted_winner: 'away' },
	{ competition: 'PL', home_team: 'Manchester United', away_team: 'Aston Villa', kickoff: '2026-11-08T16:30:00Z', date: '2026-11-08', p_home: 0.5616, p_draw: 0.2251, p_away: 0.2133, predicted_winner: 'home' },
	{ competition: 'PL', home_team: 'Brighton', away_team: 'Brentford', kickoff: '2026-11-08T14:00:00Z', date: '2026-11-08', p_home: 0.5462, p_draw: 0.238, p_away: 0.2158, predicted_winner: 'home' },
	{ competition: 'PL', home_team: 'Arsenal', away_team: 'Hull', kickoff: '2026-11-07T15:00:00Z', date: '2026-11-07', p_home: 0.7148, p_draw: 0.205, p_away: 0.0802, predicted_winner: 'home' },
	// Toinen kierros, sama kaupunki: ei saa sekoittua Man Unitedin riviin.
	{ competition: 'PL', home_team: 'Manchester City', away_team: 'Fulham', kickoff: '2026-11-21T12:30:00Z', date: '2026-11-21', p_home: 0.7226, p_draw: 0.1801, p_away: 0.0973, predicted_winner: 'home' }
];

const idx = buildProbsIndex(PENDING);

describe('Fixtures-rivin luku tuotannon nimilla', () => {
	it.each([
		['Newcastle', 0, { home: 45, draw: 25, away: 29 }],
		['Nottingham v Man City', 1, { home: 18, draw: 26, away: 57 }],
		['Man United', 2, { home: 56, draw: 23, away: 21 }],
		['Brighton Hove', 3, { home: 55, draw: 24, away: 22 }],
		['Hull City', 4, { home: 71, draw: 21, away: 8 }]
	])('%s', (_label, i, want) => {
		expect(probsFor(idx, FIXTURES[i])).toEqual(want);
	});

	it('jokainen otoksen rivi saa luvun (ei yhtaan hiljaista puutetta)', () => {
		expect(FIXTURES.map((f) => probsFor(idx, f)).filter((p) => p == null)).toHaveLength(0);
	});

	it('pyoristys = pct_int (puoli ylos), sama kuin ottelusivulla', () => {
		expect(pctInt(0.2946)).toBe(29);
		expect(pctInt(0.125)).toBe(13);
		expect(pctInt(0.5662)).toBe(57);
	});
});

describe('VAIHEINVARIANTTI: sama lukija ennen ottelua, siirron ja gradauksen jalkeen', () => {
	const f = FIXTURES[1];
	it('ennen ottelua: kirjattu rivi -> luku', () => {
		expect(probsFor(idx, f)).not.toBeNull();
	});
	it('siirretty ottelu (yli 36 h): vanha kirjaus ei kelpaa', () => {
		expect(probsFor(idx, { ...f, datetime: '2026-11-09T17:30:00Z' })).toBeNull();
	});
	it('siirto 36 h:n sisalla: sama kirjaus kelpaa', () => {
		expect(probsFor(idx, { ...f, datetime: '2026-11-08T12:00:00Z' })).not.toBeNull();
	});
	it('gradattu (rivi poistunut pendingista): ei lukua, ei 0 %', () => {
		const graded = buildProbsIndex(PENDING.filter((r) => r.home_team !== 'Nottingham Forest'));
		expect(probsFor(graded, f)).toBeNull();
	});
	it('sama pari kahdesti: lahin kickoff voittaa', () => {
		const two = buildProbsIndex([
			{ ...PENDING[1], kickoff: '2026-11-07T17:30:00Z', p_home: 0.2, p_draw: 0.3, p_away: 0.5 },
			{ ...PENDING[1], kickoff: '2026-11-08T12:00:00Z', p_home: 0.6, p_draw: 0.2, p_away: 0.2 }
		]);
		expect(probsFor(two, f)).toEqual({ home: 20, draw: 30, away: 50 });
	});
	it('kotipuoli ei saa vaihtua: kaanteinen pari -> null', () => {
		const rev = { ...f, home_team: 'Manchester City FC', home_team_short_name: 'Man City', away_team: 'Nottingham Forest FC', away_team_short_name: 'Nottingham' };
		expect(probsFor(idx, rev)).toBeNull();
	});
});

describe('rikkinainen lokirivi ei nay lukuna', () => {
	const f = FIXTURES[0];
	const base = PENDING[0];
	it.each([
		['puuttuva p_draw', { ...base, p_draw: null }],
		['summa 0.9', { ...base, p_home: 0.35 }],
		['yli 1', { ...base, p_home: 1.2, p_draw: -0.1, p_away: -0.1 }],
		['ei aikaa', { ...base, kickoff: null, date: null }],
		['sama joukkue molemmilla puolilla', { ...base, away_team: 'Newcastle United' }]
	])('%s -> null', (_l, row) => {
		expect(probsFor(buildProbsIndex([row as PendingRow]), f)).toBeNull();
	});
	it('tyhja tai puuttuva loki -> null', () => {
		expect(probsFor(buildProbsIndex([]), f)).toBeNull();
		expect(probsFor(buildProbsIndex(null), f)).toBeNull();
	});
});

describe('POIKKEUSLISTA: jokainen Fixtures-liiga kysyy lokia sen omalla koodilla', () => {
	/** Fixtures-liiga, jolla ei ole lokikoodia, ja miksi. Tyhja 2.11.2026. */
	const NO_LOG: Record<string, string> = {};
	it.each(FIXTURE_LEAGUES.map((l) => [l.code]))('%s', (code) => {
		const c = logCompetitionFor(code);
		if (c == null) {
			expect(NO_LOG[code], `${code}: lisaa LOG_COMPETITIONiin tai NO_LOGiin perustelun kanssa`).toBeTruthy();
		} else {
			expect(c).toMatch(/^[A-Z0-9]{2,4}$/);
		}
	});
	it('taulu on sama kuin sovelluksessa (goaliq-app lib/fixtureProbs.ts, ilman WC:ta)', () => {
		expect(LOG_COMPETITION).toEqual({
			'ENG-Premier League': 'PL',
			'ESP-La Liga-FD': 'PD',
			'GER-Bundesliga-FD': 'BL1',
			'ITA-Serie A-FD': 'SA',
			'FRA-Ligue 1-FD': 'FL1',
			'BRA-Serie A': 'BSA',
			'ENG-Championship': 'ELC',
			'NED-Eredivisie': 'DED',
			'POR-Primeira Liga': 'PPL',
			'INT-Champions League': 'CL'
		});
	});
});

describe('KUTSUPAIKKA: Fixtures.svelte', () => {
	const src = readFileSync(resolve(__dirname, 'components/Fixtures.svelte'), 'utf8');
	it('rivin luku tulee probsForista, indeksi buildProbsIndexista', () => {
		expect(src).toMatch(/probsFor\(probsIdx, f\)/);
		expect(src).toMatch(/buildProbsIndex\(rows\)/);
		expect(src).toMatch(/fetchPendingPredictions\(competition\)/);
		expect(src).toMatch(/logCompetitionFor\(lg\)/);
	});
	it('ei omaa prosenttilaskua (Math.round tai *100 rivilla)', () => {
		expect(src).not.toMatch(/p_home|p_draw|p_away/);
		expect(src).not.toMatch(/\*\s*100/);
	});
	it('B3: kaikki paivat kaikille, ei paivalukkoa', () => {
		expect(src).not.toMatch(/days\.slice\(0, 1\)/);
		expect(src).not.toMatch(/hiddenDays/);
		expect(src).toMatch(/\{#each rowsByDay as \[date, list\] \(date\)\}/);
	});
});
