/**
 * Pelaajakortin pistejakaumarivi (XP-DISTRIBUTION 27.8): yksi lukija sille,
 * milloin kattolause naytetaan.
 *
 * 29.9.2026 (kuvaverifiointi, Haaland GW6): kortti sanoi "14% chance of 10 or
 * more points" ja heti perään "He goes past 10 in fewer than one week in ten".
 * Molemmat ovat tosia (P(>=10) = 14 %, P(>10) < 10 %), mutta lukija nakee
 * 14 % ja "alle yhden kymmenesta" samasta pisterajasta. Ristiriidan nakoinen
 * pari syntyy AINA kun p90 on tasan pisterajan kohdalla: silloin P(>=raja)
 * on yli 10 %. Muilla p90:n arvoilla lauseet eivat tormaa (p90 < raja ->
 * P(>=raja) <= 10 %, p90 > raja -> eri pisteluku).
 */

/** Pisteraja jota rivin ensimmainen lause kayttaa ("10 or more points"). */
export const HAUL_POINTS = 10;

export function showCeiling(p90: number | null | undefined): boolean {
	return typeof p90 === 'number' && Number.isFinite(p90) && p90 !== HAUL_POINTS;
}
