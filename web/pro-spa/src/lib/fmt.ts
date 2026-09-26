/** Jaetut muotoilijat. Sama saanto kuin backendin src/models/fmt.py:
 *  `fmt_pct`: yksi desimaali, ".0" pois (51.0 -> "51%", 48.1 -> "48.1%").
 *  Sama luku renderoityy samana SPA:ssa ja goaliq.app-sivuilla, jotta lukija
 *  loytaa alaviitteen luvun linkin takaa sellaisenaan. */
export function fmtPct(x: number, decimals = 1): string {
	return `${x.toFixed(decimals).replace(/\.0+$/, '')}%`;
}
