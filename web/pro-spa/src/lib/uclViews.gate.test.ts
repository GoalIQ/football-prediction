/**
 * Portti: UCL Fantasy -sivun (/ucl) rakenne ja yhteinen nakymatila (23.9,
 * UCL-MENUT + julkaisutarkistajan RSL-korjaus).
 *
 * Villen valinta 23.9: UCL saa saman rakenteen kuin FPL ja RSL. Palkissa
 * Players | Teams, Players-osiossa FPL:n esiasetukset ja Compare.
 *
 * Vartioidaan:
 *   1. jokaisella UCL-nakymalla on sisalto sivulla tasan kerran,
 *   2. molemmat sivut lukevat nakyman yhdesta lukijasta (`gameViewState`),
 *      joka vierittaa ylos kun palkin OSIO vaihtuu (tarkistajan k1-loydos:
 *      Captain y=450 -> Teams jai disclaimeriin), ei osion sisalla,
 *   3. UCL:n vanha valilehtirivi ei palaa (kaksi valitsinta samasta asiasta),
 *   4. Teams-nakyma lukee artefaktin `teams`-lohkoa, ei laske CS%:aa itse.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { GAME_VIEWS, PLAYER_PRESETS, gameSectionOf, gameView, sectionChanged } from './tools';
import { blankComments } from './sourceScan';

const read = (rel: string) =>
	readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n');
const src = read('../routes/ucl/+page.svelte');
const markup = blankComments(src.slice(src.lastIndexOf('</script>'), src.lastIndexOf('<style>')));
const script = src.slice(0, src.lastIndexOf('</script>'));
const UCL = GAME_VIEWS.ucl;
const views = UCL.sections.flatMap((s) => s.views);

describe('UCL-rekisteri', () => {
	it('osiot Players | Teams, jokainen nakyma tasan yhdessa', () => {
		expect(UCL.sections.map((s) => s.label)).toEqual(['Players', 'Teams']);
		expect(new Set(views).size).toBe(views.length);
	});
	it('esiasetukset ovat FPL:n nimet samassa jarjestyksessa', () => {
		expect(UCL.presets.map((p) => p.label)).toEqual(
			PLAYER_PRESETS.slice(0, UCL.presets.length).map((p) => p.label)
		);
	});
	it('esiasetuksen nimessa ei ole GW-muotoista horisonttia (UCL:n kierros on matchday)', () => {
		expect(UCL.presets.some((p) => p.horizon)).toBe(false);
	});
	it('oletus on xP-lista (ilmainen nakee sen kymmenen karkea, muut listat lukossa)', () => {
		expect(gameView('ucl', '')).toBe('xp');
		expect(gameView('ucl', '#nope')).toBe('xp');
		expect(gameView('ucl', '#clean-sheets')).toBe('clean-sheets');
	});
});

describe('/ucl-sivu', () => {
	it('jokaisella nakymalla on sisalto tasan kerran', () => {
		// 'xp' ja kolme listaa jakavat yhden taulukkopolun (playersList/pickView).
		expect(script).toMatch(/let playersList = \$derived\(view === 'xp' \|\| pickView !== null\)/);
		for (const v of ['captain', 'value', 'differentials'])
			expect(script, v).toMatch(new RegExp(`${v}: '${v}'`));
		for (const v of ['compare', 'clean-sheets'])
			expect(markup.split(`view === '${v}'`).length - 1, v).toBe(1);
		expect(views.sort()).toEqual(['captain', 'clean-sheets', 'compare', 'differentials', 'value', 'xp']);
	});
	it('vanha valilehtirivi on poissa ja valitsin on sivulla', () => {
		expect(markup).not.toContain('role="tablist"');
		expect(markup).not.toContain('UCL_VIEWS');
		expect(markup).toContain('<GameViewNav game="ucl" {view}');
	});
	it('Teams lukee artefaktin joukkuetason', () => {
		expect(script).toContain('xp?.teams ?? []');
		expect(markup).toContain('f.cs_pct');
	});
	it('nakyma yhdesta lukijasta', () => {
		expect(script).toContain("gameViewState<UclPageView>('ucl', 'ucl_view_changed')");
		expect(src).not.toMatch(/location\.hash|page\.url\.hash/);
	});
});

describe('yhteinen nakymatila (gameViewState)', () => {
	const gv = read('./gameView.svelte.ts');
	it('lukee hashin gameViewin kautta ja vierittaa vain osion vaihtuessa', () => {
		expect(gv).toContain('gameView(game, page.url.hash)');
		expect(gv).toMatch(/if \(sectionChanged\(game, view, v\)\) void tick\(\)\.then\(\(\) => window\.scrollTo\(0, 0\)\)/);
	});
	it('osion vaihto: palkin kohta vaihtuu -> kylla, esiasetus osion sisalla -> ei', () => {
		expect(sectionChanged('spl', 'captain', 'clean-sheets')).toBe(true);
		expect(sectionChanged('spl', 'captain', 'model-squad')).toBe(true);
		expect(sectionChanged('spl', 'captain', 'value')).toBe(false);
		expect(sectionChanged('spl', 'clean-sheets', 'accuracy')).toBe(false);
		expect(sectionChanged('ucl', 'xp', 'clean-sheets')).toBe(true);
		expect(sectionChanged('ucl', 'xp', 'compare')).toBe(false);
	});
	it('erotteleva: jos osio luettaisiin vaarasta pelista, tulos muuttuisi', () => {
		expect(gameSectionOf('ucl', 'accuracy').id).toBe('players'); // tuntematon -> ensimmainen
		expect(sectionChanged('spl', 'accuracy', 'clean-sheets')).toBe(false);
	});
});
