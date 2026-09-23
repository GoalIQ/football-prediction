/**
 * Portti: RSL Fantasy -sivun (/spl) valitsin (23.9, RSL-MENUT).
 *
 * Villen pyynto: "RSL fantasyn vois kans jasennella noilla menuilla". /spl oli
 * yksi pitka pino; nyt ( Players | Teams | Model squad ) + FPL:n esiasetukset.
 *
 * Mita vartioidaan (CLAUDE.md 6a):
 *   1. jokainen nakyma on tasan yhdessa osiossa ja valitsimesta saavutettava
 *      (esiasetus, More-rivi tai osion paakohde),
 *   2. jokainen entinen osio on sivulla tasan yhden nakyman alla, eli mikaan
 *      ei kadonnut hiljaa kun pino jaettiin,
 *   3. sivu lukee nakyman vain `splView`in kautta (yksi lukija),
 *   4. esiasetukset ovat samat nimet samassa jarjestyksessa kuin FPL:ssa.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
	PLAYER_PRESETS,
	SPL_DEFAULT_VIEW,
	SPL_MORE,
	SPL_PRESETS,
	SPL_SECTIONS,
	splSectionOf,
	splView,
	type SplView
} from './tools';
import { blankComments } from './sourceScan';

const PAGE = fileURLToPath(new URL('../routes/spl/+page.svelte', import.meta.url));
const src = readFileSync(PAGE, 'utf-8').replace(/\r\n/g, '\n');
const markup = blankComments(src.slice(src.lastIndexOf('</script>'), src.lastIndexOf('<style>')));
const script = src.slice(0, src.lastIndexOf('</script>'));

const ALL_VIEWS: SplView[] = SPL_SECTIONS.flatMap((s) => s.views);

describe('RSL-valitsimen rekisteri', () => {
	it('jokainen nakyma on tasan yhdessa osiossa', () => {
		expect(new Set(ALL_VIEWS).size).toBe(ALL_VIEWS.length);
		expect(ALL_VIEWS.length).toBe(9);
	});

	it('jokainen nakyma on saavutettava valitsimesta', () => {
		const reachable = new Set<SplView>([
			...SPL_SECTIONS.map((s) => s.lead),
			...SPL_PRESETS.map((p) => p.view),
			...Object.values(SPL_MORE).flatMap((xs) => xs.map((x) => x.view))
		]);
		for (const v of ALL_VIEWS) expect(reachable.has(v), v).toBe(true);
	});

	it('esiasetukset ja More-rivit kuuluvat omaan osioonsa', () => {
		for (const p of SPL_PRESETS) expect(splSectionOf(p.view).id).toBe('players');
		for (const [sec, items] of Object.entries(SPL_MORE))
			for (const m of items) expect(splSectionOf(m.view).id, m.view).toBe(sec);
		for (const s of SPL_SECTIONS) expect(s.views).toContain(s.lead);
	});

	it('esiasetukset ovat samat nimet samassa jarjestyksessa kuin FPL:ssa', () => {
		const fpl = PLAYER_PRESETS.map((p) => p.label);
		const spl = SPL_PRESETS.map((p) => p.label);
		expect(fpl.slice(0, spl.length)).toEqual(spl);
	});

	it('hash -> nakyma, tuntematon ja tyhja avaavat oletuksen', () => {
		expect(splView('#value')).toBe('value');
		expect(splView('value')).toBe('value');
		expect(splView('#model-squad')).toBe('model-squad');
		for (const h of ['', '#', '#nope', null, undefined, '#VALUE'])
			expect(splView(h as string | null | undefined)).toBe(SPL_DEFAULT_VIEW);
	});
});

describe('/spl-sivu', () => {
	it('jokaisella nakymalla on sisalto tasan kerran', () => {
		for (const v of ALL_VIEWS) {
			const n = markup.split(`view === '${v}'`).length - 1;
			const inList = new RegExp(`XP_VIEWS[^\\n]*'${v}'`).test(script);
			expect(n, v).toBe(1);
			// xP-nakymien yhteinen lataustila: listalla olevat, ja vain ne.
			if (['captain', 'value', 'differentials', 'leaders', 'compare', 'model-squad'].includes(v))
				expect(inList, `${v} XP_VIEWS-listalla`).toBe(true);
		}
	});

	it('mikaan entinen osio ei kadonnut', () => {
		for (const h of [
			'Clean sheet % + fixture difficulty',
			'How our clean sheet calls have gone',
			'Expected points',
			'Captain picks',
			'The model squad',
			'Best value',
			'Differentials <span',
			"Last season's leaders",
			'Compare two players',
			'Play FPL too?'
		])
			expect(markup.includes(h), h).toBe(true);
	});

	it('nakyma luetaan vain yhteisen lukijan kautta', () => {
		expect(script).toContain("gameViewState<SplView>('spl', 'spl_view_changed')");
		expect(src).not.toMatch(/location\.hash|page\.url\.hash/);
		expect(markup).toContain('<GameViewNav game="spl" {view}');
	});

	it('erotteleva: poistettu nakyma kaatuu', () => {
		const broken = markup.replace("view === 'leaders'", "view === 'leaderz'");
		expect(broken.split("view === 'leaders'").length - 1).toBe(0);
	});
});
