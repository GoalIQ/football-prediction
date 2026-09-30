/**
 * Portti: datapohja kertoo maali- ja syottovauhdin otoksesta (30.9.2026,
 * MOBIILI-DATAPOHJA-LABEL). Ks. $lib/dataBasis. Testi mittaa lukijan
 * (tunnetut arvot, tuntematon -> null) ja KUTSUPAIKAT: XpTablen tagi ja
 * valitun pelaajan rivi seka PlayerCard kayttavat samaa lukijaa, eika
 * minuuttirivi enaa liita datapohjaa aloitus-tn:n peraan. Vanhan tekstin
 * ("No PL data yet") paluun estaa data/rejected_phrases.json.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { DATA_BASIS_LABEL, basisRatesLine, basisTag } from './dataBasis';
import { blankComments } from './sourceScan';

const lue = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'));

describe('lukija', () => {
	it('jokainen tunnettu datapohja saa rivin', () => {
		for (const b of ['pl_history', 'limited_history', 'no_history']) {
			expect(basisRatesLine(b)).toBe(`Goal and assist rates: ${DATA_BASIS_LABEL[b]}.`);
		}
	});
	it('tagi vain priorinvaraisille riveille', () => {
		expect(basisTag('pl_history')).toBeNull();
		expect(basisTag('limited_history')?.label).toBe('Thin PL sample');
		expect(basisTag('no_history')?.label).toBe('No recent PL minutes');
	});
	it('tuntematon tai puuttuva arvo ei nayta mitaan (ei raakaa arvoa)', () => {
		for (const v of [undefined, null, '', 'full', 'toString', 42]) {
			expect(basisRatesLine(v)).toBeNull();
			expect(basisTag(v)).toBeNull();
		}
	});
	it('no_history ei vaita ettei PL-dataa viela ole', () => {
		const t = basisTag('no_history')!;
		expect(`${t.label} ${t.title} ${DATA_BASIS_LABEL.no_history}`).not.toMatch(/\byet\b/i);
	});
	it('no_history: vauhti NOJAA keskiarvoon, ei ole se (joukkuekerroin, tarkistaja 30.9)', () => {
		const t = basisTag('no_history')!;
		// Vanhan yhtasuuruusmuodon paluun estaa data/rejected_phrases.json.
		for (const s of [t.title, DATA_BASIS_LABEL.no_history]) {
			expect(s).toMatch(/use the position average/);
		}
	});
});

describe('kutsupaikat', () => {
	const xt = lue('./components/XpTable.svelte');
	const pc = lue('./components/PlayerCard.svelte');
	it('XpTablen tagi kayttaa lukijaa', () => {
		expect(xt).toContain('{#if basisTag(p.data_basis)}');
		expect(xt).toContain('title={basisTag(p.data_basis)?.title}');
		expect(xt).toContain('{basisTag(p.data_basis)?.label}');
	});
	it('minuuttirivi ei liita datapohjaa, se on oma lauseensa', () => {
		const i = xt.indexOf('Minutes outlook for');
		const j = xt.indexOf('</p>', i);
		expect(i).toBeGreaterThan(0);
		expect(xt.slice(i, j)).not.toMatch(/data_basis/);
		expect(xt.indexOf('basisRatesLine(selected.data_basis)', j)).toBeGreaterThan(j);
	});
	it('PlayerCard lukee saman taulun eika pida omaa kopiota', () => {
		expect(pc).toContain("import { DATA_BASIS_LABEL, basisRatesLine } from '$lib/dataBasis';");
		expect(pc).not.toMatch(/const DATA_BASIS_LABEL\b/);
	});
	it('PlayerCardin rivi on fail-closed (ei raakaa arvoa ruudulle)', () => {
		expect(pc).toContain('{#if basisRatesLine(player.data_basis)}');
		expect(pc).toContain('{basisRatesLine(player.data_basis)}</p>');
		expect(pc).not.toMatch(/DATA_BASIS_LABEL\[[^\]]+\]\s*\?\?/);
	});
});
