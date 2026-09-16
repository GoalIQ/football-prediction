import { shareCompareCard, type ShareOutcome } from '$lib/shareCard';
import { teamColorByShort } from '$lib/teamColors';
import { startPct } from '$lib/startPct';
import type { CompareResponse, ComparePlayer } from '$lib/fantasyTools';

/* YKSI LUKIJA vertailukortille (16.9).
 *
 * MIKSI OMA MODUULI: kortti rakennettiin ComparePlayers.svelten sisalla, ja
 * 16.9 xP-lista sai oman "vertaa valitut" -napin. Kaksi rakentajaa samalle
 * kortille tarkoittaa etta toinen jaa jalkeen seuraavassa muutoksessa —
 * tasan se vika joka toistui korttisaatteissa samana paivana (sama teksti
 * kahdessa repossa). Nyt molemmat pinnat kutsuvat tata.
 *
 * Kortin sisalto seuraa dataa: rivit jotka vaativat kaikilta pelaajilta luvun
 * (DefCon, xG/90) jaavat pois kun yksikin puuttuu, koska puolikas vertailu
 * lukisi vertailuna.
 */
export function compareCardSpec(data: CompareResponse) {
	const rows = data.players;
	const best = (vals: (number | null | undefined)[]): number | null => {
		const max = Math.max(...vals.map((v) => (v == null ? -Infinity : v)));
		if (!Number.isFinite(max)) return null;
		return vals.findIndex((v) => v === max);
	};
	return {
			title: 'PLAYER COMPARISON',
			subtitle: `next ${data.meta.horizon_gw ?? 6} gameweeks, GoalIQ match model`,
			fileName: 'goaliq_player_comparison.png',
			players: rows.map((p) => {
				const tc = teamColorByShort(p.team_short);
				return {
					name: p.web_name,
					team: p.team_short,
					color: tc.color,
					textColor: tc.textColor,
					pos: p.pos
				};
			}),
			stats: [
				/* 16.9: sivussa oleva pelaaja voi olla vertailussa mukana, eika
				   hanella ole mallin lukua. Kortti sanoo "no xP", ei jata
				   tyhjaksi eika korvaa nollalla — nolla nayttaisi mitatulta
				   luvulta juuri siina muodossa joka jaetaan kuvana.
				   EI sanaa "out": se olisi kierrokseton vaite "xP 6 GWS"
				   -rivin vieressa, eli tasan se muoto jonka portti hylkasi
				   16.9 Replacements-kortilta. */
				{
					label: 'xP / GW',
					values: rows.map((p) => (p.xp_per_gw != null ? p.xp_per_gw.toFixed(2) : 'no xP')),
					bestIndex: best(rows.map((p) => p.xp_per_gw))
				},
				{
					label: `xP ${data.meta.horizon_gw ?? 6} GWS`,
					values: rows.map((p) =>
						p.xp_horizon_total != null ? p.xp_horizon_total.toFixed(1) : 'no xP'
					),
					bestIndex: best(rows.map((p) => p.xp_horizon_total))
				},
				{
					label: 'PRICE',
					values: rows.map((p) => p.price.toFixed(1)),
					bestIndex: null
				},
				/* 6.8 (Ville): VALUE tekee hinnasta kannanoton — xP koko
				 * horisontilta per miljoona. Tälle amber kuuluu. */
				{
					label: 'xP / £m',
					values: rows.map((p) =>
						p.price > 0 && p.xp_horizon_total != null
							? (p.xp_horizon_total / p.price).toFixed(2)
							: '-'
					),
					bestIndex: best(
						rows.map((p) =>
							p.price > 0 && p.xp_horizon_total != null
								? p.xp_horizon_total / p.price
								: null
						)
					)
				},
				{
					label: 'OWNED',
					values: rows.map((p) => (p.owned_pct != null ? `${p.owned_pct.toFixed(1)}%` : '-')),
					bestIndex: null
				},
				{
					label: 'START %',
					values: rows.map((p) => {
						const sp = startPct(p);
						return sp != null ? `${sp}%` : '-';
					}),
					bestIndex: best(rows.map((p) => startPct(p)))
				},
				/* 6.8 V1 (Villen idea): pelipaikkakohtaiset rivit kun KAIKKI samaa
				 * paikkaa. Luvut = xP-komponentit YHDELLE GW:lle (components_gw) —
				 * EI per-GW-keskiarvo, siksi GW-numero labelissa (komponenttisumma
				 * täsmää gameweeks[0].xp:hen, ei xp_per_gw:hen). Sama mobiilissa. */
				...(new Set(rows.map((p) => p.pos)).size === 1 &&
				rows.every((p) => p.components != null && p.components_gw != null)
					? (
							({
								GKP: [
									['saves', 'SAVES xP'],
									['clean_sheet', 'CS xP']
								],
								DEF: [
									['clean_sheet', 'CS xP'],
									['defensive_contribution', 'DEFCON xP']
								],
								/* 6.8b (Ville): DefCon myös MID/FWD:lle — 12 CBIRT-kynnys
								 * sisältää recoveryt ja leaders-listan kärkikin on MID. */
								MID: [
									['goals', 'GOALS xP'],
									['assists', 'ASSISTS xP'],
									['defensive_contribution', 'DEFCON xP'],
									['bonus', 'BONUS xP']
								],
								FWD: [
									['goals', 'GOALS xP'],
									['assists', 'ASSISTS xP'],
									['defensive_contribution', 'DEFCON xP'],
									['bonus', 'BONUS xP']
								]
							}[rows[0].pos] ?? []) as [string, string][]
						).map(([key, label]) => {
							const vals = rows.map((p) => p.components?.[key] ?? 0);
							return {
								label: `${label} GW${rows[0].components_gw}`,
								values: vals.map((v) => v.toFixed(2)),
								bestIndex: best(vals)
							};
						})
					: []),
				/* V2: raakastatit backendista kun kaikilla on ne — DEFCON HIT näkyy
				 * AINA kun jokaisella on hit rate (myös MID/FWD: 12 CBIRT sisältää
				 * recoveryt; leaders-lista rankkaa samat positiot yhdessä). */
				...(rows.every((p) => p.defcon_hit_rate_pct != null)
					? [
							{
								label: 'DEFCON HIT',
								values: rows.map((p) => `${Math.round(p.defcon_hit_rate_pct as number)}%`),
								bestIndex: best(rows.map((p) => p.defcon_hit_rate_pct))
							}
						]
					: []),
				...(rows.every((p) => p.pos === 'MID' || p.pos === 'FWD') &&
				rows.every((p) => p.xg90_prev != null)
					? [
							{
								label: `xG/90 ${rows[0].prev_season ?? 'prev'}`,
								values: rows.map((p) => (p.xg90_prev as number).toFixed(2)),
								bestIndex: best(rows.map((p) => p.xg90_prev))
							},
							{
								label: `xA/90 ${rows[0].prev_season ?? 'prev'}`,
								values: rows.map((p) => (p.xa90_prev as number).toFixed(2)),
								bestIndex: best(rows.map((p) => p.xa90_prev))
							}
						]
					: [])
			],
			verdict: data.verdict.text
		};
}

export async function shareCompare(data: CompareResponse): Promise<ShareOutcome> {
	return shareCompareCard(compareCardSpec(data));
}
