/**
 * Fixtures -> Predict: ottelu kulkee URL:ssa, ei komponentin tilassa.
 *
 * 22.9.2026 (Ville: "kun painaa fixtures kohdasta predict ohjaa vaan predict
 * valilehdelle eika ennusta pelia"). ToolsHome piti ottelun omassa
 * `$state`issa ja navigoi sitten `/matches/predict`iin. Matches-tabi avautuu
 * ryhmasivulle `/matches` ([group]/+page.svelte), ja Predict on tyokalusivu
 * ([group]/[tool]/+page.svelte): reitti vaihtuu, AppShell ja ToolsHome
 * rakentuvat uudelleen ja tila katoaa. Suoraan /matches/fixtures-osoitteesta
 * polku toimi (sama reitti, komponentti kaytetaan uudelleen), joten vika
 * nakyi vain tavallisimmalla polulla (alapalkki -> Matches -> Predict).
 *
 * URL sailyy reitinvaihdossa ja ohjauksissa (molemmat reittisivut valittavat
 * `page.url.search`in), ja linkki on jaettava. Portti: predictLink.gate.test.ts.
 */

export type PredictPrefill = { league: string; home: string; away: string };

export const PREDICT_PATH = '/matches/predict';

export function predictHref(league: string, home: string, away: string): string {
	return `${PREDICT_PATH}?${new URLSearchParams({ league, home, away })}`;
}

/** Esitaytto URL:sta. Puuttuva tai tyhja kentta -> null (ei arvata). */
export function predictPrefillFrom(q: URLSearchParams): PredictPrefill | null {
	const league = q.get('league')?.trim();
	const home = q.get('home')?.trim();
	const away = q.get('away')?.trim();
	return league && home && away ? { league, home, away } : null;
}
