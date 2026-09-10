/**
 * MODEL-VS-CONSENSUS (10.9.2026, Villen GO). Rivi "FPL's own projection: x.
 * Ours: y." nakyy pelaajakortilla VAIN kun ero on merkittava.
 *
 * KYNNYS EI ASU TASSA. Se tulee payloadin `meta.projection_gap`-lohkosta,
 * jonka builderi johtaa gradatusta tarkkuuslokista (Python:
 * src/models/fpl_projection_gap.derive_threshold — perustelu ja mitattu
 * jakauma siella). Tama tiedosto on Pythonin `gap_state`-funktion
 * pariteettikopio, ja tests/test_fpl_projection_gap.py kaataa ajon jos tanne
 * ilmestyy oma numeerinen kynnys: silloin SPA ja builderi voisivat nayttaa
 * rivin eri saannolla.
 *
 * Fail-closed: puuttuva lohko, puuttuva FPL-luku, GW-epasuhta tai molemmat
 * nollassa -> null -> rivia ei renderoida. Ei oletusarvoa.
 */
export interface ProjectionGapThreshold {
	min_abs_xp: number;
	min_rel: number;
	basis_gw?: number;
	basis_n?: number;
	[key: string]: unknown;
}

export interface ProjectionGap {
	ours: number;
	fpl: number;
	gw: number;
}

function num(v: unknown): number | null {
	return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** Sama saanto kuin Python `gap_state`: |ours - fpl| >= min_abs_xp JA
 *  |ours - fpl| / max(ours, fpl) >= min_rel. */
export function projectionGap(
	ours: unknown,
	fpl: unknown,
	gw: unknown,
	thr: ProjectionGapThreshold | null | undefined
): ProjectionGap | null {
	if (!thr) return null;
	const minAbs = num(thr.min_abs_xp);
	const minRel = num(thr.min_rel);
	const o = num(ours);
	const f = num(fpl);
	const g = num(gw);
	if (minAbs == null || minRel == null || o == null || f == null || g == null) return null;
	const hi = Math.max(o, f);
	if (hi <= 0) return null;
	const gap = Math.abs(o - f);
	if (gap < minAbs || gap / hi < minRel) return null;
	return { ours: o, fpl: f, gw: g };
}
