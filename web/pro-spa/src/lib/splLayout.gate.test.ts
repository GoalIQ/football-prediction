/**
 * Portti: /spl ei hyppaa kun data saapuu (22.9, web-audit T1).
 *
 * 🔴 MITATTU 22.9 (`vite preview`, CDP layout-shift): CLS 0,646 puhelimella
 * (390x844, 4G + 4x CPU) ja 0,736-0,762 (1280x900). Kenttadatassa /spl
 * desktop p75 0,815. Kaksi syyta, kumpikin vartioidaan:
 *   1. deadline-rivi oli `{#if deadline}`, eli prerenderoidusta HTML:sta
 *      puuttui rivi, ja datan tullessa kaikki sen alla siirtyi 37-38 px,
 *   2. latausrivit olivat yhden rivin korkuisia, joten upsell ja footer
 *      olivat ensimmaisessa ruudussa ja CS-taulukko tyonsi ne pois.
 * Korjauksen jalkeen 0,001 (390) ja 0-0,05 (1280); jaljelle jaava 0,035 on
 * web-fontin vaihto (display=swap), ei datan saapuminen.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';

const SPL = fileURLToPath(new URL('../routes/spl/+page.svelte', import.meta.url));

function layoutProblems(src: string): string[] {
	const s = src.replace(/\r\n/g, '\n');
	const markup = blankComments(s.slice(s.lastIndexOf('</script>'), s.lastIndexOf('<style>')));
	const style = s.slice(s.lastIndexOf('<style>'));
	const p: string[] = [];
	const line = markup.indexOf('<p class="deadline">');
	const cond = markup.indexOf('{#if deadline}');
	if (line === -1) p.push('deadline-rivi puuttuu');
	else if (cond !== -1 && cond < line) p.push('deadline-rivi on {#if deadline} -ehdon sisalla');
	for (const data of ['cs', 'xp']) {
		const i = markup.indexOf(`{:else if !${data}}`);
		if (i === -1) {
			p.push(`latausehtoa {:else if !${data}} ei loytynyt (portti mittaisi tyhjaa)`);
			continue;
		}
		const next = markup.slice(i, markup.indexOf('{:else', i + 5));
		if (!next.includes('loading-reserve')) p.push(`!${data}-latausrivilta puuttuu korkeusvaraus`);
	}
	const rule = /\.loading-reserve\s*\{[^}]*min-height:\s*(\d+)px/.exec(style);
	if (!rule) p.push('.loading-reserve ilman min-heightia');
	else if (Number(rule[1]) < 400) p.push(`.loading-reserve ${rule[1]} px ei tyonna upsellia ruudun alle`);
	return p;
}

describe('/spl: sama asettelu ennen ja jalkeen datan', () => {
	const src = readFileSync(SPL, 'utf-8');

	it('nykyinen sivu on kunnossa', () => {
		expect(layoutProblems(src)).toEqual([]);
	});

	it('erotteleva kontrolli: vanha {#if deadline} -rivi kaatuu', () => {
		const old = src
			.replace(/\r\n/g, '\n')
			.replace(/<p class="deadline">\s*\{#if deadline\}/, '{#if deadline}<p class="deadline">');
		expect(layoutProblems(old)).toContain('deadline-rivi on {#if deadline} -ehdon sisalla');
	});

	it('erotteleva kontrolli: varaamaton latausrivi kaatuu', () => {
		const old = src.replace(/<p class="muted loading-reserve">Loading…<\/p>/g, '<p class="muted">Loading…</p>');
		expect(layoutProblems(old).filter((x) => x.includes('korkeusvaraus')).length).toBe(2);
	});
});
