import { describe, expect, it } from 'vitest';
import { MODEL_SERIES_COPY as C } from './modelSeriesCopy';

/* 21.9 (julkaisuportti + Villen GW4-paatos): selite EI saa nayttaa lukua jota
 * payload ei kanna, eika wildcard-muotoa ilman payloadin chippia. */
describe('MODEL_SERIES_COPY', () => {
	it('GW4: luku ja keskiarvo tulevat parametreista sellaisenaan', () => {
		const t = C.unscoredNoValidFreeze(4, 49, 69);
		expect(t).toContain('would have had 49, against an average of 69.');
	});
	it('GW4 ilman payloadin lukua: ei lukua lainkaan', () => {
		const t = C.unscoredNoValidFreeze(4, null, null);
		expect(t).not.toMatch(/would have had/);
		expect(t).not.toMatch(/\d{2}/);
		expect(t.startsWith('GW4: not scored.')).toBe(true);
	});
	it('GW4: puolikas luku (keskiarvo puuttuu) ei tuota lausetta', () => {
		expect(C.unscoredNoValidFreeze(4, 49, null)).not.toMatch(/49/);
	});
	it('reseed: wildcard-muoto vain kun payload sanoo wildcard', () => {
		expect(C.reseeded(3, 2, 'wildcard')).toContain('after we played a wildcard there in GW2');
		expect(C.reseeded(5, 4, null)).not.toMatch(/wildcard/);
		expect(C.reseeded(5, 4, '3xc')).not.toMatch(/wildcard/);
	});
	it('mallin vertailu sanoo hitit vahennetyiksi kun payload sanoo niin', () => {
		expect(C.modelVsAverage({ diff: -17, gameweeks: 3, hits_deducted: true })).toBe(
			'Model vs the FPL average: -17 over 3 gameweeks, hits deducted'
		);
	});
	it('saanto 6a: bruttoluvulle ei "hits deducted" -lausetta', () => {
		expect(C.modelVsAverage({ diff: -9, gameweeks: 3, hits_deducted: false })).toBeNull();
		expect(C.modelVsAverage({ diff: -9, gameweeks: 3 })).toBeNull();
		expect(C.modelVsAverage(null)).toBeNull();
	});
});
