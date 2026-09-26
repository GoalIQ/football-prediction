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
	/** final / awaiting_check / unknown (kesken oleva ei ole mukana). */
	state: 'final' | 'awaiting_check' | 'unknown';
	matched: number;
}

export interface LedgerView {
	graded: number;
	projected: number;
	actual: number;
	diff: number;
	/** FPL:n kierroskeskiarvojen summa samoilta kierroksilta, null = ei vertailua. */
	fplAverage: number | null;
	bars: LedgerBar[];
	/** Pylvasasteikon puolikorkeus (suurin |diff|, vahintaan 1). */
	maxAbs: number;
	missing: number[];
	inProgress: number[];
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
		state: (g.state ?? (g.provisional ? 'unknown' : 'final')) as LedgerBar['state'],
		matched: g.players_matched
	}));
	return {
		graded: bars.length,
		projected: t.projected,
		actual: t.actual,
		diff: t.diff,
		fplAverage: typeof t.fpl_average === 'number' ? t.fpl_average : null,
		bars,
		maxAbs: Math.max(1, ...bars.map((b) => Math.abs(b.diff))),
		missing: [...(r.meta.missing_freeze_gws ?? [])].sort((a, b) => a - b),
		inProgress: [...(r.meta.in_progress_gws ?? [])].sort((a, b) => a - b),
		provisional: bars.filter((b) => b.state !== 'final').map((b) => b.gw),
		partial: bars.filter((b) => b.matched < 15).map((b) => ({ gw: b.gw, matched: b.matched }))
	};
}

/** Etumerkillinen yhden desimaalin luku: +179.8 / -12.4 / 0.0. */
export function signed(n: number): string {
	const v = r1(n);
	return `${v > 0 ? '+' : ''}${v.toFixed(1)}`;
}

/** Kokonaisluku etumerkilla: +169 / -31 / 0. */
export function signedInt(n: number): string {
	const v = Math.round(n);
	return `${v > 0 ? '+' : ''}${v}`;
}

/** Kiinni olevan taitoksen rivi: luku ja kierrosmaara samasta nakymasta.
 *  Julkaisutarkistaja k2 (C2): useimmat nakevat vain taman rivin, joten
 *  vertailukohta (FPL:n keskiarvo) kuuluu tahan. Ilman keskiarvoa ei
 *  etumerkkia: plus projektiota vastaan oli oletustila, ei signaali. */
export function ledgerSummary(v: LedgerView): string {
	const gws = v.graded === 1 ? '1 gameweek' : `${v.graded} gameweeks`;
	if (v.fplAverage != null) {
		return `${signed(v.diff)} vs the projection, ${signedInt(v.actual - v.fplAverage)} vs the FPL average, over ${gws}`;
	}
	return `${v.actual} points over ${gws} against a projection of ${r1(v.projected).toFixed(1)}`;
}

/** Avatun taitoksen paalause: omat pisteet, projektio ja FPL:n keskiarvo
 *  (julkaisutarkistaja 26.9 B4: ilman vertailukohtaa plus oli oletustila).
 *  Keskiarvo-osa jaa pois jos yhdellekin kierrokselle ei ole keskiarvoa. */
export function ledgerHeadline(v: LedgerView): string {
	const base = `You scored ${v.actual} over these gameweeks. The projection said ${r1(v.projected).toFixed(1)}`;
	return v.fplAverage != null ? `${base}, and the FPL average was ${v.fplAverage}.` : `${base}.`;
}

export function barTooltip(b: LedgerBar): string {
	return `GW${b.gw}: projected ${r1(b.projected).toFixed(1)}, scored ${b.actual}, ${signed(b.diff)}${b.state !== 'final' ? ' (provisional)' : ''}`;
}

const gwList = (gws: number[]) => gws.map((g) => `GW${g}`).join(', ');

/** Varaumat jotka kuuluvat lukuun (ei piiloteta). */
export function ledgerNotes(v: LedgerView): string[] {
	const out: string[] = [];
	if (v.missing.length) {
		out.push(`Not included: ${gwList(v.missing)}, because we couldn't pair a frozen projection with your picks.`);
	}
	for (const gw of v.inProgress) out.push(`GW${gw} is still being played, so it isn't included yet.`);
	// Sama kolmen tilan teksti kuin SeasonRacessa (model-race), ei omaa mekanismia.
	for (const b of v.bars) {
		if (b.state === 'awaiting_check') {
			out.push(`GW${b.gw}: played but not confirmed, so bonus points can still change these totals.`);
		} else if (b.state === 'unknown') {
			out.push(`GW${b.gw}: not confirmed yet, so these totals can still move.`);
		}
	}
	for (const p of v.partial) {
		out.push(`GW${p.gw}: ${p.matched} of your 15 had a frozen projection.`);
	}
	return out;
}
