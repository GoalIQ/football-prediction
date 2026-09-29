/**
 * MINILIIGA-JULKISUUSSAANTO (4.9.2026, portti 29.9.2026).
 *
 * Saanto: tuotteen sisalla liigan nimet nakyvat jasenille (kuten FPL:ssa),
 * mutta JULKISELLA pinnalla (jakokortti, X, video) toisen managerin
 * henkilonimea ei ole. Rival-kortti kayttaa joukkueen nimea (entry_name),
 * ja shareCard.ts sanoi sen kommentissa ("EI managerin nimi"). Kommentti ei
 * ole portti: tama testi kaatuu jos henkilonimi (player_name) paatyy
 * kortinpiirtajaan tai MiniLeague antaa rivalName-propiksi henkilonimen.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';

const lue = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'));

describe('jakokortti ei kanna toisen managerin henkilonimea', () => {
	it('kortinpiirtaja ei lue player_namea', () => {
		expect(lue('./shareCard.ts')).not.toMatch(/player_name/);
	});
	it('MiniLeague antaa rivalName-propiksi joukkueen nimen', () => {
		const src = lue('./components/MiniLeague.svelte');
		const m = src.match(/rivalName=\{([^}]+)\}/);
		expect(m).not.toBeNull();
		expect(m![1].trim()).toBe('rivalRow.entry_name');
	});
	it('RivalPanel valittaa korttiin vain propin rivalName', () => {
		const src = lue('./components/RivalPanel.svelte');
		const i = src.indexOf('shareRivalCard(');
		expect(i).toBeGreaterThan(0);
		expect(src.slice(i, i + 400)).not.toMatch(/player_name/);
	});
});
