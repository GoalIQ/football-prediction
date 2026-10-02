/**
 * lib/defconBasis.ts - DefCon-listan oletusbasis kauden vaiheesta
 * (2.10.2026, Villen mobiilikatselmus).
 *
 * 30.7 paatos oli oikea esikaudelle: koko kausi (38 pelin hit-rate) on
 * vakain basis, kun "viimeiset N" olisi viime kauden mielivaltainen hanta.
 * Mutta paatos oli kiintea, joten GW6:lla ensimmainen nakyma oli yha
 * 2025/26-lista (Anderson MCI, 37 aloitusta) vaikka kuluvan kauden
 * viimeiset 5 olivat saatavilla. Vaihe tulee palvelimelta (sama
 * fpl_player_leaders-builder kuin xG-listalla), ei klientin kellosta:
 * `is_prev_season_basis` ja `season_finished_gws`.
 *
 * Puhdas moduuli: $lib/defconBasis.gate.test.ts ajaa sen synteettisilla
 * vaiheilla (CLAUDE.md 6a kohta 3). Pariteetti: goaliq-app lib/defconBasis.ts.
 */
export type DefconBasis = 'recent' | 'season';

export interface LeadersPhase {
  is_prev_season_basis?: boolean;
  season_finished_gws?: number;
}

/** Oletusbasis: kuluvan kauden ikkuna vasta kun ikkuna on taynna pelattuja kierroksia. */
export function defconDefaultBasis(meta: LeadersPhase | null | undefined, window: number): DefconBasis {
  if (!meta || meta.is_prev_season_basis) return 'season';
  return (meta.season_finished_gws ?? 0) >= window ? 'recent' : 'season';
}
