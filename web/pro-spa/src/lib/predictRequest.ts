/**
 * YKSI LUKIJA ennustepyynnolle (23.9.2026, UEFA Nations League webiin).
 *
 * Seuraliigat -> POST /api/predict (seuramalli, top_n premium-tilan mukaan).
 * Maajoukkueet (SpaLeague.national) -> POST /api/predict-wc omalla mallillaan.
 * Liigakoodi kulkee AINA mukana: ilman sita predict-wc olettaa World Cupin ja
 * hylkaa UNL-maat (sama vika joka loytyi mobiilista 23.9, lib/nationalPredict.ts).
 */
import { findLeague } from './leagues';

export function predictRequest(
	league: string,
	home: string,
	away: string,
	topN: number
): { path: string; body: Record<string, unknown> } {
	if (findLeague(league)?.national) {
		return {
			path: '/api/predict-wc',
			body: { home_team: home, away_team: away, leagues: [league] }
		};
	}
	return {
		path: '/api/predict',
		body: { home_team: home, away_team: away, leagues: [league], top_n: topN }
	};
}
