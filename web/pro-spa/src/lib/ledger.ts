/** MP-14 (26.9.2026): oman joukkueen kausi jaadytettya projektiota vastaan.
 *
 * YKSI LUKIJA (saanto 6a) /api/fantasy/my-team-ledger -vastaukselle: otsikon
 * luku, lause, pylvaat ja taulukko tulevat tasta samasta nakymasta, joten lause
 * ja luku eivat voi tulla eri lahteesta. Mobiilin vastine: goaliq-app
 * lib/ledger.ts (sama saanto).
 *
 * Mita endpoint lupaa (src/models/fpl_my_team_ledger.py): projektio on
 * jaadytetty ennen deadlinea (ei elava), kerroin mukana molemmilla puolilla
 * (kapteeni tuplana, penkki 0), toteuma on netto hittien jalkeen. Kierros jolle
 * ei ole freezea jaa pois ja se kerrotaan; vajaa kattavuus (< 15 pelaajaa
 * freezessa) kerrotaan eika sita esiteta tayteena.
 */
import type { LedgerResponse } from './api';

export interface LedgerBar {
	gw: number;
	projected: number;
	actual: number;
	diff: number;
	provisional: boolean;
	matched: number;
}

export interface LedgerView {
	graded: number;
	projected: number;
	actual: number;
	diff: number;
	bars: LedgerBar[];
	/** Pylvasasteikon puolikorkeus (suurin |diff|, vahintaan 1). */
	maxAbs: number;
	missing: number[];
	provisional: number[];
	partial: { gw: number; matched: number }[];
}

const r1 = (n: number) => Math.round(n * 10) / 10;

export function ledgerView(r: LedgerResponse | null | undefined): LedgerView | null {
	if (!r?.meta?.available || !r.gameweeks?.length) return null;
	const t = r.totals;
	if (t?.projected == null || t.actual == null || t.diff == null) return null;
	const bars = r.gameweeks.map((g) => ({
		gw: g.gw,
		projected: g.projected,
		actual: g.actual,
		diff: g.diff,
		provisional: g.provisional === true,
		matched: g.players_matched
	}));
	return {
		graded: bars.length,
		projected: t.projected,
		actual: t.actual,
		diff: t.diff,
		bars,
		maxAbs: Math.max(1, ...bars.map((b) => Math.abs(b.diff))),
		missing: [...(r.meta.missing_freeze_gws ?? [])].sort((a, b) => a - b),
		provisional: bars.filter((b) => b.provisional).map((b) => b.gw),
		partial: bars.filter((b) => b.matched < 15).map((b) => ({ gw: b.gw, matched: b.matched }))
	};
}

/** Etumerkillinen yhden desimaalin luku: +179.8 / -12.4 / 0.0. */
export function signed(n: number): string {
	const v = r1(n);
	return `${v > 0 ? '+' : ''}${v.toFixed(1)}`;
}

/** Kiinni olevan taitoksen rivi: luku ja kierrosmaara samasta nakymasta. */
export function ledgerSummary(v: LedgerView): string {
	const gws = v.graded === 1 ? '1 gameweek' : `${v.graded} gameweeks`;
	return `${signed(v.diff)} points vs the projection over ${gws}`;
}

/** Avatun taitoksen paalause: molemmat summat, ero niiden valinen. */
export function ledgerHeadline(v: LedgerView): string {
	return `You scored ${v.actual}. The projection frozen before each deadline said ${r1(v.projected).toFixed(1)}.`;
}

export function barTooltip(b: LedgerBar): string {
	return `GW${b.gw}: projected ${r1(b.projected).toFixed(1)}, scored ${b.actual}, ${signed(b.diff)}${b.provisional ? ' (provisional)' : ''}`;
}

const gwList = (gws: number[]) => gws.map((g) => `GW${g}`).join(', ');

/** Varaumat jotka kuuluvat lukuun (ei piiloteta). */
export function ledgerNotes(v: LedgerView): string[] {
	const out: string[] = [];
	if (v.missing.length) {
		out.push(`Not included: ${gwList(v.missing)}. No projection was frozen before that deadline.`);
	}
	if (v.provisional.length) {
		out.push(`${gwList(v.provisional)} still provisional: FPL has not confirmed the points yet.`);
	}
	for (const p of v.partial) {
		out.push(`GW${p.gw}: ${p.matched} of your 15 had a frozen projection.`);
	}
	return out;
}
