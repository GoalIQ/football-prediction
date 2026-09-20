import { describe, expect, it } from 'vitest';
import { blankComments, codeLines, findInCode } from './sourceScan';

describe('blankComments', () => {
	it('sailyttaa rivimaaran ja rivinumerot', () => {
		const src = 'a\n/* x\ny */\nb // c\n<!-- d\ne -->\nf';
		const out = blankComments(src);
		expect(out.split('\n').length).toBe(src.split('\n').length);
		expect(codeLines(src).map((l) => [l.n, l.text.trim()])).toEqual([
			[1, 'a'],
			[4, 'b'],
			[7, 'f']
		]);
	});

	it('ei tulkitse URL-merkkijonon kaksoiskauttaviivaa kommentiksi', () => {
		const src = "const u = 'https://goaliq.app/fpl'; const k = 1;";
		expect(blankComments(src)).toBe(src);
	});

	it('kommentissa oleva vanha muoto ei osu porttiin, koodissa oleva osuu', () => {
		const src = [
			'// next {data.meta.horizon_gw ?? 6} GWs (poistettu 17.9)',
			'/* horizon_gw perustelu */',
			'<!-- horizon_gw markupissa -->',
			'const n = data.meta.horizon_gw ?? 6;'
		].join('\n');
		const hits = findInCode(src, /\bhorizon_gw\b/);
		expect(hits.map((h) => h.n)).toEqual([4]);
	});

	it('apostrofi markupissa ei piilota saman rivin koodia', () => {
		const src = "<p>it's {data.meta.horizon_gw} GWs</p>";
		expect(findInCode(src, /\bhorizon_gw\b/).length).toBe(1);
	});

	it('sulkematon lohkokommentti ulottuu tiedoston loppuun', () => {
		expect(blankComments('a /* b\nc').trim()).toBe('a');
	});
});
