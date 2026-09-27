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

export const TC_ASSUMPTION =
	"Each row assumes the best captain in that gameweek's XI, not the captain you have picked now.";

export const TC_PICK_LABEL = 'Best Triple Captain week for';

/** Valitun pelaajan rivi: "Haaland: GW7, +8.4 xP est." */
export function tcPickLine(c: Pick<TcCandidate, 'web_name' | 'best_gw' | 'best_xp'>): string {
	return `${c.web_name}: GW${c.best_gw}, +${c.best_xp.toFixed(1)} xP est.`;
}
