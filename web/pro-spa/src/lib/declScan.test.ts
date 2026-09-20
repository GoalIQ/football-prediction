/**
 * `declScan` on lahdeportin se osa joka vastaa kysymykseen "mika NIMI tuottaa
 * taman rivin tekstin" (18.9). Jos se lukee sijoituksen rajat vaarin, portti
 * voi arvioida vaaran lausekkeen — siksi rajat testataan erikseen, ei vain
 * portin lopputuloksen kautta.
 */
import { describe, expect, it } from 'vitest';
import { declarations, declsAtLine } from './declScan';

const byName = (src: string, name: string) =>
	declarations(src).filter((d) => d.name === name);

describe('declarations', () => {
	it('yksirivinen let/const ja sen rivinumero', () => {
		const src = ['const a = 1;', 'let b = a + 2;'].join('\n');
		expect(declarations(src).map((d) => [d.name, d.from, d.to])).toEqual([
			['a', 1, 1],
			['b', 2, 2]
		]);
	});

	it('monirivinen $derived on YKSI vaite, ei kolme', () => {
		const src = [
			'let colsLabel = $derived(',
			'\tgwCols.length === 0',
			"\t\t? horizon.label",
			"\t\t: `GW${gwCols[0]}-GW${gwCols[gwCols.length - 1]}`",
			');'
		].join('\n');
		const [d] = byName(src, 'colsLabel');
		expect([d.from, d.to]).toEqual([1, 5]);
		expect(d.rhs).toContain('gwCols');
		expect(d.rhs).toContain('horizon.label');
	});

	it('rivinvaihto lausekkeen SISALLA ei katkaise sitoutumista', () => {
		const src = ['let x = $derived(', '\ta ??', '\t\tb', ');', 'let y = 2;'].join('\n');
		expect(byName(src, 'x')[0].to).toBe(4);
		expect(byName(src, 'y')[0].from).toBe(5);
	});

	it('Svelten {@const} tunnistetaan sijoitukseksi', () => {
		const src = '{@const claim = xpTotalClaim(meta, tot)}';
		const [d] = byName(src, 'claim');
		expect(d.rhs).toContain('xpTotalClaim(meta, tot)');
	});

	it('merkkijonon sisalla oleva puolipiste tai sulku ei katkaise lauseketta', () => {
		const src = "const s = fmt('a;b)', 2);\nconst t = 1;";
		expect(byName(src, 's')[0].rhs).toContain("'a;b)'");
		expect(byName(src, 't')[0].from).toBe(2);
	});

	it('kommentti lausekkeen sisalla ei paase rhs:aan', () => {
		const src = ['let n = $derived(', '\t// gwCols.length olisi vaarin', '\thorizon.count', ');'].join(
			'\n'
		);
		const [d] = byName(src, 'n');
		expect(d.rhs).not.toContain('gwCols');
		expect(d.rhs).toContain('horizon.count');
	});

	it('funktiomaarittely on sijoitus jonka rhs on runko', () => {
		const src = ['function heat(v) {', '\treturn v / heatMax;', '}'].join('\n');
		const [d] = byName(src, 'heat');
		expect(d.rhs).toContain('heatMax');
		expect([d.from, d.to]).toEqual([1, 3]);
	});

	it('paljas sijoitus rivin alussa tunnistetaan', () => {
		expect(byName('\thorizonLabel = colsLabel;', 'horizonLabel')[0].rhs.trim()).toBe('colsLabel');
	});

	it('vertailua ei luulla sijoitukseksi', () => {
		expect(declarations('if (a === b) { }').map((d) => d.name)).toEqual([]);
	});
});

describe('declsAtLine', () => {
	it('palauttaa sijoitukset jotka kattavat rivin', () => {
		const src = ['let a = $derived(', '\tb + c', ');', 'let d = 1;'].join('\n');
		const decls = declarations(src);
		expect(declsAtLine(decls, 2).map((d) => d.name)).toEqual(['a']);
		expect(declsAtLine(decls, 4).map((d) => d.name)).toEqual(['d']);
	});

	it('tunnistamaton muoto jaa sijoituksettomaksi (fail-closed)', () => {
		expect(declsAtLine(declarations('<p>text</p>'), 1)).toEqual([]);
	});
});
