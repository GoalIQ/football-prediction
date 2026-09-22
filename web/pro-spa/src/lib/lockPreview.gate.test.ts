/**
 * Portti: lukitun premium-tyokalun oma URL nayttaa ei-maksajalle naytteen ja
 * hinnan, ei tyhjaa nakymaa (22.9, web-audit T3).
 *
 * 🔴 MITATTU 22.9 tuotannosta (390x844, kirjautumatta): yhdeksasta premium-
 * URLista kuusi renderoi ei-maksajalle tyokalurivin ja tyhjan sisallon
 * (haarat ovat muotoa `premium && show(...)`), kolme "See Premium" -laatikon.
 * Yhdellakaan ei ollut riviakaan dataa eika ostonappia.
 *
 * Kolme vaitetta:
 *   1. lukija (`lockedToolFor`) lukitsee TASAN premium-tyokalut ei-maksajalle,
 *   2. ToolsHome kysyy lukijalta ENNEN ryhmapaneeleita, joten yksikaan ryhma
 *      ei voi jattaa lukkoa pois (erotteleva kontrolli: haaran poisto kaatuu),
 *   3. nayte on palvelimen rivit sellaisenaan: ei uudelleenjarjestysta, ei
 *      keksittya rivia, ja puuttuva arvo nakyy lukkona eika nollana.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import { TOOLS, type Tool } from './tools';
import type { XpPlayer, XpResponse } from './api';
import {
	LOCKED_VALUE,
	PREVIEW_ROWS,
	gwCell,
	lockedToolFor,
	previewRows,
	valueCell
} from './lockPreview';

// CRLF -> LF: Windows-tyopuussa tiedostot ovat CRLF, CI:ssa LF. Ilman tata
// rivinvaihdon sisaltava haku olisi -1 ja ehto 'dir < branch' tyhjasti tosi.
const read = (f: string) =>
	readFileSync(resolve(__dirname, 'components', f), 'utf-8').replace(/\r\n/g, '\n');
const markup = (src: string) => blankComments(src.slice(src.lastIndexOf('</script>')));

/** ToolsHomen haaraketju: lukko ennen ensimmaista ryhmapaneelia. */
function lockBranchProblems(src: string): string[] {
	const p: string[] = [];
	const script = blankComments(src.slice(0, src.lastIndexOf('</script>')));
	if (!/const lockedTool = \$derived\(lockedToolFor\(activeTool, premium\)\)/.test(script))
		p.push('lockedTool ei tule lukijasta lockedToolFor(activeTool, premium)');
	const m = markup(src);
	// Toinen `{#if showDirectory}` aloittaa paneeliketjun (ensimmainen
	// renderoi hakemiston navin alle). Kommentit on tyhjatty, joten ankkuri
	// ei voi olla kommentin teksti.
	const dir = m.indexOf('{#if showDirectory}', m.indexOf('{#if showDirectory}') + 1);
	const branch = m.indexOf('{:else if lockedTool}');
	const comp = m.indexOf('<LockedToolPreview tool={lockedTool}');
	const firstPanel = m.indexOf("{:else if segment === 'week' || segment === 'team'}");
	if (branch === -1) p.push('{:else if lockedTool} -haara puuttuu');
	if (comp === -1) p.push('<LockedToolPreview tool={lockedTool} ...> puuttuu');
	if (dir === -1) p.push('hakemistohaaraa ei loytynyt (portti mittaisi tyhjaa)');
	if (firstPanel === -1) p.push('ryhmapaneelien ketjua ei loytynyt (portti mittaisi tyhjaa)');
	if (branch !== -1 && firstPanel !== -1 && !(dir < branch && branch < comp && comp < firstPanel))
		p.push('lukkohaara ei ole hakemiston ja ensimmaisen ryhmapaneelin valissa');
	return p;
}

const player = (over: Partial<XpPlayer>): XpPlayer =>
	({
		id: 1,
		web_name: 'A',
		team: 'X',
		team_short: 'XXX',
		pos: 'MID',
		xmins: 90,
		xp_per_gw: 5,
		xp_horizon_total: 30,
		gameweeks: [{ gw: 6, xp: 5.49, opponents: [] }],
		...over
	}) as XpPlayer;

describe('lukija: mika lukitaan', () => {
	const premiumTools = TOOLS.filter((t) => t.tier === 'premium');

	it('rekisterissa on premium-tyokaluja (muuten alla oleva menisi lapi tyhjana)', () => {
		expect(premiumTools.length).toBeGreaterThanOrEqual(9);
	});

	it('jokainen premium-tyokalu lukitaan ei-maksajalle, ei maksajalle', () => {
		for (const t of premiumTools) {
			expect(lockedToolFor(t, false), t.slug).toBe(t);
			expect(lockedToolFor(t, true), t.slug).toBeNull();
		}
	});

	it('ilmaista tyokalua ei koskaan lukita, eika hakemistoa (null)', () => {
		for (const t of TOOLS.filter((x) => x.tier === 'free')) expect(lockedToolFor(t, false)).toBeNull();
		expect(lockedToolFor(null, false)).toBeNull();
		expect(lockedToolFor(undefined as unknown as Tool, false)).toBeNull();
	});
});

describe('ToolsHome: lukko ennen ryhmapaneeleita', () => {
	const src = read('ToolsHome.svelte');

	it('nykyinen lahde on kunnossa', () => {
		expect(lockBranchProblems(src)).toEqual([]);
	});

	it('erotteleva kontrolli: ilman lukkohaaraa portti kaatuu', () => {
		const without = src.replace(
			/\{:else if lockedTool\}[\s\S]*?<LockedToolPreview tool=\{lockedTool\} onUpgrade=\{goUpgrade\} \/>\n/,
			''
		);
		expect(without).not.toBe(src);
		expect(lockBranchProblems(without).length).toBeGreaterThan(0);
	});

	it('erotteleva kontrolli: omalla ehdolla (ei lukijasta) portti kaatuu', () => {
		const own = src.replace(
			'lockedToolFor(activeTool, premium)',
			"activeTool?.slug === 'player-xp' ? activeTool : null"
		);
		expect(lockBranchProblems(own).length).toBeGreaterThan(0);
	});
});

describe('nayte on palvelimen rivit sellaisenaan', () => {
	const rows = Array.from({ length: 10 }, (_, i) =>
		player({ id: i + 1, web_name: `P${i + 1}`, xp_horizon_total: 40 - i })
	);
	const xp = (over: Partial<XpResponse['meta']> = {}, players = rows): XpResponse =>
		({ meta: { available: true, ...over }, players }) as XpResponse;

	it('enintaan PREVIEW_ROWS rivia, palvelimen jarjestyksessa', () => {
		const out = previewRows(xp());
		expect(out.length).toBe(PREVIEW_ROWS);
		expect(out.map((p) => p.id)).toEqual([1, 2, 3, 4, 5]);
		// Palvelimen jarjestys sailyy vaikka se ei olisi laskeva: ei uudelleenlajittelua.
		const shuffled = [rows[3], rows[0], rows[7]];
		expect(previewRows(xp({}, shuffled)).map((p) => p.id)).toEqual([4, 1, 8]);
	});

	it('ei koskaan enemman kuin palvelin antoi, eika mitaan kun data ei ole julkaistu', () => {
		expect(previewRows(xp({}, rows.slice(0, 2))).length).toBe(2);
		expect(previewRows(xp({ available: false }))).toEqual([]);
		expect(previewRows(null)).toEqual([]);
		expect(previewRows({ meta: { available: true } } as XpResponse)).toEqual([]);
	});

	it('puuttuva arvo = lukko, tyhja kierros = 0.0', () => {
		expect(valueCell(31.04)).toBe('31.0');
		expect(valueCell(undefined)).toBe(LOCKED_VALUE);
		expect(valueCell(null)).toBe(LOCKED_VALUE);
		expect(gwCell(player({}), 6)).toBe('5.5');
		expect(gwCell(player({}), 7)).toBe('0.0');
		expect(gwCell(player({ gameweeks: undefined as unknown as XpPlayer['gameweeks'] }), 6)).toBe(
			LOCKED_VALUE
		);
		expect(gwCell(player({}), undefined)).toBe(LOCKED_VALUE);
	});
});

describe('LockedToolPreview: hinta ja ostonappi samassa laatikossa, kauppa toissijainen', () => {
	const src = read('LockedToolPreview.svelte');
	const m = markup(src);

	it('taulukko, sumennettu loppu ja ostonapit ovat saman .lock-cardin sisalla, tassa jarjestyksessa', () => {
		const card = m.indexOf('<div class="lock-card">');
		const table = m.indexOf('<table>');
		const ghost = m.indexOf('<div class="ghost"');
		const plans = m.indexOf('{#each Object.entries(PLANS)');
		const store = m.indexOf('class="app-link"');
		expect(card).toBeGreaterThan(-1);
		expect(card < table && table < ghost && ghost < plans && plans < store).toBe(true);
	});

	it('komponentti ei lajittele eika hae muuta dataa kuin palvelimen xP-vastauksen', () => {
		const script = blankComments(src.slice(0, src.lastIndexOf('</script>')));
		expect(script).not.toMatch(/\.sort\(/);
		expect(script.match(/fetch[A-Z]\w*\(/g) ?? []).toEqual(['fetchXp(']);
	});
});
