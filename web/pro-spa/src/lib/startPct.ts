/**
 * Start% yhdesta lahteesta (COMPARE-START-PCT 29.8, START-PCT-KAKSOISPYORISTYS 27.8).
 *
 * `p_start` (0..1) on ainoa lahde; pyoristys Math.round = floor(x+0.5), sama
 * kuin sivujen `start_pct()`. `predicted_starts` on backendin kerran pyoristama
 * prosentti (esim. 91.5) ja siita pyoristaminen antoi 92 kun sivut nayttivat 91
 * (Rogers, Khusanov, Hinshelwood, Dewsbury-Hall mitattu 27.8). Se on vain
 * fallback vanhalle payloadille jossa p_start puuttuu.
 */
export function startPct(p: {
	p_start?: number | null;
	predicted_starts?: number | null;
}): number | null {
	if (typeof p.p_start === 'number') return Math.round(p.p_start * 100);
	if (typeof p.predicted_starts === 'number') return Math.round(p.predicted_starts);
	return null;
}
