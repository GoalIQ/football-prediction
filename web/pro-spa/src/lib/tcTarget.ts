/**
 * TC-TARGET-PLAYER (27.9.2026): Triple Captain -rivin kapteeni ja
 * pelaajavalitsimen tekstit. YKSI lukija (saanto 6a) SPA:lle; mobiilin
 * vastine goaliq-app lib/tcTarget.ts (englanninkieliset tekstit identtiset).
 *
 * TAUSTA: Ville vaihtoi 2.9 kentalla kapteenin Fernandesista Haalandiin eika
 * TC-ehdotus muuttunut. Laskenta on tarkoituksella XI:n paras kapteeni, mutta
 * ruutu ei sanonut sita, joten se naytti rikkinaiselta.
 */
import type { ChipWindow, TcCandidate } from './fantasyTools';

/** Rivin loppuosa: " · Haaland". Tyhja kun nimea ei ole (skaalattu rivi,
 *  maskattu vastaus): tyhja ei vaita mitaan. */
export function tcRowSuffix(w: Pick<ChipWindow, 'tc_player'>): string {
	return w.tc_player?.web_name ? ` · ${w.tc_player.web_name}` : '';
}

// Julkaisutarkistaja 27.9 k2: "Each row assumes..." ei pateny skaalatuille
// (GW26*) riveille joilla ei ole XI:ta, ja "X, not Y" on koneen rakenne.
export const TC_ASSUMPTION =
	"Each named captain is the highest-xP player in that gameweek's XI, so changing your captain won't change these numbers.";

/** Valitsin laskee vain pelaajaprojektion horisontin (meta.horizon_gws), joten
 *  label sanoo sen: muuten "best week" luettaisiin koko kauden parhaaksi,
 *  vaikka samalla kortilla on korkeampia skaalattuja GW26*-riveja. */
export function tcPickLabel(horizon: number[] | null | undefined): string {
	const gws = (horizon ?? []).filter((g) => Number.isFinite(g));
	if (gws.length === 0) return 'Best Triple Captain week for';
	return `Best Triple Captain week in GW${Math.min(...gws)}-${Math.max(...gws)} for`;
}

/** Valitun pelaajan rivi: "Haaland: GW7, +8.4 xP est." */
export function tcPickLine(c: Pick<TcCandidate, 'web_name' | 'best_gw' | 'best_xp'>): string {
	return `${c.web_name}: GW${c.best_gw}, +${c.best_xp.toFixed(1)} xP est.`;
}
