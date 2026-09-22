/**
 * Lukitun FPL-tyokalun naytte (22.9.2026, web-audit T3, Villen GO).
 *
 * 🔴 MITATTU 22.9: kirjautumaton kavija joka avasi `/players/player-xp` naki
 * tyokalulistan ja tekstilaatikon "See Premium", ei yhtaan xP-rivia. Kuusi
 * yhdeksasta premium-tyokalusta (transfer planner, chip timing, transfer
 * chains, edge mode, replacements, compare) ei renderoinyt ei-maksajalle
 * MITAAN: URL avasi tyhjan nakyman. `/ucl` teki saman oikein: 10 rivin
 * ilmainen naytte ja hinta samassa kohdassa.
 *
 * SAANTO 6a KOHTA 1 (yksi lukija): lukitun nakyman paatos ja naytteen rivit
 * tulevat tasta tiedostosta, ei jokaisen tyokalun omasta haarasta. Uusi
 * premium-tyokalu saa naytteen ilman etta kukaan muistaa lisata sita.
 *
 * PALVELINMASKI ON TOTUUS. Naytteen rivit ovat tasmalleen ne jotka
 * `/api/fantasy/xp` antaa ei-maksajalle (`mask_xp_payload`: top 10
 * `xp_horizon_total`-jarjestyksessa). Tama tiedosto ei lajittele uudelleen,
 * ei hae muuta dataa eika keksi rivia. Jos palvelin joskus maskaa arvon
 * (kentta puuttuu), solu nayttaa lukkomerkin eika nollaa.
 */
import type { XpPlayer, XpResponse } from './api';
import type { Tool } from './tools';

/** Montako palvelimen ilmaisrivia naytetaan. Palvelin antaa kymmenen
 *  (`FREE_XP_TEASER_N`); viisi pitaa hinnan ja ostonapin puhelimen
 *  ensimmaisessa ruudussa (mitattu 390x844, raportti w-spa.md). */
export const PREVIEW_ROWS = 5;

/** Sama lukkomerkki kuin Paywall- ja PremiumPreview-teasereissa. */
export const LOCKED_VALUE = '•.••';

/** Lukittu tyokalu, tai null kun nakyma saa renderoida tyokalun itse.
 *  Ainoa ehto: premium-tyokalu ja kayttajalla ei ole oikeutta. */
export function lockedToolFor(tool: Tool | null | undefined, premium: boolean): Tool | null {
	return !premium && tool?.tier === 'premium' ? tool : null;
}

/** Naytteen rivit palvelimen jarjestyksessa. Tyhja kun dataa ei ole
 *  julkaistu (`meta.available` false) tai vastaus on vajaa. */
export function previewRows(
	xp: XpResponse | null | undefined,
	n: number = PREVIEW_ROWS
): XpPlayer[] {
	if (!xp?.meta?.available || !Array.isArray(xp.players)) return [];
	return xp.players.slice(0, Math.max(0, n));
}

/** Luku yhdella desimaalilla, tai lukkomerkki kun palvelin ei antanut sita. */
export function valueCell(v: unknown): string {
	return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(1) : LOCKED_VALUE;
}

/** Kierroksen xP-solu. Puuttuva `gameweeks` = maskattu (lukko). Olemassa
 *  oleva lista ilman kierrosta = tyhja kierros = 0 pistetta, sama saanto
 *  kuin `gwXp`:ssa ($lib/api). */
export function gwCell(p: XpPlayer, gw: number | undefined): string {
	if (!Array.isArray(p.gameweeks) || gw == null) return LOCKED_VALUE;
	const g = p.gameweeks.find((x) => x.gw === gw);
	return valueCell(g ? g.xp : 0);
}
