/** fmtPct = backendin src/models/fmt.py fmt_pct (sama merkkijono molemmilla pinnoilla). */
import { describe, expect, it } from 'vitest';
import { fmtPct } from './fmt';

describe('fmtPct', () => {
	it('yksi desimaali, .0 pois (sama kuin fmt_pct)', () => {
		expect(fmtPct(48.1)).toBe('48.1%');
		expect(fmtPct(0.481 * 100)).toBe('48.1%');
		expect(fmtPct(51.0)).toBe('51%');
		expect(fmtPct(49.43)).toBe('49.4%');
		expect(fmtPct(100)).toBe('100%');
		expect(fmtPct(50, 0)).toBe('50%');
		expect(fmtPct(0)).toBe('0%');
		// Tasapisteet ylospain, sama kuin fmt_pct (Decimal ROUND_HALF_UP).
		expect(fmtPct(48.25)).toBe('48.3%');
		expect(fmtPct(46.25)).toBe('46.3%');
		expect(fmtPct(38.65)).toBe('38.6%');
	});
});
