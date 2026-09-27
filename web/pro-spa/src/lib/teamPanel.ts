/**
 * Joukkuepaneeli (PRO-JOUKKUENAKYMA, Villen paatos 27.9.2026: "suosituksen
 * mukaan"). Prossa ei ollut yhtaan joukkuenakymaa; seura nakyi vain lyhenteena
 * rivilla. Paneeli aukeaa lyhenteesta siella missa se jo nakyy (pelaajakortti,
 * Teams, Clean sheets) ja goaliq.appin 20 klubisivulta (`?team=ARS`). Ei uutta
 * navikohtaa.
 *
 * YKSI LUKIJA (saanto 6a kohta 1): paneelin luvut tulevat samoista lukijoista
 * kuin muiden pintojen, joten sama ottelu ei voi nayttaa kahta lukua:
 *   - ottelut ja CS% = `teamsCsGrid` (Teams-nakyma), kaukoriveille ei lukua
 *   - xP-ikkuna = `xpHorizon` (sama kuin xP-taulukon otsikko)
 *   - aloitus-% = `startPct`
 *
 * MASKI (fail-closed): ilmainen /api/fantasy/xp on top-N koko liigasta. Siita
 * seuran rivit olisivat 0-2 pelaajaa, ja lista "players by projected points"
 * valehtelisi olevansa koko joukkue. Maskatulla vastauksella `players` on null
 * ja paneeli nayttaa Premium-rivin + ilmaisen klubisivun linkin.
 *
 * KAUSI VAIHTUU (saanto 6a kohta 3): nousijat ja putoajat vaihtavat seurat.
 * Lyhenne haetaan datasta eika listasta; tuntematon lyhenne antaa null eika
 * vanhan kauden seuraa. Klubisivun slug on PYSYVA sopimus (sama taulu kuin
 * scripts/build_fpl_longtail.py CLUB_SLUGS, portti teamPanel.gate.test.ts).
 */
import type { FantasyResponse, XpResponse } from './api';
import { actionableGameweek } from './gameweek';
import { startPct } from './startPct';
import { teamsCsGrid } from './weekRows';
import { xpHorizon } from './xpHorizon';

/** FPL-lyhenne -> goaliq.app/fpl/club/<slug>. Sanatarkasti sama kuin
 *  generaattorin CLUB_SLUGS (portti vertaa). */
export const CLUB_SLUGS: Readonly<Record<string, string>> = {
	ARS: 'arsenal',
	AVL: 'aston-villa',
	BOU: 'bournemouth',
	BRE: 'brentford',
	BHA: 'brighton',
	BUR: 'burnley',
	CHE: 'chelsea',
	COV: 'coventry',
	CRY: 'crystal-palace',
	EVE: 'everton',
	FUL: 'fulham',
	HUL: 'hull',
	IPS: 'ipswich',
	LEE: 'leeds',
	LEI: 'leicester',
	LIV: 'liverpool',
	MCI: 'manchester-city',
	MUN: 'manchester-united',
	NEW: 'newcastle',
	NFO: 'nottingham-forest',
	SOU: 'southampton',
	SUN: 'sunderland',
	TOT: 'tottenham',
	WHU: 'west-ham',
	WOL: 'wolves'
};

export function clubPageUrl(short: string): string | null {
	const slug = CLUB_SLUGS[short];
	return slug ? `https://goaliq.app/fpl/club/${slug}` : null;
}

/** `?team=ars` -> "ARS"; kaikki muu null. Ei tarkista kautta: sen tekee
 *  `teamPanel` datasta. */
export function teamParam(raw: string | null | undefined): string | null {
	const s = (raw ?? '').trim().toUpperCase();
	return /^[A-Z]{3}$/.test(s) ? s : null;
}

export type TeamPanelFixture = {
	gw: number;
	opponent: string;
	opponentName: string;
	venue: string;
	/** Mallin CS% (palvelimen luku) lahiriveilla, null kaukoriveilla. */
	cs: number | null;
};

export type TeamPanelPlayer = {
	id: number;
	name: string;
	pos: string;
	price: number | null;
	start: number | null;
	xp: number;
};

export type TeamPanel = {
	short: string;
	name: string;
	/** Sama keskiarvo kuin Teams-nakymassa (`teamsCsGrid`), null ilman lukua. */
	avgCs: number | null;
	/** Keskiarvon kierrokset ("GW6-GW11"): Clean sheets -tyokalun oletusvali
	 *  voi sisaltaa kesken olevan kierroksen, joten luku nimeaa oman valinsa
	 *  (julkaisutarkistaja 27.9). null kun keskiarvoa ei ole. */
	avgRange: string | null;
	/** Deadline-kierroksesta eteenpain, enintaan `maxGws` kierrosta. */
	fixtures: { gw: number; items: TeamPanelFixture[] }[];
	/** null = xP maskattu (ilmainen) tai xP-dataa ei ole. */
	players: TeamPanelPlayer[] | null;
	masked: boolean;
	/** xP-summan ikkuna samasta lukijasta kuin summa ("next 6 GWs"), null
	 *  kunnes xP-vastaus on haettu: ilman metaa xpHorizon antaisi "model
	 *  horizon" -yleisnimen (mitattu livena 27.9 latauksen aikana). */
	window: string | null;
	clubUrl: string | null;
};

const teamKey = (t: { short?: string; name: string }) => t.short ?? t.name;

export function teamPanel(
	fantasy: FantasyResponse | null | undefined,
	xp: XpResponse | null | undefined,
	short: string,
	maxGws = 6
): TeamPanel | null {
	if (!fantasy?.meta?.available) return null;
	const team = (fantasy.teams ?? []).find((t) => teamKey(t) === short || t.name === short);
	if (!team) return null;
	const key = teamKey(team);
	const grid = teamsCsGrid(fantasy);
	const avgCs = grid?.rows.find((r) => r.team === key)?.avg ?? null;
	const cols = grid?.gws ?? [];
	const avgRange =
		avgCs == null || cols.length === 0
			? null
			: cols.length === 1
				? `GW${cols[0]}`
				: `GW${cols[0]}-GW${cols[cols.length - 1]}`;

	const from = actionableGameweek(fantasy.meta);
	const fixtures: TeamPanel['fixtures'] = [];
	if (from !== undefined) {
		// Ikkuna paattyy seuran viimeiseen otteluun: sen jalkeiset tyhjat
		// kierrokset eivat ole "Blank" vaan dataa jota ei viela ole.
		const lastFixture = Math.max(-Infinity, ...(team.fixtures ?? []).map((f) => f.gw));
		const last = Math.min(from + Math.max(0, maxGws) - 1, lastFixture);
		for (let gw = from; gw <= last; gw++) {
			const items = (team.fixtures ?? [])
				.filter((f) => f.gw === gw)
				.map((f) => ({
					gw,
					opponent: f.opponent_short,
					opponentName: f.opponent ?? f.opponent_short,
					venue: f.venue,
					cs: typeof f.cs_pct === 'number' && f.tier !== 'far' ? f.cs_pct : null
				}));
			fixtures.push({ gw, items });
		}
	}

	const masked = xp?.meta?.masked === true;
	let players: TeamPanelPlayer[] | null = null;
	if (xp && !masked) {
		players = (xp.players ?? [])
			.filter((p) => p.team_short === key)
			.map((p) => ({
				id: p.id,
				name: p.web_name,
				pos: p.pos,
				price: typeof p.price === 'number' ? p.price : null,
				start: startPct(p),
				xp: Number(p.xp_horizon_total) || 0
			}))
			.sort((a, b) => b.xp - a.xp);
	}
	return {
		short: key,
		name: team.name,
		avgCs,
		avgRange,
		fixtures,
		players,
		masked,
		window: xp ? xpHorizon(xp.meta).label : null,
		clubUrl: clubPageUrl(key)
	};
}
