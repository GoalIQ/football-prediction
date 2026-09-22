/**
 * Jokainen pron polku joka on joskus ollut julkinen (22.9.2026, A3).
 *
 * JAADYTETTY HISTORIA: tahan lisataan, tasta ei poisteta. Rekisteri
 * (`tools.ts`) kertoo vain NYKYISET reitit; jos vanhat polut johdettaisiin
 * siita, purettu ryhma katoaisi myos tasta ja sen jaetut URLit (/prices)
 * rikkoutuisivat hiljaa. Kaksi kayttajaa:
 *   - `redirects.gate.test.ts`: jokainen polku ratkeaa nykyiseen reittiin,
 *   - `scripts/route-heads.mjs`: buildin `_redirects` (301 palvelimella,
 *     joten jaettu vanha linkki ja sen link preview ohjautuvat ennen JS:aa).
 *
 * Ajetaan myos Nodessa (build-skripti, tyyppien riisunta): `.ts`-paatteet.
 */
import { GROUPS, TOOLS, resolvePath, toolPath } from './tools.ts';

/** Ryhmat ennen 22.9 (tools ennen 11.9). */
export const HISTORIC_GROUPS = ['week', 'team', 'players', 'prices', 'matches', 'tools'] as const;

/** Tyokalupolut ennen 22.9 (rekisteri 6b65ce233) + /tools/<slug> ennen 11.9. */
export const HISTORIC_TOOL_PATHS = [
	'/team/rate-my-team',
	'/team/fit-checker',
	'/team/transfer-planner',
	'/team/watchlist',
	'/team/chip-timing',
	'/team/transfer-chains',
	'/team/league',
	'/players/player-card',
	'/players/captain-ranker',
	'/players/fixture-swing',
	'/players/player-xp',
	'/players/clean-sheets',
	'/players/value',
	'/players/leaders',
	'/players/stats',
	'/players/differentials',
	'/players/replacements',
	'/players/compare',
	'/players/edge-mode',
	'/prices/price-watch',
	'/matches/predict',
	'/matches/fixtures',
	'/matches/table',
	'/tools/chip-timing',
	'/tools/transfer-chains',
	'/tools/edge-mode',
	'/tools/league'
] as const;

/** Nykyiset reitit: juuri, ryhmat ja tyokalut. */
export function currentRoutes(): Set<string> {
	return new Set<string>(['/', ...GROUPS.map((g) => `/${g.id}`), ...TOOLS.map((t) => toolPath(t))]);
}

export type RedirectRule = { from: string; to: string };

/**
 * Palvelimen 301-saannot (Cloudflare Pages `_redirects`), jarjestyksessa.
 * Pages kayttaa ensimmaista osumaa, joten tarkat polut ennen jokerisaantoa.
 *
 * - jokainen historiallinen polku jonka `resolvePath` vie muualle,
 * - purettujen ryhmien (joiden juuri ei ole enaa reitti) jokerisaanto
 *   `/<ryhma>/*` ryhman juuren kohteeseen: tuntematon vanha alipolku.
 * Lahde (from) ei saa koskaan olla nykyinen reitti: se varjostaisi sivun.
 */
export function redirectRules(): RedirectRule[] {
	const current = currentRoutes();
	const exact: RedirectRule[] = [];
	const splat: RedirectRule[] = [];
	for (const p of [...HISTORIC_GROUPS.map((g) => `/${g}`), ...HISTORIC_TOOL_PATHS]) {
		const to = resolvePath(p);
		if (to && to !== p && !current.has(p)) exact.push({ from: p, to });
	}
	for (const g of HISTORIC_GROUPS) {
		const root = `/${g}`;
		if (current.has(root)) continue;
		const to = resolvePath(root);
		if (to) splat.push({ from: `${root}/*`, to });
	}
	return [...exact, ...splat];
}

/** `_redirects`-tiedoston sisalto. */
export function redirectsFile(): string {
	const lines = redirectRules().map((r) => `${r.from} ${r.to} 301`);
	return `# Generoitu: scripts/route-heads.mjs <- src/lib/legacyPaths.ts. Ala muokkaa kasin.\n${lines.join('\n')}\n`;
}
