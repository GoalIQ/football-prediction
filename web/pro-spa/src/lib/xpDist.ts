/**
 * Pelaajakortin pistejakaumarivi (XP-DISTRIBUTION 27.8): yksi lukija sille,
 * milloin kattolause naytetaan.
 *
 * 29.9.2026 (kuvaverifiointi, Haaland GW6): kortti sanoi "14% chance of 10 or
 * more points" ja heti peraan "He goes past 10 in fewer than one week in ten".
 * Lause on nyt "no more than one week in ten" (julkaisutarkistaja k1 B3:
 * p90 = int(percentile(2000 simulaatiota, 90)), joten P(X > p90) <= 10 %,
 * ei aidosti alle). Silla muodolla lauseet tormaavat VAIN kun p90 on tasan
 * pisterajalla: p90 < raja -> P(>=raja) <= P(>p90) <= 10 %, p90 > raja ->
 * eri pisteluku. Tasan rajalla P(>=raja) on aina yli 10 %.
 */

/** Oletusraja jos payload ei kanna omaa (`xp_dist.haul_pts`, fpl_xp.DIST_HAUL_PTS). */
export const HAUL_POINTS = 10;

export function showCeiling(
	p90: number | null | undefined,
	haulPts: number | null | undefined = HAUL_POINTS
): boolean {
	const raja = typeof haulPts === 'number' && Number.isFinite(haulPts) ? haulPts : HAUL_POINTS;
	return typeof p90 === 'number' && Number.isFinite(p90) && p90 !== raja;
}
