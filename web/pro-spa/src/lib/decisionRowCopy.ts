/**
 * $lib/decisionRowCopy - paatos- ja hintarivien sanamuoto (2.10.2026,
 * Villen mobiilikatselmus; pariteetti goaliq-app lib/decisionRowCopy.ts).
 *
 * - Siirron hinta on HINTAERO nykyhinnoilla ("£0.2m cheaper"), ei
 *   pankkivaikutus: FPL maksaa myydysta pelaajasta myyntihinnan, jota
 *   rate-team ei kanna (julkaisutarkistaja 2.10 blokkasi "frees £0.2m").
 * - "N more on watch" vain kun ennen sita on jotain; muuten "N of your
 *   players on watch".
 */
export function transferCostText(deltaCost: number): string {
	const r = Math.round(deltaCost * 10) / 10;
	if (r > 0) return `£${r.toFixed(1)}m more expensive`;
	if (r < 0) return `£${(-r).toFixed(1)}m cheaper`;
	return 'same price';
}

export function transferWhy(deltaXp: number, deltaCost: number): string {
	return `+${deltaXp.toFixed(1)} xP over the horizon, ${transferCostText(deltaCost)}.`;
}

export function ownedWatchText(rest: number, precedingParts: number): string {
	return precedingParts > 0 ? `${rest} more on watch` : `${rest} of your players on watch`;
}
