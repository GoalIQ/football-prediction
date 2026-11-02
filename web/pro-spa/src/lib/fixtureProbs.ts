/** Fixtures-rivin 1X2-todennakoisyys webissa (ulkoasu WP10 / B3, Villen
 * paatos 1.11.2026 "Fixtures auki + % riveilla"). Pariteetti sovelluksen
 * kanssa: goaliq-app lib/fixtureProbs.ts (WP9).
 *
 * LAHDE: julkinen ennusteloki (`/api/accuracy?include=pending&competition=`).
 * Sama kirjattu ennuste jonka goaliq.app:n ottelusivu ja liigahub nayttavat ja
 * jonka track record gradaa ottelun jalkeen, joten rivin luku on
 * tarkistettavissa ilmaispinnalta. EI Predict-kutsua per rivi: se laskisi
 * uuden luvun, joka voi erota kirjatusta.
 *
 * SAANTO 6a KOHTA 1 (yksi lukija joka ei voi palauttaa vaaraa):
 *   - Fixtures-rivin nimet sovitetaan LOKIN OMIIN nimiin samalla sovittimella
 *     kuin Predictin esitaytto ($lib/teamMatch). Indeksin avain on lokin nimi
 *     sellaisenaan, joten indeksi ja haku eivat voi kayttaa eri muunnosta
 *     (goaliq-app b8695417: neljalta seuralta katosi palkki juuri siksi).
 *   - rivi yhdistetaan vain kun KOTI ja VIERAS osuvat yksikasitteisesti ja
 *     kirjattu kickoff on 36 h:n sisalla ottelun ajasta. Siirretty ottelu tai
 *     sama pari toisessa kierroksessa ei saa vanhaa lukua.
 *   - kolme lukua 0..1 ja summa 0.97..1.03, muuten ei rivia. Puuttuva luku ei
 *     ole 0 %.
 *
 * Puhdas moduuli: fixtureProbs.gate.test.ts.
 */
import { matchTeam } from './teamMatch';

/** Lokin rivi (`pending_predictions`), vain kentat joita tama lukee. */
export interface PendingRow {
	competition?: string | null;
	home_team?: string | null;
	away_team?: string | null;
	kickoff?: string | null;
	date?: string | null;
	predicted_winner?: string | null;
	p_home?: number | null;
	p_draw?: number | null;
	p_away?: number | null;
}

export interface FixtureProbs {
	/** Kokonaislukuprosentit kuten ottelusivulla (pct_int, puoli ylos). */
	home: number;
	draw: number;
	away: number;
}

const WINDOW_MS = 36 * 3600 * 1000;

/**
 * SPA:n liigakoodi ($lib/leagues) -> ennustelokin kilpailukoodi (fp
 * prediction_log `competition`). Sama taulu kuin goaliq-app
 * LOG_COMPETITION. Backend hylkaa liigakoodin muodon (`^[A-Z0-9]{2,4}$`),
 * joten ilman taulua JOKAINEN rivi jaisi ilman lukua (sovelluksen 1.11 vika).
 * Portti: jokainen FIXTURE_LEAGUES-liiga on taulussa tai poikkeuslistassa.
 */
export const LOG_COMPETITION: Readonly<Record<string, string>> = {
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
};

/** Lokin kilpailukoodi liigalle, tai null (liigaa ei kirjata -> ei hakua). */
export function logCompetitionFor(leagueCode: string): string | null {
	return LOG_COMPETITION[leagueCode] ?? null;
}

/** Puoli ylos kuten fp pct_int (sivut kayttavat pct_int:ia, ei Pythonin round). */
export function pctInt(p: number): number {
	return Math.floor(p * 100 + 0.5);
}

function valid(p: unknown): p is number {
	return typeof p === 'number' && Number.isFinite(p) && p >= 0 && p <= 1;
}

function kickoffMs(row: PendingRow): number | null {
	const iso = row.kickoff ?? (row.date ? `${row.date}T12:00:00Z` : null);
	if (!iso) return null;
	const t = Date.parse(iso);
	return Number.isFinite(t) ? t : null;
}

interface Entry {
	home: string;
	away: string;
	at: number;
	probs: FixtureProbs;
}

export interface ProbsIndex {
	/** Lokin nimet (koti + vieras), sovituksen kohdelista. */
	names: string[];
	/** Avain `${home}|${away}` LOKIN nimilla. */
	byPair: Map<string, Entry[]>;
}

export const EMPTY_INDEX: ProbsIndex = { names: [], byPair: new Map() };

/** Indeksi kirjatuista pelaamattomista riveista (yksi kilpailu kerrallaan). */
export function buildProbsIndex(rows: readonly PendingRow[] | null | undefined): ProbsIndex {
	const byPair = new Map<string, Entry[]>();
	const names = new Set<string>();
	for (const r of rows ?? []) {
		const { p_home, p_draw, p_away } = r;
		if (!valid(p_home) || !valid(p_draw) || !valid(p_away)) continue;
		const sum = p_home + p_draw + p_away;
		if (sum < 0.97 || sum > 1.03) continue;
		const at = kickoffMs(r);
		const home = r.home_team?.trim();
		const away = r.away_team?.trim();
		if (at == null || !home || !away || home === away) continue;
		names.add(home);
		names.add(away);
		const k = `${home}|${away}`;
		const list = byPair.get(k) ?? [];
		list.push({
			home,
			away,
			at,
			probs: { home: pctInt(p_home), draw: pctInt(p_draw), away: pctInt(p_away) }
		});
		byPair.set(k, list);
	}
	return { names: [...names], byPair };
}

/** Fixtures-rivin joukkue lokin nimeksi: lyhyt nimi ensin, sitten pitka. */
function resolveSide(pool: readonly string[], ...candidates: (string | null | undefined)[]) {
	for (const c of candidates) {
		if (!c) continue;
		const hit = matchTeam(c, pool);
		if (hit) return hit;
	}
	return null;
}

/** Fixtures-rivin muoto, jonka lukija tarvitsee (FixtureRow-yhteensopiva). */
export interface FixtureLike {
	datetime?: string | null;
	home_team: string;
	away_team: string;
	home_team_short_name?: string | null;
	away_team_short_name?: string | null;
}

/** Rivin luku, tai null = ei kirjattua ennustetta tai ei varmaa osumaa. */
export function probsFor(idx: ProbsIndex, f: FixtureLike): FixtureProbs | null {
	if (!f.datetime || idx.byPair.size === 0) return null;
	const t = Date.parse(f.datetime);
	if (!Number.isFinite(t)) return null;
	const home = resolveSide(idx.names, f.home_team_short_name, f.home_team);
	const away = resolveSide(idx.names, f.away_team_short_name, f.away_team);
	if (!home || !away || home === away) return null;
	const list = idx.byPair.get(`${home}|${away}`);
	if (!list) return null;
	let best: { d: number; probs: FixtureProbs } | null = null;
	for (const e of list) {
		const d = Math.abs(e.at - t);
		if (d <= WINDOW_MS && (best == null || d < best.d)) best = { d, probs: e.probs };
	}
	return best?.probs ?? null;
}
